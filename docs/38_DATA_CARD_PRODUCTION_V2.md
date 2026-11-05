# Data card: ADNN production dataset v2.0 (`adnn-dataset-2.0`)

## Summary

- **Purpose.** Each record pairs an agent state with a candidate tool action. The task is to
  label the action **reversible**, **partially reversible** or **irreversible** within a
  recovery horizon h = 1–3; h3 is primary. The task and format are the same as v1.0.
- **Uses.** It serves RQ1 (linear probes on hidden states) and RQ2 (stated judgments).
- **Size.** 2,134 gold records: 2,129 from the tool-use sandbox and 5 from ScienceWorld.
- **Robustness subset.** 707 records, at most 3 per scenario.
- **Report.** Full generation and validation details are in docs/37. v1.0 (621 records,
  docs/35) is unchanged and remains available.

| Path | `data/production/v2.0/` (git-ignored; team bundle or docs/37 §9) |
|---|---|
| Records file sha256 | `d03cd8f38ad4b36ce540409e7b3062e0eb4b457d6916483a3334ebde0acdab73` |
| Frozen manifest | `docs/preregistration/production_manifest_v2_amend1.json` (`432e7344…`); amends `production_manifest_v2.json` (`ed7b24a1…`, kept unchanged) |
| Decision record | ADR-0010, including Amendment 1 |
| Created | 2026-11-03, by Member 1 (sandbox core) |

## What changed from v1.0

- **New action situations (ADR-0010).** Nine families built only from existing sandbox tools
  and settings:
  - restoring from a backup (fresh or stale; after a deletion with the bin on or off);
  - a second edit, deletion or payment after an earlier action;
  - revert or restore after an edit or a deletion.

  They contribute 859 records.
- **Variant cap 6 (Amendment 1).** Up to 6 surface variants per coarse scenario, up from 4.
- **Unchanged from v1.0:**
  - the oracle, the gold rules and the 3-step horizon;
  - the template-signature cap (≤ 3);
  - the 8% family cap and the ≥ 30% minimal-pair floor;
  - the scenario-grouped split and the ScienceWorld records.

## Composition

| | I | P | R | Total |
|---|---|---|---|---|
| Sandbox | 577 | 756 | 796 | 2,129 |
| ScienceWorld | 0 | 2 | 3 | 5 |
| **All** | **577 (27.0%)** | **758 (35.5%)** | **799 (37.4%)** | **2,134** |

- **Sandbox families.** 27 families have records:
  - file delete, edit, restore or revert;
  - email undo;
  - payment cancel, refund, two-step or a second payment;
  - share links.

  No family exceeds 8% of records.
- **Scenarios.** The sandbox covers 183 number-masked scenarios (123.8 effective) and 253
  coarse scenarios.
- **Minimal pairs.** 439 pairs, which is 878 records (41.1%). Within each pair the action text
  is identical, the state differs in one pivot condition, and the gold labels differ.
- **ScienceWorld.** The same 5 hand-audited cases as v1.0, from 2 task families.
- **Render styles.** `kv` 999, `prose` 993 and `compact` 142; `compact` is used only in the
  test set.

## Labels

- **Sandbox.** An exact breadth-first oracle searches for a recovery within h steps.
  - A record is gold only if the search is complete, the judged action succeeds, no timers are
    pending, and the label does not change under the OQ-21 alternative reading.
  - Partial reversibility follows `scaling_pilot.PARTIAL_RULE` (team-adopted, ADR-0006 D11).
- **Earlier actions.** For families with an earlier action, that action is executed in the
  sandbox first. The judged state is the result.
- **Declared depths.** `meta.declared_depths` and `meta.declaration_agrees` are informational
  only. In 28 records (the fresh-backup member of family B1), the single-step design rule
  disagrees with the oracle on the exact restore depth. The oracle finds a valid two-step exact
  restore, so R at h3 is correct. See docs/37 §5.
- **ScienceWorld.** Labels come from the frozen `sw-admission-2` decisions; the records equal
  v1.0's.
- **All dataset labels are automated.** They are simulator (oracle) labels. The human study
  below did not change or replace any label; see *Human agreement*.
- **Not gold.** 26 OQ-21-sensitive records are in `sensitivity_oq21.jsonl`, tier P. They are
  for robustness analysis only.

## Human agreement (REQ-LBL-05)

Full report: docs/43. Added 2026-11-05. The dataset itself is unchanged.

- **Two kinds of label.**
  - **Automated labels** are the dataset's gold labels at h3. The sandbox simulator's exact
    oracle assigns them.
  - **Human labels** were assigned independently by two annotators. The annotators did not see
    the automated labels, the dataset files, the code, or each other's sheets. They worked from
    the shown task, state, action and tool list, using `ANNOTATION_INSTRUCTIONS.md`.

  The human labels are stored only with the study (git-ignored, archived). They are **not**
  part of the dataset.
- **Sample.** **100 minimal pairs (200 examples)**, drawn uniformly at random without
  replacement from the 439 strict minimal pairs, with seed 20261105. The A/B order within each
  pair is random. **All 200 examples are from the sandbox** (none from ScienceWorld). The
  automated labels in the sample are R 74, P 58, I 68.
- **Results.** All figures are independent agreement; no adjudication was done. CIs are 95%
  percentile bootstrap intervals over 1,000 resamples of pairs. No example was excluded,
  because nobody used "cannot decide".

  | Comparison | Cohen's κ (95% CI) | Raw agreement (95% CI) |
  |---|---|---|
  | Human vs human | **0.6206** [0.5059, 0.7288] | **73.5%** [64.5%, 81.5%] |
  | Annotator 1 vs automated | **0.8169** [0.7432, 0.8798] | 88.0% [83.5%, 92.0%] |
  | Annotator 2 vs automated | **0.7339** [0.6428, 0.8214] | 82.0% [75.5%, 88.0%] |

- **Disagreements.** **53** of 200 examples: **51 R/P, 2 P/I, 0 R/I**. All are unresolved.
  - All 51 R/P disagreements are file revision/backup cases (edit with a fresh or stale backup,
    restore from a backup, delete with a backup present). In each, Annotator 1 said R and
    Annotator 2 said P.
  - The other mechanisms (recycle bin, payments, email, share links) account for only 2
    disagreements in 146 examples.
- **Known ambiguity.** The annotation instructions do not state:
  - whether `revert_file` or `restore_backup` keep or advance a file's revision number;
  - that a backup at the file's current revision gives an exact restore;
  - whether restoring a backup creates a previous version;
  - how to treat a refund fee equal to the payment amount.

  These gaps fall exactly on the boundary between exact restoration within 3 actions and
  partial restoration (docs/43 §4).
- **How to read this.**
  - Agreement with the automated labels shows that humans who follow the written instructions
    largely reach the same labels. It **does not prove that the automated labels are
    correct**: the humans also deviate from them in a consistent direction, and the
    instructions are ambiguous where the deviations occur.
  - Human–automated disagreement is not proof of an automated-label error either. No label was
    changed.
  - The sample is 100 pairs from the sandbox only. It says nothing about human agreement on
    ScienceWorld records.
- **Validation note.** Annotator 2's workbook writes `no` (instead of leaving the cell empty)
  in all 200 `uncertain` cells, so strict validation fails (`strict_ok: false`, kept in
  `summary.json`). The analysis uses the approved opt-in `--accept-uncertain-no`, which reads
  only the exact trimmed, case-folded value `no` as "not uncertain" and never reads or changes
  a label. Strict validation remains the default.

## Split

- **Assignment.** A 20% test set is drawn by scenario group. The result is **425 test records
  (19.9%)** in 27 groups, and 1,709 train records in 124 groups.
- **Kept together.** Minimal pairs and surface variants never cross the split.
- **Test classes:** I 153, P 204, R 68. Reversible records are under-represented in test: 16%
  of test, and only 8.5% of R records are in test, against about 26.5% of I and P. Member 1
  accepted this.
- **Families not in test:** A2, B1, B2, B3 and S3.

## Robustness subset

`robustness_subset_le3.json` lists 707 record ids (I 178, P 253, R 276; 580 train and 127
test).
- **Rule:** at most 3 records per coarse scenario, with minimal pairs kept atomic. There are
  136 complete pairs and 0 split pairs.
- **Purpose:** it limits the extra surface variants allowed by the cap of 6.
- **Use:** report main results on both the full dataset and the subset.

## Intended use

- **For:**
  - training and evaluating probes and classifiers on train/test as given;
  - minimal-pair analyses;
  - stated-versus-internal comparisons;
  - robustness checks on the ≤ 3 subset.
- **Reporting:**
  - report per-class results and balanced accuracy or macro-F1, because R is
    under-represented in test;
  - report "N records over K scenarios", because records within a scenario are not
    independent;
  - bootstrap over scenario groups.
- **Not for:**
  - claims about real-world tools or environments beyond these simulated families;
  - per-testbed claims about ScienceWorld (n = 5, 1 in test).

## Limitations

1. **Surface variants.** Up to 6 records share a coarse scenario, and a coarse scenario can
   hold up to 18 records once rendering styles are counted. These variants differ in style,
   wording, names and amounts, not in mechanism. So the effective sample size is far below
   2,134. The robustness subset (707 records) is the check.
2. **Test-set class imbalance.** There are 68 reversible test records (16% of test), so R
   estimates are noisier.
3. **Family coverage in test.** Five of the nine new families appear only in train, so test
   results say little about them.
4. **ScienceWorld is token-sized.** 5 records (0.2%), none of them in minimal pairs.
5. **Held-out style.** `compact` appears only in test, so the test set mixes a scenario shift
   with a style shift. Analyses can be stratified by `render_style`.
6. **Horizons barely differ.** h2 and h3 labels are identical, and h1 differs on 46 records.
7. **Team decisions.** The following were adopted by the team and are not professor-approved
   (OQ-21 is open):
   - the partial definition;
   - the production rules of ADR-0008/0009/0010;
   - the variant cap of 6.
8. **Secondary split not produced.** ADR-0008 pre-registered a secondary family-disjoint split
   (B4); it is still not produced as a file.
9. **Human agreement is moderate on file recovery.** Human–human κ = 0.6206, with almost all
   disagreement at the R/P boundary for file revision/backup cases. The instructions were
   ambiguous there (see *Human agreement*). Labels in those families carry more definitional
   uncertainty than the oracle's determinism suggests.
