"""Phase 5H production generator, grouped split and ScienceWorld exporter (ADR-0009; docs/34).
Small configurations only; no Java (the ScienceWorld tests read stored evidence)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from adnn.dataset import production as prod
from adnn.dataset.api import LoadedDataset
from adnn.dataset.rendering import TEST_ONLY_STYLES
from adnn.dataset.validation import PARTIAL_POLICY_TEAM, validate_records
from adnn.scienceworld import export as sx

ROOT = Path(__file__).resolve().parents[1]
SMALL = replace(
    prod.ProductionConfig(),
    draws_per_family=8,
    legacy_families=(
        "f01_delete_bin",
        "f04_edit_versioning",
        "f09_pay_cancel_vs_final",
        "f13_pay_refund_fee",
    ),
    link_families=("s01_link_revoke_address_kind",),
    family_share_cap=0.5,
    split_search=50,
)


@pytest.fixture(scope="module")
def built() -> prod.Built:
    return prod.build(SMALL, "test")


def test_f13_refund_fee_relation_separates_label_changing_amounts() -> None:
    def keys(amount: int) -> dict[str, str]:
        state = {"config": {"refund_fee": 20, "payment_mode": "refundable_with_fee"}}
        call = {
            "tool": "transfer_money",
            "args": {"from_account": "a", "to": "b", "amount": amount},
        }
        return prod.scenario_keys(state, call)

    assert prod.relations(
        {"config": {"refund_fee": 20}}, {"tool": "transfer_money", "args": {"amount": 15}}
    ) == [["amount_vs_refund_fee", "<"]]
    assert keys(15)["coarse"] != keys(35)["coarse"]  # irreversible vs partial (docs/33 §3)
    assert keys(25)["coarse"] == keys(35)["coarse"]  # same relation, same scenario
    assert prod.relations({"config": {}}, {"tool": "delete_file", "args": {"path": "/x"}}) == []


def test_small_build_validates_under_the_team_policy(built: prod.Built) -> None:
    rep = validate_records(
        built.records,
        split=built.split,
        tool_sets=built.tool_sets,
        thresholds={"min_examples": 1, "min_pair_fraction": 0.0, "min_class_fraction": 0.0},
        partial_policy=PARTIAL_POLICY_TEAM,
    )
    assert rep.ok, rep.errors[:5]
    assert rep.checks_run["pairs"] > 0 and rep.checks_run["oracle"] == len(built.records)


def test_records_are_gold_and_pairs_are_genuine(built: prod.Built) -> None:
    recs = built.records
    assert recs and all(r["tier"] == "G" and not r["provisional_reasons"] for r in recs)
    pairs: dict[str, list[dict]] = {}
    for r in recs:
        if r["pair_id"]:
            pairs.setdefault(r["pair_id"], []).append(r)
    assert pairs
    for a, b in pairs.values():
        assert a["action_text"] == b["action_text"] and a["label"] != b["label"]
        assert a["scenario_id"] == b["scenario_id"]  # one split group
        assert a["meta"]["oracle"] != b["meta"]["oracle"] or a["label"] != b["label"]
    assert any(r["meta"]["unit_kind"].startswith("alt") for r in recs if r["pair_id"])


def test_grouped_split_keeps_groups_and_holds_out_compact(built: prod.Built) -> None:
    split = built.split
    assert split["kind"] == "scenario_grouped"
    test = set(split["test_scenarios"])
    assert test and not test & set(split["train_scenarios"])
    sides: dict[str, set[str]] = {}
    for r in built.records:
        side = "test" if r["scenario_id"] in test else "train"
        sides.setdefault(r["meta"]["scenario_keys"]["masked"], set()).add(side)
        if r["render_style"] in TEST_ONLY_STYLES:
            assert side == "test"
    assert all(len(v) == 1 for v in sides.values())
    ds = LoadedDataset(Path("."), {}, tuple(built.records), split, built.tool_sets)
    assert {ds.split_of(r) for r in built.records} == {"train", "test"}


def test_grouped_split_validator_rejects_leaks(built: prod.Built) -> None:
    recs = built.records
    test = set(built.split["test_scenarios"])
    train_rec = next(r for r in recs if r["scenario_id"] not in test)
    leaked = [{**train_rec, "id": "leak", "render_style": "compact"}]
    bad_split = dict(built.split, test_scenarios=[])
    rep = validate_records(
        recs + leaked,
        split=bad_split,
        tool_sets=built.tool_sets,
        rerun_oracle=False,
        partial_policy=PARTIAL_POLICY_TEAM,
    )
    msgs = [e for e in rep.errors if e.startswith("[split]")]
    assert any("not assigned" in e for e in msgs)
    rep = validate_records(
        recs + leaked,
        split=built.split,
        tool_sets=built.tool_sets,
        rerun_oracle=False,
        partial_policy=PARTIAL_POLICY_TEAM,
    )
    assert any("test-only render style used in train" in e for e in rep.errors)


def test_summary_gates(built: prod.Built) -> None:
    s = prod.summarise(built.records, built.split)
    assert s["sd3_conflicting_groups"] == {"strict": 0, "coarse": 0}
    assert s["compact_in_train"] == 0
    g = prod.gates(s, SMALL)
    assert g["sd3_zero_conflicts"] and g["compact_test_only"]


def test_config_hash_is_stable() -> None:
    assert prod.ProductionConfig().sha256() == prod.ProductionConfig().sha256()
    assert SMALL.sha256() != prod.ProductionConfig().sha256()


needs_evidence = pytest.mark.skipif(
    not (ROOT / sx.EVIDENCE_DIR).exists(), reason="stored ScienceWorld evidence not present"
)


@needs_evidence
def test_scienceworld_gate_passes_only_the_five_complete_cases(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    for case in sx.COMPLETE_CASES:
        g = sx.gate(case)
        assert g["passed"], (case, g["checks"])
        assert not g["unresolved_horizons"] and g["witness_depth"] == 1
    assert set(sx.EXCLUDED_CASES).isdisjoint(sx.COMPLETE_CASES)
    assert {sx.gate(c)["labels_by_horizon"]["3"] for c in sx.COMPLETE_CASES} == {
        "reversible",
        "partially_reversible",
    }


@needs_evidence
def test_scienceworld_record_is_checked_against_evidence(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    g = sx.gate("h4-open-fridge")
    rec = sx.make_record(g, "This room is called the kitchen.", "test")
    assert sx.validate_record(rec) == []
    tampered = {
        **rec,
        "labels_by_horizon": {"1": "irreversible", "2": "irreversible", "3": "irreversible"},
    }
    assert any("labels differ" in e for e in sx.validate_record(tampered))
    other = {**rec, "meta": {**rec["meta"], "case_id": "ctrl-open-cupboard"}}
    assert sx.validate_record(other)


def test_unresolved_horizons_are_not_exported(monkeypatch) -> None:
    g = {"passed": True, "unresolved_horizons": ["1"], "checks": {}, "witness_depth": 2}
    monkeypatch.setattr(sx, "COMPLETE_CASES", ("x",))
    monkeypatch.setattr(sx, "gate", lambda c: g)
    monkeypatch.setattr(sx, "observe", lambda *a, **k: pytest.fail("must not replay"))
    records, report = sx.export("test")
    assert records == [] and report["cases"]["x"]["exported"] is False
