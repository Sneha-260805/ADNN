"""Phase 4H evidence, declaration sensitivity, independent replication (docs/24 §5-§6).

Run from the repository root with the isolated runtime configured, AFTER
``phase4h_freeze.py`` and with the Phase 4G certificate reports present::

    python scripts/scienceworld/phase4h_run.py main          # M1 + rubric declarations
    python scripts/scienceworld/phase4h_run.py replica       # second fresh process
    python scripts/scienceworld/phase4h_run.py audit         # query-order measurement check
    python scripts/scienceworld/phase4h_run.py compare       # pure: replication + sensitivity

Every mode first verifies the frozen manifest and refuses to run on any mismatch.
Decisions use the unchanged rule ``sw-admission-2`` and the Phase 4G certificate
reports. Outputs go to ``results/phase4h/`` (git-ignored); nothing is a gold label.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.admission import DECISION_RULE_VERSION, decide
from adnn.scienceworld.label_evidence import collect_case
from adnn.scienceworld.phase4h_cases import PHASE4H_CASES
from adnn.scienceworld.preregistration import verify_manifest
from adnn.scienceworld.query_audit import AuditScenario, audit_scenario
from adnn.scienceworld.semantics import declaration_from_dict

PREREG = Path("docs/preregistration")
OUT = Path("results/phase4h")
CERTS = Path("results/scienceworld_certificates")
ELIGIBLE = ("eligible_reversible", "eligible_partially_reversible", "eligible_irreversible")


def _write(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=1) + "\n")


def _read(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def _reports() -> dict[str, dict]:
    reports = {}
    for p in sorted(CERTS.glob("C-*.json")):
        r = _read(p)
        reports[r["certificate_id"]] = r
    if not reports:
        raise SystemExit("Phase 4G certificate reports missing (run certificate_verification.py)")
    return reports


def _verify() -> dict[str, Any]:
    if DECISION_RULE_VERSION != "sw-admission-2":
        raise SystemExit(
            f"rule changed to {DECISION_RULE_VERSION}; Phase 4H is pinned to sw-admission-2"
        )
    bad = verify_manifest(PHASE4H_CASES, PREREG / "phase4h_manifest.json")
    if bad:
        raise SystemExit(f"pre-registration differs from the frozen manifest: {bad}")
    man = _read(PREREG / "phase4h_manifest.json")
    rubric = _read(PREREG / "phase4h_rubric_declarations.json")
    for cid, row in rubric["cases"].items():
        if (
            declaration_from_dict(row["declaration"]).sha256
            != (man["rubric_declaration_sha256"][cid])
        ):
            raise SystemExit(f"rubric declaration for {cid} differs from the manifest")
    return rubric


def _run(spec: Any, reports: dict[str, dict]) -> dict[str, Any]:
    evidence = collect_case(spec, config=RuntimeConfig.from_env())
    return {"evidence": evidence, "decision": decide(evidence, reports)}


def _row(doc: dict[str, Any]) -> dict[str, Any]:
    e, d = doc["evidence"], doc["decision"]
    return {
        "case_id": e["case"]["case_id"],
        "evidence_status": e["status"],
        "outcome": d["outcome"],
        "quarantined": d["quarantined"],
        "reasons": d["reasons"],
        "witness": d["witness"] and {k: d["witness"][k] for k in ("source", "path", "restored",
                                                                    "residual")},
        "elapsed_s": e.get("elapsed_s"),
    }  # fmt: skip


def mode_main(rubric: dict[str, Any]) -> None:
    reports = _reports()
    rows, sens = [], []
    for rec in PHASE4H_CASES:
        doc = _run(rec.spec, reports)
        _write(OUT / "main" / f"{rec.case_id}.json", doc)
        rows.append(_row(doc))
        print(json.dumps({k: rows[-1][k] for k in ("case_id", "outcome", "reasons")}))
        # Sensitivity: same case, rubric properties, M1's declared paths (property choice only).
        r = declaration_from_dict(rubric["cases"][rec.case_id]["declaration"])
        r = replace(r, paths=rec.spec.declaration.paths)
        rdoc = _run(replace(rec.spec, case_id=r.case_id, declaration=r), reports)
        _write(OUT / "rubric" / f"{rec.case_id}.json", rdoc)
        sens.append(_row(rdoc))
    counts = Counter(r["outcome"] for r in rows)
    _write(OUT / "main_summary.json", {"rule": DECISION_RULE_VERSION, "counts": counts,
                                       "cases": rows, "rubric_sensitivity": sens})  # fmt: skip
    print(json.dumps(counts))


def _eligible_ids() -> list[str]:
    return [
        r["case_id"] for r in _read(OUT / "main_summary.json")["cases"] if r["outcome"] in ELIGIBLE
    ]


def mode_replica() -> None:
    reports = _reports()
    for rec in PHASE4H_CASES:
        if rec.case_id in _eligible_ids():
            doc = _run(rec.spec, reports)
            _write(OUT / "replica" / f"{rec.case_id}.json", doc)
            print(json.dumps(_row(doc)))


def mode_audit() -> None:
    out = {}
    for rec in PHASE4H_CASES:
        if rec.case_id not in _eligible_ids():
            continue
        main = _read(OUT / "main" / f"{rec.case_id}.json")
        witness = main["decision"]["witness"] or {}
        fam = rec.spec.family
        actions = (*fam.base_actions, *rec.spec.history, rec.spec.target, *witness.get("path", []))
        audit = audit_scenario(
            AuditScenario(rec.case_id, fam.task, fam.variation, actions),
            repeats=1, shared=False, config=RuntimeConfig.from_env(),
        )  # fmt: skip
        comps = audit.summary()["comparisons"]
        out[rec.case_id] = {
            "actions": list(actions),
            "conditions": {c["condition"]: {k: c[k] for k in (
                "transitions_equal_all_k", "valid_actions_equal_all_k", "n_k_state_differs")}
                for c in comps},
        }  # fmt: skip
        print(json.dumps({rec.case_id: out[rec.case_id]["conditions"]}))
    _write(OUT / "measurement_audit.json", out)


def _attempt_sig(doc: dict[str, Any]) -> list[Any]:
    return [
        (a["source"], tuple(a["path"]), a.get("verified"), a.get("executed"),
         tuple(sorted((t, x["canonical_level"], tuple(x["concepts"]))
                      for t, x in (a.get("assessments") or {}).items())))
        for a in doc["evidence"].get("attempts", [])
    ]  # fmt: skip


def mode_compare() -> None:
    rows = {}
    for cid in _eligible_ids():
        a, b = _read(OUT / "main" / f"{cid}.json"), _read(OUT / "replica" / f"{cid}.json")
        ea, eb = a["evidence"], b["evidence"]
        checks = {
            "s0_fingerprint": ea["replay"]["s0_raw_fingerprint"]
            == eb["replay"]["s0_raw_fingerprint"],
            "target": {k: ea["target"].get(k) for k in ("status", "ticks", "no_op")}
            == {k: eb["target"].get(k) for k in ("status", "ticks", "no_op")},
            "attempts": _attempt_sig(a) == _attempt_sig(b),
            "certificate_checks": ea.get("certificate_checks") == eb.get("certificate_checks"),
            "outcome": a["decision"]["outcome"] == b["decision"]["outcome"],
            "reasons": a["decision"]["reasons"] == b["decision"]["reasons"],
            "witness": a["decision"]["witness"] == b["decision"]["witness"],
            "stochastic_exposure": ea["exclusion_signals"] == eb["exclusion_signals"],
        }  # fmt: skip
        rows[cid] = {"replicated": all(checks.values()), "checks": checks,
                     "outcome": [a["decision"]["outcome"], b["decision"]["outcome"]]}  # fmt: skip
    summary = _read(OUT / "main_summary.json")
    sens = {}
    for m, r in zip(summary["cases"], summary["rubric_sensitivity"], strict=True):
        sens[m["case_id"]] = {"m1": m["outcome"], "rubric": r["outcome"],
                              "changed": m["outcome"] != r["outcome"],
                              "m1_reasons": m["reasons"],
                              "rubric_reasons": r["reasons"]}  # fmt: skip
    audit = (
        _read(OUT / "measurement_audit.json") if (OUT / "measurement_audit.json").exists() else {}
    )
    _write(OUT / "comparison.json", {"replication": rows, "rubric_sensitivity": sens,
                                     "measurement_audit": audit})  # fmt: skip
    print(json.dumps({"replication": {k: v["replicated"] for k, v in rows.items()},
                      "sensitivity_changed": [k for k, v in sens.items() if v["changed"]]},
                     indent=1))  # fmt: skip


def mode_whatif() -> None:
    """Counterfactual review aid, NOT an official decision: how would ``sw-admission-2``
    treat the eat cases if ``C-EAT/structural-plantless`` were registered (with and
    without a coverage entry)? Uses the 4H report and its simulator checks of the same
    worlds; the official outcomes in ``main_summary.json`` are unaffected."""
    import adnn.scienceworld.admission as adm

    report = _read(Path("results/scienceworld_certificates_4h/C-EAT_structural-plantless.json"))
    ev = {o["obligation_id"]: o["evidence"] for o in report["obligations"]}
    checks = {"h4-eat-banana": ev["O6"]["check"], "h4-eat-apple-plant-world":
              ev["O7"]["plant_world"]["check"]}  # fmt: skip
    reports = _reports() | {"C-EAT/structural-plantless": report}
    out: dict[str, Any] = {"is_official_decision": False, "rule": DECISION_RULE_VERSION}
    for cid, check in checks.items():
        doc = _read(OUT / "main" / f"{cid}.json")
        evidence = json.loads(json.dumps(doc["evidence"]))
        evidence["certificate_checks"]["C-EAT"]["structural-plantless"] = check
        rows = {"official": doc["decision"]["outcome"]}
        rows["registered_without_coverage_entry"] = decide(evidence, reports)["outcome"]
        saved = dict(adm.CERTIFICATE_COVERAGE)
        try:
            adm.CERTIFICATE_COVERAGE["C-EAT/structural-plantless"] = ("present",)
            d = decide(evidence, reports)
        finally:
            adm.CERTIFICATE_COVERAGE.clear()
            adm.CERTIFICATE_COVERAGE.update(saved)
        rows["registered_with_present_coverage"] = d["outcome"]
        rows["reasons"] = d["reasons"]
        rows["precondition"] = check["status"]
        out[cid] = rows
    _write(OUT / "whatif_plantless.json", out)
    print(json.dumps(out, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("main", "replica", "audit", "compare", "whatif"))
    args = ap.parse_args()
    rubric = _verify()
    {"main": lambda: mode_main(rubric), "replica": mode_replica, "audit": mode_audit,
     "compare": mode_compare, "whatif": mode_whatif}[args.mode]()  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
