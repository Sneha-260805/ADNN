# 21 — ScienceWorld Provisional Evidence Dataset (Phase 4E)

Owner: **Sneha (M1)**.

- **Code:**
  - `src/adnn/scienceworld/provisional.py`: schema, record builder, candidate pairs, validator; no Java.
  - `src/adnn/scienceworld/provisional_sampling.py`: sampler, evidence collection, pilot pipeline.
  - `scripts/scienceworld/provisional_pilot.py`.
- **Methodology:** `docs/decisions/0002-scienceworld-provisional-methodology.md`. Decisions RD-01 to RD-11 are research-team decisions and are **not professor-approved**.
- **Status:** implemented. A pilot was run on the pinned simulator (`e8216d6`), with provisional evidence only.

> **Scope guardrail.** Phase 4E stores restoration evidence for sampled ScienceWorld state-action pairs. It does **not**:
> - assign gold labels, provisional labels or any of the words reversible / partially reversible / irreversible / undetermined as a verdict;
> - write anything into the gold dataset (contract C1) or the 210-example pilot;
> - generate the final 2,000 examples;
> - treat a failed restricted search as irreversibility (RD-04);
> - sample door actions (RD-05).

Evidence tags: **[SRC]** pinned source; **[RUN]** measured in this phase; **[ARG]** argument; **[HYP]** hypothesis.

## 1. Why a separate evidence schema

The gold schema (`docs/05`, `adnn.dataset.schema`) requires a `label` and validates against exactly three classes. ScienceWorld evidence is not yet a label:
- the restoration concepts are separate (RD-03);
- the candidate search is restricted (RD-04);
- the observed state is incomplete (RD-05, OQ-36).

Forcing records into the gold schema would therefore require inventing labels. Instead, records use their own versioned schema (`sw-evidence-0.1`). The validator *rejects*:
- any gold-schema field;
- any label-like key (`label`, `labels_by_horizon`, `restore_depth`, `pair_id`, …);
- any label word as a value;
- any evaluation signal (`score`, `reward`, `done`, gold actions).

Turning evidence into gold examples later is a separate, explicit step (§8).

## 2. Evidence record schema (`sw-evidence-0.1`)

Each record is one JSON object, one per line in `records.jsonl`. It has exactly these top-level fields (`RECORD_FIELDS`):

| Field | Content |
|---|---|
| `schema_version` | `sw-evidence-0.1` |
| `example_id` | `swp-` + first 16 hex characters of SHA-256(recipe JSON ∥ target text). Deterministic and unique per (history, action) |
| `family_id` | Scenario family (`boil-kitchen`, `power-workshop`, `grow-greenhouse`). This is the grouping unit for pairs and future splits |
| `task` | `{task_id, variation}`: explicit ids, never a random-variation API |
| `simplifications` | Normalised simplification string (`teleportAction`; RD-11) |
| `replay_recipe` | Full `sw-replay-1` recipe, including the simulator pin. It rebuilds S0 exactly |
| `action_history` | Every agent action from the start: `{action, phase, status, ticks, counts_as_agent_action: true}`. The phases are `preparation` (first tick), `base` (teleport), `prefix` (sampled walk) and `contrast` (sibling) |
| `researcher_operations` | `load_and_reset` with its arguments, `counts_as_agent_action: false` |
| `first_tick_handling` | `wait1` preparation, and why it is needed (first-tick object creation) |
| `target` | Action text, verb class, rule coverage, `template_id`, simulator `obj_ids` with names, `obj_ids_in_object_tree`, `n_templates_with_text` (= 1), `valid_in_state`, status, ticks, observation (truncated), and the observed discrete effect |
| `pre_action_state` | Agent location, moves, `look` and `inventory` text, object and valid-action counts, visible doors, full canonical records of the target objects, plus raw, canonical and discrete fingerprints |
| `state_provenance` | Path and SHA-256 of the state file (`states/<raw fp>.json`, full raw and canonical S0), capture method and canonical version |
| `elapsed_ticks` | History ticks (= S0 moves) and target ticks |
| `restoration_evidence` | See §2.1 |
| `observation_completeness` | `complete: false`, the base incompleteness reasons, unobservable items and canonicalisation notes |
| `replay_verification` | Sampler S0 fingerprint vs diagnostic S0 fingerprints; `verified` |
| `sampling` | Seed, sample index, role (`base` / `sibling` / `explicit`), `sibling_of`, `contrast_action`, prefix length, door actions excluded from the target pool |
| `provenance` | Simulator pin, runtime provenance (Java, package, JAR hash), evidence schema, diagnostics and canonical versions |
| `scientific_status` | `{status: provisional_evidence_only, gold_labels_issued: false, professor_approved: false, methodology_owner, decision_log}` |
| `content_sha256` | SHA-256 of the canonical JSON of all other fields |

### 2.1 `restoration_evidence`

- `primary_method = time_matched_counterfactual` (RD-01).
- `temperature_comparisons = [exact, within_0.01C, within_0.1C]` (RD-02).
- `candidate_set`:
  - `scope = restricted_registry`, `restricted = true`, `exhaustive = false`;
  - the rules considered, with their proposals and reasons;
  - paths proposed, attempted and executed, and `max_paths = 4`;
  - `failed_search_meaning` (RD-04).
- `attempts[]`, one per candidate path:
  - source, actions, per-step status and ticks;
  - `counterfactual {available, idle_action, note}`;
  - `comparisons` by mode:
    - `literal_canonical`;
    - `literal_projection:*`;
    - `counterfactual_canonical`, which is the **exact** comparison;
    - `counterfactual_projection:temperature-tolerance-0.01C-v1`;
    - `counterfactual_projection:temperature-tolerance-0.1C-v1`;
    - `counterfactual_projection:discrete-exploration-v1`, exploratory only, never used for a match level.
  - Each comparison carries:
    - the changes, listing at most 25;
    - created and deleted objects;
    - ignored patterns, tolerances and `n_within_tolerance`;
    - unfiltered temperature statistics;
    - `unknown_fields`, i.e. the incompleteness reasons.
  - `match_level`: `exact` / `within_0.01C` / `within_0.1C` / `none` / `not_compared`.
  - Also: a structural summary (exploratory), observability issues and the Phase 4D neutral outcomes.
- `best_counterfactual_match_level` and `evidence_status`. The status is one of:
  - `target_not_executed`;
  - `no_candidate_path_found`;
  - `no_candidate_path_executed`;
  - `counterfactual_unavailable`;
  - `counterfactual_match_exact`;
  - `counterfactual_match_within_0.01C`;
  - `counterfactual_match_within_0.1C`;
  - `counterfactual_mismatch_at_all_tolerances`.

  These are neutral evidence descriptions, not the four RD-03 concepts. For example, `counterfactual_match_exact` is *necessary* for exact restoration, but it is not sufficient while observation is incomplete. `counterfactual_mismatch_at_all_tolerances` is *not* irreversibility.
- `interpretation_constraints`: the RD-03, RD-04, RD-09 and observed-fields-only statements, repeated in every record.

### 2.2 Candidate pair schema (`sw-candidate-pair-0.1`)

Each line of `candidate_pairs.jsonl` contains:
- `candidate_pair_id` (`swpair-` + hash of the sorted record ids);
- `family_id`, `action_text` and `record_ids`;
- `relation` (`sibling` / `independent`);
- `state_difference`: the discrete changes between the two S0s (at most 25 listed), created and deleted objects, the exact change count and the temperature change count;
- `consequence_difference`: only the signature keys that differ, each with both values;
- `reference_check` and `reproducibility`;
- `status = candidate_unvalidated`, `validated = false`;
- `scientific_status` and `content_sha256`.

### 2.3 Python API

```python
from adnn.scienceworld.provisional import (
    PILOT_FAMILIES, FamilySpec, build_record, discover_candidate_pairs,
    validate_dataset, load_state_file, read_jsonl, leakage_problems,
)
from adnn.scienceworld.provisional_sampling import (
    SamplerConfig, sample_examples, collect_evidence, explicit_example, run_pilot,
)

res = run_pilot(Path("data/scienceworld_provisional/pilot-v0"), SamplerConfig())
report = validate_dataset(read_jsonl(root / "records.jsonl"),
                          read_jsonl(root / "candidate_pairs.jsonl"), root=root)
```

`explicit_example(family, prefix, target)` builds a hand-specified example under the same validity rules (role `explicit`). The tests use it for known pairs.

## 3. Sampling

### 3.1 Procedure (`sample_examples`, deterministic)

For each family, and for each `sample_index` until 8 base samples are accepted or 30 attempts are used:

1. **RNG.** `random.Random(int(SHA-256("seed:family_id:index")[:8]))`. This never depends on `PYTHONHASHSEED`. All candidate lists are sorted before drawing.
2. **Exploration walk.**
   - Load and reset (a researcher operation), run the base recipe (`wait1` for the first tick, then `teleport to <room>`), then 0–3 history actions.
   - Each history action is drawn from valid actions that:
     - have exactly one template (unambiguous);
     - are in a rule-covered class (open/close, activate/deactivate, move, pick up, pour);
     - are not door or portal actions.
   - Each history action must be accepted and must change at least one discrete observed field. Otherwise the sample is rejected (`prefix_no_observed_discrete_effect`, …).
3. **Clean rebuild (query protocol, §3.2).** S0 and its valid-action templates are taken from a fresh rebuild of the recipe, never from the exploration session.
4. **Target.**
   - Choose a verb class: rule-covered classes have weight 2; eat, mix and connect have weight 1 (RD-11).
   - Then choose an action uniformly within the class from the clean S0 templates (unambiguous, no doors).
   - Reject duplicates: the same canonical fingerprint with the same action, or the same *discrete* fingerprint (temperatures and time removed) with the same action.
   - Execute the target. It must be accepted and have an observed discrete effect. Otherwise the sampler rebuilds S0, verifies the fingerprint and tries another target, up to 3 times.
5. **Sibling** (probability 0.75). Rebuild S0 and draw one contrast action under the same history rules. Actions touching the target's objects or their containers are preferred.
   - Rebuild S0 + contrast cleanly.
   - Require:
     - the *byte-identical* target text is still valid and unambiguous;
     - it refers to the same uuids;
     - the pair is not a duplicate;
     - the target is still effective.
   - Up to 3 contrasts are tried.

A **researcher reset is never an agent action**. It appears only in `researcher_operations`. The validator checks that `action_history` equals the recipe's actions exactly.

### 3.2 Query protocol (new finding, OQ-38)

**[RUN]** In the greenhouse, the same recipe produces a *different valid-action list* depending on whether `capture_state` or `valid_action_templates` was called between steps:
- 260 entries differed;
- for example, `connect agent to soil in flower pot 1 containing soil` vs `… soil in flower pot containing soil`;
- the canonical object state was identical.

The first pilot attempt stopped on exactly this, with a sampler-rebuild `ReplayDivergenceError`.

**[SRC]** `InputParser.chooseUniqueReferents` (`input/InputParser.scala:644`) tries 10 deterministic disambiguations, and then draws referent indices from the **global** `scala.util.Random`. That generator is seeded once per environment (`environments/EnvironmentMaker.scala:23`). Every valid-action query therefore advances it.

**[RUN]** The same generator drives stochastic dynamics (`objects/livingthing/animals/Bee.scala`). We tested whether queries perturb dynamics:
- greenhouse, bee hive open, 8 idle ticks, 0 / 1 / 3 valid-action queries per tick;
- once in the initial state and once in the ambiguous-soil state.

The canonical states were identical in all cases. The hazard is real in the source, but was not observed.

**Protocol (implemented).** A state's valid-action list and action texts are defined by: fresh load → recipe actions with no interleaved queries → `capture_state` → `valid_action_templates`.
- The sampler takes S0 only from this protocol.
- `replay()` already follows it.
- The Phase 4D runner now issues the same queries in the same order on every rebuild. This is a one-line, behaviour-preserving change (`restoration_diagnostics.py`, rebuild and S1 check).

Exploration may still query freely, because only the clean rebuild is recorded.

**Remaining limitation.** The counterfactual branch and the path branch issue different query sequences between ticks. In a world where the fallback fires and a stochastic process is active, the two branches could diverge for reasons unrelated to the action. This was not observed in the probes. It is listed in §7.6.

### 3.3 Families

The three families were chosen from a probe of six candidates:

| Family | Task | Room | Valid actions after teleport | Rule-covered toggles available |
|---|---|---|---|---|
| `boil-kitchen` | 1-1 (boil), var 0 | kitchen | 2,734 | cupboard, drawers, fridge, freezer, oven, glass jar; sink, stove, oven, stopwatch |
| `power-workshop` | 3-1 (power component), var 0 | workshop | 1,609 | freezer; switch, gas generator |
| `grow-greenhouse` | 5-1 (grow plant), var 0 | greenhouse | 1,083 | bee hive; sink |

1-2 and 2-1 start in the same kitchen layout as 1-1, and 6-1 differs only slightly, so they add little diversity at pilot scale.

## 4. Evidence collection (`collect_evidence`)

For each sampled example, collection reuses the Phase 4D runner (`run_inverse_experiment`) with:
- all registry rules;
- `idle_action = "look at agent"`;
- `max_paths = 4`;
- `verify_reconstruction = True`;
- projections: 0.01 °C, 0.1 °C and discrete (exploratory).

S0 is reconstructed three times independently:
1. the sampler's clean rebuild;
2. the diagnostic's verification replay in a fresh JVM;
3. the diagnostic session.

The record is kept only if all three raw fingerprints agree.

The rest of the collection:
- Rule paths are proposed by simulator uuid, and are executed only while each action is valid.
- S1 is rebuilt and verified before every path.
- Each executed path is compared with a counterfactual of S0 plus the same number of 1-tick idle actions.
- Differences, unknown fields and tick counts are stored per comparison mode.

The candidate set is always marked restricted. When no path exists or none matches, the record keeps the neutral status; it is never turned into a verdict.

## 5. Candidate minimal pairs

A candidate pair is two records that meet all of the following:
- **Same family**, which is the scenario grouping.
- **Byte-identical target text.**
- **Both records replay-verified.**
- **No reference ambiguity.** The text has exactly one template in each state, and refers to the same simulator uuids in both.
- **A documented state difference.** At least one discrete field or object differs between the two S0s. A temperature-only difference is reported, but does not qualify.
- **Different consequences.** The *consequence signature* differs: evidence status, best match level, discrete effect (`object:field=after`), or created / deleted object names.

Pairs are **candidates only**: `status = candidate_unvalidated`, `validated = false`. They are **NOT validated reversibility minimal pairs**, and must not be counted towards REQ-DATA-05. Becoming a spec minimal pair (REQ-DATA-05: "same verb, reversibility changes with the state") requires labels, which Phase 4E does not issue. A signature difference shows only that the consequences differ.

## 6. Validation (`validate_dataset`, no Java)

| Check | What fails it |
|---|---|
| `schema_integrity` | Missing or extra fields; wrong schema version; gold-schema fields; bad recipe; id ≠ hash(recipe, action); unknown evidence status |
| `unique_ids` | Repeated `example_id` or `candidate_pair_id` |
| `content_checksums` | `content_sha256` does not match the content |
| `duplicates` | Repeated (canonical fingerprint, action) or (discrete fingerprint, action) |
| `action_validity` | History ≠ recipe; a history step that was not accepted; a researcher operation counted as an agent action; first tick not consumed; target invalid, ambiguous, refused or without an observed effect; target absent from the stored valid-action list; ticks inconsistent with S0 moves |
| `door_exclusion` | Door text, or a target uuid outside the object tree |
| `replay_verification` | Fingerprints do not agree, or `verified` is false |
| `provenance` | Recipe or record not pinned to `e8216d6` |
| `state_files` | State file missing; SHA-256 mismatch; re-canonicalising it does not give the recorded fingerprints |
| `missing_state_disclosure` | `complete` is not false; base incompleteness reasons missing; a comparison without `unknown_fields` |
| `restricted_search_disclosure` | `exhaustive` is not false, `restricted` is not true, or the failed-search meaning is missing |
| `no_label_leakage` | Label-like keys or values, or evaluation signals, anywhere in a record or pair |
| `scientific_status` | Anything other than the provisional statement (for example `professor_approved: true`) |
| `candidate_pairs` | Unknown or identical members; text, family or uuids differ; unverified member; no documented state difference; the consequence difference does not match the records; claims validation |

The pilot script adds two checks that need the simulator:
- **Fresh replay:** every record's recipe is replayed in a new JVM, and S0's raw and canonical fingerprints are compared.
- **Deterministic regeneration** (`--regenerate`): the whole pipeline runs a second time into `pilot-v0-regen/`, and `records.jsonl`, `candidate_pairs.jsonl`, `rejections.jsonl` and the state file set are compared byte for byte.

## 7. Pilot results

Command: `scripts/scienceworld/provisional_pilot.py --regenerate` with the default `SamplerConfig` (seed 20261031, 8 base samples per family, sibling rate 0.75, `max_paths` 4). Outputs are in `data/scienceworld_provisional/pilot-v0/` (git-ignored, 13 MB, 27 state files). The manifest records the git commit (`9ff62c8` plus an uncommitted Phase 4E tree) and the SHA-256 of every output file.

### 7.1 Yield [RUN]

| Family | Usable records (siblings) | Verb classes | Evidence status | Candidate pairs |
|---|---|---|---|---|
| `boil-kitchen` | 11 (4) | activate/deactivate 3, eat 2, open/close 2, pick up 2, pour 2 | match exact 4, match ≤0.1 °C 2, mismatch 1, no candidate 4 | 1 |
| `power-workshop` | 12 (4) | connect 4, pour 4, move 2, open/close 2 | match exact 6, no candidate 6 | 0 |
| `grow-greenhouse` | 12 (4) | pick up 6, open/close 4, activate/deactivate 2 | match ≤0.1 °C 6, mismatch 6 | 10 |
| **Total** | **35 (12)** | | **exact 10, ≤0.1 °C 8, mismatch 7, no candidate 10** | **11** |

- **Rejections.** `rejections.jsonl` has 89 rows, each with its reason:
  - 57 parse failures on listed actions (history 30, contrast 16, target 11);
  - 25 actions without an observed discrete effect;
  - 4 cases where the target was unavailable after the contrast;
  - 1 ambiguous contrast;
  - 1 duplicate;
  - 1 family that exhausted its attempts.

  The summary metric `sampling_attempts_incl_rejections` is also 89, by coincidence. It counts the 35 accepted examples (23 base + 12 siblings) plus the 54 history/target rejections.
  The kitchen exhausted its 30 attempts with 7 base samples.
- **Parse failures.** **[RUN]** ScienceWorld's valid-action list over-generates. For example, in a clean kitchen state `move ceramic cup to stove` is listed with template 9, but the parser rejects it with "No known action matches that input". It takes 0 ticks, and the cup is inside the closed cupboard. These failures are rejected correctly and cost no time. They are the main sampling inefficiency.
- **Duplicates.** Rate 1/89 (0.011).
- **Evidence failures.** 0: no reconstruction divergence and no invalid replay.
- **Door exclusion.** On average 176 door or portal actions were removed from each target pool (RD-05).
- **Histories.** S0 is at 3–7 ticks, with prefix lengths 0–3, plus 1 contrast for siblings.

### 7.2 Restoration evidence [RUN]

The pilot has 33 executed candidate paths, all with an available counterfactual.

| Match level vs counterfactual | Paths | Cases |
|---|---|---|
| exact | 10 | close/open freezer, deactivate/activate freezer, activate/deactivate oven, moves and pours of switch/bulb and return (workshop) |
| within 0.01 °C | 0 | — |
| within 0.1 °C | 16 | pick up glass jar / flower pot 1 / flower pot 2 / jug, then return. Only temperatures differ: 10–18 fields, max \|ΔT\| 0.0138–0.0144 °C |
| none | 7 | activate/deactivate sink (a new water object and terminals remain); open/close bee hive (bees have left the hive) |

- **The tolerance choice matters (RD-02).** Every pick-up/return residual lies between 0.01 and 0.1 °C. Choosing 0.01 or 0.1 °C as an approximation threshold moves 8 records between "within tolerance" and "mismatch". This is why all three levels are stored, and why the threshold is a sensitivity analysis rather than a hidden constant.
- **No candidate (10 records):** eat (2), connect (4), and pours/moves into another room (`pour switch into hallway`, `pour counter into kitchen`), where the return-to-parent rule finds no agent-valid return in the target room. These stay `no_candidate_path_found`, not irreversible (RD-04).

### 7.3 Candidate minimal pairs [RUN]

- **Counts.** There were 19 same-family, same-text comparisons in 14 groups. 11 became candidates: 5 sibling and 6 independent pairs. 8 were rejected for having the same consequences.
- **Yield:** 0.31 candidate pairs per record.
- **Pair types:**

| Pairs | Action | What differs |
|---|---|---|
| 1 | `activate sink` (greenhouse) | Created objects: 2 waters vs 1 (a container in the sink receives water). This is the pair type the Phase 4D sink experiments predicted |
| 3 | `pick up flower pot 1` / `flower pot 2` / `jug` | Effect: what is carried along (soil in the pot, a pot in the jug) |
| 1 | `pour counter into kitchen` | Effect: whether the lighter is moved |
| 6 | `open bee hive` | Effect: *which* bees leave the hive |

- **Caveats:**
  - **No pair differs in evidence status.** Both members always have the same restoration evidence, and only the target's effect signature differs. So none is yet a pair in which *restorability* changes with the state, which is what REQ-DATA-05 asks for.
  - **The 11 candidate pairs are NOT validated reversibility minimal pairs.**
  - **The six bee-hive pairs are not meaningful evidence.** They are driven by stochastic bee movement (`Bee.scala` uses the global `scala.util.Random`), and are reproducible under replay only. They should be excluded, or the criterion tightened (§9, OQ-39).

### 7.4 Reproducibility and validation [RUN]

- **Validator:** all 14 checks pass on 35 records and 11 pairs, including state-file checksums and re-canonicalisation.
- **Fresh-JVM replay:** 35/35 records reproduce S0's raw and canonical fingerprints. Replay takes 2.9 s mean and 3.8 s max.
- **Deterministic regeneration:** a second full run produced byte-identical `records.jsonl`, `candidate_pairs.jsonl` and `rejections.jsonl`, and the same state-file set.
- **Phase 4D query-order fix:** the first pilot attempt stopped on the query-order divergence (§3.2). After the fix, no divergences occurred in three complete pilot runs.

### 7.5 Performance [RUN]

Windows 11, native Temurin 21, one JVM at a time.

| Measure | Value |
|---|---|
| Sampling, all families | 183 s (5.2 s per accepted example, rejected draws included) |
| Evidence per record | 9.1 s mean, 16.9 s max (verification replay, S1 rebuilds, counterfactual) |
| Evidence per candidate path | 9.6 s |
| Fresh replay per record | 2.9 s mean |
| Pairs + validation (no Java) | 1.5 s |
| Pilot end to end (excluding fresh replay and regeneration) | 502 s for 35 records ≈ 14 s per record |

**Extrapolation [ARG].** At ≈14 s per record, 1,000 ScienceWorld records would take about 4 hours on one JVM. The dominant cost is per-path rebuilds; a wider candidate search multiplies it. Several JVMs in parallel are possible, since each record is independent. Bulk work should still move to Linux (OQ-32).

### 7.6 Unresolved scientific limitations

These are open; the pilot does not resolve them.

1. **Query-order dependence (OQ-38).**
   - **Cause [SRC].** Valid-action referent text depends on earlier free queries, through the shared global RNG.
   - **Mitigation.** A fixed query protocol (§3.2) makes every recorded state self-consistent and reproducible. The protocol is a team convention, not a property of the simulator.
   - **Untested risk.** Two things have not been tested at scale:
     - whether queries can perturb stochastic dynamics (not observed in 2 probes);
     - whether the counterfactual and path branches diverge because their query sequences differ.
2. **Temperature-threshold sensitivity (RD-02).** All pick-up/return residuals (0.0138–0.0144 °C) fall between the 0.01 and 0.1 °C levels, so 8 of 35 records change category with the threshold. No threshold is justified physically; the choice remains a sensitivity analysis, not a resolved definition.
3. **Stochastic processes (OQ-39).** Bee movement makes 6 of 11 candidate pairs, and the bee-hive counterfactual mismatches, depend on randomness rather than on the action.
4. **Pair criterion (OQ-40).** No pilot pair differs in evidence status. Candidate pairs are therefore not evidence that restorability changes with the state.
5. **Restricted search and incomplete observation (RD-04, RD-05).** `no_candidate_path_found` and mismatches are never irreversibility, and a match is never exact simulator-state equality.

## 8. Path to approved gold examples (not done in Phase 4E)

1. **Team decisions still needed:**
   - OQ-03: what "partial restoration at a cost" means in ScienceWorld;
   - OQ-37: whether structural replacement counts;
   - the RD-03 mapping from evidence status to concept, including whether an exact counterfactual match plus disclosed incompleteness is accepted as exact restoration;
   - the horizon semantics for `wait` (OQ-30, second part).
2. **Certificates** (`docs/19` §5) for irreversible cases: mixing (C-MIX-SALT), combustion (I1/I2) and eating, written and reviewed before any `irreversible` is issued (RD-04).
3. **A wider candidate search** on a subsample: every agent-valid 1-step action on the target's objects, and 2-step on a sample. This tests how often restricted-search statuses change.
4. **Mapping.** Apply the agreed mapping to stored evidence. No re-simulation is needed unless the candidate set changes. Undetermined cases are excluded or reported separately (RD-03).
5. **Gold records.** Build gold records with a ScienceWorld state renderer for `state_text` (a new, versioned renderer, outside prompt builder 1.0.0). Validate them with the C1 validator, generate pairs from candidate pairs whose labels actually differ, and include them in the human agreement sample (REQ-LBL-05).
6. **Scale-up** towards the ScienceWorld share of REQ-DATA-01 only after steps 1–5. Bulk generation should run on Linux (OQ-32).

## 9. Remaining decisions

The professor will not be consulted (project decision 2026-10-31). The following remain **research-team decisions** to be recorded in a new ADR:

| Item | Status |
|---|---|
| OQ-03 partial restoration in ScienceWorld | Open; blocks labels |
| OQ-37 structural replacement | Open; blocks labels for refill/replace cases |
| RD-03 evidence → concept mapping | Concepts fixed; mapping not yet decided |
| OQ-33 / RD-11 simplification preset for the final dataset (`teleportAction` vs `easy`/`openContainers`) | Pilot uses `teleportAction`; final choice open |
| OQ-38 query protocol | Implemented as proposed; to be confirmed as the dataset definition |
| OQ-34 split unit for ScienceWorld | Family-level grouping is recorded; decision open |
| OQ-39 stochastic processes (bees) | Open; 6 of 11 pilot pairs affected |
| OQ-40 gold minimal-pair criterion (label difference) and targeted contrast generators | Open; no pilot pair differs in evidence status |

## 10. Tests

- **`tests/test_scienceworld_provisional.py`** (no Java, fake kitchen). It covers:
  - temperature sensitivity, including that temperatures are never dropped;
  - the evidence ladder;
  - verb classes and door exclusion;
  - deterministic ids and RNG; ambiguity filtering;
  - full pipeline validation; agent-valid histories; no duplicates; sibling text identity;
  - byte-identical regeneration; seed sensitivity;
  - pair discovery, plus each pair rejection rule;
  - one mutation test per validator check.
- **`tests/test_scienceworld_provisional_integration.py`** (marker `scienceworld`). It covers:
  - a small real pilot that validates;
  - a fresh-JVM replay of a recorded S0;
  - all three temperature comparisons present and none ignoring temperature;
  - a real `activate sink` candidate pair;
  - no leaked Java processes.
