"""Optional Phase 4E integration tests on the pinned simulator (docs/21 §9).

Skipped unless the isolated runtime is configured (same variables as
``test_scienceworld_integration.py``). They build provisional evidence only and
never produce or check reversibility labels.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from adnn.scienceworld import (
    RuntimeConfig,
    ScienceWorldUnavailableError,
    UnpinnedRuntimeError,
    replay,
    resolve_runtime,
)
from adnn.scienceworld.provisional import (
    PILOT_FAMILIES,
    discover_candidate_pairs,
    leakage_problems,
    load_state_file,
    validate_dataset,
)
from adnn.scienceworld.provisional_sampling import (
    SamplerConfig,
    collect_evidence,
    explicit_example,
    run_pilot,
)
from adnn.scienceworld.replay import ReplayRecipe
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

KITCHEN = PILOT_FAMILIES[0]


@pytest.fixture(scope="module")
def small_pilot(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any]:
    out = tmp_path_factory.mktemp("sw-pilot")
    config = SamplerConfig(families=(KITCHEN,), base_samples_per_family=2, sibling_rate=1.0)
    return out, run_pilot(out, config, runtime=CONFIG)


def test_small_pilot_validates_without_labels(small_pilot) -> None:
    out, res = small_pilot
    assert res.records, res.summary["rejections"]
    assert res.summary["validation_ok"]
    assert validate_dataset(res.records, res.pairs, root=out).ok
    for r in res.records:
        assert not leakage_problems(r)
        assert r["scientific_status"]["professor_approved"] is False
        assert r["replay_recipe"]["simulator"]["source_commit"].startswith("e8216d6")


def test_recorded_s0_replays_in_a_fresh_simulator(small_pilot) -> None:
    _, res = small_pilot
    r = res.records[0]
    again = replay(ReplayRecipe.from_dict(r["replay_recipe"]), config=CONFIG)
    assert again.final.raw.fingerprint == r["pre_action_state"]["raw_fingerprint"]
    assert again.final.canonical.fingerprint == r["pre_action_state"]["canonical_fingerprint"]


def test_temperature_comparisons_are_all_present(small_pilot) -> None:
    _, res = small_pilot
    executed = [
        a for r in res.records for a in r["restoration_evidence"]["attempts"] if a["executed"]
    ]
    for a in executed:
        if a["counterfactual"]["available"]:
            modes = set(a["comparisons"])
            assert {"counterfactual_canonical",
                    "counterfactual_projection:temperature-tolerance-0.01C-v1",
                    "counterfactual_projection:temperature-tolerance-0.1C-v1"} <= modes  # fmt: skip
            for m in sorted(x for x in modes if not x.endswith(":discrete-exploration-v1")):
                assert "propMaterial.temperatureC" not in a["comparisons"][m]["ignored_patterns"]


def test_sink_candidate_pair_on_pinned_simulator(tmp_path: Path) -> None:
    """Same 'activate sink' text; the metal pot is in the sink in one state only (cf. E04)."""
    (tmp_path / "states").mkdir()
    records = []
    for prefix in ((), ("open cupboard", "move metal pot to sink")):
        ex = explicit_example(KITCHEN, prefix, "activate sink", runtime=CONFIG)
        record, state_bytes, _ = collect_evidence(ex, runtime=CONFIG)
        (tmp_path / record["state_provenance"]["state_file"]).write_bytes(state_bytes)
        records.append(record)
    pairs, stats = discover_candidate_pairs(records, load_state_file(tmp_path))
    assert stats.n_candidates == 1, stats.to_dict()
    assert pairs[0]["status"] == "candidate_unvalidated"
    assert validate_dataset(records, pairs, root=tmp_path).ok


def test_no_java_process_leaks() -> None:
    assert java_process_count() == 0
