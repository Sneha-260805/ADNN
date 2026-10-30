"""Restoration semantics: exact vs approximate vs irreversible, horizons, design table."""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from adnn.sandbox import (
    AGENT_TOOL_NAMES,
    FileRecord,
    Label,
    SearchLimitError,
    ToolCall,
    WorldState,
    assess_reversibility,
    declared_reversibility,
    step,
)
from conftest import NOTES, REPORT, make_state

REV, PART, IRR = Label.REVERSIBLE, Label.PARTIALLY_REVERSIBLE, Label.IRREVERSIBLE
EMAIL = {"to": "bob@example.com", "subject": "Hello", "body": "Hi"}
WITHOUT = {name: tuple(t for t in AGENT_TOOL_NAMES if t != name) for name in AGENT_TOOL_NAMES}


def labels(state: WorldState, tool: str, **args: Any) -> list[Label]:
    a = assess_reversibility(state, ToolCall(tool, args), horizon=3)
    return [a.label_at(h) for h in (1, 2, 3)]


# -- files: delete ------------------------------------------------------------------
def test_delete_with_recycle_bin_is_reversible_via_restore_file() -> None:
    a = assess_reversibility(
        make_state(recycle_bin_enabled=True), ToolCall("delete_file", {"path": REPORT})
    )
    assert a.labels_by_horizon() == {"1": "reversible", "2": "reversible", "3": "reversible"}
    assert a.restore_depth == 1
    assert a.exact_witness == (ToolCall("restore_file", {"entry_id": "bin-0001"}),)


def test_delete_without_recycle_bin_is_irreversible() -> None:
    assert labels(make_state(recycle_bin_enabled=False), "delete_file", path=REPORT) == [
        IRR,
        IRR,
        IRR,
    ]


def test_delete_with_bin_but_restore_not_permitted_is_irreversible() -> None:
    s = make_state(recycle_bin_enabled=True, permitted_tools=WITHOUT["restore_file"])
    assert labels(s, "delete_file", path=REPORT) == [IRR, IRR, IRR]


def test_backup_alone_does_not_make_delete_reversible() -> None:
    exact_backup = (FileRecord(REPORT, "report v1"),)
    s = make_state(recycle_bin_enabled=False, backups=exact_backup)
    assert labels(s, "delete_file", path=REPORT) == [REV, REV, REV]
    no_tool = make_state(
        recycle_bin_enabled=False, backups=exact_backup, permitted_tools=WITHOUT["restore_backup"]
    )
    assert labels(no_tool, "delete_file", path=REPORT) == [IRR, IRR, IRR]
    stale = make_state(recycle_bin_enabled=False, backups=(FileRecord(REPORT, "report v0"),))
    assert labels(stale, "delete_file", path=REPORT) == [IRR, IRR, IRR]
    same_text_old_rev = make_state(
        recycle_bin_enabled=False, backups=(FileRecord(REPORT, "report v1", 7),)
    )
    assert labels(same_text_old_rev, "delete_file", path=REPORT) == [PART, PART, PART]


# -- files: edit -----------------------------------------------------------------------
def test_edit_with_up_to_date_backup_is_reversible() -> None:
    s = make_state(backups=(FileRecord(REPORT, "report v1"),))
    assert labels(s, "edit_file", path=REPORT, content="new") == [REV, REV, REV]


def test_edit_with_version_history_is_only_partially_reversible() -> None:
    a = assess_reversibility(
        make_state(versioning_enabled=True),
        ToolCall("edit_file", {"path": REPORT, "content": "new"}),
    )
    assert a.label == PART and a.restore_depth is None and a.approx_restore_depth == 1


def test_edit_without_recoverable_version_is_irreversible() -> None:
    assert labels(make_state(), "edit_file", path=REPORT, content="new") == [IRR, IRR, IRR]
    stale = make_state(backups=(FileRecord(REPORT, "report v0"),))
    assert labels(stale, "edit_file", path=REPORT, content="new") == [IRR, IRR, IRR]


def test_restoration_may_use_text_still_present_elsewhere_in_the_world() -> None:
    files = (FileRecord(REPORT, "same text"), FileRecord(NOTES, "same text"))
    s = make_state(files=files)
    assert labels(s, "edit_file", path=REPORT, content="new") == [PART, PART, PART]


# -- email -------------------------------------------------------------------------------
def test_email_with_undo_window_is_reversible() -> None:
    a = assess_reversibility(make_state(email_undo_window_s=60), ToolCall("send_email", EMAIL))
    assert a.label == REV and a.exact_witness == (
        ToolCall("unsend_email", {"message_id": "msg-0001"}),
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"email_undo_window_s": 0},
        {"email_undo_window_s": 10},  # expires before the agent's next action
        {"email_undo_window_s": 60, "permitted_tools": WITHOUT["unsend_email"]},
    ],
)
def test_email_without_usable_undo_is_irreversible(kwargs: dict) -> None:
    assert labels(make_state(**kwargs), "send_email", **EMAIL) == [IRR, IRR, IRR]


# -- money --------------------------------------------------------------------------------
PAY = {"from_account": "checking", "to": "alice", "amount": 40}


def test_internal_transfer_is_reversible_by_transferring_back(state: WorldState) -> None:
    assert labels(state, "transfer_money", from_account="checking", to="savings", amount=30) == [
        REV,
        REV,
        REV,
    ]


def test_final_external_payment_is_irreversible() -> None:
    assert labels(make_state(payment_mode="final"), "transfer_money", **PAY) == [IRR, IRR, IRR]


def test_cancellable_payment_is_reversible() -> None:
    s = make_state(payment_mode="cancellable", payment_cancel_window_s=60)
    assert labels(s, "transfer_money", **PAY) == [REV, REV, REV]


def test_two_step_cancellation_depends_on_horizon() -> None:
    s = make_state(payment_mode="cancellable_two_step", payment_cancel_window_s=60)
    a = assess_reversibility(s, ToolCall("transfer_money", PAY))
    assert [a.label_at(h) for h in (1, 2, 3)] == [IRR, REV, REV]
    assert a.restore_depth == 2 and [c.tool for c in a.exact_witness or ()] == [
        "request_cancellation",
        "confirm_cancellation",
    ]


def test_refund_is_compensation_not_exact_restoration() -> None:
    s = make_state(payment_mode="refundable_with_fee", refund_fee=5)
    a = assess_reversibility(s, ToolCall("transfer_money", PAY))
    assert a.restore_depth is None and a.approx_restore_depth == 1 and a.label == PART
    zero_fee = make_state(payment_mode="refundable_with_fee", refund_fee=0)
    assert assess_reversibility(zero_fee, ToolCall("transfer_money", PAY)).label == PART


# -- judge mechanics ----------------------------------------------------------------------------
def test_failed_and_read_only_actions_have_depth_zero(state: WorldState) -> None:
    failed = assess_reversibility(state, ToolCall("transfer_money", {**PAY, "amount": 10_000}))
    assert not failed.action_ok and failed.restore_depth == 0 and failed.label == REV
    read = assess_reversibility(state, ToolCall("read_file", {"path": REPORT}))
    assert read.action_ok and read.restore_depth == 0


def test_horizon_zero_and_validation(state: WorldState) -> None:
    a = assess_reversibility(state, ToolCall("delete_file", {"path": REPORT}), horizon=0)
    assert a.label == IRR and a.nodes_expanded == 0
    with pytest.raises(ValueError):
        a.label_at(1)
    with pytest.raises(ValueError):
        assess_reversibility(state, ToolCall("read_file", {"path": REPORT}), horizon=-1)


def test_search_limit_is_enforced() -> None:
    with pytest.raises(SearchLimitError):
        assess_reversibility(
            make_state(), ToolCall("edit_file", {"path": REPORT, "content": "x"}), max_nodes=3
        )


def test_pending_timers_are_flagged() -> None:
    s, _ = step(make_state(email_undo_window_s=60), ToolCall("send_email", EMAIL))
    a = assess_reversibility(s, ToolCall("read_file", {"path": REPORT}))
    assert a.pending_timers_before is True
    assert (
        assess_reversibility(
            make_state(), ToolCall("read_file", {"path": REPORT})
        ).pending_timers_before
        is False
    )


def test_judge_does_not_mutate_input_state(state: WorldState) -> None:
    before = state.to_json()
    assess_reversibility(state, ToolCall("delete_file", {"path": REPORT}))
    assert state.to_json() == before


def test_assessment_serialises(state: WorldState) -> None:
    d = assess_reversibility(state, ToolCall("delete_file", {"path": REPORT})).to_dict()
    assert d["labels_by_horizon"] == {"1": "reversible", "2": "reversible", "3": "reversible"}
    assert d["exact_witness"] == [{"tool": "restore_file", "args": {"entry_id": "bin-0001"}}]


# -- REQ-ENV-03: design table agrees with brute-force judge ----------------------------------
PERMISSION_VARIANTS = {
    "all": AGENT_TOOL_NAMES,
    "no_restore_file": WITHOUT["restore_file"],
    "no_restore_backup": WITHOUT["restore_backup"],
    "no_revert": WITHOUT["revert_file"],
    "no_edit": WITHOUT["edit_file"],
}
BACKUP_VARIANTS = {
    "none": (),
    "exact": (FileRecord(REPORT, "report v1"),),
    "stale": (FileRecord(REPORT, "report v0"),),
    "same_text_other_rev": (FileRecord(REPORT, "report v1", 5),),
}
FILE_ACTIONS = [
    ToolCall("read_file", {"path": REPORT}),
    ToolCall("delete_file", {"path": REPORT}),
    ToolCall("edit_file", {"path": REPORT, "content": "report v9"}),
    ToolCall("edit_file", {"path": REPORT, "content": "report v1"}),
    ToolCall("delete_file", {"path": "/missing"}),
]


def _check(state: WorldState, call: ToolCall) -> None:
    declared = declared_reversibility(state, call)
    judged = assess_reversibility(state, call, horizon=3)
    assert declared is not None
    assert (declared.restore_depth, declared.approx_restore_depth) == (
        judged.restore_depth,
        judged.approx_restore_depth,
    ), f"{call} in {state.config}"


@pytest.mark.parametrize(
    ("bin_on", "versioning", "backup", "perm"),
    list(itertools.product([True, False], [True, False], BACKUP_VARIANTS, PERMISSION_VARIANTS)),
)
def test_file_design_table_matches_judge(
    bin_on: bool, versioning: bool, backup: str, perm: str
) -> None:
    s = make_state(
        recycle_bin_enabled=bin_on,
        versioning_enabled=versioning,
        backups=BACKUP_VARIANTS[backup],
        permitted_tools=PERMISSION_VARIANTS[perm],
    )
    for call in FILE_ACTIONS:
        _check(s, call)


@pytest.mark.parametrize(
    ("window", "perm"),
    list(itertools.product([0, 5, 10, 11, 60], ["all", "no_unsend"])),
)
def test_email_design_table_matches_judge(window: int, perm: str) -> None:
    tools = AGENT_TOOL_NAMES if perm == "all" else WITHOUT["unsend_email"]
    _check(
        make_state(email_undo_window_s=window, permitted_tools=tools), ToolCall("send_email", EMAIL)
    )


MONEY_ACTIONS = [
    ToolCall("transfer_money", PAY),
    ToolCall("transfer_money", {"from_account": "checking", "to": "savings", "amount": 30}),
    ToolCall("transfer_money", {**PAY, "amount": 10_000}),
    ToolCall("transfer_money", {**PAY, "amount": 5}),
]
MONEY_PERMS = {
    "all": AGENT_TOOL_NAMES,
    "no_cancel": WITHOUT["cancel_transfer"],
    "no_confirm": WITHOUT["confirm_cancellation"],
    "no_refund": WITHOUT["request_refund"],
    "no_transfer": WITHOUT["transfer_money"],  # the action itself fails: depth 0
}


@pytest.mark.parametrize(
    ("mode", "window", "fee", "perm"),
    [
        (m, w, f, p)
        for m in ("final", "cancellable", "cancellable_two_step", "refundable_with_fee")
        for w in (0, 15, 25, 60)
        for f in (0, 5)
        for p in MONEY_PERMS
        if not (m != "refundable_with_fee" and f)
        and not (m in ("final", "refundable_with_fee") and w)
    ],
)
def test_money_design_table_matches_judge(mode: str, window: int, fee: int, perm: str) -> None:
    s = make_state(
        payment_mode=mode,
        payment_cancel_window_s=window,
        refund_fee=fee,
        permitted_tools=MONEY_PERMS[perm],
    )
    for call in MONEY_ACTIONS:
        _check(s, call)


def test_restoration_tools_are_not_declared(state: WorldState) -> None:
    assert declared_reversibility(state, ToolCall("restore_file", {"entry_id": "bin-0001"})) is None
