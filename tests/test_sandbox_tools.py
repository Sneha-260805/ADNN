"""Tool engine: per-tool behaviour, error handling and time semantics."""

from __future__ import annotations

from typing import Any

import pytest

from adnn.sandbox import (
    AGENT_TOOL_NAMES,
    TOOL_SPECS,
    Account,
    ErrorCode,
    FileRecord,
    Sandbox,
    ToolCall,
    WorldState,
    canonical_hash,
    step,
)
from conftest import NOTES, REPORT, make_state


def run(state: WorldState, tool: str, **args: Any) -> tuple[WorldState, Any]:
    return step(state, ToolCall(tool, args))


def assert_failed_without_effect(
    before: WorldState, after: WorldState, result: Any, code: ErrorCode
) -> None:
    assert not result.ok
    assert result.error_code is code
    assert canonical_hash(after) == canonical_hash(before)
    assert after.clock_s == before.clock_s + before.config.seconds_per_action


# -- files ----------------------------------------------------------------------
def test_read_file_returns_content_without_changing_world(state: WorldState) -> None:
    after, res = run(state, "read_file", path=REPORT)
    assert res.ok and res.message == "report v1" and res.data["revision"] == 1
    assert canonical_hash(after) == canonical_hash(state)
    assert after.clock_s == 10 and after.counters.action_count == 1


def test_edit_file_increments_revision_and_records_history_only_with_versioning() -> None:
    plain, _ = run(make_state(), "edit_file", path=REPORT, content="report v2")
    f = plain.file(REPORT)
    assert f is not None and (f.content, f.revision, f.history) == ("report v2", 2, ())

    versioned, _ = run(make_state(versioning_enabled=True), "edit_file", path=REPORT, content="v2")
    f = versioned.file(REPORT)
    assert f is not None and f.history == ("report v1",)


def test_delete_with_recycle_bin_enabled_moves_file_to_bin() -> None:
    s = make_state(recycle_bin_enabled=True)
    after, res = run(s, "delete_file", path=REPORT)
    assert res.ok and res.data["entry_id"] == "bin-0001"
    assert after.file(REPORT) is None
    entry = after.bin_entry("bin-0001")
    assert entry is not None and entry.file == s.file(REPORT) and entry.deleted_at == 0


def test_delete_with_recycle_bin_disabled_removes_file_permanently() -> None:
    after, res = run(make_state(recycle_bin_enabled=False), "delete_file", path=REPORT)
    assert res.ok and "permanently" in res.message
    assert after.file(REPORT) is None and after.recycle_bin == ()


def test_restore_file_from_bin_and_conflict_with_existing_file() -> None:
    backup = FileRecord(REPORT, "report v1")
    s, _ = run(make_state(backups=(backup,)), "delete_file", path=REPORT)
    restored, res = run(s, "restore_file", entry_id="bin-0001")
    assert res.ok and restored.file(REPORT) == FileRecord(REPORT, "report v1")
    s2, _ = run(s, "restore_backup", path=REPORT)  # path re-occupied
    after, res = run(s2, "restore_file", entry_id="bin-0001")
    assert_failed_without_effect(s2, after, res, ErrorCode.ALREADY_EXISTS)


def test_restore_backup_replaces_whole_file_record() -> None:
    backup = FileRecord(REPORT, "old", 1)
    s, _ = run(make_state(backups=(backup,)), "edit_file", path=REPORT, content="new")
    after, res = run(s, "restore_backup", path=REPORT)
    assert res.ok and after.file(REPORT) == backup
    missing, res = run(s, "restore_backup", path=NOTES)
    assert_failed_without_effect(s, missing, res, ErrorCode.NOT_FOUND)


def test_revert_file_restores_content_but_advances_revision() -> None:
    s, _ = run(make_state(versioning_enabled=True), "edit_file", path=REPORT, content="v2")
    after, res = run(s, "revert_file", path=REPORT)
    assert res.ok
    assert after.file(REPORT) == FileRecord(REPORT, "report v1", 3, ())
    again, res = run(after, "revert_file", path=REPORT)
    assert_failed_without_effect(after, again, res, ErrorCode.PRECONDITION_FAILED)
    off, res = run(make_state(), "revert_file", path=REPORT)
    assert_failed_without_effect(make_state(), off, res, ErrorCode.PRECONDITION_FAILED)


def test_missing_file_is_not_found(state: WorldState) -> None:
    for tool, args in [
        ("read_file", {"path": "/nope"}),
        ("edit_file", {"path": "/nope", "content": "x"}),
        ("delete_file", {"path": "/nope"}),
    ]:
        after, res = step(state, ToolCall(tool, args))
        assert_failed_without_effect(state, after, res, ErrorCode.NOT_FOUND)


# -- email ------------------------------------------------------------------------
EMAIL = {"to": "bob@example.com", "subject": "Hello", "body": "Hi Bob"}


def test_send_email_without_undo_is_delivered_immediately() -> None:
    after, res = run(make_state(email_undo_window_s=0), "send_email", **EMAIL)
    assert res.ok and after.outbox[0].status == "delivered"
    s2, res = run(after, "unsend_email", message_id="msg-0001")
    assert_failed_without_effect(after, s2, res, ErrorCode.PRECONDITION_FAILED)


def test_send_email_with_undo_window_can_be_unsent_before_deadline() -> None:
    s, res = run(make_state(email_undo_window_s=60), "send_email", **EMAIL)
    assert res.ok and s.outbox[0].status == "pending" and s.outbox[0].undo_deadline == 60
    after, res = run(s, "unsend_email", message_id="msg-0001")
    assert res.ok and after.outbox == ()


def test_pending_email_is_delivered_when_window_expires() -> None:
    s, _ = run(make_state(email_undo_window_s=30), "send_email", **EMAIL)
    for _ in range(2):
        s, _ = run(s, "read_file", path=REPORT)
    assert s.clock_s == 30 and s.outbox[0].status == "delivered"
    after, res = run(s, "unsend_email", message_id="msg-0001")
    assert_failed_without_effect(s, after, res, ErrorCode.PRECONDITION_FAILED)


def test_invalid_recipient_is_rejected(state: WorldState) -> None:
    after, res = run(state, "send_email", to="not-an-address", subject="s", body="b")
    assert_failed_without_effect(state, after, res, ErrorCode.INVALID_ARGUMENTS)


# -- money ------------------------------------------------------------------------
def test_internal_transfer_moves_money_without_payment_record(state: WorldState) -> None:
    after, res = run(state, "transfer_money", from_account="checking", to="savings", amount=30)
    assert res.ok and after.payments == ()
    assert [(a.account_id, a.balance) for a in after.accounts] == [
        ("checking", 70),
        ("savings", 80),
    ]


def test_insufficient_balance_is_rejected_without_effect(state: WorldState) -> None:
    after, res = run(state, "transfer_money", from_account="savings", to="alice", amount=51)
    assert_failed_without_effect(state, after, res, ErrorCode.INSUFFICIENT_FUNDS)


@pytest.mark.parametrize(
    ("args", "code"),
    [
        ({"from_account": "checking", "to": "mallory", "amount": 1}, ErrorCode.NOT_FOUND),
        ({"from_account": "ghost", "to": "alice", "amount": 1}, ErrorCode.NOT_FOUND),
        ({"from_account": "checking", "to": "checking", "amount": 1}, ErrorCode.INVALID_ARGUMENTS),
        ({"from_account": "checking", "to": "alice", "amount": 0}, ErrorCode.INVALID_ARGUMENTS),
        ({"from_account": "checking", "to": "alice", "amount": -5}, ErrorCode.INVALID_ARGUMENTS),
        ({"from_account": "checking", "to": "alice", "amount": True}, ErrorCode.INVALID_ARGUMENTS),
        ({"from_account": "checking", "to": "alice", "amount": 1.5}, ErrorCode.INVALID_ARGUMENTS),
    ],
)
def test_invalid_transfers(state: WorldState, args: dict, code: ErrorCode) -> None:
    after, res = step(state, ToolCall("transfer_money", args))
    assert_failed_without_effect(state, after, res, code)


def test_final_payment_settles_and_cannot_be_cancelled_or_refunded() -> None:
    s, res = run(make_state(), "transfer_money", from_account="checking", to="alice", amount=40)
    assert res.ok and s.payments[0].status == "settled" and s.account("checking").balance == 60
    for tool in ("cancel_transfer", "request_refund", "request_cancellation"):
        after, res = run(s, tool, payment_id="pay-0001")
        assert_failed_without_effect(s, after, res, ErrorCode.PRECONDITION_FAILED)


def test_cancellable_payment_can_be_cancelled_within_window_only() -> None:
    s0 = make_state(payment_mode="cancellable", payment_cancel_window_s=20)
    s, _ = run(s0, "transfer_money", from_account="checking", to="alice", amount=40)
    after, res = run(s, "cancel_transfer", payment_id="pay-0001")
    assert res.ok and after.payments == () and after.account("checking").balance == 100
    late, _ = run(s, "read_file", path=REPORT)  # t=20: window closed, settled
    assert late.payments[0].status == "settled"
    after, res = run(late, "cancel_transfer", payment_id="pay-0001")
    assert_failed_without_effect(late, after, res, ErrorCode.PRECONDITION_FAILED)


def test_two_step_cancellation_requires_matching_code() -> None:
    s0 = make_state(payment_mode="cancellable_two_step", payment_cancel_window_s=60)
    s, _ = run(s0, "transfer_money", from_account="checking", to="alice", amount=40)
    s, res = run(s, "request_cancellation", payment_id="pay-0001")
    assert res.ok and res.data["code"] == "CONFIRM-pay-0001"
    bad, res = run(s, "confirm_cancellation", payment_id="pay-0001", code="WRONG")
    assert_failed_without_effect(s, bad, res, ErrorCode.PRECONDITION_FAILED)
    ok, res = run(s, "confirm_cancellation", payment_id="pay-0001", code="CONFIRM-pay-0001")
    assert res.ok and ok.payments == () and ok.account("checking").balance == 100


def test_refund_returns_amount_minus_fee_once() -> None:
    s0 = make_state(payment_mode="refundable_with_fee", refund_fee=5)
    s, _ = run(s0, "transfer_money", from_account="checking", to="alice", amount=40)
    after, res = run(s, "request_refund", payment_id="pay-0001")
    assert res.ok and after.account("checking").balance == 95
    p = after.payment("pay-0001")
    assert p is not None and (p.status, p.fee_charged) == ("refunded", 5)
    again, res = run(after, "request_refund", payment_id="pay-0001")
    assert_failed_without_effect(after, again, res, ErrorCode.PRECONDITION_FAILED)


def test_refund_rejected_when_fee_not_below_amount() -> None:
    s0 = make_state(payment_mode="refundable_with_fee", refund_fee=5)
    s, _ = run(s0, "transfer_money", from_account="checking", to="alice", amount=5)
    after, res = run(s, "request_refund", payment_id="pay-0001")
    assert_failed_without_effect(s, after, res, ErrorCode.PRECONDITION_FAILED)


# -- validation, permissions, unknown tools ---------------------------------------
@pytest.mark.parametrize(
    "action",
    [
        {"tool": "read_file", "args": {}},
        {"tool": "read_file", "args": {"path": REPORT, "extra": 1}},
        {"tool": "read_file", "args": {"path": 42}},
        {"tool": "read_file", "args": {"path": ""}},
        {"tool": "read_file", "args": {"path": "relative.txt"}},
        {"tool": "edit_file", "args": {"path": REPORT, "content": None}},
        {"tool": "read_file", "args": "not a mapping"},
        {"args": {"path": REPORT}},
        {"tool": "read_file", "args": {"path": REPORT}, "unexpected": True},
        "read_file /home/user/report.txt",
        None,
    ],
)
def test_invalid_actions_are_rejected_without_effect(state: WorldState, action: Any) -> None:
    after, res = step(state, action)
    assert_failed_without_effect(state, after, res, ErrorCode.INVALID_ARGUMENTS)


def test_unknown_tool_and_permission_denied() -> None:
    s = make_state(permitted_tools=("read_file",))
    after, res = run(s, "format_disk")
    assert_failed_without_effect(s, after, res, ErrorCode.UNKNOWN_TOOL)
    after, res = run(s, "delete_file", path=REPORT)
    assert_failed_without_effect(s, after, res, ErrorCode.PERMISSION_DENIED)


def test_tool_specs_follow_permissions_and_registry() -> None:
    assert tuple(TOOL_SPECS) == AGENT_TOOL_NAMES
    sandbox = Sandbox(make_state(permitted_tools=("read_file", "delete_file")))
    assert [t["name"] for t in sandbox.tool_specs()] == ["read_file", "delete_file"]
    schema = sandbox.tool_specs()[0]["parameters"]
    assert schema["required"] == ["path"] and schema["additionalProperties"] is False


def test_balances_never_go_negative() -> None:
    s = make_state(accounts=(Account("checking", 10),), payees=("alice",))
    for _ in range(5):
        s, _ = run(s, "transfer_money", from_account="checking", to="alice", amount=4)
    assert s.account("checking").balance == 2
    assert len(s.payments) == 2
