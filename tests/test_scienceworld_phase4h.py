"""Phase 4H: pre-registration freezing, blinded packets, the rule-based declaration
generator, agreement metrics and the source audits (no Java; docs/24)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from adnn.scienceworld.admission import DECISION_RULE_VERSION
from adnn.scienceworld.canonical import CanonicalState
from adnn.scienceworld.certificate_audit import (
    PLANTLESS_ID,
    add_object_sites,
    check_eat_plantless,
    plant_closure,
    plant_like,
    reattachment_obligation,
)
from adnn.scienceworld.certificates import MET, NOT_APPLICABLE, NOT_MET
from adnn.scienceworld.declaration_reliability import (
    build_packet,
    compare,
    role_of,
    rubric_declaration,
    rubric_to_declaration,
)
from adnn.scienceworld.phase4h_cases import PHASE4H_CASES
from adnn.scienceworld.preregistration import (
    CATEGORIES,
    PHASE4G_COMMIT,
    Preregistration,
    manifest,
    verify_manifest,
)
from adnn.scienceworld.semantics import Declaration, PropertyRef, bind

PREREG = Path(__file__).resolve().parents[1] / "docs" / "preregistration"


def _o(name: str, parent: str | None, **fields: Any) -> dict[str, Any]:
    return {"name": name, "parent": parent, "isDeleted": False, **fields}


def _s(objs: dict[str, dict[str, Any]]) -> CanonicalState:
    base = {"1": _o("universe", None), "2": _o("kitchen", "1"), "3": _o("counter", "2")}
    return CanonicalState({**base, **objs}, {}, {})


KITCHEN = {
    "4": _o("bowl", "3"),
    "5": _o("banana", "4", **{"propMaterial.temperatureC": 10.0}),
    "6": _o("fridge", "2", **{"propContainer.isOpen": False}),
    "7": _o("wood cup", "6"),
    "8": _o("orange juice", "7", **{"propMaterial.temperatureC": 4.0,
                                    "propMaterial.stateOfMatter": "liquid"}),
    "9": _o("cup", "3"),
    "10": _o("cup", "6"),
    "11": _o("agent", "2"),
}  # fmt: skip


def _packet(target: str, ids: tuple[str, ...], state: CanonicalState | None = None) -> dict:
    s0 = state or _s(KITCHEN)
    return build_packet("P99", s0, room_uuid="2", target=target, target_ids=ids,
                        task_description="Your task is to boil water.", history=())  # fmt: skip


# -- pre-registration ---------------------------------------------------------------------------
def test_frozen_manifest_matches_current_records() -> None:
    assert verify_manifest(PHASE4H_CASES, PREREG / "phase4h_manifest.json") == []
    doc = json.loads((PREREG / "phase4h_manifest.json").read_text("utf-8"))
    assert doc["phase4g_commit"] == PHASE4G_COMMIT
    assert doc["decision_rule"] == DECISION_RULE_VERSION == "sw-admission-2"
    assert len(doc["records"]) == len(PHASE4H_CASES) >= 10


def test_any_declaration_edit_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    path.write_text(json.dumps(manifest(PHASE4H_CASES, {})), "utf-8")
    first = PHASE4H_CASES[0]
    decl = first.spec.declaration
    edited = replace(decl, required=(*decl.required[:-1], replace(decl.required[-1], weight=1)))
    changed = replace(first, spec=replace(first.spec, declaration=edited))
    assert verify_manifest((changed, *PHASE4H_CASES[1:]), path) == [first.case_id]
    assert verify_manifest(PHASE4H_CASES[1:], path) == [first.case_id]  # removal detected


def test_preregistration_requires_rationale_and_known_category() -> None:
    rec = PHASE4H_CASES[0]
    with pytest.raises(ValueError):
        replace(rec, property_rationale=rec.property_rationale[1:])
    with pytest.raises(ValueError):
        replace(rec, expected_category="easy")
    assert {r.expected_category for r in PHASE4H_CASES} == set(CATEGORIES)
    assert isinstance(rec, Preregistration)
    assert rec.to_dict()["pinned"]["phase4g_commit"] == PHASE4G_COMMIT


def test_duplicate_case_ids_rejected() -> None:
    with pytest.raises(ValueError):
        manifest((PHASE4H_CASES[0], PHASE4H_CASES[0]), {})


# -- blinded packets ----------------------------------------------------------------------------
def test_role_of_uses_parent_only_when_needed() -> None:
    s = _s(KITCHEN)
    assert role_of(s, "5") == "banana"
    assert role_of(s, "9") == "cup in counter"
    assert role_of(_s({**KITCHEN, "12": _o("cup", "3")}), "9") is None


def test_packet_contains_no_declaration_or_case_identity() -> None:
    packet = _packet("eat banana", ("5",))
    text = json.dumps(packet)
    for leak in ("h4-", "weight", "required", "certificate", "expected_category", "C-EAT"):
        assert leak not in text
    assert packet["form"] == {"properties": [], "notes": ""}
    assert packet["target_objects"][0]["container"]["role"] == "bowl"
    assert packet == _packet("eat banana", ("5",))  # deterministic, hash included


# -- rule-based generator -----------------------------------------------------------------------
def test_rubric_per_verb_rules() -> None:
    eat = rubric_declaration(_packet("eat banana", ("5",)))
    assert [(p.role, p.field, p.weight) for p in eat] == [
        ("banana", "present", 1.0), ("bowl", "contents", 0.0)]  # fmt: skip
    fridge = {(p.role, p.field): p.rule for p in rubric_declaration(_packet("open fridge", ("6",)))}
    assert fridge == {
        ("fridge", "propContainer.isOpen"): "R1",
        ("orange juice", "propMaterial.temperatureC"): "R2",
        ("orange juice", "propMaterial.stateOfMatter"): "R2",
    }
    tele = rubric_declaration(_packet("teleport to workshop", ()))
    assert [(p.role, p.field) for p in tele] == [("agent", "location")]


def test_rubric_is_deterministic_and_binds() -> None:
    packet = _packet("open fridge", ("6",))
    props = rubric_declaration(packet)
    assert props == rubric_declaration(json.loads(json.dumps(packet)))
    decl = rubric_to_declaration("x@rubric", "B", props)
    assert set(bind(decl, _s(KITCHEN)).values()) == {"6", "8"}


def test_compare_metrics_on_uuid_field_pairs() -> None:
    s = _s(KITCHEN)
    a = Declaration("a", "B", (PropertyRef("banana", "present", 1),
                               PropertyRef("bowl", "contents", 0)))  # fmt: skip
    b = Declaration("b", "B", (PropertyRef("banana in bowl", "present", 0),
                               PropertyRef("bowl", "location", 0)))  # fmt: skip
    out = compare(a, bind(a, s), b, bind(b, s))
    assert out["jaccard_all"] == round(1 / 3, 3)
    assert out["jaccard_weighted"] == 0.0
    assert out["weight_flag_agreement_on_shared"] == 0.0
    assert out["weight_disagreements"] == ["5:present"]
    assert out["only_a"] == ["4:contents"] and out["only_b"] == ["4:location"]
    same = compare(a, bind(a, s), a, bind(a, s))
    assert same["jaccard_all"] == same["jaccard_weighted"] == 1.0


# -- plantless consumption checker --------------------------------------------------------------
NAMES = {"banana": "Banana", "apple": "Apple"}


def _eaten(objs: dict[str, dict[str, Any]], uuid: str) -> CanonicalState:
    return _s({k: v for k, v in objs.items() if k != uuid})


def test_plantless_check_met_only_when_every_condition_holds() -> None:
    s0 = _s(KITCHEN)
    ok = check_eat_plantless(s0, "eat banana", _eaten(KITCHEN, "5"), ("5",), NAMES)
    assert ok.status == MET and ok.certificate_id == PLANTLESS_ID
    assert check_eat_plantless(s0, "open fridge", s0, ("6",), NAMES).status == NOT_APPLICABLE
    assert check_eat_plantless(s0, "eat banana", s0, ("5",), NAMES).status == NOT_MET
    two = {**KITCHEN, "12": _o("banana", "3")}
    assert check_eat_plantless(_s(two), "eat banana", _eaten(two, "5"), ("5",), NAMES).status == (
        NOT_MET
    )
    tree = {**KITCHEN, "12": _o("apple tree", "2")}
    s1 = _eaten(tree, "5")
    assert plant_like(s1) == ["apple tree (12)"]
    assert check_eat_plantless(_s(tree), "eat banana", s1, ("5",), NAMES).status == NOT_MET
    assert check_eat_plantless(s0, "eat banana", _eaten(KITCHEN, "5"), ("5",), {}).status == (
        NOT_MET
    )


# -- source audits on synthetic trees -----------------------------------------------------------
def _tree(tmp: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")
    return tmp


def test_add_object_sites_flags_unreviewed_reattachment(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "processes/P.scala": "object P {\n  def f(c: EnvObject) {\n    c.addObject(new Ash())\n"
                             "    val x = new Ash()\n    c.addObject(x)\n    c.addObject(this)\n"
                             "  }\n}\n",
        "tasks/T.scala": "class T {\n  def g() {\n    room.addObject(stash)\n  }\n}\n",
    })  # fmt: skip
    sites = {s.site: s.category for s in add_object_sites(root)}
    assert sites == {"processes/P.scala:3": "fresh", "processes/P.scala:5": "fresh",
                     "processes/P.scala:6": "self_move"}  # fmt: skip
    _tree(tmp_path, {"processes/Q.scala": "object Q {\n  def h() {\n    c.addObject(stash)\n"
                                          "  }\n}\n"})  # fmt: skip
    o2 = reattachment_obligation(root)
    assert o2.status != "discharged"
    assert [u["site"] for u in o2.evidence["unreviewed"]] == ["processes/Q.scala:3"]


PLANT_SRC = {
    "objects/livingthing/plant/Plant.scala": "class Plant extends EnvObject {\n"
    "  override def tick() {\n    PlantReproduction.createFruit(this)\n  }\n}\n",
    "objects/livingthing/plant/PlantReproduction.scala": "object PlantReproduction {\n"
    "  def createFruit(p: Plant) {\n    val f = new Apple()\n  }\n}\n",
    "objects/Apple.scala": 'class Apple extends EnvObject {\n  this.name = "apple"\n}\n',
    "tasks/T.scala": "class T {\n  val a = new Apple()\n}\n",
}


def test_plant_closure_discharged_and_counterexample(tmp_path: Path) -> None:
    root = _tree(tmp_path, PLANT_SRC)
    assert plant_closure(root).status == "discharged"
    _tree(tmp_path, {"processes/Magic.scala": "object Magic {\n  def conjure() {\n"
                                              "    val a = new Apple()\n  }\n}\n"})  # fmt: skip
    o8 = plant_closure(root)
    assert o8.status != "discharged"
    assert o8.evidence["checks"]["fruit_runtime_only_in_createFruit"] is False
