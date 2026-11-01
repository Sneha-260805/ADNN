"""Run the Phase 4F query-order / RNG audit on the pinned simulator (docs/22 §2).

Run from the repository root with the isolated runtime configured::

    SW="$LOCALAPPDATA/adnn-sw"
    ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" \
    ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
        .venv/Scripts/python.exe scripts/scienceworld/query_order_audit.py

Writes one JSON report per scenario plus ``summary.json`` to
``results/scienceworld_query_audit/`` (git-ignored).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.query_audit import AUDIT_SCENARIOS, audit_scenario

OUT = Path("results/scienceworld_query_audit")


def main() -> int:
    config = RuntimeConfig.from_env()
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for scenario in AUDIT_SCENARIOS:
        t0 = time.perf_counter()
        report = audit_scenario(scenario, repeats=2, shared=True, config=config).summary()
        report["wall_s"] = round(time.perf_counter() - t0, 1)
        (OUT / f"{scenario.scenario_id}.json").write_text(
            json.dumps(report, indent=1) + "\n", encoding="utf-8"
        )
        row = {
            "scenario": scenario.scenario_id,
            "stochastic": scenario.stochastic,
            "wall_s": report["wall_s"],
            "conditions": [{k: c[k] for k in c if k != "per_k"} for c in report["comparisons"]],
        }
        summary.append(row)
        for c in row["conditions"]:
            print(
                f"{scenario.scenario_id:32s} {c['condition']:27s} {c['process']:6s} r{c['repeat']} "
                f"state_eq={c['transitions_equal_all_k']!s:5} "
                f"first_diff_k={c['first_k_state_differs']} "
                f"obs_eq={c['observations_equal_all_k']!s:5} "
                f"va_eq={c['valid_actions_equal_all_k']!s:5} "
                f"bees_eq={c['stochastic_equal_all_k']}"
            )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
