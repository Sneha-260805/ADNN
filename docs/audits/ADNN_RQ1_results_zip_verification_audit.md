# ADNN RQ1 — Results ZIP Verification Audit

Audit date: 2026-11-12  
Input archive: `results.zip`  
Archive SHA-256: `5f61522200432ec98340255d56aa82e648a080a5760dd063c282387b8c375796`

## Scope

Inspected the uploaded results archive (204 entries; 99 JSON, 12 JSONL, 30 PNG, 30 PDF, 3 CSV, 2 XLSX, 3 PY, 2 MD). This audit distinguishes checks against per-example predictions from checks against saved aggregate JSONs. It does not claim to rerun model inference or reconstruct unavailable hidden-state arrays.

## Verified from official per-example predictions

The four official prediction JSONL files contain 425 rows each, with unique record IDs and the same ordered record/scenario IDs across both models and tasks. Independent metric recomputation matches the official report:

| Model/task | Accuracy | Balanced accuracy | Macro-F1 | AUROC |
|---|---:|---:|---:|---:|
| Qwen 3-class | 0.9365 | 0.9216 | 0.9209 | 0.9951 |
| Llama 3-class | 0.9412 | 0.9074 | 0.9249 | 0.9918 |
| Qwen binary | 0.8871 | 0.9118 | 0.8838 | 0.9864 |
| Llama binary | 0.8847 | 0.9099 | 0.8815 | 0.9930 |

Confusion matrices (3-class label order R, P, I):
- Qwen: `[[58, 2, 8], [5, 190, 9], [3, 0, 150]]`
- Llama: `[[53, 2, 13], [0, 199, 5], [0, 5, 148]]`

Binary label order (non-irreversible, irreversible):
- Qwen: `[[224, 48], [0, 153]]`
- Llama: `[[223, 49], [0, 153]]`

## Verified from saved per-seed aggregate JSONs

Means and sample standard deviations recomputed from the three seed-specific JSONs match the summary JSONs:

| Task | Model | Accuracy | Balanced accuracy | Macro-F1 |
|---|---|---:|---:|---:|
| 3-class | Qwen | 0.8970 ± 0.0740 | 0.9037 ± 0.0694 | 0.8975 ± 0.0741 |
| 3-class | Llama | 0.8961 ± 0.0806 | 0.9010 ± 0.0791 | 0.8963 ± 0.0802 |
| Binary | Qwen | 0.9144 ± 0.0337 | 0.9192 ± 0.0415 | 0.9016 ± 0.0365 |
| Binary | Llama | 0.9365 ± 0.0424 | 0.9305 ± 0.0457 | 0.9258 ± 0.0484 |

These are supplementary fixed-hyperparameter evaluations: the official-split selected layer and C were reused. Per-example supplementary prediction JSONLs were not present, so these metrics are verified against per-seed aggregate files, not independently regenerated from per-example outputs.

## Pooling and minimal-pair results

Saved mean-action-token binary ablations:
- Qwen layer 18: accuracy 0.8729, BA 0.9007, macro-F1 0.8699, AUROC 0.9883.
- Llama layer 18: accuracy 0.8118, BA 0.8515, macro-F1 0.8100, AUROC 0.9765.

Canonical 24-family minimal-pair analysis, 72 valid pair-render instances:
- Qwen: 25/72 correct (0.3472).
- Llama: 39/72 correct (0.5417).
- Llama action-text TF-IDF: 0/72.
Qwen render style: compact 2/21; key-value 11/21; prose 7/21. Pair-level contrast accuracy is not ordinary record-level accuracy.

## Baselines and controls

Qwen saved binary controls (425 official test records):
- Majority: BA 0.5000; macro-F1 0.3902.
- Action-only TF-IDF: BA 0.7439; macro-F1 0.7417; AUROC 0.8710.
- State+action TF-IDF: BA 0.8440; macro-F1 0.8335; AUROC 0.9400.
- Layer 0: BA 0.5018; macro-F1 0.2688; AUROC 0.5018.
- Shuffled-label: BA 0.5263; macro-F1 0.5014; AUROC 0.5510.
- Random fixed action-verb label control: BA/F1/AUROC all 1.0000.

The random-verb result is a major action-identity shortcut warning. It must not be described as proof of data leakage, but it prevents interpreting aggregate probe performance as evidence of action-independent reversibility understanding. The action-only lexical baseline is materially strong; the state+action TF-IDF baseline is stronger still.

Llama's baseline directory includes some JSONs with copied/shared Qwen-style values and at least one state+action file with no metrics. Do not present these as independent Llama-specific baseline replications without provenance. The action-only lexical baseline can be described as a shared text baseline if that is how it was produced.

Within-action-verb evaluation has only two verbs with both binary classes in the official test set: `restore_backup` (n=78) and `transfer_money` (n=151). The saved report explicitly warns that this does not establish generalisation across verbs.

## Bootstrap

Both binary bootstrap JSONs specify 1,000 successful scenario-level resamples, 0 skipped, percentile 95% intervals, seed 42, 425 records and 25 scenarios. Saved estimates and intervals match the official prediction metrics. The interval files document the method, but the archive does not include the resampled metric draws or a dedicated bootstrap script; therefore the intervals were checked for metadata and estimate consistency, not independently regenerated from bootstrap draws.

## Robustness subset

The archive contains Qwen binary and 3-class robustness per-example predictions and Llama binary robustness per-example predictions. It contains Llama 3-class robustness aggregate JSON but **no** `llama_v2_3class_robustness_predictions.jsonl`. Thus Llama 3-class robustness metrics cannot be independently recomputed from per-example predictions from this archive.

Saved aggregate results:
- Qwen 3-class: n=127, accuracy 0.9291, BA 0.9280, macro-F1 0.9238.
- Llama 3-class: n=127, accuracy 0.9291, BA 0.9123, macro-F1 0.9210.
- Qwen binary: n=127, accuracy 0.8661, BA 0.9034, macro-F1 0.8571, AUROC 0.9875.
- Llama binary: n=127, accuracy 0.8504, BA 0.8920, macro-F1 0.8416, AUROC 0.9924.

The subset aggregate files state that probes were fit on the original 1,709-record training partition and evaluated on 127 subset test records without retraining on the subset.

## ScienceWorld transfer — important provenance limitation

The current transfer result JSONs agree with the reported aggregate results:
- Sandbox → ScienceWorld: 35 target records (20 R, 15 P, 0 I). Qwen BA 0.6333, macro-F1 0.6329, AUROC 0.6533. Llama BA 0.5750, macro-F1 0.4496, AUROC 0.7533.
- ScienceWorld → Sandbox: 271 Sandbox test records (67 R, 204 P). Qwen and Llama BA 0.5000, macro-F1 0.1982; AUROC Qwen 0.4837, Llama 0.3295. Both models predict every Sandbox target as the reversible/non-irreversible class in this direction.

The comparison JSON reports ScienceWorld action-verb baseline BA and macro-F1 of 1.0000. It also reports weak cross-environment BoW results.

However:
- The 35-row combined extraction index has 30 records with missing `split` and `row_index` metadata, and only five legacy records with row indices 1270–1274 (four marked train, one test).
- No per-example transfer prediction JSONLs are present.
- The archive does not contain the canonical frozen dataset and split file needed to cross-check all 35 ScienceWorld IDs against the five ScienceWorld examples in the production dataset.
- Therefore exact train/validation/test membership, the five-example non-leakage claim, and full example-level transfer predictions cannot be independently verified from this ZIP.
- The archive also contains older one-record/4-record ScienceWorld analyses in `rq1_llama/analysis/`; these are superseded by the newer dedicated `scienceworld_transfer/transfer_results.json` outputs. Document 39 should explicitly mark the older analyses as superseded, not mix them with the 35-record results.

Required wording: “ScienceWorld transfer tests generalisation to a new environment. It cannot separate state reasoning from action identity.” Treat these results as exploratory R/P transfer, not three-class generalisation.

## Model and reproducibility configuration

- Llama `extraction_checkpoint.json` records revision `0e9e39f249a16976918f6564b8830bc894c89659`. Its `model_loading_config.json` does not pin a revision. This is recorded checkpoint metadata, but the runtime loading call still needs verification before claiming the revision was enforced.
- No Qwen model revision is recorded in the included Qwen config files.
- Tokenizer revision and prompt-builder version are not recorded in the ZIP.
- Qwen has an environment snapshot with a full `pip_freeze`; Llama does not have a comparable environment snapshot in this ZIP.
- Dataset version is recorded as ADNN v2.0, but a dataset checksum and the canonical frozen split file are not included.
- The results ZIP does not contain the hidden-state `.npy` arrays or trained probe weight files. It contains result tables, metrics, prediction files, plots and some validation scripts. The extraction manifests and README refer to separately stored activation artifacts, but their presence must be verified in the separate archive/Kaggle storage.
- The ZIP contains only three Python files, all under Qwen validation; it does not contain the complete extraction, probe-training, baseline, bootstrap or transfer implementation scripts.

## Document 39 corrections required

1. Move the ScienceWorld transfer subsection currently placed after Section 10 into a single properly numbered Section 9.
2. Renumber later sections uniquely; there are currently two Section 10 headings and the ScienceWorld subsections are incorrectly numbered 9.1–9.7 after Section 10.
3. Replace the stale Section 8 sentence saying ScienceWorld has one official test record with a statement that the final exploratory transfer set has 35 records (20 R, 15 P, 0 I). Mention the older one-record analysis only as superseded.
4. Add the mean-pooling binary ablation values.
5. Add the supplementary seed mean ± sample SD table and clearly state fixed official hyperparameters.
6. Add a concise baseline table and explicitly interpret the perfect random-verb control as an action-identity confound.
7. Add the 24-family/72-render minimal-pair result and Qwen rendering-style breakdown; distinguish pair accuracy from record-level metrics.
8. Describe bootstrap as scenario-level percentile bootstrap, seed 42, 1,000 successful resamples, 25 test scenarios; state that draws/script are not in this archive.
9. Add the robustness prediction-file gap for Llama 3-class.
10. Correct ScienceWorld claims: R/P only, exploratory, 35 examples, no I; action-only baseline is perfect; transfer predictions and exact leakage audit are unavailable in this archive.
11. Replace the claim that hidden-state arrays are included in this handoff with accurate archive-location wording. This ZIP does not contain `.npy` arrays or probe weights.
12. Add a reproducibility limitations table: Qwen revision missing; Llama revision recorded but not pinned in loader; tokenizer/prompt-builder versions missing; dataset checksum/split source missing; Llama environment snapshot missing; scripts/weights/activations stored separately or missing.
13. Keep RQ1/RQ2 comparison out of Document 39, as agreed; handle it in a separate comparison document after matching checkpoints and example IDs.

## Overall handoff assessment

The official headline metrics are independently verified from per-example predictions. Supplementary means/SDs, pooling, minimal-pair results, controls and transfer aggregates are supported by saved JSON outputs. The main unresolved reproducibility gaps are ScienceWorld example-level provenance/leakage, Llama 3-class robustness predictions, exact model/tokenizer/prompt configuration, canonical dataset/split hashes, full training/evaluation scripts, trained probe weights and hidden-state arrays in the shared archive.
