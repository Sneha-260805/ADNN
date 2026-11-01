"""Restoration semantics and the partial-restoration evaluator (Phase 4G, docs/23, ADR-0004).

Six concepts are kept apart (ADR-0004 A1):

1. ``exact_state_restoration``: identity-preserving canonical equality with the
   time-matched counterfactual (the existing comparison).
2. ``approximate_restoration``: the same, with temperatures within a declared tolerance.
3. ``task_relevant_restoration``: every declared task-relevant property (weight > 0) is
   restored on the *original* objects, other differences may remain.
4. ``structural_replacement``: a declared property is matched only by an object with a
   different identity (e.g. fresh water refilling a cup).
5. ``compensation``: a declared practical-outcome predicate holds although the original
   state is not restored.
6. ``unknown``: no comparable evidence (incomplete observation or search).

Structural replacement and compensation are never restoration. Properties are declared
in a :class:`Declaration` *before* any recovery search; the declaration's hash is stored
with the evidence and re-checked at admission, so it cannot be changed retrospectively.
Everything here is pure (no simulator) and produces witnesses, never labels.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from adnn.scienceworld.canonical import CanonicalState, sha256_json
from adnn.scienceworld.diagnostics import (
    TEMPERATURE_TOLERANCE_001,
    TEMPERATURE_TOLERANCE_01,
    canonical_diff,
    projection_diff,
)

SEMANTICS_VERSION = "sw-restoration-semantics-1"

EXACT = "exact_state_restoration"
APPROXIMATE = "approximate_restoration"
TASK_RELEVANT = "task_relevant_restoration"
PARTIAL = "partial_restoration"
REPLACEMENT = "structural_replacement"
COMPENSATION = "compensation"
NONE = "no_restoration"
UNKNOWN = "unknown"
CONCEPT_ORDER = (EXACT, APPROXIMATE, TASK_RELEVANT, PARTIAL, REPLACEMENT, COMPENSATION, NONE)

PRIMARY_TOLERANCE = 0.01  # exploratory primary threshold (ADR-0004 A3)
SENSITIVITY_TOLERANCE = 0.1  # quarantine if the interpretation changes here
TOLERANCES = (0.0, PRIMARY_TOLERANCE, SENSITIVITY_TOLERANCE)

RESTORED, REPLACED, DIFFERENT = "restored", "replaced", "different"
DERIVED_FIELDS = ("present", "location", "contents")
PART_PREFIX = "terminal "  # electrical terminals: parts of every object, not contents


class BindingError(ValueError):
    """A declared role does not name exactly one object in S0."""


@dataclass(frozen=True)
class PropertyRef:
    """A declared property: ``role`` names one S0 object ("name" or "name in parent")."""

    role: str
    field: str  # a flattened canonical field, or "present" | "location" | "contents"
    weight: float = 0.0  # > 0: task-relevant (ADR-0004 A2)

    @property
    def key(self) -> str:
        return f"{self.role}.{self.field}"

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "field": self.field, "weight": self.weight}


@dataclass(frozen=True)
class OutcomePredicate:
    """``exists`` an object (``name``) in a container (``container``) holding ``contains``."""

    description: str
    name: str | None = None
    container: str | None = None
    contains: str | None = None

    def holds(self, state: CanonicalState) -> bool:
        live = _live(state)
        for u, r in live.items():
            if self.name is not None and r.get("name") != self.name:
                continue
            if self.container is not None and _name(state, r.get("parent")) != self.container:
                continue
            if self.contains is not None and self.contains not in _child_names(state, u):
                continue
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class Declaration:
    """Pre-registered properties, outcome predicates and extra recovery paths for one case."""

    case_id: str
    definition: str  # restoration definition, e.g. "B_time_matched_counterfactual"
    required: tuple[PropertyRef, ...]
    outcomes: tuple[OutcomePredicate, ...] = ()
    paths: tuple[tuple[str, ...], ...] = ()
    rationale: str = ""
    version: str = SEMANTICS_VERSION

    def __post_init__(self) -> None:
        if not self.required:
            raise ValueError("a declaration needs at least one required property")
        if len({p.key for p in self.required}) != len(self.required):
            raise ValueError("duplicate declared property")

    @property
    def task_relevant(self) -> tuple[PropertyRef, ...]:
        return tuple(p for p in self.required if p.weight > 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "definition": self.definition,
            "required": [p.to_dict() for p in self.required],
            "outcomes": [o.to_dict() for o in self.outcomes],
            "paths": [list(p) for p in self.paths],
            "rationale": self.rationale,
            "version": self.version,
        }

    @property
    def sha256(self) -> str:
        return sha256_json(self.to_dict())


def declaration_from_dict(d: Mapping[str, Any]) -> Declaration:
    return Declaration(
        d["case_id"],
        d["definition"],
        tuple(PropertyRef(**p) for p in d["required"]),
        tuple(OutcomePredicate(**o) for o in d["outcomes"]),
        tuple(tuple(p) for p in d["paths"]),
        d.get("rationale", ""),
        d.get("version", SEMANTICS_VERSION),
    )


# -- state helpers ----------------------------------------------------------------------------
def _live(state: CanonicalState) -> dict[str, dict[str, Any]]:
    return {u: r for u, r in state.objects.items() if not r.get("isDeleted")}


def _name(state: CanonicalState, uuid: Any) -> str | None:
    r = state.objects.get(str(uuid))
    return None if r is None else r.get("name")


def _children(state: CanonicalState, uuid: str) -> list[str]:
    return sorted(
        u
        for u, r in _live(state).items()
        if str(r.get("parent")) == uuid and not str(r.get("name", "")).startswith(PART_PREFIX)
    )


def _child_names(state: CanonicalState, uuid: str) -> list[str]:
    return sorted(str(state.objects[c].get("name")) for c in _children(state, uuid))


def bind(declaration: Declaration, s0: CanonicalState) -> dict[str, str]:
    """Resolve every role to exactly one live S0 uuid (before any search)."""
    out: dict[str, str] = {}
    for role in sorted({p.role for p in declaration.required}):
        name, _, parent = role.partition(" in ")
        hits = [
            u
            for u, r in _live(s0).items()
            if r.get("name") == name and (not parent or _name(s0, r.get("parent")) == parent)
        ]
        if len(hits) != 1:
            raise BindingError(f"role {role!r} matches {len(hits)} objects in S0")
        out[role] = hits[0]
    return out


def _equal(a: Any, b: Any, field_name: str, tol: float) -> bool:
    if (
        field_name.endswith("temperatureC")
        and isinstance(a, int | float)
        and isinstance(b, int | float)
    ):
        return abs(a - b) <= tol + 1e-12
    return a == b


def _lookalikes(state: CanonicalState, ref_state: CanonicalState, uuid: str) -> list[str]:
    """Live objects in ``state`` with the same name and container name as ``uuid`` in ref."""
    r = ref_state.objects.get(uuid)
    if r is None:
        return []
    parent = _name(ref_state, r.get("parent"))
    return [
        u
        for u, o in _live(state).items()
        if u != uuid and o.get("name") == r.get("name") and _name(state, o.get("parent")) == parent
    ]


def compare_property(
    ref: PropertyRef, uuid: str, reference: CanonicalState, other: CanonicalState, tol: float
) -> str:
    """Is ``ref`` (bound to ``uuid``) in ``other`` restored to its value in ``reference``?

    ``restored``: equal on the original object; ``replaced``: equal only through a
    look-alike with a different identity; ``different``: neither.
    """
    live_ref, live_other = _live(reference), _live(other)
    in_ref, in_other = uuid in live_ref, uuid in live_other
    f = ref.field
    if f == "present":
        if in_ref == in_other:
            return RESTORED
        return REPLACED if in_ref and _lookalikes(other, reference, uuid) else DIFFERENT
    if not in_ref:
        return RESTORED if not in_other else DIFFERENT
    if f == "contents":
        if in_other and _children(reference, uuid) == _children(other, uuid):
            return RESTORED
        names = _child_names(reference, uuid)
        if in_other and _child_names(other, uuid) == names:
            return REPLACED
        twins = _lookalikes(other, reference, uuid)
        return REPLACED if any(_child_names(other, t) == names for t in twins) else DIFFERENT
    if f == "location":
        want = str(live_ref[uuid].get("parent"))
        if in_other and str(live_other[uuid].get("parent")) == want:
            return RESTORED
        return REPLACED if not in_other and _lookalikes(other, reference, uuid) else DIFFERENT
    want_v = live_ref[uuid].get(f)
    if in_other:
        return RESTORED if _equal(live_other[uuid].get(f), want_v, f, tol) else DIFFERENT
    twins = _lookalikes(other, reference, uuid)
    return (
        REPLACED
        if any(_equal(other.objects[t].get(f), want_v, f, tol) for t in twins)
        else DIFFERENT
    )


# -- attempt evaluation -----------------------------------------------------------------------
def canonical_level(counterfactual: CanonicalState, s2: CanonicalState) -> str:
    if canonical_diff(counterfactual, s2).equal_on_observed_fields:
        return "exact"
    if projection_diff(counterfactual, s2, TEMPERATURE_TOLERANCE_001).equal_on_observed_fields:
        return "within_0.01C"
    if projection_diff(counterfactual, s2, TEMPERATURE_TOLERANCE_01).equal_on_observed_fields:
        return "within_0.1C"
    return "none"


LEVEL_MATCHES = {
    0.0: ("exact",),
    PRIMARY_TOLERANCE: ("exact", "within_0.01C"),
    SENSITIVITY_TOLERANCE: ("exact", "within_0.01C", "within_0.1C"),
}


@dataclass(frozen=True)
class PropertyOutcome:
    key: str
    weight: float
    changed_by_target: bool  # S1 differs from the counterfactual at t ticks
    after_recovery: str  # restored | replaced | different (vs counterfactual at t + p)
    restored_by_idling: bool  # target followed by p idle ticks already restores it

    @property
    def meaningfully_restored(self) -> bool:
        return (
            self.changed_by_target
            and self.after_recovery == RESTORED
            and not self.restored_by_idling
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "meaningfully_restored": self.meaningfully_restored}


@dataclass(frozen=True)
class AttemptAssessment:
    """One recovery attempt judged at one temperature tolerance."""

    tolerance: float
    canonical_level: str
    properties: tuple[PropertyOutcome, ...]
    outcomes_hold: bool | None  # None: no outcome predicate declared
    concepts: tuple[str, ...] = field(default=())

    @property
    def primary_concept(self) -> str:
        return min(self.concepts, key=CONCEPT_ORDER.index) if self.concepts else NONE

    @property
    def restored(self) -> list[str]:
        return [p.key for p in self.properties if p.meaningfully_restored]

    @property
    def residual(self) -> list[str]:
        return [p.key for p in self.properties if p.after_recovery != RESTORED]

    @property
    def replaced(self) -> list[str]:
        return [p.key for p in self.properties if p.after_recovery == REPLACED]

    @property
    def declared_complete(self) -> bool:
        """Every declared property restored on its original object (undeclared may differ)."""
        return all(p.after_recovery == RESTORED for p in self.properties)

    @property
    def partial_witness(self) -> bool:
        """B1: a meaningful restoration AND a declared residual. Task-relevant restoration
        whose only residuals are undeclared is reported, but is not a partial witness."""
        return PARTIAL in self.concepts

    def to_dict(self) -> dict[str, Any]:
        return {
            "tolerance": self.tolerance,
            "canonical_level": self.canonical_level,
            "concepts": list(self.concepts),
            "primary_concept": self.primary_concept,
            "restored_changed_properties": self.restored,
            "residual_properties": self.residual,
            "replaced_properties": self.replaced,
            "outcomes_hold": self.outcomes_hold,
            "partial_witness": self.partial_witness,
            "declared_complete": self.declared_complete,
            "weighted_recovery": weighted_recovery(self.properties),
            "properties": [p.to_dict() for p in self.properties],
        }


def weighted_recovery(props: Iterable[PropertyOutcome]) -> float | None:
    changed = [p for p in props if p.changed_by_target and p.weight > 0]
    total = sum(p.weight for p in changed)
    if not total:
        return None
    return round(sum(p.weight for p in changed if p.meaningfully_restored) / total, 4)


def assess_attempt(
    declaration: Declaration,
    binding: Mapping[str, str],
    *,
    s1: CanonicalState,
    cf_target: CanonicalState,
    s2: CanonicalState,
    cf_total: CanonicalState,
    idle_after_target: CanonicalState,
    tolerance: float,
) -> AttemptAssessment:
    """Judge one recovery attempt against the declaration at one tolerance.

    ``cf_target``: counterfactual after the target's ticks; ``cf_total``: after the
    target's plus the path's ticks; ``idle_after_target``: target followed by as many idle
    ticks as the path took (exposes properties that come back on their own).
    """
    level = canonical_level(cf_total, s2)
    props = []
    for ref in declaration.required:
        u = binding[ref.role]
        props.append(
            PropertyOutcome(
                ref.key,
                ref.weight,
                compare_property(ref, u, cf_target, s1, tolerance) != RESTORED,
                compare_property(ref, u, cf_total, s2, tolerance),
                compare_property(ref, u, cf_total, idle_after_target, tolerance) == RESTORED,
            )
        )
    holds = None
    if declaration.outcomes:
        holds = all(o.holds(s2) for o in declaration.outcomes)
    concepts = classify(level, props, holds, tolerance)
    return AttemptAssessment(tolerance, level, tuple(props), holds, concepts)


def classify(
    level: str, props: list[PropertyOutcome], outcomes_hold: bool | None, tolerance: float
) -> tuple[str, ...]:
    """Every concept the attempt satisfies (ADR-0004 A1, B1)."""
    out = []
    if level == "exact":
        out.append(EXACT)
    elif level in LEVEL_MATCHES[tolerance]:
        out.append(APPROXIMATE)
    if out:
        return tuple(out)
    restored = [p for p in props if p.meaningfully_restored]
    residual = [p for p in props if p.after_recovery != RESTORED]
    relevant = [p for p in props if p.weight > 0]
    if (
        relevant
        and all(p.after_recovery == RESTORED for p in relevant)
        and any(p.meaningfully_restored for p in relevant)
    ):
        out.append(TASK_RELEVANT)
    weighted = any(p.weight > 0 for p in props)
    meaningful = [p for p in restored if p.weight > 0] if weighted else restored
    if meaningful and residual:
        out.append(PARTIAL)
    if any(p.after_recovery == REPLACED for p in props):
        out.append(REPLACEMENT)
    if outcomes_hold and residual:
        out.append(COMPENSATION)
    return tuple(out) or (NONE,)
