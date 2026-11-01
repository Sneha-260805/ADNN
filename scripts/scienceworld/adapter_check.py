"""Measure the ScienceWorld adapter's replay agreement and overhead (Phase 4C, docs/18 §9).

Run from the repository root with the isolated runtime configured::

    SW="$LOCALAPPDATA/adnn-sw"
    ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" \
    ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
        .venv/Scripts/python.exe scripts/scienceworld/adapter_check.py

Writes ``results/scienceworld_adapter/adapter_check.json`` (git-ignored).
Measures only; produces no labels.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from adnn.scienceworld import (
    ReplayRecipe,
    RuntimeConfig,
    ScienceWorldSession,
    capture_state,
    compare_results,
    replay,
    replay_in_fresh_process,
    resolve_runtime,
)

BOIL = ReplayRecipe(
    "1-1",
    0,
    "teleportAction",
    actions=(
        "teleport to kitchen",
        "pour counter into sink",
        "activate sink",
        "use lighter on drawer",
        "look around",
    ),
)
OUT = Path("results/scienceworld_adapter")


def main() -> int:
    config = RuntimeConfig.from_env()
    provenance = resolve_runtime(config)
    report: dict[str, object] = {"provenance": provenance.to_dict(), "recipe": BOIL.to_dict()}

    final_runs = [replay(BOIL, config=config, capture="final") for _ in range(3)]
    all_runs = [replay(BOIL, config=config, capture="all") for _ in range(3)]
    fresh_runs = []
    fresh_wall = []
    for _ in range(3):
        t0 = time.perf_counter()
        fresh_runs.append(replay_in_fresh_process(BOIL, config=config, capture="all"))
        fresh_wall.append(round(time.perf_counter() - t0, 3))

    report["agreement"] = {
        "in_process_capture_final": [
            compare_results(final_runs[0], r).to_dict() for r in final_runs[1:]
        ],
        "in_process_capture_all": [compare_results(all_runs[0], r).to_dict() for r in all_runs[1:]],
        "fresh_process_vs_in_process": [
            compare_results(all_runs[0], r).to_dict() for r in fresh_runs
        ],
    }
    report["timings_s"] = {
        "replay_capture_final_total": [r.timings["total_s"] for r in final_runs],
        "replay_capture_all_total": [r.timings["total_s"] for r in all_runs],
        "replay_start_jvm": [r.timings["start_s"] for r in all_runs],
        "fresh_process_wall": fresh_wall,
    }

    with ScienceWorldSession(config) as s:
        s.load("1-1", 0, "teleportAction")
        s.step("teleport to kitchen")
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            state = capture_state(s)
            times.append(time.perf_counter() - t0)
    report["capture_state"] = {
        "location": state.canonical.world,
        "mean_s": round(statistics.mean(times), 4),
        "max_s": round(max(times), 4),
        "n_objects": len(state.canonical.objects),
        "n_canonical_fields": state.canonical.field_count(),
        "raw_json_bytes": len(json.dumps(state.raw.to_dict())),
        "n_valid_actions": len(state.raw.valid_actions),
        "visible_doors": state.canonical.visible_doors,
        "incomplete_reasons": list(state.canonical.incomplete_reasons),
    }
    report["final_state_steam"] = "a substance called steam" in all_runs[0].final.raw.look
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "adapter_check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("agreement", "timings_s", "capture_state")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
