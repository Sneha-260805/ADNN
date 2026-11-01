# E2 Analysis Plan v1 — Reversibility Probes

## Experiment
E2 — Linear probes for action reversibility in Qwen2.5-7B-Instruct hidden states.

## Research question
Determine whether reversibility information is linearly decodable from transformer hidden states and identify which layers contain the strongest signal.

## Model
- Model: Qwen/Qwen2.5-7B-Instruct
- Hidden layers: 0–28
- Hidden size: 3584

## Dataset
- Dataset version: v1.0
- Total records: 621
- Reversible: 279
- Partially reversible: 232
- Irreversible: 110
- Primary binary task: reversible vs irreversible
- Partially reversible examples are excluded from the binary task.
- Primary horizon: h=3

## Representation
Primary:
- Last token of the action span.

Ablation:
- Mean representation over all action tokens.

## Splits
- Scenario-disjoint splits.
- Split seeds: 0, 1, 2.
- Group key: scenario_id.
- Test performance is not used for model, layer, or hyperparameter selection.

## Probe
- Logistic regression with L2 regularization.
- C grid: 0.001, 0.01, 0.1, 1.0, 10.0.
- Standardization fitted on training data only.
- Probe random seed: 0.
- Selection objective: balanced accuracy.

## Inner cross-validation
- 5-fold GroupKFold over training scenarios.
- Validation folds containing only one binary class are invalid for balanced accuracy.
- Mean inner-CV balanced accuracy is computed over valid folds.
- At least 4 valid folds are required.
- If fewer than 4 valid folds are available, that layer/C combination is invalid.
- C is selected using training data only.

## Layer selection
For the primary outcome, the layer is selected using inner-CV balanced accuracy on the training data only.

## Evaluation metrics
- Accuracy
- Balanced accuracy
- Macro-F1
- AUROC
- Confusion matrix

## Primary outcome
Binary balanced accuracy at the inner-CV-selected layer using:
- last action token representation,
- h=3,
- minimal-pair test subset,
- compared with the lexical-action baseline.

## Controls / planned analyses
- Majority baseline
- Layer 0
- Shuffled-label control
- Control-task baseline
- Lexical-action baseline
- Last-token vs mean-token representation
- Minimal-pairs-only vs all examples
- Horizon sensitivity
- Cross-environment transfer where applicable

## Reproducibility
- Split seeds: 0, 1, 2
- Probe seed: 0
- Bootstrap resamples: 1000
- Bootstrap seed: 12345
- Confidence level: 95%

## Freeze rule
This analysis plan is frozen before the first evaluation on any test split.

Any subsequent methodological change must be documented as a decision and marked exploratory rather than silently replacing this plan.

## Current methodological clarification
The written protocol did not explicitly specify how to handle GroupKFold validation folds containing only one binary class. This version specifies that such folds are invalid for balanced accuracy, that at least four valid folds are required, and that the inner-CV score is averaged over valid folds only.

## Status
FROZEN — analysis-plan-v1
