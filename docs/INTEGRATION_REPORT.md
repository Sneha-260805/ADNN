# Integration report: `integration/final-submission`

- **Prepared:** 2026-11-15 for the 2026-11-17 submission.
- **Author:** AI-assisted (Claude Code) on behalf of Member 1. **Pending human review by all
  three members.**
- **Do not merge into `main` until every member has reviewed this branch.**

## 1. Phase 1: inspection (before any change)

### Branch heads after `git fetch --all --prune`

| Branch | Head | Unique commits vs `origin/main` | Base (merge-base with main) |
|---|---|---:|---|
| `origin/main` | `b963592` | — | — |
| `m1/sw-transfer` | `6318048` | 4 | `e2230f1` (m1/dataset-v2, already in main) |
| `m3/feat/rq2-rq3-results` | `b15e9b1` | 7 (the 4 m1 commits + 3 Member 3 commits) | `e2230f1` |
| `m2/rq1_qwen_llama` | `650f176` | 9 | `b963592` |
| `m2/linear-probes` (not merged) | `efbd620` | 3 | `4ae4cd4` (before dataset v2.0) |

Notes:
- The local `main` was 26 commits behind `origin/main`. The integration branch is based on
  `origin/main`.
- `m1/sandbox-core` and `m1/dataset-v2` are already ancestors of `origin/main` and were not
  merged again.

### Working tree

The local checkout (`m1/sw-transfer`) has **uncommitted, untracked** work:
- SWT2 preregistration and scripts;
- `docs/decisions/0012-sw-transfer-v2-design.md`;
- `tests/test_swt2_admission.py`;
- annotation workbooks and ZIP archives.

None of it is on any remote branch, so **none of it is in this integration**. The integration
was done in a separate `git worktree`, so the local checkout was not touched.

### Overlap analysis

- There are **no overlapping paths** between the three branches (`git diff --name-only`
  intersections are empty).
- The only shared files modified are `.gitignore` (m2 only) and `CONTRIBUTING.md` (m3 only).
- **Textual conflict risk was none, and none occurred.**

### Semantic risks identified

| # | Risk | Disposition |
|---|---|---|
| R1 | Doc number collision: `docs/39_SCIENCEWORLD_TRANSFER_PILOT.md` (M1) and `docs/39_RQ1_FINAL_RESULTS.md` (M2) | Both kept, **not renamed**: other documents and commits link to these paths. Recorded here |
| R2 | `docs/39_RQ1_FINAL_RESULTS.md` §9.6 item 7 and the RQ1 handoff say the labels are "not independently human-annotated". REQ-LBL-05 (docs/43) was later completed on a 100-pair v2.0 sample | Both kept unchanged. Both are true in scope: no ScienceWorld *transfer-set* record was human-annotated, and the v2.0 study covers a sample only. The README and checklist state both |
| R3 | m2 `.gitignore` re-includes `results/rq1_*` and ignores `*.zip`, `results/**/*.pdf`, `results/**/*.xlsx` | Harmless for tracked files. Member 1's local `results/` folders stay ignored, as designed |
| R4 | `m2/linear-probes` holds an earlier Qwen-only probe run (E2, `results/E2_*`, `docs/36_E2…`, `docs/37_E2…`) with a *different* `docs/39_RQ1_FINAL_RESULTS.md` | **Not merged** (instruction). It predates dataset v2.0 (base `4ae4cd4`), and `m2/rq1_qwen_llama` redoes RQ1 on v2.0 with both models. It is superseded. None of its outputs are needed by the final RQ1 documents |
| R5 | The production dataset, transfer set and human annotation outputs are git-ignored | Verified from the local copies (§4). Release packaging is still outstanding |

## 2. Phase 2: merges

All merges are normal `--no-ff` merges. No rebase, squash or force-push was used, and no team
branch was modified.

| Order | Merge commit | Parents | Conflicts |
|---|---|---|---|
| 1 | `4eddb75` Merge `m1/sw-transfer` | `b963592` + `6318048` | none |
| 2 | `6991423` Merge `m3/feat/rq2-rq3-results` | `4eddb75` + `b15e9b1` | none (the m1 commits were already shared) |
| 3 | `baadb86` Merge `m2/rq1_qwen_llama` | `6991423` + `650f176` | none |

Then come the integration commits:
- `05887fd`: validation scripts;
- `a7e4f23`: CI;
- `8226058`: documentation;
- a final fix-up commit, which corrects the run-config manifest attribution found by the
  local CI dry-run.

They change **no file under `results/` or `data/`, and no research code** under
`src/adnn/behaviour`, `scripts/rq1` or `scripts/behaviour`.

## 3. Phase 3: artifact protection check

Every file that each branch changes relative to `origin/main` was compared blob-by-blob with
the integration tree:
- 119 files (m1);
- 650 files (m3);
- 169 files (m2).

That is **938 files, all byte-identical** to their source branch.

## 4. Phase 4: validation

See [`FINAL_REPRODUCIBILITY.md`](FINAL_REPRODUCIBILITY.md) for the commands and full outcomes.
In short:
- installation succeeded;
- pytest without git-ignored data: 820 passed, 3 failed (missing `data/pilot`), 55 skipped;
- pytest with the local data: 836 passed, 1 failed (missing root-level annotation ZIP; it
  passes when the ZIP is present), 41 skipped (ScienceWorld runtime);
- frozen-artifact checksums verify (31 of 31);
- RQ1, RQ2 and RQ3 saved metrics were recomputed with no mismatch;
- 422 of 422 RQ3 traces replay exactly;
- the human agreement analysis reproduces byte-identically.

### Findings raised during validation (no change made)

| # | Finding | Severity |
|---|---|---|
| F1 | No committed version of `src/adnn/behaviour/runner.py` or `scripts/behaviour/run.py` matches the SHA-256 recorded in **any** Member 3 run `config.json`; the other 68–70 recorded source files all match. Member 3 documents that "the Git commits record the reviewed files after inference". The executed source bundles are outside git. The committed runner still replays all 422 saved traces exactly | Provenance gap; archive the Kaggle source bundles with checksums |
| F2 | `results/rq1_llama/probes/llama_v2_binary_final_test_results.json` field `test_f1` (0.8620) is the **irreversible-class** F1, not macro-F1 (0.8815). docs/39, the audits and the results table report the correct macro-F1 0.8815 | Naming ambiguity only; no reported number is wrong |
| F3 | `results/rq1_qwen/validation/qwen_v2_reproducibility_test.py` is a notebook-cell export: it depends on notebook globals (`model`, `tokenizer`, `records`, …; Ruff F821) and is not runnable on its own | Documentation |
| F4 | Ruff reports 757 findings repo-wide: 587 in the two Kaggle notebooks, about 150 in Member 2/3 code, and 1 pre-existing (`RUF100`, appears only with Ruff ≥ 0.17.5). These were not auto-fixed, because experiment code should stay identical to what produced the results | CI lints the clean scope as blocking and reports the rest without blocking |
| F5 | `scripts/behaviour/summarize.py` **overwrites** `metrics.json` in the run directory it is given. Running it on `results/rq2|rq3/...` would modify original outputs | Warning added to README and reproducibility doc |
| F6 | Two test scenario IDs in `split.json` have no records (`grp-0cc4fd8f73a6`, `grp-f8673bb166d9`), so there are 25 scenarios with records out of 27 listed. Member 2 documents this (`results/rq1_llama/dataset_verification/split_audit.json`) | Documented limitation |
| F7 | Some tests need git-ignored local inputs and fail instead of skipping when those are absent. `tests/test_share_link_dataset.py` and `tests/test_share_link_pilot_readiness.py` need `data/pilot/`. `tests/test_annotation_xlsx.py::test_zip_has_only_workbooks_and_readme` needs the root-level `ADNN_Human_Annotation_100_Pairs_Excel.zip`; its `skipif` guards only the workbook folder | Test robustness. CI deselects the 3 `data/pilot` tests explicitly; the ZIP test is skipped in CI because the workbooks are absent |

## 5. Conflicts requiring a scientific decision

None blocked the merge. These items are left for the team because they are not integration
decisions:
- Whether to rename one of the two `docs/39_*` files (R1).
- Whether to update the "no human annotation" wording in docs/39 (R2). Only Member 2 should
  edit that document.
- Whether to archive the git-ignored datasets and Member 1 results at a release tag (needs the
  ENV-09 licence check first).
