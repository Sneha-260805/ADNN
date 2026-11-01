"""Restoration-search sensitivity on a small pilot subsample (Phase 4F, docs/22 §5). No labels.

Run from the repository root with the isolated runtime configured (see
``provisional_pilot.py``) after ``provisional_pilot.py`` has written ``pilot-v0``::

    .venv/Scripts/python.exe scripts/scienceworld/expanded_search.py

Writes ``results/scienceworld_expanded_search/<example_id>.json`` and ``summary.json``
(git-ignored).
"""

from __future__ import annotations

import json
from pathlib import Path

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.expanded_search import expanded_search
from adnn.scienceworld.provisional import read_jsonl
from adnn.scienceworld.replay import ReplayRecipe

PILOT = Path("data/scienceworld_provisional/pilot-v0/records.jsonl")
OUT = Path("results/scienceworld_expanded_search")
MAX_CANDIDATES = 40

# One record per evidence category of the 4E pilot, bee-hive targets excluded (docs/22 §5.1).
SUBSAMPLE = {
    "swp-8448dd3b4847fd21": "no_candidate: eat apple",
    "swp-a7e9b6acdfbee69f": "no_candidate: pour counter into kitchen",
    "swp-d94f330cd41d5796": "no_candidate: connect (electrical)",
    "swp-4d9717d7c440158b": "no_candidate: pour switch into hallway",
    "swp-310564b27074f692": "mismatch: activate sink (kitchen)",
    "swp-ae66c8c9d0b92fbe": "mismatch: activate sink (greenhouse)",
    "swp-0c02170196d4a9a1": "within_0.1C: pick up glass jar",
    "swp-a5c464c5cc09339b": "exact control: close freezer",
}


def main() -> int:
    runtime = RuntimeConfig.from_env()
    OUT.mkdir(parents=True, exist_ok=True)
    records = {r["example_id"]: r for r in read_jsonl(PILOT)}
    summary = []
    for example_id, why in SUBSAMPLE.items():
        rec = records[example_id]
        recipe = ReplayRecipe.from_dict(rec["replay_recipe"])
        result = expanded_search(
            recipe, rec["target"]["action"], max_candidates=MAX_CANDIDATES, config=runtime
        )
        result.update(
            example_id=example_id,
            subsample_reason=why,
            original_evidence_status=rec["restoration_evidence"]["evidence_status"],
        )
        (OUT / f"{example_id}.json").write_text(json.dumps(result, indent=1) + "\n", "utf-8")
        row = {
            k: result.get(k)
            for k in (
                "example_id",
                "subsample_reason",
                "original_evidence_status",
                "target_status",
                "best_match_level",
                "branching",
                "n_candidates_tried",
                "sampled",
                "n_accepted",
                "n_refused_or_invalid",
                "matches",
                "cost",
            )
        }
        summary.append(row)
        print(
            json.dumps(
                {
                    k: row[k]
                    for k in (
                        "example_id",
                        "subsample_reason",
                        "best_match_level",
                        "branching",
                        "n_accepted",
                    )
                }
            )
        )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
