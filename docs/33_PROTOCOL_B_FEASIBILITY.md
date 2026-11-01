# 33 — Protocol B feasibility and production readiness (Phase 5G)

**Verdict: NO-GO for production generation.**
- At the proposed cap, the existing generators yield **1,687** gold records, but only **17%**
  of them are in strict minimal pairs.
- Meeting the professor's ≥ 30% pairs requirement together with the 8% family cap allows **at
  most 966 records**.
- No production manifest was frozen and no record was written.

**Reproduce.** Run `python scripts/dataset/phase5g_protocol_b_dryrun.py`. It takes about 4–6
minutes and writes only `results/phase5g/dryrun.json`, which is git-ignored. Two runs gave the
same determinism hash, `bf120eb5…`.

**Decision record.** ADR-0008 (status *Proposed*).

## 1. Dry-run design

**Draws.** 300 deterministic draws per family:
- the 16 legacy families, each giving its minimal pair plus the two Phase 5B non-pair actions;
- the 3 link families, with background removed (one file, no distractor links).

**Admission.**
- At most 4 gold surface variants per coarse scenario, each rendered in all 3 styles, which
  gives the cap of 12.
- Pairs are admitted atomically.
- Gold uses the established rules:
  - pilot rule for legacy families;
  - `gold_gate` plus a computed, unchanged OQ-21 alternative for link families.
- ADR-0006 D5 (≤ 3 per template signature) is applied.
- All text is rendered with prompt builder 1.1.0, so that one manifest could hold both legacy
  and link records.

## 2. Measured yield (Protocol B, cap 12)

| Quantity | Value |
|---|---|
| Gold surface variants (units) | 641 |
| Records (after D5: 236 dropped) | **1,687** |
| Scenarios: strict / coarse / number-masked | 225 / 182 / 139 (54 coarse already in the priors) |
| Effective number-masked scenarios (inverse Simpson) | 112; top 10 hold 16.5% of records |
| Coarse scenarios at the full 12 | 98 of 182; the rest hold 3–11 |
| h3 classes R / P / I | 810 / 627 / 250 = **48% / 37% / 15%** |
| Strict minimal pairs (ADR-0006 D6) | 145 pairs = **17.2%** of records |
| Recovery signatures | 16 |
| Largest family share | **28.8%** (f13 refund fee, 486 records); the D5 8% cap leaves 1,004 |
| **Largest total with ≥ 30% strict pairs and ≤ 8% per family** | **966** (I 17%, P 38%, R 45%) |
| ≤ 3 sensitivity subset | 525 records, 175 coarse scenarios, 17% pairs, I 14% |

**Where the shortfall comes from.**
- **Pairs are the binding constraint.** Each family's minimal pair has only a few coarse
  shapes, because the pivot fixes the structure. The cap therefore admits about 4 pairs per
  shape: 290 pair records across 13 families. Volume comes from non-pair actions.
- **Families with little or nothing:**
  - `s03` adds nothing, because its "absent" member shares a coarse scenario with `s02`.
  - `f12` adds nothing beyond f09 and f11, because it builds the same worlds.
  - `f11` and `f14` add 15 and 9 records.
- **Class imbalance.** Irreversible is under-supplied (15%), so balanced accuracy is required.

## 3. Render styles and surface variants

**Implemented.**
- Three styles exist (`kv`, `prose`, `compact`).
- Surface values (paths, names, contents, amounts) vary through `sample_params`.

**Not implemented.**
- Existing generators render **one** style per scenario.
- `compact` is reserved for test families (`TEST_ONLY_STYLES`, enforced by the validator).
- "3 styles × 4 variants" is therefore a new generation scheme, not an existing one.

**Labels across styles.**
- Labels depend only on `(state_struct, action)`, and every style is a deterministic render of
  the state.
- The class counts per style are identical, apart from D5 drops.
- In every style, both members of all 60 pairs render to **different** text, so the pivot is
  never invisible.

**Labels across surface variants: violated in f13.**
- **3 coarse groups** contain variants labelled irreversible (no recovery) and others labelled
  partially reversible (refund route). 2 of them conflict even at the strict level.
- Every conflicting group is in `f13_pay_refund_fee`. Its label depends on arithmetic over
  sampled amounts, which neither canonical form captures.
- The labels themselves are oracle-correct. What breaks is the *grouping*. This violates SD3,
  which ADR-0008 keeps.
- **f13 must be excluded, or given a canonical form that encodes the fee arithmetic, before
  any production use.** Since f13 supplies 29% of the records, this lowers yield further.

## 4. 20% record-level split, keeping groups together

| Grouping | Groups (largest share) | Styles | Test records (fraction) | Test fraction of each class (I / P / R) | Test scenarios: coarse / masked |
|---|---|---|---|---|---|
| Number-masked scenario ∪ pair | 123 (11.7%) | all 3 everywhere | **344 / 1,687 (20.4%)** | 0.20 / 0.21 / 0.20 | 36 / 30 |
| Number-masked scenario ∪ pair | 123 (11.7%) | `compact` test-only | 245 / 1,206 (20.3%) | 0.20 / 0.19 / **0.10** | 27 / 23 |
| Family ∪ masked (ADR-0006 D9) | 5 (75%) | all 3 | 341 (20.2%) | **0.09** / 0.22 / 0.22 | 36 / 25 |

**Interpretation.**
- **A stratified scenario-grouped split is feasible**, but with all styles in training it is
  only about 30 test scenarios. Keeping `compact` test-only cuts training by a third and
  unbalances the test classes.
- **A family-disjoint split is not meaningful.** The generic non-pair actions join the families
  through shared masked shapes, leaving 5 groups, one of which holds 75% of records.
- **Code gap:** the current validator and API support only family-held-out splits. A grouped
  split needs code support first.

## 5. Sharing-link metadata (fixed prospectively)

**New module:** `adnn.dataset.share_link_production` (`share-link-gen-0.3`). It reuses
`scaling_pilot.PARTIAL_RULE` and the `PROVISIONAL_*` constants, and sets `tier` and
`sensitivity_group`.

**OQ-21.**
- **It is now computed:** pre-action contents and addresses are added to the pool, as in docs/29
  §7.4.
- **Result: 0 label changes in 32 link variants.** A non-definitive alternative drops the
  pair.

**Validator.**
- A manifest-declared `partial_definition_policy: "team-adopted (ADR-0006 D2)"` makes the
  validator require:
  - the tier fields;
  - the rule text;
  - a computed OQ-21 alternative for link tools;
  - tiers consistent with OQ-21.
- It also forbids the pending-professor flag.
- Without the key, nothing changes. The default schema already rejected `tier`, which means
  Phase 5B-style records could not have passed the old validator.

**Frozen artifacts.** These are untouched: the pilot generator, the frozen manifest, its
sidecar and the 42 records. docs/30 §15 records the erratum.

## 6. ScienceWorld: the 7 eligible candidates

| Candidate | `sw-admission-2` | R5 replication + query-order audit | Symmetry (D7) | Rubric sensitivity (R7) |
|---|---|---|---|---|
| h4-open-fridge, h4-move-cup-to-table, h4-connect-battery-wire (R) | eligible | **yes** (phase4h `comparison.json`, `measurement_audit.json`) | yes | yes |
| h4-burn-painting-water-near, h4-burn-chair-water-near (P, C-BURN) | eligible | **yes** | yes | yes |
| ctrl-open-cupboard, registry-miss-connect-v2 (R; Phase 4G) | eligible | **no** (re-collected only in the 5A symmetry run) | yes | **no** |

**Five candidates meet every tier-G evidence requirement. None is a dataset record**, because
no ScienceWorld record exporter exists. `provisional.build_record` writes evidence documents,
not `state_text` / `action_text` records.

**Smallest concrete steps** (each reviewed separately; the pinned runtime is installed):
1. **Run R5 and R7 for the two Phase 4G cases**, or exclude them. The steps:
   - R5: a second fresh-process collection and the query-order audit;
   - R7: the rubric declaration check.
2. **Write a ScienceWorld record exporter** (prompt builder 1.1.0) covering:
   - `state_text` from the replayed S0 observation;
   - `action_text`;
   - `source: scienceworld_bfs`;
   - `tier`;
   - per-horizon labels.

   Below the witness depth, the h1/h2 labels are **unresolved** (search failure is not
   irreversibility). Those horizons must be marked, not filled.
3. **Freeze a small ScienceWorld manifest:** the case list, the evidence file hashes, and
   `sw-admission-2`. Then generate and validate.

**What this yields.**
- At most **7 records over 7 scenarios**: 5 R and 2 certificate-backed P, 0.4–0.7% of a
  dataset of 966–1,687 records.
- "From both testbeds" is then met only nominally.
- A meaningful ScienceWorld share still needs the sampler expansion (OQ-50; docs/26 §6).

## 7. GO / NO-GO

**NO-GO for production generation.** Blocking findings, all measured:
1. **Minimal pairs.** Pairs are 17% at full yield. Meeting the professor's ≥ 30% caps the
   dataset at 966 records, which is 1,034 short of 2,000. The cap was not raised.
2. **SD3 fails in f13.** Within-scenario label conflicts appear in the family that supplies 29%
   of records.
3. **Infrastructure is missing:**
   - grouped-split support in the validator and API;
   - the 3-style generation scheme;
   - a decision on the `compact` test-only rule;
   - legacy rendering with builder 1.1.0;
   - a ScienceWorld record exporter.
4. **ScienceWorld:** 5 candidates are ready in evidence but 0 records exist, and 2 candidates
   still lack R5/R7.

**Shortest route to a GO** (team decisions first):
1. Exclude f13, or re-canonicalise it, and re-run the dry run.
2. Decide the `compact` rule.
3. Either add new **pair** families (design work; pairs are now the binding resource), or
   accept a dataset of about 900–1,000 records with ≥ 30% pairs and report REQ-DATA-01 as
   unmet (ADR-0006 D8).
4. Implement grouped splits and the ScienceWorld exporter.
5. Re-run this dry run as the ADR-0008 B5 gate before freezing.
