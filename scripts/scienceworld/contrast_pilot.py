"""Build the Phase 4F targeted state contrasts on the pinned simulator (docs/22 §3-4). No labels.

Run from the repository root with the isolated runtime configured::

    SW="$LOCALAPPDATA/adnn-sw"
    ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" \
    ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
        .venv/Scripts/python.exe scripts/scienceworld/contrast_pilot.py

Writes ``records.jsonl``, ``no_effect_records.jsonl``, ``states/``, ``contrast_pairs.jsonl``,
``failures.jsonl``, ``validation.json`` and ``summary.json`` to
``data/scienceworld_provisional/contrasts-v0/`` (git-ignored).
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.contrasts import build_contrast, contrast_specs, validate_contrast_pair
from adnn.scienceworld.provisional import jsonl_bytes, validate_dataset

OUT = Path("data/scienceworld_provisional/contrasts-v0")


def main() -> int:
    runtime = RuntimeConfig.from_env()
    (OUT / "states").mkdir(parents=True, exist_ok=True)
    records: dict[str, dict] = {}
    no_effect: dict[str, dict] = {}  # variants without an observed effect: kept, not validated
    pairs, failures, timings = [], [], []
    for spec in contrast_specs():
        t0 = time.perf_counter()
        pair, built, failure = build_contrast(spec, runtime=runtime)
        timings.append(round(time.perf_counter() - t0, 2))
        if failure:
            failures.append({"contrast_id": spec.contrast_id, "kind": spec.kind, "reason": failure})
            print(f"{spec.contrast_id:45s} FAILED {failure[:90]}")
            continue
        for rec, state_bytes in built:
            (OUT / rec["state_provenance"]["state_file"]).write_bytes(state_bytes)
            eff = rec["target"]["observed_effect"]
            effect = bool(eff["n_changes"] or eff["created_objects"] or eff["deleted_objects"])
            (records if effect else no_effect)[rec["example_id"]] = rec
        pairs.append(pair)
        print(
            f"{spec.contrast_id:45s} {pair['level']:31s} "
            f"methods={pair['restoration_contrast_methods']} "
            f"rejected={pair['rejection_reasons']}"
        )

    recs = list(records.values())
    report = validate_dataset(recs, [], root=OUT)
    pair_errors = {p["contrast"]["contrast_id"]: validate_contrast_pair(p) for p in pairs}
    (OUT / "records.jsonl").write_bytes(jsonl_bytes(recs))
    (OUT / "contrast_pairs.jsonl").write_bytes(jsonl_bytes(pairs))
    (OUT / "failures.jsonl").write_bytes(jsonl_bytes(failures))
    (OUT / "no_effect_records.jsonl").write_bytes(jsonl_bytes(no_effect.values()))
    validation = {"records": report.to_dict(), "pair_errors": pair_errors}
    (OUT / "validation.json").write_text(json.dumps(validation, indent=1) + "\n", "utf-8")
    levels = Counter(p["level"] for p in pairs)
    summary = {
        "n_specs": len(contrast_specs()),
        "n_built": len(pairs),
        "n_failed_to_build": len(failures),
        "levels": dict(levels),
        "by_kind": {
            k: dict(Counter(p["level"] for p in pairs if p["contrast"]["kind"] == k))
            for k in sorted({p["contrast"]["kind"] for p in pairs})
        },
        "restoration_contrast_by_method": dict(
            Counter(m for p in pairs for m in p["restoration_contrast_methods"])
        ),
        "rejection_reasons": dict(Counter(r for p in pairs for r in p["rejection_reasons"])),
        "records": len(recs),
        "no_effect_records": len(no_effect),
        "records_valid": report.ok,
        "pairs_valid": not any(pair_errors.values()),
        "s_per_contrast_mean": round(sum(timings) / len(timings), 1) if timings else None,
        "total_s": round(sum(timings), 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0 if report.ok and summary["pairs_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
