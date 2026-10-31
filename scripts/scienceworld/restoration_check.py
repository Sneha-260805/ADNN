"""Run the Phase 4D restoration-diagnostic experiments on the pinned simulator (docs/19 §4).

Run from the repository root with the isolated runtime configured::

    SW="$LOCALAPPDATA/adnn-sw"
    ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" \
    ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
        .venv/Scripts/python.exe scripts/scienceworld/restoration_check.py

Writes one JSON report per experiment plus ``summary.json`` to
``results/scienceworld_restoration/`` (git-ignored). Diagnostics only: no labels.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from adnn.scienceworld import RuntimeConfig, phase4d_experiments, run_inverse_experiment

OUT = Path("results/scienceworld_restoration")
MODES = (
    "literal_canonical",
    "literal_projection:discrete-exploration-v1",
    "literal_projection:temperature-tolerance-exploration-v1",
    "counterfactual_canonical",
    "counterfactual_projection:discrete-exploration-v1",
)


def main() -> int:
    config = RuntimeConfig.from_env()
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for e in phase4d_experiments():
        t0 = time.perf_counter()
        d = run_inverse_experiment(e, config=config)
        report = d.to_dict()
        report["wall_s"] = round(time.perf_counter() - t0, 2)
        (OUT / f"{e.experiment_id}.json").write_text(json.dumps(report, indent=1) + "\n", "utf-8")
        effect = d.target_effect
        row = {
            "experiment": e.experiment_id,
            "target": e.target_action,
            "target_status": d.target_status,
            "target_effect": None
            if effect is None
            else {
                "changes": [c.key.split(":", 1)[-1] for c in effect.changes],
                "created": [n for _, n in effect.created_objects],
                "deleted": [n for _, n in effect.deleted_objects],
            },
            "rules": [(p.rule_id, p.applicable, p.reason) for p in d.proposals],
            "outcomes": list(d.outcomes),
            "attempts": [],
            "wall_s": report["wall_s"],
        }
        for a in d.attempts:
            comps = {m: a.comparison(m) for m in MODES if any(c.mode == m for c in a.comparisons)}
            loc, loose = a.structural
            row["attempts"].append(
                {
                    "source": a.source,
                    "actions": list(a.actions),
                    "step_status": [s.status for s in a.steps],
                    "n_actions_used": a.n_actions_used,
                    "ticks": a.ticks_target + a.ticks_path,
                    "n_raw_changes": a.n_raw_changes,
                    "comparisons": {
                        m: {
                            "outcome": c.outcome,
                            "n_changes": len(c.diff.changes),
                            "created": [n for _, n in c.diff.created_objects],
                            "deleted": [n for _, n in c.diff.deleted_objects],
                            "n_ignored": c.diff.n_ignored_differences,
                            "n_within_tolerance": c.diff.n_within_tolerance,
                            "n_temp_changes": c.n_temperature_changes,
                            "max_abs_dT": c.max_abs_temperature_delta,
                            "non_temp_changes": [
                                ch.key.split(":", 1)[-1]
                                for ch in c.diff.changes
                                if not ch.key.endswith("temperatureC")
                            ][:8],
                        }
                        for m, c in comps.items()
                    },
                    "structural_location_sensitive": {
                        "accounted": loc.all_objects_accounted,
                        "matches": [(m.name, m.uuid_before, m.uuid_after) for m in loc.matches],
                        "ambiguous": [
                            (g.name, g.uuids_before, g.uuids_after) for g in loc.ambiguous
                        ],
                        "unmatched_before": list(loc.unmatched_before),
                        "unmatched_after": list(loc.unmatched_after),
                        "relocated": list(loc.relocated),
                    },
                    "structural_location_insensitive": {
                        "matches": len(loose.matches),
                        "ambiguous": [
                            (g.name, g.uuids_before, g.uuids_after) for g in loose.ambiguous
                        ],
                    },
                    "observability_issues": list(a.observability_issues),
                    "outcomes": list(a.outcomes),
                }
            )
        summary.append(row)
        print(f"{e.experiment_id:22s} {d.target_status:9s} {', '.join(d.outcomes)}")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
