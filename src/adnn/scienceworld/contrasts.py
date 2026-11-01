"""Targeted state-contrast generators and two-level minimal-pair criteria (Phase 4F, docs/22 §3-4).

A :class:`ContrastSpec` builds two states that share a history and then differ by a
*controlled* intervention (container empty vs full, source on vs off, device on vs off,
object here vs there). The same byte-identical target action is then evaluated in both.

Two candidate levels (neither is a gold minimal pair, RD-09 / ADR-0003 M-08):

* **structural candidate**: byte-identical target text, valid (accepted, unambiguous,
  same uuids, observed effect) in both states, intended difference present, ticks
  matched, both states replay-verified;
* **restoration-contrast candidate**: a structural candidate whose restoration evidence
  differs under a *declared* comparison method (exact, 0.01 degC or 0.1 degC
  counterfactual match). Evidence that is not comparable on either side (no candidate
  path, counterfactual unavailable) never counts as a difference.

Uncontrolled differences (anything other than the intended fields, objects created or
deleted along the way, temperature changes) are recorded, never hidden.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from adnn.scienceworld.canonical import CanonicalState
from adnn.scienceworld.diagnostics import DISCRETE_EXPLORATION, canonical_diff, projection_diff
from adnn.scienceworld.env import Backend
from adnn.scienceworld.provenance import RuntimeConfig
from adnn.scienceworld.provisional import (
    IDLE_ACTION,
    MATCH_LEVELS,
    PILOT_FAMILIES,
    SCIENTIFIC_STATUS,
    FamilySpec,
    content_sha256,
    leakage_problems,
)

CONTRAST_SCHEMA_VERSION = "sw-contrast-pair-0.1"
KINDS = ("container_fill", "source_state", "device_state", "object_location")
METHODS: dict[str, tuple[str, ...]] = {  # declared comparison -> match levels that count as a match
    "exact": ("exact",),
    "tol_0.01C": ("exact", "within_0.01C"),
    "tol_0.1C": ("exact", "within_0.01C", "within_0.1C"),
}
COMPARABLE_LEVELS = frozenset(MATCH_LEVELS) - {"not_compared"}
GOLD_STATUS = "not_a_gold_minimal_pair"
STOCHASTIC_NAMES = ("bee",)  # RNG-driven agents (Bee.scala); excluded in Phase 4F
STOCHASTIC_AGENT = re.compile(r"^bee \d+$")  # "bee 0".."bee 4", not "bee hive"

KITCHEN, WORKSHOP, GREENHOUSE = PILOT_FAMILIES


@dataclass(frozen=True)
class IntendedChange:
    """A controlled difference: ``object`` must differ in ``field`` between state A and B."""

    object: str
    field: str


@dataclass(frozen=True)
class ContrastSpec:
    contrast_id: str
    kind: str
    family: FamilySpec
    shared: tuple[str, ...]
    variant_a: tuple[str, ...]
    variant_b: tuple[str, ...]
    target: str
    intended: tuple[IntendedChange, ...]
    description: str

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown contrast kind {self.kind!r}")
        if not self.intended:
            raise ValueError("a contrast must declare its intended difference")

    def histories(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Both histories, the shorter variant padded with idle ticks (tick matching)."""
        a, b = list(self.variant_a), list(self.variant_b)
        n = max(len(a), len(b))
        a += [IDLE_ACTION] * (n - len(a))
        b += [IDLE_ACTION] * (n - len(b))
        return (*self.shared, *a), (*self.shared, *b)

    def to_dict(self) -> dict[str, Any]:
        ha, hb = self.histories()
        return {
            "contrast_id": self.contrast_id,
            "kind": self.kind,
            "family_id": self.family.family_id,
            "shared": list(self.shared),
            "variant_a": list(self.variant_a),
            "variant_b": list(self.variant_b),
            "history_a": list(ha),
            "history_b": list(hb),
            "target": self.target,
            "intended": [{"object": i.object, "field": i.field} for i in self.intended],
            "description": self.description,
        }


def contrast_specs() -> tuple[ContrastSpec, ...]:
    """The Phase 4F generator set: templated over objects, deterministic, no bee hive."""
    out: list[ContrastSpec] = []
    open_cup = ("open cupboard",)
    # source on vs off: a container moved into an active vs inactive sink
    for fam, prep, objs in (
        (KITCHEN, open_cup, ("metal pot", "ceramic cup", "tin cup")),
        (GREENHOUSE, (), ("flower pot 1", "jug")),
    ):
        for obj in objs:
            out.append(
                ContrastSpec(
                    f"source-sink-{fam.family_id}-{obj.replace(' ', '_')}",
                    "source_state",
                    fam,
                    prep,
                    (),
                    ("activate sink",),
                    f"move {obj} to sink",
                    (IntendedChange("sink", "propDevice.isActivated"),),
                    f"sink off vs on, then move {obj} into it",
                )
            )
    # device activated vs deactivated: stove on vs off, then put a container on it
    for obj in ("metal pot", "ceramic cup", "tin cup"):
        out.append(
            ContrastSpec(
                f"device-stove-{obj.replace(' ', '_')}",
                "device_state",
                KITCHEN,
                open_cup,
                (),
                ("activate stove",),
                f"move {obj} to stove",
                (IntendedChange("stove", "propDevice.isActivated"),),
                f"stove off vs on, then move {obj} onto it",
            )
        )
    # object in one location vs another, then a device acting on that location
    for obj in ("metal pot", "ceramic cup"):
        out.append(
            ContrastSpec(
                f"location-stove-{obj.replace(' ', '_')}",
                "object_location",
                KITCHEN,
                open_cup,
                (f"move {obj} to table",),
                (f"move {obj} to stove",),
                "activate stove",
                (IntendedChange(obj, "parent"),),
                f"{obj} on the table vs on the stove, then activate the stove",
            )
        )
        out.append(
            ContrastSpec(
                f"location-sink-{obj.replace(' ', '_')}",
                "object_location",
                KITCHEN,
                open_cup,
                (f"move {obj} to table",),
                (f"move {obj} to sink",),
                "activate sink",
                (IntendedChange(obj, "parent"),),
                f"{obj} on the table vs in the sink, then activate the sink",
            )
        )
    out.append(
        ContrastSpec(
            "location-sink-greenhouse-flower_pot_1",
            "object_location",
            GREENHOUSE,
            (),
            ("move flower pot 1 to inventory",),
            ("move flower pot 1 to sink",),
            "activate sink",
            (IntendedChange("flower pot 1", "parent"),),
            "flower pot 1 carried vs in the sink, then activate the sink",
        )
    )
    # container empty vs full (water from the sink, container returned to the same place)
    fill = ("move metal pot to sink", "activate sink", "deactivate sink", "move metal pot to table")
    for target, extra in (
        ("move metal pot to stove", ("activate stove",)),
        ("pick up metal pot", ()),
        ("pour metal pot into ceramic cup", ()),
    ):
        out.append(
            ContrastSpec(
                f"fill-metal_pot-{target.split()[0]}-{target.split()[-1]}",
                "container_fill",
                KITCHEN,
                (*open_cup, *extra),
                ("move metal pot to table",),
                fill,
                target,
                (IntendedChange("water", "parent"),),
                f"metal pot empty vs filled with sink water (both on the table), then {target!r}",
            )
        )
    return tuple(out)


# -- evaluation -------------------------------------------------------------------------------
def _name_of(state: CanonicalState, uuid: str) -> str:
    return str(state.objects.get(uuid, {}).get("name"))


def state_contrast(a: CanonicalState, b: CanonicalState, spec: ContrastSpec) -> dict[str, Any]:
    """Intended vs uncontrolled differences between the two pre-action states."""
    discrete = projection_diff(a, b, DISCRETE_EXPLORATION)
    exact = canonical_diff(a, b)
    intended_keys = {(i.object, i.field) for i in spec.intended}
    intended, uncontrolled = [], []
    for ch in discrete.changes:
        uuid, _, fld = ch.key.partition(":")
        name = uuid if uuid in ("world", "door") else _name_of(a if uuid in a.objects else b, uuid)
        row = {"object": name, "field": fld, **ch.to_dict()}
        (intended if (name, fld) in intended_keys else uncontrolled).append(row)
    one_sided = (*discrete.created_objects, *discrete.deleted_objects)
    # an intended change on an object present in only one state (e.g. new water) is "created"
    present = {o for o, _ in intended_keys if o in {n for _, n in one_sided}}
    # parts of such an object (its electrical terminals) belong to the intended difference
    whole = {u for u, n in one_sided if n in present}
    part_ids = {
        u
        for u, _ in one_sided
        if str((a.objects.get(u) or b.objects.get(u) or {}).get("parent")) in whole
    }
    parts = [n for u, n in one_sided if u in part_ids]
    created = [n for u, n in discrete.created_objects if u not in part_ids]
    deleted = [n for u, n in discrete.deleted_objects if u not in part_ids]
    temps = [
        abs(c.after - c.before)
        for c in exact.changes
        if c.key.endswith("propMaterial.temperatureC")
        and isinstance(c.before, int | float)
        and isinstance(c.after, int | float)
    ]
    return {
        "intended_present": bool(intended) or bool(present),
        "intended_changes": intended,
        "intended_objects_created_or_deleted": sorted(present),
        "parts_of_intended_objects": sorted(parts),
        "uncontrolled_changes": uncontrolled[:25],
        "n_uncontrolled_changes": len(uncontrolled),
        "uncontrolled_created": sorted(n for n in created if n not in present),
        "uncontrolled_deleted": sorted(n for n in deleted if n not in present),
        "n_temperature_changes": len(temps),
        "max_abs_temperature_delta": round(max(temps, default=0.0), 6),
        "moves_equal": a.world.get("moves") == b.world.get("moves"),
    }


def matched_under(record: Mapping[str, Any], method: str) -> bool | None:
    """True/False if the record's best counterfactual comparison matches under ``method``;
    None when no comparable evidence exists (never treated as a mismatch)."""
    level = record["restoration_evidence"]["best_counterfactual_match_level"]
    if level not in COMPARABLE_LEVELS:
        return None
    return level in METHODS[method]


def _consequence(record: Mapping[str, Any]) -> dict[str, Any]:
    eff = record["target"]["observed_effect"]
    ev = record["restoration_evidence"]
    return {
        "evidence_status": ev["evidence_status"],
        "best_counterfactual_match_level": ev["best_counterfactual_match_level"],
        "n_paths_executed": ev["candidate_set"]["n_paths_executed"],
        "effect_changes": [f"{c['object']}:{c['field']}" for c in eff["changes"]][:12],
        "created": sorted(n for _, n in eff["created_objects"]),
        "deleted": sorted(n for _, n in eff["deleted_objects"]),
    }


def stochastic_exposure(state: CanonicalState) -> list[str]:
    """RNG-driven agents outside a closed container (their next tick is uncontrolled)."""
    out = []
    for r in state.objects.values():
        name = str(r.get("name", ""))
        if not STOCHASTIC_AGENT.match(name):
            continue
        parent = state.objects.get(str(r.get("parent")), {})
        if parent.get("propContainer.isOpen") is not False:  # open, unclosable or a room
            out.append(f"{name} in {parent.get('name')}")
    return sorted(out)


def evaluate_contrast(
    spec: ContrastSpec,
    rec_a: Mapping[str, Any],
    rec_b: Mapping[str, Any],
    state_a: CanonicalState,
    state_b: CanonicalState,
) -> dict[str, Any]:
    """Classify one built contrast. Pure: needs the two evidence records and S0 states."""
    ta, tb = rec_a["target"], rec_b["target"]
    sc = state_contrast(state_a, state_b, spec)
    checks = {
        "byte_identical_target": ta["action"] == tb["action"] == spec.target,
        "valid_in_both": all(
            t["valid_in_state"] and t["status"] == "accepted" and t["n_templates_with_text"] == 1
            for t in (ta, tb)
        ),
        "effect_in_both": all(
            t["observed_effect"]["n_changes"]
            or t["observed_effect"]["created_objects"]
            or t["observed_effect"]["deleted_objects"]
            for t in (ta, tb)
        ),
        "same_referents": ta["obj_ids"] == tb["obj_ids"],
        "intended_difference_present": sc["intended_present"],
        "ticks_matched": sc["moves_equal"],
        "replay_verified": rec_a["replay_verification"]["verified"]
        and rec_b["replay_verification"]["verified"],
        "no_stochastic_exposure": not (
            stochastic_exposure(state_a) or stochastic_exposure(state_b)
        ),
        "not_bee_scenario": not any(s in spec.target for s in STOCHASTIC_NAMES),
    }
    structural = all(checks.values())
    per_method = {}
    for m in METHODS:
        ma, mb = matched_under(rec_a, m), matched_under(rec_b, m)
        per_method[m] = {
            "a_matched": ma,
            "b_matched": mb,
            "comparable": ma is not None and mb is not None,
            "differs": ma is not None and mb is not None and ma != mb,
        }
    restoration_contrast = structural and any(v["differs"] for v in per_method.values())
    pair: dict[str, Any] = {
        "schema_version": CONTRAST_SCHEMA_VERSION,
        "contrast": spec.to_dict(),
        "record_ids": [rec_a["example_id"], rec_b["example_id"]],
        "checks": checks,
        "rejection_reasons": sorted(k for k, v in checks.items() if not v),
        "state_contrast": sc,
        "consequences": {"a": _consequence(rec_a), "b": _consequence(rec_b)},
        "restoration_comparison": per_method,
        "structural_candidate": structural,
        "restoration_contrast_candidate": restoration_contrast,
        "restoration_contrast_methods": sorted(m for m, v in per_method.items() if v["differs"])
        if structural
        else [],
        "level": "restoration_contrast_candidate"
        if restoration_contrast
        else "structural_candidate"
        if structural
        else "rejected",
        "gold_status": GOLD_STATUS,
        "scientific_status": dict(SCIENTIFIC_STATUS),
    }
    pair["content_sha256"] = content_sha256(pair)
    return pair


def validate_contrast_pair(pair: Mapping[str, Any]) -> list[str]:
    """Structural integrity of a contrast pair (no Java)."""
    errors = []
    if pair.get("schema_version") != CONTRAST_SCHEMA_VERSION:
        errors.append("schema_version")
    if pair.get("content_sha256") != content_sha256(pair):
        errors.append("content_checksum")
    if pair.get("gold_status") != GOLD_STATUS:
        errors.append("claims gold status")
    if pair.get("scientific_status") != SCIENTIFIC_STATUS:
        errors.append("scientific_status")
    structural = all(pair["checks"].values())
    if pair["structural_candidate"] != structural:
        errors.append("structural flag inconsistent with checks")
    differs = any(v["differs"] for v in pair["restoration_comparison"].values())
    if pair["restoration_contrast_candidate"] != (structural and differs):
        errors.append("restoration-contrast flag inconsistent")
    for m, v in pair["restoration_comparison"].items():
        if v["differs"] and not v["comparable"]:
            errors.append(f"{m}: difference claimed without comparable evidence")
    errors += [f"leakage: {p}" for p in leakage_problems(pair)]
    return errors


def build_contrast(
    spec: ContrastSpec,
    *,
    runtime: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
) -> tuple[dict[str, Any] | None, list[tuple[dict[str, Any], bytes]], str | None]:
    """Build both states, collect evidence for each, classify. Returns (pair, records, failure)."""
    from adnn.scienceworld.provisional_sampling import collect_evidence, explicit_example

    ha, hb = spec.histories()
    examples = []
    for history in (ha, hb):
        try:
            examples.append(
                explicit_example(
                    spec.family,
                    history,
                    spec.target,
                    runtime=runtime,
                    backend_factory=backend_factory,
                    allow_idle=True,
                )
            )
        except ValueError as exc:
            return None, [], f"variant_not_buildable: {exc}"
    built = [
        collect_evidence(ex, runtime=runtime, backend_factory=backend_factory) for ex in examples
    ]
    (rec_a, bytes_a, _), (rec_b, bytes_b, _) = built
    pair = evaluate_contrast(spec, rec_a, rec_b, examples[0].s0.canonical, examples[1].s0.canonical)
    return pair, [(rec_a, bytes_a), (rec_b, bytes_b)], None
