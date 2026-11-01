"""Exploratory structural object matching across re-created objects (docs/19 §5).

ScienceWorld gives every newly constructed object a fresh uuid
(``UniqueIdentifier.getNextID()``, a creation counter). Refilling a pot from the
sink, or any process that deletes and re-creates a substance, therefore yields
an object that may look the same but has a different uuid. The canonical
comparison contract (``canonical.py`` rule R1: identity = uuid) deliberately
reports such objects as deleted + created.

This module is a **separate, exploratory** view on top of two canonical states.
It does not modify them and does not replace R1. It answers: *which deleted
objects have a structurally indistinguishable counterpart among the created
ones, under these documented fields?* Rules:

* S1 uuid identity first: an object present in both states is the same object
  (relocations are reported, never re-matched).
* S2 signature: every canonical field except :data:`DEFAULT_SIGNATURE_IGNORE`
  (and caller-supplied ignores); uuid-valued fields (:data:`UUID_VALUED_FIELDS`)
  enter the signature only as their length.
* S3 location (``location_sensitive=True``): a deleted object can match a
  created object only in the *same* container, where "same" means the same
  uuid, or the structural counterpart of a matched parent. Processed top-down,
  so hidden terminals follow their substance.
* S4 uniqueness: a match is made only when exactly one deleted and exactly one
  created object share (signature, location). Otherwise every candidate is
  reported in an :class:`AmbiguousGroup`; **nothing is forced**.

A structural match means "replaced by an indistinguishable object", never "the
original object came back". Original simulator uuids are preserved throughout.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any

from adnn.scienceworld.canonical import CanonicalState
from adnn.scienceworld.diagnostics import FieldChange

STRUCTURAL_VERSION = "sw-structural-0-exploratory"
DEFAULT_SIGNATURE_IGNORE: tuple[str, ...] = ("parent", "path", "propMaterial.temperatureC")
UUID_VALUED_FIELDS: tuple[str, ...] = ("propElectricalConnection.connectedTo",)
_UNRESOLVED = "<unresolved-parent>"


def _ignored(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatchcase(name, p) for p in patterns)


def signature(record: dict[str, Any], ignore: tuple[str, ...] = DEFAULT_SIGNATURE_IGNORE) -> str:
    """Deterministic structural signature of one canonical object record (rules S2)."""
    items: dict[str, Any] = {}
    for k, v in record.items():
        if _ignored(k, ignore):
            continue
        if k in UUID_VALUED_FIELDS and isinstance(v, list):
            v = {"<uuid-valued-count>": len(v)}
        items[k] = v
    return json.dumps(items, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class StructuralMatch:
    uuid_before: str
    uuid_after: str
    name: str
    location: str  # matched container uuid (after-state) or "*" when location-insensitive
    ignored_differences: tuple[FieldChange, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "uuid_before": self.uuid_before,
            "uuid_after": self.uuid_after,
            "name": self.name,
            "location": self.location,
            "ignored_differences": [c.to_dict() for c in self.ignored_differences],
        }


@dataclass(frozen=True)
class AmbiguousGroup:
    name: str
    location: str
    uuids_before: tuple[str, ...]
    uuids_after: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "location": self.location,
            "uuids_before": list(self.uuids_before),
            "uuids_after": list(self.uuids_after),
        }


@dataclass(frozen=True)
class StructuralReport:
    version: str
    location_sensitive: bool
    signature_ignore: tuple[str, ...]
    n_uuid_identity: int
    relocated: tuple[tuple[str, str, str, str], ...]  # (uuid, name, parent_before, parent_after)
    matches: tuple[StructuralMatch, ...]
    ambiguous: tuple[AmbiguousGroup, ...]
    unmatched_before: tuple[tuple[str, str], ...]  # (uuid, name): deleted, no counterpart
    unmatched_after: tuple[tuple[str, str], ...]  # (uuid, name): created, no counterpart
    indistinguishable_before: tuple[AmbiguousGroup, ...]  # same signature + container, >1
    indistinguishable_after: tuple[AmbiguousGroup, ...]
    exploratory: bool = True
    notes: tuple[str, ...] = field(default=())

    @property
    def all_objects_accounted(self) -> bool:
        """Every object has a uuid or unique structural counterpart and none moved.

        Even when True this is NOT exact-state equality: canonical states are incomplete,
        and structurally matched objects are replacements with different uuids.
        """
        return not (
            self.relocated or self.ambiguous or self.unmatched_before or self.unmatched_after
        )

    def to_dict(self, max_items: int = 50) -> dict[str, Any]:
        return {
            "version": self.version,
            "exploratory": self.exploratory,
            "location_sensitive": self.location_sensitive,
            "signature_ignore": list(self.signature_ignore),
            "uuid_valued_fields_as_counts": list(UUID_VALUED_FIELDS),
            "all_objects_accounted": self.all_objects_accounted,
            "n_uuid_identity": self.n_uuid_identity,
            "relocated": [list(r) for r in self.relocated[:max_items]],
            "matches": [m.to_dict() for m in self.matches[:max_items]],
            "ambiguous": [g.to_dict() for g in self.ambiguous[:max_items]],
            "unmatched_before": [list(u) for u in self.unmatched_before[:max_items]],
            "unmatched_after": [list(u) for u in self.unmatched_after[:max_items]],
            "n_indistinguishable_groups_before": len(self.indistinguishable_before),
            "n_indistinguishable_groups_after": len(self.indistinguishable_after),
            "notes": list(self.notes),
        }


def _depth(rec: dict[str, Any]) -> int:
    return str(rec.get("path", "")).count("/")


def _indistinguishable(
    state: CanonicalState, ignore: tuple[str, ...]
) -> tuple[AmbiguousGroup, ...]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for uuid, rec in state.objects.items():
        groups[(signature(rec, ignore), str(rec.get("parent")))].append(uuid)
    out = []
    for (_, parent), uuids in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[1])):
        if len(uuids) > 1:
            name = str(state.objects[uuids[0]].get("name"))
            out.append(AmbiguousGroup(name, parent, tuple(sorted(uuids)), ()))
    return tuple(out)


def structural_match(
    before: CanonicalState,
    after: CanonicalState,
    *,
    ignore: tuple[str, ...] = DEFAULT_SIGNATURE_IGNORE,
    location_sensitive: bool = True,
) -> StructuralReport:
    """Exploratory structural correspondence between two canonical states (rules S1-S4)."""
    if before.version != after.version:
        raise ValueError(f"canonical versions differ: {before.version} vs {after.version}")
    a, b = before.objects, after.objects
    shared = set(a) & set(b)
    mapping: dict[str, str] = {u: u for u in shared}  # before uuid -> after uuid
    relocated = tuple(
        sorted(
            (u, str(a[u].get("name")), str(a[u].get("parent")), str(b[u].get("parent")))
            for u in shared
            if a[u].get("parent") != b[u].get("parent")
        )
    )
    gone = sorted(set(a) - shared, key=lambda u: (_depth(a[u]), u))
    available = set(b) - shared
    matches: list[StructuralMatch] = []
    ambiguous: list[AmbiguousGroup] = []
    unmatched_before: list[str] = []
    notes: list[str] = []
    n_unresolved = 0

    def location_before(u: str) -> str:
        if not location_sensitive:
            return "*"
        return mapping.get(str(a[u].get("parent")), _UNRESOLVED)

    def location_after(u: str) -> str:
        return str(b[u].get("parent")) if location_sensitive else "*"

    # Process deleted objects level by level, so a parent's match is known before its children.
    levels: dict[int, list[str]] = defaultdict(list)
    for u in gone:
        levels[_depth(a[u]) if location_sensitive else 0].append(u)
    for level in sorted(levels):
        want: dict[tuple[str, str], list[str]] = defaultdict(list)
        for u in levels[level]:
            loc = location_before(u)
            if loc == _UNRESOLVED:
                unmatched_before.append(u)
                n_unresolved += 1
                continue
            want[(signature(a[u], ignore), loc)].append(u)
        have: dict[tuple[str, str], list[str]] = defaultdict(list)
        for u in sorted(available):
            have[(signature(b[u], ignore), location_after(u))].append(u)
        for key in sorted(want):
            ws, hs = want[key], have.get(key, [])
            if not hs:
                unmatched_before.extend(ws)
            elif len(ws) == 1 and len(hs) == 1:
                ub, ua = ws[0], hs[0]
                mapping[ub] = ua
                available.discard(ua)
                diffs = tuple(
                    FieldChange(f"{ub}->{ua}:{f}", a[ub].get(f), b[ua].get(f))
                    for f in sorted(set(a[ub]) | set(b[ua]))
                    if f not in ("parent", "path") and a[ub].get(f) != b[ua].get(f)
                )
                matches.append(StructuralMatch(ub, ua, str(a[ub].get("name")), key[1], diffs))
            else:
                ambiguous.append(
                    AmbiguousGroup(str(a[ws[0]].get("name")), key[1], tuple(ws), tuple(hs))
                )
                available.difference_update(hs)
    if not location_sensitive:
        notes.append("location-insensitive: containers ignored; ambiguity is expected")
    if n_unresolved:
        notes.append(
            f"{n_unresolved} deleted object(s) left unmatched because their container has no "
            "unique counterpart (deleted, ambiguous or unmatched)"
        )
    return StructuralReport(
        version=STRUCTURAL_VERSION,
        location_sensitive=location_sensitive,
        signature_ignore=tuple(ignore),
        n_uuid_identity=len(shared),
        relocated=relocated,
        matches=tuple(matches),
        ambiguous=tuple(ambiguous),
        unmatched_before=tuple(sorted((u, str(a[u].get("name"))) for u in unmatched_before)),
        unmatched_after=tuple(sorted((u, str(b[u].get("name"))) for u in available)),
        indistinguishable_before=_indistinguishable(before, ignore),
        indistinguishable_after=_indistinguishable(after, ignore),
        notes=tuple(notes),
    )
