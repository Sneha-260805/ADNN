# Research artifact manifest

- **Branch and date:** `integration/final-submission`, 2026-11-15.
- **Scope:** every research artifact the submission relies on, where it lives and how its
  integrity can be checked.
- **Classes:**
  - **Original:** experiment outputs as produced. Never edit or regenerate them.
  - **Exploratory:** follow-up experiments run after the original results were inspected. Keep
    them separate.
  - **Derived:** analyses recomputed from originals.

**Per-file checksums.** All 669 tracked files under `results/` and `data/` are listed in
[`SHA256SUMS_tracked_results.txt`](SHA256SUMS_tracked_results.txt), generated at integration
time. Verify with:

```bash
sha256sum -c artifacts/SHA256SUMS_tracked_results.txt
```

**Out-of-git artifacts.** These have their sha256 verified by
`scripts/validation/verify_frozen_artifacts.py`; the values are in
[`docs/FINAL_REPRODUCIBILITY.md`](../docs/FINAL_REPRODUCIBILITY.md) §4.

## 1. Frozen inputs (Member 1)

| Artifact | Class | Location | In git? | Integrity |
|---|---|---|---|---|
| Production dataset `adnn-dataset-2.0` (records, split, tool sets, sensitivity, robustness subset, manifest) | Frozen input | `data/production/v2.0/` | **No** (git-ignored; checksummed bundle from Member 1) | `records.jsonl` `d03cd8f3…acdab73`, verified ✅ |
| Frozen v2.0 generation manifest | Frozen input | `docs/preregistration/production_manifest_v2_amend1.json` | Yes | `432e7344…6160c` ✅ |
| ScienceWorld transfer set `adnn-sw-transfer-1.0` (35 records) | Frozen input | `data/transfer/sw-transfer-1.0/` | **No** | `records.jsonl` `cc39fd7a…12d06d` ✅ |
| SWT pilot preregistration packets (S01–S40) | Frozen input | `docs/preregistration/swt_pilot/` | Yes | `manifest.sha256` in folder |
| RQ3 paired task set `rq3-tasks-1.0` (60 pairs, 120 versions) | Frozen input | `data/tasks/rq3-tasks-1.0/` (4 files) | Yes | `tasks.jsonl` `978a58a0…cb17` ✅ |
| Human annotation sample (100 pairs, blank sheets, instructions, sampling manifest) | Frozen input | `data/annotation/human_100_pairs/` | **No** | instructions `68df56e2…4e9b` ✅ |
| Returned annotation workbooks | Original | `ADNN_Annotator_1.xlsx`, `ADNN_Annotator_2_filled.xlsx` (repo root, Member 1's machine) | **No** | `6ac7b350…615ad`, `e146d1c0…209b5` ✅ |
| Human agreement results (`summary.json`, disagreement CSVs) | Original | `results/human_annotation/` | **No** | Re-run byte-identical ✅; archived in `ADNN_REQ-LBL-05_Human_Agreement_Archive.zip` `1db30ace…89675` ✅ |
| Production dataset v1.0 (superseded by v2.0) | Historical | `data/production/v1.0/` | No | `b5a7d58f…` (docs/35) |
| Member 1 phase results (`results/phase*`, `scienceworld_*`, `swt_pilot`, `swt_transfer`) | Original | `results/…` on Member 1's machine | **No** (`results/*` ignored) | Phase reports in `docs/` |

## 2. RQ1: hidden-state probing (Member 2)

| Artifact | Class | Location | Files | Integrity / notes |
|---|---|---|---:|---|
| Qwen RQ1 outputs (probes, predictions, baselines, analysis, ablations, plots, validation, config, ScienceWorld transfer) | Original | `results/rq1_qwen/` | 50 | Final predictions recomputed ✅ |
| Llama RQ1 outputs (+ `dataset_verification/`) | Original | `results/rq1_llama/` | 46 | Final predictions recomputed ✅ |
| Cross-model comparison, supplementary splits, rendering diagnostic, ScienceWorld transfer | Original / post-hoc diagnostic | `results/rq1_comparison/` | 55 | Reported only |
| RQ1 audits | Derived | `docs/audits/` | 4 | Team audits |
| Notebooks | Code | `notebooks/qwen-rq1-v2.ipynb`, `notebooks/llama-rq1-v2.ipynb` | 2 | Kaggle exports |
| Scripts | Code | `scripts/rq1/` | 10 | — |
| Hidden-state arrays (`.npy`), probe weights | Original | **Not archived anywhere recorded** | — | ❌ Missing; no checksum |
| Llama 3-class robustness per-example predictions; ScienceWorld transfer per-example predictions | Original | — | — | ❌ Missing (docs/39 §12) |
| Earlier Qwen-only E2 probe run (`results/E2_*`) | Superseded | branch `m2/linear-probes` only | — | Not merged |

## 3. RQ2 and RQ3: judgment and behaviour (Member 3)

| Artifact | Class | Location | Files | Integrity / notes |
|---|---|---|---:|---|
| RQ2 test runs, Qwen and Llama (config, outcomes, metrics, figure) | **Original** | `results/rq2/{qwen,llama}/test/` | 8 | Metrics recomputed; IDs = test split ✅ |
| RQ3 pilot runs (10 pairs) | **Original** | `results/rq3/{qwen,llama}/pilot/` | 48 | Metrics recomputed; 40/40 traces replay ✅ |
| RQ3 full runs (60 pairs; one trace file per task version) | **Original** | `results/rq3/{qwen,llama}/full/` | 248 | Metrics recomputed; 240/240 traces replay ✅ |
| Verified analysis (baselines, bootstrap, subgroups, RQ1–RQ2 agreement) | Derived | `results/member3_verified_analysis/` | 16 | Reported; regeneration needs backup ZIPs outside git (`raw_archive_manifest.json`) |
| Member 2 3-class predictions used for RQ1–RQ2 agreement | Copy of original | `results/member3_reference_predictions/` | 2 | Byte-identical to the corresponding `results/rq1_{qwen,llama}/probes/*3class*predictions.jsonl` (verified with `cmp`) ✅ |
| RQ2 recovery-prompt follow-ups (dev and test) | **Exploratory** | `results/member3_followups/{qwen,llama}-{dev-neutral,dev-recovery,test-recovery-v1}/` | — | Metrics recomputed where saved ✅ |
| RQ3 Llama format-prompt follow-ups (smoke, pilot, full) | **Exploratory** | `results/member3_followups/llama-format-*/` | — | 142/142 traces replay ✅ |
| Follow-up archive manifest, RQ1–RQ2 agreement CSV | Exploratory / derived | `results/member3_followups/archive_manifest.json`, `rq1_rq2_agreement.csv` | 2 | — |
| Kaggle execution source bundles (exact `runner.py` / `run.py` used) | Original | **Outside git** | — | ❌ Not in repo. Committed versions differ from the recorded hashes (Repro §7) |
| Raw backup ZIPs of all Kaggle outputs | Original | **Outside git** | — | Checksums in `results/member3_verified_analysis/raw_archive_manifest.json`, `source_archive_checksums.json` |

## 4. Missing or outstanding artifacts

| Artifact | Needed for | Owner |
|---|---|---|
| Hidden-state arrays and probe weights, archived with checksums and location | RQ1 re-fitting; DEL-04 | Member 2 |
| Qwen RQ1 model revision; Llama RQ1 pinned revision; tokenizer revision | RQ1 provenance | Member 2 |
| Per-example predictions for the Llama 3-class robustness subset and the ScienceWorld transfer | Recomputing those tables | Member 2 |
| Kaggle source bundles for all Member 3 runs | Exact execution source | Member 3 |
| Release bundle of v2.0, transfer set and annotation results (or `git add -f` at a release tag after the ENV-09 licence check) | DEL-03; outside reproduction | Member 1 |
| Library lock file (`requirements/`) | REQ-SW-02 | Member 1 |
| Paper PDF/source, slides, demo recording | DEL-01, DEL-05 | All |
