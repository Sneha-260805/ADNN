# 19 — ScienceWorld Restoration Diagnostics (Phase 4D)

Owner: **Sneha (M1)**. Code: `src/adnn/scienceworld/restoration_diagnostics.py`, `structural.py`. Status: **implemented and run against the pinned simulator (`e8216d6`); diagnostics only, no labels.** Predecessors: `16`–`18`. Decisions requested from the professor: `20_PROFESSOR_DECISION_MEMO.md`.

> **Scope guardrail.** Phase 4D investigates *whether* agent-accessible actions can restore earlier ScienceWorld states, and *how we could tell*. It does **not**:
> - assign `reversible`, `partially_reversible` or `irreversible` (not even provisionally);
> - run exhaustive search;
> - treat a failed restricted search as evidence of irreversibility;
> - treat equality of the captured (observed) state as equality of the complete simulator state.

Evidence tags used below:

- **[SRC]** read in the pinned source (`src.zip`, SHA-256 `d2c1dc1e…bfae6` = the pin);
- **[RUN]** measured on the pinned build in this phase;
- **[ARG]** argument from a manual source audit (not machine-checked);
- **[HYP]** hypothesis.

## 1. Guardrails, as implemented

| Guardrail | Mechanism |
|---|---|
| No labels | Results use only the neutral outcomes in §2.4. No result field is called `label`, `labels_by_horizon` or `restore_depth`. Unit tests walk every serialised report and fail on any label word or key |
| Restricted, never exhaustive | Candidates come from a hand-written registry (§3) and explicitly listed paths. Every report records `scope = restricted_registry`, `exhaustive = false` and `failed_search_meaning` ("…NOT evidence that the action cannot be undone…") |
| Agent-accessible restoration only | Every candidate action must be in the simulator's valid-action list *at the moment it is taken*; otherwise it is `unavailable` and is never sent. Helper and idle commands (`reset task`, `focus on`, `task`, `inventory`, `look around`, `look at`, `look in`, `read`, `wait*`) are `excluded`. `load`, `reset` and recipe replay rebuild states for the researcher and are never counted as restoration actions |
| Inverses are hypotheses | Each rule only *proposes* an action, selected by **simulator uuid** from `get_valid_action_object_combinations_with_templates()`, not by name. The candidate is then executed and the result compared |
| Observed state only | Every canonical state is incomplete (doors outside the current room, agent internals). `observed_fields_match` never sets `supports_exact_equality_claim` |
| Verified starting states | S0 is rebuilt from a `ReplayRecipe` and must equal an independent `replay()` of the same recipe (raw fingerprint). S1 is rebuilt for every further candidate and must be identical. Any mismatch raises `ReplayDivergenceError` |

## 2. Method

### 2.1 Procedure (`run_inverse_experiment`)

1. Rebuild **S0** from the recipe in a session (researcher operation), verified against an independent replay.
2. Look up the target in S0's valid actions with uuids (if absent: `target_action_not_executed`). Execute it to get **S1**, and record its discrete effect (`DISCRETE_EXPLORATION` diff S0→S1).
3. Ask every matching registry rule for candidate paths in S1, then append the experiment's explicit paths. At most `max_paths = 4` are attempted; the number proposed is recorded.
4. For each path: rebuild S1 (verified identical), execute the path step by step (availability checked before every step, and stop at the first refusal), then capture **S2**.
5. Compare:
   - **literal**: S2 vs S0, raw (count) and canonical diffs plus each projection;
   - **counterfactual**: S2 vs **C**, where C = S0 rebuilt, plus the same number of ticks of an idle action (`look at agent`, one tick each, no discrete effect). If idle ticks cannot be matched, the counterfactual is reported as unavailable;
   - **structural**: S0 vs S2, location-sensitive and location-insensitive (§5).

The session machinery is reused, not duplicated:

- `replay.run_recipe` was extracted from `replay()` unchanged in behaviour;
- `ScienceWorldSession.valid_action_templates()` is a new free call;
- all diffs are the Phase 4C functions.

### 2.2 Time accounting (from source, confirmed by runs)

`get_num_moves()` returns `AgentInterface.curIter`, which is incremented **once per universe tick** in `AgentInterface.step` [SRC `runtime/AgentInterface.scala:504-580`]. So **ticks elapsed = Δmoves exactly**:

| Action class | Ticks | Reason [SRC] |
|---|---|---|
| unparsable input, ambiguous input | 0 | `step` returns before the tick loop |
| `look around`, `inventory`, `task` | 0 | `ActionHandler.doesActionTakeTime` returns false only for these three |
| any other parsed action, **including one the simulator refuses** (e.g. "The glass jar can't be poured out, because it's not open.") | 1 | the queued action "takes time" whatever `runAction` returns [RUN: moves 4→5] |
| `wait1` / `wait` | 2 / 11 | `setWait(1)`/`setWait(10)`, then the loop ticks once more per remaining wait |

This resolves the "inferred" `wait1` accounting left open in `17` §4.3 and `18` §10. It also refines OQ-35: in ScienceWorld, *parsed-but-refused* actions **do** consume time; only unparsable input does not.

### 2.3 What every report contains

Per experiment:

- task, variation, recipe;
- target action, its status and uuids;
- the target's discrete effect;
- every rule considered (applicable or not, and why);
- the paths proposed and attempted;
- the unobservable state list;
- outcomes;
- pinned provenance.

Per path:

- each action with its status (`accepted` / `invalid` / `ambiguous` / `unavailable` / `excluded`) and whether it was executed;
- the number of actions used;
- ticks (target, path, total);
- raw change count;
- for each comparison mode: the outcome, field changes, created and deleted objects (uuid, name), ignored patterns with the count of ignored differences, tolerances with the count within tolerance, incompleteness reasons, the number of temperature changes and the maximum |ΔT|;
- structural reports;
- observability issues.

### 2.4 Neutral outcome vocabulary

| Outcome | Meaning |
|---|---|
| `candidate_path_executed` | Every action of the path was available and accepted |
| `candidate_path_not_executed` | A path action was unavailable, excluded, invalid or ambiguous (execution stopped there) |
| `no_candidate_path_found` | No rule proposed a path and no explicit path was given |
| `target_action_not_executed` | The target was not in the valid list, or was rejected as invalid/ambiguous |
| `observed_fields_match` | In at least one comparison mode, no difference among the compared observed fields |
| `observed_fields_differ` | In at least one comparison mode, some difference |
| `insufficient_observability` | The relevant property is a door state, or the target refers to uuids absent from the tree, or the target had no observed discrete effect, or the agent's room differs |

A path can carry both `observed_fields_match` and `observed_fields_differ`: different comparison modes disagree, and that disagreement is the point of OQ-30. **None of these is a label**, and no mapping to labels is implemented.

## 3. Inverse-action registry (`REGISTRY`)

All candidates are selected by **uuid**: the inverse action's `obj_ids` must equal the target object's uuid (and, for returns, the original container's uuid).

| Rule | Target | Proposed inverse (by uuid) | Precondition checked | Observability | Source [SRC] |
|---|---|---|---|---|---|
| `container-open-then-close` | `open X` (not a door) | `close X` | `propContainer.isOpen` False→True | tree | `ActionOpenCloseDoor.scala` case 2 |
| `container-close-then-open` | `close X` | `open X` | True→False | tree | same |
| `door-open-then-close` | `open door to R` | `close door to R`, same portal uuid | door R closed→open in `look()` | **current-room text** | case 1, `propPortal.isOpen`; portals not in the tree |
| `door-close-then-open` | `close door to R` | `open door to R` | open→closed | **current-room text** | same |
| `device-activate-then-deactivate` | `activate X` | `deactivate X` | `propDevice.isActivated` False→True | tree | `ActionActivate.scala` |
| `device-deactivate-then-activate` | `deactivate X` | `activate X` | True→False | tree | same |
| `return-to-original-container` | `move O to Y`, `pick up O`, `put down O`, `pour O into Y` (O not a container) | `move O to <original parent>` (and `put down O` if the original parent is the agent's room) | O's parent changed | tree | `ActionMoveObject.scala` (`addObject`) |
| `pour-contents-back` | `pour A into B` (A a container) | `pour B into A` | B held **no** movable objects in S0 (otherwise pouring back would move them too) | tree | `ActionPourObject` moves all movable contents |

Deliberately **not** in the registry: `mix`, `eat`, `use lighter on`, `connect`/`disconnect`, `dunk`, `flush`, `teleport`. These have no hypothesised inverse, or need a separate study. Their absence produces `no_candidate_path_found`, which means *undetermined*, not *irreversible*.

## 4. Experiments and results

**Setup.** Task `1-1` (boil), variation 0, simplification `teleportAction`. Every recipe starts with `FIRST_TICK_PREPARATION = ("wait1",)` and `teleport to kitchen`. Target and paths run in the kitchen (351 objects). Runs on 2026-10-31: Windows 11, Temurin 21.0.13, JAR `e77b0fee…`.

### 4.1 Summary

| ID | Target | Candidate path (source) | Executed | Ticks (S0→S2) | Literal canonical | Literal discrete projection | Literal ±2 °C projection | Counterfactual canonical | Notes |
|---|---|---|---|---|---|---|---|---|---|
| E01 | `open cupboard` | `close cupboard` (rule) | yes | 2 | differ: 81 temps + moves | **match** | **match** (81 within tol.) | **match (0 diffs)** | |
| E02 | `close cupboard` | `open cupboard` (rule) | yes | 2 | differ | **match** | **match** | **match** | |
| E03 | `activate stove` | `deactivate stove` (rule) | yes | 2 | differ | **match** | **match** | **match** | `curSetTemp` reset too |
| E04 | `activate sink` | `deactivate sink` (rule) | yes | 2 | differ | **differ**: water + 2 terminals created | differ | differ: same objects + 20 temps (≤0.0016 °C) | while on, the sink drained a new water object into `universe/sewer`; deactivation does not remove it |
| E05 | `open door to hallway` | `close door to hallway` (rule, same portal uuid) | yes | 2 | differ | match (`door:hallway` closed again) | match | match | **`insufficient_observability`**: portal uuid `17562` absent from the tree; door visible only in `look()`; other rooms' doors unknown |
| E06 | `move apple to table` | `move apple to bowl` (rule; uuids [apple, bowl]) | yes | 2 | differ | **match** | **match** | **match** | |
| E07 | `pick up apple` | `move apple to bowl` (rule) | yes | 2 | differ | **match** | **match** | **match** | inverse found by uuid although the text differs from the target |
| E08 | `pour glass jar into ceramic cup` | `pour ceramic cup into glass jar` (rule) | yes | 2 | differ | **match** (same sodium-chloride uuid returns) | **match** | **differ: 19 temps, max 0.0015 °C** | the trip changed heat exchange; **residual thermal trace** |
| E09 | `pour metal pot into sink` (pot holds water) | `pour-contents-back` rejected (sink held the pot); explicit `activate sink`, `deactivate sink` | yes | 3 | differ | **differ**: original water now in `universe/sewer`; two new waters created | differ | differ | "refill" makes a *new* water in the pot; the old one persists in the sewer |
| E10 | `mix metal pot` (water + sodium chloride) | no rule; explicit `activate sink`, `deactivate sink` | yes | 3 | differ | **differ**: sodium chloride + water deleted; salt water + 2 waters created | differ | differ | compensating only (§5.3) |
| E11 | `eat banana` | — | — | — | — | — | — | — | `no_candidate_path_found`; banana (+2 terminals) leave the tree |

Wall time per experiment: 5.0–9.9 s (79.5 s total), including the verification replay, one attempt and its counterfactual.

**Reproducibility [RUN].** The full set was run twice. The summaries (all outcomes, diffs and structural results; wall times excluded) were **identical**. Every S0/S1 reconstruction matched its reference fingerprint.

### 4.2 What was restored, what remained different

- **Restored on every observed discrete field, with time drift as the only difference** (E01, E02, E03, E06, E07):
  - under the literal comparison, the only differences are ≈81 temperatures and `moves`;
  - under the **time-matched counterfactual** there are **zero differences in 6,400+ canonical fields**.
  
  So for these actions the autonomous dynamics are exactly separable from the action's effect: the action plus its inverse left no trace in the captured state.
- **Restored on discrete fields, with a residual thermal trace** (E08): the counterfactual shows 19 temperature differences, max 0.0015 °C, because moving the substance altered heat exchange. Under an *exact* counterfactual rule (OQ-30 B) this would **not** count as exact restoration. Under a tolerance rule (C) it would.
- **Toggle restored, side effects not** (E04): "activate ↔ deactivate" sounds inverse, but the sink created objects while on. The registry proposed the path, the experiment refuted it as a full restoration, and that is the intended behaviour.
- **Door** (E05): the door is closed again *as seen from the kitchen*. Whether anything else changed in rooms we cannot see is unknown. Reported as `insufficient_observability`.
- **Replacement, not restoration** (E09, E10): refilling produces new objects with new uuids, and the originals are either elsewhere (the sewer) or deleted (mixing).

### 4.3 Temperature and time effects [RUN]

- Every timed action ticks the world. In the kitchen, 81–84 temperatures change over two or three ticks (max |ΔT| 0.68–0.90 °C). A literal canonical comparison **always** differs after any timed path.
- The ±2 °C projection (`TEMPERATURE_TOLERANCE_EXPLORATION`, exploratory) absorbed all drift in these short paths. 2 °C is a placeholder, not an approved value.
- The counterfactual removed drift **exactly** for actions that do not move matter between thermal neighbours. Residues appeared when matter moved or was created (E04: 0.0016 °C, E08: 0.0015 °C, E09: 0.0039 °C, E10: 0.0031 °C).
- **Time alone can delete objects [SRC].** Living things consume water: `objWater.get.delete()` appears in every `processes/lifestage/*LifeStage.scala`. **Time alone can create objects [SRC]**: sinks, fountains and self-watering flower pots add `new Water()` on ticks; `PlantReproduction` creates fruit. A literal comparison therefore conflates action effects with autonomous creation and deletion.
- `wait` is **one action but 11 ticks**. A horizon of 3 actions can therefore span up to 33 ticks: enough for autonomous processes (growth, reproduction, burning) to act. This bears on OQ-30 and OQ-31.

### 4.4 Unobservable or unknown state (reported in every experiment)

- `portals_absent_from_object_tree`: door actions carry portal uuids that never occur in the tree [RUN: E05 uuid `17562`];
- `doors_outside_current_room_not_observable`;
- `agent_internal_state_not_exposed(wait_counter, focus_monitor, goal_progress)`;
- the door states of every room except the agent's current one.

## 5. Structural object-matching prototype (`structural.py`, exploratory)

### 5.1 Why

`UniqueIdentifier.getNextID()` is a global creation counter. `count` only increases, and `reset()` is called only at load/reset [SRC `util/UniqueIdentifier.scala`]. A re-created substance therefore always has a **new** uuid. The canonical contract (`18` rule R1: identity = uuid) correctly reports it as deleted + created. The prototype asks a different question, *"is there an indistinguishable replacement?"*, **without changing R1** (a regression test asserts `canonical_diff` still reports deleted + created).

### 5.2 Rules

- **S1 uuid first.** Objects present in both states are the same object. Relocations are reported and never re-matched.
- **S2 signature.** All canonical fields except `parent`, `path` and `propMaterial.temperatureC` (caller-configurable). `propElectricalConnection.connectedTo` (a uuid list) enters only as its length.
- **S3 location.** A deleted object may match a created one only in the same container: the same uuid, or the structural counterpart of a matched parent. Processing is top-down, so hidden terminals follow their substance. A location-insensitive variant exists for diagnosis.
- **S4 uniqueness.** A match is made only for a 1:1 (signature, location) group. Otherwise an `AmbiguousGroup` lists every candidate and **nothing is forced**. Indistinguishable groups (same signature and container, size > 1) are listed per state.

Raw states and simulator uuids are never modified (tested). A match reads "replaced by an indistinguishable object", never "the original returned".

### 5.3 Results

| Case | Result |
|---|---|
| Move and return (E06, E07; unit test) | Every object matched by uuid; no structural matching needed; `all_objects_accounted = true` |
| Empty and refill (E09) | The original water is **relocated** (pot → sewer, same uuid); the new pot water is `unmatched_after`. Under S1 a still-existing original is never "replaced" by a look-alike, so this is **not** reported as restoration. Whether a structural definition *should* accept it is a modelling question (memo Q3) |
| Mixing + refill (E10) | Location-sensitive: deleted pot water `17604` ↔ new pot water `17613` (and both terminals) matched, with only the temperature differing (reported). **`sodium chloride` (`17292`) unmatched; `salt water` and the sewer's new water unmatched.** Location-insensitive: water 1 → {`17613`, `17616`} and terminals 2 → 3 are **ambiguous**, so nothing is matched |
| Indistinguishable objects (unit tests) | Two identical tin cups: the inverse is chosen by uuid (`move tin cup 17 to table`), never the twin. One deleted water vs two new waters in the same container → `AmbiguousGroup`, no match |

### 5.4 Limitations

- The signature is a choice. Ignoring temperature makes a hot replacement match a cold original (the difference is reported). Including it would make replacements almost never match.
- S1 means a relocated original plus a look-alike in its old place counts as *relocated + extra*, never as *restored*.
- Fields that the tree does not expose (portals, agent internals) cannot enter any signature.
- It is exploratory (`sw-structural-0-exploratory`) and is not used by any comparison outcome.

## 6. Source-backed irreversibility investigation

**General facts [SRC]:**

- `EnvObject.delete()` removes the object from its container, disconnects terminals, appends " (deleted)" to its name and sets `deleted = true`. `deleted` is never set back to false (`struct/EnvObject.scala:24, 397-411`).
- Agent actions can only refer to objects reachable from containers and portals: `InputParser.collectAccessibleObjects` (`input/InputParser.scala:151-152, 742-768`).
- The only world reset is the researcher's `load`/`reset`. The agent action `reset task` resets goal progress and focus only (`ActionFocus.scala: ActionResetTask`).

**Consequence [ARG].** A deleted or detached object can never be referenced by an agent action again, so its uuid can never re-appear in the tree. Under any definition that requires the *same uuid* (identity-based literal restoration), every deletion is permanent. That would make refilling a cup of water "irreversible", which is plainly over-strict. **Object deletion therefore proves irreversibility only under identity-based definitions.** Under structural definitions, one must also show that no structurally equivalent object can be (re-)created.

### 6.1 Mixing

| Item | Finding |
|---|---|
| Code | `actions/ActionMix.scala` (`ActionMix.runAction`, `isValidAction`: container holds ≥ 2 objects) → `processes/Chemistry.scala: mixContainer` (lines 63-440) |
| Transitions | For a fixed recipe table keyed on the number of non-hidden contents (2/3/4) and substance names, e.g. water + sodium chloride: `water.delete(); sodiumChloride.delete(); container.addObject(new SaltWater())` (lines 134-142). Other rules: soapy water, sugar water, dough, s'mores, rust, sodium acetate, sandwiches, coloured paper, paints (with an any-N-paints → brown catch-all). If no rule applies, `mix` is still **accepted** and returns "does not appear to produce anything new" without changing state |
| Inputs | **Deleted**, not transformed; a new output object with a new uuid is **created** [RUN E10] |
| Reconstruction by agent actions | (a) The original uuids: impossible [ARG, above]. (b) A structurally equivalent **water**: possible (sink/fountain create `new Water()`) [RUN E10]. (c) Structurally equivalent **sodium chloride**: no runtime path found. `new SodiumChloride()` occurs only in world construction (`environments/BuildingMaker.scala`, three task set-ups). The name/substance "sodium chloride" occurs only in `SodiumChloride`/`SodiumChlorideProp`. `StateOfMatter.ChangeOfState` renames an object only through *its own* `nameInStateOfMatter` map. `substanceName` is never reassigned at runtime (only in an `UnknownSubstance` factory at construction). No process takes `SaltWater` as an input |
| Proposed invariant (certificate candidate C-MIX-SALT) | If `mix C` applies the salt-water rule, and S1 contains **no other object with `substanceName = "sodium chloride"` anywhere in the universe tree**, then no sequence of agent actions reaches a state containing such an object |
| Restoration definitions under which it would hold | Any definition requiring sodium chloride to exist: literal (A), counterfactual (B; the counterfactual world still has it), and task-relevant structural (C) if substance identity is among the selected properties |
| Counterexamples / caveats | Another sodium-chloride object elsewhere (other jar, other room, inventory) breaks the premise, so the checker must scan the whole tree, not just the room. Definition C *without* substance identity (e.g. "the pot contains two substances") would not be blocked. The argument covers commit `e8216d6` only |
| Status | **Source-backed certificate candidate (manual audit, not a formal or machine-checked proof).** Adoption needs professor approval of the certificate policy (OQ-31), a per-state precondition checker and a unit test. Other mixing rules need their own audits (e.g. water inputs are always replaceable) |

### 6.2 Combustion

| Item | Finding |
|---|---|
| Code | `processes/Combustion.scala`: `setObjectOnFire` (12-24), `putOutFire` (33-38), `combustionTick` (41-110); called from `objects/devices/Lighter.scala:29` (`use lighter on X`) and from `EnvObject.tick` (517) every tick |
| Transitions | Ignition (lighter, or `temperatureC ≥ combustionPoint`): `isCombusting = true`, **`hasCombusted = true`**. Each tick on fire: **`combustionTicks -= 1`** and the temperature is raised to at least the burning temperature. Liquid water in the same container puts the fire out (`isCombusting = false`, temperature set 10 °C below the combustion point; the water is heated). At `combustionTicks == 0`: `new Ash()` is added to the container and the object is `delete(expelContents = true)`. Descriptions show "burned X" for extinguished objects (`EnvObject.scala:381`) |
| Deleted / transformed / replaced | Partly burned: **transformed** (flags/counter changed, same uuid). Fully burned: **deleted and replaced** by ash |
| Reconstruction | **I1:** `hasCombusted` is only ever assigned `true` (`Combustion.scala:19`; Ash defaults) [SRC, exhaustive grep of writes]. **I2:** `combustionTicks` is only ever decremented at runtime (`-= 1`, line 56) [SRC]. So once an object ignites, no action can restore *that object's* `hasCombusted`/`combustionTicks` |
| Proposed invariant (C-BURN) | For an object O with `hasCombusted = false` in S0: if the target ignites O (directly, or by heating it past its combustion point) **and the counterfactual would not have ignited O**, then O's `hasCombusted` is true in every reachable state |
| Holds under | A and B for O's own fields; C if `hasCombusted` (and/or `combustionTicks`) is a selected property. Caution: the existing exploratory `DISCRETE_EXPLORATION` **ignores `combustionTicks`**, so an approved projection must not |
| Counterexamples | (1) O would have ignited anyway (e.g. already on an active stove), which the counterfactual exposes. (2) Under structural definitions an unburned look-alike could replace O (`Chopping` creates `new Wood()`; `PlantReproduction` creates fruit). (3) The burned object is deleted, so for fully burned objects the argument reduces to §6 general facts |
| Status | **I1/I2: source-backed invariants (exhaustive search for writes in the pinned source; a proof relative to that source text, assuming no mutation outside Scala code).** C-BURN as a certificate: **candidate**, not run empirically (no combustion experiment in 4D) |

### 6.3 Eating / consumption

| Item | Finding |
|---|---|
| Code | `actions/ActionEat.scala: runAction` (lines 16-36); valid only if `propEdibility.isEdible` |
| Transitions | `food.removeAndResetContainer()` in both the poisonous and edible cases: the object is **detached** (no container) but **not** `delete()`d. `isDeleted` stays false; it simply leaves the tree [RUN E11: banana + 2 terminals absent] |
| Reconstruction | The same uuid: impossible (unreachable; [ARG]). A structurally equivalent food: **possible in some worlds**, because `PlantReproduction` creates `new Apple()`, `new Banana()`, `new Orange()`, … from pollinated fruiting plants over many ticks. Ordinary actions create no food. The agent's starting orange is created at construction |
| Proposed invariant | Identity-based: the eaten uuid never returns (holds under A, B). Structural: holds only if no fruit-producing plant of the same kind can produce a fruit within the horizon, which is a per-world, time-dependent condition (and `wait` = 11 ticks) |
| Status | Identity part: **strong source argument [ARG]**. Structural part: **hypothesis**; no general certificate proposed |

## 7. Findings that change open questions

| Finding | Affects |
|---|---|
| Time-matched counterfactual removes drift exactly for toggles and moves; small thermal residues remain after matter moves (≤ 0.004 °C) | OQ-30 (B needs a tolerance or is strict) |
| Parsed-but-refused actions consume a tick; only unparsable input is free | OQ-35 |
| `wait` = 11 ticks in one action; autonomous creation/deletion of objects | OQ-30, OQ-31 (horizon unit), OQ-33 |
| Door actions refer to portal uuids absent from the tree; restoration verifiable only from the current room | OQ-36 |
| Deletion is permanent by uuid, but water (and fruit) can be structurally replaced; sodium chloride cannot (C-MIX-SALT) | OQ-31 (certificates), OQ-03 |
| "Activate/deactivate" restores the toggle but not created objects (sink → sewer water) | OQ-03 (compensating vs restoring) |

## 8. Tests and how to run

```bash
# unit tests (no Java)
.venv/Scripts/python.exe -m pytest -q tests/test_scienceworld_restoration.py

# optional integration tests on the pinned runtime
SW="$LOCALAPPDATA/adnn-sw"
ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
  .venv/Scripts/python.exe -m pytest -q -m scienceworld tests/test_scienceworld_restoration_integration.py

# the experiment set (writes results/scienceworld_restoration/*.json, git-ignored)
ADNN_SW_JAVA_HOME=… ADNN_SW_SITE_PACKAGES=… .venv/Scripts/python.exe scripts/scienceworld/restoration_check.py
```

**Unit tests** (`tests/scienceworld_restoration_fake.py`, a state-driven fake kitchen with uuid-resolved valid actions) cover:

- uuid-based candidate selection among indistinguishable objects;
- unavailable, invalid and excluded candidates;
- restricted-search reporting;
- the pour-back precondition;
- refused targets;
- temperature drift and tolerances;
- door observability;
- an unavailable counterfactual;
- structural matching (re-created objects, ambiguity, location sensitivity, mixing);
- R1 regression;
- divergence when rebuilding S0 and S1;
- session cleanup after errors;
- absence of any label word or key.

Two deliberate mutations (forcing ambiguous matches; selecting the return move without the destination uuid) each made the relevant tests fail.

**Integration tests (7)** pin the §4 findings on the real simulator (E01, E04, E05, E08, E10, E11, plus reproducibility and no leaked JVM).

**Measured on 2026-10-31:**

| Run | Result |
|---|---|
| `test_scienceworld_restoration.py` (no runtime) | 35 passed (0.5 s) |
| Full suite without runtime | 492 passed, 20 skipped (all 20 are the runtime-only integration tests) |
| All integration tests with runtime (`-m scienceworld`) | 20 passed (13 from Phase 4C + 7 new), ≈2 min; `java.exe` left: 0 |
| `ruff check .`, `ruff format --check src tests scripts` | clean |
| `restoration_check.py`, run twice | 11 experiments each; identical summaries |

## 9. Limitations

- One task (`1-1`), one variation, one room, eleven targets, at most one attempt each. These are illustrations, not coverage.
- The registry is tiny by design. Absent rules (connect/disconnect, dunk, flush, teleport) are unexplored.
- The counterfactual idle action (`look at agent`) is assumed to have no effect beyond a tick. This is supported by the exact matches in E01–E07, not proven from source for every object.
- Source arguments are manual audits of one commit. Reflection, py4j server calls and code outside `simulator/src/main/scala` were not audited.
- Combustion was analysed from source only. No experiment ignited anything.
- The structural matcher's signature and location rules are choices (§5.4).

## 10. What blocks labels

See `20_PROFESSOR_DECISION_MEMO.md`. In short:

- **OQ-30**: the restoration target;
- **OQ-31**: which evidence may establish `irreversible`;
- **OQ-03**: the operational meaning of "partially reversible";
- **OQ-36**: door handling.

The memo also flags interactions with OQ-29 and OQ-35. Until these are decided, Phase 4E may build infrastructure but must not emit gold labels.
