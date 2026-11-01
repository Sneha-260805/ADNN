"""Generate the production dataset from the FROZEN manifest (ADR-0009; docs/34).

    python scripts/dataset/phase5h_generate.py --out data/production/v1.0

Refuses to run unless the frozen manifest matches its sidecar, HEAD descends from its
``base_commit``, ``src/adnn`` is unchanged since then and the generation config and the
ScienceWorld evidence hashes equal the frozen ones. Needs the pinned ScienceWorld runtime
(``ADNN_SW_JAVA_HOME``, ``ADNN_SW_SITE_PACKAGES``) for the five ScienceWorld records.

Writes ``records.jsonl``, ``tool_sets.json``, ``split.json``, ``manifest.json`` (loadable by
``adnn.dataset.api.load_dataset``), ``sensitivity_oq21.jsonl`` (tier P, never gold) and
``generation_report.json``. Exit status 1 if a gate or the validator fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from adnn.dataset import production as prod
from adnn.dataset.api import load_dataset
from adnn.dataset.schema import sha256_file, write_json, write_jsonl
from adnn.dataset.validation import validate_directory
from adnn.scienceworld import export as sx

FROZEN = Path("docs/preregistration/production_manifest.json")
SIDECAR = Path("docs/preregistration/production_manifest.sha256")
THRESHOLDS = {"min_examples": 1, "min_pair_fraction": 0.30, "min_class_fraction": 0.25}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def verify_freeze() -> dict[str, Any]:
    sha = hashlib.sha256(FROZEN.read_bytes()).hexdigest()
    if sha != SIDECAR.read_text("utf-8").split()[0]:
        raise SystemExit("frozen manifest does not match its sidecar")
    m = json.loads(FROZEN.read_text("utf-8"))
    base = m["base_commit"]
    if _git("merge-base", "--is-ancestor", base, "HEAD").returncode != 0:
        raise SystemExit(f"HEAD does not descend from base_commit {base}")
    if _git("diff", "--quiet", base, "--", "src/adnn").returncode != 0:
        raise SystemExit("src/adnn differs from base_commit")
    cfg = prod.ProductionConfig()
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    m = verify_freeze()
    t0 = time.perf_counter()
    cfg = prod.ProductionConfig()
    built = prod.build(cfg, prod.DATASET_VERSION)
    sw_records, sw_report = sx.export(prod.DATASET_VERSION)
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
            prod.DATASET_VERSION,
            tool_sets,
        )
        for u in built.report["_sensitivity"]
    ]
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "records.jsonl", records)
    write_json(out / "tool_sets.json", tool_sets)
    write_json(out / "split.json", split)
    write_jsonl(out / "sensitivity_oq21.jsonl", sensitivity)
    manifest = {
        "dataset_version": prod.DATASET_VERSION,
        "purpose": "ADNN production dataset (sandbox + ScienceWorld); gold tier only",
        "prompt_builder_version": cfg.prompt_builder_version,
        "partial_definition_policy": m["partial_definition_policy"],
        "generator_version": prod.GENERATOR_VERSION,
        "grouping_version": prod.GROUPING_VERSION,
        "frozen_manifest": {
            "path": str(FROZEN).replace("\\", "/"),
            "sha256": m["_sha256"],
            "base_commit": m["base_commit"],
        },
        "split": {"file": "split.json", "sha256": sha256_file(out / "split.json")},
        "files": {
            "dataset": {"file": "records.jsonl", "sha256": sha256_file(out / "records.jsonl")},
            "tool_sets": {"file": "tool_sets.json", "sha256": sha256_file(out / "tool_sets.json")},
            "sensitivity_oq21": {
                "file": "sensitivity_oq21.jsonl",
                "sha256": sha256_file(out / "sensitivity_oq21.jsonl"),
            },
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
    gates = prod.gates(summary, cfg) | {
        "validator_errors": not rep.errors,
        "loader_prompt_hashes": rebuilt == len(records),
    }
    report = {
        "status": "OK" if all(gates.values()) else "FAILED",
        "gates": gates,
        "req_data_01_met": len(records) >= 2000,
        "frozen_manifest_sha256": m["_sha256"],
        "head": _git("rev-parse", "HEAD").stdout.strip(),
        "output_sha256": {k: v["sha256"] for k, v in manifest["files"].items()}
        | {"split": manifest["split"]["sha256"]},
        "sandbox_records_sha256": prod.sha256_text(prod.stable_json(built.records)),
        "summary": summary,
        "by_environment": {
            e: sum(r["environment"] == e for r in records) for e in ("sandbox", "scienceworld")
        },
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
