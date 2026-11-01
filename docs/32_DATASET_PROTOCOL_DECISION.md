# 32 — Decision memo: production protocol for the labelled dataset

**Status.** DRAFT for team review. Nothing was generated, and no gate, label, manifest or code
was changed. No professor approval is claimed and the professor was not contacted.
**Base:** `f32b1e7` (docs/31).

## 1. What the professor requires, and what we added

**Professor's specification** (`references/ADNN_Project_Option_1_Irreversibility.docx`):

| Ref | Exact text | Our id |
|---|---|---|
| §4.3 | "Target at least 2,000 labelled (state, action) pairs in total, from both testbeds." | REQ-DATA-01 |
| §4.3 | "Keep the three classes roughly balanced; if they are not, report the class counts and use balanced accuracy." | REQ-DATA-02 |
| §4.3 | "Keep 20% aside as a test set, split by task or scenario, not by individual action. Otherwise the probe can memorise a scenario and your numbers will be inflated." | REQ-DATA-03 |
| §6 Step 1 | "At least 30% of your data must be minimal pairs." | REQ-DATA-05 |
| §4.2 | Labels are reversible, partially reversible or irreversible, with the horizon 3 as a parameter (report 1, 2, 3); a hand-labelled sample of 100 pairs | REQ-LBL-* |

The specification sets **no limit on records per scenario and no scenario-novelty
requirement**. Its split rule assumes several actions per scenario: "split by task or
scenario, not by individual action".

**Rules the team added** (internal; none comes from the professor):

| Rule | Source | Status |
|---|---|---|
| SD1: ≥ 50% of gold records in coarse scenarios new against the prior datasets | docs/27 §6 | Prospective gate for the next *expansion pilot*. Frozen only in the Phase 5E pilot manifest. |
| SD2: ≤ 3 gold records per coarse scenario | docs/27 §6 | Same as SD1. |
| D5: ≤ 3 records per surface-masked template signature; ≤ 8% per family; effective fraction ≥ 0.6 | ADR-0006 | Adopted team rule. |
| D3: counted tiers (only G counts) | ADR-0006 | Adopted team rule. |
| D6: strict pairs (same `scenario_id`, byte-identical action, all tier G) | ADR-0006 | Adopted team rule. |
| D4: ≥ 28 sandbox families; 400–600 ScienceWorld gold | ADR-0006 | Research target, already missed. |

**Answer to question 3.** The figure of ≥ 667 distinct coarse scenarios comes **only from our
SD2 rule** (2,000 / 3). The professor's 2,000 counts state-action pairs. What the
specification does need is (a) enough scenarios for a meaningful scenario-held-out 20% test
set and (b) no scenario memorisation inflating the results.

SD2 was designed to stop an expansion pilot from presenting cosmetic re-sampling as *new
diversity*. It was never derived from a statistical requirement on the final dataset.

## 2. Supply this decision rests on (docs/31; pooled gold of `pilot_v0.1` and Phase 5B)

- **347 gold records** over **57 coarse scenarios**.
  - Class mix: R 170 / P 77 / I 100.
  - Every coarse scenario has a single label. A minimal pair therefore spans two coarse
    scenarios.
- **Scenarios per class:** R 25 / P 18 / **I 14**. Irreversible is the scarcest class *at the
  scenario level*.
- **Scenario sizes are skewed:** the largest has 31 records, and 17 scenarios have 1. Records
  kept at each cap:

  | Cap per scenario | Records kept |
  |---|---|
  | 3 | 129 (R 60 / P 36 / I 33) |
  | 6 | 210 |
  | 12 | 280 |
- **Reachable scenario universe with the current generators:** about **126–177** coarse
  scenarios. That is the 57 existing, plus 59 (number-masked) to 110 (raw) new legacy shapes,
  plus 10 link scenarios. Most of these are known behaviours in new combinations.
- **ScienceWorld:** **0** gold records. There are 7 tier-G candidates from constructed cases,
  but the stratum is stopped (OQ-50).

## 3. The three protocols

| | **A. SD2 ≤ 3 unchanged** | **B. Higher cap (≤ 12), scenario-disjoint** | **C. Two tiers: diverse evaluation set plus augmentation set** |
|---|---|---|---|
| Attainable gold (estimate) | **≈ 350–500**: 3 × 126–177 scenarios, less attrition | **≈ 1,400–2,000**: ceiling 12 × 126–177. D5's 8% per family limits each family to ≈ 160 records, and both bounds bind. Not verified; needs a dry run. | Evaluation set as in A (≈ 350–500), plus training-only variants (≥ 1,500 feasible). Total ≥ 2,000 is the most reachable. |
| Class balance | ≈ 47 / 28 / 26% (R / P / I) at cap 3: acceptable | Tracks the scenario mix, ≈ 44 / 32 / 25%: borderline "roughly balanced"; report counts and balanced accuracy | Evaluation set as in A; augmentation can be stratified |
| Strict minimal-pair rate | ≈ 40% (current gold 0.41–0.47) | 40–60%, if both pair members are varied together | Evaluation set ≈ 40%; augmentation as generated |
| Leakage risk | Lowest | **Medium**: within-scenario variants are near-duplicates, safe only if the split groups by number-masked scenario ∪ `pair_id` | Lowest for test, because no test scenario is ever augmented. Risk moves to misreporting counts. |
| Scientific validity | Highest per record. The test set has only ≈ 30 scenarios and ≈ 90 records, so CIs are about ±10 percentage points. | Valid **if** claims are made per scenario: CIs from a scenario-clustered bootstrap, effective n = scenarios, Hewitt–Liang control tasks. The probe could otherwise learn scenario identity. | High for headline metrics, which use the evaluation set only. The augmentation tier has no inferential weight. |
| Professor compatibility | Balance, pairs and split met. **2,000 missed**, so ADR-0006 D8 applies (report as unmet). | All four met **if** the estimate holds. Otherwise D8 applies. | Pairs and balance met. The "20% test" holds by scenario but is ≈ 5–20% by record count, so it needs explaining. |
| Rule changes needed (prospective ADR) | None | Replace SD2 with cap 12. Retire SD1 for production (it measures expansion against priors, and production re-uses known scenarios). Keep D5; variation must come from axes D5 does not mask. | New tier field and data-card rules; SD2 applies to the evaluation tier only |
| Complexity | Lowest | Low: one dataset, one rule | Highest: two tiers, two counts, separate training and testing procedures for M2 |

## 4. Recommendation: Protocol B, with A as a pre-registered sensitivity subset

**Why B.**
- **It is one dataset with one rule.** For an undergraduate research paper that is the
  simplest design that matches the specification as written.
- **The professor anticipates several actions per scenario** and protects against
  memorisation through the scenario-level split. B keeps that split, and makes it stricter by
  grouping on number-masked scenario plus `pair_id`, with the ADR-0006 D9 family-disjoint
  split as a secondary analysis.
- **Within-scenario variation is useful for a probe, not just padding.** Render style, names,
  values and distractor files test whether the probe reads reversibility rather than surface
  form.
- **The cost is honesty about the unit of inference.** The paper reports "N records over K
  scenarios", gives scenario-clustered CIs, and never presents within-scenario variants as
  independent evidence.

**Why the cap is 12.**
- It equals 3 render styles × ≤ 4 surface instantiations per style. It is tied to the
  declared variation axes, **not** tuned to reach 2,000.
- It is frozen before generation. If the dry run yields fewer than 2,000, REQ-DATA-01 is
  reported as unmet (D8) and the cap is **not** raised after the fact.

**Safeguard.** The ≤ 3-per-scenario subset (Protocol A) is a pre-registered sensitivity
analysis for RQ1 and RQ2. If the probe's results differ materially between the full set and
the subset, that difference is itself a finding about scenario memorisation.

**Why not the others.**
- **A** alone is defensible but misses 2,000 by a factor of about 4 and gives a very small
  test set.
- **C** is the cleanest for testing, but adds a second tier, a second count and a "20% test"
  explanation. That is complexity B avoids, because B gets the same protection from the A
  sensitivity subset.

**Prerequisites before any production manifest.** Each is a separate reviewed step:
1. An ADR amending SD1 and SD2 for production as described above.
2. A dry run to measure per-scenario variant yield under D5, and the scenario class mix.
3. The link-flag fix (§5).
4. A decision on ScienceWorld (§6, R1).

**Regenerate, don't pool.** Production should regenerate all records under the new manifest,
not pool historical records. `pilot_v0.1` keeps its original flags, and its gold cannot be
re-marked.

## 5. Prospective fix for the sharing-link partial marker (F1)

The issue: `share_link_family.make_record` writes `PROVISIONAL_PARTIAL` for any P label. Phase
5B's `_finish` instead removes that reason, sets `tier` and `sensitivity_group`, and writes
`meta.partial_definition = scaling_pilot.PARTIAL_RULE` (ADR-0006 D2/D11).

**Fix**, in a later reviewed step:
- **New versions:** bump `GENERATOR_VERSION` and `FAMILY_VERSION` (e.g. `share-link-gen-0.3`)
  and apply the 5B marking. Import `PARTIAL_RULE`; do not copy its text.
- **Document OQ-21 for link tools.** The record currently asserts
  `oq21_alternative_labels_by_horizon: None` ("not applicable to link tools") without
  justification. Before tier G is assigned, that must be either justified in writing with a
  test, or computed.
- **Validator rule:** a production manifest rejects any record that still carries the
  pending-professor reason. Records under the frozen Phase 5E manifest stay readable and
  unchanged.
- **Docs:** add an erratum note to docs/30. The frozen manifest, its sidecar, the spec and the
  42 pilot records are **not** touched, and the pilot stays diagnostic and is never pooled.

## 6. Unresolved risks

- **R1. "From both testbeds" is unmet under every protocol.**
  - ScienceWorld has 0 gold records.
  - ADR-0006 D8 allows relaxing the testbed minimum, but not to zero without a stated
    decision.
  - The options are to admit the 7 candidates through the stopped pipeline, or to lift the
    OQ-50 deferral. Either needs review.
- **R2. The supply estimates are unverified.**
  - 126–177 scenarios and up to 12 variants per scenario are dry-run estimates.
  - The class mix of the new scenarios is unmeasured.
  - Irreversible is the scarcest scenario class (14 of 57), so balance may fail.
- **R3. Small effective test size.**
  - B gives about 25–35 test scenarios. Clustered CIs will be wide whatever the record count.
- **R4. The heuristic canonicaliser.**
  - Coarse and masked scenario ids decide split grouping. Under-merging leaks near-duplicates
    across the split, and over-merging only reduces n.
- **R5. Interpretation risk.**
  - "Target at least 2,000" is our reading of a target, not a quota. The professor may read
    records-per-scenario differently.
  - That cannot be resolved without contact, which is out of scope here.
- **R6. Missed internal targets stay missed.**
  - D4's 28 families (16 legacy plus 1 link mechanism) and the 400–600 ScienceWorld gold are
    missed under every protocol, and must be reported under D8.
- **R7. Link records need an OQ-21 justification** (§5) before any can count as gold.
