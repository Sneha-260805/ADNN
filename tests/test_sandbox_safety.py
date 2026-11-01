"""REQ-SAFE-01: the sandbox has no external side effects.

Two independent checks: a static scan of imports and dangerous builtins in
the sandbox source, and a runtime check that exercises every tool and the
restoration judge while file, process and network primitives are booby-trapped.
"""

from __future__ import annotations

import ast
import builtins
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

import adnn
from adnn.sandbox import FileRecord, Sandbox, ToolCall, assess_reversibility
from conftest import REPORT, make_state

SANDBOX_SOURCES = [
    *sorted((Path(adnn.__file__).parent / "sandbox").glob("*.py")),
    Path(adnn.__file__).parent / "demo.py",
]
FORBIDDEN_MODULES = {
    "os", "sys", "io", "shutil", "subprocess", "socket", "ssl", "smtplib", "http", "urllib",
    "requests", "httpx", "pathlib", "tempfile", "ctypes", "multiprocessing", "asyncio",
    "pickle", "importlib", "random", "time", "datetime",
}  # fmt: skip
FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__", "input"}


@pytest.mark.parametrize("path", SANDBOX_SOURCES, ids=lambda p: p.name)
def test_sandbox_source_imports_no_side_effecting_modules(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            roots = {(node.module or "").split(".")[0]}
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in FORBIDDEN_CALLS, f"{path.name}: {node.func.id}()"
            continue
        else:
            continue
        assert not (roots & FORBIDDEN_MODULES), f"{path.name} imports {roots & FORBIDDEN_MODULES}"


def _trap(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("sandbox attempted a real side effect")


@pytest.fixture
def booby_trapped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(builtins, "open", _trap)
    monkeypatch.setattr(socket, "socket", _trap)
    monkeypatch.setattr(socket, "create_connection", _trap)
    monkeypatch.setattr(subprocess, "Popen", _trap)
    for name in ("remove", "unlink", "rename", "replace", "rmdir", "mkdir", "system", "makedirs"):
        monkeypatch.setattr(os, name, _trap)
    monkeypatch.setattr(shutil, "rmtree", _trap)
    monkeypatch.setattr(shutil, "move", _trap)


ALL_TOOL_CALLS = [
    ToolCall("read_file", {"path": REPORT}),
    ToolCall("edit_file", {"path": REPORT, "content": "x"}),
    ToolCall("revert_file", {"path": REPORT}),
    ToolCall("delete_file", {"path": REPORT}),
    ToolCall("restore_file", {"entry_id": "bin-0001"}),
    ToolCall("restore_backup", {"path": REPORT}),
    ToolCall("send_email", {"to": "bob@example.com", "subject": "s", "body": "b"}),
    ToolCall("unsend_email", {"message_id": "msg-0001"}),
    ToolCall("transfer_money", {"from_account": "checking", "to": "alice", "amount": 10}),
    ToolCall("cancel_transfer", {"payment_id": "pay-0001"}),
    ToolCall("request_cancellation", {"payment_id": "pay-0001"}),
    ToolCall("confirm_cancellation", {"payment_id": "pay-0001", "code": "CONFIRM-pay-0001"}),
    ToolCall("request_refund", {"payment_id": "pay-0001"}),
]


@pytest.mark.usefixtures("booby_trapped")
@pytest.mark.parametrize("mode", ["cancellable", "cancellable_two_step", "refundable_with_fee"])
def test_every_tool_runs_without_touching_the_real_world(mode: str) -> None:

    s = make_state(
        versioning_enabled=True,
        email_undo_window_s=60,
        payment_mode=mode,
        payment_cancel_window_s=60,
        refund_fee=1,
        backups=(FileRecord(REPORT, "report v1"),),
    )
    sandbox = Sandbox(s)
    for call in ALL_TOOL_CALLS:
        sandbox.execute(call)
        assess_reversibility(sandbox.state, call, horizon=2)
    sandbox.get_observation()
    Sandbox.from_json(sandbox.to_json())
    assert len(sandbox.get_action_history()) == len(ALL_TOOL_CALLS)
