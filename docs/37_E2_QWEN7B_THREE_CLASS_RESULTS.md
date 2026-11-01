# E2 Three-Class R/P/I Probe Results — Qwen 2.5 7B

## 1. Purpose

This document records the authoritative three-class extension of E2 for the Qwen/Qwen2.5-7B-Instruct model.

The experiment asks whether hidden representations at different transformer layers contain information useful for distinguishing:

- `reversible`
- `partially_reversible`
- `irreversible`

This is an extension of the frozen binary R/I probe analysis.

The results reported here use the exact sklearn logistic-regression methodology specified for E2. An earlier GPU implementation was rejected after failing equivalence validation against sklearn and is not used in these results.

## 2. Frozen Experimental Setup

### Dataset

- Dataset version: v1.0
- Total records: 621
- Reversible: 279
- Partially reversible: 232
- Irreversible: 110

### Model

`Qwen/Qwen2.5-7B-Instruct`

- Hidden size: 3584
- Transformer hidden layers: 28
- Hidden-state representations: layers 0–28
- Representation: last token of the action

### Task

Three-class classification:

```text
R = reversible
P = partially_reversible
I = irreversible
```

No records were excluded based on label.

### Splits

Three scenario-disjoint seeds were used.

| Seed | Train | Test | Train R/P/I | Test R/P/I |
|---|---:|---:|---|---|
| 0 | 497 | 124 | 224/185/88 | 55/47/22 |
| 1 | 497 | 124 | 223/186/88 | 56/46/22 |
| 2 | 497 | 124 | 223/186/88 | 56/46/22 |

All splits have zero train/test scenario overlap and all three labels are present in both train and test.

## 3. Probe

The classifier is L2-regularized multinomial logistic regression implemented with sklearn.

- StandardScaler
- LogisticRegression
- penalty = L2
- solver = `lbfgs`
- `max_iter = 2000`
- C grid = `[0.001, 0.01, 0.1, 1.0, 10.0]`
- random_state = 0

Standardization is fitted only on the training portion of each inner CV fold.

## 4. Inner Cross-Validation

Layer and C are selected using training data only.

- GroupKFold
- 5 requested folds
- grouping variable: `scenario_id`
- folds lacking all three classes are excluded
- at least 4 valid folds are required
- selection metric: balanced accuracy
- highest mean inner-CV balanced accuracy is selected
- ties are resolved by lowest layer, then lower C

No test-set information is used for layer or C selection.

## 5. Selected Layers

| Seed | Selected layer | Selected C | Inner-CV BA |
|---|---:|---:|---:|
| 0 | 18 | 0.1 | 0.751599 |
| 1 | 18 | 10.0 | 0.704357 |
| 2 | 14 | 0.001 | 0.715586 |

The selected representations are concentrated in the middle/upper-middle portion of the model rather than at layer 0.

## 6. Test Results

### Seed 0

- Accuracy: 0.790323
- Balanced accuracy: 0.706061
- Macro-F1: 0.716308
- Macro-AUROC: 0.969126

Confusion matrix:

```text
             Predicted
             R   P   I
Actual R    44  11   0
       P     0  47   0
       I     3  12   7
```

### Seed 1

- Accuracy: 0.701613
- Balanced accuracy: 0.616907
- Macro-F1: 0.610077
- Macro-AUROC: 0.794831

Confusion matrix:

```text
             Predicted
             R   P   I
Actual R    41  12   3
       P     2  41   3
       I     5  12   5
```

### Seed 2

- Accuracy: 0.733871
- Balanced accuracy: 0.635399
- Macro-F1: 0.625549
- Macro-AUROC: 0.958340

Confusion matrix:

```text
             Predicted
             R   P   I
Actual R    43  13   0
       P     2  44   0
       I     6  12   4
```

## 7. Cross-Seed Summary

| Metric | Mean | SD |
|---|---:|---:|
| Accuracy | 0.7419 | 0.0446 |
| Balanced accuracy | **0.6528** | **0.0471** |
| Macro-F1 | **0.6506** | **0.0574** |
| Macro-AUROC | **0.9074** | **0.0977** |

The primary three-class summary is:

**Balanced accuracy = 0.6528 ± 0.0471 across three scenario-disjoint seeds.**

## 8. Error Pattern

Across all three seeds, reversible and partially reversible actions are generally classified more successfully than irreversible actions.

The dominant error pattern for irreversible examples is:

```text
irreversible → partially_reversible
```

rather than:

```text
irreversible → reversible
```

This indicates that the main difficulty is separating irreversible actions from the partially reversible class.

## 9. Relation to Binary R/I Results

The earlier authoritative binary experiment reported:

**Binary R/I balanced accuracy = 0.7674 ± 0.0972**

The three-class experiment reports:

**R/P/I balanced accuracy = 0.6528 ± 0.0471**

The lower three-class score is consistent with the additional requirement to distinguish the intermediate partially reversible class. The two experiments should not be interpreted as directly interchangeable tasks.

## 10. Interpretation

The three-class probe provides evidence that Qwen 2.5 7B hidden states contain information useful for distinguishing the three reversibility categories.

However, the result does not establish that the model contains a clean, action-invariant representation of reversibility.

In particular, the binary E2 controls showed strong information associated with action identity. Therefore, successful decoding can partly reflect correlations between action identity and reversibility labels.

The three-class result should consequently be interpreted as:

> Hidden states support above-chance decoding of reversibility categories, with reversible and partially reversible states substantially easier to distinguish than irreversible states. Further controls and cross-action generalization analyses are required before attributing the signal specifically to action-invariant reversibility information.

## 11. Methodological Validation

The authoritative results were produced using sklearn logistic regression.

A GPU logistic-regression implementation was initially benchmarked against sklearn. Although it matched sklearn for some cases, it failed equivalence validation on informative layers.

Therefore:

- GPU three-class results are not used.
- No GPU-derived metrics are reported here.
- The sklearn implementation is the authoritative implementation.
- The final experiment was rerun using the validated sklearn methodology.

## 12. Reproducibility

Final result files:

```text
results/E2_extensions/qwen2.5-7b-instruct/three_class_probe_sklearn/
├── seed_0.json
├── seed_1.json
├── seed_2.json
├── all_seeds.json
├── predictions_seed_0.jsonl
├── predictions_seed_1.jsonl
└── predictions_seed_2.jsonl
```

Split files:

```text
results/E2_extensions/qwen2.5-7b-instruct/three_class_splits/
├── split_seed_0.json
├── split_seed_1.json
└── split_seed_2.json
```

Hidden states were extracted previously and are stored outside git according to the repository result-storage policy.

## 13. Status

Status: **COMPLETE**

This is the authoritative Qwen 2.5 7B three-class R/P/I probe result.

The analysis plan remains frozen as `analysis-plan-v1`. This extension does not replace or modify the frozen binary analysis plan.

The next planned extension is the horizon ablation for `h=1` and `h=2`.
