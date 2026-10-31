# 24: ScienceWorld irreversibility evidence and declaration reliability (Phase 4H)

- **Status:** research report (Phase 4H). Nothing in it is a gold label. **No professor approval is claimed.** No professor consultation is planned (ADR-0002 project decision).
- **Pins:**
  - Phase 4G commit `5b74630929f80e4f4a5973019e2fb2286142fbd2`;
  - decision rule `sw-admission-2`, unchanged in this phase;
  - semantics `sw-restoration-semantics-1`;
  - evidence `sw-label-evidence-0.1`;
  - ScienceWorld `e8216d6`.
- **Decision record:** `docs/decisions/0005-scienceworld-label-reliability.md`.
- **Evidence tags:** [SRC] pinned Scala source, read-only; [RUN] pinned simulator; [DEC] team decision.
- **Code:**
  - `preregistration.py`
  - `phase4h_cases.py`
  - `declaration_reliability.py`
  - `certificate_audit.py`
  - `scripts/scienceworld/phase4h_{freeze,certificates,run}.py`
- **Frozen artefacts (committable, hashed):** `docs/preregistration/`.
- **Generated results (git-ignored):**
  - `results/phase4h/`
  - `results/scienceworld_certificates_4h/`

## 1. Summary

| Question | Answer |
|---|---|
| Can ScienceWorld support defensible irreversible examples? | **Not under the current admitted certificates: 0 eligible irreversible out of 12 new pre-registered cases** (and 0 out of 15 in Phase 4G). One narrower, world-conditional claim, `C-EAT/structural-plantless`, now has all eight obligations discharged *source-relatively*. If a new rule version registered it, one case (`h4-eat-banana`) would become eligible irreversible (§4.3, §6). This is a what-if for review, not a result. |
| Are property declarations reliable enough for gold labels? | **Not yet established.** No human second declaration exists. A rule-based generator agrees with the team's declarations exactly on 8 of 12 cases. Property choice changed **1 of 12** admission outcomes: the freezer case, unresolved under M1 and partial under the rubric (§5). That alone rules out treating declarations as settled. |
| Reversible and partial yield | 3 eligible reversible (fridge, move cup, battery connection) and 2 eligible partially reversible (both burn cases). All 5 replicated in a second fresh process, and all 5 were unaffected by query order (§6). |
| Recommended dataset design | ScienceWorld provides **reversible and partially reversible examples plus a small, explicitly world-conditional irreversible slice**, if and only if a new ADR registers the plantless claim. Otherwise ScienceWorld is reversible/partial only and irreversible examples come from the sandbox. **Do not force three-class balance in ScienceWorld** (§8). |

**Team decisions after review (ADR-0005 R9; no professor contact or approval):**
- OQ-46 accepted: no forced three-class balance in ScienceWorld.
- OQ-44 deferred: the plantless claim stays unregistered and exploratory.

**Four distinctions this report keeps throughout:**
1. **Source-relative assurance is not mathematical proof.** Certificates are audits of the pinned Scala source under stated assumptions (§4).
2. **Reproducibility is not independent scientific validation.** Two processes of one deterministic simulator agreeing (§6) is reproducibility only.
3. **A rule-based comparison is not human inter-annotator agreement.** No human annotator exists (§5).
4. **Eligible outcomes are not gold labels.** Nothing here is exported as a label (§7).

## 2. Audit of the admission rule (Part 1)

### 2.1 Why C-BURN and C-MIX-SALT failed v2 coverage (reconstructed)

`decide` (`admission.py`) admits `eligible_irreversible` only under all of these conditions:
1. there is no positive witness at either tolerance;
2. some named claim `supports_irreversible`, meaning the report is admissible, the precondition is `MET` and the declared definition is covered;
3. `_coverage` finds every weighted property that the target changed among the claim's protected `(uuid, field)` pairs.

`CERTIFICATE_COVERAGE` lists the protected fields:
- C-BURN: `hasCombusted` and `combustionTicks`;
- C-MIX-SALT: `present`.

Both 4G cases failed condition 3:
- **cert-burn-chair:** weighted `isCombusting` changed false→true and is not protected.
- **cert-mix-salt:** weighted `water in metal pot.present` changed and is not protected. The C-MIX-SALT checker binds the sodium chloride only.

### 2.2 Hidden assumptions found

| # | Assumption | Where | Consequence |
|---|---|---|---|
| H1 | **Counterfactual measurement asymmetry.** CF(t) is S0 plus idle ticks. The attempt branch runs `valid_action_templates()` after the target; the CF branch does not. | `label_evidence.py` | Harmless in deterministic worlds (Phase 4F), but not proven neutral where the global RNG matters (bees, ambiguous referents). The stochastic gate is the only protection. |
| H2 | **Recovery starts immediately and is single-step** in the expanded search. `EXCLUDED_RESTORATION` drops `wait*`, `look*`, `focus` and similar commands. | `restoration_diagnostics.py` and `label_evidence.py` | Restoration that needs time (cooling, regrowth) can never be found. "No witness" is search-relative in time as well as in depth. |
| H3 | **Identity is S0 uuids only.** Roles bind S0 objects; objects created by the target cannot be declared. | `semantics.bind` | Products (ash, salt water) are invisible to declarations. Replacement is detected only through the `REPLACED` concept. |
| H4 | **Observation completeness is recorded but not gated.** Every canonical state carries `incomplete_reasons` (portals absent from the tree, remote doors, agent internals). `decide` gates only door actions. | `canonical.py` and `admission.py` | Certificate checks quantify over "the tree", so C-MIX-SALT and plantless preconditions assume that the tree contains every object of interest. |
| H5 | **Weights act only as flags.** `weight > 0` makes a property required. `weighted_recovery` is descriptive only. If no property is weighted, all are required. | `admission._coverage` | Partial versus none never depends on numeric weights, only on the 0/1 choice, so the 0/1 choice is the sensitive decision (§5). |
| H6 | **"Changed by target" comes from the first assessed attempt at 0.01 °C.** If there are no attempts, every weighted property is required. | `admission._coverage` | Defensible, but tolerance-dependent: a property that changes by 0.005 °C is not required. |
| H7 | **Certificate scope is per class or per world.** The C-BURN structural O8 audited `Chair` only. The C-EAT structural check counted living non-bee lifeforms only and ignored flowers, pollen and seeds. | `certificate_verification.py` and `certificates.check_eat` | The 4G C-EAT/structural claim was rightly rejected; its checker's precondition is weaker than the property it needs (§4.3). |
| H8 | **Permitted actions are the 25 action files** under `actions/`. Researcher `load`/`reset` are excluded. Teleport is enabled (`teleportAction` simplification). | O5 | Claims are relative to this simplification set. |

### 2.3 Proof obligations (formal statements)

Notation:
- `T` is the transition relation of the pinned simulator under agent actions `A` (O5) and ticks;
- `Reach(s)` is the set of states reachable from `s` by any finite sequence over `A`;
- `obj(s)` is the set of live uuids in the full object tree of `s`. This is not the observed tree; H4 is where the two differ;
- `f(s, u)` is field `f` of object `u`;
- `D` is a declaration with weighted required set `W = {(r, f) : weight > 0}`;
- `β` is the S0 binding;
- `CF_t` is the counterfactual at time `t`;
- `δ` is the tolerance.

- **Reversible(D, H):** there is a path `p` with `|p| ≤ H` from `s1` such that, for every `(r, f) ∈ D.required`, `|f(p(s1), β(r)) − f(CF_{t+|p|}, β(r))| ≤ δ`, with identity: the same uuid, not a replacement. In addition:
  - all canonical differences are within `δ` (exact canonical equality), and
  - this holds for both `δ = 0.01` and `δ = 0.1`.
- **Partial(D, H):** there is a path `p` with `|p| ≤ H` such that:
  - some changed `(r, f) ∈ W` is restored, and
  - some changed `(r', f') ∈ D.required` remains unrestored, and is declared.

  As a statement about the world, it adds `¬Reversible(D, H)`. **The procedure can establish only the first part**, because the absence of a reversible path is search-relative (§7).
- **Irreversible(D):** for every changed `(r, f) ∈ W` and every `s ∈ Reach(s1)`, `f(s, β(r))` is not within `δ` of `f(CF, β(r))` at any time, and the restoration is not achieved by a replacement object. A certificate for property `(r, f)` must discharge:
  - **O-inv:** an invariant `I` with `I(s1)` and `I(s) ∧ s→s' ⇒ I(s')` over all of `A` and ticks;
  - **O-sep:** `I(s) ⇒ (r, f)` differs from its CF value;
  - **O-reattach:** detached or deleted objects never re-enter `obj(·)`;
  - **O-create:** no runtime construction path re-creates an object satisfying the role. This applies only to structural (class-level) claims;
  - **O-scope:** the precondition checker implies the invariant's hypothesis. For tree-quantified hypotheses this requires completeness of `obj(·)` (H4);
  - **O-cover:** every changed `(r, f) ∈ W` is protected (ADR-0004 C5).

  A failed search discharges none of these.

## 3. Pre-registered cases (Part 2)

The cases were frozen by `phase4h_freeze.py` at 2026-10-31T15:27:40Z, **before any recovery experiment**. The S0 state was built for every case, but no target was executed. Every record is pinned to the Phase 4G commit and `sw-admission-2`, and its SHA-256 is in `docs/preregistration/phase4h_manifest.json`. `phase4h_run.py` refuses to run if any record differs from the manifest, and a unit test checks the same. No declaration was changed after the freeze.

**Freeze timing check:**
- The manifest was written at 20:57:40 IST (15:27:40Z).
- The first certificate experiment output appeared at 21:04 IST, and the first case evidence at 21:06 IST.
- The scratch probes before the freeze (20:48–20:52 IST) only built S0 states and listed valid actions. They executed no frozen target and no recovery path.
- Prior knowledge from Phase 4G was available and is disclosed below, for example the 4G C-BURN probe showing that a movable burning object can be extinguished.

**Selection rule [DEC]:** one or two cases per state-changing action category (container, movement, liquid transfer, thermal, chemistry, combustion, consumption, electrical, navigation). They were chosen for representativeness, not certifiability, and are spread across the four expected categories.

**Disclosure:**
- The combustion and consumption source had been read (Part 4) before the freeze.
- The burn cases' declared extinguishing paths are hypotheses taken from `Combustion.scala` and are labelled as such in the records.
- The pre-registered annotator protocol (`PHASE4H_ANNOTATOR_PROTOCOL.md`) was written after the freeze. It restates the frozen rubric and is not covered by the manifest hash; the rubric itself is covered.

| Case (hash prefix) | World / history | Target | Weighted properties (w=1) | Recorded (w=0) | Expected category |
|---|---|---|---|---|---|
| h4-open-fridge (ce9a6f6e9b71) | 1-1 kitchen | open fridge | fridge isOpen; juice temperatureC | wood cup location | likely reversible |
| h4-move-cup-to-table (41c5688927a1) | open cupboard | move ceramic cup to table | cup location | cup temperatureC | likely reversible |
| h4-pour-juice-into-sink (d291bc9c8aae) | open fridge | pour cup containing orange juice into sink | wood cup contents; juice present | sink contents | potentially irreversible |
| h4-cup-water-to-freezer (cbf88df70be3) | fill cup, open freezer | move ceramic cup to freezer | cup location; water temperatureC; water stateOfMatter | | likely partial |
| h4-mix-soap-water (f6720b2acc7c) | fill pot, soap into pot | mix metal pot | soap present; water present | pot contents | potentially irreversible |
| h4-mix-salt-two-salts (4908493e871a) | 6-1 var 8, salt into pot | mix metal pot | sodium chloride present; water present | pot contents | unknown (C-MIX-SALT precondition test) |
| h4-burn-painting-water-near (ba4a15fc68da) | fill pot | use lighter on painting | hasCombusted; isCombusting | present | likely partial |
| h4-burn-chair-water-near (fd28e3c65ae8) | fill pot | use lighter on chair | hasCombusted; isCombusting | present | likely partial |
| h4-eat-banana (89bb19b33f28) | 1-1 kitchen (no plants) | eat banana | banana present | bowl contents | potentially irreversible |
| h4-eat-apple-plant-world (f01629b7c149) | 4-1 kitchen (apple tree) | eat apple | apple present | bowl contents | unknown (regrowth control) |
| h4-connect-battery-wire (704365fecd72) | 3-1 workshop | connect anode in battery to orange wire terminal 1 | both terminals' connectedTo | | unknown |
| h4-teleport-to-workshop (cd5be2b06ba5) | 1-1 kitchen | teleport to workshop | agent location | | likely reversible |

Every record also holds:
- a one-line rationale per property;
- identity requirements: the S0 uuid is primary, and a new uuid counts as replacement, never restoration;
- the horizon and restoration criterion. The defaults are the registry plus declared paths plus a 20-path, single-step expanded search, with exact or tolerance comparison against CF(t);
- observation limitations: the base incompleteness plus case-specific items.

## 4. Certificate evidence (Part 4) [SRC] [RUN]

`scripts/scienceworld/phase4h_certificates.py` produces the reports in `results/scienceworld_certificates_4h/`. The 4G reports that admission reads are unchanged.

**Shared new evidence: O-reattach (O2) is discharged source-relatively.**
- All 88 runtime `addObject` sites outside `environments/` and `tasks/` were classified:
  - 63 fresh;
  - 13 tree contents;
  - 3 agent;
  - 3 self-move (bee);
  - 2 parsed referents (tree walks);
  - 1 pass-through (inclined plane);
  - 3 constructor bodies.
- 0 sites are unreviewed and 0 reviews are stale.
- Agent referents come from `InputParser.collectAccessibleObjects` (a tree walk), and ticks recurse through the tree only. So a detached object (`ActionEat` calls only `removeAndResetContainer()`) is never referenced or ticked again.
- 22 sites rely on a manual justification recorded in `certificate_audit.REVIEWED_SITES`. A unit test checks that a new unreviewed site makes O2 fail.

### 4.1 C-BURN

- **Pathways [SRC].** `Combustion.scala` has three kinds of write:
  - `setObjectOnFire` sets `isCombusting = true` and `hasCombusted = true`;
  - `putOutFire` sets `isCombusting = false` and the temperature to the combustion point − 10. It is called when liquid water is among the object's contents or its container's contents;
  - at burn-out (`combustionTicks == 0`) the code sets `isCombusting = false`, creates `new Ash` in the container and calls `obj.delete(expelContents = true)`.

  `hasCombusted` is only ever assigned `true`.
- **Experiments [RUN]:**

| Experiment | Result |
|---|---|
| Chair lit, then `pour metal pot into chair` | `isCombusting` true→false, `hasCombusted` stays true, ticks 99→98, still false 3 ticks later |
| Chair lit, then `pour metal pot into kitchen` (floor) | the same: extinguished |
| Relight after extinguishing | `isCombusting` true again, `hasCombusted` true, ticks continue to decrease (97) |
| Painting lit, then `move painting to metal pot` | extinguished; `hasCombusted` true |
| Chair left to burn out | deleted at tick 100; one `ash` object appears; `hasCombusted` monotone and `combustionTicks` non-increasing throughout |

- **Coverage findings:**
  - `hasCombusted` is monotone: the source and the experiments agree.
  - `isCombusting` is **restorable**: a counterexample to any claim that it is irreversible.
  - `present` is lost only at burn-out. The deleted object's uuid never returns (O2), but ash is a different object.
  - **Erratum:** docs/23 §6.3 said "the chair is not movable". That is false. The chair has `propMoveable.isMovable = true`, and pouring water into it works. Corrected in docs/23.
- **Assurance:** "`hasCombusted` never reverts" is source-relative assurance (no formal proof; Scala semantics, the JVM and reflection limits are assumed, as in ADR-0004 C2).
- **Proof gaps and residual uncertainty:**
  - O8 (structural) still covers `Chair` only. For the painting, the definition-B claim rests on O2 to O7.
  - A burn case can be irreversible under C5 **only** if every weighted changed property is `hasCombusted` or `combustionTicks`. For example, a case declaring only `hasCombusted` would qualify, but declaring that after seeing these results would be retrospective (ADR-0005 R3).

### 4.2 C-MIX-SALT

- **Precondition test [RUN].** Task 6-1 variation 8 contains a second sodium chloride (`universe/workshop/sodium chloride`). After mixing in the kitchen, that salt remains. The checker returns `precondition_not_met`, so the case cannot be admitted (h4-mix-salt-two-salts). In the single-salt world the checker returns `precondition_met`, and no sodium chloride is left anywhere.
- **Production pathways [SRC] (4G O8, re-checked):** `SodiumChloride` is constructed only during world/task construction. No runtime chemistry produces it (the 4G report is unchanged).
- **Coverage:** the water consumed by mixing is **not** covered. Its uuid is lost (identity loss), and new water is obtainable from the sink (structural replacement). So no mix case that weights water can be irreversible.
- **Residual uncertainty:**
  - the checker quantifies over the observed tree (H4);
  - only 1 of the probed world variations violates the precondition, so world-specific checking is essential, not optional.

### 4.3 C-EAT: identity, regrowth, completeness

- **Removal [SRC]:**
  - `ActionEat` detaches the food (`removeAndResetContainer()`). It does not delete it: no `(deleted)` suffix, terminals not disconnected, contents stay inside the detached object.
  - O2 shows a detached object is never re-attached or ticked.
  - So **the eaten uuid never returns (identity)**. This is identity loss and is never admissible alone (ADR-0004 C3); `C-EAT/identity` is reported `identity_loss_only`.
- **Regrowth [SRC]:**
  - fruit classes (Apple, Banana, … , ten audited) are constructed at runtime only in `PlantReproduction.createFruit`;
  - `createFruit` is called from a flower's tick (`Plant.scala`) or from a debug `def main` that the simulator never invokes;
  - flowers are created only by `PlantLifeStage.tick` of a live plant;
  - new plants arise only via `createFruit`/`createSeed`, and `createSeed` is called only at task construction.
- **New narrower claim:** `C-EAT/structural-plantless`.

  > "If the eaten object is an audited fruit class, no other object of that class exists, and no plant, flower, pollen or seed exists anywhere in the tree, then no object of that class ever exists again."

  O1 to O8 are all discharged (`verified_source_relative`):
  - O8 is the plant closure above;
  - O6: in the 1-1 kitchen, after eating the banana the precondition is met and no banana exists for 100 ticks;
  - O7: a bounded search of 25 paths finds no banana, and the checker rejects the 4-1 world (apple tree present).

  **It is not registered with `sw-admission-2`** (ADR-0005 R6).
- **Why the 4G structural claim stays rejected:** its checker ignored flowers, pollen and seeds and was not class-conditional (H7).
- **Residual uncertainty:**
  - plant-likeness is detected by object name and lifeform type, not by class;
  - fruit names map to classes by default display name;
  - completeness of the tree is assumed (H4);
  - the claim is class-level, so "a banana" is a structural notion. It says nothing about other edible objects;
  - a world with a single seed defeats it.

## 5. Declaration reliability (Part 3)

**What exists:**
- 12 blinded packets (`docs/preregistration/packets/P01…P12`). Each contains only the task text, prior actions, the target, the named objects and the S0 room scene. The packets contain no declarations, case ids or outcomes (checked with grep, and by a unit test on a synthetic packet).
- A deterministic protocol for a future human annotator (`PHASE4H_ANNOTATOR_PROTOCOL.md`).
- A rule-based generator `sw-declaration-rubric-1`, frozen with the cases.

**What does not exist:** any human second declaration. **No inter-annotator agreement, no human validation and no annotator is reported or implied.**

### 5.1 Automated consistency (M1 vs rubric, on S0 (uuid, field) pairs)

| Case | Jaccard all | Jaccard weighted | Weight-flag agreement | Disagreement |
|---|---|---|---|---|
| open-fridge | 0.40 | 0.50 | 1.00 | rubric adds wood cup temperature and juice stateOfMatter; omits cup location (A1, A4, A6) |
| move-cup | 0.50 | 1.00 | 1.00 | M1 records temperature at w0; the rubric does not (A6) |
| cup-water-to-freezer | 0.75 | 0.75 | 1.00 | rubric adds the cup's own temperature (A1) |
| burn-painting, burn-chair | 1.00 | 0.67 | 0.67 | `present`: M1 w0, rubric w1 (A2) |
| the other 7 | 1.00 | 1.00 | 1.00 | none |

Exact agreement on 8 of 12. The M1 declarations and the rubric were written by the same team, so this measures consistency of one team's practice with its own written rule. It does not measure independent agreement.

### 5.2 Sensitivity of the admission outcome to property choice [RUN]

Each case was rerun with the rubric's properties and M1's declared paths, so only property choice varies.

- **11 of 12 outcomes unchanged.**
- **h4-cup-water-to-freezer changed:**
  - under M1 it is unresolved: partial at 0.01 °C (cup moved back; water temperature residual) but none at 0.1 °C, so `temperature_sensitive`;
  - under the rubric it is **eligible partially reversible**, because it also declares the cup's own temperature.
  - So a defensible extra property turned an excluded case into an eligible one.
- The burn cases' `present` disagreement (A2) did **not** change the outcome, because `present` never changed within the observation window.

### 5.3 Ambiguous property choices and proposed fixed rubric

A1 to A6 are listed in the protocol. Proposed resolutions for `sw-declaration-rubric-2` [DEC, proposal only]:
- **A1:** declare the temperature of every object in or directly on a thermal device, at w1.
- **A2:** combustion `present` at w0. It is a time-dependent consequence, not the designed effect.
- **A3:** declare both the container's `contents` (w0) and each substance's `present` (w1).
- **A4:** do not declare unmoved contents.
- **A5:** declare both terminals.
- **A6:** record (w0) every container whose contents change.

Adopting these requires a new pre-registration round and must not be applied to the 4H cases retroactively.

## 6. Independent replication (Part 5) [RUN]

Commands: `phase4h_run.py replica`, then `audit`, then `compare`. Results are in `results/phase4h/comparison.json`.

**Two fresh processes.**
- Each of the 5 eligible cases was collected again in a separate Python process with a new JVM.
- **5 of 5 replicated** on every compared item:
  - the S0 raw fingerprint;
  - the target status, ticks and no-op flag;
  - every attempt's path, verification, execution, and per-tolerance level and concepts;
  - the certificate checks;
  - the outcome, reasons and witness;
  - the stochastic-exposure signals.
- There were no disagreements and no stochastic differences.
- The 7 unresolved cases were not replicated, because they are excluded either way.

**Temperature sensitivity.** All 5 eligible cases have the same interpretation at 0.01 °C and at 0.1 °C. The admission rule requires this, and the replica reproduces it. The temperature-unstable case (freezer, M1) is excluded, not replicated.

**Measurement effects (Phase 4F query-order audit, `measurement_audit.json`).**
- For each eligible case, the full action sequence (base, history, target, witness path) was replayed in fresh processes under these conditions:
  - no queries (the baseline);
  - observing after every step (B);
  - enumerating valid actions after every step (C);
  - observe-then-enumerate (D1);
  - enumerate-then-observe (D2).
- **All 5 cases: transitions identical at every step under every condition, valid-action lists identical, 0 steps with a state difference.**

**What this does and does not show.**
- The two processes run the same deterministic simulator with the same seed and the same query protocol. Agreement shows process-level reproducibility, not methodological independence.
- The query-order audit is the evidence that these particular results do not depend on our queries. It covers only these 5 action sequences, and only these query types.
- A different search (other expanded samples) was not tried. So the *absence* of a better witness for the partial cases is not replicated in any meaningful sense; it is search-relative by construction (§7).

## 7. Candidate three-class mapping (Part 6) [DEC]

The mapping is frozen in ADR-0005 R4. In summary:

| Admission outcome | Candidate class | Requirement |
|---|---|---|
| `eligible_reversible`, replicated | **reversible** | verified restoration witness (exact canonical, stable at 0.01 and 0.1 °C), replicated in two fresh processes |
| `eligible_partially_reversible`, replicated | **partially reversible** | positive meaningful witness plus a declared residual, replicated |
| `eligible_irreversible`, replicated | **irreversible** | an admissible certificate covering every weighted changed property, replicated; never a failed search |
| any `unresolved_*`, non-replicating, quarantined | **outside the three classes** | not exported |

**Partial is horizon- and search-relative, not absolute.** A partial witness proves that the declared residual was *not* restored *by that path*. It does not prove that no other path restores the residual. The class therefore means "partially restorable within the declared search (registry plus declared paths plus a 20-path single-step expanded search, immediate start, no waiting), and residual not shown restorable". For the burn cases, the residual `hasCombusted` is protected by C-BURN, so for them the residual is also certificate-backed. They are the only partial cases where the residual is known to be permanent (source-relative).

**Candidate classes from Phase 4H** (not gold labels; nothing exported):
- reversible: open-fridge, move-cup, connect-battery-wire;
- partially reversible: burn-painting, burn-chair;
- irreversible: none.

## 8. Feasibility of scaling (Part 7)

- **Yield per class:**

  | Phase | Cases | Reversible | Partial | Irreversible |
  |---|---|---|---|---|
  | 4G | 15 | 2 | 3 | 0 |
  | 4H | 12 | 3 | 2 | 0 |
  | **Pooled** | **27** | **5 (19%)** | **5 (19%)** | **0** |

  Over half of all cases are unresolved. Expected yield for irreversible is 0 under the current rule. Under the plantless what-if it rises to about one case per plantless world with a fruit, so all such cases would come from one consumption template.
- **Diversity:**
  - reversible covers containers, movement and electrical;
  - partial covers matter in or under devices and combustion;
  - liquid transfer, chemistry, consumption and navigation produced no eligible case.
- **Navigation is a search-scope failure, not irreversibility.** For teleport, the inverse `teleport to kitchen` was never proposed: the registry has no teleport rule and the expanded search samples actions on the target's objects. Its declaration was frozen and is not revised.
- **Minimal pairs:**
  - feasible for reversible versus partial (e.g. device-on versus device-off contrasts in 4F/4G);
  - for irreversible, the only candidate contrast is plantless versus plant world (eat banana versus eat apple). That pair differs in world, task and fruit, so it is not a minimal pair. A same-world pair (e.g. with versus without a seed) would need a world edit, which is outside the pinned-simulator protocol.
- **Runtime cost:** 18 to 42 s per case for main evidence on this machine, about 2× that with the rubric rerun, plus a replication run and a measurement audit per eligible case. A 1,000-candidate ScienceWorld pool would take roughly 25 to 40 CPU-hours before replication, so runtime is feasible.
- **Certificate coverage:**
  - C-BURN covers `hasCombusted`;
  - C-MIX-SALT covers salt presence in single-salt worlds only;
  - `C-EAT/structural-plantless` (unregistered) covers class-level fruit presence;
  - no certificate covers liquids, temperature, mixtures or connections.
- **Selection bias:** every eligible irreversible candidate would be selected by certificate availability, i.e. by what the source makes provable. Irreversible examples would then concentrate on a few verbs, and a probe could learn "eat in a world without plants" rather than irreversibility.
- **Template risk:** high. One or two templates (consumption, possibly combustion with `hasCombusted`-only declarations) would supply the whole irreversible class.

**Honest alternative [DEC, adopted for OQ-46 in ADR-0005 R9]:**
1. Use ScienceWorld for **reversible versus partially reversible** examples, plus a clearly flagged, *world-conditional irreversible slice* only if ADR-0005's R6 path is taken.
2. Take irreversible examples, and the three-class balance, primarily from the sandbox, where irreversibility is defined by construction.
3. Report ScienceWorld results as two-class (or three-class with the irreversible slice reported separately, with its template concentration disclosed).
4. Never up-sample or re-declare ScienceWorld cases to reach balance.

## 9. Tests and remaining risks

- **Tests:**
  - `tests/test_scienceworld_phase4h.py` (no Java) covers: the manifest matching the current records; edit and removal detection; the rationale requirement; packet blinding and determinism; per-verb rubric rules; agreement metrics; the plantless checker; reattachment and plant-closure audits on synthetic Scala trees, including counterexamples.
  - Gate (2026-10-31): `pytest -q` 587 passed, 37 skipped (no Java); real ScienceWorld integration `-m scienceworld` 37 passed, including the new Phase 4H tests and the static source audits; `ruff check .` and `ruff format --check src tests scripts` clean.
- **Risks:**
  1. Declarations are not human-validated.
  2. "Partial" is search-relative (H2).
  3. Certificates are source-relative, not formal.
  4. Tree completeness is assumed (H4).
  5. The counterfactual measurement asymmetry (H1).
  6. Irreversibility rests on certificate availability, a selection bias.
  7. All 12 cases come from 4 worlds, so between-world generalisation is unmeasured.
