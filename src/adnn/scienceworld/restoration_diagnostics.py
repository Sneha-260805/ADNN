"""Restoration diagnostics with restricted inverse-action candidates (Phase 4D, docs/19).

For one verified starting state S0 (rebuilt from a :class:`ReplayRecipe`), one
target action, and a *small explicit registry* of candidate inverse paths, this
module executes each candidate and describes how the resulting state S2
differs from S0, and from a time-matched do-nothing counterfactual.

Guardrails (docs/19 §1):

* **No reversibility labels.** Results use neutral outcomes only
  (:data:`OUTCOMES`). Nothing here returns or stores ``reversible``,
  ``partially_reversible`` or ``irreversible``.
* **Restricted, never exhaustive.** Candidates come from :data:`REGISTRY` and
  explicit experiment paths. Finding no matching path is *not* evidence of
  irreversibility (:data:`FAILED_SEARCH_MEANING`).
* **Agent-accessible restoration only.** Every candidate action must be in the
  simulator's valid-action list at the moment it is taken, and helper or idle
  commands (:data:`EXCLUDED_RESTORATION`) are never candidates. ``load``,
  ``reset`` and recipe replay are researcher operations used to rebuild
  states; they are never counted as restoration actions.
* **Observed state only.** Canonical states are incomplete (doors outside the
  current room, agent internals), so ``observed_fields_match`` is never
  exact-state equality.
* **Inverse candidates are hypotheses.** A rule says which action *might* undo
  the target, selected by simulator uuid (not by name). Each one is then tested.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from adnn.scienceworld.canonical import CanonicalState, CapturedState, capture_state
from adnn.scienceworld.diagnostics import (
    DISCRETE_EXPLORATION,
    TEMPERATURE_TOLERANCE_EXPLORATION,
    Projection,
    StateDiff,
    canonical_diff,
    projection_diff,
    raw_diff,
)
from adnn.scienceworld.env import ActionTemplate, Backend, ScienceWorldSession, StepResult
from adnn.scienceworld.provenance import RuntimeConfig
from adnn.scienceworld.replay import (
    FIRST_TICK_PREPARATION,
    ReplayDivergenceError,
    ReplayRecipe,
    TraceComparison,
    replay,
    run_recipe,
)
from adnn.scienceworld.structural import StructuralReport, structural_match

DIAGNOSTICS_VERSION = "sw-restoration-diagnostics-1"

# -- neutral outcomes (never research labels) -----------------------------------------
CANDIDATE_PATH_EXECUTED = "candidate_path_executed"
CANDIDATE_PATH_NOT_EXECUTED = "candidate_path_not_executed"
NO_CANDIDATE_PATH_FOUND = "no_candidate_path_found"
TARGET_NOT_EXECUTED = "target_action_not_executed"
OBSERVED_FIELDS_MATCH = "observed_fields_match"
OBSERVED_FIELDS_DIFFER = "observed_fields_differ"
INSUFFICIENT_OBSERVABILITY = "insufficient_observability"
OUTCOMES: tuple[str, ...] = (
    CANDIDATE_PATH_EXECUTED,
    CANDIDATE_PATH_NOT_EXECUTED,
    NO_CANDIDATE_PATH_FOUND,
    TARGET_NOT_EXECUTED,
    OBSERVED_FIELDS_MATCH,
    OBSERVED_FIELDS_DIFFER,
    INSUFFICIENT_OBSERVABILITY,
)

SEARCH_SCOPE = "restricted_registry"
FAILED_SEARCH_MEANING = (
    "Only a restricted, hand-written candidate set was tried. Finding no candidate, or no "
    "candidate whose result matches, is NOT evidence that the action cannot be undone; "
    "under the proposed OQ-31 policy such a case is 'undetermined'."
)
LABEL_POLICY = "diagnostic only: no reversibility label is produced (docs/19 §1)"

# Observability channel of the property a rule restores.
OBJECT_TREE = "object_tree"
CURRENT_ROOM_TEXT = "current_room_look_text"

EXCLUDED_RESTORATION = re.compile(
    r"^(reset task|focus on|task|inventory|look around|look at|look in|read|wait\d*)\b"
)
STATUS_UNAVAILABLE = "unavailable"  # not in the valid-action list; not sent to the simulator
STATUS_EXCLUDED = "excluded"  # helper/idle command; never a restoration action


# -- registry ----------------------------------------------------------------------------
@dataclass(frozen=True)
class InverseContext:
    """What a rule may look at: S0, S1 (after the target) and S1's valid actions with uuids."""

    target: str
    target_ids: tuple[str, ...]
    before: CanonicalState
    after: CanonicalState
    after_templates: tuple[ActionTemplate, ...]


@dataclass(frozen=True)
class RuleProposal:
    rule_id: str
    applicable: bool
    paths: tuple[tuple[str, ...], ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "applicable": self.applicable,
            "paths": [list(p) for p in self.paths],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class InverseRule:
    rule_id: str
    pattern: str  # regex on the target action text
    observability: str
    hypothesis: str
    source: str  # upstream evidence at e8216d6 (docs/19 §3)
    propose: Callable[[InverseContext], RuleProposal] = field(repr=False, compare=False)

    def matches(self, action: str) -> bool:
        return re.search(self.pattern, action) is not None

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "pattern": self.pattern,
            "observability": self.observability,
            "hypothesis": self.hypothesis,
            "source": self.source,
        }


def _by_ids(ctx: InverseContext, verb: str, ids: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        (t.action,)
        for t in ctx.after_templates
        if t.action.startswith(verb + " ") and t.obj_ids == ids
    )


def _toggle(rule_id: str, fld: str, before: Any, after: Any, inverse_verb: str) -> Callable:
    def propose(ctx: InverseContext) -> RuleProposal:
        if len(ctx.target_ids) != 1 or ctx.target_ids[0] not in ctx.before.objects:
            return RuleProposal(rule_id, False, (), "target object is not in the object tree")
        obj = ctx.target_ids[0]
        got = (ctx.before.objects[obj].get(fld), ctx.after.objects.get(obj, {}).get(fld))
        if got != (before, after):
            return RuleProposal(
                rule_id, False, (), f"precondition failed: {fld} {got[0]!r}->{got[1]!r}, "
                f"expected {before!r}->{after!r}"
            )  # fmt: skip
        paths = _by_ids(ctx, inverse_verb, (obj,))
        why = f"'{inverse_verb}' on uuid {obj}" if paths else "inverse action not valid in S1"
        return RuleProposal(rule_id, True, paths, why)

    return propose


def _door(rule_id: str, before: str, after: str, inverse_verb: str) -> Callable:
    def propose(ctx: InverseContext) -> RuleProposal:
        m = re.match(r"^\w+ door to (.+)$", ctx.target)
        room = m.group(1) if m else ""
        got = (ctx.before.visible_doors.get(room), ctx.after.visible_doors.get(room))
        if got != (before, after):
            return RuleProposal(rule_id, False, (), f"precondition failed: door {got!r}")
        paths = _by_ids(ctx, inverse_verb + " door to", ctx.target_ids)
        why = "same portal uuid" if paths else "inverse action not valid in S1"
        return RuleProposal(rule_id, True, paths, why)

    return propose


def _agent_room(state: CanonicalState) -> str | None:
    agents = [r for r in state.objects.values() if r.get("name") == "agent"]
    return str(agents[0]["parent"]) if len(agents) == 1 else None


def _return_to_parent(ctx: InverseContext) -> RuleProposal:
    rid = "return-to-original-container"
    if not ctx.target_ids or ctx.target_ids[0] not in ctx.before.objects:
        return RuleProposal(rid, False, (), "moved object is not in the object tree")
    obj = ctx.target_ids[0]
    if ctx.target.startswith("pour ") and ctx.before.objects[obj].get("propContainer.isContainer"):
        return RuleProposal(rid, False, (), "pouring a container moves its contents, not itself")
    if obj not in ctx.after.objects:
        return RuleProposal(rid, False, (), "object absent after the target")
    origin = str(ctx.before.objects[obj]["parent"])
    if str(ctx.after.objects[obj]["parent"]) == origin:
        return RuleProposal(rid, False, (), "precondition failed: object did not move")
    paths = _by_ids(ctx, "move", (obj, origin))
    if origin == _agent_room(ctx.after):
        paths += _by_ids(ctx, "put down", (obj,))
    why = f"move uuid {obj} back to uuid {origin}" if paths else "no valid action returns it"
    return RuleProposal(rid, True, paths, why)


def _pour_back(ctx: InverseContext) -> RuleProposal:
    rid = "pour-contents-back"
    if len(ctx.target_ids) != 2 or ctx.target_ids[0] not in ctx.before.objects:
        return RuleProposal(rid, False, (), "pour source is not in the object tree")
    src, dst = ctx.target_ids
    if not ctx.before.objects[src].get("propContainer.isContainer"):
        return RuleProposal(rid, False, (), "source is not a container (handled as a move)")
    dst_movable = [
        u
        for u, r in ctx.before.objects.items()
        if r.get("parent") == dst and r.get("propMoveable.isMovable")
    ]
    if dst_movable:
        return RuleProposal(
            rid, False, (), f"precondition failed: destination already held {len(dst_movable)} "
            "movable object(s); pouring back would move them too"
        )  # fmt: skip
    paths = _by_ids(ctx, "pour", (dst, src))
    return RuleProposal(rid, True, paths, "pour destination back into source" if paths else
                        "inverse pour not valid in S1")  # fmt: skip


_OPEN_CLOSE_SRC = "actions/ActionOpenCloseDoor.scala: ActionOpenDoor/ActionCloseDoor case 2"
_ACTIVATE_SRC = "actions/ActionActivate.scala: ActionActivate/ActionDeactivate (isActivated)"
REGISTRY: tuple[InverseRule, ...] = (
    InverseRule(
        "container-open-then-close", r"^open (?!door to )", OBJECT_TREE,
        "closing a container opened by the target restores propContainer.isOpen",
        _OPEN_CLOSE_SRC, _toggle("container-open-then-close", "propContainer.isOpen",
                                 False, True, "close"),
    ),
    InverseRule(
        "container-close-then-open", r"^close (?!door to )", OBJECT_TREE,
        "opening a container closed by the target restores propContainer.isOpen",
        _OPEN_CLOSE_SRC, _toggle("container-close-then-open", "propContainer.isOpen",
                                 True, False, "open"),
    ),
    InverseRule(
        "door-open-then-close", r"^open door to ", CURRENT_ROOM_TEXT,
        "closing the same portal restores the door state (visible only from this room)",
        "actions/ActionOpenCloseDoor.scala: case 1 (propPortal.isOpen); portals not in tree",
        _door("door-open-then-close", "closed", "open", "close"),
    ),
    InverseRule(
        "door-close-then-open", r"^close door to ", CURRENT_ROOM_TEXT,
        "opening the same portal restores the door state (visible only from this room)",
        "actions/ActionOpenCloseDoor.scala: case 1 (propPortal.isOpen); portals not in tree",
        _door("door-close-then-open", "open", "closed", "open"),
    ),
    InverseRule(
        "device-activate-then-deactivate", r"^activate ", OBJECT_TREE,
        "deactivating restores propDevice.isActivated; side effects while on are NOT undone",
        _ACTIVATE_SRC, _toggle("device-activate-then-deactivate", "propDevice.isActivated",
                               False, True, "deactivate"),
    ),
    InverseRule(
        "device-deactivate-then-activate", r"^deactivate ", OBJECT_TREE,
        "activating restores propDevice.isActivated",
        _ACTIVATE_SRC, _toggle("device-deactivate-then-activate", "propDevice.isActivated",
                               True, False, "activate"),
    ),
    InverseRule(
        "return-to-original-container", r"^(move .+ to |pick up |put down |pour .+ into )",
        OBJECT_TREE, "moving the same uuid back to its original container restores 'parent'",
        "actions/ActionMoveObject.scala: ActionMoveObject/PickUp/PutDown/Pour (addObject)",
        _return_to_parent,
    ),
    InverseRule(
        "pour-contents-back", r"^pour .+ into ", OBJECT_TREE,
        "pouring the destination back moves the same content uuids back, if it was empty",
        "actions/ActionMoveObject.scala: ActionPourObject (moves all movable contents)",
        _pour_back,
    ),
)  # fmt: skip
RULES_BY_ID = {r.rule_id: r for r in REGISTRY}


# -- experiments ------------------------------------------------------------------------
@dataclass(frozen=True)
class ExplicitPath:
    """A hand-specified candidate path (e.g. a compensating refill). Still agent-valid only."""

    name: str
    actions: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class InverseExperiment:
    experiment_id: str
    recipe: ReplayRecipe  # rebuilds S0 (researcher operation, not a restoration action)
    target_action: str
    rules: tuple[str, ...] | None = None  # None = every registry rule whose pattern matches
    explicit_paths: tuple[ExplicitPath, ...] = ()
    idle_action: str = "look at agent"  # one tick, no discrete effect: counterfactual filler
    purpose: str = ""

    def __post_init__(self) -> None:
        for rid in self.rules or ():
            if rid not in RULES_BY_ID:
                raise ValueError(f"unknown inverse rule {rid!r}")
        for p in self.explicit_paths:
            if not p.actions:
                raise ValueError("explicit paths need at least one action")

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "recipe": self.recipe.to_dict(),
            "target_action": self.target_action,
            "rules": list(self.rules) if self.rules is not None else None,
            "explicit_paths": [
                {"name": p.name, "actions": list(p.actions), "rationale": p.rationale}
                for p in self.explicit_paths
            ],
            "idle_action": self.idle_action,
            "purpose": self.purpose,
        }


# -- results ------------------------------------------------------------------------------
@dataclass(frozen=True)
class CandidateStep:
    action: str
    status: str  # accepted | invalid | ambiguous | unavailable | excluded
    result: StepResult | None

    @property
    def ticks(self) -> int:
        return 0 if self.result is None else self.result.moves_after - self.result.moves_before

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "status": self.status,
            "executed": self.result is not None,
            "ticks": self.ticks,
            "observation": None if self.result is None else self.result.observation[:200],
        }


@dataclass(frozen=True)
class ComparisonSummary:
    mode: str
    outcome: str  # observed_fields_match | observed_fields_differ
    diff: StateDiff
    n_temperature_changes: int
    max_abs_temperature_delta: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "outcome": self.outcome,
            "n_temperature_changes_unfiltered": self.n_temperature_changes,
            "max_abs_temperature_delta_unfiltered": self.max_abs_temperature_delta,
            "diff": self.diff.to_dict(max_changes=25),
        }


def _temperature_stats(a: CanonicalState, b: CanonicalState) -> tuple[int, float]:
    deltas = [
        abs(c.after - c.before)
        for c in canonical_diff(a, b).changes
        if c.key.endswith(":propMaterial.temperatureC")
        and isinstance(c.before, int | float)
        and isinstance(c.after, int | float)
    ]
    return len(deltas), round(max(deltas, default=0.0), 6)


def _summary(mode: str, diff: StateDiff, a: CanonicalState, b: CanonicalState) -> ComparisonSummary:
    n, mx = _temperature_stats(a, b)
    outcome = OBSERVED_FIELDS_MATCH if diff.equal_on_observed_fields else OBSERVED_FIELDS_DIFFER
    return ComparisonSummary(mode, outcome, diff, n, mx)


@dataclass(frozen=True)
class PathAttempt:
    source: str  # "rule:<id>" or "explicit:<name>"
    actions: tuple[str, ...]
    steps: tuple[CandidateStep, ...]
    executed: bool
    ticks_target: int
    ticks_path: int
    n_raw_changes: int
    comparisons: tuple[ComparisonSummary, ...]
    structural: tuple[StructuralReport, ...]
    observability_issues: tuple[str, ...]
    counterfactual_note: str | None
    outcomes: tuple[str, ...]

    @property
    def n_actions_used(self) -> int:
        return sum(1 for s in self.steps if s.result is not None)

    def comparison(self, mode: str) -> ComparisonSummary:
        return next(c for c in self.comparisons if c.mode == mode)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "actions": list(self.actions),
            "steps": [s.to_dict() for s in self.steps],
            "executed": self.executed,
            "n_actions_used": self.n_actions_used,
            "ticks_target": self.ticks_target,
            "ticks_path": self.ticks_path,
            "ticks_since_s0": self.ticks_target + self.ticks_path,
            "n_raw_changes_vs_s0": self.n_raw_changes,
            "comparisons": [c.to_dict() for c in self.comparisons],
            "structural": [s.to_dict() for s in self.structural],
            "observability_issues": list(self.observability_issues),
            "counterfactual_note": self.counterfactual_note,
            "outcomes": list(self.outcomes),
        }


@dataclass(frozen=True)
class RestorationDiagnostic:
    experiment: InverseExperiment
    target_status: str
    target_step: StepResult | None
    target_ids: tuple[str, ...]
    target_effect: StateDiff | None
    proposals: tuple[RuleProposal, ...]
    n_paths_proposed: int
    attempts: tuple[PathAttempt, ...]
    unobservable: tuple[str, ...]
    outcomes: tuple[str, ...]
    provenance: dict[str, Any] | None
    max_paths: int

    def to_dict(self) -> dict[str, Any]:
        e = self.experiment
        return {
            "version": DIAGNOSTICS_VERSION,
            "label_policy": LABEL_POLICY,
            "experiment": e.to_dict(),
            "task": e.recipe.task,
            "variation": e.recipe.variation,
            "target_action": e.target_action,
            "target_status": self.target_status,
            "target_step": None if self.target_step is None else self.target_step.to_dict(),
            "target_ids": list(self.target_ids),
            "target_effect_discrete": (
                None if self.target_effect is None else self.target_effect.to_dict(25)
            ),
            "candidate_set": {
                "scope": SEARCH_SCOPE,
                "exhaustive": False,
                "rules_considered": [p.to_dict() for p in self.proposals],
                "n_paths_proposed": self.n_paths_proposed,
                "n_paths_attempted": len(self.attempts),
                "max_paths": self.max_paths,
                "failed_search_meaning": FAILED_SEARCH_MEANING,
            },
            "attempts": [a.to_dict() for a in self.attempts],
            "unobservable": list(self.unobservable),
            "outcomes": list(self.outcomes),
            "provenance": self.provenance,
        }


# -- runner ----------------------------------------------------------------------------------
def _divergence(what: str, n_steps: int) -> ReplayDivergenceError:
    return ReplayDivergenceError(TraceComparison(False, n_steps, (what,), n_steps))


def _execute_path(session: ScienceWorldSession, actions: tuple[str, ...]) -> list[CandidateStep]:
    steps: list[CandidateStep] = []
    for action in actions:
        if EXCLUDED_RESTORATION.match(action):
            steps.append(CandidateStep(action, STATUS_EXCLUDED, None))
            break
        if action not in session.valid_actions():
            steps.append(CandidateStep(action, STATUS_UNAVAILABLE, None))
            break
        result = session.step(action)
        steps.append(CandidateStep(action, result.status, result))
        if result.status != "accepted":
            break
    return steps


def _unobservable(s0: CapturedState, s1: CapturedState) -> tuple[str, ...]:
    room = s0.canonical.world.get("agent_location")
    out = list(s0.canonical.incomplete_reasons)
    out.append(f"door states of every room except {room!r} (only its doors appear in look())")
    if s1.canonical.world.get("agent_location") != room:
        out.append("agent moved: S1 doors describe a different room than S0 doors")
    return tuple(out)


def run_inverse_experiment(
    experiment: InverseExperiment,
    *,
    config: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
    projections: tuple[Projection, ...] = (
        DISCRETE_EXPLORATION,
        TEMPERATURE_TOLERANCE_EXPLORATION,
    ),
    counterfactual: bool = True,
    verify_reconstruction: bool = True,
    max_paths: int = 4,
) -> RestorationDiagnostic:
    """Run one restoration-diagnostic experiment (docs/19 §2). Produces no labels.

    1. Rebuild S0 from the recipe; with ``verify_reconstruction`` it must equal an
       independent :func:`replay` of the same recipe (raw fingerprint).
    2. Execute the target action; capture S1 and the target's discrete effect.
    3. Collect candidate paths from the registry (selected by uuid) and explicit paths.
    4. For each path (at most ``max_paths``): rebuild S1 (verified identical), execute the
       path with agent-valid actions only, capture S2 and compare it with S0 (literal) and
       with a time-matched counterfactual (S0 + the same number of idle ticks).
    """
    recipe = experiment.recipe
    n_recipe = len(recipe.all_actions)
    reference = None
    if verify_reconstruction:
        reference = replay(recipe, config=config, backend_factory=backend_factory)

    with ScienceWorldSession(
        config, step_limit=recipe.step_limit, backend_factory=backend_factory
    ) as session:

        def rebuild_s0() -> CapturedState:
            run_recipe(session, recipe, strict=True)
            state = capture_state(session)
            if reference is not None and state.raw.fingerprint != reference.final.raw.fingerprint:
                raise _divergence("raw_state(S0 reconstruction)", n_recipe)
            return state

        s0 = rebuild_s0()
        templates0 = {t.action: t for t in session.valid_action_templates()}
        provenance = session.provenance.to_dict() if session.provenance else None
        target = experiment.target_action

        def finish(
            status: str, step: StepResult | None, ids: tuple[str, ...]
        ) -> RestorationDiagnostic:
            return RestorationDiagnostic(
                experiment, status, step, ids, None, (), 0, (),
                _unobservable(s0, s0), (TARGET_NOT_EXECUTED,), provenance, max_paths,
            )  # fmt: skip

        if target not in templates0:
            return finish(STATUS_UNAVAILABLE, None, ())
        target_ids = templates0[target].obj_ids
        target_step = session.step(target)
        if target_step.status != "accepted":
            return finish(target_step.status, target_step, target_ids)
        s1 = capture_state(session)
        templates1 = tuple(session.valid_action_templates())
        effect = projection_diff(s0.canonical, s1.canonical, DISCRETE_EXPLORATION)

        ctx = InverseContext(target, target_ids, s0.canonical, s1.canonical, templates1)
        rules = (
            list(REGISTRY)
            if experiment.rules is None
            else [RULES_BY_ID[r] for r in experiment.rules]
        )
        proposals = tuple(r.propose(ctx) for r in rules if r.matches(target))
        rule_obs = {r.rule_id: r.observability for r in rules}
        candidates: list[tuple[str, tuple[str, ...], str]] = []
        for p in proposals:
            for path in p.paths:
                if all(path != c[1] for c in candidates):
                    candidates.append((f"rule:{p.rule_id}", path, rule_obs[p.rule_id]))
        for ep in experiment.explicit_paths:
            candidates.append((f"explicit:{ep.name}", ep.actions, OBJECT_TREE))

        base_issues: list[str] = []
        missing = [i for i in target_ids if i not in s0.canonical.objects]
        if missing:
            base_issues.append(f"target refers to uuid(s) absent from the object tree: {missing}")
        if any(c.key.startswith("door:") for c in effect.changes):
            base_issues.append("target changed a door state, observable only from this room")
        if effect.equal_on_observed_fields:
            base_issues.append(
                "target produced no observed discrete effect (refused by the simulator, or its "
                "effect is outside the captured state)"
            )

        attempts: list[PathAttempt] = []
        for i, (source, path, channel) in enumerate(candidates[:max_paths]):
            if i > 0:
                rebuild_s0()
                again = session.step(target)
                if capture_state(session).raw.fingerprint != s1.raw.fingerprint or (
                    again.status != "accepted"
                ):
                    raise _divergence("raw_state(S1 reconstruction)", n_recipe + 1)
            steps = _execute_path(session, path)
            executed = len(steps) == len(path) and all(s.status == "accepted" for s in steps)
            s2 = capture_state(session)
            ticks_target = target_step.moves_after - target_step.moves_before
            ticks_path = sum(s.ticks for s in steps)
            issues = list(base_issues)
            if channel == CURRENT_ROOM_TEXT:
                issues.append("restored property is a door state: visible only in look() text")
            if s2.canonical.world.get("agent_location") != s0.canonical.world.get("agent_location"):
                issues.append("agent location differs from S0: door observations not comparable")

            comps = [_summary("literal_canonical", canonical_diff(s0.canonical, s2.canonical),
                              s0.canonical, s2.canonical)]  # fmt: skip
            comps += [
                _summary(f"literal_projection:{p.name}", projection_diff(s0.canonical,
                         s2.canonical, p), s0.canonical, s2.canonical)
                for p in projections
            ]  # fmt: skip
            structural = (
                structural_match(s0.canonical, s2.canonical),
                structural_match(s0.canonical, s2.canonical, location_sensitive=False),
            )
            cf_note = None
            if counterfactual:
                rebuild_s0()
                idle = [_execute_path_idle(session, experiment.idle_action) for _ in
                        range(ticks_target + ticks_path)]  # fmt: skip
                if all(t == 1 for t in idle):
                    c = capture_state(session)
                    comps.append(_summary("counterfactual_canonical",
                                          canonical_diff(c.canonical, s2.canonical),
                                          c.canonical, s2.canonical))  # fmt: skip
                    comps += [
                        _summary(f"counterfactual_projection:{p.name}", projection_diff(
                            c.canonical, s2.canonical, p), c.canonical, s2.canonical)
                        for p in projections
                    ]  # fmt: skip
                    cf_note = f"S0 + {len(idle)} x {experiment.idle_action!r} (1 tick each) vs S2"
                else:
                    cf_note = f"counterfactual unavailable: idle ticks {idle} (need 1 each)"

            outcomes = {CANDIDATE_PATH_EXECUTED if executed else CANDIDATE_PATH_NOT_EXECUTED}
            if executed:
                outcomes.update(c.outcome for c in comps)
            if issues:
                outcomes.add(INSUFFICIENT_OBSERVABILITY)
            attempts.append(
                PathAttempt(
                    source, path, tuple(steps), executed, ticks_target, ticks_path,
                    len(raw_diff(s0.raw, s2.raw).changes), tuple(comps), structural,
                    tuple(issues), cf_note, tuple(sorted(outcomes)),
                )
            )  # fmt: skip

    top: set[str] = set()
    if not candidates:
        top.add(NO_CANDIDATE_PATH_FOUND)
        if base_issues:
            top.add(INSUFFICIENT_OBSERVABILITY)
    for a in attempts:
        top.update(a.outcomes)
    return RestorationDiagnostic(
        experiment, target_step.status, target_step, target_ids, effect, proposals,
        len(candidates), tuple(attempts), _unobservable(s0, s1), tuple(sorted(top)),
        provenance, max_paths,
    )  # fmt: skip


def _execute_path_idle(session: ScienceWorldSession, idle_action: str) -> int:
    """Take one idle step for the counterfactual; returns the ticks it consumed (0 if refused)."""
    if idle_action not in session.valid_actions():
        return 0
    r = session.step(idle_action)
    return r.moves_after - r.moves_before if r.status == "accepted" else 0


# -- the Phase 4D experiment set ----------------------------------------------------------
def phase4d_experiments() -> tuple[InverseExperiment, ...]:
    """Experiments run in docs/19 §4 (task 1-1 'boil', variation 0, kitchen)."""
    base = ReplayRecipe(
        "1-1", 0, "teleportAction", preparation=FIRST_TICK_PREPARATION,
        actions=("teleport to kitchen",),
    )  # fmt: skip
    sink_cycle = ExplicitPath(
        "sink-refill",
        ("activate sink", "deactivate sink"),
        "compensating refill: the sink adds a NEW water object to an open container inside it",
    )
    pot_with_water = base.extend(
        "open cupboard", "move metal pot to sink", "activate sink", "deactivate sink"
    )
    salt_and_water = base.extend(
        "open cupboard", "open glass jar", "pour glass jar into metal pot",
        "move metal pot to sink", "activate sink", "deactivate sink",
    )  # fmt: skip
    return (
        InverseExperiment("E01-container-open", base, "open cupboard",
                          purpose="container door: tree-observable toggle"),
        InverseExperiment("E02-container-close", base.extend("open cupboard"), "close cupboard",
                          purpose="container door, reverse direction"),
        InverseExperiment("E03-device-stove", base, "activate stove",
                          purpose="device toggle with a heating side effect"),
        InverseExperiment("E04-device-sink", base, "activate sink",
                          purpose="device toggle that creates objects while on"),
        InverseExperiment("E05-door", base, "open door to hallway",
                          purpose="portal: state only in current-room look() text"),
        InverseExperiment("E06-move-return", base, "move apple to table",
                          purpose="move an object and return it"),
        InverseExperiment("E07-pickup-return", base, "pick up apple",
                          purpose="pick up into inventory and return"),
        InverseExperiment("E08-pour-back", base.extend("open cupboard", "open glass jar"),
                          "pour glass jar into ceramic cup",
                          purpose="move contents to another container and pour them back"),
        InverseExperiment("E09-empty-refill", pot_with_water, "pour metal pot into sink",
                          explicit_paths=(sink_cycle,),
                          purpose="empty a container, refill from the sink (new uuids)"),
        InverseExperiment("E10-mix", salt_and_water, "mix metal pot",
                          explicit_paths=(sink_cycle,),
                          purpose="mixing deletes inputs; refill is compensating only"),
        InverseExperiment("E11-eat", base, "eat banana",
                          purpose="consumption detaches the object; no registry rule"),
    )  # fmt: skip
