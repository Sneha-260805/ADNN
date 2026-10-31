"""Restoration-search sensitivity: an expanded 1-step candidate set (Phase 4F, docs/22 §5).

The Phase 4D/4E registry proposes a few hand-written inverses. This module asks how
much that restriction matters on a small subsample: after the target, it tries *every*
agent-valid single action whose objects touch the target's objects, their containers
(before and after the target) or objects the target created ("object-local 1-step").
Each candidate is compared with the time-matched counterfactual at exact, 0.01 degC and
0.1 degC. It also reports the full 1-step branching factor (all valid actions), which is
counted but not executed.

Guardrails: still restricted (object-local, 1 step, optionally sampled), so a failure is
never irreversibility; helper/idle commands and door/portal actions are never candidates;
the same fixed query protocol is used on every rebuild (docs/21 §3.2).
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from adnn.scienceworld.canonical import CanonicalState, CapturedState, capture_state
from adnn.scienceworld.diagnostics import (
    TEMPERATURE_TOLERANCE_001,
    TEMPERATURE_TOLERANCE_01,
    canonical_diff,
    projection_diff,
)
from adnn.scienceworld.env import ActionTemplate, Backend, ScienceWorldSession
from adnn.scienceworld.provenance import RuntimeConfig
from adnn.scienceworld.provisional import IDLE_ACTION, MATCH_LEVELS, door_exclusion_reason
from adnn.scienceworld.replay import (
    ReplayDivergenceError,
    ReplayRecipe,
    TraceComparison,
    run_recipe,
)
from adnn.scienceworld.restoration_diagnostics import (
    EXCLUDED_RESTORATION,
    REGISTRY,
    InverseContext,
)

SEARCH_VERSION = "sw-expanded-search-2"
SCOPE = "object_local_1step"


def match_level(counterfactual: CanonicalState, s2: CanonicalState) -> str:
    if canonical_diff(counterfactual, s2).equal_on_observed_fields:
        return "exact"
    if projection_diff(counterfactual, s2, TEMPERATURE_TOLERANCE_001).equal_on_observed_fields:
        return "within_0.01C"
    if projection_diff(counterfactual, s2, TEMPERATURE_TOLERANCE_01).equal_on_observed_fields:
        return "within_0.1C"
    return "none"


def related_objects(
    s0: CanonicalState, s1: CanonicalState, target_ids: tuple[str, ...]
) -> set[str]:
    created = set(s1.objects) - set(s0.objects)
    core = set(target_ids) | created
    parents = {
        str(state.objects[u].get("parent"))
        for state in (s0, s1)
        for u in core
        if u in state.objects
    }
    return (core | parents) - {"None"}


def candidate_pool(
    templates: list[ActionTemplate],
    s0: CanonicalState,
    s1: CanonicalState,
    target_ids: tuple[str, ...],
) -> tuple[list[str], dict[str, int]]:
    """Object-local candidates (sorted) and the branching counts at each filter stage."""
    groups: dict[str, set[tuple[str, ...]]] = {}
    for t in templates:
        groups.setdefault(t.action, set()).add(t.obj_ids)
    unambiguous = {a: next(iter(ids)) for a, ids in groups.items() if len(ids) == 1}
    allowed = {
        a: ids
        for a, ids in unambiguous.items()
        if not EXCLUDED_RESTORATION.match(a) and not door_exclusion_reason(a, ids, s1)
    }
    related = related_objects(s0, s1, target_ids)
    local = sorted(a for a, ids in allowed.items() if set(ids) & related)
    return local, {
        "valid_actions": len(groups),
        "unambiguous": len(unambiguous),
        "agent_restoration_allowed": len(allowed),
        "object_local": len(local),
    }


def verb_of(action: str) -> str:
    words = action.split()
    return " ".join(words[:2]) if words[:2] in (["pick", "up"], ["put", "down"]) else words[0]


def registry_inverses(ctx: InverseContext) -> list[str]:
    """The Phase 4D/4E hand-written single-step inverses for this target (the original set)."""
    out: list[str] = []
    for rule in REGISTRY:
        if rule.matches(ctx.target):
            out += [p[0] for p in rule.propose(ctx).paths if len(p) == 1 and p[0] not in out]
    return out


def select_candidates(
    local: list[str], always: list[str], max_candidates: int, seed: int
) -> list[str]:
    """All of ``always`` (if object-local), then a verb-stratified, seeded round-robin fill.

    Uniform sampling is dominated by the most numerous verb (e.g. ``connect X to Y``);
    stratifying by verb keeps rare but relevant verbs such as ``open``/``close``.
    """
    chosen = [a for a in always if a in local]
    rest = [a for a in local if a not in chosen]
    if len(chosen) + len(rest) <= max_candidates:
        return sorted(chosen + rest)
    rng = random.Random(seed)
    groups: dict[str, list[str]] = {}
    for a in rest:
        groups.setdefault(verb_of(a), []).append(a)
    queues = [rng.sample(g, len(g)) for _, g in sorted(groups.items())]
    while len(chosen) < max_candidates and any(queues):
        for q in queues:
            if q and len(chosen) < max_candidates:
                chosen.append(q.pop(0))
    return sorted(chosen)


@dataclass(frozen=True)
class CandidateResult:
    action: str
    status: str
    ticks: int
    match_level: str
    source: str  # "registry" (original hand-written inverse) | "expanded"

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _divergence(what: str) -> ReplayDivergenceError:
    return ReplayDivergenceError(TraceComparison(False, None, (what,), 0))


def expanded_search(
    recipe: ReplayRecipe,
    target: str,
    *,
    max_candidates: int = 50,
    seed: int = 0,
    config: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
) -> dict[str, Any]:
    """Run the object-local 1-step search for one (S0, target). Produces no label."""
    t0 = time.perf_counter()
    with ScienceWorldSession(
        config, step_limit=recipe.step_limit, backend_factory=backend_factory
    ) as session:

        def rebuild() -> tuple[CapturedState, list[ActionTemplate]]:
            run_recipe(session, recipe, strict=True)
            return capture_state(session), session.valid_action_templates()

        s0, templates0 = rebuild()
        by_text = {t.action: t for t in templates0}
        if target not in by_text:
            return {"version": SEARCH_VERSION, "target_status": "unavailable"}
        target_ids = by_text[target].obj_ids
        r = session.step(target)
        if r.status != "accepted":
            return {"version": SEARCH_VERSION, "target_status": r.status}
        s1 = capture_state(session)
        templates1 = session.valid_action_templates()
        local, branching = candidate_pool(templates1, s0.canonical, s1.canonical, target_ids)
        ctx = InverseContext(target, target_ids, s0.canonical, s1.canonical, tuple(templates1))
        original = registry_inverses(ctx)
        ticks_target = r.moves_after - r.moves_before
        chosen = select_candidates(local, original, max_candidates, seed)

        counterfactuals: dict[int, CanonicalState | None] = {}

        def counterfactual(ticks: int) -> CanonicalState | None:
            if ticks not in counterfactuals:
                rebuild()
                ok = True
                for _ in range(ticks):
                    step = session.step(IDLE_ACTION)
                    ok = (
                        ok
                        and step.status == "accepted"
                        and step.moves_after - step.moves_before == 1
                    )
                counterfactuals[ticks] = capture_state(session).canonical if ok else None
            return counterfactuals[ticks]

        results: list[CandidateResult] = []
        t_cand = time.perf_counter()
        for action in chosen:
            state, _ = rebuild()
            if state.raw.fingerprint != s0.raw.fingerprint:
                raise _divergence("raw_state(S0 rebuild, expanded search)")
            again = session.step(target)
            if capture_state(session).raw.fingerprint != s1.raw.fingerprint or (
                again.status != "accepted"
            ):
                raise _divergence("raw_state(S1 rebuild, expanded search)")
            session.valid_action_templates()  # same query order as the first pass
            step = session.step(action)
            ticks = step.moves_after - step.moves_before
            s2 = capture_state(session).canonical
            level = "not_compared"
            if step.status == "accepted":
                cf = counterfactual(ticks_target + ticks)
                level = "not_compared" if cf is None else match_level(cf, s2)
            source = "registry" if action in original else "expanded"
            results.append(CandidateResult(action, step.status, ticks, level, source))
        t_end = time.perf_counter()

    executed = [c for c in results if c.status == "accepted"]
    best = min((c.match_level for c in executed), key=MATCH_LEVELS.index, default="not_compared")
    return {
        "version": SEARCH_VERSION,
        "scope": SCOPE,
        "restricted": True,
        "exhaustive": False,
        "target": target,
        "target_status": "accepted",
        "branching": branching,
        "registry_inverses": original,
        "registry_inverses_outside_pool": [a for a in original if a not in local],
        "registry_best_match_level": min(
            (c.match_level for c in executed if c.source == "registry"),
            key=MATCH_LEVELS.index,
            default="not_compared",
        ),
        "selection": "registry inverses + verb-stratified seeded round-robin",
        "n_candidates_tried": len(chosen),
        "sampled": len(chosen) < len(local),
        "coverage_of_object_local": round(len(chosen) / len(local), 3) if local else None,
        "n_accepted": len(executed),
        "n_refused_or_invalid": len(results) - len(executed),
        "best_match_level": best,
        "matches": {
            lv: [c.action for c in executed if c.match_level == lv]
            for lv in ("exact", "within_0.01C", "within_0.1C")
        },
        "candidates": [c.to_dict() for c in results],
        "cost": {
            "total_s": round(t_end - t0, 1),
            "s_per_candidate": round((t_end - t_cand) / len(chosen), 2) if chosen else None,
            "estimated_s_full_1step": round(
                (t_end - t_cand) / len(chosen) * branching["agent_restoration_allowed"], 0
            )
            if chosen
            else None,
            "estimated_s_object_local_2step": round(
                (t_end - t_cand) / len(chosen) * len(local) ** 2, 0
            )
            if chosen
            else None,
        },
        "failed_search_meaning": "an unsuccessful expanded 1-step search is still restricted "
        "and is not evidence that the action cannot be undone (RD-04)",
    }
