"""Optional restoration-diagnostic integration tests on the pinned simulator (docs/19 §8).

Skipped unless the isolated runtime is configured (same variables as
``test_scienceworld_integration.py``). They check diagnostic behaviour only and
never produce or check reversibility labels.
"""

from __future__ import annotations

import pytest

from adnn.scienceworld import (
    RuntimeConfig,
    ScienceWorldUnavailableError,
    UnpinnedRuntimeError,
    phase4d_experiments,
    resolve_runtime,
    run_inverse_experiment,
)
from adnn.scienceworld.restoration_diagnostics import (
    INSUFFICIENT_OBSERVABILITY,
    NO_CANDIDATE_PATH_FOUND,
    OBSERVED_FIELDS_DIFFER,
    OBSERVED_FIELDS_MATCH,
)
from test_scienceworld_integration import java_process_count

CONFIG = RuntimeConfig.from_env()
try:
    resolve_runtime(CONFIG)
    SKIP_REASON = ""
except (ScienceWorldUnavailableError, UnpinnedRuntimeError) as exc:
    SKIP_REASON = f"pinned ScienceWorld runtime not available: {exc}"

pytestmark = [
    pytest.mark.scienceworld,
    pytest.mark.skipif(bool(SKIP_REASON), reason=SKIP_REASON or "runtime unavailable"),
]

EXPERIMENTS = {e.experiment_id: e for e in phase4d_experiments()}
DISCRETE = "literal_projection:discrete-exploration-v1"


def run(experiment_id: str):
    return run_inverse_experiment(EXPERIMENTS[experiment_id], config=CONFIG)


def test_container_toggle_matches_counterfactual_exactly_but_not_literally() -> None:
    (a,) = run("E01-container-open").attempts
    assert a.actions == ("close cupboard",) and a.executed and a.ticks_target + a.ticks_path == 2
    assert a.comparison("literal_canonical").outcome == OBSERVED_FIELDS_DIFFER
    assert a.comparison("literal_canonical").n_temperature_changes > 50
    assert a.comparison(DISCRETE).outcome == OBSERVED_FIELDS_MATCH
    assert a.comparison("counterfactual_canonical").outcome == OBSERVED_FIELDS_MATCH


def test_sink_deactivation_leaves_created_water() -> None:
    (a,) = run("E04-device-sink").attempts
    assert a.actions == ("deactivate sink",)
    assert "water" in {n for _, n in a.comparison(DISCRETE).diff.created_objects}
    assert a.comparison("counterfactual_canonical").outcome == OBSERVED_FIELDS_DIFFER


def test_door_restoration_is_insufficiently_observable() -> None:
    d = run("E05-door")
    (a,) = d.attempts
    assert INSUFFICIENT_OBSERVABILITY in a.outcomes
    assert a.comparison(DISCRETE).outcome == OBSERVED_FIELDS_MATCH
    assert not a.comparison(DISCRETE).diff.supports_exact_equality_claim
    assert any("absent from the object tree" in i for i in a.observability_issues)
    assert any("look() text" in i for i in a.observability_issues)


def test_pour_back_restores_discrete_fields_with_a_thermal_trace() -> None:
    (a,) = run("E08-pour-back").attempts
    assert a.actions == ("pour ceramic cup into glass jar",)
    assert a.comparison(DISCRETE).outcome == OBSERVED_FIELDS_MATCH
    cf = a.comparison("counterfactual_canonical")
    assert cf.outcome == OBSERVED_FIELDS_DIFFER  # tiny residual heat exchange differences
    assert 0 < cf.max_abs_temperature_delta < 0.01
    assert all(c.key.endswith("temperatureC") for c in cf.diff.changes)


def test_mixing_refill_gives_structural_water_match_and_no_salt_match() -> None:
    d = run("E10-mix")
    assert not d.proposals  # no registry rule for mixing
    (a,) = d.attempts
    loc, loose = a.structural
    assert "water" in {m.name for m in loc.matches}
    assert "sodium chloride" in {n for _, n in loc.unmatched_before}
    assert "salt water" in {n for _, n in loc.unmatched_after}
    assert any(g.name == "water" and len(g.uuids_after) == 2 for g in loose.ambiguous)


def test_eating_has_no_candidate_and_no_label() -> None:
    d = run("E11-eat")
    assert d.outcomes == (NO_CANDIDATE_PATH_FOUND,)
    out = d.to_dict()
    assert out["candidate_set"]["exhaustive"] is False and "label" not in out
    assert "banana" in {n for _, n in d.target_effect.deleted_objects}


def test_diagnostics_are_reproducible_and_leave_no_jvm() -> None:
    before = java_process_count()
    a, b = run("E06-move-return"), run("E06-move-return")
    strip = [x.to_dict() for x in (a, b)]
    for s in strip:
        s.pop("provenance")
    assert strip[0] == strip[1]
    if before is not None:
        assert java_process_count() == before
