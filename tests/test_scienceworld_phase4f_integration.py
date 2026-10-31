"""Optional Phase 4F integration tests on the pinned simulator (docs/22 §8).

Skipped unless the isolated runtime is configured (same variables as
``test_scienceworld_integration.py``). They measure query-order effects, build one
targeted contrast and run a tiny expanded search. No labels are produced or checked.
"""

from __future__ import annotations

import pytest

from adnn.scienceworld import (
    RuntimeConfig,
    ScienceWorldUnavailableError,
    UnpinnedRuntimeError,
    resolve_runtime,
)
from adnn.scienceworld.contrasts import build_contrast, contrast_specs, validate_contrast_pair
from adnn.scienceworld.expanded_search import expanded_search
from adnn.scienceworld.query_audit import AuditScenario, audit_scenario
from adnn.scienceworld.replay import FIRST_TICK_PREPARATION, ReplayRecipe
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


def _rows(scenario: AuditScenario) -> dict[str, dict]:
    audit = audit_scenario(scenario, repeats=1, shared=False, config=CONFIG)
    return {r["condition"]: r for r in audit.summary()["comparisons"]}


def test_deterministic_kitchen_is_query_order_independent() -> None:
    scenario = AuditScenario(
        "kitchen-short", "1-1", 0, ("teleport to kitchen", "open cupboard", "activate sink")
    )
    rows = _rows(scenario)
    assert all(r["transitions_equal_all_k"] for r in rows.values())


def test_enumeration_changes_bee_transitions() -> None:
    """Measured effect (docs/22 §2): valid-action enumeration consumes global randomness."""
    scenario = AuditScenario(
        "bees-short", "5-1", 0,
        ("teleport to greenhouse", "open bee hive", "look at agent"), stochastic=True,
    )  # fmt: skip
    rows = _rows(scenario)
    assert rows["B_observe"]["transitions_equal_all_k"]
    assert not rows["C_enumerate"]["stochastic_equal_all_k"]


def test_source_contrast_builds_and_validates() -> None:
    spec = next(s for s in contrast_specs() if s.contrast_id == "location-stove-metal_pot")
    pair, recs, failure = build_contrast(spec, runtime=CONFIG)
    assert failure is None and len(recs) == 2
    assert validate_contrast_pair(pair) == []
    assert pair["checks"]["byte_identical_target"] and pair["checks"]["valid_in_both"]
    assert pair["gold_status"] == "not_a_gold_minimal_pair"


def test_expanded_search_close_freezer_control() -> None:
    recipe = ReplayRecipe(task="3-1", variation=0, simplifications="teleportAction",
                          preparation=FIRST_TICK_PREPARATION,
                          actions=("teleport to workshop", "open freezer"))  # fmt: skip
    out = expanded_search(recipe, "close freezer", max_candidates=6, config=CONFIG)
    assert out["target_status"] == "accepted" and out["restricted"]
    assert out["branching"]["valid_actions"] >= out["branching"]["object_local"]
    assert java_process_count() == 0
