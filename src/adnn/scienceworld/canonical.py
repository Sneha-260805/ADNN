"""State capture: raw diagnostic state and canonical comparison state (docs/18 §5).

Two representations, never mixed:

* :class:`RawState` keeps everything the simulator exposes: the object tree
  exactly as returned, the free ``look()`` and ``inventory()`` texts, the move
  counter and the sorted valid-action list.
* :class:`CanonicalState` is derived from the raw state by the explicit rules
  in :data:`CANONICAL_RULES` (version :data:`CANONICAL_VERSION`). Every field of
  every tree object is kept. Object identity is the simulator ``uuid``, which
  the Phase 4B trial showed to be deterministic for a fixed task/variation on
  the pinned build (docs/17 §4.2). No uuid-free mapping is applied.

Completeness: the object tree contains no portals (doors), so door states are
known only for the agent's current room, from ``look()``. Agent-internal
state (wait counter, focus monitor, goal progress) is not exposed at all.
Every canonical state therefore carries ``incomplete_reasons`` and
``is_complete == False``. Comparisons must not be read as exact-state equality.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

CANONICAL_VERSION = "sw-canonical-1"

CANONICAL_RULES: tuple[str, ...] = (
    "R1 identity: one record per tree object, keyed by its simulator uuid (string); no "
    "uuid-free remapping",
    "R2 structure: nesting is replaced by a 'parent' field (parent uuid; null for the root) "
    "and a 'path' field (names from the root, '/'-separated, for readability only)",
    "R3 properties: each prop* block is flattened to '<block>.<field>'; an absent block "
    "(JSON null) is recorded as '<block>': null; nothing is dropped",
    "R4 types: propContainer.isContainer is emitted by the simulator as the string "
    "'true'/'false' and is converted to a boolean; all other values keep their JSON type",
    "R5 numbers: floats (e.g. temperatureC) are kept exactly as reported; no rounding or "
    "tolerance is applied in the canonical state",
    "R6 world: 'moves' (simulator move counter) and 'agent_location' (name of the room "
    "containing the agent object) are recorded as world fields",
    "R7 doors: door states are parsed from look() lines 'A door to the <room> (that is "
    "open|closed)' and recorded as visible_doors for the agent's current room only",
    "R8 excluded from canonical state (kept in raw state): look() and inventory() text, "
    "valid-action list, task description, score",
)

INCOMPLETE_DOORS = "doors_outside_current_room_not_observable"
INCOMPLETE_PORTALS = "portals_absent_from_object_tree"
INCOMPLETE_AGENT = "agent_internal_state_not_exposed(wait_counter,focus_monitor,goal_progress)"
BASE_INCOMPLETE_REASONS: tuple[str, ...] = (INCOMPLETE_PORTALS, INCOMPLETE_DOORS, INCOMPLETE_AGENT)

_DOOR_LINE = re.compile(r"^\s*A door to the (.+?) \(that is (open|closed)\)", re.MULTILINE)
_ROOM_LINE = re.compile(r"^This room is called the (.+?)\.", re.MULTILINE)


class StateSource(Protocol):
    def object_tree(self) -> dict[str, Any]: ...
    def look(self) -> str: ...
    def inventory(self) -> str: ...
    def valid_actions(self) -> list[str]: ...
    def moves(self) -> int: ...


def sha256_json(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RawState:
    """Everything the simulator exposes at one moment (diagnostics only)."""

    object_tree: dict[str, Any]
    look: str
    inventory: str
    moves: int
    valid_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_tree": self.object_tree,
            "look": self.look,
            "inventory": self.inventory,
            "moves": self.moves,
            "valid_actions": list(self.valid_actions),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RawState:
        return cls(
            object_tree=d["object_tree"],
            look=d["look"],
            inventory=d["inventory"],
            moves=int(d["moves"]),
            valid_actions=tuple(d["valid_actions"]),
        )

    @property
    def fingerprint(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class CanonicalState:
    """Normalised comparison state (rules R1-R8). Explicitly incomplete."""

    objects: dict[str, dict[str, Any]]  # uuid -> flattened fields
    world: dict[str, Any]
    visible_doors: dict[str, str]  # room -> "open" | "closed" (current room only)
    incomplete_reasons: tuple[str, ...] = BASE_INCOMPLETE_REASONS
    version: str = CANONICAL_VERSION
    notes: tuple[str, ...] = field(default=())

    @property
    def is_complete(self) -> bool:
        return not self.incomplete_reasons

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "objects": self.objects,
            "world": self.world,
            "visible_doors": self.visible_doors,
            "incomplete_reasons": list(self.incomplete_reasons),
            "notes": list(self.notes),
        }

    @property
    def fingerprint(self) -> str:
        return sha256_json(self.to_dict())

    def field_count(self) -> int:
        return sum(len(rec) for rec in self.objects.values())


@dataclass(frozen=True)
class CapturedState:
    raw: RawState
    canonical: CanonicalState

    def to_dict(self) -> dict[str, Any]:
        return {"raw": self.raw.to_dict(), "canonical": self.canonical.to_dict()}


def _flatten_object(node: dict[str, Any], parent: str | None, path: str) -> dict[str, Any]:
    rec: dict[str, Any] = {"parent": parent, "path": path}
    for key, value in node.items():
        if key in ("uuid", "contents"):
            continue
        if key.startswith("prop"):
            if value is None:
                rec[key] = None
                continue
            if not isinstance(value, dict):
                raise ValueError(f"unexpected non-object property block {key}")
            for sub, sub_value in value.items():
                if key == "propContainer" and sub == "isContainer" and isinstance(sub_value, str):
                    sub_value = {"true": True, "false": False}[sub_value.lower()]
                rec[f"{key}.{sub}"] = sub_value
        else:
            rec[key] = value
    return rec


def canonicalize(raw: RawState) -> CanonicalState:
    objects: dict[str, dict[str, Any]] = {}

    def walk(node: dict[str, Any], parent: str | None, path: str) -> None:
        uuid = str(node["uuid"])
        if uuid in objects:
            raise ValueError(f"duplicate uuid {uuid} in object tree")
        objects[uuid] = _flatten_object(node, parent, path)
        for child in (node.get("contents") or {}).values():
            walk(child, uuid, f"{path}/{child.get('name')}")

    root = raw.object_tree
    walk(root, None, str(root.get("name")))

    agent_rooms = [
        objects[rec["parent"]]["name"]
        for rec in objects.values()
        if rec.get("name") == "agent" and rec["parent"] in objects
    ]
    header = _ROOM_LINE.search(raw.look)
    notes: list[str] = []
    location = agent_rooms[0] if len(agent_rooms) == 1 else None
    if len(agent_rooms) != 1:
        notes.append(f"agent objects found: {len(agent_rooms)}")
    if header and location and header.group(1) != location:
        notes.append(f"look() room {header.group(1)!r} != tree room {location!r}")
    return CanonicalState(
        objects=objects,
        world={"moves": raw.moves, "agent_location": location},
        visible_doors={m.group(1): m.group(2) for m in _DOOR_LINE.finditer(raw.look)},
        notes=tuple(notes),
    )


def capture_raw(source: StateSource) -> RawState:
    return RawState(
        object_tree=source.object_tree(),
        look=source.look(),
        inventory=source.inventory(),
        moves=source.moves(),
        valid_actions=tuple(source.valid_actions()),
    )


def capture_state(source: StateSource) -> CapturedState:
    """Capture the raw state with free actions only (no simulation time passes)."""
    raw = capture_raw(source)
    return CapturedState(raw=raw, canonical=canonicalize(raw))
