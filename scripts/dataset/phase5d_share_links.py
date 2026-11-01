"""Phase 5D Candidate A diagnostics (docs/29). Run from the repository root.

    python scripts/dataset/phase5d_share_links.py

Refuses to run unless the frozen spec hash verifies. Runs the 10 frozen diagnostic cases,
a replay-determinism check and the scenario-novelty audit against the 450 historical records
(read-only), and writes ``results/phase5d/diagnostics.json`` (git-ignored). Produces no
dataset records.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from adnn.dataset.schema import write_json
from adnn.feasibility import scenario_diversity as sd
from adnn.feasibility import share_link_diagnostics as sl

OUT = Path("results/phase5d/diagnostics.json")
PRIOR = {
    "pilot": Path("data/pilot/pilot_v0.1.jsonl"),
    "phase5b": Path("data/scaling_pilot/records.jsonl"),
}


def _load(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x]


def main() -> int:
    spec_sha = sl.verify_spec()
    t0 = time.perf_counter()
    rows = sl.run_all()
    t_cases = round(time.perf_counter() - t0, 2)
    deterministic = sl.run_all() == rows
    cases = {c.case_id: c for c in sl.cases()}
    records = [sl.as_record(cases[r["case"]], r) for r in rows if r["is_definitive"]]
    prior = {name: _load(p) for name, p in PRIOR.items()}
    pooled = [*prior["pilot"], *prior["phase5b"]]
    novelty = sd.audit({"prior": pooled, "candidate_a": records})
    cross = novelty["cross"]["candidate_a_vs_prior"]
    doc = {
        "spec_version": sl.SPEC_VERSION,
        "spec_sha256": spec_sha,
        "n_cases": len(rows),
        "cases": rows,
        "falsified_cases": [r["case"] for r in rows if r["falsified"]],
        "oq21_label_changes": [r["case"] for r in rows if r["oq21_label_change"]],
        "residual_types": {r["case"]: r.get("residual_type") for r in rows},
        "diversity_version": sd.DIVERSITY_VERSION,
        "replay_deterministic": deterministic,
        "novelty": {
            "recovery_signatures": novelty["datasets"]["candidate_a"]["recovery_signatures"],
            "recovery_signatures_new_vs_prior": cross["recovery_signature"]["novel_ids"],
            "coarse_scenarios": novelty["datasets"]["candidate_a"]["within"]["scenario_coarse"],
            "coarse_new_vs_prior": cross["scenario_coarse"]["novel_ids"],
            "coarse_records_reusing_prior": cross["scenario_coarse"]["records_reusing_prior"],
            "conflicts": cross["pooled_conflicts"],
        },
        "runtime_s": {"cases": t_cases, "total": round(time.perf_counter() - t0, 2)},
    }
    write_json(OUT, doc)
    for r in rows:
        partial = r["observed"] == "partially_reversible"
        print(
            r["case"],
            r["observed"],
            f"(predicted {r['predicted']})",
            "depth",
            r["approx_restore_depth"] if partial else r["restore_depth"],
            "FALSIFIED" if r["falsified"] else "ok",
            r.get("residual", ""),
        )
    keys = ("spec_sha256", "falsified_cases", "oq21_label_changes", "residual_types",
            "replay_deterministic", "diversity_version", "novelty", "runtime_s")  # fmt: skip
    print(json.dumps({k: doc[k] for k in keys}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
