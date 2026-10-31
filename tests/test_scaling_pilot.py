"""Phase 5B: frozen scaling-pilot design, executable stop conditions and structural
uniqueness (no Java; docs/26)."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from adnn.dataset.pilot import FAMILIES
from adnn.dataset.schema import PROVISIONAL_OQ21, PROVISIONAL_PARTIAL
from adnn.feasibility import stop_conditions as sc
from adnn.feasibility.scaling_pilot import (
    ALL_FAMILIES,
    EXISTING_PER_DOMAIN,
    NEW_FAMILIES,
    _finish,
    build_manifest,
    freeze_split,
    generate,
    select_existing,
    structure_signature,
    sw_sampler_assessment,
    verify_manifest,
)

SW = {"decision": "stop"}


# -- frozen design ------------------------------------------------------------------------------
def test_manifest_is_deterministic_and_tamper_evident() -> None:
    a, b = build_manifest("c", SW), build_manifest("c", SW)
    assert a == b and verify_manifest(a)
    bad = copy.deepcopy(a)
    bad["sandbox"]["scenarios_per_family"] = 6
    assert not verify_manifest(bad)
    with pytest.raises(ValueError, match="hash mismatch"):
        generate(bad)


def test_family_allocation_and_split_are_seeded_per_domain() -> None:
    chosen = select_existing(20261101)
    assert chosen == select_existing(20261101)
    for domain, k in EXISTING_PER_DOMAIN.items():
        assert sum(ALL_FAMILIES[f].domain == domain for f in chosen) == k
    assert set(chosen) <= {f.family_id for f in FAMILIES}
    split = freeze_split([*chosen, *(f.family_id for f in NEW_FAMILIES)], 20261101)
    assert len(split["test_families"]) == 3
    assert {ALL_FAMILIES[f].domain for f in split["test_families"]} == {"files", "email", "money"}
    assert not set(split["test_families"]) & set(split["train_families"])


def test_new_families_use_existing_tools_and_one_pivot() -> None:
    for fam in NEW_FAMILIES:
        assert fam.pivot_scope == "config.payment_cancel_window_s"
        assert fam.family_id not in {f.family_id for f in FAMILIES}


def test_sw_assessment_counts_genuinely_distinct_families() -> None:
    a = sw_sampler_assessment()
    assert a["n_distinct"] == 7 and a["required"] == 8
    assert a["physical_family_of_class"]["move"] == a["physical_family_of_class"]["pick_up"]
    assert a["decision"].startswith("stop") and a["task_cap_satisfiable"] is False


def test_finish_drops_pending_partial_flag_and_tiers_oq21() -> None:
    base: dict[str, Any] = {"provisional_reasons": [PROVISIONAL_PARTIAL], "meta": {}}
    g = _finish(copy.deepcopy(base))
    assert g["tier"] == "G" and not g["label_provisional"] and g["sensitivity_group"] is None
    p = _finish({"provisional_reasons": [PROVISIONAL_PARTIAL, PROVISIONAL_OQ21], "meta": {}})
    assert p["tier"] == "P" and p["sensitivity_group"] == "OQ-21" and p["label_provisional"]
    assert "ADR-0006 D11" in p["meta"]["partial_definition"]


def test_structure_signature_ignores_surface_values_not_configuration() -> None:
    def rec(path: str, amount: int, mode: str) -> dict[str, Any]:
        return {"state_struct": {"config": {"payment_mode": mode}, "clock_s": 0,
                                 "files": [{"path": path, "content": "x", "revision": amount}]},
                "action_call": {"tool": "delete_file", "args": {"path": path}}}  # fmt: skip

    assert structure_signature(rec("/a", 3, "final")) == structure_signature(rec("/b", 9, "final"))
    assert structure_signature(rec("/a", 3, "final")) != structure_signature(
        rec("/a", 3, "cancellable")
    )


# -- stop conditions ----------------------------------------------------------------------------
def test_sw_conditions_not_evaluable_without_candidates_and_checkpoint() -> None:
    assert not sc.s1_sw_yield(None, None).evaluable
    assert not sc.s1_sw_yield(40, 1).evaluable  # before the 80-candidate checkpoint
    assert sc.s1_sw_yield(80, 7).triggered and not sc.s1_sw_yield(80, 8).triggered
    assert not sc.s3_rubric_sensitivity(None, 0).evaluable
    assert sc.s3_rubric_sensitivity(2, 10).triggered


def test_replication_and_rederivation_tolerate_no_failure() -> None:
    assert sc.s2_replication(1).triggered and not sc.s2_replication(0).triggered
    assert sc.s2_replication(0, n_affected=1, n_cases=10).triggered
    assert sc.s7_rederivation(1).triggered and not sc.s7_rederivation(0).triggered


def test_family_concentration_and_thresholds() -> None:
    recs = [{"label": "irreversible", "template_id": f} for f in "aaaabbbccc"]
    assert not sc.s4_family_concentration(recs).triggered  # largest share 0.4 = threshold
    recs += [{"label": "irreversible", "template_id": "a"}] * 3
    out = sc.s4_family_concentration(recs)
    assert out.triggered and out.value["irreversible"][0] == "a"
    assert sc.s5_effective_fraction(0.59).triggered and not sc.s5_effective_fraction(0.6).triggered
    assert sc.s6_strict_pairs(0.29).triggered and not sc.s6_strict_pairs(0.30).triggered
    s = sc.summary([sc.s1_sw_yield(None, None), sc.s6_strict_pairs(0.1)])
    assert s["triggered"] == ["S6"] and s["not_evaluable"] == ["S1"]
