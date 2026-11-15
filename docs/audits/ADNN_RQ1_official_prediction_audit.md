# ADNN RQ1 — Official Prediction Metric Audit

**Scope:** Recalculation from the four uploaded official test prediction JSONL files. This audit does not cover supplementary splits, robustness, baselines, ablations, or ScienceWorld.

## Method
- Accuracy, balanced accuracy and macro-F1 were recalculated from saved true and predicted labels.
- Binary AUROC was recalculated from `probability_irreversible`.
- Three-class macro-AUROC was recalculated using one-vs-rest macro averaging from saved class probabilities.
- Confusion matrices use rows=true labels and columns=predicted labels.
- All four files were checked for record-ID and scenario-ID alignment against the Qwen three-class file.

## Results

| Model/task | N | Accuracy | Balanced accuracy | Macro-F1 | AUROC |
|---|---:|---:|---:|---:|---:|
| Qwen 3-class | 425 | 0.9365 | 0.9216 | 0.9209 | 0.9951 |
| Qwen binary | 425 | 0.8871 | 0.9118 | 0.8838 | 0.9864 |
| Llama binary | 425 | 0.8847 | 0.9099 | 0.8815 | 0.9930 |
| Llama 3-class | 425 | 0.9412 | 0.9074 | 0.9249 | 0.9918 |

## Confusion matrices

### Qwen 3-class
Label order: `['reversible', 'partially_reversible', 'irreversible']`

```text
[58, 2, 8]
[5, 190, 9]
[3, 0, 150]
```

### Qwen binary
Label order: `['non_irreversible', 'irreversible']`

```text
[224, 48]
[0, 153]
```

### Llama binary
Label order: `['non_irreversible', 'irreversible']`

```text
[223, 49]
[0, 153]
```

### Llama 3-class
Label order: `['reversible', 'partially_reversible', 'irreversible']`

```text
[53, 2, 13]
[0, 199, 5]
[0, 5, 148]
```

## Alignment checks

All four files contain 425 records, 425 unique record IDs and 25 unique scenarios. All four have the same ordered record IDs and scenario IDs.

## Interpretation

The recalculated metrics match the previously documented official RQ1 metrics to four decimal places.

## Limitations

- This verifies the saved predictions and metric calculations, not the correctness of the original hidden-state extraction or probe training.
- It does not independently verify the saved hyperparameter-selection process.
- This audit does not verify supplementary, robustness, baseline/control, minimal-pair, pooling-ablation or ScienceWorld results.
- The class labels and probability columns were read directly from the uploaded prediction files.