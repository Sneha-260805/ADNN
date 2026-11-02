"""Dataset v2.0 bounded feasibility check: v1.0 generator + ADR-0010 families (sandbox only).

    python scripts/dataset/v2_feasibility.py [--surface-variants N]

Runs the complete production build in memory (admission, grouping, split, rendering,
selection), adds the five frozen v1.0 ScienceWorld records (split by the v1.0 rule), runs
the full production validator (oracle re-run, production thresholds) and writes only
``results/v2/feasibility_capN.json`` (git-ignored). No dataset file is written.
Exit status 1 if any production gate or validation check fails.

``--surface-variants`` (default 6, the adopted v2.0 value; v1.0 uses 4) is the per-scenario
variant cap (ADR-0010 Amendment 1). The final dataset is made by ``v2_generate.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from adnn.dataset import families_v2 as v2
from adnn.dataset import production as prod
from adnn.dataset.schema import sha256_text, stable_json, write_json
from adnn.dataset.validation import PARTIAL_POLICY_TEAM, validate_records

V1 = Path("data/production/v1.0")
THRESHOLDS = {"min_examples": 1, "min_pair_fraction": 0.30, "min_class_fraction": 0.25}
SUBSET_CAP = v2.ROBUSTNESS_CAP


def scienceworld_v1() -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """The frozen v1.0 ScienceWorld records and their v1.0 train/test groups."""
    rows = [json.loads(x) for x in (V1 / "records.jsonl").read_text("utf-8").splitlines() if x]
    sw = [
        r | {"dataset_version": v2.DATASET_VERSION}
        for r in rows
        if r["environment"] == "scienceworld"
    ]
    split = json.loads((V1 / "split.json").read_text("utf-8"))
    groups = {r["scenario_id"] for r in sw}
    return (
        sw,
        sorted(groups & set(split["train_scenarios"])),
        sorted(groups & set(split["test_scenarios"])),
    )


def class_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(r["label"] for r in records).items()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--surface-variants", type=int, default=v2.SURFACE_VARIANTS)
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    cfg = replace(v2.config(), surface_variants=args.surface_variants)
    built = v2.build(cfg, v2.DATASET_VERSION)
    summary = prod.summarise(built.records, built.split)
    gates = prod.gates(summary, cfg)

    sw, sw_train, sw_test = scienceworld_v1()
    records = sorted(built.records + sw, key=lambda r: r["id"])
    split = dict(built.split)
    split["train_scenarios"] = sorted(split["train_scenarios"] + sw_train)
    split["test_scenarios"] = sorted(split["test_scenarios"] + sw_test)
    test_groups = set(split["test_scenarios"])
    test = [r for r in records if r["scenario_id"] in test_groups]
    rep = validate_records(
        records,
        split=split,
        tool_sets=dict(built.tool_sets)
        | {
            sw[0]["tool_set_id"]: json.loads((V1 / "tool_sets.json").read_text("utf-8"))[
                sw[0]["tool_set_id"]
            ]
        },
        thresholds=THRESHOLDS,
        declared_builder_version=cfg.prompt_builder_version,
        partial_policy=PARTIAL_POLICY_TEAM,
    )
    subset = v2.capped_subset(records, SUBSET_CAP)
    mismatches = [
        {
            "id": r["id"],
            "family": r["template_id"],
            "label": r["label"],
            "declared_depths": r["meta"]["declared_depths"],
            "oracle_depths": [r["restore_depth"], r["approx_restore_depth"]],
            "state_sha": sha256_text(r["state_text"])[:12],
        }
        for r in records
        if r["environment"] == "sandbox" and r["meta"].get("declaration_agrees") is False
    ]
    report = {k: v for k, v in built.report.items() if not k.startswith("_")}
    result = {
        "config": cfg.to_dict(),
        "config_sha256": cfg.sha256(),
        "build": report,
        "summary": summary,
        "gates": gates,
        "validation": {"ok": rep.ok, "errors": rep.errors[:50], "n_errors": len(rep.errors)},
        "total_records": len(records),
        "sandbox_records": len(built.records),
        "scienceworld_records": len(sw),
        "classes_h3": class_counts(records),
        "minimal_pair_fraction": round(sum(1 for r in records if r["pair_id"]) / len(records), 4),
        "distinct_scenarios": {
            "scenario_id": len({r["scenario_id"] for r in records}),
            **summary["scenarios"],
        },
        "test": {
            "records": len(test),
            "fraction": round(len(test) / len(records), 4),
            "groups": len(test_groups),
            "classes_h3": class_counts(test),
            "families": dict(sorted(Counter(r["template_id"] for r in test).items())),
        },
        f"capped_subset_le{SUBSET_CAP}": {
            "records": len(subset),
            "classes_h3": class_counts(subset),
            "minimal_pair_fraction": round(
                sum(1 for r in subset if r["pair_id"]) / max(1, len(subset)), 4
            ),
        },
        "declaration_mismatches": mismatches,
        "declaration_mismatches_by_family": dict(Counter(m["family"] for m in mismatches)),
        "by_family": dict(sorted(Counter(r["template_id"] for r in records).items())),
        "records_sha256": sha256_text(stable_json(records)),
        "runtime_s": round(time.perf_counter() - t0, 1),
    }
    suffix = f"_cap{args.surface_variants}"
    out = Path(f"results/v2/feasibility{suffix}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, result)
    skip = {"config", "summary", "declaration_mismatches", "by_family"}
    print(json.dumps({k: v for k, v in result.items() if k not in skip}, indent=1))
    return 0 if all(gates.values()) and rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
