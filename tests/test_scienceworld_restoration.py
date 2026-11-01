"""Restoration-diagnostic and structural-matching unit tests (docs/19 §8). No Java needed."""

from __future__ import annotations

import json
from typing import Any

import pytest

from adnn.scienceworld import (
    OUTCOMES,
    REGISTRY,
    ExplicitPath,
    InverseExperiment,
    RawState,
    ReplayDivergenceError,
    ReplayRecipe,
    ScienceWorldSession,
    canonical_diff,
    canonicalize,
    phase4d_experiments,
    run_inverse_experiment,
    run_recipe,
    structural_match,
)
from adnn.scienceworld.canonical import CanonicalState
from adnn.scienceworld.restoration_diagnostics import (
    CANDIDATE_PATH_EXECUTED,
    CANDIDATE_PATH_NOT_EXECUTED,
    EXCLUDED_RESTORATION,
    INSUFFICIENT_OBSERVABILITY,
    NO_CANDIDATE_PATH_FOUND,
    OBSERVED_FIELDS_DIFFER,
    OBSERVED_FIELDS_MATCH,
    TARGET_NOT_EXECUTED,
)
from scienceworld_restoration_fake import MiniKitchen

BASE = ReplayRecipe("1-1", 0, "", preparation=("wait1",))
DISCRETE = "literal_projection:discrete-exploration-v1"
TOLERANT = "literal_projection:temperature-tolerance-exploration-v1"
SINK_CYCLE = ExplicitPath("sink-refill", ("activate sink", "deactivate sink"), "refill")


def run(exp: InverseExperiment, created: list[MiniKitchen] | None = None, **kw: Any):
    knobs = kw.pop("knobs", {})

    def factory() -> MiniKitchen:
        k = MiniKitchen(**knobs)
        if created is not None:
            created.append(k)
        return k

    return run_inverse_experiment(exp, backend_factory=factory, **kw)


def exp(target: str, recipe: ReplayRecipe = BASE, **kw: Any) -> InverseExperiment:
    return InverseExperiment(f"t-{target}", recipe, target, **kw)


# -- registry and candidate selection ---------------------------------------------------
def test_registry_rules_are_documented_and_patterns_are_disjoint_for_doors() -> None:
    for rule in REGISTRY:
        assert rule.hypothesis and rule.source and rule.observability
    door = [r.rule_id for r in REGISTRY if r.matches("open door to hallway")]
    assert door == ["door-open-then-close"]
    assert [r.rule_id for r in REGISTRY if r.matches("open cupboard")] == [
        "container-open-then-close"
    ]
    with pytest.raises(ValueError, match="unknown inverse rule"):
        exp("open cupboard", rules=("made-up",))


def test_inverse_is_selected_by_uuid_among_indistinguishable_objects() -> None:
    d = run(exp("move tin cup 17 to bowl"))
    (attempt,) = d.attempts
    assert attempt.actions == ("move tin cup 17 to table",)  # not the identical cup 18
    assert attempt.source == "rule:return-to-original-container"
    assert attempt.comparison(DISCRETE).outcome == OBSERVED_FIELDS_MATCH
    assert d.target_ids == ("17", "14")


def test_container_toggle_executes_and_reports_every_comparison() -> None:
    d = run(exp("open cupboard"))
    (a,) = d.attempts
    assert a.executed and a.n_actions_used == 1 and (a.ticks_target, a.ticks_path) == (1, 1)
    assert a.comparison(DISCRETE).outcome == OBSERVED_FIELDS_MATCH
    assert a.comparison("literal_canonical").outcome == OBSERVED_FIELDS_DIFFER  # time drift
    assert a.comparison("counterfactual_canonical").outcome == OBSERVED_FIELDS_MATCH
    assert CANDIDATE_PATH_EXECUTED in a.outcomes
    assert not a.comparison(DISCRETE).diff.supports_exact_equality_claim


def test_opposite_sounding_actions_are_tested_not_assumed() -> None:
    d = run(exp("activate sink"))
    (a,) = d.attempts
    assert a.actions == ("deactivate sink",) and a.executed
    disc = a.comparison(DISCRETE)
    assert disc.outcome == OBSERVED_FIELDS_DIFFER
    assert "water" in {n for _, n in disc.diff.created_objects}  # drained into the sewer
    assert a.comparison("counterfactual_canonical").outcome == OBSERVED_FIELDS_DIFFER


def test_unavailable_inverse_gives_no_candidate_path() -> None:
    d = run(exp("open cupboard"), knobs={"hidden": frozenset({"close cupboard"})})
    (p,) = d.proposals
    assert p.applicable and not p.paths and "not valid" in p.reason
    assert d.attempts == () and d.outcomes == (NO_CANDIDATE_PATH_FOUND,)


def test_unavailable_explicit_step_is_not_sent_to_the_simulator() -> None:
    path = ExplicitPath("bogus", ("close cupboard", "fly to the moon"), "test")
    d = run(exp("open cupboard", rules=("container-close-then-open",), explicit_paths=(path,)))
    (a,) = d.attempts
    assert [s.status for s in a.steps] == ["accepted", "unavailable"]
    assert not a.executed and a.steps[1].result is None and a.n_actions_used == 1
    assert a.outcomes == (CANDIDATE_PATH_NOT_EXECUTED,)


def test_invalid_candidate_is_reported_and_stops_the_path() -> None:
    d = run(exp("open cupboard"), knobs={"invalid": frozenset({"close cupboard"})})
    (a,) = d.attempts
    assert [s.status for s in a.steps] == ["invalid"] and a.ticks_path == 0
    assert CANDIDATE_PATH_NOT_EXECUTED in a.outcomes


def test_empty_rule_list_means_explicit_paths_only() -> None:
    d = run(exp("open cupboard", rules=(), explicit_paths=(SINK_CYCLE,)))
    assert d.proposals == () and [a.source for a in d.attempts] == ["explicit:sink-refill"]


@pytest.mark.parametrize("action", ["look at agent", "wait1", "focus on apple", "reset task"])
def test_helper_and_idle_commands_are_never_restoration_actions(action: str) -> None:
    assert EXCLUDED_RESTORATION.match(action)
    path = ExplicitPath("idle", (action,), "test")
    d = run(exp("open cupboard", rules=("container-close-then-open",), explicit_paths=(path,)))
    assert d.attempts[0].steps[0].status == "excluded" and not d.attempts[0].executed


def test_restricted_search_reports_scope_and_never_claims_irreversibility() -> None:
    d = run(exp("eat apple"))
    out = d.to_dict()
    assert d.outcomes == (NO_CANDIDATE_PATH_FOUND,) and d.attempts == ()
    assert out["candidate_set"]["exhaustive"] is False
    assert out["candidate_set"]["scope"] == "restricted_registry"
    assert "NOT evidence" in out["candidate_set"]["failed_search_meaning"]
    deleted = {n for _, n in d.target_effect.deleted_objects}
    assert deleted == {"apple"}  # detached object leaves the tree


def test_pour_back_requires_an_empty_destination() -> None:
    opened = BASE.extend("open cupboard")
    ok = run(exp("pour glass jar into ceramic cup", opened))
    assert [a.actions for a in ok.attempts] == [("pour ceramic cup into glass jar",)]
    assert ok.attempts[0].comparison(DISCRETE).outcome == OBSERVED_FIELDS_MATCH
    bad = run(exp("pour glass jar into bowl"))  # the bowl already holds an apple
    pour = next(p for p in bad.proposals if p.rule_id == "pour-contents-back")
    assert not pour.applicable and "already held" in pour.reason


def test_refused_target_without_effect_is_flagged() -> None:
    d = run(exp("open cupboard"), knobs={"refuse": frozenset({"open cupboard"})})
    assert d.target_status == "accepted" and d.target_step.advanced_time  # costs a tick
    assert not d.proposals[0].applicable
    assert d.outcomes == (INSUFFICIENT_OBSERVABILITY, NO_CANDIDATE_PATH_FOUND)


def test_unavailable_target_is_not_executed() -> None:
    d = run(exp("open cupboard"), knobs={"hidden": frozenset({"open cupboard"})})
    assert d.target_status == "unavailable" and d.target_step is None
    assert d.outcomes == (TARGET_NOT_EXECUTED,)


# -- time and observability --------------------------------------------------------------
def test_temperature_drift_is_reported_and_tolerances_are_counted() -> None:
    (a,) = run(exp("open cupboard")).attempts
    lit = a.comparison("literal_canonical")
    assert lit.n_temperature_changes > 0 and lit.max_abs_temperature_delta == pytest.approx(0.5)
    tol = a.comparison(TOLERANT)
    assert tol.outcome == OBSERVED_FIELDS_MATCH and tol.diff.n_within_tolerance > 0
    assert a.comparison(DISCRETE).diff.n_ignored_differences > 0


def test_missing_door_state_is_insufficient_observability() -> None:
    d = run(exp("open door to hallway"))
    (a,) = d.attempts
    assert a.actions == ("close door to hallway",) and a.executed
    assert INSUFFICIENT_OBSERVABILITY in a.outcomes
    assert any("absent from the object tree" in i for i in a.observability_issues)
    assert any("look() text" in i for i in a.observability_issues)
    assert a.comparison(DISCRETE).outcome == OBSERVED_FIELDS_MATCH  # current room only
    assert any("door states of every room except" in u for u in d.unobservable)


def test_counterfactual_unavailable_when_idle_action_is_invalid() -> None:
    (a,) = run(exp("open cupboard", idle_action="look at unicorn")).attempts
    assert a.counterfactual_note.startswith("counterfactual unavailable")
    assert not any(c.mode.startswith("counterfactual") for c in a.comparisons)


# -- structural matching -----------------------------------------------------------------
def _state(objects: dict[str, dict[str, Any]]) -> CanonicalState:
    return CanonicalState(objects=objects, world={"moves": 0}, visible_doors={})


def _rec(name: str, parent: str | None, temp: float = 10.0) -> dict[str, Any]:
    return {"parent": parent, "path": name, "name": name, "propMaterial.temperatureC": temp}


def test_move_and_return_needs_no_structural_matching() -> None:
    (a,) = run(exp("pick up apple")).attempts
    loc, _ = a.structural
    assert loc.all_objects_accounted and not loc.matches and loc.n_uuid_identity > 10


def test_recreated_object_gets_a_structural_match_but_keeps_both_uuids() -> None:
    before = _state({"1": _rec("pot", None), "2": _rec("water", "1", 10.0)})
    after = _state({"1": _rec("pot", None), "9": _rec("water", "1", 12.5)})
    rep = structural_match(before, after)
    (m,) = rep.matches
    assert (m.uuid_before, m.uuid_after) == ("2", "9")
    assert [c.key.split(":")[1] for c in m.ignored_differences] == ["propMaterial.temperatureC"]
    plain = canonical_diff(before, after)  # canonical contract R1 unchanged: uuid identity
    assert plain.deleted_objects == (("2", "water"),) and plain.created_objects == (("9", "water"),)


def test_ambiguous_structural_matches_are_reported_not_forced() -> None:
    before = _state({"1": _rec("sewer", None), "2": _rec("water", "1")})
    after = _state({"1": _rec("sewer", None), "8": _rec("water", "1"), "9": _rec("water", "1")})
    rep = structural_match(before, after)
    assert rep.matches == ()
    (g,) = rep.ambiguous
    assert g.uuids_before == ("2",) and g.uuids_after == ("8", "9")
    assert not rep.all_objects_accounted
    assert rep.indistinguishable_after[0].uuids_before == ("8", "9")


def test_location_sensitivity_prevents_cross_container_matches() -> None:
    before = _state({"1": _rec("pot", None), "5": _rec("cup", None), "2": _rec("water", "1")})
    after = _state({"1": _rec("pot", None), "5": _rec("cup", None), "9": _rec("water", "5")})
    assert structural_match(before, after).matches == ()
    loose = structural_match(before, after, location_sensitive=False)
    assert [(m.uuid_before, m.uuid_after) for m in loose.matches] == [("2", "9")]


def test_mixing_then_refill_matches_water_only_and_never_the_salt() -> None:
    salty = BASE.extend("open cupboard", "pour glass jar into metal pot",
                        "move metal pot to sink", "activate sink", "deactivate sink")  # fmt: skip
    d = run(exp("mix metal pot", salty, explicit_paths=(SINK_CYCLE,)))
    assert not d.proposals and d.n_paths_proposed == 1  # no registry rule for mix
    (a,) = d.attempts
    loc, loose = a.structural
    assert {m.name for m in loc.matches} == {"water", "terminal 1", "terminal 2"}
    assert ("8", "sodium chloride") in loc.unmatched_before
    assert "salt water" in {n for _, n in loc.unmatched_after}
    assert loose.ambiguous  # without locations the two new waters are indistinguishable
    assert a.comparison(DISCRETE).outcome == OBSERVED_FIELDS_DIFFER


def test_structural_matching_preserves_raw_ids_and_states() -> None:
    raw = RawState({"uuid": 1, "name": "u", "contents": {"w": {"uuid": 2, "name": "water"}}},
                   "", "", 0, ())  # fmt: skip
    c = canonicalize(raw)
    fp = (raw.fingerprint, c.fingerprint)
    structural_match(c, c)
    assert (raw.fingerprint, c.fingerprint) == fp and set(c.objects) == {"1", "2"}


# -- divergence, cleanup, no labels ----------------------------------------------------------
def test_reconstruction_divergence_is_detected_and_sessions_close() -> None:
    created: list[MiniKitchen] = []
    with pytest.raises(ReplayDivergenceError, match="S0 reconstruction"):
        run(exp("open cupboard"), created, knobs={"noise": 0.5})
    assert created and all(k.closed for k in created)


def test_divergence_when_rebuilding_s1_for_a_second_path() -> None:
    created: list[MiniKitchen] = []
    with pytest.raises(ReplayDivergenceError, match="S1 reconstruction"):
        run(exp("open cupboard", explicit_paths=(SINK_CYCLE,)), created,
            knobs={"noise": 0.5}, verify_reconstruction=False)  # fmt: skip
    assert all(k.closed for k in created)


def test_session_closes_after_an_error_inside_a_candidate_path() -> None:
    created: list[MiniKitchen] = []
    with pytest.raises(RuntimeError, match="injected failure"):
        run(exp("open cupboard"), created, knobs={"fail_on": "close cupboard"})
    assert len(created) == 2 and all(k.closed for k in created)


LABEL_WORDS = {"reversible", "irreversible", "partially_reversible"}
LABEL_KEYS = {"label", "labels_by_horizon", "restore_depth", "approx_restore_depth"}


def _walk(obj: Any):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield ("key", k)
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)
    else:
        yield ("value", obj)


@pytest.mark.parametrize(
    "experiment",
    [
        exp("open cupboard"),
        exp("activate sink"),
        exp("open door to hallway"),
        exp("eat apple"),
        exp("pick up apple"),
    ],
    ids=lambda e: e.target_action,
)
def test_no_gold_label_is_ever_produced(experiment: InverseExperiment) -> None:
    out = run(experiment).to_dict()
    json.dumps(out)  # serialisable
    for kind, item in _walk(out):
        if kind == "key":
            assert item not in LABEL_KEYS
        elif isinstance(item, str):
            assert item.lower() not in LABEL_WORDS
    assert not LABEL_WORDS & set(OUTCOMES)
    assert out["label_policy"].startswith("diagnostic only")


# -- shared plumbing -------------------------------------------------------------------------
def test_valid_action_templates_are_free_and_use_string_ids() -> None:
    with ScienceWorldSession(backend_factory=MiniKitchen) as s:
        initial, steps, t_loaded = run_recipe(s, BASE)
        moves = s.moves()
        templates = s.valid_action_templates()
        assert s.moves() == moves == 2 and isinstance(t_loaded, float) and len(steps) == 1
    door = next(t for t in templates if t.action == "open door to hallway")
    assert door.obj_ids == ("90",) and "90" not in initial.canonical.objects


def test_phase4d_experiment_set_is_well_formed() -> None:
    exps = phase4d_experiments()
    assert len({e.experiment_id for e in exps}) == len(exps) == 11
    for e in exps:
        assert not EXCLUDED_RESTORATION.match(e.target_action)
        assert e.recipe.preparation == ("wait1",) and e.recipe.task == "1-1"
