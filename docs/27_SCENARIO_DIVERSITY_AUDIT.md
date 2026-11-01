# 27: Scenario-level diversity audit (Phase 5C, Task 1)

- **Status:** audit report (Phase 5C). **No records were generated.** The following are all unchanged:
  - sandbox, dataset, ScienceWorld and prompt code;
  - the frozen Phase 5B manifest;
  - the historical records.
- **Team decisions (2026-11-01):** recorded in §6. No professor approval is claimed. The professor was not contacted.
- **Base:** Phase 5B commit `841ffdb605cf23e9967d52f0e1876081c247a7bc`.
- **Mandate:** OQ-51 (approved): future dataset validation must measure underlying scenario diversity (ADR-0007 P7). OQ-50 remains deferred: no ScienceWorld expansion.
- **Code:**
  - `src/adnn/feasibility/scenario_diversity.py`
  - `scripts/dataset/phase5c_diversity.py`
  - `tests/test_scenario_diversity.py`
- **Output (git-ignored):** `results/phase5c/diversity.json`. The audit is deterministic: two runs produce identical output apart from runtime.
- **Inputs (read-only, checksums verified):**
  - the 210-example pilot, `f66b98ba…` (matches `data/pilot/manifest.json`);
  - the Phase 5B records, `bfd1175f…` (matches its generation report).

## 1. Summary

> **What the numbers are.** The **63** coarse and **95** strict canonical scenarios are heuristic counts. The **13** recovery signatures are operational labels derived from oracle witnesses. **None of them is an independently validated count of causal mechanisms or underlying scenarios** (§2, §5).

- **Phase 5B added no new recovery signature.** All 13 already occur in the 210-example pilot.
- **Reuse:**
  - **Primary measure (coarse):** 208 of 240 Phase 5B records (86.7%) and 188 of 220 gold records reuse a canonical scenario from the pilot. 17 new coarse scenarios.
  - **Sensitivity (strict):** 192 / 240 (80.0%), 174 / 220 gold, 32 new.
- **Correction to the earlier heuristic figure.** Phase 5B reported 213 / 240 using `structure_signature`. That signature over-counts reuse slightly, because it masks every value and so loses equality relations. The coarse form keeps them and finds 208 (§4.3).
- **The scenario counts were checked against the oracle.** Across both datasets, no canonical group contains records with different labels (at any horizon) or different recovery signatures: 0 conflicts at either level. All 23 coarse groups that the strict level splits further behave identically. This consistency check does not validate the canonical forms (§5).
- **The two new families mostly reproduce existing scenarios.** n01's 60-second-window members are canonically identical to existing cancellable-payment scenarios in f09/f12, and n02's are identical to two-step scenarios in f10/f14. Only their short-window (expired) variants are new.

## 2. Identifiers

| Level | Identifier | Definition | Basis | Validated? |
|---|---|---|---|---|
| Recovery signature | `recovery_signature_id` | action tool plus the oracle-evidenced recovery route: the tool sequence of the exact witness, else of the approximate witness, else `none` | stored oracle evidence (`meta.oracle`), relative to D and h = 3 | **No: an operational label, not a causal mechanism** (see below) |
| Canonical scenario: **coarse (primary, provisional)** | `scenario_id(level="coarse")` | full world state plus action. Configuration is kept verbatim. Strings are alpha-renamed, with action arguments first, so equality relations survive and names do not. List order is normalised; clock and counters are dropped. Numbers keep **equality only**. | record `state_struct` and `action_call` | **No: a heuristic** |
| Canonical scenario: strict (sensitivity analysis) | `scenario_id(level="strict")` | as coarse, but keeps the **rank order** of all non-configuration numbers | same | **No: a heuristic** |
| Surface template | `template` | the surface-masked text signature (`composition.template_signature`, as in ADR-0006 D5) | rendered text | measures text only |
| Surface variant | `surface` | hash of the exact task, state and action text | rendered text | measures text only |

**Recovery signatures are not mechanisms.** Following the team decision (§6, item 4), these are **not** treated as distinct causal mechanisms:
- action tool names;
- recovery-route names;
- the absence of a recovery path.

Two signatures may share a cause, such as a time window governing both cancellation routes. One signature may cover several causes: every irreversible transfer is `transfer_money|none`, whether the cause is final mode, an expired window or something else. Routes come from the oracle's first witness, and alternative witnesses of equal depth are not enumerated.

The generator's `template_id` (the declared family) and `scenario_id` (a provenance slot such as `sp-f02-00`) are kept as provenance. They are **not** used as identity across datasets, because families share scenarios (§4.4).

## 3. Counts

**Note on pilot gold.** The 210-example pilot predates the tier field. Its gold status is **approximated** as `label_provisional == False` (127 records). Phase 5B gold is `tier == "G"` (220 records).

| | 210-example pilot | Phase 5B (240) | Phase 5B gold (220) | Pooled (450) |
|---|---|---|---|---|
| Recovery signatures (operational) | 13 | 13 | 13 | 13 |
| Canonical scenarios, coarse (primary) | 46 | 54 | 51 | 63 |
| Canonical scenarios, strict (sensitivity) | 63 | 75 | n/a | 95 |
| Surface templates | 161 | 183 | n/a | 324 (see docs/26 §4.3) |
| Surface variants | 210 | 240 | 220 | 450 |
| Largest number of records per coarse scenario | 23 | 18 | 18 | |
| Coarse scenarios with more than 3 records | 20 | n/a | 27 | |

**Recovery signatures by class (operational, descriptive):**

| Class | Signatures |
|---|---|
| Reversible (7) | `delete_file` recovered by `restore_file` or by `restore_backup`; `edit_file` recovered by `restore_backup`; `send_email` recovered by `unsend_email`; `transfer_money` recovered by `cancel_transfer`, by `request_cancellation` then `confirm_cancellation`, or by a reverse `transfer_money` |
| Partial (2) | `edit_file` approximated by `revert_file`; `transfer_money` approximated by `request_refund` |
| Irreversible (4) | one per action tool (route `none`). This says nothing about cause. |

**Phase 5B per family:** records and distinct coarse scenarios per class (R / P / I):

| Family | R | P | I |
|---|---|---|---|
| f02 | 7 / 3 | 6 / 3 | 7 / 2 |
| f03 | 7 / 2 | 6 / 3 | 7 / 2 |
| f04 | 4 / 2 | 10 / 2 | 6 / 1 |
| f06 | 9 / 3 | 2 / 1 | 9 / 2 |
| f07 | 9 / 3 | 6 / 3 | 5 / 1 |
| f08 | 9 / 3 | 6 / 3 | 5 / 1 |
| f10 | 9 / 3 | 4 / 2 | 7 / 1 |
| f11 | 4 / 2 | 9 / 4 | 7 / 2 |
| f12 | 9 / 3 | 11 / 3 | none |
| f13 | 4 / 3 | 9 / 3 | 7 / 4 |
| n01 | 9 / 3 | 4 / 2 | 7 / 1 |
| n02 | 9 / 3 | 4 / 2 | 7 / 1 |

A family produces about 1–4 distinct coarse scenarios per class, however many records it emits.

## 4. Reuse

### 4.1 Cross-dataset (Phase 5B against the pilot)

| Identifier | Phase 5B records reusing a pilot id | Gold records reusing one | New ids |
|---|---|---|---|
| Recovery signature | 240 (100%) | 220 | **0** |
| **Scenario, coarse (primary)** | **208 (86.7%)** | **188** | **17** |
| Scenario, strict (sensitivity) | 192 (80.0%) | 174 | 32 |
| Surface template | 29 (12.1%) | 27 | 163 |
| Surface variant | 0 | 0 | 240 |

The gap between template reuse (12%) and scenario reuse (87%) is what the original stop conditions measured, and why they missed the repetition (ADR-0007 P6a). New surface text was produced for scenarios that were not new.

### 4.2 Where the 32 coarse-novel Phase 5B records come from

- **n01/n02, 20 records:**
  - expired-window pair members (I): 10;
  - non-pair records: 10.
- **Existing families, 12 records:** scattered non-pair records plus three pair members. These are f11 (P and I members of one scenario) and f13 (one I member).

### 4.3 Comparison with the Phase 5B heuristic

- `structure_signature` reports 213 reused; the coarse canonical form reports 208.
- The 5 records the heuristic over-counts (e.g. `sp-f11_pay_refund_vs_final-02-pa/pb`, `sp-f02_delete_backup_fresh-02-s1`) differ from every pilot scenario only in an **equality relation**, such as whether a backup's content equals the current file. That relation is erased when every value is masked.
- The test `test_equality_relations_separate_scenarios_the_old_heuristic_merges` pins this case.

### 4.4 Within-dataset and cross-family reuse

- **Within Phase 5B gold:** 51 coarse scenarios over 220 records. 205 records sit in repeated scenarios, and 27 scenarios exceed 3 records.
- **Pooled:** 37 strict scenarios (310 records) are realised by more than one declared family. Examples:
  - f04 + f06 (6 scenarios);
  - f07 + f08 (4);
  - f09 + f12 + n01 (3);
  - f10 + f14 + n02 (3).
- Some non-pair records in up to six families are the same scenario: a generic action in a world whose configuration equals the default.
- Families are therefore not independent units of diversity.

### 4.5 Duplicate examples (from `diversity.json`)

- **Same strict scenario, different surface:**
  - `sp-f02_delete_backup_fresh-00-pa` (deletes `/home/user/docs/meeting_minutes.txt`) and pilot `sbx-f02_delete_backup_fresh-00-pa` (deletes `/home/user/finance/plan.txt`): both reversible, same state shape, different paths and contents.
- **Same coarse but not strict** (numeric order differs, behaviour identical):
  - `sp-f02_delete_backup_fresh-01-s0` transfers 15 from `checking`;
  - pilot `sbx-f02_delete_backup_fresh-01-s` transfers 10 from `daily`.
  - Both are partial via `request_refund`.

## 5. Uncertainty

- **Strict versus coarse.**
  - Pooled: 95 strict against 63 coarse.
  - 23 coarse groups are split by numeric order, and all 23 are behaviourally identical (same labels at h = 1–3, same recovery signature). The strict splits seen here therefore look cosmetic, which is why coarse is primary.
  - Over-merging at the coarse level is detectable only when behaviour differs. There are 0 such conflicts.
  - Two scenarios that behave identically on these records but would diverge elsewhere (e.g. at a longer horizon or in a wider domain) would go unnoticed.
- **Behavioural consistency is weak evidence.**
  - The conflict check compares labels and recovery signatures, which are themselves coarse.
  - Zero conflicts means the canonicaliser never merged records the oracle tells apart. It does not mean the canonical scenarios are the "true" underlying scenarios.
- **Isomorphism.** List normalisation sorts elements by a masked skeleton. Two structurally identical worlds whose lists tie on that skeleton but are renamed differently could get different ids, which would undercount reuse. This is covered only by a list-reversal test. It is not measured on the data and not proven.
- **Recovery-signature granularity:** see §2. These signatures under-resolve irreversible cases and may over-resolve reversible ones.
- **Pilot gold is approximated** (§3 note).

## 6. Team decisions and prospective gates (2026-11-01)

The research team decided the following. No professor approval is claimed.

1. **Coarse canonical scenarios are the PRIMARY provisional diversity measure.** Strict canonical scenarios are reported as a sensitivity analysis. Neither is ground truth.
2. **SD1–SD3 are accepted as prospective gates for the NEXT expansion pilot.** They take effect only when frozen in that pilot's manifest, before any record is generated. **They do not apply to Phase 5B**, which ran without them and is neither passed nor failed by them. The frozen Phase 5B manifest is unchanged.
3. **SD4 (mechanisms per class) is deferred** until an explicit, auditable mechanism taxonomy and irreversibility-cause representation exist.
4. **Action tool names, recovery-route names and missing recovery paths are not equated with distinct causal mechanisms** (§2).
5. **New partial-reversibility mechanisms are a design priority**, without forcing labels or class balance.
6. OQ-50 remains deferred: no ScienceWorld expansion.

**Prospective gates for the next expansion pilot:**

| Id | Gate (halts generation for review) | Threshold | Phase 5B: descriptive only, NOT a pass or fail |
|---|---|---|---|
| SD1 | Share of gold records whose coarse scenario is absent from all prior datasets | ≥ 0.50 | 0.145 |
| SD2 | Largest number of gold records per coarse scenario | ≤ 3 | 18 |
| SD3 | Behaviourally conflicting canonical groups (coarse level, pooled with prior datasets; subsumes strict-level conflicts) | 0 | 0 |
| SD4 | (deferred) | n/a | descriptive only: 7 R / 2 P / 4 I recovery signatures |

Notes:
- SD1 is measured at the record level, against the prior datasets given to the audit. The next manifest must list those datasets explicitly.
- `prospective_gate_values` returns descriptive values only, with no pass or fail. Tests assert that it reports no verdict and no SD4 value.

## 7. Recommended next action

Before any new family is built under OQ-49:
1. Freeze SD1–SD3 and the list of prior datasets in the next manifest.
2. Require each proposed family to show, by a dry-run canonicalisation of its planned states (no generation), that it contributes coarse scenarios new against the pooled 63. Under that check, n01/n02 would have been flagged at design time.
3. Prioritise genuinely new partial-reversibility mechanisms. There are currently 2 partial recovery signatures (revert, refund). Do not force labels or class balance.
4. Draft the mechanism taxonomy and irreversibility-cause representation that SD4 needs, as a separate reviewed step.

## 8. Tests and runtime

- `tests/test_scenario_diversity.py`: 10 tests covering:
  - a changed filename (same scenario, different surface);
  - a changed list order;
  - changed amounts (same when order is preserved; a strict-only split when amount exceeds balance);
  - changed wording (same scenario, different template);
  - different configuration (different scenario and recovery signature);
  - a different action tool and a two-step route;
  - the approximate-route fallback;
  - the equality-relation refinement over the old heuristic;
  - cross-dataset reuse, gold counting, conflict detection and SD3;
  - the descriptive-only gate output with SD4 deferred;
  - determinism.
- The audit runs in about 0.15 s over 450 records.
