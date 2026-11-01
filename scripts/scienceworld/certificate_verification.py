"""Verify the source certificates against their proof obligations (Phase 4G, docs/23 §4).

Run from the repository root with the isolated runtime configured (see
``provisional_pilot.py``) and the pinned simulator source extracted::

    .venv/Scripts/python.exe scripts/scienceworld/certificate_verification.py \
        --source <ScienceWorld-e8216d6.../simulator/src/main/scala/scienceworld>

Writes ``results/scienceworld_certificates/<claim>.json`` and ``summary.json``
(git-ignored). Produces verification reports, never labels.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.certificate_probes import run_probes
from adnn.scienceworld.certificate_verification import (
    constructor_sites,
    obligation,
    static_obligations,
    verification_report,
)
from adnn.scienceworld.certificates import (
    C_BURN,
    C_EAT,
    C_MIX_SALT,
    DEF_COUNTERFACTUAL,
    DEF_LITERAL,
)

OUT = Path("results/scienceworld_certificates")
HORIZON = "unbounded under agent actions and ticks; researcher load/reset excluded"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--budget", type=int, default=25)
    args = ap.parse_args()
    root = args.source
    OUT.mkdir(parents=True, exist_ok=True)
    probes = run_probes(budget=args.budget, config=RuntimeConfig.from_env())
    struct_c = "C_structural_selected_properties"
    reports = []

    burn_obs, burn_log = probes["C-BURN"]
    reports.append((verification_report(
        "C-BURN", C_BURN.claim, static_obligations("C-BURN", root) + burn_obs,
        definitions=(DEF_LITERAL, DEF_COUNTERFACTUAL,
                     f"{struct_c} (if hasCombusted is selected; Chair only, O8)"),
        identity_loss_only=False, horizon=HORIZON,
        notes=("covers the burned object's own flags while it exists; a fully burned object "
               "is deleted (identity loss) and replaced by ash",
               f"Chair constructor sites: {constructor_sites(root, 'Chair')}"),
    ), burn_log))  # fmt: skip

    mix_obs, mix_log = probes["C-MIX-SALT"]
    reports.append((verification_report(
        "C-MIX-SALT", C_MIX_SALT.claim, static_obligations("C-MIX-SALT", root) + mix_obs,
        definitions=(DEF_LITERAL, DEF_COUNTERFACTUAL,
                     f"{struct_c} (if substance identity is selected)"),
        identity_loss_only=False, horizon=HORIZON,
        notes=("conditional: applies only when the checker finds no other sodium chloride "
               "anywhere in the universe tree",),
    ), mix_log))  # fmt: skip

    eat_obs, eat_log = probes["C-EAT"]
    o2_identity = obligation(
        "O2",
        "a detached (eaten) object can never be re-attached by any action",
        None,
        "rests on the reachability argument (InputParser.collectAccessibleObjects); not "
        "mechanically discharged",
    )
    reports.append((verification_report(
        "C-EAT/identity", "the eaten object's uuid never re-enters the object tree",
        [*static_obligations("C-EAT/identity", root), o2_identity, *eat_obs],
        definitions=(DEF_LITERAL, DEF_COUNTERFACTUAL), identity_loss_only=True,
        horizon=HORIZON,
        notes=("identity loss only: equally true of any deletion (ADR-0003 D3)",),
    ), eat_log))  # fmt: skip
    regrowth = obligation(
        "O7",
        "world-conditional regrowth exclusion (no plants or seeds now, none obtainable "
        "within the horizon)",
        None,
        {"world_facts": eat_log["world"], "note": "seed availability not proven"},
    )
    reports.append((verification_report(
        "C-EAT/structural", C_EAT.claim,
        [*static_obligations("C-EAT/structural", root), regrowth],
        definitions=(struct_c,), identity_loss_only=False, horizon=HORIZON,
        notes=("PlantReproduction.createFruit creates new fruit at runtime: the general "
               "structural claim has a source counterexample mechanism",),
    ), {}))  # fmt: skip

    summary = []
    for report, log in reports:
        report["probe_log"] = log
        name = report["certificate_id"].replace("/", "_")
        (OUT / f"{name}.json").write_text(json.dumps(report, indent=1) + "\n", "utf-8")
        summary.append({k: report[k] for k in (
            "certificate_id", "status", "admissible_for_irreversible_label",
            "identity_loss_only", "open_or_failed",
        )})  # fmt: skip
        print(json.dumps(summary[-1]))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
