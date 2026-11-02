"""Dataset v2.0 families (ADR-0010): strict pairs, gold labels, unchanged v1.0 config."""

from __future__ import annotations

import json
import random
from dataclasses import replace
from pathlib import Path

import pytest

from adnn.dataset import families_v2 as v2
from adnn.dataset import pilot
from adnn.dataset import production as prod
from adnn.dataset.validation import PARTIAL_POLICY_TEAM, flat_diff, validate_records

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [f for f in v2.FAMILIES if f.pivot is not None]
SINGLES = {
    "v2s1_restore_backup_over_edit": "irreversible",
    "v2s2_revert_after_edit": "irreversible",
    "v2s3_restore_from_bin": "partially_reversible",
}


def _gold(state, call) -> str | None:
    u = prod.Unit("t", 0, "t", state, call, "task", None)
    prod.label(u)
    return None if u.reason or u.tier != "G" else u.labels["3"]


@pytest.mark.parametrize("fam", PAIRS, ids=lambda f: f.family_id)
def test_pair_family_is_strict_gold_and_flips(fam) -> None:
    for i in range(2):
        rng = random.Random(f"t|{fam.family_id}|{i}")
        p = pilot.sample_params(rng)
        for base in fam.bases:
            a, b = (v2.state_for(fam, p, {**base, fam.pivot: v}) for v in fam.pivot_values)
            assert a is not None and b is not None
            diff = flat_diff(a.to_dict(), b.to_dict())
            scope = v2.SCOPES[fam.pivot]
            inside = [d == scope or d.startswith((scope + ".", scope + "[")) for d in diff]
            assert diff and all(inside), diff
            labels = (_gold(a, fam.action(p)), _gold(b, fam.action(p)))
            assert labels == fam.expected, (base, labels)


@pytest.mark.parametrize("fid", sorted(SINGLES))
def test_non_pair_situations_are_gold(fid) -> None:
    fam = next(f for f in v2.FAMILIES if f.family_id == fid)
    p = pilot.sample_params(random.Random(f"t|{fid}"))
    for base in fam.bases:
        st = v2.state_for(fam, p, base)
        assert st is not None and _gold(st, fam.action(p)) == SINGLES[fid], base


def test_v1_config_unchanged_against_frozen_manifest() -> None:
    m = json.loads((ROOT / "docs/preregistration/production_manifest_amend1.json").read_text())
    assert prod.ProductionConfig().sha256() == m["generation"]["config_sha256"]
    assert v2.config().seed == prod.ProductionConfig().seed
    assert v2.config().generator_version == v2.GENERATOR_VERSION


def test_v2_config_differs_from_v1_only_in_version_and_cap() -> None:
    v1, new = prod.ProductionConfig().to_dict(), v2.config().to_dict()
    changed = {k for k in v1 if v1[k] != new[k]}
    assert changed == {"generator_version", "surface_variants"}
    assert (v1["surface_variants"], new["surface_variants"]) == (4, 6)


def _rec(rid: str, coarse: str, pair: str | None = None) -> dict:
    return {"id": rid, "environment": "sandbox", "pair_id": pair,
            "meta": {"scenario_keys": {"coarse": coarse}}}  # fmt: skip


def test_capped_subset_caps_scenarios_and_keeps_pairs_whole() -> None:
    recs = [_rec(f"s{i}", "A") for i in range(5)]
    recs += [_rec("p1a", "A", "p1"), _rec("p1b", "A", "p1")]
    recs += [_rec("p2a", "B", "p2"), _rec("p2b", "B", "p2"), _rec("b1", "B")]
    recs += [{"id": "sw", "environment": "scienceworld", "pair_id": None, "meta": {}}]
    out = v2.capped_subset(recs, 3)
    per: dict[str, int] = {}
    for r in out:
        key = r["meta"].get("scenario_keys", {}).get("coarse", r["id"])
        per[key] = per.get(key, 0) + 1
    assert max(per.values()) <= 3 and "sw" in per
    ids = {r["id"] for r in out}
    for a, b in (("p1a", "p1b"), ("p2a", "p2b")):
        assert (a in ids) == (b in ids)
    assert v2.capped_subset(list(reversed(recs)), 3) == out


def test_capped_subset_pair_across_coarse_keys_is_atomic() -> None:
    """Regression (v2.0 manifest amendment 1): pair members with DIFFERENT coarse keys."""
    recs = [_rec(f"a{i}", "A") for i in range(3)]  # singles fill scenario A to the cap
    recs += [_rec("p1a", "A", "p1"), _rec("p1b", "B", "p1")]  # no room in A: drop both
    recs += [_rec("p2a", "C", "p2"), _rec("p2b", "D", "p2")]  # room in C and D: keep both
    recs += [_rec(f"e{i}", "E") for i in range(2)]
    recs += [_rec("p3a", "E", "p3"), _rec("p3b", "F", "p3")]  # E would reach 3: keep both
    recs += [_rec("p4a", "E", "p4"), _rec("p4b", "G", "p4")]  # E would reach 4: drop both
    out = v2.capped_subset(recs, 3)
    ids = {r["id"] for r in out}
    assert ids == {"a0", "a1", "a2", "p2a", "p2b", "e0", "e1", "p3a", "p3b"}
    per: dict[str, int] = {}
    for r in out:
        per[r["meta"]["scenario_keys"]["coarse"]] = (
            per.get(r["meta"]["scenario_keys"]["coarse"], 0) + 1
        )
    assert max(per.values()) <= 3
    pairs: dict[str, int] = {}
    for r in out:
        if r["pair_id"]:
            pairs[r["pair_id"]] = pairs.get(r["pair_id"], 0) + 1
    assert all(n == 2 for n in pairs.values())


def test_small_v2_build_validates() -> None:
    cfg = replace(
        v2.config(),
        draws_per_family=6,
        legacy_families=("f01_delete_bin",),
        link_families=(),
        family_share_cap=0.5,
        split_search=50,
    )
    built = v2.build(cfg, "test")
    fams = {r["template_id"] for r in built.records}
    assert fams & set(v2.FAMILY_IDS)
    assert any(r["pair_id"] and r["template_id"] in v2.FAMILY_IDS for r in built.records)
    assert all(r["meta"]["generator_version"] == v2.GENERATOR_VERSION for r in built.records)
    rep = validate_records(
        built.records,
        split=built.split,
        tool_sets=built.tool_sets,
        thresholds={"min_examples": 1, "min_pair_fraction": 0.0, "min_class_fraction": 0.0},
        partial_policy=PARTIAL_POLICY_TEAM,
    )
    assert rep.ok, rep.errors[:5]
