"""Gold-admission decision procedure for ScienceWorld evidence (Phase 4G, ADR-0004 D1-D6).

Input: one label-evidence document (``label_evidence.collect_case``) and the certificate
verification reports. Output: one of

- ``eligible_reversible``            an executed, verified path restores the state exactly
                                     or within the primary tolerance;
- ``eligible_partially_reversible``  a non-trivial partial witness with a meaningful residual;
- ``eligible_irreversible``          no positive witness AND an admissible verified
                                     certificate whose precondition holds for this case;
- ``unresolved_excluded``            everything else, with explicit reasons.

"Eligible" means admissible to a future gold dataset under ADR-0004; it is not a gold
label and none is written anywhere. The procedure never infers irreversibility from a
failed bounded or restricted search: without an admissible certificate, the absence of a
witness is ``unresolved_excluded``. Every decision carries a full explanation trace.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from adnn.scienceworld.canonical import sha256_json
from adnn.scienceworld.certificates import MET, SOURCE_COMMIT
from adnn.scienceworld.label_evidence import EVIDENCE_VERSION
from adnn.scienceworld.semantics import (
    COMPENSATION,
    PARTIAL,
    PRIMARY_TOLERANCE,
    REPLACEMENT,
    SENSITIVITY_TOLERANCE,
    declaration_from_dict,
)

DECISION_RULE_VERSION = "sw-admission-2"  # v2 adds certificate coverage (ADR-0004 C5)
ELIGIBLE_REVERSIBLE = "eligible_reversible"
ELIGIBLE_PARTIAL = "eligible_partially_reversible"
ELIGIBLE_IRREVERSIBLE = "eligible_irreversible"
UNRESOLVED = "unresolved_excluded"
OUTCOMES = (ELIGIBLE_REVERSIBLE, ELIGIBLE_PARTIAL, ELIGIBLE_IRREVERSIBLE, UNRESOLVED)

FAILED_SEARCH = "no_positive_witness_and_failed_search_is_not_irreversibility"
UNCOVERED = "certificate_does_not_cover_every_weighted_changed_property"
# Fields each claim protects on the objects its precondition check names (ADR-0004 C5).
CERTIFICATE_COVERAGE: dict[str, tuple[str, ...]] = {
    "C-BURN": ("propMaterial.hasCombusted", "propMaterial.combustionTicks"),
    "C-MIX-SALT": ("present",),
    "C-EAT/identity": ("present",),
    "C-EAT/structural": ("present",),
}
_RANK = {"reversible": 2, "partial": 1, "none": 0}


def _interpretation(assessment: Mapping[str, Any] | None) -> str:
    if assessment is None:
        return "none"
    concepts = assessment["concepts"]
    if "exact_state_restoration" in concepts or "approximate_restoration" in concepts:
        return "reversible"
    return "partial" if PARTIAL in concepts else "none"


def _assessment(attempt: Mapping[str, Any], tol: float) -> Mapping[str, Any] | None:
    return (attempt.get("assessments") or {}).get(str(tol))


def _certificate(
    evidence: Mapping[str, Any], reports: Mapping[str, Mapping[str, Any]], definition: str
) -> dict[str, Any]:
    """Does any named certificate support irreversibility for this case? (ADR-0004 C3, D4)."""
    out: dict[str, Any] = {"admissible": False, "claims": []}
    checks = evidence.get("certificate_checks") or {}
    for cid in evidence["case"]["certificates"]:
        check = checks.get(cid, {})
        parts = [(f"{cid}/{k}", v) for k, v in check.items()] if cid == "C-EAT" else [(cid, check)]
        for claim_id, result in parts:
            report = reports.get(claim_id)
            row = {
                "claim": claim_id,
                "report_status": None if report is None else report["status"],
                "admissible_claim": bool(report and report["admissible_for_irreversible_label"]),
                "identity_loss_only": None if report is None else report["identity_loss_only"],
                "precondition": result.get("status"),
                "definition_covered": bool(
                    report and any(d.startswith(definition) for d in report["definitions"])
                ),
            }
            row["supports_irreversible"] = (
                row["admissible_claim"] and row["precondition"] == MET and row["definition_covered"]
            )
            row["protects"] = [
                [uuid, f]
                for uuid in result.get("objects", [])
                for f in CERTIFICATE_COVERAGE.get(claim_id, ())
            ]
            out["claims"].append(row)
            out["admissible"] = out["admissible"] or row["supports_irreversible"]
    return out


def _coverage(evidence: Mapping[str, Any], decl: Any, cert: Mapping[str, Any]) -> dict[str, Any]:
    """Which weighted properties changed by the target are protected by a supporting claim?

    A certificate protects named fields of named objects only. Any other weighted property
    the target changed could still be restored by a path the bounded search missed, which
    would make the case partial, so irreversibility needs every one of them covered.
    """
    if decl is None:
        return {"required": [], "uncovered": ["<no declaration>"]}
    refs = {r.key: r for r in decl.required}
    weighted = [r for r in decl.required if r.weight > 0] or list(decl.required)
    changed: set[str] | None = None
    for a in evidence.get("attempts", []):
        asm = _assessment(a, PRIMARY_TOLERANCE)
        if asm and asm.get("properties"):
            changed = {p["key"] for p in asm["properties"] if p["changed_by_target"]}
            break
    required = [r for r in weighted if changed is None or r.key in changed]
    protected = {
        (uuid, f)
        for row in cert["claims"]
        if row["supports_irreversible"]
        for uuid, f in row["protects"]
    }
    binding = evidence.get("binding") or {}
    uncovered = [
        r.key for r in required if (binding.get(r.role), refs[r.key].field) not in protected
    ]
    return {
        "required": [r.key for r in required],
        "changed_known": changed is not None,
        "uncovered": uncovered,
    }


def decide(
    evidence: Mapping[str, Any], certificate_reports: Mapping[str, Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """Apply the decision rule to one evidence document. Pure; never writes a label."""
    reports = certificate_reports or {}
    trace: list[dict[str, Any]] = []
    reasons: list[str] = []

    def gate(check: str, passed: bool, detail: Any = None, reason: str | None = None) -> bool:
        trace.append({"stage": "gate", "check": check, "passed": bool(passed), "detail": detail})
        if not passed:
            reasons.append(reason or check)
        return bool(passed)

    case = evidence.get("case", {})

    def finish(outcome: str, *, quarantined: bool = False, witness: Any = None,
               certificate: Any = None) -> dict[str, Any]:  # fmt: skip
        return {
            "decision_rule_version": DECISION_RULE_VERSION,
            "case_id": case.get("case_id"),
            "outcome": outcome,
            "quarantined": quarantined,
            "reasons": reasons,
            "witness": witness,
            "certificate": certificate,
            "trace": trace,
            "evidence_sha256": sha256_json(evidence),
            "is_gold_label": False,
        }

    gate(
        "schema", evidence.get("schema_version") == EVIDENCE_VERSION, evidence.get("schema_version")
    )
    pin = evidence.get("provenance", {}).get("recipe", {}).get("simulator", {})
    gate("provenance_pinned", pin.get("source_commit") == SOURCE_COMMIT, pin.get("source_commit"))
    status = evidence.get("status")
    if not gate("evidence_complete", status == "complete", status, reason=f"evidence_{status}"):
        return finish(UNRESOLVED)
    try:
        decl = declaration_from_dict(evidence["declaration"])
        intact = decl.sha256 == evidence["declaration_sha256"]
    except (KeyError, TypeError, ValueError):
        decl, intact = None, False
    gate("declaration_integrity", intact and evidence.get("declared_before_search") is True,
         evidence.get("declaration_sha256"),
         reason="declaration_altered_or_not_preregistered")  # fmt: skip
    gate("replay_verified", evidence["replay"]["verified"], evidence["replay"],
         reason="incomplete_or_divergent_replay")  # fmt: skip
    t = evidence["target"]
    gate("target_valid", t.get("status") == "accepted" and t.get("n_templates_with_text") == 1,
         {k: t.get(k) for k in ("status", "n_templates_with_text")},
         reason="invalid_target")  # fmt: skip
    obs = evidence["observation"]
    gate("no_hidden_door_state", not t.get("door_exclusion") and not obs["history_door_actions"],
         {"target": t.get("door_exclusion"), "history": obs["history_door_actions"]},
         reason="hidden_door_state")  # fmt: skip
    gate("not_no_op", not t.get("no_op"), t.get("discrete_effect_vs_counterfactual"),
         reason="no_op_target")  # fmt: skip
    sig = evidence["exclusion_signals"]
    exposed = [*sig.get("stochastic_exposure_s0", []), *sig.get("stochastic_exposure_s1", []),
               *sig.get("stochastic_exposure_s2", [])]  # fmt: skip
    gate("no_stochastic_exposure",
         not exposed and not obs["history_bee_actions"] and "bee" not in t["action"],
         {"exposed": exposed, "history": obs["history_bee_actions"]},
         reason="uncontrolled_stochastic_process")  # fmt: skip
    if reasons:
        return finish(UNRESOLVED)

    attempts = evidence.get("attempts", [])
    usable = [a for a in attempts if a.get("executed") and a.get("counterfactual_available")]
    unverified = [a["path"] for a in attempts if not a.get("verified")]
    trace.append({"stage": "attempts", "check": "usable_attempts", "passed": True,
                  "detail": {"total": len(attempts), "usable": len(usable),
                             "unverified_rebuilds": unverified}})  # fmt: skip
    if unverified and not gate("attempt_rebuilds_verified", False, unverified,
                               reason="incomplete_or_divergent_replay"):  # fmt: skip
        return finish(UNRESOLVED)

    by_tol: dict[float, tuple[str, dict[str, Any] | None]] = {}
    for tol in (PRIMARY_TOLERANCE, SENSITIVITY_TOLERANCE):
        best, witness = "none", None
        for a in usable:
            interp = _interpretation(_assessment(a, tol))
            if _RANK[interp] > _RANK[best]:
                asm = _assessment(a, tol) or {}
                best, witness = interp, {
                    "source": a["source"], "path": a["path"], "tolerance": tol,
                    "canonical_level": asm.get("canonical_level"),
                    "concepts": asm.get("concepts"),
                    "restored": asm.get("restored_changed_properties"),
                    "residual": asm.get("residual_properties"),
                    "replaced": asm.get("replaced_properties"),
                    "weighted_recovery": asm.get("weighted_recovery"),
                }  # fmt: skip
        by_tol[tol] = (best, witness)
        trace.append({"stage": "witness", "check": f"best_interpretation_at_{tol}C",
                      "passed": True,
                      "detail": {"interpretation": best, "witness": witness}})  # fmt: skip

    primary, witness = by_tol[PRIMARY_TOLERANCE]
    sensitivity, _ = by_tol[SENSITIVITY_TOLERANCE]
    cert = _certificate(evidence, reports, decl.definition if decl else "")
    trace.append({"stage": "certificate", "check": "admissible_certificate",
                  "passed": cert["admissible"], "detail": cert})  # fmt: skip

    if primary != sensitivity:
        reasons.append(f"temperature_sensitive: {primary} at 0.01C vs {sensitivity} at 0.1C")
        return finish(UNRESOLVED, quarantined=True, witness=witness, certificate=cert)
    if primary == "reversible":
        if cert["admissible"]:
            reasons.append("contradiction: restoration witness and irreversibility certificate")
            return finish(UNRESOLVED, quarantined=True, witness=witness, certificate=cert)
        return finish(ELIGIBLE_REVERSIBLE, witness=witness, certificate=cert)
    if primary == "partial":
        return finish(ELIGIBLE_PARTIAL, witness=witness, certificate=cert)
    coverage = _coverage(evidence, decl, cert)
    trace.append({"stage": "certificate", "check": "covers_weighted_changed_properties",
                  "passed": not coverage["uncovered"], "detail": coverage})  # fmt: skip
    if cert["admissible"] and not coverage["uncovered"]:
        return finish(ELIGIBLE_IRREVERSIBLE, certificate=cert)

    reasons.append(FAILED_SEARCH)
    if cert["admissible"] and coverage["uncovered"]:
        reasons.append(f"{UNCOVERED}: {coverage['uncovered']} (partial restoration not excluded)")
    concepts = {
        c for a in usable for c in (_assessment(a, PRIMARY_TOLERANCE) or {}).get("concepts", [])
    }
    if REPLACEMENT in concepts:
        reasons.append("structural_replacement_is_not_restoration")
    if COMPENSATION in concepts:
        reasons.append("compensation_is_not_restoration")
    if any((_assessment(a, PRIMARY_TOLERANCE) or {}).get("declared_complete") for a in usable):
        reasons.append("declared_properties_restored_but_undeclared_differences_remain")
    for row in cert["claims"]:
        if not row["supports_irreversible"]:
            reasons.append(f"certificate_not_admissible: {row['claim']} "
                           f"(status={row['report_status']}, precondition={row['precondition']}, "
                           f"identity_loss_only={row['identity_loss_only']})")  # fmt: skip
    return finish(UNRESOLVED, certificate=cert)
