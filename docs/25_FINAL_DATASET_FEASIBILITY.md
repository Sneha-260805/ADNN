# 25: Final dataset feasibility and quality design (Phase 5A)

- **Status:** design report (Phase 5A). **No dataset is generated here.** The 210-example pilot, prompt builder 1.0.0 and the shared dataset API are unchanged. **No professor approval is claimed and the professor was not contacted.**
- **Base:** Phase 4H commit `0ddcf645e8b8115f60da0658ec0ddd67b58ed694`, rule `sw-admission-2`.
- **Decision record:** `docs/decisions/0006-final-dataset-design.md`.
- **Code:**
  - `src/adnn/feasibility/pilot_audit.py`
  - `src/adnn/feasibility/composition.py`
  - `src/adnn/scienceworld/measurement_symmetry.py`
  - `scripts/scienceworld/phase5a_symmetry.py`
- **Results (git-ignored):** `results/phase5a/`.
- **Evidence tags:**
  - [RUN] measured here;
  - [PILOT] measured on the pilot (read-only);
  - [DEC] team decision;
  - [EST] estimate with stated basis.

## 1. Summary

| Target | Assessment |
|---|---|
| ≥2,000 labelled examples across both testbeds (REQ-DATA-01) | **Projected achievable, not demonstrated.** This is a projection from the 210-example pilot and 27 constructed ScienceWorld cases, mainly from the sandbox. Sandbox labels are justified by an exhaustive bounded search, and generation is cheap. No yield at scale has been measured; the scaling pilot (§9) is the test. |
| Roughly balanced testbed representation (OQ-10: ≥1,200 sandbox / ≥800 ScienceWorld) | **At risk for ScienceWorld.** About 19% of constructed cases become eligible reversible, about 19% eligible partial and 0% irreversible. Diversity concentrates on a few verbs. Planned: 1,400–1,600 sandbox and 400–600 ScienceWorld, with the ScienceWorld number set by measured yield. A 1,000/1,000 split is not supported. |
| Three classes preserved across the combined dataset (REQ-DATA-02) | **Achievable.** The sandbox supplies all irreversible examples (OQ-46, ADR-0005 R9). ScienceWorld is reversible/partial only. Balance is reported per environment, and is not forced in ScienceWorld. |
| ≥30% genuine minimal pairs (REQ-DATA-05, strict definition) | **Achievable overall, from the sandbox.** Under the strict definition (byte-identical action and different *justified* labels), the pilot reaches 28.6% if every provisional label is excluded. Once the sandbox partial definition is adopted by the team (ADR-0006 D2) and OQ-21-sensitive records are excluded, it reaches 52.4%. Strict ScienceWorld pairs are expected to be close to 0. |
| Family-disjoint splits without leakage | **Achievable with more families.** The pilot is family-disjoint with no exact overlap. Its 3 held-out families give only 45 test examples, so the final dataset needs at least 28 sandbox families. |
| Human label reliability (REQ-LBL-05) | **Not yet available.** A protocol is defined. No annotator, κ or agreement score exists or is reported. |

## 2. Custom-sandbox pilot audit [PILOT] [RUN]

`pilot_audit.audit` reads `data/pilot/pilot_v0.1.jsonl`. Its SHA-256 `f66b98ba…` was identical before and after the audit. For each record the audit:
1. re-runs the oracle from `state_struct`;
2. replays each witness independently of the search;
3. classifies what the evidence establishes (runtime 473 s).

| Label | n | Support | Meaning |
|---|---|---|---|
| reversible | 81 | **verified exact witness** (81/81) | A concrete sequence of ≤3 tool calls returns the canonical state. This is a constructive proof relative to the sandbox rules. |
| partially reversible | 66 | **verified approximate witness, plus a complete search with no exact restoration ≤3** (66/66) | Core projection restored, and exact restoration excluded by exhaustive search over D. |
| irreversible | 63 | **complete bounded impossibility** (63/63) | Exhaustive search over D to depth 3 found neither an exact nor an approximate restoration. |

**All 210 stored labels re-derive.** All 210 searches were complete, and no budget was exhausted.

**What "complete" means:** an exhaustive argument relative to three things:
1. the sandbox transition rules (`tools.step`);
2. the action domain D (every permitted tool over its argument domain, with free values drawn from the post-action argument pool);
3. horizon 3.

This matches the spec's horizon-relative label definition (spec §4.2). It is not a claim about irreversibility beyond the horizon, or about actions outside D.

**Provisional labels and unresolved assumptions:**

| Assumption | Records affected | Status |
|---|---|---|
| Sandbox partial definition (core projection with refund fees added back; ENG-15) | 66 (every partial label) | Flagged `partial_reversibility_definition_pending_professor`. ADR-0006 D2 proposes adopting it as a **team** decision for the final dataset. The pilot records keep their flag. |
| OQ-21 information rule (restoration may not use pre-action text) | 17 irreversible labels (12 `edit_file`, 5 `delete_file`) | Each would become `partially_reversible` under the alternative reading. They stay provisional. |
| OQ-24 action domain (no email-field recombination; amounts only from payments) | 0 | **Measured:** a widened pool (positive balances, pairwise sums of amounts, recombined email fields) changed **0 of 129** non-reversible labels. The assumption is not label-relevant in the pilot. Only this specific widening was tested. |
| OQ-23 wait semantics (failed calls cost time) | not measured | It matters for undo windows, e.g. f08 (one-step window). It remains a documented default. |
| OQ-22 pending timers before the action | 0 | Excluded by generation. |

**Result:** 127 of 210 labels (81 R, 46 I, 0 P) are fully supported and non-provisional today. With D2 adopted, the 66 partials join them, giving 193 of 210. The remaining 17 OQ-21-sensitive labels stay provisional.

**Other pilot findings** (they inform the design, and the pilot is not changed):
- **Template duplication:** 161 distinct surface-masked signatures for 210 records (an effective fraction of 0.77). 10 signatures recur across scenarios.
- **Verb shortcut:** on the test families, the per-verb majority label gives 0.47 accuracy, equal to the test majority-class rate (0.47). There is no lexical advantage over the majority baseline in this split, but per-family label skew exists (docs/13 §8).

## 3. ScienceWorld label audit (`sw-admission-2`, plantless claim NOT registered) [RUN]

Phases 4G and 4H pooled: 27 constructed, pre-registered cases.

| Outcome | n | Cases |
|---|---|---|
| eligible reversible | 5 | ctrl-open-cupboard, registry-miss-connect-v2, h4-open-fridge, h4-move-cup-to-table, h4-connect-battery-wire |
| eligible partially reversible | 5 | partial-pot-into-active-sink, partial-stove-heats-pot, partial-cup-in-active-sink, h4-burn-painting, h4-burn-chair |
| eligible irreversible | **0** | — |
| unresolved / excluded | 17 | kept separately; never relabelled (search failures are not irreversibility) |

**Justification tiers (ADR-0006 D3):**
- **ScienceWorld reversible:** a replayed restoration witness proves restorability within the horizon. These labels are **fully justified**, given exact canonical comparison against the time-matched counterfactual, stability across tolerances, replication and measurement-symmetry stability.
- **ScienceWorld partial:** the witness proves the meaningful part. "Not exactly restorable" is **search-relative**: there is no complete search. The exception is where a certificate protects the residual. **Only the two burn cases** are certificate-backed, through the `hasCombusted` residual under C-BURN. So **3 of 5 partials are search-relative classifications, not fully justified gold**.

| ScienceWorld candidate group | n | Cases | Tier |
|---|---|---|---|
| Eligible reversible (witness-proven) | **5** | ctrl-open-cupboard, registry-miss-connect-v2, h4-open-fridge, h4-move-cup-to-table, h4-connect-battery-wire | G candidates |
| Eligible partial, certificate-supported residual | **2** | h4-burn-painting-water-near, h4-burn-chair-water-near (C-BURN `hasCombusted`) | G candidates |
| Eligible partial, search-relative residual | **3** | partial-pot-into-active-sink, partial-stove-heats-pot, partial-cup-in-active-sink | S (not gold) |

These are candidates from constructed validation cases, not gold labels.
- The unregistered plantless claim and the Phase 4E provisional records (35, `sw-evidence-0.1`) are excluded from this audit and are not labels.

## 4. Measurement symmetry [RUN]

**Protocols compared.**
- **Frozen asymmetric protocol (ADR-0003 D8):** the attempt branch enumerates valid actions after the target. The counterfactual branch only rebuilds and idles.
- **Symmetric variant (`measurement_symmetry.SymmetricRun`):** the counterfactual also enumerates valid actions at the same tick offset (after the target's ticks), then idles the rest.
- For every counterfactual, the variant records the hash of both states, so transitions are compared directly.

`scripts/scienceworld/phase5a_symmetry.py` collected all 27 Phase 4G/4H cases twice in fresh sessions, once per protocol, and decided both runs under `sw-admission-2`. The output is in `results/phase5a/symmetry_summary.json`. Frozen 4G/4H results were not read for decisions and not overwritten.

| Check | Result |
|---|---|
| Counterfactual state identical under both protocols (every enumerated counterfactual; 1–2 per case) | **25/25 cases with complete evidence** |
| Per-attempt levels and concepts at all tolerances identical | 25/25 |
| Admission outcome and witness identical | **27/27** (the 2 incomplete cases fail identically: binding failure, invalid target) |
| Cases affected → quarantined | **0** |

**Scope and caveats:**
- The check covers one enumeration, placed after the target's ticks, before at most one recovery step (all attempts here are single-step), in 27 constructed cases.
- **The bee-hive case is unaffected only because the counterfactual never opens the hive.** Bees inside a closed hive draw no random numbers. Phase 4F showed that enumeration *does* change bee transitions once the hive is open, which is the attempt branch. That exposure is handled by the stochastic gate (the case is excluded for that reason), not by symmetry.
- **For deterministic cases, the asymmetry did not change any transition or outcome.** It remains a protocol property to check for every new candidate (ADR-0006 D7). The result does not generalise to stochastic or ambiguous-referent states.

## 5. Final dataset composition [DEC proposal] [EST]

The target is ≥2,000 examples whose labels meet the gold tier (§8), with search-relative ScienceWorld partials reported **separately**. They are not counted toward 2,000 unless the team accepts the weaker tier for that use.

| Testbed | Target | Classes | Basis | Achievable? |
|---|---|---|---|---|
| Sandbox | 1,400–1,600 | roughly ⅓ R / ⅓ P / ⅓ I by family quotas | Exhaustive bounded search; the pilot generated 210 in about 40 s; 0 dropped | **Yes**, once the family count rises from 14 to at least 28 (new domains need design and brute-force verification) |
| ScienceWorld | 400–600 gold (R plus certificate-backed P), plus search-relative P separately | R-heavy; P mostly search-relative; I = 0 | Constructed-case yield of 5/27 R and 2/27 certificate-backed P; distinct templates are few (open/close, move, connect, device toggles, combustion) | **Uncertain**: about 2,000–3,000 candidates would be needed at measured yield. The binding constraint is diversity, not compute (§9). |
| **Combined** | **≥2,000** | I ≥ 25% overall is reachable only through the sandbox | | **Projected yes** for the count (not demonstrated); **at risk** for testbed balance |

**Rules (ADR-0006 D4):**
1. Each sandbox family has one action and one documented pivot. It is verified by brute force before inclusion, and the oracle's labels are asserted against the design.
2. ScienceWorld examples come only from cases that pass `sw-admission-2`, two-process replication, the symmetric-protocol check and the rubric-sensitivity check.
3. **Independence:** the unit of independence is the surface-masked template signature (`composition.template_signature`). Per family and per signature, counts are capped (ADR-0006 D5). Re-sampled names, paths and amounts within one template do not count as new templates in diversity reporting.
4. No up-sampling, duplication or re-declaration to reach balance.

## 6. Minimal-pair feasibility

**Strict definition (ADR-0006 D6):**
- same `scenario_id`;
- byte-identical `action_text`;
- at least two distinct labels;
- every member's label justified (gold tier).

Different immediate effects alone do not qualify. `composition.minimal_pairs` implements this.

| Pilot measurement [PILOT] | Genuine member fraction |
|---|---|
| Any pair group (generator's definition) | 0.667 |
| Strict, excluding all provisional labels (today) | **0.286** |
| Strict, partial definition adopted (D2), excluding OQ-21-sensitive | **0.524** |

Pilot pair label types: 40 R/I, 15 P/I, 15 R/P.

**Projection [EST]:**
- With the pilot's design (one pair and one non-pair per scenario) and the same rate of OQ-21 sensitivity, a 1,500-example sandbox gives about 785 strict pair members.
- With ScienceWorld contributing about 0 strict pairs, that is about 39% of 2,000. **≥30% is projected to be achievable from the sandbox alone** (not yet demonstrated).
- The ScienceWorld fraction is reported separately and is expected to be about 0–5%. A strict ScienceWorld pair needs both states' labels justified. R-versus-search-relative-P contrasts (Phase 4F: 10 restoration-contrast candidates) do not qualify.

## 7. Splits, class balance and leakage

**Splits:**
- **Primary split for generalisation claims [DEC proposal]:** family-disjoint (template-held-out).
- **Required split (REQ-DATA-03):** scenario-level. It is kept and reported, with three frozen seeds (REQ-STAT-01).
- The pilot's family-disjoint split had:
  - 0 scenario overlap;
  - 0 exact input overlap;
  - 3 normalised-signature overlaps (masked templates shared across families);
  - a verb-majority test accuracy equal to the majority baseline.

**Risks:**
1. **Few families means wide confidence intervals.** 3 test families gave 45 examples in the pilot. With at least 28 families and 20% held out per seed, about 6 families (about 300 examples) are held out per seed.
2. **Per-family label skew.** f05/f12/f14 have no irreversible examples, so held-out family choice changes the test class mix. Splits are stratified by family label profile, with balanced accuracy always reported.
3. **ScienceWorld has no irreversible class**, so ScienceWorld-only metrics are two-class. Cross-environment transfer (REQ-ABL-04) on three classes is **not evaluable** in the sandbox→ScienceWorld direction. Per OQ-48 (ADR-0006 D11), transfer claims are limited to reversible versus **certificate-supported** partial. This is a revised scope that M2 must report.
4. **Lexical cues** (payment-mode names in `kv`/`compact` renderings) are kept as a measured risk. Mitigations: lexical baselines, held-out phrasings and verb-shortcut reporting (`split_leakage`).
5. **ScienceWorld task-description leakage** (OQ-34): ScienceWorld examples are split by task family, never by variation within a task.

## 8. Label reliability and tiers

| Tier | Definition | Use |
|---|---|---|
| **G (gold, fully justified)** | Sandbox: verified witness or complete bounded impossibility over D at h, under the adopted rules, not OQ-21-sensitive. ScienceWorld: eligible reversible, or partial with a certificate-protected residual, that is replicated, symmetric-stable and rubric-stable. | Counted toward 2,000; primary metrics |
| **S (search-relative)** | ScienceWorld eligible partial whose residual is not certificate-protected | Reported separately and flagged; secondary analyses only |
| **P (provisional)** | The label changes under a documented alternative rule (OQ-21) or a pending definition | Kept and flagged; excluded from primary metrics and strict pairs |
| **X (excluded)** | Unresolved, quarantined, non-replicating, measurement-affected | Not in the dataset; counts reported |

**Blinded rubric and human review (protocol only; no annotators exist):**
- **Property declarations (ScienceWorld):** `sw-declaration-rubric-2`, with A1 to A6 resolved as proposed in docs/24 §5.3. It is frozen before any new case. At least two annotators work on the blinded packets (`PHASE4H_ANNOTATOR_PROTOCOL.md`).
- **Adjudication:**
  1. Disagreements are resolved by a third team member using only the rubric text. The rubric is never applied to results.
  2. The adjudicated declaration is pre-registered as a *new* record.
  3. Cases whose outcome differs between the annotators' declarations are excluded from tier G.
- **Labels (REQ-LBL-05):** 100 examples (seed 20261101, at least 30 ScienceWorld), shown as `state_text`, `action_text` and the written label rules only. The plan (docs/05 §10):
  - two annotators;
  - κ between the humans and κ between each human and the automatic label;
  - adjudication;
  - no recomputation after inspection.
- **No human annotation has been done.** No κ, agreement score or annotator is reported or implied.

## 9. Scaling pilot (proposal, not run)

**Sample (about 400 examples or candidates):**

| Stratum | Count | Detail |
|---|---|---|
| Sandbox | 240 | 12 families (6 existing, 2 per domain; 6 new, 2 per new domain) × 5 scenarios × 4 examples (one pair, two non-pair). Target about 80 R / 80 P / 80 I (±15). Pair types R/I, P/I and R/P at least 20 pairs each. |
| ScienceWorld candidates | 160 | 8 action families (container, device, movement, liquid transfer, thermal, combustion, consumption, electrical) × 20. At least 4 task families, never more than 25% from one task. |
| ScienceWorld contrast candidates | 40 | 20 state pairs with byte-identical action text, for strict minimal-pair yield |

**Expected rates [EST, from 4G/4H]:** ScienceWorld:
- about 15–25% eligible R;
- about 10–20% eligible P, of which about 30–40% certificate-backed;
- 0% I;
- 55–70% unresolved or excluded.

Strict ScienceWorld pairs about 0–2. Sandbox: 0% rejection, about 8% OQ-21-provisional.

**Runtime, storage and audit cost [EST]:**

| Item | Cost basis | Estimate |
|---|---|---|
| ScienceWorld evidence plus replication, symmetric check and rubric run | about 2–2.5 min per case (measured 18–42 s per collection) | about 7–8 h single-process for 200 |
| Sandbox generation plus audit | 210 records ≈ 40 s generation, 8 min audit with OQ-24 widening | under 20 min |
| Storage | about 80 KB evidence per run, about 130 KB per symmetric comparison | about 80–100 MB, git-ignored |
| Manual audit | 15 min per ScienceWorld eligible case (all certificate cases and a 20% sample), 5 min per sandbox record (10% sample) | about 8–12 person-hours |
| Human declaration and label study | 2 annotators × (12–20 packets + 100 labels) at about 5 min each | about 10 h per annotator |

**Stop conditions:** each one halts scaling and triggers a review, not a rule change.
1. ScienceWorld gold yield below 10% after 80 candidates.
2. Any replication failure, or more than 2% measurement-affected cases.
3. Rubric sensitivity changing more than 10% of eligible ScienceWorld outcomes.
4. One action family supplying more than 40% of any class in either testbed.
5. A surface-masked effective fraction below 0.6.
6. A strict genuine-pair fraction below 0.30 on the sandbox stratum.
7. Any sandbox label that fails re-derivation.

## 10. Honest fallbacks (ADR-0006 D8)

| If this fails | Fallback | Original target revised |
|---|---|---|
| ScienceWorld gold below 400 | Sandbox about 1,600–1,800 plus all ScienceWorld gold. Report the testbed ratio. | OQ-10 testbed minimum (≥800 ScienceWorld), *not* REQ-DATA-01 |
| Fewer than 2,000 gold overall | Report the gold count. Release tiers S and P separately, labelled as such; never merged. | REQ-DATA-01 is reported as unmet. It is not met by relabelling. |
| Strict pairs below 30% | Report both the strict and the spec's definition ("same action verb, reversibility changes with state"). Add sandbox pair families. | REQ-DATA-05 is reported against the spec definition, with the strict figure alongside it |
| Three-class transfer to ScienceWorld impossible | Report R-versus-P transfer only, both directions | REQ-ABL-04 scope narrowed and documented |
| No human annotators | Report that REQ-LBL-05 is unmet. No automated proxy is presented as human agreement. | REQ-LBL-05 |

No definition is weakened to reach a number. In particular:
- search failure is never irreversibility;
- tier S is never counted as gold without an explicit team decision recorded in an ADR;
- the plantless claim is not used.

## 11. Tests and files

- `tests/test_feasibility.py` (no Java) covers:
  - strict minimal-pair classification, including the byte-identical action, cross-scenario and unjustified-label cases;
  - template masking, duplicates, leakage and the verb-shortcut indicator;
  - pilot-audit support classes on generated sandbox worlds;
  - OQ-24 widening scoping;
  - symmetric-runner scoping and the protocol comparison.
- Gate (2026-10-31): `pytest -q` 595 passed, 37 skipped (no Java); real ScienceWorld integration `-m scienceworld` 37 passed; `ruff check .` and `ruff format --check src tests scripts` clean; pilot SHA-256 unchanged.
