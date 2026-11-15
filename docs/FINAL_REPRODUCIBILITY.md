# Final reproducibility record

- **Branch:** `integration/final-submission`.
- **Validation date:** 2026-11-15.
- **Machine:** Windows 11, Python 3.11.9, fresh virtual environment, CPU only. No model was
  loaded and no GPU was used.

Each line below is labelled with one of three evidence levels:
- **EXECUTED:** run during integration, with the observed outcome.
- **REPORTED:** stated in team documents and not re-executed here.
- **BLOCKED:** cannot be reproduced from what exists in or alongside the repository.

## 1. Environment

| Step | Command | Outcome |
|---|---|---|
| Install | `python -m pip install -e ".[dev,data,probes,annotation]"` in a new 3.11 venv | **EXECUTED, success.** Resolved, among others: numpy 2.4.6, scikit-learn 1.9.1, scipy 1.17.1, matplotlib 3.11.2, openpyxl 3.1.5, pytest 9.2.0, ruff 0.17.5 |
| Lock file (REQ-SW-02) | — | **Missing.** `pyproject.toml` declares unpinned ranges. The GPU runs recorded their versions in run configs (Member 3: torch 2.11.0+cu130, transformers 5.20.2, accelerate 1.15.0, Python 3.13.16; Member 2 Qwen: `results/rq1_qwen/config/environment.json`) |

## 2. Tests and linting

| Check | Outcome |
|---|---|
| `pytest` (no git-ignored data present) | **EXECUTED:** 820 passed, **3 failed**, 55 skipped. All 3 failures are `FileNotFoundError` for git-ignored `data/pilot/` (`test_share_link_dataset.py::test_v10_prompt_hashes_of_the_historical_pilot_still_rebuild`, `test_share_link_pilot_readiness.py::test_legacy_pilot_loads_exactly_as_before`, `…::test_pilot_diversity_reports_both_levels_and_flags_sd1_inflation`) |
| `pytest` (local data copied in read-only) | **EXECUTED:** 836 passed, **1 failed**, 41 skipped. The failure is `test_annotation_xlsx.py::test_zip_has_only_workbooks_and_readme`, which needs the git-ignored root-level `ADNN_Human_Annotation_100_Pairs_Excel.zip`. With that file present, the module passes 12/12 |
| Skipped tests | 35 need the pinned ScienceWorld runtime (`ADNN_SW_SITE_PACKAGES`), 2 need `ADNN_SW_SOURCE_DIR`, and 4 need stored ScienceWorld evidence. **Not executed here.** REPORTED by Member 1 (docs/41): "210 passed, 2 skipped" with the pinned runtime |
| `ruff check` (whole repo, 0.17.5) | **EXECUTED:** 757 findings. Notebooks account for 587. Member 2/3 code accounts for about 150 (`scripts/behaviour`, `scripts/rq1`, `src/adnn/behaviour`, `results/rq1_qwen/validation/*.py`, one test). One `RUF100` in `src/adnn/scienceworld/provisional_sampling.py` is pre-existing on `main` and appears only with Ruff ≥ 0.17.5 |
| `ruff check` (team pin 0.17.3, excluding notebooks, results and Member 2/3 experiment code) | **EXECUTED:** all checks passed |
| `ruff format --check` (same scope, Python only) | **EXECUTED:** 138 files already formatted. Eleven Markdown docs contain code samples that Ruff would reformat. This is pre-existing and documented in docs/41 |

Experiment code was **not** auto-fixed, so that the committed code stays identical to the
reviewed code each member submitted.

## 3. Sandbox demonstration

`python -m adnn.demo` was **EXECUTED** (exit code 0).
- Scenario A, recycle bin enabled: deleting `report.txt` is judged *reversible* at h = 1, 2
  and 3, and `restore_file` returns the canonical initial state (`True`).
- Scenario B, recycle bin disabled: `restore_file` fails with `not_found`, and the state is not
  restored (`False`).

## 4. Frozen artifact checksums

`python scripts/validation/verify_frozen_artifacts.py` was **EXECUTED** on the local copies,
read-only: **31/31 OK**. On the original files in Member 1's checkout, the 16 checks that
apply all passed.

| Artifact | File(s) | SHA-256 (verified) |
|---|---|---|
| Production v2.0 | `records.jsonl` | `d03cd8f38ad4b36ce540409e7b3062e0eb4b457d6916483a3334ebde0acdab73` |
| | `split.json` | `110d1b6ae9b704987f95df328a10b6473c6a71993488674fcf6e4f3865c94d3e` |
| | `tool_sets.json` | `a45f798be15a7019dca356334f83fe1be5fa99741d7d8b813cda31e9e09eba33` |
| | `sensitivity_oq21.jsonl` | `3406198c52593e5786bab93014f223a1ba6ded8d2946813f8ebab1aeac2de852` |
| | `robustness_subset_le3.json` | `10039b1be789f83e9e1a5e91da8289399163106c622497e135eff277d5e1dfe5` |
| | frozen manifest `docs/preregistration/production_manifest_v2_amend1.json` | `432e73445d48e7867d1e32a7dde8e90e744c38efcda064cdc7afb147deb6160c` |
| SW transfer 1.0 | `records.jsonl` (file) | `cc39fd7a9e498549f34d9bb335f1bc1095fc0338da94775994d83ca0a312d06d` |
| | canonical `records_sha256` | `f4c20afc9672d2ae62a83412769b569a50a296f8d9ea9b5b6e614aedf6b6faf5` |
| | `cv_folds_by_room.json` | `36eda70b65b48644be72c0bca475bcce7ff0e243570449f013a11eca66087181` |
| | `tool_sets.json` | `328fec62744f9b343c8bbafbe6d05e329040dd0e46d8dc1232e152f529655147` |
| RQ3 tasks 1.0 | `tasks.jsonl` | `978a58a0cbfacc56b8e209eceb32e399b05d02bf8db5ef42b1847dadc7e8cb17` |
| | `tool_sets.json` | `4ceaf1155dc4ba1abe61f7e90be916ae91ef05699863b7a2586cc678cd68096e` |
| | `validation.json` | `c220960c7953a4ccfeabf479a40dbdfb4d4aa4240f11479245f21f0134b428e9` |
| Human annotation | `ANNOTATION_INSTRUCTIONS.md` | `68df56e2a5f57fb7933db597062b8726502a4c23f600d18ddb4f264c8c524e9b` |
| | REQ-LBL-05 archive ZIP (repo root, untracked) | `1db30aced999a6e065ed5af2b0420a24908b869bcf66b93c375695b90cd89675` (matches docs/43) |
| | returned workbooks | A1 `6ac7b350…615ad`, A2 `e146d1c0…209b5` (match docs/43) |

Cross-links were also verified:
- The `dataset_manifest_sha256` in all 15 Member 3 run configs matches a frozen manifest.
  - The 7 RQ3 runs (4 original, 3 format follow-ups) match `data/tasks/rq3-tasks-1.0/manifest.json`.
  - The 8 RQ2 runs (2 original, 6 follow-ups) match `data/production/v2.0/manifest.json`.
- The RQ3 task manifest and the annotation manifest both cite the v2.0 records hash.
- Without the git-ignored bundle (as in CI), the 8 RQ2 checks report MISSING, not a mismatch.

## 5. RQ1: saved-prediction recomputation (Member 2)

`python scripts/validation/recompute_saved_metrics.py` was **EXECUTED**. It uses
scikit-learn on the saved per-example test predictions.

| Prediction file | Recomputed vs saved | IDs = official v2.0 test split | Gold-label mismatches |
|---|---|---|---|
| `rq1_qwen/probes/qwen_v2_binary_predictions.jsonl` | acc, bal-acc, macro-F1, AUROC, confusion matrix: **all match** | yes (425) | 0 |
| `rq1_qwen/probes/qwen_v2_3class_test_predictions.jsonl` | bal-acc, macro-F1, macro-AUROC (saved to 4 d.p.): **match** | yes | 0 |
| `rq1_llama/probes/llama_v2_binary_predictions.jsonl` | acc, bal-acc, AUROC, confusion matrix, macro-F1 (`classification_report`): **match**; `test_f1` = irreversible-class F1 | yes | 0 |
| `rq1_llama/probes/llama_v2_3class_predictions.jsonl` | acc, bal-acc, macro-F1, macro-AUROC: **match** | yes | 0 |

What remains:
- **REPORTED:** layer screening, inner-CV selection, baselines and controls, supplementary
  splits, robustness subset, rendering-style diagnostic and ScienceWorld transfer
  (docs/39 §6–§9). These were not recomputed, because they need hidden states or refitting.
- **BLOCKED:** re-extracting hidden states and re-fitting probes.
  - The hidden-state `.npy` arrays and probe weights are not in git, and no archive location
    or checksum is recorded (docs/39 §12).
  - The Qwen RQ1 model revision is unrecorded.
  - The Llama RQ1 loading call was unpinned.
  - The Llama 3-class robustness per-example predictions are absent.
  - The ScienceWorld transfer per-example predictions are absent.
  - `results/rq1_qwen/validation/qwen_v2_reproducibility_test.py` is a notebook-cell export
    and cannot run standalone.

## 6. RQ2: saved-prediction recomputation (Member 3)

**EXECUTED** with `adnn.behaviour.judgment.classification_metrics` on `outcomes.jsonl`,
compared field by field with `metrics.json` (tolerance 1e-9):

| Run | Outcome |
|---|---|
| `results/rq2/qwen/test`, `results/rq2/llama/test` (original) | **match** |
| `member3_followups/{qwen,llama}-dev-neutral`, `{qwen,llama}-dev-recovery`, `llama-test-recovery-v1` (exploratory) | **match** |
| `member3_followups/qwen-test-recovery-v1` | no `metrics.json` saved in the run folder. Its figures are in `results/member3_verified_analysis` / `member3_followups` CSVs (REPORTED) |

**Dataset alignment (EXECUTED).** The RQ2 run configs record the v2.0 manifest hash (§4). In
addition, the outcome rows were checked one by one against the frozen bundle.
- **Test runs:** all four (two original, two recovery follow-ups) contain exactly the 425
  official test IDs, with 0 duplicates and 0 gold-label mismatches.
- **Dev runs:** all four contain 0 test-split IDs, so there is no test leakage into prompt
  development. All their IDs exist in v2.0, with 0 label mismatches.

**REPORTED, not recomputed:**
- the TF-IDF baseline, scenario-bootstrap intervals and RQ1–RQ2 κ;
- `results/member3_verified_analysis/`, which needs the backup ZIPs named in
  `raw_archive_manifest.json`, kept outside git.

## 7. RQ3: trajectory replay and metric recomputation (Member 3)

**EXECUTED.**
- **Metrics:** `behaviour_metrics` reproduces the saved `metrics.json` of the 4 original runs
  (`rq3/{qwen,llama}/{pilot,full}`), including the bootstrap CIs (seed 42, 1,000 resamples).
- **Replay:** every saved per-task trace was fed back, one raw model output at a time, through
  the committed `adnn.behaviour.runner.run_task` with the frozen `rq3-tasks-1.0`. The replay
  compared prompts (`messages`), `state_before`/`state_after`, events, errors, tool results and
  observations at every step, plus all outcome fields.

| Run | Traces replayed | Exact match |
|---|---:|---:|
| `rq3/qwen/full` | 120 | 120 |
| `rq3/llama/full` | 120 | 120 |
| `rq3/qwen/pilot` | 20 | 20 |
| `rq3/llama/pilot` | 20 | 20 |
| `member3_followups/llama-format-full` (exploratory) | 120 | 120 |
| `member3_followups/llama-format-pilot` (exploratory) | 20 | 20 |
| `member3_followups/llama-format-smoke` (exploratory) | 2 | 2 |

The three `llama-format-*` follow-ups store no `metrics.json`. Their summary numbers are
REPORTED in `docs/MEMBER3_FOLLOWUP_RESULTS.md`.

**Provenance caveat.** The SHA-256 recorded for `src/adnn/behaviour/runner.py` and
`scripts/behaviour/run.py` in every run config matches **no** committed version. All other
recorded source files match. Member 3 states that the commits contain the reviewed
post-inference files. The replay shows that the committed runner reproduces every saved trace,
but the exact executed source is only in the Kaggle bundles, which are outside git.

**BLOCKED:** re-running inference. It needs a GPU and the model weights, and it would not be
done in CI.

## 8. Human agreement study (Member 1)

**EXECUTED** in the integration worktree, writing to a fresh `results/human_annotation/`
there:

```
python scripts/annotation/human_100.py agreement --a1 ADNN_Annotator_1.xlsx --a2 ADNN_Annotator_2_filled.xlsx --accept-uncertain-no
```

- All four CSV/JSON outputs are **byte-identical** to the originals.
- `summary.json` differs only in `computed_utc` and in the absolute input path. docs/43
  documents this.

## 9. Not reproducible from this repository

| What | Why |
|---|---|
| Dataset regeneration | Possible in principle (frozen manifest, generator safeguards), but not run. The frozen bundle is the reference |
| Hidden-state extraction, probe fitting | Arrays and weights not archived; revisions not fully pinned (§5) |
| Model inference for RQ2/RQ3 | GPU; executed source bundles outside git (§7) |
| `results/member3_verified_analysis` regeneration | Needs backup ZIPs outside git |
| ScienceWorld label evidence | Needs the pinned ScienceWorld runtime (Java) |
| Paper, slides, demo recording | Not in the repository |

## 10. Reproduction commands (CPU)

```bash
python -m pip install -e ".[dev,data,probes,annotation]"
python -m adnn.demo
python -m pytest -q
python scripts/validation/verify_frozen_artifacts.py    # exit 0 = all OK, 2 = some artifacts absent, 1 = mismatch
python scripts/validation/recompute_saved_metrics.py --out recompute_report.json
```

**Warning.** `scripts/behaviour/summarize.py RUN_DIR` rewrites `RUN_DIR/metrics.json`. Use it
only on a copy of an original run directory.
