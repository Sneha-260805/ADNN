# ScienceWorld transfer handoff package audit

**Audit date:** 2026-11-12  
**Scope:** Files available in the current handoff workspace (`/mnt/data`), `results.zip`, `ADNN_reproducible_scripts.zip`, and `40_SW_TRANSFER_SET_AND_MEMBER2_HANDOFF.md`.

## Verdict

**Partially packaged; not independently reproducible from the supplied handoff files alone.** The aggregate transfer metrics, extraction indexes, transfer protocol/provenance note, and a companion transfer script are present. The frozen 35-record dataset, transfer hidden-state arrays, and per-example transfer prediction outputs are not present in the inspected workspace or ZIP archives.

## What is present

| Artifact | Finding |
|---|---|
| `40_SW_TRANSFER_SET_AND_MEMBER2_HANDOFF.md` | Documents the 35-record `adnn-sw-transfer-1.0` set, source composition, expected hashes, validation, protocol, and limitations. |
| `results/rq1_qwen/scienceworld_transfer/transfer_results.json` | Qwen aggregate results for both transfer directions. |
| `results/rq1_llama/scienceworld_transfer/transfer_results.json` | Llama aggregate results for both directions, including confusion matrices and predicted/true class counts. |
| `results/rq1_qwen/scienceworld_transfer/extraction_index.jsonl` | 30 pilot records, with row indices 0–29 and action-token spans/prompt hashes. |
| `results/rq1_llama/scienceworld_transfer/extraction_index.jsonl` | 30 pilot records, with action-token spans/prompt hashes; row indices are null. |
| `results/rq1_comparison/scienceworld_transfer/combined_extraction_index.jsonl` | 35 rows total: 30 pilot + 5 legacy. The five legacy rows retain v2.0 row indices 1270–1274, model metadata, and split metadata (four train, one test). The 30 pilot rows have null row index, model, dataset version, and split fields. |
| `complete_transfer_comparison.json` and `qwen_llama_comparison.csv` | Combined aggregate comparison and baseline summary. |
| `ADNN_reproducible_scripts.zip` | Includes `cross_environment_transfer.py` and companion probe/robustness scripts. The README says these scripts use saved hidden-state arrays and do not repeat extraction. |

## What is missing or incomplete

1. **Frozen transfer dataset files are absent.** The documented path `data/transfer/sw-transfer-1.0/` and its `records.jsonl`, `tool_sets.json`, `cv_folds_by_room.json`, and `manifest.json` were not found in the workspace or inspected archives. Therefore the documented record and manifest SHA-256 values cannot be checked here.
2. **Transfer hidden-state arrays are absent.** The results archive contains empty `scienceworld_transfer/` directories under the model result folders and no `.npy` transfer arrays. The transfer script requires a records JSONL and a row-aligned hidden-state array.
3. **No per-example transfer prediction JSONLs are included.** Aggregate metrics and class counts are present, but the actual target IDs, labels, predictions, and probabilities for both directions/models cannot be independently audited from per-example outputs.
4. **Extraction-index provenance is uneven.** The 35-row combined index identifies all five legacy records and their original v2.0 split positions, but the 30 pilot rows have no `row_index`, `model`, `dataset_version`, or `split`. The separate Qwen index has row indices 0–29; the separate Llama index does not. These indexes document token spans and prompt hashes, not the full hidden-state tensors.
5. **The reproducible script is not a complete reproduction package.** It performs fixed-setting binary transfer on supplied aligned inputs. It does not recreate hidden states or perform source-side room-fold hyperparameter selection. The README explicitly says it is a companion implementation, not evidence that experiments were rerun.
6. **The results archive contains a stale/conflicting README.** `results/README.md` says “Empty: no experiment has been run,” although the same ZIP contains extensive experiment outputs, including ScienceWorld transfer results. Replace or remove this README before final handoff.
7. **The scripts ZIP includes compiled `__pycache__` files.** Not a scientific validity issue, but clean these out of the handoff archive and package source scripts only.

## Recommended handoff wording

> The ScienceWorld transfer handoff includes the documented protocol and provenance note, aggregate Qwen/Llama results, extraction indexes, comparison tables, and a companion fixed-configuration transfer script. The frozen 35-record transfer dataset, transfer hidden-state arrays, and per-example transfer predictions are not included in this package. Consequently, the reported aggregate transfer results are documented but cannot be independently rerun or fully audited from this package alone. The transfer set's documented hashes and validation status are reported from the dataset-builder handoff and were not re-verified against the absent dataset files in this audit.

## Priority actions before final submission

1. Obtain and include the exact frozen `sw-transfer-1.0` directory (or a checksum-verified archive of its four files) and verify the documented hashes.
2. Include the model-specific ScienceWorld hidden-state arrays, or provide durable access paths plus SHA-256 hashes and exact row-order mapping.
3. Export per-example predictions for Sandbox→ScienceWorld and ScienceWorld→Sandbox for both Qwen and Llama, with record IDs, gold labels, predicted labels, and probabilities/scores.
4. Complete the pilot extraction-index metadata for both models, especially explicit row mapping and model/runtime/prompt-builder provenance.
5. Include the actual source-side room-fold assignments and selected-C/layer selection outputs used for each direction, so the CV selection can be audited.
6. Replace the stale `results/README.md`; rebuild the scripts ZIP without `__pycache__`; then record final archive checksums.

## Integrity note

This audit checks the files available in the supplied handoff workspace and archive contents. It does **not** rerun the ScienceWorld experiment, validate the dataset-builder's original 2026-11-04 validation run, or prove absence of leakage in the underlying records. The existing report's cautious language about transfer limitations should remain unchanged.
