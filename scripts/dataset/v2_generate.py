"""Generate production dataset v2.0 from the FROZEN amended v2 manifest (ADR-0010; docs/37).

    python scripts/dataset/v2_generate.py --out data/production/v2.0

Refuses to run unless the frozen manifest matches its sidecar, HEAD descends from its
``base_commit``, the ``src/adnn`` code hash, the generation config, the ScienceWorld evidence
hashes and the protected artifacts (incl. every v1.0 file) equal the frozen ones. Needs the
pinned ScienceWorld runtime (``ADNN_SW_JAVA_HOME``, ``ADNN_SW_SITE_PACKAGES``).

Writes the v1.0 file set (``records.jsonl``, ``tool_sets.json``, ``split.json``,
``manifest.json``, ``sensitivity_oq21.jsonl``, ``generation_report.json``) plus
``robustness_subset_le3.json``. Exit status 1 if a gate or the validator fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from v2_freeze_manifest import code_sha256  # same directory as this script

from adnn.dataset import families_v2 as v2
from adnn.dataset import production as prod
from adnn.dataset.api import load_dataset
from adnn.dataset.schema import sha256_file, write_json, write_jsonl
from adnn.dataset.validation import validate_directory
from adnn.scienceworld import export as sx

FROZEN = Path("docs/preregistration/production_manifest_v2_amend1.json")
SIDECAR = Path("docs/preregistration/production_manifest_v2_amend1.sha256")
THRESHOLDS = {"min_examples": 1, "min_pair_fraction": 0.30, "min_class_fraction": 0.25}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def verify_freeze() -> dict[str, Any]:
    sha = hashlib.sha256(FROZEN.read_bytes()).hexdigest()
    if sha != SIDECAR.read_text("utf-8").split()[0]:
        raise SystemExit("frozen manifest does not match its sidecar")
    m = json.loads(FROZEN.read_text("utf-8"))
    if _git("merge-base", "--is-ancestor", m["base_commit"], "HEAD").returncode != 0:
        raise SystemExit(f"HEAD does not descend from base_commit {m['base_commit']}")
    if code_sha256() != m["code_sha256"]:
        raise SystemExit("src/adnn differs from the frozen code_sha256")
    cfg = v2.config()
    if (
        cfg.to_dict() != m["generation"]["config"]
        or cfg.sha256() != m["generation"]["config_sha256"]
    ):
        raise SystemExit("generation config differs from the frozen manifest")
    for case, h in m["scienceworld"]["cases"].items():
        if sx.sha256_path(sx.EVIDENCE_DIR / f"{case}.json") != h:
            raise SystemExit(f"ScienceWorld evidence for {case} changed")
    for path, h in m["protected_artifacts_sha256"].items():
        if sha256_file(Path(path)) != h:
            raise SystemExit(f"{path}: protected artifact changed")
    m["_sha256"] = sha
    return m


def _sw_test_family(records: list[dict[str, Any]]) -> str:
    sizes: dict[str, int] = {}
    for r in records:
        sizes[r["scenario_id"]] = sizes.get(r["scenario_id"], 0) + 1
    target = 0.20 * len(records)
    return min(sorted(sizes), key=lambda g: abs(sizes[g] - target))


def _classes(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(r["label"] for r in records).items()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    m = verify_freeze()
    t0 = time.perf_counter()
    cfg = v2.config()
    built = v2.build(cfg, v2.DATASET_VERSION)
    sw_records, sw_report = sx.export(v2.DATASET_VERSION)
    sw_test = _sw_test_family(sw_records)
    records = sorted(built.records + sw_records, key=lambda r: r["id"])
    tool_sets = dict(built.tool_sets) | {sx.SW_TOOL_SET_ID: sx.SW_TOOLS}
    split = dict(built.split)
    sw_groups = sorted({r["scenario_id"] for r in sw_records})
    split["train_scenarios"] = sorted(
        split["train_scenarios"] + [g for g in sw_groups if g != sw_test]
    )
    split["test_scenarios"] = sorted(split["test_scenarios"] + [sw_test])
    split["scienceworld_rule"] = m["scienceworld"]["split_rule"]
    sensitivity = [
        prod.make_record(
            replace(u, pair_key=None, pivot=None),
            "kv",
            "sensitivity",
            v2.DATASET_VERSION,
            tool_sets,
        )
        for u in built.report["_sensitivity"]
    ]
    for r in sensitivity:
        r["meta"]["generator_version"] = cfg.generator_version
    subset = v2.capped_subset(records)
    test_groups = set(split["test_scenarios"])
    in_subset = {r["id"] for r in subset}
    subset_doc = {
        "rule": m["robustness_subset"]["rule"],
        "records": len(subset),
        "classes_h3": _classes(subset),
        "train": sum(r["scenario_id"] not in test_groups for r in subset),
        "test": sum(r["scenario_id"] in test_groups for r in subset),
        "ids": sorted(in_subset),
    }
    subset_pairs = Counter(r["pair_id"] for r in subset if r["pair_id"])
    subset_per = Counter(
        r["meta"]["scenario_keys"]["coarse"] if r["environment"] == "sandbox" else r["id"]
        for r in subset
    )
    subset_doc |= {
        "complete_pairs": sum(n == 2 for n in subset_pairs.values()),
        "split_pairs": sum(n != 2 for n in subset_pairs.values()),
        "max_records_per_coarse_scenario": max(subset_per.values()),
        "coarse_scenarios": len(subset_per),
    }
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "records.jsonl", records)
    write_json(out / "tool_sets.json", tool_sets)
    write_json(out / "split.json", split)
    write_jsonl(out / "sensitivity_oq21.jsonl", sensitivity)
    write_json(out / "robustness_subset_le3.json", subset_doc)
    manifest = {
        "dataset_version": v2.DATASET_VERSION,
        "purpose": "ADNN production dataset v2.0 (sandbox + ScienceWorld); gold tier only",
        "prompt_builder_version": cfg.prompt_builder_version,
        "partial_definition_policy": m["partial_definition_policy"],
        "generator_version": cfg.generator_version,
        "families_version": v2.FAMILIES_VERSION,
        "grouping_version": prod.GROUPING_VERSION,
        "frozen_manifest": {
            "path": str(FROZEN).replace("\\", "/"),
            "sha256": m["_sha256"],
            "base_commit": m["base_commit"],
            "code_sha256": m["code_sha256"],
        },
        "split": {"file": "split.json", "sha256": sha256_file(out / "split.json")},
        "files": {
            name: {"file": f, "sha256": sha256_file(out / f)}
            for name, f in (
                ("dataset", "records.jsonl"),
                ("tool_sets", "tool_sets.json"),
                ("sensitivity_oq21", "sensitivity_oq21.jsonl"),
                ("robustness_subset_le3", "robustness_subset_le3.json"),
            )
        },
    }
    write_json(out / "manifest.json", manifest)
    rep = validate_directory(out, thresholds=THRESHOLDS)
    ds = load_dataset(out)
    rebuilt = sum(
        ds.probe_prompt(r).prompt_sha256 == r["meta"]["probe_prompt_sha256"]
        and ds.stated_prompt(r).prompt_sha256 == r["meta"]["stated_prompt_sha256"]
        for r in ds.records
    )
    summary = prod.summarise(records, split)
    test = [r for r in records if r["scenario_id"] in test_groups]
    v1_sw = [
        json.loads(x)
        for x in Path("data/production/v1.0/records.jsonl").read_text("utf-8").splitlines()
        if x and json.loads(x)["environment"] == "scienceworld"
    ]
    sw_same = sorted(
        (r | {"dataset_version": "-"} for r in sw_records), key=lambda r: r["id"]
    ) == sorted((r | {"dataset_version": "-"} for r in v1_sw), key=lambda r: r["id"])
    mismatches = [
        {
            "id": r["id"],
            "family": r["template_id"],
            "label": r["label"],
            "declared_depths": r["meta"]["declared_depths"],
            "oracle_depths": [r["restore_depth"], r["approx_restore_depth"]],
        }
        for r in records
        if r["environment"] == "sandbox" and r["meta"].get("declaration_agrees") is False
    ]
    gates = prod.gates(summary, cfg) | {
        "validator_errors": not rep.errors,
        "loader_prompt_hashes": rebuilt == len(records),
        "loader_split_counts": len(list(ds.iter_split("train"))) + len(test) == len(records),
        "scienceworld_records_equal_v1": sw_same,
        "records_identical_to_first_run": sha256_file(out / "records.jsonl")
        == m["expected_identical_to_first_run"]["records_jsonl_sha256"],
        "split_identical_to_first_run": sha256_file(out / "split.json")
        == m["expected_identical_to_first_run"]["split_json_sha256"],
        "subset_pairs_atomic": subset_doc["split_pairs"] == 0,
        "subset_cap_respected": subset_doc["max_records_per_coarse_scenario"] <= v2.ROBUSTNESS_CAP,
    }
    report = {
        "status": "OK" if all(gates.values()) else "FAILED",
        "gates": gates,
        "req_data_01_met": len(records) >= 2000,
        "frozen_manifest_sha256": m["_sha256"],
        "head": _git("rev-parse", "HEAD").stdout.strip(),
        "code_sha256": m["code_sha256"],
        "output_sha256": {k: v["sha256"] for k, v in manifest["files"].items()}
        | {"split": manifest["split"]["sha256"]},
        "sandbox_records_sha256": prod.sha256_text(prod.stable_json(built.records)),
        "summary": summary,
        "by_environment": {
            e: sum(r["environment"] == e for r in records) for e in ("sandbox", "scienceworld")
        },
        "test": {
            "records": len(test),
            "groups": len(test_groups),
            "classes_h3": _classes(test),
            "share_of_class_in_test": {
                c: round(n / summary["classes_h3"][c] if c in summary["classes_h3"] else 0, 3)
                for c, n in _classes(test).items()
            },
        },
        "robustness_subset_le3": {k: v for k, v in subset_doc.items() if k != "ids"},
        "declaration_mismatches": {
            "count": len(mismatches),
            "by_family": dict(Counter(x["family"] for x in mismatches)),
            "patterns_label_declared_oracle": dict(
                Counter(
                    json.dumps([x["label"], x["declared_depths"], x["oracle_depths"]])
                    for x in mismatches
                )
            ),
            "ids": [x["id"] for x in mismatches],
        },
        "by_family": dict(sorted(Counter(r["template_id"] for r in records).items())),
        "scienceworld": sw_report | {"test_group": sw_test},
        "build": {k: v for k, v in built.report.items() if not k.startswith("_")},
        "sensitivity_oq21_records": len(sensitivity),
        "validator": {
            "errors": rep.errors,
            "warnings": rep.warnings,
            "checks_run": dict(rep.checks_run),
        },
        "runtime_s": round(time.perf_counter() - t0, 1),
    }
    write_json(out / "generation_report.json", report)
    keys = ("status", "gates", "req_data_01_met", "output_sha256", "by_environment", "runtime_s")
    print(json.dumps({k: report[k] for k in keys}, indent=1))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
