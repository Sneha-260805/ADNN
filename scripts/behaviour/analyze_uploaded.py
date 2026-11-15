"""Analyze supplied backups without altering their contents or rerunning models."""
import argparse
import csv
import hashlib
import json
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import cohen_kappa_score
from sklearn.pipeline import make_pipeline

from adnn.behaviour.analysis import behaviour_metrics
from adnn.behaviour.judgment import LABELS, classification_metrics
from adnn.dataset.api import load_dataset


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def table(path, rows):
    if rows:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def intervals(rows, group_key, resamples=1000):
    # Keep each scenario/pair together; use three fixed classes in every resample.
    label_index = {label: i for i, label in enumerate(LABELS)}
    grouped = {}
    for row in rows:
        cm = grouped.setdefault(row[group_key], np.zeros((3, 4), dtype=int))
        cm[label_index[row["label"]], label_index.get(row["prediction"], 3)] += 1
    matrices = np.asarray(list(grouped.values()))
    def score(cm):
        diagonal = cm[:, :3].diagonal()
        support = cm.sum(axis=1)
        recall = np.divide(diagonal, support, out=np.zeros(3), where=support != 0)
        denom = support + cm[:, :3].sum(axis=0)
        f1 = np.divide(2*diagonal, denom, out=np.zeros(3), where=denom != 0)
        return [diagonal.sum()/cm.sum(), recall.mean(), f1.mean()]
    rng = np.random.default_rng(42)
    scores = [score(matrices[rng.integers(len(matrices), size=len(matrices))].sum(axis=0))
              for _ in range(resamples)]
    bounds = np.quantile(scores, [.025, .975], axis=0)
    return {name: bounds[:, i].tolist()
            for i, name in enumerate(["accuracy", "balanced_accuracy", "macro_f1"])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--downloads", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("results/member3_verified_analysis"))
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    ds = load_dataset("data/production/v2.0")
    train, test = list(ds.iter_split("train")), list(ds.iter_split("test"))
    records = {r["id"]: r for r in test}
    majority = Counter(r["label"] for r in train).most_common(1)[0][0]
    lexical = make_pipeline(TfidfVectorizer(ngram_range=(1, 2)),
                            LogisticRegression(C=1, max_iter=2000, random_state=42))
    lexical.fit([r["action_text"] for r in train], [r["label"] for r in train])
    lexical_predictions = dict(zip([r["id"] for r in test],
                                  lexical.predict([r["action_text"] for r in test]), strict=True))
    qwen_text = subprocess.check_output([
        "git", "show", "origin/m2/rq1_qwen_llama:results/rq1_qwen/probes/"
        "qwen_v2_3class_test_predictions.jsonl"], text=True)
    probes = {
        "qwen": {r["record_id"]: r for r in map(json.loads, qwen_text.splitlines())},
        "llama": {r["record_id"]: r for r in map(json.loads,
            (args.downloads / "llama_v2_3class_predictions.jsonl").read_text().splitlines())},
    }
    classification, comparisons, behaviour, mechanisms, subgroups = [], [], [], [], []
    source_manifest = {}
    for model in ["qwen", "llama"]:
        paths = [args.downloads / f"{model}-{kind}-backup.zip" for kind in ["rq2", "full"]]
        for path in paths:
            source_manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with zipfile.ZipFile(paths[0]) as z:
            rows = [json.loads(l) for l in z.read("outcomes.jsonl").decode().splitlines()]
        assert len(rows) == len(records) and {r["example_id"] for r in rows} == set(records)
        for row in rows:
            assert row["label"] == records[row["example_id"]]["label"]
        metrics = classification_metrics(rows)
        ci = intervals(rows, "scenario_id")
        write_json(args.output / f"{model}_rq2_metrics.json", metrics | {"ci95": ci})
        for name in ["accuracy", "balanced_accuracy", "macro_f1"]:
            classification.append(dict(model=model, method="stated", metric=name,
                estimate=metrics[name], ci_low=ci[name][0], ci_high=ci[name][1], n=len(rows)))
        for method, predictions in {
            "train_majority": {k: majority for k in records},
            "always_irreversible": {k: "irreversible" for k in records},
            "always_reversible": {k: "reversible" for k in records},
            "always_partially_reversible": {k: "partially_reversible" for k in records},
            "action_text_tfidf": lexical_predictions,
        }.items():
            baseline = [dict(r, prediction=predictions[r["example_id"]]) for r in rows]
            bm, bc = classification_metrics(baseline), intervals(baseline, "scenario_id")
            for name in ["accuracy", "balanced_accuracy", "macro_f1"]:
                classification.append(dict(model=model, method=method, metric=name,
                    estimate=bm[name], ci_low=bc[name][0], ci_high=bc[name][1], n=len(rows)))
        for field in ["environment", "render_style"]:
            for value in sorted({r[field] for r in rows}):
                subset = [r for r in rows if r[field] == value]
                sm = classification_metrics(subset)
                subgroups.append(dict(model=model, field=field, value=value, n=len(subset),
                    accuracy=sm["accuracy"], balanced_accuracy=sm["balanced_accuracy"],
                    macro_f1=sm["macro_f1"]))
        paired = [r for r in rows if r.get("pair_id")]
        if paired:
            write_json(args.output / f"{model}_rq2_minimal_pair_subset.json",
                       classification_metrics(paired) | {"ci95": intervals(paired, "scenario_id")})
        pred = probes[model]
        assert set(pred) == set(records)
        assert all(pred[k]["true_label"] == records[k]["label"] for k in records)
        stated, probed = [r["prediction"] for r in rows], [pred[r["example_id"]]["predicted_label"] for r in rows]
        comparisons.append(dict(model=model, n=len(rows),
            agreement=float(np.mean(np.array(stated) == np.array(probed))),
            cohen_kappa=cohen_kappa_score(stated, probed, labels=list(LABELS))))
        table(args.output / f"{model}_rq2_joined_predictions.csv", [dict(
            example_id=r["example_id"], scenario_id=r["scenario_id"], truth=r["label"],
            stated=r["prediction"], probe=pred[r["example_id"]]["predicted_label"])
            for r in rows])
        with zipfile.ZipFile(paths[1]) as z:
            runs = [json.loads(l) for l in z.read("outcomes.jsonl").decode().splitlines()]
            stats = behaviour_metrics(runs)
            write_json(args.output / f"{model}_rq3_metrics.json", stats)
            for name, value in stats["outcomes"].items():
                behaviour.append(dict(model=model, metric=name, estimate=value["estimate"],
                    ci_low=value["ci95"][0], ci_high=value["ci95"][1], n_pairs=60))
            for mechanism in sorted({r["mechanism"] for r in runs}):
                for version in ["reversible", "irreversible"]:
                    subset = [r for r in runs if r["mechanism"]==mechanism and r["version"]==version]
                    mechanisms.append(dict(model=model, mechanism=mechanism, version=version,
                        n=len(subset), success=sum(r["task_success"] for r in subset),
                        cautious=sum(r["cautious"] for r in subset),
                        irreversible_execution=sum(r["took_irreversible_action"] for r in subset),
                        parsing_failures=sum(r["parse_failures"] for r in subset)))
    table(args.output / "rq2_scores_and_baselines.csv", classification)
    table(args.output / "rq2_probe_agreement.csv", comparisons)
    table(args.output / "rq2_subgroups.csv", subgroups)
    table(args.output / "rq3_comparison.csv", behaviour)
    table(args.output / "rq3_by_mechanism.csv", mechanisms)
    write_json(args.output / "source_archive_checksums.json", source_manifest)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for ax, metric in zip(axes, ["balanced_accuracy", "macro_f1"], strict=True):
        selected = [r for r in classification if r["method"]=="stated" and r["metric"]==metric]
        ax.bar([r["model"] for r in selected], [r["estimate"] for r in selected])
        for i, r in enumerate(selected): ax.plot([i, i], [r["ci_low"], r["ci_high"]], color="black")
        ax.set_ylim(0, 1); ax.set_title(metric.replace("_", " "))
    fig.suptitle("Stated judgments with scenario bootstrap intervals")
    fig.tight_layout();fig.savefig(args.output / "rq2_model_comparison.png", dpi=200);plt.close(fig)
    print(json.dumps({"probe_agreement": comparisons, "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
