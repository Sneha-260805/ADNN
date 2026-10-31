# 31 — Dataset capacity audit (Phase 5F)

**Status.** Audit only. **No production manifest was frozen and no production records were
generated.** The audit found that a defensible ~500-record first batch cannot pass the frozen
diversity gates (§5), so Part 3 stops at this documented blocker, as instructed.

Reproduce with `python scripts/dataset/phase5f_capacity_audit.py`, which writes
`results/phase5f/capacity_audit.json` (git-ignored) in about 15 s. Every number below comes
from that run unless marked as quoted from an earlier document.

## 1. Gold rules used

These follow ADR-0006 D3, the frozen Phase 5B rules and the Phase 5F instruction:

| Dataset | Counted as gold | Not counted |
|---|---|---|
| `pilot_v0.1` (210) | records with **no** provisional reason. The pilot keeps its original flags (ADR-0006 D2). | 66 partials flagged pending-professor; 17 OQ-21-sensitive |
| Phase 5B scaling pilot (240) | `tier == "G"` | 20 tier P (OQ-21) |
| Phase 5E link pilot (42) | **0**: a diagnostic pilot kept separate by decision | all 42. Its 28 partials also carry the obsolete pending-professor flag (§6, finding F1) |
| ScienceWorld | **0 records** | 7 tier-G *candidates* from constructed cases are not dataset records; 3 tier S; 17 unresolved (§3) |

## 2. Existing datasets

| | pilot_v0.1 | Phase 5B | Link pilot | Pooled production gold |
|---|---|---|---|---|
| Total records | 210 | 240 | 42 | — |
| Gold records | **127** | **220** | 0 | **347** |
| Gold classes at h3 (R / P / I) | 81 / 0 / 46 | 89 / 77 / 54 | — (all: 21 / 21 / 0) | 170 / 77 / 100 |
| Distinct coarse scenarios, gold (all records) | 30 (46) | 51 (54) | 0 (42) | **57** |
| Distinct strict scenarios, gold (all records) | 43 (63) | 71 (75) | 0 (42) | 86 |
| Largest number of gold records per coarse scenario | 18 | 18 | — | — |
| Gold keepable at ≤ 3 per coarse scenario (SD2) | 63 | 114 | 0 | **129** |
| Recovery signatures, gold (all records) | 10 (13) | 12 (13) | 0 (5) | 12 |
| Strict minimal pairs, both members gold | 30 (0.47 of gold) | 45 (0.41) | 0 | 75 |
| Provisional / unresolved | 66 pending-partial, 17 OQ-21 | 20 OQ-21 | 28 pending-partial flags | — |

All three datasets together contain 105 distinct coarse scenarios over all records.

**Genuine recovery mechanisms.** The pooled gold covers 12 recovery signatures from the legacy
mechanisms: bin, versioning and backup restore; email undo; payment cancel, two-step cancel and
refund; plus irreversible variants. The link pilot adds one mechanism with 5 signatures, but
none of it counts as gold. As in docs/27, signatures are operational labels, not validated
causal mechanisms.

## 3. ScienceWorld: actual eligible cases

These figures are quoted from docs/25 §3 and docs/26 §6:
- **27** constructed, pre-registered cases:
  - **5** eligible reversible and **2** eligible partial with a certificate-protected residual
    (the burn cases). These are tier-G *candidates*, **not records**.
  - **3** partials whose residual is search-relative (tier S, never gold).
  - **17** unresolved or excluded.
  - **0** eligible irreversible.
- **The stratum is stopped.** The sampler supports 7 distinct physical families where 8 are
  required, and combustion is not sampled. Expansion is deferred (OQ-50).
- **ScienceWorld gold records: 0.** None is counted here.

## 4. Can existing generators produce genuinely different scenarios?

**Method.** Each generator family was drawn 100 times with a fresh seed. The resulting
pair-member and single states were canonicalised (structure only, no records). The test
checks whether they are new against all 492 existing records.

**Legacy sandbox families (f01–f14, n01, n02).**
- **They saturate.** Each family yields 10–17 distinct coarse scenarios after 100 draws (f13:
  46), and the saturation curves flatten by about 25–50 draws.
- **Raw novelty.** 110 coarse scenarios are new against the priors.
- **Number-masked novelty.** Masking every number token in both the draws and the priors
  removes novelty that is only an equality coincidence among sampled values. This is measured
  separately from the 110, not as a subset, and leaves **59** distinct structural shapes that
  are new against the priors.
- **What the 59 are.** **50** are non-pair singles (a family's world combined with one of the
  generic "other" actions) and **9** are pair members. 32 come from one family (f13, refund fee).
- **Behaviour.** One representative per shape was labelled with the oracle. **All 59 are
  gold-eligible**, but **0** show a new recovery signature and **0** a new (labels, signature)
  behaviour. They recombine known mechanisms in new state/action combinations.

**Link families (s01–s03).**
- **With background variation:** 146 / 122 / 124 distinct coarse scenarios per family from 200
  states each, almost all "new".
- **Background-ablated:** the target file plus only the links the action touches. This leaves
  **4 per family and 10 in total** (the absent-history states are shared by s02 and s03), over
  5 recovery signatures.
- **So nearly all link novelty is distractor variation.** That is the mechanical novelty
  docs/30 already declared and the Phase 5F instruction forbids counting.

**ScienceWorld.** No generator can run (§3).

## 5. Feasibility of a ~500-record first batch (the blocker)

| Gate (prospective, docs/27 §6) | Requirement for 500 | Defensible supply | Result |
|---|---|---|---|
| **SD1:** ≥ 50% of gold records in coarse scenarios new against the priors | ≥ 250 novel records | At most 3 per novel scenario (SD2) × (59 legacy structural shapes + 10 link mechanism scenarios) = **≤ 207**, and that already counts behaviour-free recombinations as novel | **Fails by ≥ 43 records** |
| SD1, stricter reading (novel = new recovery behaviour) | ≥ 250 | **0** | Fails by 250 |
| SD2: ≤ 3 records per coarse scenario | ≥ 167 distinct scenarios | 69 novel + up to 105 reused | Passable in count only |
| Minimal pairs ≥ 30% | ≥ 75 strict pairs | Only 9 of the novel shapes are pair members, so pairs would come almost entirely from reused scenarios | Passable only by reuse |
| SD3 = 0 | — | Not measurable without generating | — |

Even under the generous reading, **two of every three records per novel scenario would differ
only in wording or values**. That is exactly what SD2 allows and what the instruction says must
not be presented as genuine diversity.

A 500 batch can only pass by counting either link distractor variation or numeric
coincidences as novelty. Either would manufacture novelty. **So no manifest was frozen and
nothing was generated.**

The most the frozen gates would admit is a batch of about **≤ 414 records** (2 × 207). Its
novel half would carry 0 new recovery behaviours. It is listed as option R4 for a team decision
and was not built.

## 6. Findings

- **F1. The Phase 5E link generator uses the obsolete partial flag.** It writes
  `partial_reversibility_definition_pending_professor`, where Phase 5B uses the ADR-0006 D2
  marker (`partial_definition: team-adopted`, plus `tier` and `sensitivity_group`). The frozen
  pilot is left unchanged. Any production use of `share_link_family` must adopt the D2 fields
  first.
- **F2. Numeric equality relations inflate coarse novelty in parameter-rich families.** f13
  alone produced 46 distinct coarse scenarios (34 of them new) and 32 of the 59 new masked
  shapes, all with known behaviours. For production
  manifests, a number-masked novelty measure should be reported next to SD1.
- **F3. Non-pair singles are the main source of residual legacy novelty** (50 of 59 shapes).
  They contribute no minimal pairs and no new behaviour.

## 7. 2,000 gold: is it achievable?

**Not under the current gates with the current generators.**
- At most 3 records per coarse scenario means 2,000 gold needs **≥ 667 distinct coarse gold
  scenarios**.
- The available total is 57 (pooled gold) + 59 to 110 (legacy recombinations) + 10 (link
  mechanism scenarios) ≈ **126–177**.
- That leaves a **shortfall of about 490–540 distinct scenarios**.
- Scenario-level train/test separation and ≥ 30% pairs are not the binding constraints;
  scenario supply is.

**Shortest defensible routes to 2,000.** All of these need a team decision; none was taken
here.

| Route | What it takes | Yield estimate | Risk |
|---|---|---|---|
| **R1. New sandbox mechanisms** (Candidate B/C in docs/28, and others) | review, then the same spec → diagnostics → freeze cycle as Candidate A | about 10 mechanism-relevant scenarios per mechanism (Candidate A: 10), so **about 50 new mechanisms** for the shortfall | slow, and may still saturate; each mechanism needs brute-force validation |
| **R2. ScienceWorld sampler expansion** (OQ-50) | lift the deferral; add combustion and more task families; run the frozen admission protocol | constructed-case gold rate 7/27 ≈ 26%, but diversity is bounded by about 8 physical families; docs/25 projected 400–600 gold, now unmeasured | R- and P-only; certificate coverage limits P |
| **R3. Redefine the target's unit** (ADR) | decide whether REQ-DATA-01 counts records at ≤ 3 per scenario (current) or reports scenarios and effective sample size separately | removes the scenario shortfall from the record count, but not from the science | must be an explicit, documented decision, never a silent loosening |
| **R4. Honest bounded batch now** | freeze a manifest for at most about 400 records under the current gates, with number-masked novelty reported | ≤ 414 records, 0 new behaviours in the novel half | adds records, not mechanisms |
| **R5. ADR-0006 D8 fallback** | report REQ-DATA-01 as unmet with the achieved gold count and tiers | — | none scientifically; a requirement gap |

**Recommendation.**
- Take **R3 + R5** as the immediate, defensible decision: report effective scenarios next to
  records and accept that 2,000 *independent* scenarios are out of reach.
- In parallel, pursue R1 and R2 only where review confirms genuinely new recovery behaviour.
- R4 is worth doing only if downstream members need more records for pipeline work, labelled
  as recombinations.

## 8. Limitations

- **Coarse, strict and number-masked forms are heuristics**, and recovery signatures are not
  causal mechanisms (docs/27).
- **Dry-run capacity is a lower bound for structure and an upper bound for usefulness.** 100
  draws per family flatten the saturation curves, but rare shapes may exist. Conversely, a
  structurally new shape need not be a useful scenario.
- **The behavioural test labels one representative per masked shape**, not every member.
- **The ScienceWorld figures are quoted**, not re-run (the stratum is stopped).
