# ADR-0004: ScienceWorld restoration semantics, partial restoration and gold-admission procedure (research decision log)

- **Status:** Adopted by the research team as the *proposed* admission procedure for ScienceWorld evidence (Phase 4G). These are team decisions with explicit limitations. **No claim of professor approval is made** (RD-08); the team decided not to seek methodological clarification at this stage.
- **Date:** 2026-10-31
- **Deciders:** Sneha (M1) drafted it. M2 and M3 review it as consumers of ScienceWorld data (RD-10).
- **Builds on:** ADR-0002 (RD-01 to RD-11) and ADR-0003 (D1 to D9). Where this record is more specific, it **refines** them. It does not revise them:
  - ADR-0003 D1 left "partial" uncomputed. A2 and B1 below make it computable, but only for cases with a pre-registered declaration.
  - ADR-0003 D4 required stability across 0.01 °C and 0.1 °C. A3 keeps that rule and names 0.01 °C the exploratory primary threshold.
  - ADR-0003 D6 said certificates were not yet gold evidence. C1 to C4 define the proof obligations that would make one admissible.
- **Does not change:**
  - the sandbox or its pilot labels;
  - the dataset schema and API;
  - prompt builder 1.0.0;
  - the 35 Phase 4E provisional records. They are not passed through this procedure and keep their recorded statuses.
- **Evidence base:** `docs/23` (Phase 4G measurements). Code:
  - `src/adnn/scienceworld/semantics.py`
  - `label_evidence.py`
  - `certificate_verification.py`
  - `certificate_probes.py`
  - `admission.py`

---

## A. Restoration semantics

### A1: Six concepts, kept separate

All comparisons are made against the time-matched counterfactual defined in ADR-0003 D2.

| Concept | Operational test | Is it restoration? |
|---|---|---|
| Exact state restoration | Identity-preserving canonical equality on every observed field (the existing comparison, `canonical_level == "exact"`) | Yes |
| Approximate restoration | The same comparison, with temperatures within the declared tolerance | Yes, at that tolerance |
| Task-relevant restoration | Every declared property with weight > 0 is restored **on the original object identities**, and at least one of them was meaningfully restored (A4). Other differences may remain | No. It is reported in the trace. It never becomes "reversible", and it is a partial witness only when a *declared* property also remains different (B1). With only undeclared residuals it is unresolved (`declared_properties_restored_but_undeclared_differences_remain`) |
| Structural replacement | A declared property is matched only by a look-alike object with a different uuid, the same name and the same container name (e.g. fresh water refilling the cup) | **No** |
| Compensation | A pre-declared practical-outcome predicate holds (e.g. "a container on the table holds water") while the declared state properties are not restored | **No** |
| Unknown | No comparable evidence: incomplete observation, an exclusion rule, no executed path, or no counterfactual | No conclusion |

Replacement and compensation are recorded as concepts so that they are visible in the trace. They never count towards restoration.

### A2: Pre-registered property declaration

Every case carries a `Declaration`, fixed **before** any simulator run. It contains:

- the restoration definition (B, time-matched counterfactual);
- required properties as `(role, field, weight)`:
  - `role` names exactly one S0 object;
  - `field` is a flattened canonical field, or `present`, `location` or `contents`;
- optional practical-outcome predicates, used only to detect compensation;
- optional extra recovery paths;
- a free-text rationale.

The declaration is hashed (SHA-256) and the hash is stored before the search starts. At admission the declaration is re-hashed. A changed declaration, or a missing `declared_before_search` flag, excludes the case. This is the team's guard against choosing relevant properties retrospectively to obtain a preferred label.

**Selection protocol** (applied when writing a declaration):

1. Include every property the target action is *designed* to change, e.g. a device's `isActivated` or a container's `isOpen`.
2. Include every property a user would observe as the practical consequence, e.g. what a container holds or where an object is.
3. Give weight > 0 only to properties in (1) or (2). Recorded-only properties, such as an incidental temperature, get weight 0.
4. Never add, remove or reweight a property after seeing any search result. A different declaration is a different case, with a new id.

### A3: Tolerances

- Every assessment is computed at 0 °C (exact), 0.01 °C and 0.1 °C.
- 0.01 °C is the **exploratory primary threshold**.
- If the best interpretation at 0.01 °C (reversible, partial or none) differs from that at 0.1 °C, the case is **quarantined** (`temperature_sensitive`). This is ADR-0003 D4, made operational.
- No threshold is claimed to be physically validated.

### A4: Meaningful restoration

A declared property counts as *meaningfully restored* only if all three hold:

- the target changed it relative to the counterfactual (it differs in S1 vs CF(target));
- it equals the counterfactual after recovery, on the original identity;
- it is **not** restored by idling alone for the same number of ticks.

## B. Partial restoration

### B1: Partial witness

A path is a partial witness at tolerance τ if and only if:

1. it was executed on a verified rebuild, using the fixed query protocol (ADR-0003 D8);
2. at least one declared property was meaningfully restored (A4). If any weights are declared, at least one meaningfully restored property must have weight > 0;
3. at least one declared property remains different or replaced (a meaningful residual);
4. the state is not already exact or approximate at τ.

Failure to find an exact path is **never** sufficient. A partial label needs a positive witness **and** a residual. The witness records:

- the restored properties;
- the residual properties;
- the replaced properties;
- `weighted_recovery`, which is reported only and never thresholded.

### B2: Vacuous partials are rejected

The following do not count as partial witnesses:

- a path that restores only properties the target never changed;
- a path that restores properties which come back by idling;
- a path that restores only unweighted properties when weights exist.

### B3: Transparency note: partial-witness rule strengthened after the first run

This is a **revision made after the first complete validation run**. It is not a rule fixed in advance of that run.

**What was wrong.** In the first run, the implementation counted a path as a partial witness when it showed either:
- partial restoration; or
- task-relevant restoration, i.e. all weighted declared properties restored, even if the only remaining differences were **undeclared** fields.

That contradicted B1, which requires a declared residual.

**The change.** A valid partial witness now needs **both**:
- a meaningfully restored property (A4);
- a declared property that is still different or replaced.

The purpose was to make the implementation match the intended definition of partial restoration (`semantics.AttemptAssessment.partial_witness`; `admission._interpretation`). Task-relevant restoration with only undeclared residuals is still reported in the trace, and now gives `declared_properties_restored_but_undeclared_differences_remain`.

**Effect.** Recomputing every case's best interpretation from the final evidence under both definitions shows:
- **Glass jar.** The only case whose reported decision changed. At 0.01 °C its interpretation went from partial to none. Its outcome did not change: it is still unresolved and quarantined as temperature-sensitive (now "none at 0.01 °C vs reversible at 0.1 °C").
- **adv-bee-hive.** Its witness-level interpretation also changes, from partial to none at all three tolerances. Its outcome and reasons do not change, because the stochastic-exposure gate excludes it before witnesses are evaluated.
- **All other cases** are unaffected.

**What did not change.** No pre-registered property declaration was changed: all 15 stored declaration hashes match `label_cases.py`.

**Versioning.**
- The rule label `sw-admission-2` was introduced together with C5. This change went into the same, then-uncommitted version before the final run, without a separate version bump.
- `SEMANTICS_VERSION` (`sw-restoration-semantics-1`) was **not** incremented, so evidence from the first run and the final run carries the same semantics version string.
- All evidence was then regenerated with the final code and decided under `sw-admission-2`.

## C. Certificates

### C1: Proof obligations

A certificate claim is verified (`verified_source_relative`) only if O1 to O8 are all discharged:

- **O1:** precise invariant, horizon and definition.
- **O2:** every occurrence of the protected identifier is classified mechanically, and no write undoes the invariant.
- **O3:** the owning property object is never reassigned in a method.
- **O4:** reflection is limited to type tags.
- **O5:** the audited action space equals `actions/`.
- **O6:** the invariant holds on the pinned simulator.
- **O7:** a bounded counterexample search finds no violation.
- **O8:** no runtime constructor recreates the protected object (replacement or regrowth).

Status follows from the obligations:

- a failed obligation with a counterexample means **rejected**;
- any other open or failed obligation means **provisional**.

A precondition checker returning `precondition_met` is **not** a proof.

### C2: Source-relative, not formal

A verified claim is still **not a formal proof**. It is:

- relative to the pinned source text (e8216d6);
- relative to the heuristic scope scanner;
- relative to the harness API surface (`HARNESS_API`). Researcher-only calls such as `load` and `reset` are outside the horizon.

### C3: Identity loss is not practical irreversibility

A claim that only proves an object's uuid never returns (`identity_loss_only`) is never admissible for an irreversible label. The same statement is true of every deletion (ADR-0003 D3).

### C4: When a certificate applies to a case

A certificate supports an irreversible label for a case only if all of these hold:

- the claim is admissible (verified and not identity loss only);
- its precondition checker returns `MET` on that case's S0 and target;
- the claim covers the case's restoration definition.

If a positive restoration witness also exists, the result is a **contradiction**. The case is quarantined and the certificate is re-examined.

### C5: Coverage of every weighted changed property (added in `sw-admission-2`)

A certificate protects **named fields of named objects**. For example, C-BURN protects `hasCombusted` and `combustionTicks` of the objects its check reports as ignited. Any other weighted property the target changed could still be restored by a path the bounded search missed, and that would make the case partially reversible. So an irreversible outcome needs **every** weighted declared property that the target changed to be covered by a supporting claim (`CERTIFICATE_COVERAGE` in `admission.py`). Otherwise the case stays unresolved, with the reason `certificate_does_not_cover_every_weighted_changed_property`.

**Transparency note.** This rule was added *after* the first full run (`docs/23` §6.3). Under `sw-admission-1`, two cases were admitted as irreversible:
- **cert-burn-chair.** Its weighted `isCombusting` is not protected by C-BURN. An extinguishing path would restore it, as the painting probe showed for a movable object.
- **cert-mix-salt.** Its weighted `water.present` is identity loss of the water, which only the provisional C-EAT/identity-type argument would cover.

In both cases v1 depended on the bounded search for the unprotected properties, which RD-04 forbids. Version 2 is strictly more conservative. No declaration was changed to obtain or avoid a label.

## D. Admission procedure (`sw-admission-2`)

### D1: Inputs

The procedure takes:

- one evidence document (`sw-label-evidence-0.1`), which carries the recipe provenance pinned to e8216d6, the declaration and its hash, the double-rebuild replay check, observation and exclusion signals, the target check, certificate precondition results and all attempts at three tolerances;
- the certificate verification reports.

### D2: Gates, in order

Any gate failure means `unresolved_excluded`, with the reason recorded:

1. evidence schema;
2. pinned provenance;
3. evidence complete (`evidence_<status>`);
4. declaration integrity (`declaration_altered_or_not_preregistered`);
5. replay verified (`incomplete_or_divergent_replay`);
6. target valid, i.e. accepted and with a unique template (`invalid_target`);
7. no door action in the target or history (`hidden_door_state`; ADR-0003 D7);
8. target not a no-op relative to the counterfactual (`no_op_target`);
9. no bee in S0, S1 or S2, no bee action, and the target not involving bees (`uncontrolled_stochastic_process`);
10. every attempt's rebuild fingerprint verified.

### D3: Decision (rule `sw-admission-2`)

The best interpretation (reversible > partial > none) is computed over the usable attempts at 0.01 °C and at 0.1 °C. Then:

1. If the two interpretations differ, the outcome is **unresolved and quarantined** (`temperature_sensitive`).
2. If the result is reversible:
   - with an admissible certificate as well: **unresolved and quarantined** (contradiction);
   - otherwise: **eligible reversible**.
3. If the result is partial: **eligible partially reversible**.
4. If there is no witness, an admissible certificate applies (C4) and it covers every weighted changed property (C5): **eligible irreversible**.
5. Otherwise: **unresolved**, with the reason `no_positive_witness_and_failed_search_is_not_irreversibility`. Replacement, compensation, declared-complete-but-undeclared-residual and certificate-not-admissible details are recorded as further reasons.

The procedure **never** infers irreversibility from a failed bounded or restricted search.

### D4: Outputs

Each decision contains:

- the outcome;
- a `quarantined` flag;
- the reasons;
- the witness or certificate;
- a full trace (each gate, the attempts, the witness at each tolerance, and the certificate);
- the evidence hash;
- `decision_rule_version`;
- `is_gold_label: false`.

"Eligible" means admissible to a *future* gold dataset under this record. No gold label is written anywhere.

### D5: Gold-admission criteria

A ScienceWorld example may enter the eventual gold dataset only if all of these hold:

- it receives an eligible outcome from `sw-admission-2`, or a later version recorded in a new ADR;
- its evidence document is archived with its hashes;
- its outcome is reproduced by a second independent rebuild run;
- for irreversible examples, the certificate report it relies on is `verified_source_relative`, not identity loss only, and its residual risks (C2) are reported alongside the dataset.

Label mapping to the dataset schema (ADR-0003 D5) remains an M1/M2 decision. It is still open.

### D6: Exclusions retained from ADR-0003 D7

The following stay excluded:

- door actions and door history;
- bees outside a closed container;
- plant reproduction;
- ambiguous referents (binding or template ambiguity);
- temperature-sensitive cases.

## Consequences and limitations

- Partial labels depend on declared properties. A different reasonable declaration could give a different outcome. Pre-registration makes this visible but does not remove it.
- `weighted_recovery` is descriptive only. No threshold on it is adopted.
- The certificate scanner is heuristic. It uses brace-based scopes and bounded constructor resolution, and unresolved sites leave a claim provisional. Its conclusions hold only for the pinned source.
- Only a handful of constructed cases have been run (`docs/23` §6). Yields, costs and failure rates at scale are unknown.
- Observations are limited to the canonical object tree. Properties that are not serialised, such as electrical connections per role, cannot be declared directly.
