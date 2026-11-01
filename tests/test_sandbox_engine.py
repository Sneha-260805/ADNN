"""Sandbox engine: determinism, snapshots, serialisation, history, agent boundary."""

from __future__ import annotations

import dataclasses
import inspect
import itertools

import pytest

from adnn.sandbox import (
    AGENT_TOOL_NAMES,
    TOOL_SPECS,
    ErrorCode,
    InvalidStateError,
    Sandbox,
    WorldState,
    canonical_hash,
    full_hash,
)
from conftest import NOTES, REPORT, make_state

SCRIPT: list[dict] = [
    {"tool": "read_file", "args": {"path": REPORT}},
    {"tool": "edit_file", "args": {"path": REPORT, "content": "report v2"}},
    {"tool": "delete_file", "args": {"path": NOTES}},
    {"tool": "send_email", "args": {"to": "bob@example.com", "subject": "S", "body": "B"}},
    {"tool": "transfer_money", "args": {"from_account": "checking", "to": "alice", "amount": 7}},
    {"tool": "restore_file", "args": {"entry_id": "bin-0001"}},
    {"tool": "transfer_money", "args": {"from_account": "savings", "to": "alice", "amount": 999}},
    {"tool": "no_such_tool", "args": {}},
    {"tool": "unsend_email", "args": {"message_id": "msg-0001"}},
]


def initial() -> WorldState:
    return make_state(
        versioning_enabled=True,
        email_undo_window_s=60,
        payment_mode="cancellable",
        payment_cancel_window_s=60,
    )


def run_script(state: WorldState) -> Sandbox:
    sandbox = Sandbox(state)
    for action in SCRIPT:
        sandbox.execute(action)
    return sandbox


def test_deterministic_replay() -> None:
    a, b = run_script(initial()), run_script(initial())
    assert a.to_json() == b.to_json()
    assert full_hash(a.state) == full_hash(b.state)
    assert a.get_action_history() == b.get_action_history()


def test_sandbox_json_round_trip_includes_history() -> None:
    a = run_script(initial())
    b = Sandbox.from_json(a.to_json())
    assert b.state == a.state
    assert b.get_action_history() == a.get_action_history()
    assert b.to_json() == a.to_json()


def test_action_history_is_correct() -> None:
    sandbox = run_script(initial())
    history = sandbox.get_action_history()
    assert [r.step for r in history] == list(range(1, len(SCRIPT) + 1))
    assert [r.tool for r in history] == [a["tool"] for a in SCRIPT]
    assert [r.ok for r in history] == [True, True, True, True, True, True, False, False, True]
    assert history[6].error_code == ErrorCode.INSUFFICIENT_FUNDS.value
    assert history[7].error_code == ErrorCode.UNKNOWN_TOOL.value
    assert dict(history[1].args) == SCRIPT[1]["args"]
    for prev, cur in itertools.pairwise(history):
        assert cur.clock_before == prev.clock_after
        assert cur.state_hash_before == prev.state_hash_after
    assert history[0].state_hash_before == canonical_hash(initial())
    assert history[-1].state_hash_after == sandbox.state_hash()
    # read_file and failed actions do not change the canonical state
    for i in (0, 6, 7):
        assert history[i].state_hash_before == history[i].state_hash_after


def test_history_records_are_read_only_copies() -> None:
    action = {"tool": "read_file", "args": {"path": REPORT}}
    sandbox = Sandbox(initial())
    sandbox.execute(action)
    action["args"]["path"] = "/mutated"
    record = sandbox.get_action_history()[0]
    assert record.args["path"] == REPORT
    with pytest.raises(TypeError):
        record.args["path"] = "/x"  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.ok = False  # type: ignore[misc]


def test_snapshot_isolation_and_restore() -> None:
    sandbox = Sandbox(initial())
    sandbox.execute(SCRIPT[1])
    snap = sandbox.snapshot()
    frozen_json = snap.state.to_json()
    for action in SCRIPT[2:]:
        sandbox.execute(action)
    assert snap.state.to_json() == frozen_json  # later actions did not leak into snapshot
    assert len(snap.history) == 1
    sandbox.restore_snapshot(snap)
    assert sandbox.state.to_json() == frozen_json
    assert sandbox.get_action_history() == snap.history
    # executing after restore does not alter the snapshot either
    sandbox.execute(SCRIPT[2])
    assert snap.state.to_json() == frozen_json and len(snap.history) == 1


def test_reset_validates_and_clears_history() -> None:
    sandbox = run_script(initial())
    sandbox.reset(initial().to_dict())
    assert sandbox.get_action_history() == ()
    assert sandbox.state == initial()
    with pytest.raises(InvalidStateError):
        sandbox.reset(make_state(payees=("checking",)))
    with pytest.raises(TypeError):
        sandbox.restore_snapshot("not a snapshot")  # type: ignore[arg-type]


RESEARCHER_ONLY = {
    "reset",
    "snapshot",
    "restore_snapshot",
    "to_json",
    "from_json",
    "get_action_history",
    "state",
    "state_hash",
}


def test_researcher_functions_are_not_agent_tools() -> None:
    public = {n for n, _ in inspect.getmembers(Sandbox) if not n.startswith("__")}
    assert public >= RESEARCHER_ONLY
    assert not (public & set(AGENT_TOOL_NAMES))
    assert not (public & set(TOOL_SPECS))
    sandbox = Sandbox(initial())
    sandbox.execute(SCRIPT[1])
    snap = sandbox.snapshot()
    for name in sorted(public | {"_state", "__init__", "eval", "exec"}):
        before = sandbox.state
        result = sandbox.execute({"tool": name, "args": {}})
        assert not result.ok and result.error_code is ErrorCode.UNKNOWN_TOOL, name
        assert canonical_hash(sandbox.state) == canonical_hash(before)
    assert canonical_hash(sandbox.state) == canonical_hash(snap.state)
    names_in_specs = {t["name"] for t in sandbox.tool_specs()}
    assert names_in_specs <= set(AGENT_TOOL_NAMES)
    assert not (names_in_specs & RESEARCHER_ONLY)


def test_observation_is_deterministic_text() -> None:
    a, b = run_script(initial()), run_script(initial())
    assert a.get_observation() == b.get_observation()
    obs = a.get_observation()
    assert "recycle_bin: enabled" in obs and "Time: t=90s" in obs
    assert "pay-0001: 7 from checking to alice: pending" in obs
    assert "msg-0001" not in obs  # unsent by the last action
