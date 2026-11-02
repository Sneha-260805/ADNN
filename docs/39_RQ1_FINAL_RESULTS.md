# RQ1 — Do AI Agents Know Which Actions Cannot Be Undone?

## 1. Objective

RQ1 tests whether action reversibility is encoded in transformer hidden states.
The primary experiment uses a linear probe on Qwen/Qwen2.5-7B-Instruct hidden states.

The primary representation is the last token of the action. Mean pooling over action tokens is evaluated as an ablation.

The primary binary task distinguishes `reversible` from `irreversible`; `partially_reversible` is excluded.

## 2. Experimental Protocol

- Model: Qwen/Qwen2.5-7B-Instruct
- Hidden size: 3584
- Transformer layers evaluated: 0–28
- Primary representation: last action token
- Ablation: mean action-token representation
- Probe: L2 logistic regression
- Hyperparameter selection: inner GroupKFold CV
- Grouping variable: `scenario_id`
- Frozen scenario-disjoint splits: seeds 0, 1, 2
- Primary horizon: h=3
- Primary metric: balanced accuracy
- Additional metrics: accuracy, macro-F1, AUROC

The primary outcome is balanced accuracy on the minimal-pair test subset, compared with the lexical action-text baseline.

## 3. Primary Binary Result

### Last-action-token representation

Across the full test sets:
- Balanced accuracy: 0.746643 ± 0.016714
- Macro-F1: 0.689944 ± 0.077321
- AUROC: 0.820128 ± 0.059302

However, performance drops substantially on the controlled minimal-pair subset:
- Balanced accuracy: 0.508746 ± 0.031290
- Macro-F1: 0.366770 ± 0.110894
- AUROC: 0.512562 ± 0.191976

The drop in balanced accuracy from the unrestricted test set to the minimal-pair subset is approximately -0.238.

## 4. Lexical Baseline

A TF-IDF word n-gram baseline using action text was evaluated on the same minimal-pair test subsets.

Results:
- Balanced accuracy: 0.607346 ± 0.093073
- Macro-F1: 0.585429 ± 0.154266
- AUROC: 0.854677 ± 0.071104

The hidden-state last-token representation therefore does not outperform the lexical baseline on the primary minimal-pair outcome.

Hidden minus lexical balanced accuracy:
-0.098600

All 112 minimal pairs were checked and pair members had identical action text, so within-pair action-text identity was preserved.

## 5. Mean-Action-Token Ablation

Mean pooling over action tokens was evaluated using the same frozen splits and binary task.

Full-test results:
- Balanced accuracy: 0.779693 ± 0.143082
- Macro-F1: 0.761832 ± 0.128682
- AUROC: 0.863398 ± 0.119363

Minimal-pair results:
- Balanced accuracy: 0.640153 ± 0.237185
- Macro-F1: 0.625607 ± 0.212441
- AUROC: 0.754832 ± 0.300276

The mean-token point estimate is above the lexical baseline in balanced accuracy, but the result varies substantially across seeds and has lower mean AUROC than the lexical baseline. Therefore, no robust superiority claim is made.

## 6. Horizon Ablation

The binary task was evaluated at horizons h=1, h=2, and h=3.

### Full test sets

- h=1 balanced accuracy: 0.819183 ± 0.010442
- h=2 balanced accuracy: 0.746643 ± 0.016714
- h=3 balanced accuracy: 0.746643 ± 0.016714

### Minimal-pair subsets

- h=1 balanced accuracy: 0.511574 ± 0.039488
- h=2 balanced accuracy: 0.508746 ± 0.031290
- h=3 balanced accuracy: 0.508746 ± 0.031290

The strong unrestricted h=1 performance does not survive the controlled minimal-pair evaluation.

## 7. Control Experiments

### Majority baseline

Balanced accuracy was 0.500 for all three seeds.

### Layer 0

Layer 0 achieved 0.500 balanced accuracy in inner-CV evaluation for all three seeds.

### Shuffled labels

Test balanced accuracy by seed:
- Seed 0: 0.564032
- Seed 1: 0.490514
- Seed 2: 0.687970

The shuffled-label control does not show a consistent above-chance pattern.

### Random fixed label per action verb

This control was treated as exploratory rather than as a formal statistical control because action-verb frequencies and scenario distributions were highly imbalanced. The held-out balanced accuracy for the successful runs was 0.387192 and 0.426169, while one seed had no valid candidate.

The control therefore does not provide evidence of reliable held-out generalization of a random verb-level mapping.

## 8. Scenario-Level Bootstrap

Primary minimal-pair hidden-vs-lexical comparisons used 1000 scenario-level bootstrap resamples.

Because the minimal-pair subsets contained only 2–4 independent scenarios per seed, the resulting confidence intervals are highly underpowered and should not be interpreted as strong population-level uncertainty estimates.

For the last-token hidden-vs-lexical balanced-accuracy difference:
- Seed 0: -0.182759, CI [-0.200000, -0.057143]
- Seed 1: 0.000000, CI [0.000000, 0.000000]
- Seed 2: -0.113043, CI [-0.172973, 0.133333]

## 9. Cross-Environment Transfer

Formal Sandbox-to-ScienceWorld binary transfer is not estimable with the current production dataset.

ScienceWorld contains only 3 binary examples in total and contains zero irreversible examples. The test split contains only one ScienceWorld example.

Therefore, no cross-environment generalization claim is made.

## 10. Three-Class R/P/I Analysis

The three-class analysis was attempted under the same frozen protocol.

Seed 0 was formally estimable:
- Valid inner-CV folds: 5/5
- Selected layer: 20
- C: 0.1
- Inner-CV balanced accuracy: 0.802125
- Test accuracy: 0.639344
- Test balanced accuracy: 0.660672
- Macro-F1: 0.632076
- AUROC: 0.755486

Seeds 1 and 2 each had only 3/5 valid inner-CV folds because two validation folds contained zero irreversible examples.

The predefined minimum of 4 valid folds was therefore not satisfied. The protocol was not relaxed, the frozen splits were not changed, and no test evaluation was performed for those seeds.

No three-seed mean ± SD is reported.

The detailed protocol decision is documented in `docs/decisions/e2-qwen7b-three-class-protocol-outcome.md`.

## 11. Overall Interpretation

The Qwen 7B last-action-token representation shows substantial balanced accuracy on unrestricted test data, but this performance largely disappears under the controlled minimal-pair evaluation.

The primary minimal-pair balanced accuracy is approximately chance level (0.509), and it is below the lexical baseline (0.607).

The mean-action-token representation performs better than the last-token representation on the minimal-pair point estimate, but its large seed-to-seed variability prevents a robust claim that it captures reversibility better than lexical information.

Taken together, these results suggest that unrestricted probe performance may be substantially influenced by action identity, context, or other lexical/environmental cues rather than reflecting a robust representation of action reversibility itself.

This conclusion is deliberately limited to the evaluated Qwen 7B representation and current dataset. It does not establish that transformer hidden states never encode reversibility.

## 12. Outstanding / Deferred Work

Human annotation reliability remains deferred.

The planned QC consists of two independent annotators labeling the same random sample of 100 pairs, followed by:
- Cohen's kappa
- human-vs-automatic agreement

This was explicitly deferred and is not required to reinterpret the computational results above.

## 13. Reproducibility Status

The fresh Qwen 7B hidden-state extraction, frozen split mapping, binary probes, minimal-pair evaluation, lexical baseline, mean-token ablation, horizon ablation, controls, bootstrap analysis, cross-environment diagnostic, and three-class protocol analysis have been completed or explicitly documented as not estimable.

No post-freeze test-set tuning was used to obtain the reported primary result.
