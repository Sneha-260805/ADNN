"""Pilot generator and validator: safeguards, determinism, and fault detection.

Uses a small build (1 scenario per family, 42 examples) so the suite stays fast.
The full 210-example pilot is built and validated by the commands in docs/13.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from adnn.dataset import pilot
from adnn.dataset.schema import PROVISIONAL_OQ21, PROVISIONAL_PARTIAL, read_jsonl
from adnn.dataset.validation import (
    PILOT_THRESHOLDS,
    flat_diff,
    validate_directory,
    validate_records,
)

SMALL = {**PILOT_THRESHOLDS, "min_examples": 0}


@pytest.fixture(scope="module")
def small_build(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("pilot_small")
    pilot.build_pilot(out, scenarios_per_family=1)
    return out


def _load(d: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = json.loads((d / pilot.MANIFEST_FILE).read_text(encoding="utf-8"))
    split = json.loads((d / pilot.SPLIT_FILE).read_text(encoding="utf-8"))
    tools = json.loads((d / pilot.TOOL_SETS_FILE).read_text(encoding="utf-8"))
    return read_jsonl(d / pilot.DATASET_FILE), split, tools, manifest


def test_small_build_validates(small_build: Path) -> None:
    rep = validate_directory(small_build, thresholds=SMALL)
    assert rep.ok, rep.errors
    assert rep.checks_run["oracle"] == 42 and rep.checks_run["pairs"] == 14


def test_build_is_byte_deterministic(small_build: Path, tmp_path: Path) -> None:
    pilot.build_pilot(tmp_path, scenarios_per_family=1)
    for name in (pilot.DATASET_FILE, pilot.SPLIT_FILE, pilot.TOOL_SETS_FILE):
        assert (tmp_path / name).read_bytes() == (small_build / name).read_bytes(), name


def test_split_is_frozen_before_rendering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []
    real = pilot.render_and_label

    def spy(plans: Any, split: Any, seed: int) -> Any:
        calls.append((tmp_path / pilot.SPLIT_FILE).exists())
        return real(plans, split, seed)

    monkeypatch.setattr(pilot, "render_and_label", spy)
    pilot.build_pilot(tmp_path, scenarios_per_family=1)
    assert calls == [True]


def test_split_depends_only_on_family_ids_and_seed() -> None:
    a, b = pilot.freeze_split(1), pilot.freeze_split(1)
    assert a == b and len(a["test_families"]) == 3
    domains = {f.family_id: f.domain for f in pilot.FAMILIES}
    assert sorted(domains[f] for f in a["test_families"]) == ["email", "files", "money"]


def test_safeguards_hold_in_every_record(small_build: Path) -> None:
    records, split, _, manifest = _load(small_build)
    assert manifest["oracle"]["on_budget_exhausted"] == "return"
    assert manifest["oracle"]["action_domain_limitations"]
    test_f = set(split["test_families"])
    for r in records:
        o = r["meta"]["oracle"]
        assert o["is_definitive"] and o["status"] == "complete"
        assert not any(m["status"] == "pending" for m in r["state_struct"]["outbox"])
        assert not any(p["status"] == "pending" for p in r["state_struct"]["payments"])
        if "partially_reversible" in r["labels_by_horizon"].values():
            assert PROVISIONAL_PARTIAL in r["provisional_reasons"] and r["label_provisional"]
        if r["render_style"] == "compact":
            assert r["template_id"] in test_f


def test_oq21_sensitivity_is_recorded(small_build: Path) -> None:
    records, *_ = _load(small_build)
    flagged = [r for r in records if PROVISIONAL_OQ21 in r["provisional_reasons"]]
    assert flagged, "expected at least one OQ-21-sensitive example"
    for r in flagged:
        assert r["action_verb"] in ("edit_file", "delete_file")
        assert r["meta"]["oq21_alternative_labels_by_horizon"] != r["labels_by_horizon"]


def test_design_expectations_are_enforced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import dataclasses

    wrong = dataclasses.replace(pilot.FAMILIES[0], expected=("irreversible", "reversible"))
    monkeypatch.setattr(pilot, "FAMILIES", (wrong,))
    with pytest.raises(AssertionError, match="oracle"):
        pilot.build_pilot(tmp_path, scenarios_per_family=1)


def test_flat_diff() -> None:
    assert flat_diff({"a": [1, 2], "b": {"c": 1}}, {"a": [1, 3], "b": {"c": 1}}) == ["a[1]"]
    assert flat_diff({"a": []}, {"a": [1]}) == ["a"]


# -- the validator must catch each fault ------------------------------------------------------
def _pair_member(records: list[dict[str, Any]], family: str, kind: str) -> dict[str, Any]:
    return next(r for r in records if r["template_id"] == family and r["id"].endswith(kind))


def _corrupt_label(rs: list[dict[str, Any]]) -> None:
    r = _pair_member(rs, "f01_delete_bin", "-pa")
    r["label"] = r["labels_by_horizon"]["3"] = "irreversible"


def _corrupt_action(rs: list[dict[str, Any]]) -> None:
    _pair_member(rs, "f01_delete_bin", "-pb")["action_text"] += " "


def _corrupt_state_text(rs: list[dict[str, Any]]) -> None:
    _pair_member(rs, "f04_edit_versioning", "-pa")["state_text"] += "\n"


def _second_pivot(rs: list[dict[str, Any]]) -> None:
    _pair_member(rs, "f01_delete_bin", "-pb")["state_struct"]["config"]["versioning_enabled"] = (
        False
    )


def _pending_timer(rs: list[dict[str, Any]]) -> None:
    r = _pair_member(rs, "f07_email_undo", "-pa")
    r["state_struct"]["outbox"] = [
        {"message_id": "msg-0001", "to": "a@example.com", "subject": "s", "body": "b",
         "sent_at": 0, "status": "pending", "undo_deadline": 60}
    ]  # fmt: skip


def _leak(rs: list[dict[str, Any]]) -> None:
    _pair_member(rs, "f01_delete_bin", "-pa")["task_text"] += " (label: reversible)"


def _cross_split(rs: list[dict[str, Any]]) -> None:
    _pair_member(rs, "f01_delete_bin", "-pa")["template_id"] = "f05_edit_backup_fresh"


def _unflagged_partial(rs: list[dict[str, Any]]) -> None:
    r = _pair_member(rs, "f04_edit_versioning", "-pa")
    r["provisional_reasons"], r["label_provisional"] = [], False


def _metadata_field(rs: list[dict[str, Any]]) -> None:
    rs[0]["split"] = "train"


FAULTS = {
    "label": (_corrupt_label, "oracle"),
    "action_not_byte_identical": (_corrupt_action, "pairs"),
    "state_text": (_corrupt_state_text, "replay"),
    "second_state_difference": (_second_pivot, "pairs"),
    "pending_timer": (_pending_timer, "replay"),
    "leak_in_prompt": (_leak, "leakage"),
    "family_crosses_split": (_cross_split, "split"),
    "partial_not_provisional": (_unflagged_partial, "provisional"),
    "unknown_field": (_metadata_field, "schema"),
}


@pytest.mark.parametrize("fault", FAULTS, ids=list(FAULTS))
def test_validator_detects_fault(small_build: Path, fault: str) -> None:
    records, split, tools, _ = _load(small_build)
    corrupt, expected_check = FAULTS[fault]
    records = copy.deepcopy(records)
    corrupt(records)
    # Only a corrupted label needs the (slow) oracle re-run to be detected.
    rep = validate_records(
        records, split=split, tool_sets=tools, thresholds=SMALL, rerun_oracle=fault == "label"
    )
    assert not rep.ok
    assert any(e.startswith(f"[{expected_check}]") for e in rep.errors), rep.errors[:5]


def test_validator_detects_tampered_file(small_build: Path, tmp_path: Path) -> None:
    for name in (pilot.DATASET_FILE, pilot.SPLIT_FILE, pilot.TOOL_SETS_FILE, pilot.MANIFEST_FILE):
        (tmp_path / name).write_bytes((small_build / name).read_bytes())
    with (tmp_path / pilot.DATASET_FILE).open("a", encoding="utf-8") as fh:
        fh.write("\n")
    rep = validate_directory(tmp_path, thresholds=SMALL, rerun_oracle=False)
    assert any(e.startswith("[file_hashes] dataset") for e in rep.errors)


def test_validator_enforces_size_and_pair_fraction(small_build: Path) -> None:
    records, split, tools, _ = _load(small_build)
    rep = validate_records(records, split=split, tool_sets=tools, rerun_oracle=False)
    assert any("< 150" in e for e in rep.errors)
    singles = [r for r in records if not r["pair_id"]]
    rep = validate_records(
        singles, split=split, tool_sets=tools, thresholds=SMALL, rerun_oracle=False
    )
    assert any("minimal-pair fraction" in e for e in rep.errors)
