"""Generate the Phase 4E provisional ScienceWorld evidence pilot (docs/21). No labels.

Run from the repository root with the isolated runtime configured::

    SW="$LOCALAPPDATA/adnn-sw"
    ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" \
    ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
        .venv/Scripts/python.exe scripts/scienceworld/provisional_pilot.py [--regenerate]

Writes to ``data/scienceworld_provisional/pilot-v0/`` (git-ignored):
``records.jsonl``, ``states/``, ``candidate_pairs.jsonl``, ``rejections.jsonl``,
``performance.jsonl``, ``validation.json``, ``replay_check.json`` and ``manifest.json``.
With ``--regenerate`` the pipeline runs a second time into ``pilot-v0-regen/`` and
the two outputs are compared byte for byte (deterministic regeneration).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from adnn.scienceworld import RuntimeConfig, replay
from adnn.scienceworld.provisional import (
    DECISION_LOG,
    EVIDENCE_SCHEMA_VERSION,
    PAIR_SCHEMA_VERSION,
    SCIENTIFIC_STATUS,
    read_jsonl,
)
from adnn.scienceworld.provisional_sampling import SamplerConfig, run_pilot
from adnn.scienceworld.replay import ReplayRecipe

OUT = Path("data/scienceworld_provisional")
COMPARED = ("records.jsonl", "candidate_pairs.jsonl", "rejections.jsonl")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fresh_replay_check(out: Path, config: RuntimeConfig) -> dict:
    """Rebuild every record's S0 in a fresh simulator and compare raw fingerprints."""
    rows = []
    for r in read_jsonl(out / "records.jsonl"):
        res = replay(ReplayRecipe.from_dict(r["replay_recipe"]), config=config)
        rows.append({
            "example_id": r["example_id"],
            "reproduced": res.final.raw.fingerprint == r["pre_action_state"]["raw_fingerprint"],
            "canonical_reproduced": (
                res.final.canonical.fingerprint == r["pre_action_state"]["canonical_fingerprint"]
            ),
            "n_actions": len(res.steps),
            **res.timings,
        })  # fmt: skip
    totals = [x["total_s"] for x in rows]
    return {
        "n_records": len(rows),
        "n_reproduced": sum(x["reproduced"] and x["canonical_reproduced"] for x in rows),
        "replay_s_mean": round(sum(totals) / len(totals), 3) if totals else None,
        "replay_s_max": max(totals, default=None),
        "rows": rows,
    }


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--regenerate", action="store_true", help="run twice and compare outputs")
    args = parser.parse_args()
    runtime = RuntimeConfig.from_env()
    config = SamplerConfig()
    out = OUT / "pilot-v0"

    result = run_pilot(out, config, runtime=runtime)
    t0 = time.perf_counter()
    replay_check = fresh_replay_check(out, runtime)
    replay_check["wall_s"] = round(time.perf_counter() - t0, 2)
    (out / "replay_check.json").write_text(json.dumps(replay_check, indent=1) + "\n", "utf-8")

    regeneration = None
    if args.regenerate:
        regen = OUT / "pilot-v0-regen"
        run_pilot(regen, config, runtime=runtime)
        regeneration = {name: sha256(out / name) == sha256(regen / name) for name in COMPARED} | {
            "states": sorted(p.name for p in (out / "states").iterdir())
            == sorted(p.name for p in (regen / "states").iterdir())
        }

    manifest = {
        "evidence_schema": EVIDENCE_SCHEMA_VERSION,
        "pair_schema": PAIR_SCHEMA_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "decision_log": DECISION_LOG,
        "git": {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))},
        "summary": result.summary,
        "fresh_replay": {k: v for k, v in replay_check.items() if k != "rows"},
        "deterministic_regeneration": regeneration,
        "files": {
            name: sha256(out / name)
            for name in (
                "records.jsonl",
                "candidate_pairs.jsonl",
                "rejections.jsonl",
                "performance.jsonl",
                "validation.json",
                "replay_check.json",
            )
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    s = result.summary
    print(f"records={s['n_records']} pairs={s['n_candidate_pairs']} valid={s['validation_ok']} "
          f"replayed={replay_check['n_reproduced']}/{replay_check['n_records']} "
          f"regeneration={regeneration}")  # fmt: skip
    print(json.dumps(s["evidence_status"]), json.dumps(s["performance"]))
    ok = s["validation_ok"] and replay_check["n_reproduced"] == replay_check["n_records"]
    return 0 if ok and (regeneration is None or all(regeneration.values())) else 1


if __name__ == "__main__":
    raise SystemExit(main())
