# 26: Controlled dataset scaling pilot (Phase 5B)

- **Status:** pilot report (Phase 5B). This is **not** the final dataset.
- **Unchanged:** the 210-example pilot (sha256 `f66b98ba…`, re-checked after generation), prompt builder 1.0.0, the shared dataset API, `src/adnn/sandbox` and `sw-admission-2`.
- **Approval:** no professor approval is claimed. Professor contact was not required and did not happen.
- **Base:** Phase 5A commit `c47cc221918adaeec59bdfec5f1cd09a70007889`.
- **Decision record:** `docs/decisions/0007-dataset-scaling-pilot.md`.
- **Frozen protocol:** `docs/preregistration/phase5b_manifest.json`.
  - content hash `4b029749a2ea9d00129e1e29a74840032a0a5d3a1bbcae227962687912e0f0ad`;
  - frozen 2026-10-31T18:22:27Z, before any record was generated.
- **Code:**
  - `src/adnn/feasibility/scaling_pilot.py`
  - `src/adnn/feasibility/stop_conditions.py`
  - `scripts/dataset/phase5b_pilot.py`
  - `tests/test_scaling_pilot.py`
- **Outputs (git-ignored):**
  - records in `data/scaling_pilot/`;
  - audit and replicas in `results/phase5b/`.
- **Evidence tags:**
  - [RUN] measured here;
  - [DEC] team decision;
  - [EST] estimate with stated basis.

## 1. Summary

| Question | Answer |
|---|---|
| Sandbox stratum | 240 / 240 planned records, 12 families, no drops, no family excluded [RUN] |
| ScienceWorld stratum | **Stopped before generation.** The existing sampler offers 7 genuinely distinct action families, not 8, and only 3 task families, so the 25% per-task cap cannot be met. No candidates were run (§6). |
| Gold (tier G) | 220. Another 20 are tier P (the OQ-21 sensitivity group, all irreversible). 0 rejected [RUN] |
| Re-derivation | 240 / 240 labels re-derive with valid support. OQ-24 widening changes 0 [RUN] |
| Strict minimal pairs | 45 genuine pair groups out of 60. 90 / 240 records = **0.375** [RUN] |
| Stop conditions | S2, S4–S7 evaluated, none triggered. **S1 and S3 are NOT EVALUABLE, not passing**, because no ScienceWorld data exists (§5) |
| Reproducibility | Two fresh-process replicas are byte-identical (sha256 `bfd1175f…`) [RUN] |
| Main finding | **The count scales cheaply, but underlying diversity does not.** The 240 records realise only **37 distinct state/action structures**. **213 / 240 records reuse a scenario structure from the earlier 210-example pilot, and none of the original stop conditions S1–S7 detected this** (§4.5, §5). |
| Full-scale generation justified? | **Not yet** (§8). |

## 2. Frozen protocol (STEP 1)

The manifest was written by `phase5b_pilot.py freeze`, which refuses to overwrite an existing manifest. `generate` refuses to run if the manifest hash does not verify, and it writes `split.json` before any record text. The manifest fixes:

- **Seeds:** master seed `20261101`. Family selection, split and generation each derive their seed from it by string-keyed `random.Random`.
- **Admission and label rules:**
  - sandbox oracle BFS, complete over D at h = 3, `max_nodes` 200000;
  - keep only definitive results;
  - partial definition per ADR-0006 D11 (OQ-47);
  - OQ-21 and OQ-23 defaults as documented;
  - OQ-24 limitations listed;
  - ScienceWorld `sw-admission-2`, pinned to e8216d6, with no irreversible admission and no bee or hidden-door gold.
- **Family allocation:**
  - 10 existing families chosen by seed with fixed per-domain counts (files 4, email 2, money 4): f02, f03, f04, f06, f07, f08, f10, f11, f12, f13;
  - 2 new families (§3.1);
  - 5 scenarios × 4 examples each.
- **Split (family-disjoint):**
  - one test family per domain: f06_edit_backup_present, f08_email_undo_short, f13_pay_refund_fee;
  - the other 9 families are train.
  - The test families use a held-out render style (`compact`) in addition to the train styles.
- **Exclusions:**
  - duplicates within the set;
  - duplicates against the 210-example pilot (state and action text);
  - non-definitive oracle results;
  - any new family whose labels do not match its declared design (the whole family is excluded, never patched).
- **Sensitivity groups:** OQ-21 (tier P, kept, never counted as gold).
- **Code hashes:** of `scaling_pilot.py`, `stop_conditions.py`, `dataset/pilot.py`, `sandbox/restoration.py` and `sandbox/tools.py`.
- **ScienceWorld decision:** recorded at freeze time (§6).

**Deviation from the docs/25 §9 proposal, decided at freeze time:**
- The proposal planned 6 existing families plus 6 new ones.
- Only 2 new families could be built honestly from the existing tool set. Each varies one configuration pivot (`payment_cancel_window_s`).
- Any further genuinely new mechanism needs new sandbox tools or state. That is outside this phase's limits, which forbid modifying `src/adnn/sandbox`.
- The remaining slots were filled with existing families. They are not padded with cosmetic variants presented as new families.

## 3. Sandbox stratum (STEP 2)

### 3.1 New families

| Family | Mechanism | Window (pivot values) | Expected design | Outcome |
|---|---|---|---|---|
| n01_pay_cancel_window | cancellable payment; restoration possible only while the cancel window is open | 60 s vs 10 s | R / I | matched; included |
| n02_pay_two_step_window | two-step cancellable payment with a window | 60 s vs 20 s | R / I | matched; included |

Both families are verified by brute force (the full oracle) on every record. A design mismatch would have excluded the whole family. Neither was excluded.

### 3.2 Counts [RUN]

| | Reversible | Partial | Irreversible | Total |
|---|---|---|---|---|
| All | 89 | 77 | 74 | 240 |
| Tier G | 89 | 77 | 54 | 220 |
| Tier P (OQ-21) | 0 | 0 | 20 | 20 |
| Train (9 families) | 67 | 60 | 53 | 180 |
| Test (3 families) | 22 | 17 | 21 | 60 |

The class shares are 0.37 / 0.32 / 0.31, within the ±15 target of about 80 each.

**Per family (R / P / I):**

| Family | R | P | I |
|---|---|---|---|
| f02_delete_backup_fresh | 7 | 6 | 7 |
| f03_delete_backup_present | 7 | 6 | 7 |
| f04_edit_versioning | 4 | 10 | 6 |
| f06_edit_backup_present (test) | 9 | 2 | 9 |
| f07_email_undo | 9 | 6 | 5 |
| f08_email_undo_short (test) | 9 | 6 | 5 |
| f10_pay_two_step_vs_final | 9 | 4 | 7 |
| f11_pay_refund_vs_final | 4 | 9 | 7 |
| f12_pay_cancel_vs_refund | 9 | 11 | **0** |
| f13_pay_refund_fee (test) | 4 | 9 | 7 |
| n01_pay_cancel_window | 9 | 4 | 7 |
| n02_pay_two_step_window | 9 | 4 | 7 |

f12 contributes no irreversible examples. This is by design: cancel versus refund are both restorable within h = 3.

**Labels per horizon:**

| Horizon | R | P | I |
|---|---|---|---|
| h = 1 | 79 | 77 | 84 |
| h = 2 | 89 | 77 | 74 |
| h = 3 | 89 | 77 | 74 |

Ten records labelled I at h = 1 become R at h ≥ 2. Labels are horizon-relative. h = 3 is the declared label.

### 3.3 Evidence quality [RUN]

| Support class | Count |
|---|---|
| reversible, verified exact witness (replayed) | 89 |
| partial, verified approximate witness plus complete exact exclusion | 77 |
| irreversible, complete bounded impossibility over D at h = 3 | 74 |
| unsupported | **0** |

- **OQ-24 widened domain** (positive balances plus pairwise sums of amounts plus recombined email fields): 0 label changes.
- **OQ-21 alternative information rule:** 20 label changes. These 20 records form the sensitivity group (tier P). They are kept in `records.jsonl` with `sensitivity_group: "OQ-21"` and excluded from gold and from strict pairs.

## 4. Quality and leakage audit (STEP 5)

### 4.1 Gold, provisional and rejected

- 220 gold;
- 20 provisional (OQ-21);
- 0 rejected or dropped;
- 0 families excluded;
- 0 duplicates rejected against the 210-example pilot. The generator checks for them, and none occurred.

### 4.2 Strict minimal pairs (ADR-0006 D6)

**Denominator:** all 240 records, or 60 pair groups (one per scenario).

| Definition | Genuine pair groups | Member fraction |
|---|---|---|
| **Strict:** same scenario, byte-identical action text, ≥ 2 distinct labels, every member tier G | **45 / 60** | **0.375** (90 / 240) |
| Spec (REQ-DATA-05: same action, label changes with state, any tier) | 60 / 60 | 0.500 (120 / 240) |

The 15 groups that fail the strict test do so because a member is tier P (OQ-21-sensitive). Identical action text alone is never counted as a pair. The non-pair examples (s0/s1) are, by construction, not pair members, so 0.5 is the ceiling for this design.

### 4.3 Duplicates and near-duplicates

- Exact duplicates: unique inputs (state text, action text) 240 / 240; unique (state_struct, action_call) 240 / 240.
- **Surface-masked template signatures:** 183 / 240, an effective fraction of **0.7625**. 4 signatures are shared across scenarios.
- **Pooled with the 210-example pilot:** 324 signatures over 450 records. The maximum is 5 records per signature, and 5 signatures exceed the D5 cap of 3.

### 4.4 Split integrity and leakage

| Check | Result |
|---|---|
| Group (family) disjoint | yes |
| Scenario overlap train ↔ test | 0 |
| Exact input overlap | 0 |
| Normalised template overlap | **1** signature |
| Verb-majority baseline on test (predict the train-majority label for the action verb) | **0.417**, against a test majority-class rate of 0.367 |

The verb shortcut gains about 5 points over the majority class. The verb × label table shows why:
- `edit_file` is mostly partial (48 P, 15 I, 5 R);
- `delete_file` is mostly reversible (30 R, 14 I).

The leak is moderate. It must be reported next to every model accuracy on this split, and it argues for more verb-balanced families (§8).

### 4.5 Unique underlying scenarios versus cosmetic rewordings

`structure_signature` masks surface values (paths, names, amounts, text) outside the configuration and drops clock and counters. It keeps the configuration, tool and state shape. Two records with the same structure differ only cosmetically.

| Measure | Value |
|---|---|
| Distinct structures in the 240 new records | **37** (fraction 0.154) |
| Records whose structure already occurs in the 210-example pilot | **213 / 240** |
| Structures that are new relative to the pilot | 9 (27 records: 20 from n01/n02, 7 scattered variants in existing families) |
| Template signatures shared with the pilot | 20 |
| Largest structure group in the new set | 23 records |

**Interpretation:**
- The 240 records are distinct examples: no exact duplicates, and a 0.76 effective fraction at the surface-masked level.
- But they are mostly **re-sampled surface values of a small set of underlying scenarios**. The generator, which reuses existing family builders, is close to saturation.
- The headline effective fraction (S5) does not detect this, because S5 masks only names and amounts, not values that encode the same structure.

This is the binding constraint on scaling (§7).

### 4.6 Reproducibility, provenance and checksums

- Two fresh-subprocess regenerations (`results/phase5b/replica_a`, `replica_b`) produced byte-identical `records.jsonl` (sha256 `bfd1175f…`).
- `generation_report.json` stores:
  - the manifest hash;
  - the `split.json` hash;
  - the records hash;
  - a per-record sha256 of each record's full JSON, covering evidence, witness, search status and labels per horizon.
- Each record carries its scenario_id, family, tier, sensitivity group, partial-definition note and generator version.

### 4.7 Temperature and declaration sensitivity

These checks apply to ScienceWorld only. The stratum did not run, so they were not measured in this pilot. The Phase 4H findings (docs/24) stand unchanged. In the sandbox, the analogous sensitivities are the declaration checks OQ-21 (20 changes) and OQ-24 (0 changes) (§3.3).

## 5. Stop conditions (STEP 4)

These are executable in `adnn.feasibility.stop_conditions`. A check that is not evaluable is reported as such, never as a pass.

| # | Condition | Threshold | Value | Triggered |
|---|---|---|---|---|
| S1 | ScienceWorld gold yield at the 80-candidate checkpoint | ≥ 0.10 | **not evaluable** (no candidates) | n/a |
| S2 | Replication failures / measurement-affected fraction | 0 / ≤ 0.02 | 0 / 0.0 (sandbox; ScienceWorld not run) | no |
| S3 | Rubric-sensitive fraction of eligible ScienceWorld outcomes | ≤ 0.10 | **not evaluable** | n/a |
| S4 | Largest family share of a class | ≤ 0.40 | I: f06 0.122 · P: f12 0.143 · R: f06 0.101 | no |
| S5 | Surface-masked effective fraction | ≥ 0.60 | 0.7625 | no |
| S6 | Strict genuine-pair fraction | ≥ 0.30 | 0.375 | no |
| S7 | Sandbox re-derivation failures | 0 | 0 | no |

**S1 and S3 are NOT EVALUABLE, not passing.** No ScienceWorld candidate exists, so no ScienceWorld yield or rubric-sensitivity claim follows from this pilot.

**The conditions did not detect prior-scenario reuse.** All evaluable conditions passed, yet 213 / 240 records reuse a scenario structure from the 210-example pilot (§4.5). S5 counts surface-masked signatures within the new set only. It neither compares structures nor compares against earlier datasets. This is a gap in the original conditions; it is not retroactively patched. Under OQ-51 (approved), future validation must measure underlying scenario diversity.

No threshold was changed after the results were seen. The thresholds are frozen in the manifest. The ScienceWorld stop (§6) is a separate frozen decision, not one of S1–S7. It happened earlier: the stratum could not be sampled as specified.

## 6. ScienceWorld stratum (STEP 3): stopped

**The sampler was assessed against the pre-registered requirement before freezing.** The result is stored in the manifest under `scienceworld`.

The sampler verb classes are:
- `open_close` → container;
- `activate_deactivate` → device;
- `move` and `pick_up` → **relocation (one family)**;
- `pour` → liquid transfer;
- `eat` → consumption;
- `mix` → chemistry;
- `connect` → electrical.

This gives **7 genuinely distinct physical families**, not 8. `move` and `pick_up` both relocate an object between containers. Counting them separately would manufacture diversity.

**Combustion** (`use lighter on X`) is not supported by the sampler. Note that combustion is the only family that currently yields certificate-supported partials (C-BURN).

**Task coverage:**
- 3 configured task families (1-1, 3-1, 5-1);
- the smallest achievable maximum task share is 1/3 = 0.333, above the 25% cap.

**Decision (frozen, per the instruction):** *stop and report; do not manufacture artificial diversity.* No ScienceWorld candidate or contrast candidate was generated. S1 and S3 are therefore not evaluable.

**What would unblock the stratum (a team decision, not done here):**
1. Add a combustion verb class, with lighter handling and the C-BURN certificate path, to the sampler.
2. Configure at least 4 task families so that the 25% cap is satisfiable.
3. Optionally split `move` into genuinely different mechanisms (e.g. device placement versus container transfer), only if their transition semantics actually differ.

Each change requires a new frozen manifest. None changes `sw-admission-2`.

## 7. Performance and the updated 2,000-gold estimate (STEP 6)

### 7.1 Measured [RUN]

| Item | Value |
|---|---|
| Sandbox generation (240 records, including oracle and witness replay) | 98.9 s ≈ 0.41 s / record |
| Evidence audit (240 records, including OQ-24 widened re-search) | 448 s ≈ 1.9 s / record |
| One fresh replica (regeneration) | 90–95 s |
| Storage | records.jsonl 810 KB (≈ 3.4 KB / record); report 26 KB; split 0.6 KB; tool sets 6.4 KB |
| Failure rates | 0 drops, 0 non-definitive, 0 re-derivation failures, 0 replication failures |
| ScienceWorld | not run; the docs/25 estimate of about 2–2.5 min per case stands, unmeasured here |

### 7.2 Updated estimate (not linear)

Compute is not the constraint. 2,000 sandbox records would take about 14 min to generate and about 1 h to audit, and need about 7 MB. A linear extrapolation of counts ("240 in 99 s, so 2,000 is trivial") would, however, be misleading. The constraints are diversity and the composition rules:

- **ScienceWorld gold is currently 0 by construction.** The stratum cannot run until the sampler is extended. Docs/25 projected 400–600 ScienceWorld gold; that projection now depends entirely on the work in §6. Until then the sandbox must carry the whole target.
- **Sandbox gold yield** is 220 / 240 = 0.917, because OQ-21 removes about 8%. 2,000 gold therefore needs about 2,180 sandbox records.
- **ADR-0006 D5 limits:**
  - at most 3 records per signature, so ≥ 667 distinct signatures;
  - at most 8% per family, so ≥ 13 families.
- **Saturation:**
  - The 12 families produced 183 signatures, but only 37 underlying structures, about 3 per family.
  - Generating more records from the same families adds surface variation, not new scenarios.
  - Pooled with the pilot, 5 signatures already exceed the per-signature cap of 3.
  - So the D5 per-signature cap would bind long before 2,000 if generation stayed within the existing families.
- **Required diversity [EST]:** reaching 2,000 gold with genuinely distinct scenarios, at the observed ~3 structures per family and ≤ 8% per family, needs **roughly 28+ families with new mechanisms**. That is the ADR-0006 D4 target. The 2 new families in this pilot are config-pivot variants of existing payment mechanisms. They do not demonstrate that 14+ mechanistically new families can be built.

**Assessment:**
- 2,000 gold remains **feasible in compute and in label validity**: 0 re-derivation failures, all three classes, 0.375 strict pairs.
- It is **not demonstrated in diversity**. As things stand, it would be reached mainly by cosmetic re-sampling, which ADR-0006 D5 forbids.
- Feasibility is conditional on (a) new sandbox mechanisms (new tools or state, which needs a decision because it touches `src/adnn/sandbox`) and (b) the ScienceWorld sampler extensions in §6.

## 8. Is full-scale generation justified?

**Not yet.** The label machinery is sound at scale: reproducible, fully supported and three-class. But:

1. The ScienceWorld stratum has not run (it was stopped by design).
2. The sandbox families are saturated at the structure level (37 structures; 213 / 240 records repeat pilot structures).
3. There is a moderate verb shortcut (about 5 points).

**Team decisions (2026-11-01, ADR-0007 P7):**
- OQ-49, approved in principle: future sandbox extensions may add genuinely new mechanisms.
- OQ-50, deferred: no ScienceWorld sampler expansion now; the stratum stays stopped.
- OQ-51, approved: future dataset validation must measure underlying scenario diversity.

**Recommended next steps:**
- design and brute-force-verify mechanistically new sandbox families, which requires permission to extend `src/adnn/sandbox`;
- extend the ScienceWorld sampler with combustion and more task families, under a new frozen manifest;
- add a structure-level diversity check (`structure_signature`) to the stop conditions for full-scale generation, since S5 alone does not detect structural saturation;
- prefer families that balance labels within each verb.

## 9. Limitations

- **The ScienceWorld stratum was not run.** No new ScienceWorld yield, temperature, rubric or symmetry data exists from this phase.
- **Only 2 new sandbox families,** both config-pivot variants. The pilot does not test whether genuinely new mechanisms can be built.
- **The structure signature is a heuristic.** It may merge records whose differences matter (e.g. the relative timing of a window) or split cosmetic ones. The 37 count is indicative, not exact.
- **The verb shortcut** is measured with a single heuristic (verb majority). Stronger lexical baselines, such as bag-of-words, are not run here; they belong to M2's baseline work.
- **Labels remain relative** to h = 3 and D, with the OQ-21 and OQ-23 defaults and the OQ-24 limitations. None is a claim of universal irreversibility.
- **Only one split seed** was evaluated (family-disjoint). The three-seed scenario-level splits (ADR-0006 D9) are not exercised by this pilot.
- No human annotation exists (REQ-LBL-05 is still unmet).

## 10. Tests and files

- `tests/test_scaling_pilot.py` covers:
  - the manifest determinism and tamper check;
  - the per-domain seeded allocation and split;
  - the new-family constraints;
  - the distinct-family ScienceWorld assessment (7 < 8; move = pick_up);
  - OQ-21 tiering;
  - the structure signature;
  - stop-condition semantics, including "not evaluable is not a pass" and the boundary thresholds.
- Re-run with:

```
python scripts/dataset/phase5b_pilot.py generate   # deterministic; refuses on a bad manifest
python scripts/dataset/phase5b_pilot.py audit      # writes results/phase5b/audit.json
```
