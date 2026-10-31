"""Phase 4H certificate audit and experiments (docs/24 §4).

Run from the repository root with the isolated runtime configured and the pinned source::

    .venv/Scripts/python.exe scripts/scienceworld/phase4h_certificates.py --source <scala root>

Writes ``results/scienceworld_certificates_4h/*.json`` (git-ignored). Reports are
source-relative evidence, never labels, and nothing here changes ``sw-admission-2``:
the Phase 4G reports in ``results/scienceworld_certificates/`` remain the ones admission
reads. ``C-EAT/structural-plantless`` is a new, narrower, world-conditional claim that is
reported for review only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.certificate_audit import (
    AUDIT_VERSION,
    PLANTLESS_ID,
    add_object_sites,
    combustion_pathways,
    fruit_names,
    plant_closure,
    reattachment_obligation,
    run_experiments,
)
from adnn.scienceworld.certificate_verification import (
    _common,
    obligation,
    verification_report,
)
from adnn.scienceworld.certificates import DEF_COUNTERFACTUAL, DEF_LITERAL, DEF_STRUCTURAL, MET
from adnn.scienceworld.phase4h_cases import (
    FILL_POT,
    KITCHEN,
    PLANT_WORLD,
    SALT_IN_POT,
    TWO_SALT_WORLD,
)

OUT = Path("results/scienceworld_certificates_4h")
HORIZON = "unbounded under agent actions and ticks; researcher load/reset excluded"


def _write(path: Path, doc: object) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=1) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--budget", type=int, default=25)
    args = ap.parse_args()
    root = args.source
    OUT.mkdir(parents=True, exist_ok=True)
    names = fruit_names(root)
    o2 = reattachment_obligation(root)
    o8 = plant_closure(root)
    common = _common(root)
    exp = run_experiments(
        families={"kitchen": KITCHEN, "two_salt": TWO_SALT_WORLD, "plant_world": PLANT_WORLD},
        histories={"fill_pot": FILL_POT, "salt_in_pot": SALT_IN_POT},
        names=names,
        budget=args.budget,
        config=RuntimeConfig.from_env(),
    )
    eat_free, eat_plants = exp["eat"]["plantless_world"], exp["eat"]["plant_world"]
    never_again = all(not ids for ids in eat_free["same_name_objects_over_100_ticks"])
    search_none = not eat_free["bounded_search"]["returns"]

    identity = verification_report(
        "C-EAT/identity", "the eaten object's uuid never re-enters the object tree",
        [obligation("O1", "an eaten object's uuid never re-enters the object tree", True,
                    "stated"), o2, *common,
         obligation("O6", "simulator: the eaten uuid stays absent for 100 ticks", never_again,
                    eat_free["same_name_objects_over_100_ticks"]),
         obligation("O7", "bounded search finds no return", search_none,
                    eat_free["bounded_search"])],
        definitions=(DEF_LITERAL, DEF_COUNTERFACTUAL), identity_loss_only=True, horizon=HORIZON,
        notes=("identity loss only: never admissible for an irreversible label (ADR-0004 C3)",),
    )  # fmt: skip
    plantless = verification_report(
        PLANTLESS_ID,
        "if the eaten object is an audited fruit class, no other object of that class exists "
        "and no plant, flower, pollen or seed exists anywhere in the universe tree, then no "
        "object of that class ever exists again (at any horizon, under agent actions and "
        "ticks)",
        [obligation("O1", "invariant stated with its world precondition", True, "stated"),
         o2, *common,
         obligation("O6", "simulator: plantless world, precondition met and no banana for 100 "
                    "ticks", eat_free["check"]["status"] == MET and never_again,
                    {"check": eat_free["check"],
                     "over_100_ticks": eat_free["same_name_objects_over_100_ticks"]}),
         obligation("O7", "bounded search finds no return; the checker rejects a world with "
                    "plants", search_none and eat_plants["check"]["status"] != MET,
                    {"search": eat_free["bounded_search"], "plant_world": eat_plants}),
         o8],
        definitions=(DEF_COUNTERFACTUAL, f"{DEF_STRUCTURAL} (class-level presence)"),
        identity_loss_only=False, horizon=HORIZON,
        notes=("world-conditional and class-conditional; narrower than C-EAT/structural",
               "NOT registered with sw-admission-2; adopting it requires a new ADR and rule "
               "version (ADR-0005 R6)",
               "fruit names are matched to classes by their default display name"),
    )  # fmt: skip
    plantless["registered_with_admission"] = False
    burn = exp["burn"]
    burn_doc = {
        "version": AUDIT_VERSION,
        "claim": "C-BURN (Phase 4G report unchanged)",
        "source_pathways": combustion_pathways(root),
        "experiments": burn,
        "coverage_findings": {
            "hasCombusted": "monotone (source writes '= true' only; experiments agree)",
            "isCombusting": "NOT irreversible: extinguished by water inside the object or in its "
            "container (pour into chair / pour onto the kitchen floor)",
            "present": "the object is deleted only when combustion runs to completion; an "
            "extinguished object stays present",
        },
        "conclusion": "C-BURN cannot be broadened to isCombusting or present; burn cases with "
        "weighted isCombusting are partial candidates, not irreversible ones",
    }
    salt_doc = {
        "version": AUDIT_VERSION,
        "claim": "C-MIX-SALT (Phase 4G report unchanged)",
        "experiments": exp["salt"],
        "coverage_findings": {
            "sodium chloride present": "covered when no other sodium chloride exists",
            "water present": "NOT covered: the water's uuid is lost (identity loss); new water "
            "is obtainable from the sink (structural replacement)",
        },
    }
    sites = [s.__dict__ for s in add_object_sites(root)]
    for name, doc in (("C-EAT_identity_4h", identity), ("C-EAT_structural-plantless", plantless),
                      ("C-BURN_coverage", burn_doc), ("C-MIX-SALT_precondition", salt_doc),
                      ("add_object_sites",
                       {"version": AUDIT_VERSION, "sites": sites})):  # fmt: skip
        _write(OUT / f"{name}.json", doc)
    summary = {
        "C-EAT/identity": {k: identity[k] for k in ("status", "admissible_for_irreversible_label")},
        PLANTLESS_ID: {k: plantless[k] for k in ("status", "admissible_for_irreversible_label",
                                                  "open_or_failed")}
        | {"registered_with_admission": False},
        "C-BURN": {f"extinguished_{k}": burn[k]["extinguished"]
                   for k in ("pour_into_chair", "pour_into_kitchen")}
        | {"burn_out": {k: burn["burn_out"][k] for k in ("deleted_by_tick", "ash_objects")}},
        "C-MIX-SALT": {k: v["check"]["status"] for k, v in exp["salt"].items()},
    }  # fmt: skip
    _write(OUT / "summary.json", summary)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
