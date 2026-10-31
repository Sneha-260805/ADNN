"""Blinded declaration packets, a rule-based rubric generator and agreement metrics.

Phase 4H Part 3 (docs/24 §5, ADR-0005 R3-R4).

- :func:`build_packet` turns S0, the target and the task description into a packet that a
  second human annotator can complete later. It contains no property declaration, no
  recovery path and no result, and uses a neutral packet id.
- :func:`rubric_declaration` is a deterministic implementation of the written rubric
  :data:`RUBRIC`. It is a *technical comparison*: agreement between it and the M1
  declarations measures how mechanical the rubric is. It is **not** inter-annotator
  agreement and must never be reported as human validation.
- :func:`compare` measures agreement between two declarations on (bound uuid, field)
  pairs, so role spelling differences do not count as disagreement.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from adnn.scienceworld.canonical import CanonicalState, sha256_json
from adnn.scienceworld.semantics import PART_PREFIX, Declaration, PropertyRef

PACKET_VERSION = "sw-declaration-packet-1"
RUBRIC_VERSION = "sw-declaration-rubric-1"

# The rubric a human annotator follows (docs/preregistration/PHASE4H_ANNOTATOR_PROTOCOL.md).
RUBRIC: tuple[tuple[str, str], ...] = (
    (
        "R1",
        "Designed effect (weight 1): the property the verb is defined to change - "
        "open/close: isOpen; activate/deactivate: isActivated; move/pick up: location of the "
        "moved object; pour: contents of the poured container and presence of each poured "
        "substance; mix: presence of each substance in the mixed container; use lighter on X: "
        "X hasCombusted, isCombusting and present; eat X: X present; connect A to B: "
        "connectedTo of both terminals; teleport: agent location.",
    ),
    (
        "R2",
        "Practical consequence (weight 1): temperature (and, for liquids, state of "
        "matter) of objects placed into, or exposed by opening/activating, a heating or "
        "cooling container or device; contents of containers inside an activated water source.",
    ),
    (
        "R3",
        "Recorded only (weight 0): containers whose contents change as a side effect "
        "(destination of a pour, container of an eaten object, a mixed container's contents).",
    ),
    (
        "R4",
        "Identity: every property refers to the S0 object; objects created by the action "
        "cannot be declared. Choose roles that name exactly one S0 object.",
    ),
    ("R5", "Never consult restoration results, recovery paths or another declaration."),
)
AMBIGUITIES: tuple[tuple[str, str], ...] = (
    (
        "A1",
        "Should temperature changes caused by a thermal device count as a practical "
        "consequence (R2) when they are small over one tick?",
    ),
    (
        "A2",
        "For combustion, is the object's eventual deletion ('present') part of the designed "
        "effect (R1) or only recorded (R3)?",
    ),
    (
        "A3",
        "For pour/mix, is the container's 'contents' the designed effect or are the "
        "substances' identities ('present')?",
    ),
    ("A4", "Is the location of objects inside a container that is opened/closed relevant?"),
    ("A5", "For electrical connections, should both terminals or only the first be declared?"),
    ("A6", "Which recorded side effects (R3) to list at all."),
)
COOLING_OR_HEATING = ("fridge", "freezer", "stove", "oven", "fire pit", "furnace", "blast furnace")
WATER_SOURCES = ("sink", "bathtub", "toilet")
SCENE_FIELDS = (
    "propContainer.isOpen", "propDevice.isActivated", "propDevice.isActivable",
    "propMaterial.temperatureC", "propMaterial.stateOfMatter", "propMaterial.substanceName",
    "propMaterial.hasCombusted", "propMaterial.isCombusting", "propMaterial.combustionTicks",
    "propMoveable.isMovable", "propEdibility.isEdible", "propElectricalConnection.connectedTo",
)  # fmt: skip


def _live(state: CanonicalState) -> dict[str, Mapping[str, Any]]:
    return {u: r for u, r in state.objects.items() if not r.get("isDeleted")}


def role_of(state: CanonicalState, uuid: str) -> str | None:
    """A role string ("name" or "name in parent") that binds to exactly ``uuid``, or None."""
    live = _live(state)
    rec = live[uuid]
    name = rec["name"]
    if sum(1 for r in live.values() if r["name"] == name) == 1:
        return name
    parent = live.get(str(rec.get("parent")), {}).get("name")
    same = [
        u
        for u, r in live.items()
        if r["name"] == name and live.get(str(r.get("parent")), {}).get("name") == parent
    ]
    return f"{name} in {parent}" if same == [uuid] else None


def _children(state: CanonicalState, uuid: str) -> list[str]:
    return sorted(
        u
        for u, r in _live(state).items()
        if str(r.get("parent")) == uuid and not str(r["name"]).startswith(PART_PREFIX)
    )


def _describe(state: CanonicalState, uuid: str, depth: int) -> dict[str, Any]:
    rec = _live(state)[uuid]
    out: dict[str, Any] = {"role": role_of(state, uuid), "name": rec["name"]}
    out.update({f: rec[f] for f in SCENE_FIELDS if rec.get(f) is not None})
    if depth > 0:
        kids = _children(state, uuid)
        if kids:
            out["contains"] = [_describe(state, k, depth - 1) for k in kids]
    return out


def build_packet(
    packet_id: str,
    s0: CanonicalState,
    *,
    room_uuid: str,
    target: str,
    target_ids: Sequence[str],
    task_description: str,
    history: Sequence[str],
) -> dict[str, Any]:
    """The blinded packet: S0 scene, target and task semantics only."""
    live = _live(s0)
    targets = []
    for u in target_ids:
        if u in live:
            parent = str(live[u].get("parent"))
            targets.append(
                {
                    **_describe(s0, u, 2),
                    "container": _describe(s0, parent, 0) if parent in live else None,
                }
            )
    packet = {
        "version": PACKET_VERSION,
        "packet_id": packet_id,
        "task_description": task_description,
        "actions_already_taken": list(history),
        "target_action": target,
        "target_objects": targets,
        "scene": [_describe(s0, u, 3) for u in _children(s0, room_uuid)],
        "rubric_version": RUBRIC_VERSION,
        "form": {"properties": [], "notes": ""},
    }
    packet["sha256"] = sha256_json({k: v for k, v in packet.items() if k != "sha256"})
    return packet


# -- rule-based generator -----------------------------------------------------------------
@dataclass(frozen=True)
class RubricProperty:
    role: str
    field: str
    weight: float
    rule: str


def _is_thermal(obj: Mapping[str, Any]) -> bool:
    return any(k in str(obj.get("name")) for k in COOLING_OR_HEATING)


def _contents(obj: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return list(obj.get("contains", []))


def _thermal_consequences(objs: Iterable[Mapping[str, Any]]) -> list[RubricProperty]:
    out = []
    for o in objs:
        if o.get("role") and "propMaterial.temperatureC" in o:
            out.append(RubricProperty(o["role"], "propMaterial.temperatureC", 1.0, "R2"))
        if o.get("role") and o.get("propMaterial.stateOfMatter") == "liquid":
            out.append(RubricProperty(o["role"], "propMaterial.stateOfMatter", 1.0, "R2"))
        out += _thermal_consequences(_contents(o))
    return out


def _find(packet: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    def walk(objs: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
        for o in objs:
            if o.get("name") == name:
                return o
            hit = walk(_contents(o))
            if hit:
                return hit
        return None

    return walk(packet["scene"])


def rubric_declaration(packet: Mapping[str, Any]) -> list[RubricProperty]:
    """Apply :data:`RUBRIC` mechanically to a packet (deterministic; no results used)."""
    action: str = packet["target_action"]
    tgt = list(packet["target_objects"])
    props: list[RubricProperty] = []
    first = tgt[0] if tgt else {}
    role = first.get("role")
    if action.startswith(("open ", "close ")) and role:
        props.append(RubricProperty(role, "propContainer.isOpen", 1.0, "R1"))
        if _is_thermal(first):
            props += _thermal_consequences(_contents(first))
    elif action.startswith(("activate ", "deactivate ")) and role:
        props.append(RubricProperty(role, "propDevice.isActivated", 1.0, "R1"))
        if _is_thermal(first):
            props += _thermal_consequences(_contents(first))
        if any(k in str(first.get("name")) for k in WATER_SOURCES):
            props += [
                RubricProperty(c["role"], "contents", 1.0, "R2")
                for c in _contents(first)
                if c.get("role")
            ]
    elif action.startswith(("move ", "pick up ")) and role:
        props.append(RubricProperty(role, "location", 1.0, "R1"))
        dest = tgt[1] if len(tgt) > 1 else {}
        if dest and _is_thermal(dest):
            props += _thermal_consequences([first])
    elif action.startswith("pour ") and role:
        props.append(RubricProperty(role, "contents", 1.0, "R1"))
        props += [
            RubricProperty(c["role"], "present", 1.0, "R1")
            for c in _contents(first)
            if c.get("role")
        ]
        if len(tgt) > 1 and tgt[1].get("role"):
            props.append(RubricProperty(tgt[1]["role"], "contents", 0.0, "R3"))
    elif action.startswith("mix ") and role:
        props += [
            RubricProperty(c["role"], "present", 1.0, "R1")
            for c in _contents(first)
            if c.get("role")
        ]
        props.append(RubricProperty(role, "contents", 0.0, "R3"))
    elif action.startswith("use lighter on "):
        burned = tgt[-1] if tgt else {}
        if burned.get("role"):
            props += [
                RubricProperty(burned["role"], "propMaterial.hasCombusted", 1.0, "R1"),
                RubricProperty(burned["role"], "propMaterial.isCombusting", 1.0, "R1"),
                RubricProperty(burned["role"], "present", 1.0, "R1"),
            ]
    elif action.startswith("eat ") and role:
        props.append(RubricProperty(role, "present", 1.0, "R1"))
        cont = first.get("container") or {}
        if cont.get("role"):
            props.append(RubricProperty(cont["role"], "contents", 0.0, "R3"))
    elif action.startswith("connect "):
        props += [
            RubricProperty(t["role"], "propElectricalConnection.connectedTo", 1.0, "R1")
            for t in tgt
            if t.get("role")
        ]
    elif action.startswith("teleport to "):
        agent = _find(packet, "agent")
        if agent and agent.get("role"):
            props.append(RubricProperty(agent["role"], "location", 1.0, "R1"))
    seen: dict[tuple[str, str], RubricProperty] = {}
    for p in props:
        seen.setdefault((p.role, p.field), p)
    return list(seen.values())


def rubric_to_declaration(
    case_id: str, definition: str, props: Sequence[RubricProperty]
) -> Declaration:
    return Declaration(
        case_id,
        definition,
        tuple(PropertyRef(p.role, p.field, p.weight) for p in props),
        rationale=f"generated by {RUBRIC_VERSION}: "
        + ", ".join(f"{p.role}.{p.field}={p.rule}" for p in props),
    )


# -- agreement ------------------------------------------------------------------------------
def _pairs(decl: Declaration, binding: Mapping[str, str]) -> dict[tuple[str, str], float]:
    return {(binding[r.role], r.field): r.weight for r in decl.required if r.role in binding}


def _jaccard(a: set[Any], b: set[Any]) -> float | None:
    return None if not a and not b else round(len(a & b) / len(a | b), 3)


def compare(
    a: Declaration, a_binding: Mapping[str, str], b: Declaration, b_binding: Mapping[str, str]
) -> dict[str, Any]:
    """Agreement on (uuid, field) pairs and on which pairs carry weight > 0."""
    pa, pb = _pairs(a, a_binding), _pairs(b, b_binding)
    wa = {k for k, w in pa.items() if w > 0}
    wb = {k for k, w in pb.items() if w > 0}
    shared = set(pa) & set(pb)
    return {
        "jaccard_all": _jaccard(set(pa), set(pb)),
        "jaccard_weighted": _jaccard(wa, wb),
        "weight_flag_agreement_on_shared": (
            round(sum((pa[k] > 0) == (pb[k] > 0) for k in shared) / len(shared), 3)
            if shared
            else None
        ),
        "only_a": sorted(f"{u}:{f}" for u, f in set(pa) - set(pb)),
        "only_b": sorted(f"{u}:{f}" for u, f in set(pb) - set(pa)),
        "weight_disagreements": sorted(
            f"{u}:{f}" for u, f in shared if (pa[(u, f)] > 0) != (pb[(u, f)] > 0)
        ),
    }
