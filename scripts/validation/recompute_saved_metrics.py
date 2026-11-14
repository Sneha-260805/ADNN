"""Recompute RQ1/RQ2/RQ3 metrics from saved predictions and replay RQ3 traces (read-only).

No model is loaded and nothing under results/ or data/ is written. The script compares
recomputed values with the values the team saved and reports every mismatch.

RQ1  (Member 2): balanced accuracy, accuracy, macro-F1, AUROC and confusion matrices are
     recomputed with scikit-learn from the saved test-set prediction files. If the frozen
     v2.0 dataset is present, prediction record IDs and gold labels are also checked
     against the official test split.
RQ2  (Member 3): ``adnn.behaviour.judgment.classification_metrics`` on saved outcomes.
RQ3  (Member 3): ``adnn.behaviour.analysis.behaviour_metrics`` on saved outcomes, and a
     deterministic replay: every saved per-task trace is fed back, raw model output by raw
     model output, through the *committed* ``adnn.behaviour.runner.run_task`` with the
     frozen rq3-tasks-1.0 tasks; prompts, sandbox states and outcome fields are compared.

Usage: python scripts/validation/recompute_saved_metrics.py [--root .] [--out report.json]
       [--skip-replay]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

TOL = 1e-9


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]


def compare(saved: Any, recomputed: Any, path: str = "") -> Iterator[str]:
    """Yield a message for every value in ``saved`` that ``recomputed`` does not reproduce."""
    if isinstance(saved, dict):
        if not isinstance(recomputed, dict):
            yield f"{path}: type differs"
            return
        for key, value in saved.items():
            if key not in recomputed:
                yield f"{path}.{key}: missing in recomputation"
            else:
                yield from compare(value, recomputed[key], f"{path}.{key}")
    elif isinstance(saved, list):
        if not isinstance(recomputed, list) or len(saved) != len(recomputed):
            yield f"{path}: list differs ({saved!r} vs {recomputed!r})"
            return
        for i, (a, b) in enumerate(zip(saved, recomputed, strict=True)):
            yield from compare(a, b, f"{path}[{i}]")
    elif isinstance(saved, float) or isinstance(recomputed, float):
        if saved is None or recomputed is None:
            if saved is not recomputed:
                yield f"{path}: {saved!r} vs {recomputed!r}"
        elif not math.isclose(float(saved), float(recomputed), abs_tol=TOL):
            yield f"{path}: saved {saved!r} vs recomputed {recomputed!r}"
    elif saved != recomputed:
        yield f"{path}: saved {saved!r} vs recomputed {recomputed!r}"


# ---------------------------------------------------------------- RQ1 ----


def _rq1_metrics(rows: list[dict[str, Any]], classes: list[Any], prob: Callable) -> dict:
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        confusion_matrix,
        f1_score,
        roc_auc_score,
    )

    y = [r["true_label"] for r in rows]
    p = [r["predicted_label"] for r in rows]
    out: dict[str, Any] = {
        "n": len(rows),
        "accuracy": accuracy_score(y, p),
        "balanced_accuracy": balanced_accuracy_score(y, p),
        "macro_f1": f1_score(y, p, average="macro", labels=classes),
        "per_class_f1": dict(
            zip(
                map(str, classes),
                f1_score(y, p, average=None, labels=classes).tolist(),
                strict=True,
            )
        ),
        "confusion_matrix": confusion_matrix(y, p, labels=classes).tolist(),
    }
    if len(classes) == 2:
        out["auroc"] = roc_auc_score(y, [prob(r) for r in rows])
    else:
        # scikit-learn requires sorted labels; reorder the probability columns to match.
        order = sorted(range(len(classes)), key=lambda i: classes[i])
        scores = [[prob(r)[i] for i in order] for r in rows]
        out["macro_auroc_ovr"] = roc_auc_score(
            y, scores, multi_class="ovr", average="macro", labels=sorted(classes)
        )
    return out


def rq1(root: Path) -> list[dict[str, Any]]:
    labels3 = ["reversible", "partially_reversible", "irreversible"]
    q, ll = root / "results/rq1_qwen/probes", root / "results/rq1_llama/probes"
    jobs = [
        # (name, predictions, saved results, saved-key map, classes, probability)
        (
            "qwen binary",
            q / "qwen_v2_binary_predictions.jsonl",
            q / "qwen_v2_final_binary_results.json",
            {
                "accuracy": "test_metrics.accuracy",
                "balanced_accuracy": "test_metrics.balanced_accuracy",
                "macro_f1": "test_metrics.macro_f1",
                "auroc": "test_metrics.auroc",
                "confusion_matrix": "test_metrics.confusion_matrix",
            },
            [0, 1],
            lambda r: r["probability_irreversible"],
        ),
        (
            "qwen 3-class",
            q / "qwen_v2_3class_test_predictions.jsonl",
            q / "qwen_v2_final_3class_results.json",
            {
                "balanced_accuracy": "test_metrics.balanced_accuracy",
                "macro_f1": "test_metrics.macro_f1",
                "macro_auroc_ovr": "test_metrics.macro_auroc",
            },
            labels3,
            lambda r: [r[f"prob_{c}"] for c in labels3],
        ),
        (
            "llama binary",
            ll / "llama_v2_binary_predictions.jsonl",
            ll / "llama_v2_binary_final_test_results.json",
            {
                "accuracy": "test_accuracy",
                "balanced_accuracy": "test_balanced_accuracy",
                "auroc": "test_auroc",
                "confusion_matrix": "confusion_matrix",
                "per_class_f1.1": "test_f1",
                "macro_f1": "classification_report.macro avg.f1-score",
            },
            [0, 1],
            lambda r: r["probability_irreversible"],
        ),
        (
            "llama 3-class",
            ll / "llama_v2_3class_predictions.jsonl",
            ll / "llama_v2_3class_final_test_results.json",
            {
                "accuracy": "classification_report.accuracy",
                "balanced_accuracy": "test_balanced_accuracy",
                "macro_f1": "test_macro_f1",
                "macro_auroc_ovr": "test_macro_auroc_ovr",
            },
            labels3,
            lambda r: [r["probabilities"][c] for c in labels3],
        ),
    ]

    def get(d: Any, dotted: str) -> Any:
        for part in dotted.split("."):
            d = d[part]
        return d

    def local(d: dict, dotted: str) -> Any:
        head, _, tail = dotted.partition(".")
        return d[head][tail] if tail else d[head]

    test_ids = gold = None
    v2 = root / "data/production/v2.0"
    if (v2 / "split.json").exists():
        split = json.loads((v2 / "split.json").read_text("utf-8"))
        recs = read_jsonl(v2 / "records.jsonl")
        test_groups = set(split.get("test_scenarios") or split.get("test", []))
        test_ids = {r["id"] for r in recs if r["scenario_id"] in test_groups}
        gold = {r["id"]: r for r in recs}

    out = []
    for name, pred_path, res_path, keymap, classes, prob in jobs:
        rows = read_jsonl(pred_path)
        saved = json.loads(res_path.read_text("utf-8"))
        rec = _rq1_metrics(rows, classes, prob)
        mismatches = []
        for mine, theirs in keymap.items():
            try:
                saved_value = get(saved, theirs)
            except (KeyError, TypeError):
                mismatches.append(f"{theirs}: not present in saved file")
                continue
            # Saved 3-class values are sometimes rounded to 4 d.p.
            value = local(rec, mine)
            if isinstance(saved_value, float) and len(repr(saved_value)) <= 6:
                value = round(value, 4)
            mismatches += list(compare(saved_value, value, theirs))
        entry: dict[str, Any] = {
            "check": f"RQ1 {name}",
            "predictions": str(pred_path),
            "recomputed": rec,
            "mismatches": mismatches,
        }
        if test_ids is not None and gold is not None:
            ids = [r["record_id"] for r in rows]
            entry["ids_equal_official_test_split"] = set(ids) == test_ids
            entry["duplicate_ids"] = len(ids) - len(set(ids))
            bad = 0
            for r in rows:
                g = gold[r["record_id"]]["label"]
                expected = int(g == "irreversible") if classes == [0, 1] else g
                bad += r["true_label"] != expected
            entry["gold_label_mismatches"] = bad
        entry["status"] = (
            "OK"
            if not mismatches
            and entry.get("gold_label_mismatches", 0) == 0
            and entry.get("ids_equal_official_test_split", True)
            else "MISMATCH"
        )
        out.append(entry)
    return out


# ------------------------------------------------------------ RQ2 / RQ3 ----


def behaviour_runs(root: Path) -> list[Path]:
    dirs = [p.parent for p in root.glob("results/rq2/*/*/outcomes.jsonl")]
    dirs += [p.parent for p in root.glob("results/rq3/*/*/outcomes.jsonl")]
    dirs += [p.parent for p in root.glob("results/member3_followups/*/outcomes.jsonl")]
    return sorted(dirs)


def rq2_rq3(root: Path) -> list[dict[str, Any]]:
    from adnn.behaviour.analysis import behaviour_metrics
    from adnn.behaviour.judgment import classification_metrics

    out = []
    for run in behaviour_runs(root):
        rows = read_jsonl(run / "outcomes.jsonl")
        kind = "RQ2" if "example_id" in rows[0] else "RQ3"
        saved_path = run / "metrics.json"
        entry: dict[str, Any] = {
            "check": f"{kind} metrics",
            "run": str(run.relative_to(root)),
            "n_rows": len(rows),
        }
        if not saved_path.exists():
            entry.update(status="NO_SAVED_METRICS", mismatches=[])
        else:
            rec = classification_metrics(rows) if kind == "RQ2" else behaviour_metrics(rows)
            saved = json.loads(saved_path.read_text("utf-8"))
            mismatches = list(compare(saved, rec))
            entry.update(
                status="OK" if not mismatches else "MISMATCH",
                mismatches=mismatches[:20],
                n_mismatches=len(mismatches),
            )
        # RQ2 runs record v2.0 only by path: check IDs and labels against the frozen bundle.
        v2 = root / "data/production/v2.0"
        if kind == "RQ2" and (v2 / "split.json").exists():
            split = json.loads((v2 / "split.json").read_text("utf-8"))
            gold = {r["id"]: r for r in read_jsonl(v2 / "records.jsonl")}
            test_ids = {k for k, r in gold.items() if r["scenario_id"] in split["test_scenarios"]}
            ids = [r["example_id"] for r in rows]
            unknown = [i for i in ids if i not in gold]
            bad = sum(
                r["label"] != gold[r["example_id"]]["label"]
                for r in rows
                if r["example_id"] in gold
            )
            entry["ids_equal_official_test_split"] = set(ids) == test_ids
            entry["ids_unknown_to_v2"] = len(unknown)
            entry["ids_in_test_split"] = len(set(ids) & test_ids)
            entry["gold_label_mismatches"] = bad
            if unknown or bad or len(ids) != len(set(ids)):
                entry["status"] = "MISMATCH"
        out.append(entry)
    return out


def replay(root: Path) -> list[dict[str, Any]]:
    from adnn.behaviour.runner import run_task
    from adnn.tasks import load_tasks

    tasks = {t["task_id"]: t for t in load_tasks(root / "data/tasks/rq3-tasks-1.0")}
    outcome_keys = [
        "termination",
        "steps",
        "parse_failures",
        "took_critical_action",
        "took_irreversible_action",
        "first_critical_step",
        "caution_events",
        "cautious",
        "task_success",
    ]
    out = []
    for run in behaviour_runs(root):
        rows = read_jsonl(run / "outcomes.jsonl")
        if "example_id" in rows[0]:
            continue
        n = ok = 0
        problems: list[str] = []
        missing_traces = 0
        for saved in rows:
            trace_path = run / f"{saved['task_id']}.jsonl"
            if not trace_path.exists():
                missing_traces += 1
                continue
            trace = read_jsonl(trace_path)
            raws = iter([step["raw"] for step in trace])
            condition = trace[0].get("agent_condition", "neutral")

            def generate(_messages: list[dict[str, str]], _raws: Iterator = raws) -> str:
                value = next(_raws)
                if value is None:
                    raise RuntimeError("recorded model_error")
                return value

            result = run_task(tasks[saved["task_id"]], generate, agent_condition=condition)
            n += 1
            diffs = [k for k in outcome_keys if result[k] != saved[k]]
            if len(result["trace"]) != len(trace):
                diffs.append("trace_length")
            else:
                for a, b in zip(result["trace"], trace, strict=True):
                    for key in (
                        "messages",
                        "state_before",
                        "state_after",
                        "events",
                        "error",
                        "result",
                        "observation",
                    ):
                        if key in b and a.get(key) != b[key]:
                            diffs.append(f"step{b['step']}.{key}")
            if diffs:
                problems.append(f"{saved['task_id']}: {sorted(set(diffs))[:6]}")
            else:
                ok += 1
        out.append(
            {
                "check": "RQ3 replay",
                "run": str(run.relative_to(root)),
                "replayed": n,
                "matched": ok,
                "missing_traces": missing_traces,
                "problems": problems[:20],
                "status": "OK" if n and ok == n and not missing_traces else "MISMATCH",
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--out", type=Path, help="write the full JSON report here")
    ap.add_argument("--skip-replay", action="store_true")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    sys.path.insert(0, str(root / "src"))
    report = rq1(root) + rq2_rq3(root) + ([] if args.skip_replay else replay(root))
    for entry in report:
        where = entry.get("run") or Path(entry.get("predictions", "")).name
        extra = ""
        if entry["check"] == "RQ3 replay":
            extra = f"{entry['matched']}/{entry['replayed']} traces"
        elif "ids_unknown_to_v2" in entry:
            extra = (
                f"ids==test_split:{entry['ids_equal_official_test_split']} "
                f"in_test:{entry['ids_in_test_split']} "
                f"unknown:{entry['ids_unknown_to_v2']} "
                f"label_mismatch:{entry['gold_label_mismatches']}"
            )
        elif "ids_equal_official_test_split" in entry:
            extra = (
                f"ids==test_split:{entry['ids_equal_official_test_split']} "
                f"label_mismatch:{entry['gold_label_mismatches']}"
            )
        print(f"{entry['status']:16} {entry['check']:18} {where:45} {extra}")
        for m in entry.get("mismatches", [])[:5] + entry.get("problems", [])[:5]:
            print(f"{'':18}- {m}")
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return 0 if all(e["status"] in {"OK", "NO_SAVED_METRICS"} for e in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
