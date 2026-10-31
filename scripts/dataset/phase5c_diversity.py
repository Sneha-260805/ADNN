"""Phase 5C scenario-level diversity audit (docs/27). Run from the repository root.

    python scripts/dataset/phase5c_diversity.py

Reads the 210-example pilot and the Phase 5B records (read-only; both checksums are verified
against their recorded values and reported) and writes ``results/phase5c/diversity.json``
(git-ignored). Generates no records and touches no simulator.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from adnn.dataset.schema import write_json
from adnn.feasibility import scenario_diversity as sd
from adnn.feasibility.scaling_pilot import structure_signature

PILOT = Path("data/pilot/pilot_v0.1.jsonl")
PILOT_MANIFEST = Path("data/pilot/manifest.json")
PHASE5B = Path("data/scaling_pilot/records.jsonl")
PHASE5B_REPORT = Path("data/scaling_pilot/generation_report.json")
OUT = Path("results/phase5c/diversity.json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x]


def main() -> int:
    t0 = time.perf_counter()
    pilot, p5b = _load(PILOT), _load(PHASE5B)
    pilot_sha, p5b_sha = _sha(PILOT), _sha(PHASE5B)
    recorded_5b = json.loads(PHASE5B_REPORT.read_text("utf-8"))["records_sha256"]
    report = sd.audit(
        {"pilot": pilot, "phase5b": p5b},
        gold={"pilot": lambda r: not r["label_provisional"], "phase5b": lambda r: r["tier"] == "G"},
    )
    old_struct = {structure_signature(r) for r in pilot}
    report["inputs"] = {
        "pilot_sha256": pilot_sha,
        "pilot_sha256_recorded_in_manifest": pilot_sha in PILOT_MANIFEST.read_text("utf-8"),
        "phase5b_sha256": p5b_sha,
        "phase5b_sha256_matches_generation_report": p5b_sha == recorded_5b,
    }
    report["phase5b_heuristic_comparison"] = {
        "structure_signature_reuse": sum(structure_signature(r) in old_struct for r in p5b),
        "note": "Phase 5B structure_signature (all non-config values masked) for comparison",
    }
    report["prospective_gates_descriptive"] = sd.prospective_gate_values(report, "phase5b")
    report["runtime_s"] = round(time.perf_counter() - t0, 2)
    write_json(OUT, report)
    c = report["cross"]["phase5b_vs_prior"]
    print(
        json.dumps(
            {
                "inputs": report["inputs"],
                "reuse": {
                    k: c[k] for k in ("recovery_signature", "scenario_strict", "scenario_coarse")
                },
                "heuristic": report["phase5b_heuristic_comparison"]["structure_signature_reuse"],
                "uncertainty": report["uncertainty"],
                "runtime_s": report["runtime_s"],
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
