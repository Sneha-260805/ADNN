"""Collect label-validation evidence for one deliberately constructed case (Phase 4G, docs/23).

Order of operations (ADR-0004 A2):

1. the case's :class:`~adnn.scienceworld.semantics.Declaration` is hashed and recorded
   *before* the simulator is touched;
2. S0 is built twice from its recipe and must reproduce bit-for-bit (replay check);
3. roles are bound to S0 uuids; the target is checked (valid, unambiguous, not a door);
4. the permitted recovery paths are the registry inverses, the declared paths and an
   object-local, verb-stratified 1-step expansion (``expanded_search``);
5. every path is executed from a fresh, fingerprint-checked rebuild, judged against the
   time-matched counterfactual and against "target then idle" at 0, 0.01 and 0.1 degC.

Certificate preconditions are evaluated for the cases that name a certificate. The
output is evidence for :mod:`adnn.scienceworld.admission`, never a label.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from adnn.scienceworld.canonical import CanonicalState, CapturedState, capture_state
from adnn.scienceworld.certificates import check_burn, check_eat, check_mix_salt
from adnn.scienceworld.contrasts import stochastic_exposure
from adnn.scienceworld.diagnostics import DISCRETE_EXPLORATION, projection_diff
from adnn.scienceworld.env import ActionTemplate, Backend, ScienceWorldSession
from adnn.scienceworld.expanded_search import candidate_pool, registry_inverses, select_candidates
from adnn.scienceworld.provenance import RuntimeConfig
from adnn.scienceworld.provisional import IDLE_ACTION, FamilySpec, door_exclusion_reason
from adnn.scienceworld.replay import ReplayRecipe, run_recipe
from adnn.scienceworld.restoration_diagnostics import InverseContext
from adnn.scienceworld.semantics import (
    TOLERANCES,
    BindingError,
    Declaration,
    assess_attempt,
    bind,
)

EVIDENCE_VERSION = "sw-label-evidence-0.1"


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    family: FamilySpec
    history: tuple[str, ...]
    target: str
    declaration: Declaration
    certificates: tuple[str, ...] = ()
    max_expanded: int = 20
    purpose: str = ""
    expected: str = ""  # what the case was constructed to exercise (not used by admission)

    def recipe(self) -> ReplayRecipe:
        return self.family.base_recipe().extend(*self.history)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "family_id": self.family.family_id,
            "task": self.family.task,
            "history": list(self.history),
            "target": self.target,
            "certificates": list(self.certificates),
            "max_expanded": self.max_expanded,
            "purpose": self.purpose,
            "expected": self.expected,
        }


@dataclass
class _Run:
    session: ScienceWorldSession
    recipe: ReplayRecipe
    cf: dict[int, CanonicalState | None] = field(default_factory=dict)
    idle: dict[int, CanonicalState | None] = field(default_factory=dict)

    def rebuild(self) -> tuple[CapturedState, list[ActionTemplate]]:
        run_recipe(self.session, self.recipe, strict=True)
        return capture_state(self.session), self.session.valid_action_templates()

    def _idle(self, n: int) -> bool:
        ok = True
        for _ in range(n):
            r = self.session.step(IDLE_ACTION)
            ok = ok and r.status == "accepted" and r.moves_after - r.moves_before == 1
        return ok

    def counterfactual(self, ticks: int) -> CanonicalState | None:
        if ticks not in self.cf:
            self.rebuild()
            ok = self._idle(ticks)
            self.cf[ticks] = capture_state(self.session).canonical if ok else None
        return self.cf[ticks]

    def target_then_idle(self, target: str, ticks: int) -> CanonicalState | None:
        if ticks not in self.idle:
            self.rebuild()
            self.session.step(target)
            self.session.valid_action_templates()
            ok = self._idle(ticks)
            self.idle[ticks] = capture_state(self.session).canonical if ok else None
        return self.idle[ticks]


def _certificate_checks(
    spec: CaseSpec, s0: CanonicalState, s1: CanonicalState, cf: CanonicalState | None,
    target_ids: tuple[str, ...],
) -> dict[str, Any]:  # fmt: skip
    out: dict[str, Any] = {}
    for cid in spec.certificates:
        if cid == "C-MIX-SALT":
            out[cid] = check_mix_salt(s0, spec.target, s1, counterfactual=cf).to_dict()
        elif cid == "C-BURN":
            out[cid] = check_burn(s0, spec.target, s1, counterfactual=cf).to_dict()
        elif cid == "C-EAT":
            identity, structural = check_eat(s0, spec.target, s1, target_ids)
            out[cid] = {"identity": identity.to_dict(), "structural": structural.to_dict()}
        else:
            raise ValueError(f"unknown certificate {cid!r}")
    return out


def collect_case(
    spec: CaseSpec,
    *,
    config: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
) -> dict[str, Any]:
    """Build the case on the simulator and return its evidence document."""
    t0 = time.perf_counter()
    declaration = spec.declaration.to_dict()
    doc: dict[str, Any] = {
        "schema_version": EVIDENCE_VERSION,
        "case": spec.to_dict(),
        "declaration": declaration,
        "declaration_sha256": spec.declaration.sha256,
        "declared_before_search": True,  # hashed above, before any simulator call
        "provenance": {"recipe": spec.recipe().to_dict()},
        "status": "incomplete",
    }
    recipe = spec.recipe()
    with ScienceWorldSession(
        config, step_limit=recipe.step_limit, backend_factory=backend_factory
    ) as session:
        run = _Run(session, recipe)
        s0, templates0 = run.rebuild()
        again, _ = run.rebuild()
        doc["replay"] = {
            "verified": again.raw.fingerprint == s0.raw.fingerprint,
            "s0_raw_fingerprint": s0.raw.fingerprint,
            "rebuild_raw_fingerprint": again.raw.fingerprint,
        }
        doc["observation"] = {
            "canonical_incomplete_reasons": list(s0.canonical.incomplete_reasons),
            "history_door_actions": [a for a in spec.history if "door" in a],
            "history_bee_actions": [a for a in spec.history if "bee" in a],
        }
        doc["exclusion_signals"] = {"stochastic_exposure_s0": stochastic_exposure(s0.canonical)}
        try:
            binding = bind(spec.declaration, s0.canonical)
        except BindingError as exc:
            doc["status"] = f"binding_failed: {exc}"
            return doc
        doc["binding"] = binding
        matches = [t for t in templates0 if t.action == spec.target]
        target_info: dict[str, Any] = {
            "action": spec.target,
            "n_templates_with_text": len({t.obj_ids for t in matches}),
            "in_valid_actions": bool(matches),
        }
        doc["target"] = target_info
        if len({t.obj_ids for t in matches}) != 1:
            doc["status"] = "target_unavailable_or_ambiguous"
            return doc
        target_ids = matches[0].obj_ids
        target_info["obj_ids"] = list(target_ids)
        target_info["door_exclusion"] = door_exclusion_reason(spec.target, target_ids, s0.canonical)
        r = session.step(spec.target)
        ticks_t = r.moves_after - r.moves_before
        target_info.update(status=r.status, observation=r.observation, ticks=ticks_t)
        if r.status != "accepted":
            doc["status"] = f"target_{r.status}"
            return doc
        s1 = capture_state(session)
        templates1 = session.valid_action_templates()
        cf_t = run.counterfactual(ticks_t)
        if cf_t is None:
            doc["status"] = "counterfactual_unavailable"
            return doc
        effect = projection_diff(cf_t, s1.canonical, DISCRETE_EXPLORATION)
        target_info["discrete_effect_vs_counterfactual"] = [c.key for c in effect.changes][:25]
        target_info["created"] = [n for _, n in effect.created_objects]
        target_info["deleted"] = [n for _, n in effect.deleted_objects]
        target_info["no_op"] = effect.equal_on_observed_fields
        doc["exclusion_signals"]["stochastic_exposure_s1"] = stochastic_exposure(s1.canonical)
        doc["certificate_checks"] = _certificate_checks(
            spec, s0.canonical, s1.canonical, cf_t, target_ids
        )

        ctx = InverseContext(spec.target, target_ids, s0.canonical, s1.canonical, tuple(templates1))
        registry = registry_inverses(ctx)
        local, branching = candidate_pool(templates1, s0.canonical, s1.canonical, target_ids)
        expanded = select_candidates(local, [], spec.max_expanded, seed=0)
        paths: list[tuple[str, tuple[str, ...]]] = [("registry", (a,)) for a in registry]
        paths += [("declared", p) for p in spec.declaration.paths]
        paths += [("expanded", (a,)) for a in expanded]
        seen: set[tuple[str, ...]] = set()
        attempts = []
        for source, path in paths:
            if path in seen:
                continue
            seen.add(path)
            attempts.append(_attempt(run, spec, binding, source, path, s0, s1, cf_t, ticks_t))
        doc["search"] = {
            "registry_inverses": registry,
            "declared_paths": [list(p) for p in spec.declaration.paths],
            "n_expanded": len(expanded),
            "object_local_pool": len(local),
            "branching": branching,
            "restricted": True,
            "note": "bounded search; failure to find a path is never irreversibility (RD-04)",
        }
        doc["attempts"] = attempts
        stoch = sorted({b for a in attempts for b in a.get("stochastic_exposure_s2", [])})
        doc["exclusion_signals"]["stochastic_exposure_s2"] = stoch
    doc["status"] = "complete"
    doc["elapsed_s"] = round(time.perf_counter() - t0, 1)
    return doc


def _attempt(
    run: _Run, spec: CaseSpec, binding: dict[str, str], source: str, path: tuple[str, ...],
    s0: CapturedState, s1: CapturedState, cf_t: CanonicalState, ticks_t: int,
) -> dict[str, Any]:  # fmt: skip
    row: dict[str, Any] = {"source": source, "path": list(path)}
    state, _ = run.rebuild()
    again = run.session.step(spec.target)
    s1_again = capture_state(run.session)
    row["verified"] = (
        state.raw.fingerprint == s0.raw.fingerprint
        and again.status == "accepted"
        and s1_again.raw.fingerprint == s1.raw.fingerprint
    )
    run.session.valid_action_templates()  # fixed query protocol (ADR-0003 D8)
    ticks_p, statuses = 0, []
    for action in path:
        step = run.session.step(action)
        statuses.append(step.status)
        ticks_p += step.moves_after - step.moves_before
        if step.status != "accepted":
            break
    row.update(statuses=statuses, ticks=ticks_p)
    if not row["verified"] or any(s != "accepted" for s in statuses):
        row["executed"] = False
        return row
    row["executed"] = True
    s2 = capture_state(run.session).canonical
    row["stochastic_exposure_s2"] = stochastic_exposure(s2)
    cf_total = run.counterfactual(ticks_t + ticks_p)
    idle = run.target_then_idle(spec.target, ticks_p)
    if cf_total is None or idle is None:
        row["assessments"] = None
        row["counterfactual_available"] = False
        return row
    row["counterfactual_available"] = True
    row["assessments"] = {
        str(tol): assess_attempt(
            spec.declaration, binding, s1=s1.canonical, cf_target=cf_t, s2=s2,
            cf_total=cf_total, idle_after_target=idle, tolerance=tol,
        ).to_dict()
        for tol in TOLERANCES
    }  # fmt: skip
    return row
