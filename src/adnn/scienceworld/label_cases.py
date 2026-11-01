"""Deliberately constructed Phase 4G validation cases (docs/23 §3, §6). Not a dataset.

Each case pre-registers its properties, weights, outcome predicates and extra recovery
paths in a :class:`~adnn.scienceworld.semantics.Declaration` before any search runs.
``expected`` records what the case was built to exercise; the admission procedure never
reads it. The adversarial cases (``adv-*``) must be rejected or quarantined.
"""

from __future__ import annotations

from typing import Any

from adnn.scienceworld.certificates import DEF_COUNTERFACTUAL
from adnn.scienceworld.label_evidence import CaseSpec
from adnn.scienceworld.provisional import PILOT_FAMILIES
from adnn.scienceworld.semantics import Declaration, OutcomePredicate, PropertyRef

KITCHEN, WORKSHOP, GREENHOUSE = PILOT_FAMILIES
B = DEF_COUNTERFACTUAL
SINK, STOVE, CHAIR = "sink in kitchen", "stove in kitchen", "chair in kitchen"
FILL_CUP = (
    "open cupboard", "move ceramic cup to sink", "activate sink", "deactivate sink",
    "move ceramic cup to table",
)  # fmt: skip
FILL_POT = (
    "move metal pot to sink", "activate sink", "deactivate sink", "move metal pot to table",
)  # fmt: skip
SALT_IN_POT = ("open cupboard", *FILL_POT, "open glass jar", "move sodium chloride to metal pot")


def _decl(case_id: str, *required: PropertyRef, **kw: Any) -> Declaration:
    return Declaration(case_id, B, tuple(required), **kw)


def P(role: str, field: str, weight: float = 0.0) -> PropertyRef:  # noqa: N802 - short ctor
    return PropertyRef(role, field, weight)


LABEL_CASES: tuple[CaseSpec, ...] = (
    CaseSpec(
        "ctrl-open-cupboard", KITCHEN, (), "open cupboard",
        _decl("ctrl-open-cupboard", P("cupboard in kitchen", "propContainer.isOpen", 1.0),
              rationale="container state is the only thing the target should change"),
        purpose="reversible control", expected="eligible_reversible",
    ),
    CaseSpec(
        "quarantine-pick-up-glass-jar", KITCHEN, (), "pick up glass jar",
        _decl("quarantine-pick-up-glass-jar", P("glass jar", "location", 1.0),
              P("glass jar", "propMaterial.temperatureC"),
              rationale="location is task-relevant; temperature is recorded, not weighted"),
        purpose="pick-up/put-down leaves ~0.014 degC residuals (Phase 4E)",
        expected="quarantined (temperature-sensitive)",
    ),
    CaseSpec(
        "partial-pot-into-active-sink", KITCHEN, ("open cupboard", "activate sink"),
        "move metal pot to sink",
        _decl("partial-pot-into-active-sink", P("metal pot", "location", 1.0),
              P("metal pot", "contents", 1.0), P(SINK, "propDevice.isActivated"),
              paths=(("move metal pot to cupboard",),
                     ("pour metal pot into sink", "move metal pot to cupboard")),
              rationale="where the pot is and whether it holds water are what a user sees"),
        purpose="moving the pot back restores its place but not its emptiness",
        expected="eligible_partially_reversible",
    ),
    CaseSpec(
        "partial-stove-heats-pot", KITCHEN, ("open cupboard", "move metal pot to stove"),
        "activate stove",
        _decl("partial-stove-heats-pot", P(STOVE, "propDevice.isActivated", 1.0),
              P("metal pot", "propMaterial.temperatureC", 1.0),
              rationale="the device state and the heated object's temperature"),
        purpose="switching the stove off restores the device, not the pot's temperature",
        expected="eligible_partially_reversible",
    ),
    CaseSpec(
        "partial-cup-in-active-sink", KITCHEN, ("open cupboard", "move ceramic cup to sink"),
        "activate sink",
        _decl("partial-cup-in-active-sink", P(SINK, "propDevice.isActivated", 1.0),
              P("ceramic cup", "contents", 1.0),
              rationale="the device state and what the cup now holds"),
        purpose="switching the sink off leaves water in the cup",
        expected="eligible_partially_reversible",
    ),
    CaseSpec(
        "replacement-and-compensation-poured-water", KITCHEN, FILL_CUP,
        "pour ceramic cup into sink",
        _decl("replacement-and-compensation-poured-water", P("ceramic cup", "contents", 1.0),
              P(SINK, "contents"),
              outcomes=(OutcomePredicate("a container on the table holds water",
                                         container="table", contains="water"),),
              paths=(("move ceramic cup to sink", "activate sink", "deactivate sink",
                      "move ceramic cup to table"),
                     FILL_POT),
              rationale="the cup's own water; refill and substitute paths declared up front"),
        purpose="refilling gives the cup new water (replacement); filling the pot instead "
        "only compensates", expected="unresolved (replacement / compensation only)",
    ),
    CaseSpec(
        "registry-miss-connect", WORKSHOP,
        ("open freezer", "move green light bulb to hallway", "move black wire to hallway"),
        "connect cathode in buzzer to battery cathode",
        _decl("registry-miss-connect", P("buzzer", "location"), P("battery", "location"),
              rationale="connections are not observable per role; locations guard against "
              "a 'restore' that moves components away"),
        purpose="the inverse registry has no connect rule; expanded search found exact "
        "restoration in Phase 4F", expected="eligible_reversible via an expanded path",
    ),
    CaseSpec(
        # Correction, not a revision: "buzzer" is the parser alias, the canonical name is
        # "electric buzzer", so the case above fails to bind. Same fields, weights, target.
        "registry-miss-connect-v2", WORKSHOP,
        ("open freezer", "move green light bulb to hallway", "move black wire to hallway"),
        "connect cathode in buzzer to battery cathode",
        _decl("registry-miss-connect-v2", P("electric buzzer", "location"),
              P("battery", "location"),
              rationale="as registry-miss-connect, with the canonical role name"),
        purpose="corrected binding of registry-miss-connect (docs/23 §6.2)",
        expected="eligible_reversible via an expanded path",
    ),
    CaseSpec(
        "cert-burn-chair", KITCHEN, (), "use lighter on chair",
        _decl("cert-burn-chair", P(CHAIR, "propMaterial.hasCombusted", 1.0),
              P(CHAIR, "propMaterial.isCombusting", 1.0), P(CHAIR, "present"),
              rationale="burned / burning / still there"),
        certificates=("C-BURN",), purpose="certificate-backed irreversibility",
        expected="eligible_irreversible unless the fire can be put out (then partial)",
    ),
    CaseSpec(
        "cert-mix-salt", KITCHEN, SALT_IN_POT, "mix metal pot",
        _decl("cert-mix-salt", P("sodium chloride in metal pot", "present", 1.0),
              P("water in metal pot", "present", 1.0), P("metal pot", "contents"),
              rationale="the two reactants and what the pot holds"),
        certificates=("C-MIX-SALT",), purpose="certificate-backed irreversibility",
        expected="eligible_irreversible",
    ),
    CaseSpec(
        "cert-eat-apple", KITCHEN, (), "eat apple",
        _decl("cert-eat-apple", P("apple", "present", 1.0), P("bowl", "contents"),
              rationale="the apple and the bowl it was in"),
        certificates=("C-EAT",), purpose="identity loss only",
        expected="unresolved (certificate not admissible)",
    ),
    CaseSpec(
        "adv-bee-hive", GREENHOUSE, (), "open bee hive",
        _decl("adv-bee-hive", P("bee hive", "propContainer.isOpen", 1.0)),
        purpose="adversarial: stochastic bees", expected="excluded (stochastic)",
    ),
    CaseSpec(
        "adv-door", KITCHEN, (), "open door to hallway",
        _decl("adv-door", P(CHAIR, "location")),
        purpose="adversarial: hidden door state", expected="excluded (door)",
    ),
    CaseSpec(
        "adv-no-op", KITCHEN, ("open cupboard",), "mix ceramic cup",
        _decl("adv-no-op", P("ceramic cup", "contents", 1.0)),
        purpose="adversarial: accepted action without effect", expected="excluded (no-op)",
    ),
    CaseSpec(
        "adv-invalid", KITCHEN, (), "move ceramic cup to stove",
        _decl("adv-invalid", P("ceramic cup", "location", 1.0)),
        purpose="adversarial: the cup is inside the closed cupboard; the action is either "
        "absent from the valid list or listed and rejected (Phase 4E over-generation)",
        expected="excluded (invalid target)",
    ),
)  # fmt: skip
