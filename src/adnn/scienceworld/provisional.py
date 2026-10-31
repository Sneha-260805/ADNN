"""Provisional ScienceWorld evidence records, candidate minimal pairs and validation (docs/21).

Phase 4E stores *restoration evidence* for sampled ScienceWorld state-action pairs.
It deliberately stores **no reversibility label**:

* A record is not a gold example. It is not in the dataset schema (contract C1,
  ``adnn.dataset.schema``), and the validator rejects any label-like field or value.
* The primary comparison is time-matched counterfactual restoration (RD-01,
  ``docs/decisions/0002``). Temperatures are compared at exact equality, 0.01 degC and
  0.1 degC (RD-02); they are never dropped.
* Exact, partial, irreversible and undetermined are distinct concepts (RD-03). A record
  carries neutral evidence statuses (:data:`EVIDENCE_STATUSES`), never one of those
  four words as a verdict. A failed restricted search is not irreversibility (RD-04).
* Door actions are excluded from the candidate pool (RD-05).
* Every methodological choice is a research-team decision, **not professor-approved**
  (:data:`SCIENTIFIC_STATUS`).

This module never starts Java. Sampling and evidence collection live in
:mod:`adnn.scienceworld.provisional_sampling`.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any

from adnn.dataset.schema import ALL_FIELDS as GOLD_FIELDS
from adnn.dataset.schema import LABELS
from adnn.scienceworld.canonical import (
    BASE_INCOMPLETE_REASONS,
    CANONICAL_VERSION,
    CanonicalState,
    CapturedState,
    RawState,
    canonicalize,
    sha256_json,
)
from adnn.scienceworld.diagnostics import (
    DISCRETE_EXPLORATION,
    TEMPERATURE_TOLERANCE_001,
    TEMPERATURE_TOLERANCE_01,
    canonical_diff,
    projection_diff,
)
from adnn.scienceworld.env import ActionTemplate
from adnn.scienceworld.provenance import PINNED
from adnn.scienceworld.replay import FIRST_TICK_PREPARATION, ReplayRecipe
from adnn.scienceworld.restoration_diagnostics import (
    DIAGNOSTICS_VERSION,
    FAILED_SEARCH_MEANING,
    SEARCH_SCOPE,
    PathAttempt,
    RestorationDiagnostic,
)

EVIDENCE_SCHEMA_VERSION = "sw-evidence-0.1"
PAIR_SCHEMA_VERSION = "sw-candidate-pair-0.1"
DECISION_LOG = "docs/decisions/0002-scienceworld-provisional-methodology.md"
MAX_LISTED_CHANGES = 25

SCIENTIFIC_STATUS: dict[str, Any] = {
    "status": "provisional_evidence_only",
    "gold_labels_issued": False,
    "professor_approved": False,
    "methodology_owner": "ADNN research team (Member 1 draft, docs/decisions/0002)",
    "decision_log": DECISION_LOG,
}

# -- RD-01 / RD-02: primary method and temperature sensitivity ------------------------------
PRIMARY_METHOD = "time_matched_counterfactual"
IDLE_ACTION = "look at agent"  # 1 tick, no discrete effect (docs/19 §2)
MODE_EXACT = "counterfactual_canonical"
MODE_TOL_001 = f"counterfactual_projection:{TEMPERATURE_TOLERANCE_001.name}"
MODE_TOL_01 = f"counterfactual_projection:{TEMPERATURE_TOLERANCE_01.name}"
MODE_DISCRETE = f"counterfactual_projection:{DISCRETE_EXPLORATION.name}"
MATCH_LADDER: tuple[tuple[str, str], ...] = (
    ("exact", MODE_EXACT),
    ("within_0.01C", MODE_TOL_001),
    ("within_0.1C", MODE_TOL_01),
)
MATCH_NONE = "none"
MATCH_NOT_COMPARED = "not_compared"
MATCH_LEVELS: tuple[str, ...] = (*(lv for lv, _ in MATCH_LADDER), MATCH_NONE, MATCH_NOT_COMPARED)

# -- RD-03 / RD-04: neutral record-level evidence statuses (never labels) --------------------
EV_TARGET_NOT_EXECUTED = "target_not_executed"
EV_NO_CANDIDATE = "no_candidate_path_found"
EV_NOT_EXECUTED = "no_candidate_path_executed"
EV_CF_UNAVAILABLE = "counterfactual_unavailable"
EV_MATCH_EXACT = "counterfactual_match_exact"
EV_MATCH_001 = "counterfactual_match_within_0.01C"
EV_MATCH_01 = "counterfactual_match_within_0.1C"
EV_MISMATCH = "counterfactual_mismatch_at_all_tolerances"
EVIDENCE_STATUSES: tuple[str, ...] = (
    EV_TARGET_NOT_EXECUTED,
    EV_NO_CANDIDATE,
    EV_NOT_EXECUTED,
    EV_CF_UNAVAILABLE,
    EV_MATCH_EXACT,
    EV_MATCH_001,
    EV_MATCH_01,
    EV_MISMATCH,
)
_STATUS_BY_LEVEL = {
    "exact": EV_MATCH_EXACT,
    "within_0.01C": EV_MATCH_001,
    "within_0.1C": EV_MATCH_01,
    MATCH_NONE: EV_MISMATCH,
}
INTERPRETATION_CONSTRAINTS: tuple[str, ...] = (
    "RD-09: Phase 4E issues no gold labels; this record is evidence, not a label.",
    "RD-03: exact, partial, irreversible and undetermined are distinct concepts; no evidence "
    "status below is a synonym for any of them.",
    "RD-04: the candidate set is restricted; a missing or non-matching candidate path is not "
    "evidence that the action cannot be undone.",
    "Observed fields only: the canonical state is incomplete (observation_completeness), so a "
    "match is never a claim of exact simulator-state equality.",
)

# -- action classes, RD-05 door exclusion ------------------------------------------------
VERB_CLASSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("open_close", re.compile(r"^(open|close) ")),
    ("activate_deactivate", re.compile(r"^(activate|deactivate) ")),
    ("move", re.compile(r"^move ")),
    ("pick_up", re.compile(r"^pick up ")),
    ("pour", re.compile(r"^pour ")),
    ("eat", re.compile(r"^eat ")),
    ("mix", re.compile(r"^mix ")),
    ("connect", re.compile(r"^connect ")),
)
# Classes with at least one inverse rule in the Phase 4D registry.
RULE_COVERED_CLASSES: frozenset[str] = frozenset(
    {"open_close", "activate_deactivate", "move", "pick_up", "pour"}
)
PREFIX_CLASSES = RULE_COVERED_CLASSES  # history actions: simple, inspectable, never terminal
TARGET_CLASSES: frozenset[str] = frozenset(c for c, _ in VERB_CLASSES)
DOOR_WORD = re.compile(r"\bdoor\b")
EXCLUDED_DOOR = "door_action_excluded(RD-05)"
EXCLUDED_PORTAL = "refers_to_uuid_outside_object_tree(RD-05)"


def verb_class(action: str) -> str | None:
    return next((name for name, rx in VERB_CLASSES if rx.match(action)), None)


def door_exclusion_reason(action: str, obj_ids: Iterable[str], state: CanonicalState) -> str | None:
    """RD-05: door actions (and anything referring to a portal uuid) are not sampled."""
    if DOOR_WORD.search(action):
        return EXCLUDED_DOOR
    if any(i not in state.objects for i in obj_ids):
        return EXCLUDED_PORTAL
    return None


# -- forbidden content (no gold-label or evaluation-signal leakage) --------------------------
FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "label",
        "labels",
        "gold_label",
        "labels_by_horizon",
        "restore_depth",
        "approx_restore_depth",
        "label_rationale",
        "label_provisional",
        "provisional_reasons",
        "pair_id",
        "pivot",
        "reversibility",
    }
)
HIDDEN_SIGNAL_KEYS: frozenset[str] = frozenset(
    {"score", "reward", "done", "gold_actions", "gold_action_sequence", "task_score"}
)
FORBIDDEN_VALUES: frozenset[str] = frozenset(
    {*LABELS, "partially reversible", "partial", "undetermined"}
)


# -- families and sampled examples ---------------------------------------------------------
@dataclass(frozen=True)
class FamilySpec:
    """A scenario family: one task variation, simplification set and starting room."""

    family_id: str
    task: str
    variation: int
    simplifications: str = "teleportAction"
    base_actions: tuple[str, ...] = ()

    def base_recipe(self, step_limit: int = 100) -> ReplayRecipe:
        return ReplayRecipe(
            self.task,
            self.variation,
            self.simplifications,
            preparation=FIRST_TICK_PREPARATION,
            actions=self.base_actions,
            step_limit=step_limit,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "task": self.task,
            "variation": self.variation,
            "simplifications": self.simplifications,
            "base_actions": list(self.base_actions),
        }


PILOT_FAMILIES: tuple[FamilySpec, ...] = (
    FamilySpec("boil-kitchen", "1-1", 0, base_actions=("teleport to kitchen",)),
    FamilySpec("power-workshop", "3-1", 0, base_actions=("teleport to workshop",)),
    FamilySpec("grow-greenhouse", "5-1", 0, base_actions=("teleport to greenhouse",)),
)


@dataclass(frozen=True)
class HistoryStep:
    action: str
    phase: str  # preparation | base | prefix | contrast
    status: str
    ticks: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "phase": self.phase,
            "status": self.status,
            "ticks": self.ticks,
            "counts_as_agent_action": True,
        }


def example_id(recipe: ReplayRecipe, action: str) -> str:
    digest = hashlib.sha256(f"{recipe.to_json()}\x1f{action}".encode()).hexdigest()
    return f"swp-{digest[:16]}"


@dataclass(frozen=True)
class SampledExample:
    """A sampled (S0, target) whose history was verified in the sampler session."""

    family: FamilySpec
    recipe: ReplayRecipe
    history: tuple[HistoryStep, ...]
    target: ActionTemplate
    target_class: str
    s0: CapturedState
    sample_index: int
    role: str  # base | sibling
    sibling_of: str | None = None
    contrast_action: str | None = None
    n_door_actions_excluded: int = 0
    seed: int = 0

    @property
    def example_id(self) -> str:
        return example_id(self.recipe, self.target.action)


def discrete_fingerprint(state: CanonicalState) -> str:
    """Fingerprint without temperatures, combustion ticks and time (duplicate detection only)."""
    drop = {"propMaterial.temperatureC", "propMaterial.combustionTicks"}
    return sha256_json(
        {
            "objects": {
                u: {k: v for k, v in r.items() if k not in drop} for u, r in state.objects.items()
            },
            "world": {k: v for k, v in state.world.items() if k != "moves"},
            "doors": state.visible_doors,
        }
    )  # fmt: skip


def state_document(state: CapturedState) -> bytes:
    """Deterministic bytes of the sidecar file holding one full pre-action state."""
    doc = {"raw": state.raw.to_dict(), "canonical": state.canonical.to_dict()}
    return (json.dumps(doc, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def state_file_name(state: CapturedState) -> str:
    return f"states/{state.raw.fingerprint}.json"


# -- record construction ---------------------------------------------------------------------
def _names(state: CanonicalState, ids: Iterable[str]) -> dict[str, str | None]:
    return {i: (state.objects[i].get("name") if i in state.objects else None) for i in ids}


def _change_rows(diff: Any, state: CanonicalState) -> list[dict[str, Any]]:
    rows = []
    for ch in diff.changes[:MAX_LISTED_CHANGES]:
        uuid, _, fld = ch.key.partition(":")
        row = ch.to_dict()
        row["object"] = (
            state.objects.get(uuid, {}).get("name") if uuid not in ("world", "door") else uuid
        )
        row["field"] = fld
        rows.append(row)
    return rows  # fmt: skip


def match_level(attempt: PathAttempt) -> str:
    modes = {c.mode: c for c in attempt.comparisons}
    if not attempt.executed or MODE_EXACT not in modes:
        return MATCH_NOT_COMPARED
    for level, mode in MATCH_LADDER:
        if mode in modes and modes[mode].diff.equal_on_observed_fields:
            return level
    return MATCH_NONE


def _comparison_row(c: Any, state: CanonicalState) -> dict[str, Any]:
    d = c.diff
    return {
        "outcome": c.outcome,
        "kind": d.kind,
        "exploratory": d.exploratory,
        "n_changes": len(d.changes),
        "changes": _change_rows(d, state),
        "created_objects": [list(x) for x in d.created_objects],
        "deleted_objects": [list(x) for x in d.deleted_objects],
        "ignored_patterns": list(d.ignored_patterns),
        "n_ignored_differences": d.n_ignored_differences,
        "tolerances": dict(d.tolerances),
        "n_within_tolerance": d.n_within_tolerance,
        "n_temperature_changes_unfiltered": c.n_temperature_changes,
        "max_abs_temperature_delta_unfiltered": c.max_abs_temperature_delta,
        "unknown_fields": list(d.incomplete_reasons),
    }


def _attempt_row(a: PathAttempt, state: CanonicalState) -> dict[str, Any]:
    loc, loose = a.structural
    return {
        "source": a.source,
        "actions": list(a.actions),
        "steps": [
            {"action": s.action, "status": s.status, "executed": s.result is not None,
             "ticks": s.ticks}
            for s in a.steps
        ],
        "executed": a.executed,
        "n_actions_used": a.n_actions_used,
        "ticks_target": a.ticks_target,
        "ticks_path": a.ticks_path,
        "counterfactual": {
            "available": MODE_EXACT in {c.mode for c in a.comparisons},
            "idle_action": IDLE_ACTION,
            "note": a.counterfactual_note,
        },
        "comparisons": {c.mode: _comparison_row(c, state) for c in a.comparisons},
        "match_level": match_level(a),
        "structural_exploratory": {
            "location_sensitive_all_accounted": loc.all_objects_accounted,
            "location_insensitive_all_accounted": loose.all_objects_accounted,
            "n_ambiguous_groups": len(loc.ambiguous),
        },
        "observability_issues": list(a.observability_issues),
        "diagnostic_outcomes": list(a.outcomes),
    }  # fmt: skip


def evidence_status(diagnostic: RestorationDiagnostic) -> tuple[str, str]:
    """(record-level neutral evidence status, best counterfactual match level)."""
    if diagnostic.target_status != "accepted":
        return EV_TARGET_NOT_EXECUTED, MATCH_NOT_COMPARED
    if diagnostic.n_paths_proposed == 0:
        return EV_NO_CANDIDATE, MATCH_NOT_COMPARED
    executed = [a for a in diagnostic.attempts if a.executed]
    if not executed:
        return EV_NOT_EXECUTED, MATCH_NOT_COMPARED
    levels = [match_level(a) for a in executed]
    best = min(levels, key=MATCH_LEVELS.index)
    if best == MATCH_NOT_COMPARED:
        return EV_CF_UNAVAILABLE, best
    return _STATUS_BY_LEVEL[best], best


def content_sha256(doc: Mapping[str, Any]) -> str:
    return sha256_json({k: v for k, v in doc.items() if k != "content_sha256"})


def build_record(
    example: SampledExample,
    diagnostic: RestorationDiagnostic,
    *,
    state_sha256: str,
    runtime: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Assemble one provisional evidence record (no label, no score, no reward)."""
    s0 = example.s0
    c0 = s0.canonical
    tgt = example.target
    status, best = evidence_status(diagnostic)
    effect = diagnostic.target_effect
    executed = [a for a in diagnostic.attempts if a.executed]
    history_ticks = sum(h.ticks for h in example.history)
    verified = (
        diagnostic.s0_raw_fingerprint == s0.raw.fingerprint
        and diagnostic.s0_canonical_fingerprint == c0.fingerprint
    )
    record: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "example_id": example.example_id,
        "family_id": example.family.family_id,
        "task": {"task_id": example.recipe.task, "variation": example.recipe.variation},
        "simplifications": example.recipe.simplifications,
        "replay_recipe": example.recipe.to_dict(),
        "action_history": [h.to_dict() for h in example.history],
        "researcher_operations": [
            {
                "operation": "load_and_reset",
                "arguments": {
                    "task": example.recipe.task,
                    "variation": example.recipe.variation,
                    "simplifications": example.recipe.simplifications,
                },
                "counts_as_agent_action": False,
                "note": "rebuilds the episode; never part of a history or a restoration path",
            }
        ],
        "first_tick_handling": {
            "preparation": list(example.recipe.preparation),
            "reason": "the first tick creates objects (e.g. fountain water, terminals); "
            "'wait1' consumes it before any sampled action (docs/17 §4.1)",
        },
        "target": {
            "action": tgt.action,
            "verb_class": example.target_class,
            "registry_rule_coverage": example.target_class in RULE_COVERED_CLASSES,
            "template_id": tgt.template_id,
            "obj_ids": list(tgt.obj_ids),
            "object_names": _names(c0, tgt.obj_ids),
            "obj_ids_in_object_tree": all(i in c0.objects for i in tgt.obj_ids),
            "n_templates_with_text": 1,
            "valid_in_state": tgt.action in s0.raw.valid_actions,
            "status": diagnostic.target_status,
            "ticks": (
                0 if diagnostic.target_step is None
                else diagnostic.target_step.moves_after - diagnostic.target_step.moves_before
            ),
            "observation": (
                None if diagnostic.target_step is None else diagnostic.target_step.observation[:300]
            ),
            "observed_effect": {
                "projection": DISCRETE_EXPLORATION.name,
                "note": "discrete fields only, used to confirm the action had an observable "
                "effect; temperatures are compared in restoration_evidence",
                "n_changes": None if effect is None else len(effect.changes),
                "changes": [] if effect is None else _change_rows(effect, c0),
                "created_objects": [list(x) for x in (effect.created_objects if effect else ())],
                "deleted_objects": [list(x) for x in (effect.deleted_objects if effect else ())],
            },
        },
        "pre_action_state": {
            "agent_location": c0.world.get("agent_location"),
            "moves": c0.world.get("moves"),
            "look": s0.raw.look,
            "inventory": s0.raw.inventory,
            "n_objects": len(c0.objects),
            "n_valid_actions": len(s0.raw.valid_actions),
            "visible_doors": dict(c0.visible_doors),
            "target_objects": {i: c0.objects[i] for i in tgt.obj_ids if i in c0.objects},
            "raw_fingerprint": s0.raw.fingerprint,
            "canonical_fingerprint": c0.fingerprint,
            "discrete_fingerprint": discrete_fingerprint(c0),
        },
        "state_provenance": {
            "state_file": state_file_name(s0),
            "state_file_sha256": state_sha256,
            "raw_capture": "object_tree, look, inventory, moves, valid_actions (free calls)",
            "canonical_version": CANONICAL_VERSION,
            "captured_by": "sampler session",
            "reconstructed_by": "restoration-diagnostic verification replay and session",
        },
        "elapsed_ticks": {
            "history_ticks": history_ticks,
            "s0_moves": c0.world.get("moves"),
            "target_ticks": None,
        },
        "restoration_evidence": {
            "primary_method": PRIMARY_METHOD,
            "temperature_comparisons": [lv for lv, _ in MATCH_LADDER],
            "candidate_set": {
                "scope": SEARCH_SCOPE,
                "restricted": True,
                "exhaustive": False,
                "rules_considered": [p.to_dict() for p in diagnostic.proposals],
                "n_paths_proposed": diagnostic.n_paths_proposed,
                "n_paths_attempted": len(diagnostic.attempts),
                "n_paths_executed": len(executed),
                "max_paths": diagnostic.max_paths,
                "failed_search_meaning": FAILED_SEARCH_MEANING,
            },
            "attempts": [_attempt_row(a, c0) for a in diagnostic.attempts],
            "comparisons_available": sorted({c.mode for a in executed for c in a.comparisons}),
            "best_counterfactual_match_level": best,
            "evidence_status": status,
            "diagnostic_outcomes": list(diagnostic.outcomes),
            "interpretation_constraints": list(INTERPRETATION_CONSTRAINTS),
        },
        "observation_completeness": {
            "complete": False,
            "incomplete_reasons": list(c0.incomplete_reasons),
            "unobservable": list(diagnostic.unobservable),
            "notes": list(c0.notes),
        },
        "replay_verification": {
            "sampler_s0_raw_fingerprint": s0.raw.fingerprint,
            "diagnostic_s0_raw_fingerprint": diagnostic.s0_raw_fingerprint,
            "diagnostic_s0_canonical_fingerprint": diagnostic.s0_canonical_fingerprint,
            "independent_reconstructions": 3,
            "verified": verified,
        },
        "sampling": {
            "seed": example.seed,
            "sample_index": example.sample_index,
            "role": example.role,
            "sibling_of": example.sibling_of,
            "contrast_action": example.contrast_action,
            "prefix_length": sum(1 for h in example.history if h.phase in ("prefix", "contrast")),
            "n_door_actions_excluded_from_target_pool": example.n_door_actions_excluded,
        },
        "provenance": {
            "simulator": PINNED.to_dict(),
            "runtime": dict(runtime) if runtime else None,
            "evidence_schema": EVIDENCE_SCHEMA_VERSION,
            "diagnostics_version": DIAGNOSTICS_VERSION,
            "canonical_version": CANONICAL_VERSION,
        },
        "scientific_status": dict(SCIENTIFIC_STATUS),
    }  # fmt: skip
    record["elapsed_ticks"]["target_ticks"] = record["target"]["ticks"]
    record["content_sha256"] = content_sha256(record)
    return record


RECORD_FIELDS: tuple[str, ...] = (
    "schema_version", "example_id", "family_id", "task", "simplifications", "replay_recipe",
    "action_history", "researcher_operations", "first_tick_handling", "target",
    "pre_action_state", "state_provenance", "elapsed_ticks", "restoration_evidence",
    "observation_completeness", "replay_verification", "sampling", "provenance",
    "scientific_status", "content_sha256",
)  # fmt: skip


# -- candidate minimal pairs (Step 4) --------------------------------------------------------
def consequence_signature(record: Mapping[str, Any]) -> dict[str, Any]:
    """What the target did and what the restricted restoration evidence found."""
    eff = record["target"]["observed_effect"]
    ev = record["restoration_evidence"]
    return {
        "evidence_status": ev["evidence_status"],
        "best_counterfactual_match_level": ev["best_counterfactual_match_level"],
        "effect": sorted(
            f"{c['object']}:{c['field']}={json.dumps(c['after'])}" for c in eff["changes"]
        ),
        "created": sorted(n for _, n in eff["created_objects"]),
        "deleted": sorted(n for _, n in eff["deleted_objects"]),
    }  # fmt: skip


def pair_id(record_ids: Iterable[str]) -> str:
    digest = hashlib.sha256("\x1f".join(sorted(record_ids)).encode()).hexdigest()
    return f"swpair-{digest[:16]}"


@dataclass
class PairStats:
    n_groups: int = 0
    n_comparisons: int = 0
    n_candidates: int = 0
    rejected: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        self.rejected[reason] = self.rejected.get(reason, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_groups_with_repeated_action": self.n_groups,
            "n_comparisons": self.n_comparisons,
            "n_candidates": self.n_candidates,
            "rejected": dict(sorted(self.rejected.items())),
        }


def discover_candidate_pairs(
    records: list[Mapping[str, Any]],
    load_state: Callable[[Mapping[str, Any]], CanonicalState],
) -> tuple[list[dict[str, Any]], PairStats]:
    """Candidate minimal pairs: same family, byte-identical action, different consequences.

    Requirements (docs/21 §5): both records replay-verified; the action text resolves to
    the same simulator uuids in both states with exactly one template each (no reference
    ambiguity); the two pre-action states differ in at least one discrete field or object
    (a temperature-only difference does not qualify, but is reported); the consequence
    signatures differ. Output pairs are *unvalidated candidates*.
    """
    stats = PairStats()
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for r in records:
        groups.setdefault((r["family_id"], r["target"]["action"]), []).append(r)
    pairs = []
    for (family, action), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        stats.n_groups += 1
        for a, b in combinations(sorted(members, key=lambda r: r["example_id"]), 2):
            stats.n_comparisons += 1
            if not (a["replay_verification"]["verified"] and b["replay_verification"]["verified"]):
                stats.reject("replay_not_verified")
                continue
            ta, tb = a["target"], b["target"]
            if (
                ta["obj_ids"] != tb["obj_ids"]
                or ta["n_templates_with_text"] != 1
                or tb["n_templates_with_text"] != 1
            ):
                stats.reject("reference_ambiguity")
                continue
            sa, sb = load_state(a), load_state(b)
            discrete = projection_diff(sa, sb, DISCRETE_EXPLORATION)
            if discrete.equal_on_observed_fields:
                stats.reject("no_discrete_state_difference")
                continue
            ca, cb = consequence_signature(a), consequence_signature(b)
            differing = {k: [ca[k], cb[k]] for k in ca if ca[k] != cb[k]}
            if not differing:
                stats.reject("same_consequences")
                continue
            exact = canonical_diff(sa, sb)
            relation = (
                "sibling"
                if b["sampling"]["sibling_of"] == a["example_id"]
                or a["sampling"]["sibling_of"] == b["example_id"]
                else "independent"
            )
            pair: dict[str, Any] = {
                "schema_version": PAIR_SCHEMA_VERSION,
                "candidate_pair_id": pair_id([a["example_id"], b["example_id"]]),
                "family_id": family,
                "action_text": action,
                "record_ids": [a["example_id"], b["example_id"]],
                "relation": relation,
                "state_difference": {
                    "projection": DISCRETE_EXPLORATION.name,
                    "n_discrete_changes": len(discrete.changes),
                    "discrete_changes": _change_rows(discrete, sa),
                    "created_objects": [list(x) for x in discrete.created_objects],
                    "deleted_objects": [list(x) for x in discrete.deleted_objects],
                    "n_exact_changes": len(exact.changes),
                    "n_temperature_changes": sum(
                        1 for c in exact.changes if c.key.endswith("propMaterial.temperatureC")
                    ),
                },
                "consequence_difference": differing,
                "reference_check": {
                    "obj_ids": list(ta["obj_ids"]),
                    "same_referents": True,
                    "unambiguous_in_both": True,
                },
                "reproducibility": {"both_replay_verified": True},
                "status": "candidate_unvalidated",
                "validated": False,
                "scientific_status": dict(SCIENTIFIC_STATUS),
            }  # fmt: skip
            pair["content_sha256"] = content_sha256(pair)
            pairs.append(pair)
            stats.n_candidates += 1
    return pairs, stats


PAIR_FIELDS: tuple[str, ...] = (
    "schema_version", "candidate_pair_id", "family_id", "action_text", "record_ids",
    "relation", "state_difference", "consequence_difference", "reference_check",
    "reproducibility", "status", "validated", "scientific_status", "content_sha256",
)  # fmt: skip


# -- validation (Step 5; no Java) -------------------------------------------------------------
CHECKS: tuple[str, ...] = (
    "schema_integrity", "unique_ids", "content_checksums", "duplicates", "action_validity",
    "door_exclusion", "replay_verification", "provenance", "state_files",
    "missing_state_disclosure", "restricted_search_disclosure", "no_label_leakage",
    "scientific_status", "candidate_pairs",
)  # fmt: skip


@dataclass
class ValidationReport:
    n_records: int
    n_pairs: int
    errors: dict[str, list[str]] = field(default_factory=lambda: {c: [] for c in CHECKS})

    @property
    def ok(self) -> bool:
        return not any(self.errors.values())

    def add(self, check: str, message: str) -> None:
        self.errors[check].append(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "n_records": self.n_records,
            "n_pairs": self.n_pairs,
            "checks": {c: {"passed": not e, "errors": e[:20], "n_errors": len(e)}
                       for c, e in self.errors.items()},
        }  # fmt: skip


def _walk(obj: Any, path: str = "") -> Iterable[tuple[str, str | None, Any]]:
    """Yield (path, key, value) for every key and every leaf in a JSON document."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", k, v
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield f"{path}[{i}]", None, v
            yield from _walk(v, f"{path}[{i}]")


def leakage_problems(doc: Any) -> list[str]:
    """Label-like keys, gold-schema label fields, label values, or evaluation signals."""
    problems = []
    for path, key, value in _walk(doc):
        if key is not None and key in FORBIDDEN_KEYS:
            problems.append(f"{path}: label-like key {key!r}")
        if key is not None and key in HIDDEN_SIGNAL_KEYS:
            problems.append(f"{path}: hidden evaluation signal {key!r}")
        if isinstance(value, str) and value.strip().lower() in FORBIDDEN_VALUES:
            problems.append(f"{path}: label-like value {value!r}")
    return problems


def _check_record(r: Mapping[str, Any], rep: ValidationReport, root: Path | None) -> None:
    rid = r.get("example_id", "<missing id>")
    for p in leakage_problems(r):
        rep.add("no_label_leakage", f"{rid}: {p}")
    if set(r) != set(RECORD_FIELDS):
        rep.add("schema_integrity", f"{rid}: fields {sorted(set(r) ^ set(RECORD_FIELDS))}")
        return
    if r["schema_version"] != EVIDENCE_SCHEMA_VERSION:
        rep.add("schema_integrity", f"{rid}: schema {r['schema_version']!r}")
    if set(r) & set(GOLD_FIELDS):
        rep.add("schema_integrity", f"{rid}: carries gold-schema fields")
    try:
        recipe = ReplayRecipe.from_dict(r["replay_recipe"])
    except (KeyError, TypeError, ValueError) as exc:
        rep.add("schema_integrity", f"{rid}: bad replay recipe ({exc})")
        return
    if example_id(recipe, r["target"]["action"]) != rid:
        rep.add("schema_integrity", f"{rid}: id does not match recipe + action")
    if r["content_sha256"] != content_sha256(r):
        rep.add("content_checksums", f"{rid}: content checksum mismatch")

    # action validity, researcher operations and ticks
    hist = r["action_history"]
    if [h["action"] for h in hist] != list(recipe.preparation) + list(recipe.actions):
        rep.add("action_validity", f"{rid}: action_history does not match the recipe")
    for h in hist:
        if h["status"] != "accepted" or h["counts_as_agent_action"] is not True:
            rep.add(
                "action_validity", f"{rid}: history step {h['action']!r} not a valid agent action"
            )
    if any(op["counts_as_agent_action"] for op in r["researcher_operations"]):
        rep.add("action_validity", f"{rid}: a researcher operation counted as an agent action")
    if tuple(recipe.preparation) != FIRST_TICK_PREPARATION:
        rep.add("action_validity", f"{rid}: first tick not consumed by {FIRST_TICK_PREPARATION}")
    t = r["target"]
    if not (t["valid_in_state"] and t["status"] == "accepted" and t["n_templates_with_text"] == 1):
        rep.add("action_validity", f"{rid}: target not a valid, unambiguous, accepted action")
    if (
        not t["observed_effect"]["n_changes"]
        and not t["observed_effect"]["created_objects"]
        and not t["observed_effect"]["deleted_objects"]
    ):
        rep.add("action_validity", f"{rid}: target had no observed effect")
    ticks = r["elapsed_ticks"]
    if (
        ticks["history_ticks"] != ticks["s0_moves"]
        or r["pre_action_state"]["moves"] != ticks["s0_moves"]
    ):
        rep.add("action_validity", f"{rid}: elapsed ticks inconsistent with S0 moves")

    # RD-05
    if DOOR_WORD.search(t["action"]) or not t["obj_ids_in_object_tree"]:
        rep.add("door_exclusion", f"{rid}: door/portal target {t['action']!r}")

    v = r["replay_verification"]
    if not v["verified"] or v["sampler_s0_raw_fingerprint"] != v["diagnostic_s0_raw_fingerprint"]:
        rep.add("replay_verification", f"{rid}: S0 reconstruction not verified")
    if v["sampler_s0_raw_fingerprint"] != r["pre_action_state"]["raw_fingerprint"]:
        rep.add("replay_verification", f"{rid}: verified fingerprint is not the recorded S0")

    if r["provenance"]["simulator"] != PINNED.to_dict() or recipe.simulator != PINNED:
        rep.add("provenance", f"{rid}: simulator is not the pinned build")

    if root is not None:
        _check_state_file(r, rep, root)

    oc = r["observation_completeness"]
    if oc["complete"] is not False or not set(BASE_INCOMPLETE_REASONS) <= set(
        oc["incomplete_reasons"]
    ):
        rep.add("missing_state_disclosure", f"{rid}: incompleteness not disclosed")
    for a in r["restoration_evidence"]["attempts"]:
        for mode, c in a["comparisons"].items():
            if not c["unknown_fields"]:
                rep.add("missing_state_disclosure", f"{rid}: {mode} lists no unknown fields")

    cs = r["restoration_evidence"]["candidate_set"]
    if (
        cs["exhaustive"] is not False
        or cs["restricted"] is not True
        or not cs["failed_search_meaning"]
    ):
        rep.add("restricted_search_disclosure", f"{rid}: restricted candidate set not disclosed")
    if r["restoration_evidence"]["evidence_status"] not in EVIDENCE_STATUSES:
        rep.add("schema_integrity", f"{rid}: unknown evidence status")

    if r["scientific_status"] != SCIENTIFIC_STATUS:
        rep.add("scientific_status", f"{rid}: scientific status is not the provisional statement")


def _check_state_file(r: Mapping[str, Any], rep: ValidationReport, root: Path) -> None:
    rid, prov, pre = r["example_id"], r["state_provenance"], r["pre_action_state"]
    path = root / prov["state_file"]
    if not path.is_file():
        rep.add("state_files", f"{rid}: missing {prov['state_file']}")
        return
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != prov["state_file_sha256"]:
        rep.add("state_files", f"{rid}: state file checksum mismatch")
        return
    raw = RawState.from_dict(json.loads(data)["raw"])
    canonical = canonicalize(raw)
    if (
        raw.fingerprint != pre["raw_fingerprint"]
        or canonical.fingerprint != pre["canonical_fingerprint"]
    ):
        rep.add("state_files", f"{rid}: state file does not reproduce the recorded fingerprints")
    elif discrete_fingerprint(canonical) != pre["discrete_fingerprint"]:
        rep.add("state_files", f"{rid}: discrete fingerprint mismatch")
    if r["target"]["action"] not in raw.valid_actions:
        rep.add("action_validity", f"{rid}: target absent from the stored valid-action list")


def load_state_file(root: Path) -> Callable[[Mapping[str, Any]], CanonicalState]:
    def load(record: Mapping[str, Any]) -> CanonicalState:
        doc = json.loads((root / record["state_provenance"]["state_file"]).read_bytes())
        return canonicalize(RawState.from_dict(doc["raw"]))

    return load


def validate_dataset(
    records: list[Mapping[str, Any]],
    pairs: list[Mapping[str, Any]],
    *,
    root: Path | None = None,
) -> ValidationReport:
    """Validate provisional records and candidate pairs (no simulator needed)."""
    rep = ValidationReport(len(records), len(pairs))
    ids = [r.get("example_id") for r in records]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        rep.add("unique_ids", f"duplicate example_id {dup}")
    seen: dict[tuple[str, str], str] = {}
    for r in records:
        _check_record(r, rep, root)
        if set(r) != set(RECORD_FIELDS):
            continue
        for kind in ("canonical_fingerprint", "discrete_fingerprint"):
            key = (f"{kind}:{r['pre_action_state'][kind]}", r["target"]["action"])
            if key in seen:
                rep.add("duplicates", f"{r['example_id']} duplicates {seen[key]} ({kind})")
            seen.setdefault(key, r["example_id"])

    by_id = {r["example_id"]: r for r in records if "example_id" in r}
    pair_ids = [p.get("candidate_pair_id") for p in pairs]
    for dup in sorted({i for i in pair_ids if pair_ids.count(i) > 1}):
        rep.add("unique_ids", f"duplicate candidate_pair_id {dup}")
    for p in pairs:
        _check_pair(p, by_id, rep, root)
    return rep


def _check_pair(
    p: Mapping[str, Any],
    by_id: Mapping[str, Mapping[str, Any]],
    rep: ValidationReport,
    root: Path | None,
) -> None:
    pid = p.get("candidate_pair_id", "<missing id>")
    if set(p) != set(PAIR_FIELDS):
        rep.add("candidate_pairs", f"{pid}: fields {sorted(set(p) ^ set(PAIR_FIELDS))}")
        return
    if p["content_sha256"] != content_sha256(p):
        rep.add("content_checksums", f"{pid}: content checksum mismatch")
    ids = p["record_ids"]
    if len(ids) != 2 or ids[0] == ids[1] or pair_id(ids) != pid:
        rep.add("candidate_pairs", f"{pid}: malformed record ids")
        return
    missing = [i for i in ids if i not in by_id]
    if missing:
        rep.add("candidate_pairs", f"{pid}: unknown records {missing}")
        return
    a, b = (by_id[i] for i in ids)
    if not (a["target"]["action"] == b["target"]["action"] == p["action_text"]):
        rep.add("candidate_pairs", f"{pid}: action text is not byte-identical")
    if not (a["family_id"] == b["family_id"] == p["family_id"]):
        rep.add("candidate_pairs", f"{pid}: records from different families")
    if a["target"]["obj_ids"] != b["target"]["obj_ids"]:
        rep.add("candidate_pairs", f"{pid}: action refers to different objects")
    if not (a["replay_verification"]["verified"] and b["replay_verification"]["verified"]):
        rep.add("candidate_pairs", f"{pid}: a member is not replay-verified")
    sd = p["state_difference"]
    if not (sd["n_discrete_changes"] or sd["created_objects"] or sd["deleted_objects"]):
        rep.add("candidate_pairs", f"{pid}: no documented state difference")
    ca, cb = consequence_signature(a), consequence_signature(b)
    if not p["consequence_difference"] or any(
        p["consequence_difference"][k] != [ca[k], cb[k]] for k in p["consequence_difference"]
    ):
        rep.add("candidate_pairs", f"{pid}: consequence difference does not match the records")
    if p["status"] != "candidate_unvalidated" or p["validated"] is not False:
        rep.add("candidate_pairs", f"{pid}: pair claims validation")
    if p["scientific_status"] != SCIENTIFIC_STATUS:
        rep.add("scientific_status", f"{pid}: scientific status is not the provisional statement")
    for problem in leakage_problems(p):
        rep.add("no_label_leakage", f"{pid}: {problem}")
    if root is not None:
        loader = load_state_file(root)
        if projection_diff(loader(a), loader(b), DISCRETE_EXPLORATION).equal_on_observed_fields:
            rep.add("candidate_pairs", f"{pid}: stored states show no discrete difference")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows).encode()
