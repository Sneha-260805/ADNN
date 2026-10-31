"""Phase 4G: restoration semantics, partial restoration, certificate verification and the
gold-admission procedure, including adversarial cases (no Java; docs/23 §8)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from adnn.scienceworld.admission import (
    ELIGIBLE_IRREVERSIBLE,
    ELIGIBLE_PARTIAL,
    ELIGIBLE_REVERSIBLE,
    FAILED_SEARCH,
    UNCOVERED,
    UNRESOLVED,
    decide,
)
from adnn.scienceworld.canonical import CanonicalState
from adnn.scienceworld.certificate_verification import (
    DISCHARGED,
    PROVISIONAL,
    REJECTED,
    VERIFIED,
    Obligation,
    action_space,
    constructor_sites,
    obligation,
    occurrences,
    property_reassignments,
    reflection_sites,
    status_of,
    verification_report,
)
from adnn.scienceworld.certificates import ALL_AGENT_ACTIONS, MET, NOT_MET
from adnn.scienceworld.label_cases import LABEL_CASES
from adnn.scienceworld.label_evidence import CaseSpec, collect_case
from adnn.scienceworld.provisional import FamilySpec
from adnn.scienceworld.semantics import (
    COMPENSATION,
    EXACT,
    NONE,
    PARTIAL,
    REPLACED,
    REPLACEMENT,
    RESTORED,
    TASK_RELEVANT,
    BindingError,
    Declaration,
    OutcomePredicate,
    PropertyOutcome,
    PropertyRef,
    bind,
    classify,
    compare_property,
    declaration_from_dict,
    weighted_recovery,
)
from scienceworld_restoration_fake import MiniKitchen

FAKE = FamilySpec("fake-kitchen", "1-1", 0, "")
B = "B_time_matched_counterfactual"


# -- synthetic states -------------------------------------------------------------------------
def _o(name: str, parent: str | None, **fields: Any) -> dict[str, Any]:
    return {"name": name, "parent": parent, "isDeleted": False, **fields}


def _s(objs: dict[str, dict[str, Any]]) -> CanonicalState:
    base = {"1": _o("universe", None), "2": _o("kitchen", "1"), "3": _o("table", "2")}
    return CanonicalState({**base, **objs}, {}, {})


CUP_WITH_WATER = {"6": _o("cup", "3"), "7": _o("water", "6"), "71": _o("terminal 1", "7")}


# -- Part A: semantics ------------------------------------------------------------------------
def test_declaration_hash_is_stable_and_round_trips() -> None:
    d = Declaration("c", B, (PropertyRef("cup", "contents", 1.0),),
                    (OutcomePredicate("x", contains="water"),), (("a", "b"),))  # fmt: skip
    assert declaration_from_dict(d.to_dict()) == d
    assert d.sha256 == declaration_from_dict(d.to_dict()).sha256
    changed = Declaration("c", B, (PropertyRef("cup", "contents", 2.0),))
    assert changed.sha256 != d.sha256
    with pytest.raises(ValueError):
        Declaration("c", B, ())
    with pytest.raises(ValueError):
        Declaration("c", B, (PropertyRef("a", "x"), PropertyRef("a", "x")))


def test_bind_requires_unique_roles() -> None:
    s = _s({**CUP_WITH_WATER, "8": _o("cup", "2")})
    d = Declaration("c", B, (PropertyRef("cup in table", "contents"),))
    assert bind(d, s) == {"cup in table": "6"}
    with pytest.raises(BindingError):
        bind(Declaration("c", B, (PropertyRef("cup", "contents"),)), s)
    with pytest.raises(BindingError):
        bind(Declaration("c", B, (PropertyRef("kettle", "present"),)), s)


def test_compare_property_separates_identity_from_replacement() -> None:
    cf = _s(CUP_WITH_WATER)
    refilled = _s({"6": _o("cup", "3"), "9": _o("water", "6")})  # new water, new uuid
    empty = _s({"6": _o("cup", "3")})
    contents = PropertyRef("cup", "contents")
    assert compare_property(contents, "6", cf, cf, 0.01) == RESTORED
    assert compare_property(contents, "6", cf, refilled, 0.01) == REPLACED
    assert compare_property(contents, "6", cf, empty, 0.01) == "different"
    present = PropertyRef("water", "present")
    assert compare_property(present, "7", cf, refilled, 0.01) == REPLACED
    assert compare_property(present, "7", cf, empty, 0.01) == "different"


def test_temperature_tolerance_is_applied_per_property() -> None:
    a = _s({"6": _o("cup", "3", **{"propMaterial.temperatureC": 20.0})})
    b = _s({"6": _o("cup", "3", **{"propMaterial.temperatureC": 20.05})})
    t = PropertyRef("cup", "propMaterial.temperatureC")
    assert compare_property(t, "6", a, b, 0.01) == "different"
    assert compare_property(t, "6", a, b, 0.1) == RESTORED
    assert compare_property(t, "6", a, b, 0.0) == "different"


def _po(key: str, w: float, changed: bool, after: str, idle: bool = False) -> PropertyOutcome:
    return PropertyOutcome(key, w, changed, after, idle)


def test_classify_partial_requires_meaningful_restoration_and_residual() -> None:
    restored = _po("pot.location", 1, True, RESTORED)
    residual = _po("pot.contents", 1, True, "different")
    assert PARTIAL in classify("none", [restored, residual], None, 0.01)
    assert TASK_RELEVANT not in classify("none", [restored, residual], None, 0.01)
    # vacuous: the restored property comes back by idling alone
    idle = _po("pot.location", 1, True, RESTORED, idle=True)
    assert classify("none", [idle, residual], None, 0.01) == (NONE,)
    # vacuous: the restored property was never changed by the target
    unchanged = _po("pot.location", 1, False, RESTORED)
    assert classify("none", [unchanged, residual], None, 0.01) == (NONE,)
    # weights declared: restoring only an unweighted property is not meaningful
    light = _po("sink.isActivated", 0, True, RESTORED)
    assert PARTIAL not in classify("none", [light, residual], None, 0.01)
    # no residual: not partial (and exact/approximate are decided by the canonical level)
    assert classify("exact", [restored], None, 0.01) == (EXACT,)


def test_task_relevant_without_declared_residual_is_not_a_partial_witness() -> None:
    """All declared properties restored, only undeclared fields differ (glass jar at 0.01C)."""
    loc = _po("jar.location", 1, True, RESTORED)
    temp = _po("jar.propMaterial.temperatureC", 0, True, RESTORED)
    assert classify("within_0.1C", [loc, temp], None, 0.01) == (TASK_RELEVANT,)


def test_classify_flags_replacement_and_compensation_without_partial() -> None:
    replaced = _po("cup.contents", 1, True, REPLACED)
    assert classify("none", [replaced], None, 0.01) == (REPLACEMENT,)
    compensated = classify("none", [_po("cup.contents", 1, True, "different")], True, 0.01)
    assert compensated == (COMPENSATION,)
    assert weighted_recovery([_po("a", 1, True, RESTORED), _po("b", 3, True, "different")]) == 0.25


def test_outcome_predicate() -> None:
    s = _s(CUP_WITH_WATER)
    assert OutcomePredicate("x", container="table", contains="water").holds(s)
    assert not OutcomePredicate("x", container="kitchen", contains="water").holds(s)
    assert not OutcomePredicate("x", name="cup", contains="juice").holds(s)


def test_label_cases_are_preregistered_and_unique() -> None:
    ids = [c.case_id for c in LABEL_CASES]
    assert len(ids) == len(set(ids)) == 15
    for c in LABEL_CASES:
        assert c.declaration.case_id == c.case_id and c.declaration.required
    assert {c.case_id for c in LABEL_CASES if c.case_id.startswith("adv-")} == {
        "adv-bee-hive", "adv-door", "adv-no-op", "adv-invalid"}  # fmt: skip


# -- Part B: evidence and partial restoration on the fake -------------------------------------
def _case(case_id: str, history: tuple[str, ...], target: str, *props: PropertyRef,
          certificates: tuple[str, ...] = ()) -> CaseSpec:  # fmt: skip
    return CaseSpec(case_id, FAKE, history, target, Declaration(case_id, B, props),
                    certificates=certificates, max_expanded=6)  # fmt: skip


@pytest.fixture(scope="module")
def evidence() -> dict[str, dict[str, Any]]:
    cases = [
        _case("rev", (), "open cupboard", PropertyRef("cupboard", "propContainer.isOpen", 1)),
        _case("partial", ("open cupboard", "move ceramic cup to sink"), "activate sink",
              PropertyRef("sink", "propDevice.isActivated", 1),
              PropertyRef("ceramic cup", "contents", 1)),
        _case("eat", (), "eat apple", PropertyRef("apple", "present", 1),
              certificates=("C-EAT",)),
    ]  # fmt: skip
    return {c.case_id: collect_case(c, backend_factory=MiniKitchen) for c in cases}


def test_evidence_records_preregistration_replay_and_attempts(evidence) -> None:
    e = evidence["partial"]
    assert e["status"] == "complete" and e["declared_before_search"]
    assert e["replay"]["verified"] and e["binding"] == {"ceramic cup": "6", "sink": "11"}
    assert e["search"]["registry_inverses"] == ["deactivate sink"] and e["search"]["restricted"]
    reg = next(a for a in e["attempts"] if a["source"] == "registry")
    asm = reg["assessments"]["0.01"]
    assert asm["partial_witness"]
    assert asm["restored_changed_properties"] == ["sink.propDevice.isActivated"]
    assert "ceramic cup.contents" in asm["residual_properties"]
    assert set(reg["assessments"]) == {"0.0", "0.01", "0.1"}


def test_admission_on_fake_cases(evidence) -> None:
    assert decide(evidence["rev"])["outcome"] == ELIGIBLE_REVERSIBLE
    partial = decide(evidence["partial"])
    assert partial["outcome"] == ELIGIBLE_PARTIAL and partial["witness"]["source"] == "registry"
    eat = decide(evidence["eat"], {})
    assert eat["outcome"] == UNRESOLVED and FAILED_SEARCH in eat["reasons"]
    assert all(d["is_gold_label"] is False for d in map(decide, evidence.values()))


# -- Part D/E: adversarial validation ---------------------------------------------------------
def _verified_report(cid: str, *, identity: bool = False, status: str = VERIFIED) -> dict:
    return {"certificate_id": cid, "status": status, "identity_loss_only": identity,
            "admissible_for_irreversible_label": status == VERIFIED and not identity,
            "definitions": [B]}  # fmt: skip


def _no_witness(ev: dict) -> dict:
    ev = copy.deepcopy(ev)
    for a in ev["attempts"]:
        for asm in (a.get("assessments") or {}).values():
            asm.update(concepts=[NONE], partial_witness=False, canonical_level="none",
                       declared_complete=False)  # fmt: skip
    return ev


def _with_cert(ev: dict, status: str, *extra: PropertyRef) -> dict:
    """Recast the evidence as a burn case: a protected chair flag plus ``extra`` properties."""
    ev = _no_witness(ev)
    props = (PropertyRef("chair", "propMaterial.hasCombusted", 1), *extra)
    decl = Declaration(ev["case"]["case_id"], B, props)
    ev["declaration"], ev["declaration_sha256"] = decl.to_dict(), decl.sha256
    ev["binding"] = {p.role: "99" for p in props}
    ev["case"]["certificates"] = ["C-BURN"]
    ev["certificate_checks"] = {"C-BURN": {"status": status, "objects": ["99"]}}
    rows = [{"key": p.key, "weight": p.weight, "changed_by_target": True} for p in props]
    for a in ev["attempts"]:
        for asm in (a.get("assessments") or {}).values():
            asm["properties"] = rows
    return ev


def test_adversarial_no_op_target(evidence) -> None:
    ev = copy.deepcopy(evidence["rev"])
    ev["target"]["no_op"] = True
    d = decide(ev)
    assert d["outcome"] == UNRESOLVED and "no_op_target" in d["reasons"]


def test_adversarial_visible_appearance_only() -> None:
    """A path that equalises an undeclared field but not the declared one is no witness."""
    pot = PropertyRef("pot", "location", 1)
    s0 = _s({"6": _o("pot", "3", color="grey")})
    s1 = _s({"6": _o("pot", "2", color="shiny")})
    s2 = _s({"6": _o("pot", "2", color="grey")})  # looks the same, still moved
    assert compare_property(pot, "6", s0, s2, 0.01) == "different"
    out = _po("pot.location", 1, compare_property(pot, "6", s0, s1, 0.01) != RESTORED,
              compare_property(pot, "6", s0, s2, 0.01))  # fmt: skip
    assert classify("none", [out], None, 0.01) == (NONE,)


def test_adversarial_replacement_object(evidence) -> None:
    ev = _no_witness(evidence["partial"])
    ev["attempts"][0]["assessments"]["0.01"]["concepts"] = [REPLACEMENT]
    d = decide(ev)
    assert d["outcome"] == UNRESOLVED
    assert "structural_replacement_is_not_restoration" in d["reasons"]


def test_adversarial_temperature_sensitive(evidence) -> None:
    ev = _no_witness(evidence["rev"])
    a = ev["attempts"][0]["assessments"]
    a["0.1"].update(concepts=["approximate_restoration"], canonical_level="within_0.1C")
    d = decide(ev)
    assert d["outcome"] == UNRESOLVED and d["quarantined"]
    assert d["reasons"][0].startswith("temperature_sensitive")


def test_adversarial_stochastic_bee(evidence) -> None:
    ev = copy.deepcopy(evidence["rev"])
    ev["exclusion_signals"]["stochastic_exposure_s2"] = ["bee 0 in greenhouse"]
    assert "uncontrolled_stochastic_process" in decide(ev)["reasons"]
    ev2 = copy.deepcopy(evidence["rev"])
    ev2["observation"]["history_bee_actions"] = ["open bee hive"]
    assert decide(ev2)["outcome"] == UNRESOLVED


def test_adversarial_hidden_door_state(evidence) -> None:
    ev = copy.deepcopy(evidence["rev"])
    ev["target"]["door_exclusion"] = "door_action_excluded(RD-05)"
    assert "hidden_door_state" in decide(ev)["reasons"]
    ev2 = copy.deepcopy(evidence["rev"])
    ev2["observation"]["history_door_actions"] = ["open door to hallway"]
    assert "hidden_door_state" in decide(ev2)["reasons"]


def test_adversarial_invalid_action(evidence) -> None:
    ev = copy.deepcopy(evidence["rev"])
    ev["status"] = "target_invalid"
    d = decide(ev)
    assert d["outcome"] == UNRESOLVED and d["reasons"] == ["evidence_target_invalid"]


def test_adversarial_incomplete_replay(evidence) -> None:
    ev = copy.deepcopy(evidence["rev"])
    ev["replay"]["verified"] = False
    assert "incomplete_or_divergent_replay" in decide(ev)["reasons"]
    ev2 = copy.deepcopy(evidence["rev"])
    ev2["attempts"][0]["verified"] = False
    assert decide(ev2)["outcome"] == UNRESOLVED


def test_adversarial_vacuous_partial(evidence) -> None:
    ev = _no_witness(evidence["partial"])
    asm = ev["attempts"][0]["assessments"]["0.01"]
    asm["concepts"] = [NONE]  # restored property came back by idling -> classifier: none
    assert decide(ev)["outcome"] == UNRESOLVED


def test_adversarial_false_certificate_precondition(evidence) -> None:
    reports = {"C-BURN": _verified_report("C-BURN")}
    assert decide(_with_cert(evidence["rev"], MET), reports)["outcome"] == ELIGIBLE_IRREVERSIBLE
    d = decide(_with_cert(evidence["rev"], NOT_MET), reports)
    assert d["outcome"] == UNRESOLVED and FAILED_SEARCH in d["reasons"]
    for bad in ({"C-BURN": _verified_report("C-BURN", status=PROVISIONAL)},
                {"C-BURN": _verified_report("C-BURN", identity=True)}, {}):  # fmt: skip
        assert decide(_with_cert(evidence["rev"], MET), bad)["outcome"] == UNRESOLVED
    uncovered = {"C-BURN": {**_verified_report("C-BURN"), "definitions": ["A_literal"]}}
    assert decide(_with_cert(evidence["rev"], MET), uncovered)["outcome"] == UNRESOLVED


def test_certificate_must_cover_every_weighted_changed_property(evidence) -> None:
    """A certificate protects named fields only: an unprotected weighted property the target
    changed (a burning chair's isCombusting) could still be restored -> not irreversible."""
    reports = {"C-BURN": _verified_report("C-BURN")}
    burning = PropertyRef("chair", "propMaterial.isCombusting", 1)
    d = decide(_with_cert(evidence["rev"], MET, burning), reports)
    assert d["outcome"] == UNRESOLVED
    assert any(r.startswith(UNCOVERED) for r in d["reasons"]) and FAILED_SEARCH in d["reasons"]
    # an unweighted extra property does not need coverage
    recorded = PropertyRef("chair", "propMaterial.isCombusting", 0)
    assert decide(_with_cert(evidence["rev"], MET, recorded), reports)["outcome"] == (
        ELIGIBLE_IRREVERSIBLE
    )


def test_adversarial_registry_miss_is_found_by_expanded_path(evidence) -> None:
    ev = _no_witness(evidence["rev"])
    exp = next(a for a in ev["attempts"] if a["source"] == "expanded" and a.get("assessments"))
    for asm in exp["assessments"].values():
        asm.update(concepts=[EXACT], canonical_level="exact")
    d = decide(ev)
    assert d["outcome"] == ELIGIBLE_REVERSIBLE and d["witness"]["source"] == "expanded"


def test_adversarial_reversible_witness_contradicts_certificate(evidence) -> None:
    ev = copy.deepcopy(evidence["rev"])
    ev["case"]["certificates"] = ["C-BURN"]
    ev["certificate_checks"] = {"C-BURN": {"status": MET}}
    d = decide(ev, {"C-BURN": _verified_report("C-BURN")})
    assert d["outcome"] == UNRESOLVED and d["quarantined"] and "contradiction" in d["reasons"][0]


def test_adversarial_declaration_altered_after_search(evidence) -> None:
    ev = copy.deepcopy(evidence["partial"])
    ev["declaration"]["required"][0]["weight"] = 5.0
    assert "declaration_altered_or_not_preregistered" in decide(ev)["reasons"]
    ev2 = copy.deepcopy(evidence["partial"])
    ev2["declared_before_search"] = False
    assert decide(ev2)["outcome"] == UNRESOLVED


def test_decision_trace_is_complete(evidence) -> None:
    d = decide(evidence["partial"])
    stages = [t["stage"] for t in d["trace"]]
    assert stages.count("gate") == 9 and "witness" in stages and "certificate" in stages
    assert d["decision_rule_version"] == "sw-admission-2" and d["evidence_sha256"]


# -- Part C: certificate verification scanners ------------------------------------------------
def _tree(tmp: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp


def test_occurrences_classify_writes_defaults_and_named_arguments(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "properties/MaterialProperties.scala":
            "class MaterialProperties {\n  var hasCombusted:Boolean = false\n"
            "  def toJSON() = { \"\\\"hasCombusted\\\":\" + v }\n}\n"
            "class AshProp extends MaterialProperties {\n  hasCombusted = true\n}\n",
        "processes/Combustion.scala":
            "object Combustion {\n  def ignite(o:X) {\n    o.propMaterial.get.hasCombusted = true\n"
            "  }\n  def bad(o:X) {\n    o.propMaterial.get.hasCombusted = false\n  }\n"
            "  def find(c:X) = get(c, hasCombusted = true)\n}\n",
        "tasks/T.scala": "class T {\n  def f() {\n    var hasCombusted = 1\n"
                         "    hasCombusted = 2\n  }\n}\n",
    })  # fmt: skip
    kinds = {(o.file.split("/")[0], o.line): o.kind for o in occurrences(root, "hasCombusted")}
    assert kinds[("properties", 2)] == "declaration"
    assert kinds[("properties", 3)] == "json"
    assert kinds[("properties", 6)] == "default"
    assert kinds[("processes", 3)] == "write" and kinds[("processes", 6)] == "write"
    assert kinds[("processes", 8)] == "named_argument"
    assert kinds[("tasks", 4)] == "local_variable"


def test_constructor_sites_and_reassignments(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "tasks/T.scala": "class T {\n  val a = new Foo()\n  val b = new Bar()\n}\n",
        "objects/Bar.scala": "class Bar {\n  val inner = new Foo\n}\n",
        "objects/Factory.scala": "object Factory {\n  def mk() = {\n    new Foo()\n  }\n}\n",
        "environments/E.scala": "object E {\n  def build() { Factory.mk() }\n}\n",
        "processes/P.scala": "object P {\n  def grow() {\n    val f = new Foo()\n"
                             "    x.propMaterial = Some(new Y)\n  }\n}\n",
    })  # fmt: skip
    sites = constructor_sites(root, "Foo")
    assert "tasks/T.scala:2" in sites["construction"]
    assert any("via Bar" in s for s in sites["construction"])
    assert any("in mk" in s for s in sites["construction"])
    assert sites["runtime"] == ["processes/P.scala:3 (in grow, called from 0 sites)"]
    assert property_reassignments(root) == ["processes/P.scala:4: x.propMaterial = Some(new Y)"]


def test_reflection_and_action_space(tmp_path: Path) -> None:
    files = {f"actions/{a}.scala": "class A\n" for a in ALL_AGENT_ACTIONS}
    files["actions/Action.scala"] = "trait Action\n"
    files["struct/E.scala"] = "import scala.reflect.ClassTag\n"
    root = _tree(tmp_path, {**files, "processes/C.scala": "object C\n"})
    assert action_space(root)["complete"]
    assert reflection_sites(root) == {"type_tags_only": ["struct/E.scala:1"], "other": []}
    _tree(tmp_path, {"struct/R.scala": "x.setAccessible(true)\n"})
    assert reflection_sites(root)["other"] == ["struct/R.scala:1"]


def test_status_of_and_report() -> None:
    ok = obligation("O1", "x", True, None)
    open_ = obligation("O2", "y", None, None)
    bad = obligation("O8", "z", False, None, counterexample=True)
    soft = obligation("O7", "w", False, None)
    assert ok.status == DISCHARGED and status_of([ok]) == VERIFIED
    assert status_of([ok, open_]) == PROVISIONAL and status_of([ok, soft]) == PROVISIONAL
    assert status_of([ok, bad, open_]) == REJECTED and status_of([]) == PROVISIONAL
    r = verification_report("C-X", "c", [ok], definitions=(B,), identity_loss_only=True,
                            horizon="h")  # fmt: skip
    assert r["status"] == VERIFIED and r["admissible_for_irreversible_label"] is False
    assert r["is_formal_proof"] is False and r["issues_labels"] is False
    assert isinstance(ok, Obligation)
