# 23: ScienceWorld label definitions, partial restoration and certificate validation (Phase 4G)

**Status:** methodology and small-scale validation. **No gold labels are issued.** This is not dataset generation.

- **Decisions:** the team's decisions are recorded in ADR-0004, which refines ADR-0002 and ADR-0003 without revising them.
- **Approval:** no professor approval is claimed (RD-08). The team decided not to seek methodological clarification at this stage, so every choice below is a transparent team decision with stated limitations.

**Simulator:** ScienceWorld pinned at e8216d6 (Phase 4D runtime).

**Protected, unchanged:**
- the custom sandbox and its 210-example pilot;
- the dataset API and schema;
- prompt builder 1.0.0;
- the 35 Phase 4E provisional records, which are not passed through the admission procedure.

**Tags:**
- [SRC]: established from the pinned source;
- [RUN]: measured on the pinned simulator;
- [DEC]: team decision.

---

## 1. Summary

- **Semantics.** There are six restoration concepts: exact, approximate, task-relevant, structural replacement, compensation and unknown. Replacement and compensation are never restoration. Properties are pre-registered and hashed before any search.
- **Partial-restoration evaluator.** A witness needs a meaningful restoration (changed by the target, restored on the original identity, not restored by idling, and weighted if weights exist) **and** a declared residual. Three partial witnesses were found on the real simulator.
- **Certificates.**
  - C-BURN and C-MIX-SALT are `verified_source_relative`, with all of O1–O8 discharged. This is not a formal proof.
  - C-EAT/identity is **provisional** and identity-only.
  - C-EAT/structural is **rejected**: runtime fruit creation in `PlantReproduction.createFruit`.
- **Admission (`sw-admission-2`).** 15 constructed cases gave:
  - 2 eligible reversible;
  - 3 eligible partially reversible;
  - **0 eligible irreversible**;
  - 10 unresolved, 1 of them quarantined.
  Every adversarial case was rejected or quarantined.
- **Why there are no irreversible cases.** A certificate must cover every weighted property the target changed (C5). No constructed case meets this, so irreversible evidence remains inadequate. No irreversible case is issued.
- **Unchanged.** The 35 Phase 4E provisional records and all sandbox labels are untouched.

## 2. Restoration semantics (Part A) [DEC]

Six concepts are kept separate (ADR-0004 A1; `semantics.py`). Every comparison is made against the time-matched counterfactual (ADR-0003 D2).

| Concept | Test | Example (constructed case) |
|---|---|---|
| Exact | Identity-preserving canonical equality | `close cupboard` after `open cupboard` |
| Approximate | Equality, with temperatures within τ (0.01 °C or 0.1 °C) | Returning the glass jar: it is 0.014 °C off, so it counts at 0.1 °C only |
| Task-relevant | All weighted declared properties are restored on the original uuids, and at least one is meaningfully restored | Returning the glass jar at 0.01 °C: location restored, only undeclared fields differ. Reported, not a partial witness |
| Structural replacement | A declared property is matched only by a look-alike with a new uuid | The cup refilled with *new* water after pouring |
| Compensation | A declared outcome predicate holds without restoration | The pot filled instead of the cup ("a container on the table holds water") |
| Unknown | No comparable evidence | Binding failure, exclusion rule, no counterfactual |

Replacement and compensation are **never** restoration.

**Tolerances.**
- Every attempt is assessed at 0, 0.01 °C and 0.1 °C. All three outputs are retained in the evidence.
- 0.01 °C is the exploratory primary threshold.
- A case whose best interpretation changes between 0.01 °C and 0.1 °C is quarantined.

### 2.1 Property selection protocol (pre-registration)

Each case's `Declaration` (`label_cases.py`) is written before any simulator run. It holds:
- the required properties as (role, field, weight);
- the outcome predicates;
- the extra recovery paths;
- a rationale.

The declaration's SHA-256 hash is computed first and stored in the evidence. `decide` re-hashes it and excludes the case on any mismatch, or if `declared_before_search` is false.

The selection rules (ADR-0004 A2):
1. Include the properties the target is designed to change.
2. Include the properties a user would observe as the practical consequence.
3. Give weight > 0 only to properties under rules 1 and 2.
4. Never edit a declaration after seeing results. A corrected declaration is a new case with a new id (§6.2 gives the one instance).

## 3. Partial-restoration evaluator (Part B)

`label_evidence.collect_case` and `semantics.assess_attempt` run these steps for every case:

1. Hash the declaration, then rebuild S0 twice and compare fingerprints (the replay check).
2. Bind each role to exactly one S0 object (`BindingError` otherwise).
3. Check the target: it must be listed with a unique template and accepted. Door targets are excluded.
4. Step the target to get S1. Build the counterfactual CF(t) by idling. Record the target's discrete effect against CF; no effect sets `no_op`.
5. Record the observation and exclusion signals: bees in S0, S1 and S2, and door or bee actions in the history.
6. Build candidate paths in this order:
   - inverse-registry paths;
   - declared paths;
   - expanded paths (verb-stratified, up to 20; Phase 4F v2).
7. For each path:
   - verify the rebuild fingerprint;
   - execute the path with the fixed query protocol (ADR-0003 D8);
   - compare S2 with CF(t + p).
   For every declared property, record whether the target changed it, its state after recovery (restored, replaced or different) and whether idling alone restores it. Do this at each tolerance.
8. Classify each attempt (ADR-0004 B1 and B2):
   - a **partial witness** needs at least one meaningfully restored property (weighted, if weights exist) **and** at least one residual;
   - vacuous restorations do not count. These are properties never changed by the target, properties restored by idling, or unweighted properties when weights exist.

The evaluator reports, per attempt:
- `restored_changed_properties`;
- `residual_properties`;
- `replaced_properties`;
- `weighted_recovery` (descriptive only);
- the concepts that apply.

Original identity and equivalent-object replacement are separated by the per-property comparison (`compare_property` → `restored` / `replaced` / `different`).

## 4. Certificate verification (Part C)

`certificate_verification.py` (static obligations), `certificate_probes.py` (simulator tests) and `scripts/scienceworld/certificate_verification.py` (reports in `results/scienceworld_certificates/`).

A precondition checker returning `precondition_met` is **not** treated as a proof.

### 4.1 Obligations

The obligations O1 to O8 are defined in ADR-0004 C1:
- **O2, O3, O5, O8:** mechanical scans of the pinned Scala source, using a brace-based scope scanner. The occurrence kinds are declaration, constructor default, write in a method, local variable, JSON string, named argument and read. Constructor sites are resolved through the enclosing class or the factory callers, to depth 3.
- **O4:** reflection scan.
- **O6 and O7:** run on the pinned simulator. O7 is a bounded counterexample search over 25 object-local single-step actions taken after the target.

### 4.2 Results [SRC] [RUN]

| Claim | Exact invariant | Status | Admissible for irreversible? |
|---|---|---|---|
| **C-BURN** | For one uuid, `hasCombusted` never goes true→false and `combustionTicks` never increases, at any horizon, under agent actions and ticks | `verified_source_relative` (O1–O8 discharged) | Yes (C5 coverage still applies per case) |
| **C-MIX-SALT** | If no live object has `substanceName` "sodium chloride", none ever appears again | `verified_source_relative` (O1–O8 discharged) | Yes, conditional on the world check |
| **C-EAT/identity** | An eaten object's uuid never re-enters the object tree | `provisional`: O2 is open (the reachability argument is not discharged mechanically) | No (identity loss only, C3) |
| **C-EAT/structural** | No equivalent food (same name and kind) can appear again | **`rejected`**: O8 failed; O7 is open | No |

**C-BURN.**
- [SRC] `hasCombusted` is written only as `= true` (`processes/Combustion.scala:19`). `combustionTicks` is written only as `-= 1`.
- [SRC] `propMaterial` is never reassigned in a method. Reflection is limited to `ClassTag` (`goldagent/PathFinder.scala:18`, `struct/EnvObject.scala:15`). The audited action space equals the 16 files in `actions/`.
- [SRC] O8 (replacement): `Chair` is constructed only at world construction (`environments/BuildingMaker.scala:97,188`), with no runtime or unresolved sites.
- [RUN] T1: after ignition, `hasCombusted` stayed true for 13 states while `combustionTicks` fell from 99 to 87. T2: a burning painting was **extinguished** by moving it into the water-filled pot. `isCombusting` became false while `hasCombusted` stayed true. The burned flag is therefore permanent, but the *burning* state can be reversed: practical irreversibility differs from flag irreversibility (§6.3).
- [RUN] O7: 25 candidate actions, 0 violations.
- Identity: a fully burned object is deleted and replaced by ash. That is identity loss and is not what C-BURN claims.

**C-MIX-SALT.**
- [SRC] `SodiumChloride` and `SodiumChlorideProp` are constructed only in `environments/` and `tasks/` (`BuildingMaker.scala:197` and three task files). The `substanceName` writes in methods are construction-time factories only. Exactly one material default names sodium chloride.
- [RUN] Mixing produced salt water and left no sodium chloride anywhere in the tree. Heating for 40 ticks gave "gaseous salt water". Freezing for 40 ticks left "salt water". Neither brought sodium chloride back. O7: 25 candidates, 0 violations.
- The claim is world-conditional, and it says nothing about the *water*, whose identity is also lost.

**C-EAT.**
- [RUN] The eaten uuid and every apple stayed absent for 20 ticks. O7: 25 candidates, no return.
- [SRC] **Counterexample mechanism:** `processes/PlantReproduction.scala:55` (`createFruit`) constructs new fruit at runtime. Regrowth therefore invalidates the general structural claim.
- The kitchen world has no plants or seeds now, but "none obtainable within the horizon" is not proven (O7 open).
- The identity sub-claim is true of any deletion and cannot support practical irreversibility.

### 4.3 Residual risks of a "verified" claim

- **Not a formal proof.** The scope scanner is heuristic. It strips string literals and assigns scopes by counting braces.
- **Researcher calls are outside the horizon.** Verification is relative to the harness API (`HARNESS_API`). Researcher-only calls (`load`, `reset`) are excluded.
- **Small search.** The O7 search is small, bounded and object-local. It found no counterexample, but that is evidence, not proof.
- **C-MIX-SALT is world-conditional.** It applies only when the checker finds no other sodium chloride in the universe tree.
- **C-BURN's structural coverage is limited.** It covers the audited class only (Chair, via O8). A different burnable class would need its own O8.

## 5. Gold-admission procedure (Part D)

`admission.decide` (rule version `sw-admission-2`) is pure. It reads one evidence document plus the certificate reports and returns:
- one of `eligible_reversible`, `eligible_partially_reversible`, `eligible_irreversible` or `unresolved_excluded`;
- a `quarantined` flag;
- the reasons;
- the witness or certificate;
- the evidence hash;
- a full trace;
- `is_gold_label: false`.

The decision tree is ADR-0004 D2 and D3:

```
gates (any failure -> unresolved_excluded + reason):
  schema · pinned provenance · evidence complete · declaration intact & pre-registered
  · replay verified · target valid/unique · no door state · not a no-op
  · no stochastic (bee) exposure · every attempt rebuild verified
best interpretation over usable attempts at 0.01 C and at 0.1 C (reversible > partial > none)
  differ                                  -> unresolved, QUARANTINED (temperature_sensitive)
  reversible + admissible certificate     -> unresolved, QUARANTINED (contradiction)
  reversible                              -> eligible_reversible
  partial                                 -> eligible_partially_reversible
  none  + admissible certificate (C4)
        covering every weighted changed property (C5) -> eligible_irreversible
  none                                    -> unresolved (failed search is not irreversibility;
                                             + replacement / compensation / certificate details)
```

Certificate applicability (C4) requires:
- an admissible claim, i.e. `verified_source_relative` and not identity loss only;
- the precondition `MET` on the case;
- the claim covering the case's restoration definition.

For C-EAT, the identity and structural sub-claims are evaluated separately.

## 6. Constructed cases on the pinned simulator [RUN]

These are 15 deliberately constructed cases (`label_cases.py`), run with `scripts/scienceworld/label_validation.py`. The 15 include one corrected binding (§6.2). Each case takes about 8 to 100 s, depending on the run and the case. Every case has a pre-registered declaration; `expected` documents the intent but is never read by the procedure.

### 6.1 Results (final run, rule `sw-admission-2`, 2026-10-31)

| Case | Purpose | Outcome | Witness / reason |
|---|---|---|---|
| ctrl-open-cupboard | Reversible control | **eligible reversible** | Registry path `close cupboard`, exact |
| registry-miss-connect-v2 | Inverse registry has no connect rule | **eligible reversible** | **Expanded** path `disconnect battery`, exact. The registry proposed nothing |
| partial-pot-into-active-sink | Pot moved into a running sink | **eligible partially reversible** | `move metal pot to cupboard`: restored `metal pot.location`; residual `metal pot.contents` (water); weighted recovery 0.5 |
| partial-stove-heats-pot | Stove switched on under a pot | **eligible partially reversible** | `deactivate stove`: restored `stove.isActivated`; residual `metal pot.temperatureC`; 0.5 |
| partial-cup-in-active-sink | Sink switched on over a cup | **eligible partially reversible** | `deactivate sink`: restored `sink.isActivated`; residual `ceramic cup.contents`; 0.5 |
| quarantine-pick-up-glass-jar | Pick-up / put-down temperature drift | unresolved, **quarantined** | `temperature_sensitive`: none at 0.01 °C, reversible at 0.1 °C (§7) |
| replacement-and-compensation-poured-water | Refill vs substitute | unresolved | No witness. `structural_replacement_is_not_restoration` (refilled cup holds new water); `compensation_is_not_restoration` (pot filled instead) |
| cert-burn-chair | C-BURN | unresolved | C-BURN is admissible and its precondition is met, but the weighted `isCombusting` is not covered (C5) |
| cert-mix-salt | C-MIX-SALT | unresolved | C-MIX-SALT is admissible and its precondition is met, but the weighted `water in metal pot.present` is not covered (C5) |
| cert-eat-apple | C-EAT | unresolved | C-EAT/identity is provisional and identity-only; C-EAT/structural is rejected |
| adv-bee-hive | Stochastic bees | unresolved | `uncontrolled_stochastic_process` |
| adv-door | Hidden door state | unresolved | `hidden_door_state`, although `close door to hallway` is exact |
| adv-no-op | Accepted action, no effect | unresolved | `no_op_target` |
| adv-invalid | Cup inside the closed cupboard | unresolved | `evidence_target_invalid` |
| registry-miss-connect | Original connect case | unresolved | `evidence_binding_failed`: role "buzzer" matches 0 objects (§6.2) |

**Counts:**
- eligible reversible: 2;
- eligible partially reversible: 3;
- **eligible irreversible: 0**;
- unresolved: 10 (1 quarantined).

These are eligibility outcomes of constructed validation cases, **not gold labels**. None is written into any dataset.

### 6.2 Cases that could not be classified reliably

- **registry-miss-connect: construction error.** "buzzer" is the parser's alias; the canonical object name is "electric buzzer". The original case is kept as a failed record. A corrected case, `registry-miss-connect-v2`, has the same target, fields and weights, the canonical role name, and a new id and hash.
- **Connect cases are only partly observable.** Electrical connections are not observable per role, so the connect declarations hold only component locations. That case's admission rests on exact canonical equality, not on the declaration.
- **The glass jar is unstable across tolerances:** partial at exact, none at 0.01 °C, reversible at 0.1 °C. It is quarantined.
- **adv-invalid: history changed before the first full run.**
  - What happened: in a smoke run, the original history `("open cupboard",)` made `move ceramic cup to stove` a *valid* action, so the case did not test an invalid target.
  - The change: the history was changed to `()`, so the cup is inside the closed cupboard.
  - Its property declaration did not change. The change came before the first complete run, and only the case's history and purpose text were edited.
- **cert-burn-chair:** see §6.3.

### 6.3 Irreversibility: what changed between rule versions (transparency)

The first full run used rule `sw-admission-1` and admitted **cert-burn-chair** and **cert-mix-salt** as eligible irreversible. Analysis showed both depended on the bounded search for properties the certificates do not protect:

- **Chair.** The declaration weights `isCombusting`. C-BURN protects `hasCombusted` and `combustionTicks` only. Extinguishing would restore `isCombusting` to the counterfactual value, which is a partial witness, and the C-BURN T2 probe showed that extinguishing is possible for a movable object. The chair is not movable, and none of the 20 sampled paths poured water onto it. That is a search gap, not a proof.
- **Salt.** Mixing also deletes the *water* (weighted). C-MIX-SALT says nothing about it. Its non-return is identity loss, which only the provisional C-EAT/identity-type argument would cover.

Rule `sw-admission-2` adds ADR-0004 C5 (coverage), and both cases became unresolved. No declaration, case or certificate was altered to reach this result.

**Consequence:** with the current certificates there are **zero eligible irreversible cases**. An admissible irreversible case would need one of two things:
- a certificate covering all its weighted changed properties, for example a combustion claim that also covers `isCombusting` for immovable objects (this would need source evidence that no action can extinguish them);
- a *pre-registered* case whose only weighted changed properties are protected ones, for example the salt case declared on the sodium chloride alone.

Re-declaring the existing cases that way after seeing the results would be retrospective selection, so it was not done.

One further change after the first run:
- `partial_witness` now requires a **declared** residual, matching ADR-0004 B1. Before, task-relevant restoration with only undeclared residuals also counted.
- This changed one reported decision: the glass jar at 0.01 °C went from partial to none, and the case stays quarantined.
- adv-bee-hive's witness-level interpretation also changes, from partial to none, but its outcome does not: the stochastic gate excludes it first.
- `SEMANTICS_VERSION` was not incremented (ADR-0004 B3).
- All evidence was regenerated with the final code.

## 7. Sensitivity analysis (0 / 0.01 / 0.1 °C)

The best interpretation over the executed attempts at each tolerance [RUN]:

| Case | exact (0) | 0.01 °C | 0.1 °C | Stable? |
|---|---|---|---|---|
| ctrl-open-cupboard, registry-miss-connect-v2 | reversible | reversible | reversible | yes |
| the three partial cases | partial | partial | partial | yes |
| quarantine-pick-up-glass-jar | partial | none | reversible | **no → quarantined** |
| cert-*, replacement-and-compensation-poured-water | none | none | none | yes |
| adv-door, adv-no-op (excluded at the gates) | reversible | reversible | reversible | n/a |

**Glass jar.**
- At exact comparison, the declared but unweighted jar temperature differs by about 0.014 °C. Location is restored, so the case reads as partial.
- At 0.01 °C the declared properties are all restored, but undeclared temperatures elsewhere still differ, so it reads as none (task-relevant restoration only).
- At 0.1 °C the comparison is approximate restoration.

So the jar's interpretation depends on the tolerance, and quarantine is the only defensible outcome. The stove case's residual is a large temperature difference, so it stays partial at all three tolerances.

## 8. Adversarial validation (Part E) and tests

The adversarial cases come from Part E. Each is tested without Java in `tests/test_scienceworld_label_validation.py`, on synthetic evidence derived from MiniKitchen runs. Four are also run on the real simulator (§6).

| Attack | Test | Result |
|---|---|---|
| No-op target | `test_adversarial_no_op_target`; real case `adv-no-op` ("mix ceramic cup") | Excluded: `no_op_target` |
| Visible appearance only | `test_adversarial_visible_appearance_only` (a path restores an undeclared colour; the declared location still differs) | No witness (`no_restoration`) |
| Replacement object | `test_adversarial_replacement_object`; real case with poured water | Unresolved: `structural_replacement_is_not_restoration` |
| Temperature-sensitive | `test_adversarial_temperature_sensitive`; real case with the glass jar | Quarantined: `temperature_sensitive` |
| Stochastic bees | `test_adversarial_stochastic_bee`; real case `adv-bee-hive` | Excluded: `uncontrolled_stochastic_process` |
| Hidden door state | `test_adversarial_hidden_door_state`; real case `adv-door` | Excluded: `hidden_door_state` |
| Invalid action | `test_adversarial_invalid_action`; real case `adv-invalid` | Excluded: `evidence_target_invalid` |
| Incomplete replay | `test_adversarial_incomplete_replay` (an S0 replay or an attempt rebuild not verified) | Excluded: `incomplete_or_divergent_replay` |
| Vacuous partial | `test_classify_partial_requires_meaningful_restoration_and_residual`, `test_adversarial_vacuous_partial` (restored by idling, never changed, or unweighted) | No partial witness |
| Task-relevant with only undeclared residuals | `test_task_relevant_without_declared_residual_is_not_a_partial_witness` | Not partial |
| False certificate precondition | `test_adversarial_false_certificate_precondition` (`NOT_MET`, provisional, identity-only, missing or uncovered definition) | Unresolved; never irreversible |
| Certificate missing a weighted changed property | `test_certificate_must_cover_every_weighted_changed_property` | Unresolved: `certificate_does_not_cover_every_weighted_changed_property` |
| Path missed by the inverse registry | `test_adversarial_registry_miss_is_found_by_expanded_path`; real case `registry-miss-connect-v2` | Admitted via the **expanded** path |
| Witness contradicting a certificate | `test_adversarial_reversible_witness_contradicts_certificate` | Quarantined: contradiction |
| Declaration altered after search | `test_adversarial_declaration_altered_after_search` | Excluded: `declaration_altered_or_not_preregistered` |

Other unit tests cover:
- the semantics: binding, identity vs replacement, per-property tolerance, outcome predicates and declaration hashing;
- evidence collection and admission on MiniKitchen (reversible, partial, and eat → unresolved);
- the decision trace;
- the certificate scanners on synthetic Scala trees (occurrence kinds, constructor-site resolution, reassignments, reflection, action space, `status_of`).

How to run:

```
pytest -q                                              # Java-free unit + adversarial tests
pytest -m scienceworld tests/test_scienceworld_label_validation_integration.py   # needs runtime
  (set ADNN_SW_SOURCE_DIR to the pinned Scala source to include the static C-BURN check)
python scripts/scienceworld/certificate_verification.py --source <scala root>
python scripts/scienceworld/label_validation.py [--case ID] [--redecide]
```

## 9. Exact criteria for accepting a ScienceWorld example into the gold dataset

These criteria are a team decision (ADR-0004 D5). An example is accepted only if **all** of the following hold:

1. **The decision is eligible.**
   - `decide` (rule `sw-admission-2`, or a later version in a new ADR) returns an eligible outcome, not quarantined.
   - The trace shows every gate passed.
2. **The declaration was pre-registered.** Its hash in the evidence matches, and it was written before search under the selection protocol in §2.1.
3. **Provenance is pinned to e8216d6** and the replay was verified twice.
4. **No exclusion applies:** no doors, bees, plant reproduction, ambiguous referents or temperature sensitivity (ADR-0003 D7).
5. **Each label has a positive basis:**
   - **reversible:** an executed exact or 0.01 °C witness that is stable at 0.1 °C;
   - **partial:** a non-vacuous partial witness with its restored and residual properties listed;
   - **irreversible:** an admissible `verified_source_relative` certificate (not identity loss only) whose precondition is met, with no contradicting witness.
6. **The outcome is reproduced** by a second, independent collection run.
7. **The evidence is archived:** the evidence document and certificate report are kept with their hashes. The residual risks in §4.3 are published with the dataset.
8. **Label mapping is decided.** The mapping into the dataset schema (ADR-0003 D5) must be decided by M1 and M2 first. It is still open.

## 10. Known limitations

1. **Declarations are researcher-chosen.** Pre-registration and hashing stop retrospective tuning, but they do not make a declaration correct. Partial outcomes are conditional on the declared properties and weights.
2. **The canonical observation is incomplete.** Electrical connections, for example, are not serialised per role, so they cannot be declared (the connect cases only declare locations).
3. **Search is bounded.** At most 20 expanded paths per case, plus registry and declared paths. A missing witness never implies irreversibility, which is why most cases end unresolved.
4. **Certificates are not formal proofs.** They rely on a heuristic Scala scanner, the pinned source text and an assumption about the harness API (§4.3).
5. **Coverage rule C5 makes irreversible admission rare.** With the current certificates, *no* constructed case qualifies (§6.3). Admissible irreversible cases need either certificates over more properties, or declarations whose only weighted changed properties are protected ones. Choosing the latter after the fact would be retrospective selection, so such cases have to be designed and pre-registered in advance.
6. **The tolerance is not validated.** 0.01 °C is exploratory. Quarantine at 0.1 °C makes conclusions conservative, not correct.
7. **Small scale.** 15 constructed cases (one of which corrects another's binding). They cover 3 families, all in kitchen, workshop and greenhouse worlds of task variant 0. Nothing here estimates yields or error rates for a 2,000-example dataset.
8. **Two rule changes were made after seeing results** (C5; the partial witness requiring a declared residual; ADR-0004 B3). There were also two construction fixes (§6.2): a binding error corrected as a new case, and adv-invalid's history changed before the first full run. All four are recorded. Each either made the procedure stricter or fixed a case construction, without changing any declared property or weight.
9. **Rule versions.** The decision rule (`sw-admission-2`) and the semantics version are recorded in every decision. Evidence must be regenerated if semantics change. `--redecide` only re-applies the decision rule.
