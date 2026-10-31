"""Phase 4F: query-order audit, targeted contrasts, certificates and expanded search (no Java).

All simulator behaviour comes from the MiniKitchen fake (docs/22 §8).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from adnn.scienceworld.canonical import CanonicalState
from adnn.scienceworld.certificates import (
    CERTIFICATES,
    MET,
    NOT_APPLICABLE,
    NOT_MET,
    check_burn,
    check_eat,
    check_mix_salt,
)
from adnn.scienceworld.contrasts import (
    GOLD_STATUS,
    KINDS,
    ContrastSpec,
    IntendedChange,
    build_contrast,
    contrast_specs,
    evaluate_contrast,
    matched_under,
    stochastic_exposure,
    validate_contrast_pair,
)
from adnn.scienceworld.expanded_search import candidate_pool, expanded_search
from adnn.scienceworld.provisional import IDLE_ACTION, FamilySpec, content_sha256
from adnn.scienceworld.query_audit import (
    BASELINE,
    CONDITIONS,
    AuditScenario,
    audit_scenario,
)
from adnn.scienceworld.replay import FIRST_TICK_PREPARATION, ReplayRecipe
from scienceworld_restoration_fake import MiniKitchen

FAKE = FamilySpec("fake-kitchen", "1-1", 0, "")
SCENARIO = AuditScenario(
    "fake", "1-1", 0, ("open cupboard", "move ceramic cup to sink", "activate sink"), ""
)


class EnumerationDrawsKitchen(MiniKitchen):
    """Valid-action enumeration consumes a shared 'RNG' that a later tick reads (like Bee.tick)."""

    def load(self, *args: Any, **kwargs: Any) -> None:
        self.draws = 0  # reseeded at load, as the JVM global Random is
        super().load(*args, **kwargs)

    def get_valid_action_object_combinations_with_templates(self) -> list[dict[str, Any]]:
        self.draws += 1
        return super().get_valid_action_object_combinations_with_templates()

    def _tick(self) -> None:
        super()._tick()
        if getattr(self, "draws", 0) % 2:
            self.objects["15"]["propMaterial"]["temperatureC"] += 1.0  # the apple


# -- Step 2: query-order audit ---------------------------------------------------------------
def test_query_audit_deterministic_fake_is_query_independent() -> None:
    audit = audit_scenario(SCENARIO, repeats=2, shared=True, backend_factory=MiniKitchen)
    rows = audit.summary()["comparisons"]
    assert len(rows) == 2 * len(CONDITIONS) + len(CONDITIONS) - 1
    assert all(r["transitions_equal_all_k"] and r["observations_equal_all_k"] for r in rows)
    assert audit.summary()["baseline"]["condition"] == BASELINE


def test_query_audit_detects_enumeration_that_consumes_randomness() -> None:
    audit = audit_scenario(
        SCENARIO, repeats=1, shared=False, backend_factory=EnumerationDrawsKitchen
    )
    by_cond = {r["condition"]: r for r in audit.summary()["comparisons"]}
    assert by_cond["B_observe"]["transitions_equal_all_k"]
    for c in ("C_enumerate", "D1_observe_then_enumerate", "D2_enumerate_then_observe"):
        assert not by_cond[c]["transitions_equal_all_k"]
        assert by_cond[c]["first_k_state_differs"] == 1
        changed = {o for k in by_cond[c]["per_k"] for o in k["changed_objects"]}
        assert changed == {"apple"}


# -- Step 3/4: contrasts ---------------------------------------------------------------------
def test_contrast_specs_are_controlled_and_bee_free() -> None:
    specs = contrast_specs()
    assert len(specs) == 16 and {s.kind for s in specs} == set(KINDS)
    assert len({s.contrast_id for s in specs}) == len(specs)
    for s in specs:
        ha, hb = s.histories()
        assert len(ha) == len(hb) and ha != hb
        assert "bee" not in s.target and not any("bee" in a for a in ha + hb)
        assert set(ha[len(s.shared) :]) - set(s.variant_a) <= {IDLE_ACTION}


def test_contrast_spec_requires_intended_difference() -> None:
    with pytest.raises(ValueError):
        ContrastSpec("x", "source_state", FAKE, (), (), ("activate sink",), "t", (), "d")
    with pytest.raises(ValueError):
        ContrastSpec("x", "nope", FAKE, (), (), (), "t", (IntendedChange("a", "b"),), "d")


SOURCE = ContrastSpec(
    "src", "source_state", FAKE, ("open cupboard",), (), ("activate sink",),
    "move ceramic cup to sink", (IntendedChange("sink", "propDevice.isActivated"),), "sink",
)  # fmt: skip
LOCATION = ContrastSpec(
    "loc", "object_location", FAKE, ("open cupboard",), ("move ceramic cup to table",),
    ("move ceramic cup to sink",), "activate sink", (IntendedChange("ceramic cup", "parent"),),
    "cup location",
)  # fmt: skip


@pytest.fixture(scope="module")
def built() -> dict[str, Any]:
    out = {}
    for spec in (SOURCE, LOCATION):
        pair, recs, failure = build_contrast(spec, backend_factory=MiniKitchen)
        assert failure is None
        out[spec.contrast_id] = (spec, pair, recs)
    return out


def test_source_contrast_is_a_restoration_contrast_candidate(built: dict[str, Any]) -> None:
    _, pair, _ = built["src"]
    assert pair["level"] == "restoration_contrast_candidate"
    assert pair["restoration_contrast_methods"] == ["exact", "tol_0.01C", "tol_0.1C"]
    assert pair["gold_status"] == GOLD_STATUS == "not_a_gold_minimal_pair"
    assert pair["state_contrast"]["intended_changes"][0]["object"] == "sink"
    assert validate_contrast_pair(pair) == []


def test_location_contrast_is_structural_only(built: dict[str, Any]) -> None:
    _, pair, _ = built["loc"]
    assert pair["level"] == "structural_candidate" and pair["rejection_reasons"] == []
    assert not any(v["differs"] for v in pair["restoration_comparison"].values())
    assert validate_contrast_pair(pair) == []


def _states(recs: list[tuple[dict[str, Any], bytes]]) -> list[CanonicalState]:
    import json

    from adnn.scienceworld.canonical import RawState, canonicalize

    return [canonicalize(RawState.from_dict(json.loads(b)["raw"])) for _, b in recs]


def test_evaluate_contrast_rejects_text_and_referent_mismatch(built: dict[str, Any]) -> None:
    spec, _, recs = built["src"]
    (ra, _), (rb, _) = recs
    sa, sb = _states(recs)
    rb2 = copy.deepcopy(rb)
    rb2["target"]["action"] = spec.target + " "
    rb2["target"]["obj_ids"] = ["999"]
    pair = evaluate_contrast(spec, ra, rb2, sa, sb)
    assert pair["level"] == "rejected"
    assert {"byte_identical_target", "same_referents"} <= set(pair["rejection_reasons"])
    assert pair["restoration_contrast_methods"] == []


def test_evaluate_contrast_rejects_stochastic_exposure(built: dict[str, Any]) -> None:
    spec, _, recs = built["src"]
    (ra, _), (rb, _) = recs
    sa, sb = _states(recs)
    objs = dict(sb.objects)
    objs["900"] = {"name": "bee 0", "parent": "2", "isDeleted": False}
    objs["901"] = {"name": "bee hive", "parent": "2", "isDeleted": False}
    sb2 = CanonicalState(objs, sb.world, sb.visible_doors)
    assert stochastic_exposure(sb2) == ["bee 0 in kitchen"]
    assert evaluate_contrast(spec, ra, rb, sa, sb2)["rejection_reasons"] == [
        "no_stochastic_exposure"
    ]


def test_matched_under_never_treats_missing_evidence_as_mismatch() -> None:
    rec = {"restoration_evidence": {"best_counterfactual_match_level": "not_compared"}}
    assert matched_under(rec, "exact") is None
    rec["restoration_evidence"]["best_counterfactual_match_level"] = "within_0.1C"
    assert (matched_under(rec, "exact"), matched_under(rec, "tol_0.1C")) == (False, True)


def test_validate_contrast_pair_detects_tampering(built: dict[str, Any]) -> None:
    _, pair, _ = built["src"]
    bad = copy.deepcopy(pair)
    bad["gold_status"] = "gold_minimal_pair"
    bad["checks"]["valid_in_both"] = False
    bad["content_sha256"] = content_sha256(bad)
    errors = validate_contrast_pair(bad)
    assert "claims gold status" in errors
    assert "structural flag inconsistent with checks" in errors
    tampered = copy.deepcopy(pair)
    tampered["level"] = "gold"
    assert "content_checksum" in validate_contrast_pair(tampered)


# -- Step 5: expanded search -----------------------------------------------------------------
RECIPE = ReplayRecipe(task="1-1", variation=0, preparation=FIRST_TICK_PREPARATION)


def test_expanded_search_finds_inverse_and_never_claims_irreversibility() -> None:
    out = expanded_search(RECIPE, "open cupboard", backend_factory=MiniKitchen)
    assert out["matches"]["exact"] == ["close cupboard"] and out["restricted"]
    sink = expanded_search(RECIPE, "activate sink", backend_factory=MiniKitchen)
    assert sink["best_match_level"] == "none" and not sink["exhaustive"]
    assert "not evidence" in sink["failed_search_meaning"]
    b = sink["branching"]
    assert b["valid_actions"] >= b["agent_restoration_allowed"] >= b["object_local"] > 0


def test_expanded_search_sampling_is_deterministic_and_reported() -> None:
    a = expanded_search(RECIPE, "activate sink", max_candidates=5, backend_factory=MiniKitchen)
    b = expanded_search(RECIPE, "activate sink", max_candidates=5, backend_factory=MiniKitchen)
    assert a["sampled"] and a["n_candidates_tried"] == 5
    assert [c["action"] for c in a["candidates"]] == [c["action"] for c in b["candidates"]]


def test_candidate_pool_excludes_helpers_and_unrelated_objects() -> None:
    from adnn.scienceworld.env import ActionTemplate

    objs = {"5": {"name": "cup", "parent": "2"}, "7": {"name": "jar", "parent": "2"}}
    s = CanonicalState({**objs, "2": {"name": "kitchen"}}, {}, {})
    templates = [
        ActionTemplate("look at cup", 1, ("5",)),
        ActionTemplate("pick up cup", 2, ("5",)),
        ActionTemplate("pick up jar", 2, ("7",)),
        ActionTemplate("open thing", 3, ("8",)),
        ActionTemplate("open thing", 3, ("9",)),
    ]
    local, counts = candidate_pool(templates, s, s, ("5",))
    assert local == ["pick up cup"]
    assert counts == {
        "valid_actions": 4, "unambiguous": 3, "agent_restoration_allowed": 2, "object_local": 1,
    }  # fmt: skip


# -- Step 6: certificates --------------------------------------------------------------------
def _obj(name: str, parent: str = "2", **fields: Any) -> dict[str, Any]:
    return {"name": name, "parent": parent, "isDeleted": False, **fields}


def _state(objs: dict[str, dict[str, Any]]) -> CanonicalState:
    return CanonicalState({"2": _obj("kitchen", "1"), **objs}, {}, {})


SALT = {"propMaterial.substanceName": "sodium chloride"}


def test_mix_salt_preconditions() -> None:
    s0 = _state({"8": _obj("sodium chloride", "7", **SALT), "9": _obj("water", "7")})
    s1 = _state({"20": _obj("salt water", "7")})
    assert check_mix_salt(s0, "mix jar", s1, counterfactual=s0).status == MET
    unchecked = check_mix_salt(s0, "mix jar", s1)
    assert unchecked.status == MET and any("definition B" in c for c in unchecked.caveats)
    other = _state({"20": _obj("salt water", "7"), "30": _obj("sodium chloride", "4", **SALT)})
    assert check_mix_salt(s0, "mix jar", other).status == NOT_MET
    assert check_mix_salt(s0, "activate sink", s1).status == NOT_APPLICABLE
    assert check_mix_salt(s1, "mix jar", s1).status == NOT_APPLICABLE
    assert check_mix_salt(s0, "mix jar", s1, counterfactual=s1).status == NOT_MET


def test_burn_preconditions() -> None:
    cold = {"propMaterial.hasCombusted": False}
    hot = {"propMaterial.hasCombusted": True}
    s0, s1 = _state({"5": _obj("paper", **cold)}), _state({"5": _obj("paper", **hot)})
    assert check_burn(s0, "use lighter on paper", s1, counterfactual=s0).status == MET
    assert check_burn(s0, "use lighter on paper", s1, counterfactual=s1).status == NOT_MET
    assert check_burn(s0, "look at paper", s0).status == NOT_APPLICABLE


def test_eat_identity_and_structural_parts() -> None:
    s0 = _state({"15": _obj("apple")})
    s1 = _state({})
    identity, structural = check_eat(s0, "eat apple", s1, ("15",))
    assert identity.status == MET and structural.status == MET
    plant = {"propLife.lifeformType": "plant", "propLife.isDead": False}
    s1p = _state({"40": _obj("apple tree", **plant)})
    assert check_eat(s0, "eat apple", s1p, ("15",))[1].status == NOT_MET
    assert check_eat(s0, "eat apple", s0, ("15",))[0].status == NOT_MET
    assert check_eat(s0, "open cupboard", s1, ("15",))[0].status == NOT_APPLICABLE


def test_certificates_are_not_proofs_or_labels() -> None:
    for c in CERTIFICATES:
        d = c.to_dict()
        assert d["is_formal_proof"] is False and d["issues_labels"] is False
        assert d["audited_source"] and d["counterexamples"] and d["holds_under"]
    assert check_burn(_state({}), "x", _state({})).to_dict()["is_label"] is False


def test_select_candidates_keeps_registry_inverses_and_rare_verbs() -> None:
    from adnn.scienceworld.expanded_search import select_candidates, verb_of

    local = [f"connect x{i} to freezer" for i in range(50)] + ["open freezer", "pick up jar"]
    chosen = select_candidates(local, ["open freezer", "not local"], 5, seed=0)
    assert len(chosen) == 5 and "open freezer" in chosen and "pick up jar" in chosen
    assert "not local" not in chosen
    assert chosen == select_candidates(local, ["open freezer"], 5, seed=0)
    assert verb_of("pick up jar") == "pick up" and verb_of("open freezer") == "open"


def test_expanded_search_reports_registry_inverse_as_original_set() -> None:
    out = expanded_search(RECIPE, "open cupboard", max_candidates=3, backend_factory=MiniKitchen)
    assert out["registry_inverses"] == ["close cupboard"]
    assert out["registry_best_match_level"] == "exact"
    assert any(c["source"] == "registry" for c in out["candidates"])
