"""Phase 4E provisional evidence records, candidate pairs and validation (no Java; docs/21)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from adnn.dataset.schema import ALL_FIELDS as GOLD_FIELDS
from adnn.scienceworld.canonical import CanonicalState
from adnn.scienceworld.diagnostics import (
    TEMPERATURE_TOLERANCE_001,
    TEMPERATURE_TOLERANCE_01,
    canonical_diff,
    projection_diff,
)
from adnn.scienceworld.provisional import (
    EV_MATCH_001,
    EV_MATCH_01,
    EV_MATCH_EXACT,
    EV_MISMATCH,
    EV_NO_CANDIDATE,
    EV_NOT_EXECUTED,
    EVIDENCE_STATUSES,
    MODE_EXACT,
    MODE_TOL_001,
    MODE_TOL_01,
    RECORD_FIELDS,
    SCIENTIFIC_STATUS,
    FamilySpec,
    content_sha256,
    discover_candidate_pairs,
    door_exclusion_reason,
    evidence_status,
    example_id,
    leakage_problems,
    load_state_file,
    match_level,
    validate_dataset,
    verb_class,
)
from adnn.scienceworld.provisional_sampling import (
    SamplerConfig,
    collect_evidence,
    explicit_example,
    run_pilot,
    sample_rng,
    unambiguous_templates,
)
from adnn.scienceworld.replay import ReplayRecipe
from scienceworld_restoration_fake import MiniKitchen

FAKE = FamilySpec("fake-kitchen", "1-1", 0, "")
CONFIG = SamplerConfig(seed=7, families=(FAKE,), base_samples_per_family=6)


@pytest.fixture(scope="module")
def pilot(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any]:
    out = tmp_path_factory.mktemp("pilot")
    return out, run_pilot(out, CONFIG, backend_factory=MiniKitchen)


@pytest.fixture(scope="module")
def sink_pair(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, Any]]]:
    """Same text 'activate sink'; the bowl is in the sink in one state only."""
    out = tmp_path_factory.mktemp("pair")
    (out / "states").mkdir()
    records = []
    for prefix in ((), ("move bowl to sink",)):
        ex = explicit_example(FAKE, prefix, "activate sink", backend_factory=MiniKitchen)
        record, state_bytes, _ = collect_evidence(ex, backend_factory=MiniKitchen)
        (out / record["state_provenance"]["state_file"]).write_bytes(state_bytes)
        records.append(record)
    return out, records


def _state(temps: dict[str, float]) -> CanonicalState:
    return CanonicalState(
        objects={u: {"name": f"o{u}", "propMaterial.temperatureC": t} for u, t in temps.items()},
        world={"moves": 3, "agent_location": "kitchen"},
        visible_doors={},
    )


# -- RD-02 temperature sensitivity -----------------------------------------------------------
@pytest.mark.parametrize(
    ("delta", "exact", "tol001", "tol01"),
    [(0.0, True, True, True), (0.005, False, True, True), (0.05, False, False, True),
     (0.5, False, False, False)],
)  # fmt: skip
def test_temperature_comparisons_never_drop_temperature(delta, exact, tol001, tol01) -> None:
    a, b = _state({"1": 20.0}), _state({"1": 20.0 + delta})
    assert canonical_diff(a, b).equal_on_observed_fields is exact
    d1 = projection_diff(a, b, TEMPERATURE_TOLERANCE_001)
    d2 = projection_diff(a, b, TEMPERATURE_TOLERANCE_01)
    assert d1.equal_on_observed_fields is tol001
    assert d2.equal_on_observed_fields is tol01
    assert TEMPERATURE_TOLERANCE_001.ignore == TEMPERATURE_TOLERANCE_01.ignore == ()
    # a within-tolerance difference is counted, never hidden
    assert d1.n_within_tolerance + len(d1.changes) == (delta != 0)


def test_tolerance_does_not_excuse_moves_or_discrete_fields() -> None:
    a = _state({"1": 20.0})
    b = CanonicalState({"1": {"name": "o1", "propMaterial.temperatureC": 20.0}},
                       {"moves": 4, "agent_location": "kitchen"}, {})  # fmt: skip
    assert not projection_diff(a, b, TEMPERATURE_TOLERANCE_01).equal_on_observed_fields


# -- RD-03 / RD-04 evidence ladder -------------------------------------------------------------
def _attempt(executed: bool, equal: dict[str, bool]) -> Any:
    comps = tuple(
        SimpleNamespace(mode=m, diff=SimpleNamespace(equal_on_observed_fields=e))
        for m, e in equal.items()
    )
    return SimpleNamespace(executed=executed, comparisons=comps)


def _diag(*attempts: Any, proposed: int | None = None, status: str = "accepted") -> Any:
    n = len(attempts) if proposed is None else proposed
    return SimpleNamespace(target_status=status, attempts=attempts, n_paths_proposed=n)


def test_match_level_ladder() -> None:
    every = {MODE_EXACT: True, MODE_TOL_001: True, MODE_TOL_01: True}
    assert match_level(_attempt(True, every)) == "exact"
    assert match_level(_attempt(True, every | {MODE_EXACT: False})) == "within_0.01C"
    assert match_level(
        _attempt(True, {MODE_EXACT: False, MODE_TOL_001: False, MODE_TOL_01: True})
    ) == ("within_0.1C")
    assert match_level(_attempt(True, dict.fromkeys(every, False))) == "none"
    assert match_level(_attempt(False, every)) == "not_compared"
    assert match_level(_attempt(True, {"literal_canonical": True})) == "not_compared"


def test_evidence_status_is_neutral_and_failed_search_is_not_irreversible() -> None:
    every = {MODE_EXACT: True, MODE_TOL_001: True, MODE_TOL_01: True}
    no = dict.fromkeys(every, False)
    assert evidence_status(_diag(proposed=0))[0] == EV_NO_CANDIDATE
    assert evidence_status(_diag(_attempt(False, every)))[0] == EV_NOT_EXECUTED
    assert evidence_status(_diag(_attempt(True, no)))[0] == EV_MISMATCH
    assert evidence_status(_diag(_attempt(True, no), _attempt(True, every)))[0] == EV_MATCH_EXACT
    assert evidence_status(_diag(_attempt(True, every | {MODE_EXACT: False})))[0] == EV_MATCH_001
    assert evidence_status(_diag(_attempt(True, no | {MODE_TOL_01: True})))[0] == EV_MATCH_01
    for s in EVIDENCE_STATUSES:
        assert not leakage_problems({"evidence_status": s})
        assert not {"reversible", "irreversible", "partial", "undetermined"} & set(s.split("_"))


# -- sampling helpers ------------------------------------------------------------------------
def test_verb_classes_and_door_exclusion() -> None:
    state = _state({"5": 10.0})
    assert verb_class("open cupboard") == "open_close"
    assert verb_class("pick up apple") == "pick_up"
    assert verb_class("focus on apple") is None
    assert verb_class("teleport to kitchen") is None
    assert door_exclusion_reason("open door to hallway", ("5",), state) is not None
    assert door_exclusion_reason("close drain to sewer", ("90",), state) is not None  # portal uuid
    assert door_exclusion_reason("open cupboard", ("5",), state) is None


def test_ids_and_rng_are_deterministic() -> None:
    r = ReplayRecipe("1-1", 0, "", preparation=("wait1",))
    assert example_id(r, "open cupboard") == example_id(r, "open cupboard")
    assert example_id(r, "open cupboard") != example_id(r, "close cupboard")
    assert example_id(r, "open cupboard") != example_id(r.extend("activate sink"), "open cupboard")
    assert sample_rng(1, "f", 2).random() == sample_rng(1, "f", 2).random()
    assert sample_rng(1, "f", 2).random() != sample_rng(1, "f", 3).random()


def test_ambiguous_action_text_is_never_sampled() -> None:
    from adnn.scienceworld.env import ActionTemplate

    ts = [ActionTemplate("move cup to table", 9, ("1", "9")),
          ActionTemplate("move cup to table", 9, ("2", "9")),
          ActionTemplate("open cupboard", 0, ("5",))]  # fmt: skip
    single, n_ambiguous = unambiguous_templates(ts)
    assert set(single) == {"open cupboard"}
    assert n_ambiguous == 1


# -- pipeline on the fake kitchen --------------------------------------------------------------
def test_pilot_records_validate_and_carry_no_labels(pilot) -> None:
    out, res = pilot
    assert res.records and res.summary["validation_ok"]
    report = json.loads((out / "validation.json").read_text("utf-8"))
    assert report["ok"] and all(c["passed"] for c in report["checks"].values())
    for r in res.records:
        assert tuple(r) == RECORD_FIELDS or set(r) == set(RECORD_FIELDS)
        assert not set(r) & set(GOLD_FIELDS)
        assert not leakage_problems(r)
        assert r["scientific_status"] == SCIENTIFIC_STATUS
        assert r["scientific_status"]["professor_approved"] is False
        assert r["restoration_evidence"]["primary_method"] == "time_matched_counterfactual"
        assert r["restoration_evidence"]["candidate_set"]["exhaustive"] is False
        assert r["observation_completeness"]["complete"] is False


def test_pilot_histories_are_agent_valid_and_researcher_reset_is_not_an_action(pilot) -> None:
    _, res = pilot
    for r in res.records:
        hist = r["action_history"]
        assert hist[0]["action"] == "wait1" and hist[0]["phase"] == "preparation"
        assert all(h["status"] == "accepted" and h["counts_as_agent_action"] for h in hist)
        assert not any("reset" in h["action"] or "load" in h["action"] for h in hist)
        assert [op["counts_as_agent_action"] for op in r["researcher_operations"]] == [False]
        assert r["elapsed_ticks"]["history_ticks"] == r["pre_action_state"]["moves"]
        assert r["target"]["valid_in_state"] and r["target"]["n_templates_with_text"] == 1
        assert "door" not in r["target"]["action"]
        assert r["replay_verification"]["verified"]


def test_pilot_has_no_duplicate_state_actions(pilot) -> None:
    _, res = pilot
    keys = [
        (r["pre_action_state"]["discrete_fingerprint"], r["target"]["action"]) for r in res.records
    ]
    assert len(keys) == len(set(keys))
    assert len({r["example_id"] for r in res.records}) == len(res.records)


def test_siblings_reuse_byte_identical_target(pilot) -> None:
    _, res = pilot
    by_id = {r["example_id"]: r for r in res.records}
    siblings = [r for r in res.records if r["sampling"]["role"] == "sibling"]
    assert siblings
    for s in siblings:
        base = by_id[s["sampling"]["sibling_of"]]
        assert s["target"]["action"] == base["target"]["action"]
        assert s["target"]["obj_ids"] == base["target"]["obj_ids"]
        assert s["replay_recipe"]["actions"][:-1] == base["replay_recipe"]["actions"]
        assert s["replay_recipe"]["actions"][-1] == s["sampling"]["contrast_action"]


def test_regeneration_is_byte_identical(pilot, tmp_path: Path) -> None:
    out, _ = pilot
    run_pilot(tmp_path, CONFIG, backend_factory=MiniKitchen)
    for name in ("records.jsonl", "candidate_pairs.jsonl", "rejections.jsonl"):
        assert (out / name).read_bytes() == (tmp_path / name).read_bytes(), name


def test_different_seed_gives_different_sample(pilot, tmp_path: Path) -> None:
    _, res = pilot
    other = run_pilot(tmp_path, SamplerConfig(seed=8, families=(FAKE,), base_samples_per_family=6),
                      backend_factory=MiniKitchen)  # fmt: skip
    assert {r["example_id"] for r in other.records} != {r["example_id"] for r in res.records}


# -- candidate minimal pairs -----------------------------------------------------------------
def test_sink_minimal_pair_is_discovered(sink_pair) -> None:
    root, records = sink_pair
    pairs, stats = discover_candidate_pairs(records, load_state_file(root))
    assert stats.n_candidates == 1
    (p,) = pairs
    assert p["action_text"] == "activate sink" and p["status"] == "candidate_unvalidated"
    assert p["validated"] is False
    assert p["state_difference"]["n_discrete_changes"] > 0
    assert p["consequence_difference"]
    assert validate_dataset(records, pairs, root=root).ok


def test_pair_rules_reject_same_state_same_consequence_and_ambiguity(sink_pair) -> None:
    root, records = sink_pair
    same = load_state_file(root)(records[0])
    _, stats = discover_candidate_pairs(records, lambda _r: same)
    assert stats.rejected == {"no_discrete_state_difference": 1}

    a, b = copy.deepcopy(records)
    b["restoration_evidence"] = a["restoration_evidence"]
    b["target"]["observed_effect"] = a["target"]["observed_effect"]
    _, stats = discover_candidate_pairs([a, b], load_state_file(root))
    assert stats.rejected == {"same_consequences": 1}

    a, b = copy.deepcopy(records)
    b["target"]["obj_ids"] = ["999"]
    _, stats = discover_candidate_pairs([a, b], load_state_file(root))
    assert stats.rejected == {"reference_ambiguity": 1}

    a, b = copy.deepcopy(records)
    b["replay_verification"]["verified"] = False
    _, stats = discover_candidate_pairs([a, b], load_state_file(root))
    assert stats.rejected == {"replay_not_verified": 1}


# -- validator catches every class of defect --------------------------------------------------
def _resign(r: dict[str, Any]) -> dict[str, Any]:
    r["content_sha256"] = content_sha256(r)
    return r


MUTATIONS = {
    "no_label_leakage": lambda r: r.update(label="reversible"),
    "no_label_leakage ": lambda r: r["target"].update(note="irreversible"),
    "no_label_leakage  ": lambda r: r["target"].update(score=100),
    "scientific_status": lambda r: r["scientific_status"].update(professor_approved=True),
    "restricted_search_disclosure": lambda r: r["restoration_evidence"]["candidate_set"].update(
        exhaustive=True
    ),
    "missing_state_disclosure": lambda r: r["observation_completeness"].update(complete=True),
    "door_exclusion": lambda r: r["target"].update(obj_ids_in_object_tree=False),
    "action_validity": lambda r: r["action_history"][0].update(status="invalid"),
    "action_validity ": lambda r: r["researcher_operations"][0].update(counts_as_agent_action=True),
    "replay_verification": lambda r: r["replay_verification"].update(verified=False),
    "provenance": lambda r: r["provenance"]["simulator"].update(source_commit="0" * 40),
    "state_files": lambda r: r["state_provenance"].update(state_file_sha256="0" * 64),
    "schema_integrity": lambda r: r["restoration_evidence"].update(evidence_status="reversible"),
}


@pytest.mark.parametrize("check", sorted(MUTATIONS))
def test_validator_detects_mutation(sink_pair, check: str) -> None:
    root, records = sink_pair
    bad = copy.deepcopy(records[0])
    MUTATIONS[check](bad)
    _resign(bad)
    report = validate_dataset([bad], [], root=root)
    assert report.errors[check.strip()], report.to_dict()


def test_validator_detects_checksum_duplicates_and_unknown_fields(sink_pair) -> None:
    root, records = sink_pair
    tampered = copy.deepcopy(records[0])
    tampered["target"]["observation"] = "edited"
    assert validate_dataset([tampered], [], root=root).errors["content_checksums"]
    assert validate_dataset([records[0], records[0]], [], root=root).errors["unique_ids"]
    assert validate_dataset([records[0], records[0]], [], root=root).errors["duplicates"]
    extra = _resign({**copy.deepcopy(records[0]), "horizon": 3})
    assert validate_dataset([extra], [], root=root).errors["schema_integrity"]


def test_validator_detects_bad_pairs(sink_pair) -> None:
    root, records = sink_pair
    pairs, _ = discover_candidate_pairs(records, load_state_file(root))
    claims = copy.deepcopy(pairs[0])
    claims["validated"] = True
    assert validate_dataset(records, [_resign(claims)], root=root).errors["candidate_pairs"]
    wrong = copy.deepcopy(pairs[0])
    wrong["consequence_difference"] = {"evidence_status": ["x", "y"]}
    assert validate_dataset(records, [_resign(wrong)], root=root).errors["candidate_pairs"]
    orphan = copy.deepcopy(pairs[0])
    assert validate_dataset(records[:1], [orphan], root=root).errors["candidate_pairs"]


def test_explicit_example_rejects_doors_and_no_effect_history() -> None:
    with pytest.raises(ValueError, match=r"RD-05|not a valid"):
        explicit_example(FAKE, (), "open door to hallway", backend_factory=MiniKitchen)
    with pytest.raises(ValueError, match="rejected"):
        explicit_example(FAKE, ("look at apple",), "open cupboard", backend_factory=MiniKitchen)
