"""State-difference diagnostics (docs/18 §6).

These functions *describe* differences. They do not decide whether a state was
"restored": exact and partial restoration in ScienceWorld are open professor
decisions (OQ-03, OQ-30, OQ-31), and nothing here produces reversibility labels.

Every comparison reports exactly which fields it ignored and which numeric
tolerances it applied, and it propagates the canonical state's incompleteness.
``equal_on_observed_fields`` can therefore never be read as exact-state equality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any

from adnn.scienceworld.canonical import CanonicalState, RawState

_MISSING = object()


@dataclass(frozen=True)
class FieldChange:
    key: str  # "<uuid>:<field>" or "world:<field>" or "door:<room>"
    before: Any
    after: Any

    def to_dict(self) -> dict[str, Any]:
        def j(v: Any) -> Any:
            return "<absent>" if v is _MISSING else v

        return {"key": self.key, "before": j(self.before), "after": j(self.after)}


@dataclass(frozen=True)
class StateDiff:
    kind: str  # "raw" | "canonical" | "projection:<name>"
    changes: tuple[FieldChange, ...]
    created_objects: tuple[tuple[str, str], ...]  # (uuid, name)
    deleted_objects: tuple[tuple[str, str], ...]
    ignored_patterns: tuple[str, ...]
    n_ignored_differences: int
    tolerances: dict[str, float]
    n_within_tolerance: int
    incomplete_reasons: tuple[str, ...]
    exploratory: bool = False
    notes: tuple[str, ...] = field(default=())

    @property
    def equal_on_observed_fields(self) -> bool:
        """No reported difference among the compared fields (NOT exact-state equality)."""
        return not self.changes and not self.created_objects and not self.deleted_objects

    @property
    def supports_exact_equality_claim(self) -> bool:
        return self.equal_on_observed_fields and not self.incomplete_reasons

    def to_dict(self, max_changes: int = 50) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "equal_on_observed_fields": self.equal_on_observed_fields,
            "supports_exact_equality_claim": self.supports_exact_equality_claim,
            "n_changes": len(self.changes),
            "changes": [c.to_dict() for c in self.changes[:max_changes]],
            "created_objects": [list(x) for x in self.created_objects],
            "deleted_objects": [list(x) for x in self.deleted_objects],
            "ignored_patterns": list(self.ignored_patterns),
            "n_ignored_differences": self.n_ignored_differences,
            "tolerances": dict(self.tolerances),
            "n_within_tolerance": self.n_within_tolerance,
            "incomplete_reasons": list(self.incomplete_reasons),
            "exploratory": self.exploratory,
            "notes": list(self.notes),
        }


def flatten_json(obj: Any, path: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten_json(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(obj, list):
        if not obj:
            out[path] = []
        for i, v in enumerate(obj):
            out.update(flatten_json(v, f"{path}[{i}]"))
    else:
        out[path] = obj
    return out


def raw_diff(a: RawState, b: RawState) -> StateDiff:
    """Every difference between two raw states, including texts and the valid-action list."""
    fa, fb = flatten_json(a.to_dict()), flatten_json(b.to_dict())
    changes = tuple(
        FieldChange(k, fa.get(k, _MISSING), fb.get(k, _MISSING))
        for k in sorted(set(fa) | set(fb))
        if fa.get(k, _MISSING) != fb.get(k, _MISSING)
    )
    return StateDiff("raw", changes, (), (), (), 0, {}, 0, ())


def _matches(key: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatchcase(key, p) for p in patterns)


def _numeric(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def canonical_diff(
    a: CanonicalState,
    b: CanonicalState,
    *,
    ignore: tuple[str, ...] = (),
    tolerances: dict[str, float] | None = None,
    kind: str = "canonical",
    exploratory: bool = False,
) -> StateDiff:
    """Field-level difference between two canonical states.

    ``ignore`` and ``tolerances`` take glob patterns over field names (e.g.
    ``"propMaterial.temperatureC"``, ``"world.moves"``, ``"door:*"``). Ignored
    and within-tolerance differences are counted and reported, never hidden.
    """
    tolerances = dict(tolerances or {})
    if a.version != b.version:
        raise ValueError(f"canonical versions differ: {a.version} vs {b.version}")
    changes: list[FieldChange] = []
    n_ignored = n_tol = 0

    def consider(key: str, name: str, before: Any, after: Any) -> None:
        nonlocal n_ignored, n_tol
        if before == after:
            return
        if _matches(name, ignore):
            n_ignored += 1
            return
        tol = next((t for p, t in tolerances.items() if fnmatchcase(name, p)), None)
        if tol is not None and _numeric(before) and _numeric(after) and abs(after - before) <= tol:
            n_tol += 1
            return
        changes.append(FieldChange(key, before, after))

    shared = sorted(set(a.objects) & set(b.objects))
    for uuid in shared:
        ra, rb = a.objects[uuid], b.objects[uuid]
        for f in sorted(set(ra) | set(rb)):
            consider(f"{uuid}:{f}", f, ra.get(f, _MISSING), rb.get(f, _MISSING))
    for w in sorted(set(a.world) | set(b.world)):
        consider(f"world:{w}", f"world.{w}", a.world.get(w, _MISSING), b.world.get(w, _MISSING))
    for room in sorted(set(a.visible_doors) | set(b.visible_doors)):
        consider(
            f"door:{room}",
            f"door:{room}",
            a.visible_doors.get(room, _MISSING),
            b.visible_doors.get(room, _MISSING),
        )

    def names(state: CanonicalState, uuids: set[str]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((u, str(state.objects[u].get("name"))) for u in uuids))

    notes = []
    if a.world.get("agent_location") != b.world.get("agent_location"):
        notes.append("agent location differs: visible_doors describe different rooms")
    return StateDiff(
        kind=kind,
        changes=tuple(changes),
        created_objects=names(b, set(b.objects) - set(a.objects)),
        deleted_objects=names(a, set(a.objects) - set(b.objects)),
        ignored_patterns=tuple(ignore),
        n_ignored_differences=n_ignored,
        tolerances=tolerances,
        n_within_tolerance=n_tol,
        incomplete_reasons=tuple(sorted(set(a.incomplete_reasons) | set(b.incomplete_reasons))),
        exploratory=exploratory,
        notes=tuple(notes),
    )


@dataclass(frozen=True)
class Projection:
    """A named, explicitly exploratory view of a canonical state. NOT a restoration rule."""

    name: str
    ignore: tuple[str, ...]
    tolerances: dict[str, float]
    purpose: str


DISCRETE_EXPLORATION = Projection(
    name="discrete-exploration-v1",
    ignore=("propMaterial.temperatureC", "propMaterial.combustionTicks", "world.moves"),
    tolerances={},
    purpose=(
        "Exploration only: hides continuous/time-driven fields to see discrete effects of an "
        "action. Not an approved definition of exact or partial restoration (OQ-30)."
    ),
)


def projection_diff(a: CanonicalState, b: CanonicalState, projection: Projection) -> StateDiff:
    return canonical_diff(
        a,
        b,
        ignore=projection.ignore,
        tolerances=projection.tolerances,
        kind=f"projection:{projection.name}",
        exploratory=True,
    )
