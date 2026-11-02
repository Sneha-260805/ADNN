# E2 Qwen 7B — Three-Class R/P/I Analysis: Protocol Outcome

## Status

The three-class R/P/I analysis was evaluated under `analysis-plan-v1` using the frozen scenario-disjoint splits.

The predefined inner-CV procedure was:
- 5-fold GroupKFold
- grouping by `scenario_id`
- minimum 4 valid folds
- a validation fold is valid only when all three classes are represented
- L2 logistic regression
- C grid: 0.001, 0.01, 0.1, 1.0, 10.0
- layer selection by highest inner-CV balanced accuracy
- ties resolved by lowest layer, then lowest C

No test-set information was used for layer or C selection.

## Results

### Seed 0

- Valid inner-CV folds: 5/5
- Selected layer: 20
- Selected C: 0.1
- Inner-CV balanced accuracy: 0.802125
- Test accuracy: 0.639344
- Test balanced accuracy: 0.660672
- Test macro-F1: 0.632076
- Test AUROC: 0.755486

Confusion matrix, with rows and columns ordered as irreversible / partially_reversible / reversible:

```text
[[16,  1,  6],
 [ 3, 35,  6],
 [12, 16, 27]]
```

### Seed 1

- Valid inner-CV folds: 3/5
- Two validation folds contained zero irreversible examples.
- This is below the predefined minimum of 4 valid folds.
- Therefore, three-class layer/C selection was not estimable under the frozen protocol.
- No three-class test evaluation was performed.

### Seed 2

- Valid inner-CV folds: 3/5
- Two validation folds contained zero irreversible examples.
- This is below the predefined minimum of 4 valid folds.
- Therefore, three-class layer/C selection was not estimable under the frozen protocol.
- No three-class test evaluation was performed.

## Protocol Decision

The predefined protocol was not relaxed to obtain results for Seeds 1 and 2.

Specifically:
- The minimum of 4 valid inner-CV folds was not lowered.
- GroupKFold was not replaced with another splitting method.
- The frozen scenario-disjoint splits were not modified.
- Test data were not used for layer or C selection.
- No three-seed mean ± SD was reported because only Seed 0 was formally estimable.

## Interpretation

The three-class analysis exposes a limitation of the current dataset/split structure: the irreversible class is concentrated in relatively few scenarios. Under scenario-grouped inner validation, this causes the irreversible class to be absent from some validation folds for Seeds 1 and 2.

This should be treated as a dataset/protocol limitation rather than a reason to alter the predefined analysis procedure.

The Seed 0 result is therefore reported as a valid three-class result, while Seeds 1 and 2 are reported as not estimable under `analysis-plan-v1`.
