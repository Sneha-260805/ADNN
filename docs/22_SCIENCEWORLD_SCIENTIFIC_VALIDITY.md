# 22: ScienceWorld scientific validity and targeted contrasts (Phase 4F)

**Status:** Provisional evidence and methodology only. **No gold labels were issued. No pair below is a gold reversibility minimal pair.**

**Unchanged:** ScienceWorld pin e8216d6, the sandbox, the 210-example pilot, the dataset API and prompt builder 1.0.0.

**Decisions:** recorded as research-team decisions in ADR-0003. There is no claim of professor approval.

**Evidence tags:** [SRC] pinned source, [RUN] measured here, [ARG] argument, [HYP] hypothesis.

| Section | Module | Script | Output (git-ignored) |
|---|---|---|---|
| §2 query order | `adnn.scienceworld.query_audit` | `scripts/scienceworld/query_order_audit.py` | `results/scienceworld_query_audit/` |
| §3–4 contrasts | `adnn.scienceworld.contrasts` | `scripts/scienceworld/contrast_pilot.py` | `data/scienceworld_provisional/contrasts-v0/` |
| §5 expanded search | `adnn.scienceworld.expanded_search` | `scripts/scienceworld/expanded_search.py` | `results/scienceworld_expanded_search/` |
| §6 certificates | `adnn.scienceworld.certificates` | (unit tests and a scratch probe) | n/a |
| §7 decisions | `docs/decisions/0003-scienceworld-operational-definitions.md` | n/a | n/a |

## 1. Summary

1. **The simulator is not measurement-independent [RUN].**
   - Valid-action enumeration consumes the global random generator and changes later bee transitions.
   - Look, inventory and object-tree queries had no measured effect.
   - In two deterministic scenarios, no query condition changed any transition.
2. **Targeted contrasts yield candidates.**
   - 16 specifications produced 15 structural candidates.
   - 10 of these are restoration-contrast candidates under at least one declared method.
   - 8 of the 10 are stable across 0.01 °C and 0.1 °C.
   - The Phase 4E sampler found 0 pairs that differed in evidence status.
3. **Expanding the restoration search matters [RUN].** An object-local 1-step search found exact restoration paths for a case where the hand-written registry had proposed none (electrical `connect`).
4. **Certificates have per-state precondition checkers.**
   - These are C-MIX-SALT, C-BURN and C-EAT.
   - On the real simulator, C-BURN's precondition was met for three lighter ignitions, and C-EAT's for eating an apple.
   - They remain manual audits, not proofs.
5. **ScienceWorld is not ready for gold-label generation** (§8).

### 1.1 Explicit scientific limitations

- **Enumeration changes bee movement.** Valid-action enumeration changes bee movement (§2). The query protocol makes measurement consistent, not neutral.
- **Contrasts are not single-variable.** Each pair also carries entailed and incidental differences (§3.3).
- **Not gold minimal pairs.** The 10 restoration-contrast candidates are **not** gold minimal pairs. They differ in restricted-search evidence, not in labels (§4).
- **The restricted registry missed paths.** Expanded search recovered restoration paths that the restricted inverse registry missed (electrical `connect`, §5). Registry-based "no candidate" statuses therefore understate restorability.
- **Failed search proves nothing.** A failed search, restricted or expanded, never proves irreversibility (RD-04).
- **Certificates are preliminary.** All three source certificates (C-MIX-SALT, C-BURN, C-EAT) are preliminary manual audits. They are not formal proofs and not gold labels (§6).
- **No validated temperature tolerance.** No primary temperature tolerance has been experimentally validated. Results are reported at 0, 0.01 and 0.1 °C, and temperature-sensitive cases are excluded (ADR-0003 D4, OQ-42).
- **No gold labels.** No ScienceWorld gold labels have been issued.

## 2. Query-order and RNG audit (Step 2)

### 2.1 Source facts [SRC]

- **The generator is global.** It is the global `scala.util.Random`, reseeded with the variation index at load (`PythonInterface.scala:110,114`; `EnvironmentMaker.scala:23`).
- **Referent disambiguation can draw from it.** `InputParser.chooseUniqueReferents` falls back to `Random.nextInt` after 10 failed deterministic attempts (`input/InputParser.scala:612-644`).
- **Enumeration reaches that fallback.**
  - Valid-action enumeration (`AgentInterface.scala:213-280`) builds referents over all universe objects, so it reaches the fallback.
  - `getObjectTree` is `universe.toJSON()` and does no referent work.
- **Two runtime processes draw randomness during play:**
  - bees: `Bee.scala:174-190` draws `nextInt(2)` for every bee on every tick, even in a closed hive;
  - plant genetics: `Chromosomes.scala:201,268`.

### 2.2 Design

- **Scenarios.** Four fixed (task, variation, action sequence) scenarios, listed in the results table.
- **Conditions.** A condition is a bundle of queries issued before every step:

  | Condition | Queries before every step |
  |---|---|
  | A | none |
  | B | look, inventory, object tree |
  | C | valid actions and templates |
  | D1 | B then C |
  | D2 | C then B (the reverse order) |

- **Probes.** To observe step k without adding queries to condition A, every probe:
  1. reloads the task;
  2. runs k steps under the condition;
  3. captures the state once, identically in every condition.
- **Runs.** Every condition was run 2× in fresh JVMs and 1× in a shared JVM, and compared with A (fresh, repeat 0) at every k:
  - canonical state;
  - object tree;
  - look and inventory text;
  - valid actions;
  - step statuses and observations;
  - bee container paths.

### 2.3 Results [RUN]

Each scenario had 14 comparisons against the baseline.

| Scenario | Steps | Comparisons with a differing state | First differing k | Valid actions differ | Step observations differ |
|---|---|---|---|---|---|
| kitchen-deterministic (1-1) | 7 | 0 | none | 0 | 0 |
| workshop-deterministic (3-1) | 6 | 0 | none | 0 | 0 |
| greenhouse-bees (5-1) | 6 | **9**: C, D1, D2 × 3 runs | 3 (first tick after `open bee hive`) | 9 | 0 |
| greenhouse-ambiguous-soil-bees (5-1) | 8 | **9**: C, D1, D2 × 3 runs | 6 (after `open bee hive`) | 9 | 0 |

- **Bee scenario.** With enumeration, different bees leave the hive on each tick: bees 2, 3 and 4 differ at k=3, and bee 4 at k=5. By k=6 all bees are out, and the states agree again. This explains the Phase 4E null result, which probed only after 8 ticks.
- **Ambiguous-referent scenario.** At k=5 (after `pour flower pot 2 into flower pot 1`), the valid-action *text* already differs under enumeration, but the canonical state is identical. This is the OQ-38 effect: text depends on earlier queries, and state does not.
- **B never differed.** Look, inventory and object-tree queries (condition B) never changed anything.
- **Reproducibility.** Every repeat was identical to its counterpart: fresh vs fresh, and fresh vs shared. The effect is deterministic, given the query schedule.
- **Step observations never differed.** The observation text does not mention bees, so observation-only logging would hide the effect.

### 2.4 Interpretation and protocol

- **Measurement dependence is real.** Valid-action enumeration is not passive.
  - When an RNG consumer (bees) is active, it changes transitions.
  - In ambiguous-referent states, it changes action text.
  - We do **not** claim measurement independence.
- **The deterministic null is not a no-draw result.** The deterministic scenarios showed no effect, but that does not show enumeration draws nothing there. It shows only that no observable process consumed the draws.
- **Protocol (ADR-0003 D8).** We keep the fixed schedule used since Phase 4E:
  1. load;
  2. recipe actions with no queries;
  3. `capture_state`;
  4. `valid_action_templates`.
- **What the protocol does and does not do.** It makes measurement consistent, not neutral. Branches of different lengths still issue different numbers of enumeration calls.
- **Stochastic cases are therefore excluded (ADR-0003 D7.2), not corrected for.**
  - Closed-hive states are kept: the hive was closed in the kitchen and workshop scenarios, and those were query-independent.
- **Limitations.**
  - Only four scenarios were audited.
  - D1 and D2 were each compared with A, not directly with each other, though their changed-object sets were identical.
  - Plant reproduction was not exercised.

## 3. Targeted contrast generators (Step 3)

### 3.1 Specification

`contrast_specs()` defines 16 deterministic specifications, all bee-free:

- **Source state ×5.** Sink off vs on, then `move X to sink`. X is a metal pot, ceramic cup or tin cup (kitchen), or flower pot 1 or the jug (greenhouse).
- **Device state ×3.** Stove off vs on, then `move X to stove`.
- **Object location ×5.** X on the table vs on the stove, then `activate stove`; X on the table vs in the sink, then `activate sink`; greenhouse flower pot 1 carried vs in the sink, then `activate sink`.
- **Container fill ×3.** Metal pot empty vs filled with sink water, both on the table. Targets: `move metal pot to stove` (stove on), `pick up metal pot`, `pour metal pot into ceramic cup`.

Every specification has:
- shared prefix actions;
- two variants, the shorter padded with `look at agent` so ticks match;
- one target string used verbatim in both states;
- a declared intended difference, as (object, field) pairs.

Both variants are built with the Phase 4E verified sampler (`explicit_example(..., allow_idle=True)`). The target must be:
- a valid, unambiguous template;
- accepted by the simulator;
- replay-verified.

Evidence is then collected for each variant with the Phase 4E restricted restoration diagnostic.

### 3.2 Recorded per pair

For every pair, the following is recorded:
- the intended difference found;
- **uncontrolled differences**: every other discrete change between the two S0 states, plus one-sided objects, temperature changes and tick equality;
- action consequences in each state: the effect, created and deleted objects, and the evidence status.

Parts of an intended created object, such as its electrical terminals, are listed separately.

### 3.3 Uncontrolled differences (honest reading)

Some uncontrolled differences are causally entailed by the intended one, but are still listed as uncontrolled:

- **Source pairs.** An active sink fills itself with water in one tick, so S0 also differs by a new `water` in the sink.
- **Device pairs.** An active stove has a different `curSetTemp`.
- **Location pairs.** The moved object's `path` and its terminals' paths differ.

There are also sub-0.01 °C temperature differences:
- maximum 0.0096 °C, in the fill pairs;
- 0.0035 °C in the kitchen source pairs.

None of the pairs is a single-field contrast. A reviewer should read these lists as part of each pair's definition.

## 4. Stronger minimal-pair criteria and yield (Step 4)

- **Structural candidate.** All of the following hold:
  - byte-identical target;
  - valid and accepted, with an observed effect, in both states;
  - same referent uuids;
  - the intended difference is present;
  - ticks are matched;
  - both variants are replay-verified;
  - no stochastic exposure: no `bee N` outside a closed container;
  - not a bee scenario.
- **Restoration-contrast candidate.** A structural candidate whose best counterfactual match differs between the two states under a declared method:

  | Method | Counts as a match |
  |---|---|
  | `exact` | exact |
  | `tol_0.01C` | exact or within 0.01 °C |
  | `tol_0.1C` | exact, within 0.01 °C or within 0.1 °C |

  Missing evidence is never counted as a difference.
- **Gold status.** Every pair carries `gold_status = not_a_gold_minimal_pair` (ADR-0003 D5).

### 4.1 Yield [RUN]

Results come from 16 specifications and 32 records. Validation: records OK, pairs OK.

| Kind | Specs | Structural | Restoration-contrast | Rejected |
|---|---|---|---|---|
| source_state | 5 | 5 | 5 | 0 |
| device_state | 3 | 3 | 3 | 0 |
| object_location | 5 | 5 | 2 | 0 |
| container_fill | 3 | 2 | 0 | 1 |
| **Total** | **16** | **15** | **10** | **1** |

- **Restoration contrasts by method:**
  - exact: 2 (`location-stove-*`: on the table, `deactivate stove` restores exactly; on the stove, the object is heated);
  - 0.01 °C: 8;
  - 0.1 °C: 10.
- **Stability (ADR-0003 D4).** 8 pairs differ under both tolerances. The 2 greenhouse source pairs differ only at 0.1 °C: their sink-off variant matches only within 0.1 °C. They are temperature-sensitive.
- **Typical restoration-contrast pattern.**
  - In the "off" state, the registry inverse restores within tolerance.
  - In the "on" state, the moved container has been filled with water or heated, and no tried path restores it.
  - This is a difference in restricted-search evidence, **not** a difference in reversibility (RD-04).
- **Structural-only pairs.**
  - `location-sink-*` ×3: activating the sink creates new water in both states, so both variants mismatch.
  - `fill-metal_pot-move-stove`: both variants mismatch.
  - `fill-metal_pot-pick-pot`: both variants match within 0.01 °C.
- **Rejected (1).** `fill-metal_pot-pour-cup`: pouring an empty pot has no observed effect (reason `effect_in_both`). Its no-effect record is kept in `no_effect_records.jsonl`.
- **First run.** Every pair failed `no_stochastic_exposure` because the check matched the name "bee hive". The check now matches only `bee <n>`, and this is covered by a unit test.
- **Reproducibility.** Two independent runs produced identical content checksums for all 32 records.
- **Cost.** About 23.5 s per contrast (375 s in total).

## 5. Restoration-search sensitivity (Step 5)

### 5.1 Method

`expanded_search(recipe, target)` works as follows:

1. **Rebuild and step.** It rebuilds S0 and steps the target. Every rebuild is raw-fingerprint-checked against S0 and S1.
2. **Build the pool.** The pool contains every agent-valid, unambiguous, non-helper, non-door single action whose objects intersect:
   - the target's objects;
   - their containers before and after the target;
   - objects the target created.
3. **Select candidates.** The registry's original single-step inverses are always included. The rest is filled by a seeded, verb-stratified round-robin, up to 40 candidates.
4. **Compare.** Each candidate is compared with the time-matched counterfactual at the three thresholds. Counterfactuals are cached per tick count.
5. **Branching.** The full 1-step branching factor (all valid actions) is counted, not executed.

**Version 1 used uniform sampling, which missed the original inverse.** For `close freezer`, uniform sampling of 40 of 185 candidates was dominated by `connect X to freezer`. It missed `open freezer` and reported no match for the exact control. A search that can lose the original inverse does not measure sensitivity to expansion, so version 2 always includes the registry inverses. Version 1 results are kept for the record (`results/scienceworld_expanded_search-v1-uniform/`).

**Subsample.** One Phase 4E record per evidence category was used, with no bee targets.

### 5.2 Results [RUN] (version 2)

| Case (4E status) | Valid actions | Agent-allowed | Object-local | Tried | Accepted | Registry inverse result | Expanded result |
|---|---|---|---|---|---|---|---|
| eat apple (no candidate) | 2610 | 2177 | 147 | 40 | 33 | n/a | none |
| pour counter into kitchen (no candidate) | 2734 | 2291 | 266 | 40 | 35 | n/a | none |
| **connect cathode in buzzer to battery cathode (no candidate)** | 1197 | 1033 | 21 | 21 (all) | 21 | n/a | **exact ×5** |
| pour switch into hallway (no candidate) | 1445 | 1268 | 177 | 40 | 40 | n/a | none |
| activate sink, kitchen (mismatch) | 2497 | 2074 | 364 | 40 | 17 | none | none |
| activate sink, greenhouse (mismatch) | 1158 | 926 | 373 | 40 | 24 | none | none |
| pick up glass jar (within 0.1 °C) | 2572 | 2140 | 315 | 40 | 34 | within 0.1 °C | within 0.1 °C ×2 |
| close freezer (exact control) | 2452 | 2030 | 185 | 40 | 30 | exact | exact (`open freezer`) |

- **The connect case gained restoration paths.** The search found five exact paths:
  - `disconnect battery`;
  - `disconnect buzzer`;
  - `move battery to table`;
  - `move buzzer to workshop`;
  - `pour battery into table`.

  The registry has no rule for `connect`, so the 4E status "no candidate path found" reflected only the registry's coverage. That moving a component restores the connection matches the observation; the mechanism (moving resets connections) is [HYP] and has not been source-audited.
- **Other cases.** No other former failure gained a path within the 1-step object-local scope. Specific gaps:
  - `pour switch into hallway` plausibly needs two steps: go to the hallway, then move the switch back [HYP].
  - `activate sink` creates new water objects, which under identity comparison (ADR-0003 D3) no path can remove-and-restore.
- **Refused or invalid candidates.** 0–23 per case were accepted by the valid-action list but refused or invalid in the simulator (valid-list over-generation, Phase 4E).
- **Search cost.**
  - 0.7–2.3 s per candidate; 20–97 s per case.
  - Estimated full 1-step search over all agent-allowed actions: 600–4700 s per case.
  - Estimated 2-step object-local search: 365 s to about 175,000 s (about 49 h) per case.
  - Exhaustive or multi-step search is infeasible at dataset scale without much stronger pruning.
- **Coverage limits.**
  - Object-local scope only: actions on unrelated objects and the agent's own location are excluded unless they touch related objects.
  - A single step only.
  - 40 of up to 373 object-local candidates were tried.
  - Teleport is excluded unless it touches related objects.
  - **A failed expanded search is still restricted, and is not evidence of irreversibility (RD-04).**

## 6. Source-backed invariant evidence (Step 6)

`adnn.scienceworld.certificates` records, for each certificate:
- the audited source lines;
- the searches performed;
- the audited action files (all 16 files in `actions/`, plus processes run by `EnvObject.tick`);
- the restoration definitions it holds and does not hold under;
- what it establishes and does not establish;
- remaining counterexamples.

Each also has a per-state checker returning `precondition_met`, `precondition_not_met` or `not_applicable`. No checker returns a label (`is_label: false`, `is_formal_proof: false`).

### 6.1 Mixing: C-MIX-SALT

**Re-verified [SRC].**
- `new SodiumChloride()` appears 4 times, all at construction: `BuildingMaker.scala:197`, `TaskChemistryMix.scala:36`, `TaskElectricalConductivity.scala:66`, `TaskUseInstrumentThermometer.scala:53`.
- `SodiumChlorideProp` is attached only by the `SodiumChloride` class (`Substance.scala:134`).
- `SaltWaterProp.nameInStateOfMatter` contains only salt-water names (`MaterialProperties.scala:986-988`).
- The only non-default `substanceName` write is at construction (`UnknownSubstance.scala:71`).
- Every `propMaterial = Some(...)` is inside an object constructor.
- No process consumes `SaltWater`.

**What it establishes.** Under the audited text, mixing that consumes the *last* sodium chloride in the tree cannot be undone under the literal or counterfactual definitions, or under a structural definition that keeps substance identity.

**Counterexamples.**
- Any other sodium-chloride object, anywhere in the tree.
- Structural definitions without substance identity.
- Object-tree incompleteness, which is assumed away.

**Not run.** There was no empirical mixing probe: no pilot world was set up with the salt rule.

### 6.2 Combustion: C-BURN

**I1 [SRC].** `hasCombusted` is assigned only `= true` (`Combustion.scala:19`); `putOutFire` leaves it unchanged (`:33-38`).

**I2 [SRC].** `combustionTicks` is only decremented (`-= 1`, `:56`). Its defaults are 100 (`MaterialProperties.scala:17`) and 0 for ash (`:901`).

**What it establishes.** For the same uuid, an ignition caused by the target cannot be undone. This matters only when the counterfactual does not also ignite the object; the checker compares with the counterfactual.

**[RUN] probe.** This is a scratch probe, not a repository script.
- In 1-1, `use lighter on chair`, `use lighter on cupboard` and `use lighter on drawer in counter` each ignited one object, and C-BURN returned `precondition_met` with the counterfactual supplied.
- `use lighter on cup containing nothing in table` heated the glass cup without igniting it, and C-BURN returned `not_applicable`.

**Not tested.** Persistence of `hasCombusted` after extinguishing has not been tested empirically.

**Counterexamples.**
- Structural look-alikes (`Chopping` creates `Wood`).
- Fully burned objects are deleted, so the argument reduces to identity.

### 6.3 Consumption: C-EAT

**[SRC]** `ActionEat` detaches the object (`removeAndResetContainer`), and detached objects can never be referenced again.

**What it establishes.**
- **Identity part:** the eaten uuid never returns. This holds equally for any deletion, so on its own it does not separate eating from emptying a cup (ADR-0003 D3, D5).
- **Structural part:** this is a hypothesis. Only `PlantReproduction` creates new food at runtime. The checker requires no living plant in the tree.

**[RUN]** In 1-1, `eat apple` met both parts: the uuid left the tree, and there was no living plant.

**Checker limitation.** Seeds that could be planted later are not detected. The structural part therefore remains a hypothesis.

### 6.4 What remains unresolved

- None of the three is a formal proof. All hold only for e8216d6.
- C-MIX-SALT and the persistence of C-BURN lack end-to-end empirical confirmation (OQ-43).
- No irreversible claim is made in this phase.

## 7. Recommended operational label definitions

Full text is in ADR-0003.

| Proposed label | Required evidence |
|---|---|
| Reversible (under the declared definition) | An executed path with an exact or approximate outcome, stable across 0.01 °C and 0.1 °C |
| Irreversible | A source-backed certificate whose checker returns `precondition_met` for the specific (S0, T, S1, counterfactual), and whose holds-under list contains the declared definition. **Never** a failed search |
| Unknown / excluded | Everything else, including:<br>• partial outcomes (not yet computed);<br>• temperature-sensitive cases;<br>• hidden door states;<br>• stochastic exposure;<br>• plant reproduction;<br>• ambiguous referents. |

Identity-based comparison is primary. Structural matching is exploratory only.

## 8. Readiness for gold-label generation

**Not ready.** Blocking items:

1. **"Partial" is not computed** (ADR-0003 D1, OQ-41).
2. **The irreversible route is thin.**
   - Only three certificate candidates exist.
   - Two lack end-to-end confirmation (OQ-43).
   - Most targets have no applicable certificate, so they would be unknown.
3. **Restoration contrasts are search-evidence contrasts, not label contrasts.**
   - The 8 stable candidates differ in what a restricted search found.
   - Mapping them to labels needs (1) and (2), plus a reversible witness in one state.
   - It also needs a certificate, or an accepted *unknown*, in the other.
4. **Coverage.** The contrast set is small (16 specifications, 3 task worlds). Yield at dataset scale is unmeasured.
5. **The threshold is unsettled.** ADR-0003 D4 excludes temperature-sensitive cases; a primary threshold is still open (OQ-42).

## 9. Tests and how to run

**Unit tests.** `tests/test_scienceworld_phase4f.py` (19 tests, no Java, MiniKitchen fake) covers:
- query-audit independence;
- detection of an enumeration-consuming fake;
- contrast specifications;
- contrast building and classification;
- rejection rules;
- tamper detection;
- expanded search, selection and branching;
- certificate checkers;
- the not-a-proof and not-a-label flags.

**Integration tests.** `tests/test_scienceworld_phase4f_integration.py` (4 tests, marker `scienceworld`) covers:
- kitchen query independence;
- the bee enumeration effect;
- one real contrast;
- a small expanded search.

**Runtime.** The scripts need the isolated runtime variables (`docs/21` §9).
