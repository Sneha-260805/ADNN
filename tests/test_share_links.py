"""Phase 5D Candidate A: sharing-link mechanism (share-links-spec-1.0; docs/29). No Java."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from adnn.feasibility import share_link_diagnostics as sl
from adnn.sandbox import TOOL_SPECS, SandboxConfig, WorldState, canonical_hash, full_hash
from adnn.sandbox.restoration import (
    argument_pool,
    assess_reversibility,
    candidate_calls,
    core_hash,
    core_projection,
)
from adnn.sandbox.state import (
    AGENT_TOOL_NAMES,
    EXTENSION_TOOL_NAMES,
    FileRecord,
    InvalidStateError,
    validate_state,
)
from adnn.sandbox.tools import ErrorCode, ToolCall, generated_address, step

F1 = sl.F1
NO_CREATE = tuple(t for t in sl.ALL_TOOL_NAMES if t != "create_share_link")


def case(cid: str) -> sl.Case:
    return {c.case_id: c for c in sl.cases()}[cid]


# -- legacy isolation -------------------------------------------------------------------------
def test_extension_tools_are_not_in_the_legacy_registry_or_default_permissions() -> None:
    assert tuple(TOOL_SPECS) == AGENT_TOOL_NAMES
    assert not set(EXTENSION_TOOL_NAMES) & set(SandboxConfig().permitted_tools)
    s = WorldState(files=(FileRecord(F1, "x"),))
    _, res = step(s, {"tool": "revoke_share_link", "args": {"link_id": "lnk-0001"}})
    assert not res.ok and res.error_code is ErrorCode.PERMISSION_DENIED


def test_legacy_states_serialise_and_project_without_links() -> None:
    s = WorldState(files=(FileRecord(F1, "x"),))
    assert "share_links" not in s.to_dict()
    assert "share_links" not in core_projection(s)
    pool = argument_pool(s, ToolCall("delete_file", {"path": F1}))
    assert pool.addresses == ()
    assert not any(c.tool in EXTENSION_TOOL_NAMES for c in candidate_calls(s, pool))


def test_empty_strings_still_rejected_for_legacy_parameters() -> None:
    s = WorldState(files=(FileRecord(F1, "x"),))
    _, res = step(s, {"tool": "edit_file", "args": {"path": F1, "content": ""}})
    assert not res.ok and res.error_code is ErrorCode.INVALID_ARGUMENTS


def test_round_trip_and_invariants() -> None:
    s = case("D5").state
    assert WorldState.from_dict(s.to_dict()) == s
    validate_state(s)
    dup = WorldState(
        config=s.config,
        files=s.files,
        share_links=(sl.custom("lnk-0001", F1, "view"), sl.custom("lnk-0002", F1, "edit")),
    )
    with pytest.raises(InvalidStateError, match="active link addresses"):
        validate_state(dup)


# -- semantics ----------------------------------------------------------------------------------
def test_generated_tokens_are_reserved_and_custom_addresses_held_per_file() -> None:
    s = sl.world((sl.generated("lnk-0001", F1, "view", active=False),))
    reserved = {"path": F1, "access": "view", "address": generated_address("lnk-0001")}
    _, res = step(s, {"tool": "create_share_link", "args": reserved})
    assert not res.ok and res.error_code is ErrorCode.ALREADY_EXISTS
    held = sl.world((replace(sl.custom("lnk-0001", F1, "view"), active=False),))
    other = {"path": sl.F2, "access": "view", "address": "q3-board"}
    _, res = step(held, {"tool": "create_share_link", "args": other})
    assert not res.ok and res.error_code is ErrorCode.ALREADY_EXISTS


# -- exact vs functional restoration ------------------------------------------------------------
def test_custom_link_restores_exactly_by_reactivation() -> None:
    c = case("D1")
    a = assess_reversibility(c.state, c.action)
    assert a.label.value == "reversible" and a.restore_depth == 1
    s1, _ = step(c.state, c.action)
    end, ok = sl.replay(s1, [w.to_dict() for w in a.exact_witness or ()])
    assert ok and canonical_hash(end) == canonical_hash(c.state)


def test_generated_link_restores_only_functionally_with_explicit_url_residual() -> None:
    c = case("D2")
    a = assess_reversibility(c.state, c.action)
    assert a.label.value == "partially_reversible"
    assert a.restore_depth is None and a.approx_restore_depth == 1
    s1, _ = step(c.state, c.action)
    end, ok = sl.replay(s1, [w.to_dict() for w in a.approx_witness or ()])
    assert ok and core_hash(end) == core_hash(c.state)
    assert canonical_hash(end) != canonical_hash(c.state)
    diffs = sl.residual(c.state, end)
    assert "share_links.lnk-0001.active: True -> False" in diffs
    new = next(k for k in end.share_links if k.active)
    assert new.link_id != "lnk-0001" and new.address != c.state.share_links[0].address
    assert sl._address_changed(diffs)


def test_creating_a_link_leaves_an_inactive_record_not_an_address_change() -> None:
    row = sl.run_case(case("D8"))
    assert row["observed"] == "partially_reversible"
    assert row["residual"] and not row["residual_has_address_change"]


@pytest.mark.parametrize("cid", ["D1", "D2"])
def test_inaccessible_recovery_is_irreversible(cid: str) -> None:
    c = case(cid)
    a = assess_reversibility(sl.with_tools(c.state, NO_CREATE), c.action)
    assert a.is_definitive and a.label.value == "irreversible"


# -- frozen predictions, determinism, spec integrity ------------------------------------------
def test_all_frozen_predictions_hold_and_runs_are_deterministic() -> None:
    rows = sl.run_all()
    assert len(rows) <= 12
    assert [r["case"] for r in rows if r["falsified"]] == []
    assert sl.run_all() == rows
    c = case("D5")
    assert full_hash(step(c.state, c.action)[0]) == full_hash(step(c.state, c.action)[0])


def test_spec_hash_is_verified_and_tampering_is_detected(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    assert len(sl.verify_spec(root)) == 64
    for rel in (sl.SPEC_PATH, sl.SPEC_HASH_PATH):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(root / rel, tmp_path / rel)
    with (tmp_path / sl.SPEC_PATH).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("\ntampered\n")
    with pytest.raises(ValueError, match="spec hash mismatch"):
        sl.verify_spec(tmp_path)


# -- Task 3 validation: exact vs core field coverage, OQ-21, residual categories ----------------
def _hashes(links: tuple[sl.ShareLink, ...]) -> tuple[str, str]:
    s = sl.world(links)
    return canonical_hash(s), core_hash(s)


def test_exact_state_covers_every_world_field() -> None:
    from dataclasses import fields

    from adnn.sandbox.state import NON_CANONICAL_FIELDS, canonical_dict

    s = case("D5").state
    expected = {f.name for f in fields(WorldState)} - set(NON_CANONICAL_FIELDS)
    assert set(canonical_dict(s)) == expected


@pytest.mark.parametrize(
    ("field", "value", "core_changes"),
    [
        ("link_id", "lnk-0009", False),  # generated identifier: exact only
        ("address", "gen-ffffffffff", False),  # generated token: exact only
        ("access", "view", True),  # effective permission
        ("path", sl.F2, True),  # target resource
        ("active", False, True),  # effective access withdrawn
        ("custom", True, True),  # user-chosen address becomes part of the core
    ],
)
def test_core_implements_the_frozen_functional_rule_for_generated_links(
    field: str, value: object, core_changes: bool
) -> None:
    base = (sl.custom("lnk-0001", F1, "view"), sl.generated("lnk-0002", F1, "edit"))
    exact0, core0 = _hashes(base)
    mutated = (base[0], replace(base[1], **{field: value}))
    exact1, core1 = _hashes(mutated)
    assert exact1 != exact0
    assert (core1 != core0) is core_changes


def test_custom_address_is_core_and_inactive_records_are_not() -> None:
    exact0, core0 = _hashes((sl.custom("lnk-0001", F1, "view"),))
    assert _hashes((sl.custom("lnk-0001", F1, "view", "other-name"),))[1] != core0
    inactive = sl.generated("lnk-0002", F1, "edit", active=False)
    with_inactive = _hashes((sl.custom("lnk-0001", F1, "view"), inactive))
    changed = _hashes((sl.custom("lnk-0001", F1, "view"), replace(inactive, access="view")))
    assert with_inactive[1] == core0 == changed[1]
    assert len({exact0, with_inactive[0], changed[0]}) == 3


def test_sensitivity_pool_keeps_link_addresses() -> None:
    # regression: extra_contents used to rebuild the pool and drop custom addresses
    c = case("D1")
    a = assess_reversibility(c.state, c.action, extra_contents=("anything",))
    assert a.label.value == "reversible" and a.restore_depth == 1


def test_oq21_alternative_changes_no_label() -> None:
    for c in sl.cases():
        row = sl.run_case(c)
        assert not row["oq21_label_change"], c.case_id


def test_three_diagnostic_categories_are_distinguished() -> None:
    types = {r["case"]: r.get("residual_type") for r in sl.run_all()}
    assert {types[c] for c in ("D1", "D3", "D6")} == {"none"}
    assert {types[c] for c in ("D2", "D4", "D5", "D7")} == {"identity_loss"}
    assert {types[c] for c in ("D8", "D9")} == {"residual_history"}


def test_id_allocation_never_overwrites_an_existing_link() -> None:
    # a hand-built state with an id gap: count + 1 would collide with lnk-0002
    s = sl.world((sl.generated("lnk-0002", F1, "view"),))
    after, res = step(s, {"tool": "create_share_link", "args": {"path": F1, "access": "view",
                                                                "address": ""}})  # fmt: skip
    assert not res.ok and res.error_code is ErrorCode.PRECONDITION_FAILED
    assert after.share_links == s.share_links
