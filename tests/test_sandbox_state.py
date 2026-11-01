"""State model: serialisation, normalisation, invariants, canonical state."""

from __future__ import annotations

import dataclasses
import json

import pytest

from adnn.sandbox import (
    Account,
    BinEntry,
    Counters,
    EmailMessage,
    FileRecord,
    InvalidStateError,
    Payment,
    SandboxConfig,
    WorldState,
    canonical_dict,
    canonical_hash,
    full_hash,
    validate_state,
)
from conftest import REPORT, make_state


def rich_state() -> WorldState:
    return WorldState(
        config=SandboxConfig(
            recycle_bin_enabled=True,
            versioning_enabled=True,
            email_undo_window_s=60,
            payment_mode="cancellable",
            payment_cancel_window_s=60,
            permitted_tools=("read_file", "delete_file", "restore_file"),
        ),
        files=(FileRecord(REPORT, "v3", 3, ("v1", "v2")),),
        backups=(FileRecord(REPORT, "v2", 2, ("v1",)),),
        recycle_bin=(BinEntry("bin-0001", FileRecord("/tmp/x.txt", "x"), 0),),
        outbox=(EmailMessage("msg-0001", "bob@example.com", "Hi", "Body", 0, "pending", 60),),
        accounts=(Account("savings", 5), Account("checking", 10)),
        payees=("zoe", "alice"),
        payments=(Payment("pay-0001", "checking", "alice", 3, 0, "pending", 60),),
        clock_s=20,
        counters=Counters(2, 2, 2, 2),
    )


def test_json_round_trip_is_lossless() -> None:
    s = rich_state()
    validate_state(s)
    assert WorldState.from_json(s.to_json()) == s
    assert WorldState.from_dict(json.loads(json.dumps(s.to_dict()))) == s


def test_collections_are_normalised_so_order_does_not_matter() -> None:
    s = rich_state()
    reordered = dataclasses.replace(
        s, accounts=tuple(reversed(s.accounts)), payees=("alice", "zoe")
    )
    assert reordered == s
    assert [a.account_id for a in s.accounts] == ["checking", "savings"]


def test_state_is_immutable() -> None:
    s = rich_state()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.clock_s = 5  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.files[0].content = "hacked"  # type: ignore[misc]
    assert isinstance(s.files, tuple)


def test_canonical_state_excludes_clock_and_counters_only() -> None:
    s = rich_state()
    later = dataclasses.replace(s, clock_s=999, counters=Counters(9, 9, 9, 9))
    assert canonical_hash(later) == canonical_hash(s)
    assert full_hash(later) != full_hash(s)
    assert set(canonical_dict(s)) == set(s.to_dict()) - {"clock_s", "counters"}
    changed = dataclasses.replace(s, files=(FileRecord(REPORT, "v3", 4, ("v1", "v2")),))
    assert canonical_hash(changed) != canonical_hash(s)  # revision is canonical


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"files": (FileRecord("/a", "x"), FileRecord("/a", "y"))}, "duplicate file paths"),
        ({"files": (FileRecord("relative.txt", "x"),)}, "absolute"),
        ({"accounts": (Account("checking", -1),)}, "negative balance"),
        ({"payees": ("checking",)}, "overlap"),
        ({"files": (FileRecord("/a", "x", 2, ("old",)),)}, "versioning disabled"),
        ({"permitted_tools": ("restore_snapshot",)}, "unknown permitted tools"),
        ({"payment_mode": "magic"}, "payment_mode"),
        ({"seconds_per_action": 0}, "seconds_per_action"),
    ],
)
def test_invariant_violations_are_rejected(kwargs: dict, message: str) -> None:
    config_keys = {f.name for f in dataclasses.fields(SandboxConfig)}
    cfg = {k: v for k, v in kwargs.items() if k in config_keys}
    rest = {k: v for k, v in kwargs.items() if k not in config_keys}
    with pytest.raises(InvalidStateError, match=message):
        validate_state(make_state(**rest, **cfg))


def test_bin_entries_require_enabled_bin() -> None:
    s = dataclasses.replace(
        make_state(recycle_bin_enabled=False),
        recycle_bin=(BinEntry("bin-0001", FileRecord("/x", "x"), 0),),
    )
    with pytest.raises(InvalidStateError, match="disabled"):
        validate_state(s)


def test_malformed_dict_raises_invalid_state() -> None:
    with pytest.raises(InvalidStateError):
        WorldState.from_dict({"files": [{"path": "/a"}]})
