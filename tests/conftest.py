"""Shared fixtures: small, hand-built sandbox worlds (no generated data)."""

from __future__ import annotations

from typing import Any

import pytest

from adnn.sandbox import Account, FileRecord, SandboxConfig, WorldState

REPORT = "/home/user/report.txt"
NOTES = "/home/user/notes.txt"


def make_state(
    *,
    files: tuple[FileRecord, ...] | None = None,
    backups: tuple[FileRecord, ...] = (),
    accounts: tuple[Account, ...] | None = None,
    payees: tuple[str, ...] = ("alice",),
    **config: Any,
) -> WorldState:
    return WorldState(
        config=SandboxConfig(**config),
        files=files
        if files is not None
        else (FileRecord(REPORT, "report v1"), FileRecord(NOTES, "notes v1")),
        backups=backups,
        accounts=accounts
        if accounts is not None
        else (Account("checking", 100), Account("savings", 50)),
        payees=payees,
    )


@pytest.fixture
def state() -> WorldState:
    return make_state()
