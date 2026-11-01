# ADR-0005: ScienceWorld label reliability: pre-registration, declaration reliability, replication and candidate class mapping (research decision log)

- **Status:** *Adopted* by the research team (Phase 4H), together with the team decisions on OQ-44 and OQ-46 recorded in R9. These are team decisions with explicit limitations. **No claim of professor approval is made, and the professor was not contacted** (RD-08).
- **Date:** 2026-10-31
- **Deciders:** Sneha (M1) drafted it. M2 and M3 are to review it as consumers of ScienceWorld data (RD-10).
- **Builds on:** ADR-0003 and ADR-0004. **It changes neither `sw-admission-2` nor `sw-restoration-semantics-1`.**
- **Evidence base:** `docs/24`.
- **Does not change:**
  - the sandbox and its 210-example pilot;
  - the dataset schema and API;
  - prompt builder 1.0.0.
- **Does not produce** gold labels, the final dataset or behavioural tasks.

## R1: Pre-registration is frozen by hash before any recovery run

Every Phase 4H case is a `Preregistration` record. It holds:
- the case and declaration;
- a rationale for each property;
- identity requirements;
- the horizon and restoration criterion;
- observation limitations;
- the expected category and the selection rationale;
- pins to the Phase 4G commit `5b74630…`, `sw-admission-2`, the semantics version and the evidence version.

Rules:
- The manifest (`docs/preregistration/phase4h_manifest.json`) stores each record's SHA-256.
- Evidence collection refuses to run on any mismatch.
- A record is never edited after the freeze. A correction is a new record with a new id, and the old record is kept and reported.

## R2: Case selection is representative, not convenient

Cases are chosen per state-changing action category and spread across the expected categories: likely reversible, likely partial, potentially irreversible and unknown. Every case stays in the report whatever its outcome. Source code read before the freeze must be disclosed, as must any declared path taken from the source.

## R3: No retrospective re-declaration

A declaration that would make a case eligible after its outcome is known is retrospective selection and is not allowed. This holds even when the new declaration is reasonable, for example declaring only `hasCombusted` for a burn case, or only the sodium chloride for a mix case. Such declarations are allowed only in a **new** pre-registration round, frozen before any run.

## R4: Candidate three-class mapping (frozen; no labels exported)

| Condition | Candidate class |
|---|---|
| `eligible_reversible` and replicated (R5) | reversible |
| `eligible_partially_reversible` and replicated | partially reversible |
| `eligible_irreversible` and replicated | irreversible |
| anything else (unresolved, quarantined, not replicated, excluded) | outside the three classes; never relabelled into one |

- **Partial is horizon- and search-relative.** It asserts a positive meaningful witness and a declared residual that this witness did not restore. It does not assert that no other path restores the residual, unless a certificate protects the residual. Reports must state this.
- **Irreversible** requires an admissible certificate covering every weighted changed property (ADR-0004 C5). A failed search never qualifies.
- Zero irreversible cases is an acceptable result.

## R5: Independent replication is required for eligibility

- Every potentially eligible case is re-collected in a second fresh simulator process.
- The two runs must agree on:
  - the S0 fingerprint;
  - the target effect;
  - the per-attempt levels and concepts;
  - the certificate checks;
  - the outcome, reasons and witness;
  - the stochastic-exposure signals.
- Any disagreement excludes the case.
- In addition, the replayed path (history, target, witness) is run through the Phase 4F query-order audit, with no queries, observation, enumeration and both orders. It must show identical transitions under every condition.
- Identical outputs from the same query protocol are **not** evidence of independence from measurement effects. That is why the query-order audit is a separate requirement.

## R6: New certificates enter admission only through a new rule version

`C-EAT/structural-plantless` is `verified_source_relative` (docs/24 §4.3), but it is **not** registered. Registering it requires three things:
- a new ADR;
- a new rule version (`sw-admission-3`), with the claim and its coverage entry (`present` of the eaten object) added to `CERTIFICATE_COVERAGE`;
- re-running every affected case under the new version, with both versions' outcomes reported.

Under `sw-admission-2`, the what-if analysis (`results/phase4h/whatif_plantless.json`) is a review aid only. Even if the claim were registered without a coverage entry, no case would change. With the coverage entry, `h4-eat-banana` would become eligible irreversible and `h4-eat-apple-plant-world` would stay unresolved (precondition not met).

## R7: Declaration reliability is reported, never assumed

- Blinded packets and a deterministic annotator protocol are frozen, together with a rule-based generator (`sw-declaration-rubric-1`).
- Generator-versus-team comparisons are labelled **automated consistency**. They are never called inter-annotator agreement.
- No human agreement statistic is reported until at least two human annotators complete the protocol. Any chance-corrected statistic must be pre-registered first.
- Before gold labels, every candidate case must be shown to keep its outcome under the rubric declaration (property-choice sensitivity). If it does not, it is excluded. In Phase 4H this excludes no eligible case: the one outcome that changed (freezer) was unresolved under M1.

## R8: Dataset design consequence (proposal)

**Do not force three-class balance in ScienceWorld.**
- ScienceWorld supplies reversible and partially reversible examples.
- An irreversible ScienceWorld slice is allowed only via R6, and it is reported separately with its template concentration (a single consumption template).
- The sandbox supplies the balanced three-class set.

The team adopted this on 2026-10-31 (R9).

## R9: Team decisions on OQ-44 and OQ-46 (2026-10-31)

- **OQ-46 accepted:**
  - three-class balance is **not** forced inside ScienceWorld;
  - the custom sandbox provides the stronger irreversible coverage;
  - ScienceWorld provides scientifically supported reversible and partially reversible cases;
  - R8 is therefore adopted.
- **OQ-44 deferred:** `C-EAT/structural-plantless` is **not** registered in the gold admission rule.
  - Its evidence is preserved as an exploratory, source-relative claim (`certificate_audit.py`, `phase4h_certificates.py`, docs/24 §4.3).
  - `sw-admission-2` remains the rule.
  - The what-if analysis is not an outcome.
- These decisions were taken by the research team. The professor was not consulted, and no approval is implied.

## Consequences and limitations

- The yield of defensible irreversible ScienceWorld cases is currently zero, and at best one template under R6.
- Declarations remain researcher-chosen and not human-validated, and one of the 12 outcomes depended on property choice.
- "Partial" is not absolute.
- Certificates are source-relative, assume a complete object tree and are scoped to a class or a world.
- docs/23 §6.3 carried a factual error ("the chair is not movable"). It is corrected with an erratum note, and the 4G conclusion is unchanged.
