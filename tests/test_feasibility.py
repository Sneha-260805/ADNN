"""Phase 5A: dataset-composition validators, pilot evidence audit and the
measurement-symmetry harness (no Java; docs/25)."""

from __future__ import annotations

from typing import Any

import adnn.scienceworld.label_evidence as label_evidence
from adnn.feasibility.composition import (
    class_balance,
    duplicate_templates,
    minimal_pairs,
    normalise,
    split_leakage,
    template_signature,
)
from adnn.feasibility.pilot_audit import (
    COMPLETE_IMPOSSIBILITY,
    UNSUPPORTED,
    VERIFIED_EXACT,
    oq24_widened,
    summarise,
    support,
)
from adnn.sandbox import restoration
from adnn.scienceworld.measurement_symmetry import (
    SymmetricRun,
    compare_protocols,
    symmetric_protocol,
)


def _r(rid: str, label: str, *, pair: str | None = None, scen: str = "s1", action: str = "a",
       prov: bool = False, fam: str = "f1", verb: str = "v",
       state: str = "x") -> dict[str, Any]:  # fmt: skip
    return {"id": rid, "label": label, "pair_id": pair, "scenario_id": scen,
            "action_text": action, "label_provisional": prov, "template_id": fam,
            "action_verb": verb, "state_text": state, "environment": "sandbox"}  # fmt: skip


# -- minimal pairs ------------------------------------------------------------------------------
def test_genuine_pairs_need_identical_action_bytes_different_justified_labels() -> None:
    recs = [
        _r("1", "reversible", pair="p1"), _r("2", "irreversible", pair="p1"),
        _r("3", "reversible", pair="p2"), _r("4", "reversible", pair="p2"),
        _r("5", "reversible", pair="p3"), _r("6", "partially_reversible", pair="p3", prov=True),
        _r("7", "reversible", pair="p4", action="a"), _r("8", "irreversible", pair="p4",
                                                          action="a "),
        _r("9", "reversible"), _r("10", "irreversible"),
    ]  # fmt: skip
    out = minimal_pairs(recs)
    assert out["group_kinds"] == {"genuine": 1, "same_label": 1,
                                  "label_difference_not_justified": 1, "malformed": 1}  # fmt: skip
    assert out["genuine_member_fraction"] == 0.2
    assert out["any_pair_member_fraction"] == 0.8
    lenient = minimal_pairs(recs, justified=lambda r: True)
    assert lenient["group_kinds"]["genuine"] == 2


def test_cross_scenario_group_is_malformed() -> None:
    recs = [_r("1", "reversible", pair="p", scen="a"), _r("2", "irreversible", pair="p", scen="b")]
    assert minimal_pairs(recs)["group_kinds"] == {"malformed": 1}


# -- duplicates and leakage ---------------------------------------------------------------------
def test_template_signature_masks_surface_values() -> None:
    a = _r("1", "reversible", state="file /home/u/a.txt rev 3", action='{"path": "/x/y"}')
    b = _r("2", "reversible", state="file /home/u/b.csv rev 7", action='{"path": "/q"}')
    c = _r("3", "reversible", state="backup missing", action='{"path": "/q"}')
    assert template_signature(a) == template_signature(b) != template_signature(c)
    assert normalise("Send 40 to bob@example.com") == "send <num> to <email>"
    dup = duplicate_templates([a, {**b, "scenario_id": "s2"}, c])
    assert dup["n_signatures"] == 2 and dup["signatures_shared_across_scenarios"] == 1


def test_split_leakage_reports_overlap_and_verb_shortcut() -> None:
    recs = [
        _r("1", "reversible", fam="f1", scen="a", verb="delete", state="s"),
        _r("2", "reversible", fam="f1", scen="a", verb="delete", state="t"),
        _r("3", "irreversible", fam="f2", scen="b", verb="pay", state="u"),
        _r("4", "reversible", fam="f3", scen="c", verb="delete", state="s"),
        _r("5", "irreversible", fam="f3", scen="c", verb="pay", state="z"),
    ]  # fmt: skip
    out = split_leakage(recs, ["f3"])
    assert out["group_disjoint"] and out["scenario_overlap"] == 0
    assert out["exact_input_overlap"] == 1  # record 4 repeats record 1's input
    assert out["verb_majority_accuracy_on_test"] == 1.0
    bal = class_balance(recs)
    assert bal["all"]["reversible"] == (3, 0.6)


# -- pilot evidence audit -----------------------------------------------------------------------
def _sandbox_record(bin_enabled: bool) -> dict[str, Any]:
    import random

    from adnn.dataset.pilot import act_delete_a, build_world, sample_params

    p = sample_params(random.Random("test"))
    call = act_delete_a(p)
    return {
        "id": f"t-{bin_enabled}",
        "state_struct": build_world(p, bin_on=bin_enabled, versioning=False).to_dict(),
        "action_call": {"tool": call.tool, "args": dict(call.args)},
        "label": "reversible" if bin_enabled else "irreversible",
    }


def test_support_classifies_witness_and_complete_impossibility() -> None:
    rev = support(_sandbox_record(True))
    assert rev["agrees"] and rev["support"] == VERIFIED_EXACT
    irr = support(_sandbox_record(False))
    assert irr["agrees"] and irr["support"] == COMPLETE_IMPOSSIBILITY and irr["search_complete"]


def test_oq24_widening_is_scoped_and_summary_counts() -> None:
    original = restoration.argument_pool
    with oq24_widened():
        assert restoration.argument_pool is not original
    assert restoration.argument_pool is original
    rows = [
        {"id": "a", "stored_label": "reversible", "agrees": True, "support": VERIFIED_EXACT,
         "provisional_reasons": [], "oq21_changes_label": False},
        {"id": "b", "stored_label": "irreversible", "agrees": True, "support": UNSUPPORTED,
         "provisional_reasons": ["x"], "oq21_changes_label": True, "oq24_changes_label": True},
    ]  # fmt: skip
    s = summarise(rows)
    assert s["fully_supported_non_provisional"] == 1
    assert s["oq24_changed_ids"] == ["b"] and s["oq21_label_changes"] == 1


# -- measurement symmetry -----------------------------------------------------------------------
def test_symmetric_protocol_swaps_runner_only_inside_block() -> None:
    original = label_evidence._Run
    with symmetric_protocol() as runs:
        run = label_evidence._Run(None, None)  # type: ignore[arg-type]
        assert isinstance(run, SymmetricRun) and runs == [run]
    assert label_evidence._Run is original


def _doc(outcome: str, level: str = "exact") -> dict[str, Any]:
    att = {"path": ["close x"], "assessments": {"0.01": {"canonical_level": level,
                                                          "concepts": []}}}  # fmt: skip
    return {"evidence": {"attempts": [att]}, "decision": {"outcome": outcome, "witness": None}}


def test_compare_protocols_flags_any_transition_or_outcome_difference() -> None:
    same = [{"enumerated_at": 1, "equal": True}]
    ok = compare_protocols(_doc("eligible_reversible"), _doc("eligible_reversible"), same)
    assert not ok["affected"] and ok["n_counterfactuals_with_enumeration"] == 1
    diff = [{"enumerated_at": 1, "equal": False}]
    assert compare_protocols(_doc("r"), _doc("r"), diff)["affected"]
    assert compare_protocols(_doc("r"), _doc("r", "none"), same)["affected"]
    assert compare_protocols(_doc("r"), _doc("u"), same)["affected"]
