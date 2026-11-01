# E2 — Qwen 2.5 7B Reversibility Linear-Probe Results

## 1. Purpose

This document records the results of Experiment E2 for RQ1:

> Do transformer hidden states encode whether an action is reversible?

The experiment evaluates whether reversibility can be decoded from hidden-state representations while controlling for action identity and testing generalization across scenarios and action types.

This document records results after the analysis plan was frozen as `analysis-plan-v1`.

The frozen analysis plan remains the methodological authority. This document records the resulting measurements, controls, exploratory analyses, and interpretation. It does not replace or modify the frozen plan.

---

## 2. Frozen Experimental Configuration

- Experiment: E2
- Analysis plan: `analysis-plan-v1`
- Dataset: production `v1.0`
- Dataset size: 621 records
- Model: `Qwen/Qwen2.5-7B-Instruct`
- Hidden size: 3584
- Transformer hidden layers: 28
- Extracted hidden-state layers: 0–28, giving 29 representations including layer 0
- Primary task: binary classification
- Labels:
  - `reversible`
  - `irreversible`
- Excluded label:
  - `partially_reversible`
- Primary horizon: `h=3`
- Primary representation: last token of the action
- Representation ablation: mean over action tokens
- Probe: L2 logistic regression
- Standardization: fitted on training data only
- C grid: `0.001, 0.01, 0.1, 1.0, 10.0`
- Inner CV: 5-fold GroupKFold by `scenario_id`
- Layer selection: highest inner-CV balanced accuracy, tie broken by lowest layer
- Primary metric: balanced accuracy
- Seeds: 0, 1, 2
- Bootstrap: 1000 resamples, seed `12345`, 95% percentile CI, scenario-level unit
- Paired test specified in plan: McNemar

The complete configuration is stored in:

`configs/e2_qwen7b.yaml`

The frozen analysis plan is stored in:

`docs/decisions/analysis-plan-v1-e2.md`

---

## 3. Hidden-State Extraction

Hidden states were extracted for all 621 production records.

### Extracted arrays

- Last action token:
  - shape: `(621, 29, 3584)`
  - dtype: float16

- Mean action tokens:
  - shape: `(621, 29, 3584)`
  - dtype: float16

Verification performed:

- correct record count: 621
- correct number of layers: 29
- hidden size: 3584
- all values finite
- 621 unique record IDs
- labels match the production dataset:
  - reversible: 279
  - partially reversible: 232
  - irreversible: 110

The hidden-state extraction artifacts and manifest are referenced by the E2 result manifest.

---

## 4. Binary Scenario-Disjoint Evaluation

The frozen production dataset contains 621 records. For the binary R/I task, `partially_reversible` records are excluded.

The scenario-level split artifacts describe the complete test split, including all three labels. The probe evaluation then filters those test records to the binary R/I task.

| Seed | Complete staged test | Partially reversible excluded | Binary test evaluated |
|---|---:|---:|---:|
| 0 | 122 | 44 | 78 |
| 1 | 124 | 46 | 78 |
| 2 | 124 | 46 | 78 |

The evaluated binary test sets contain:

- Seed 0: 55 reversible, 23 irreversible
- Seed 1: 55 reversible, 23 irreversible
- Seed 2: 57 reversible, 21 irreversible

The saved prediction IDs were reconciled against the staged split artifacts. For every seed, all 78 evaluated prediction records are contained in the corresponding staged test split, and the remaining staged test records are exclusively `partially_reversible`.

Therefore, the saved `probe_run_v4` evaluation is consistent with the binary task definition.

---

## 5. Primary Probe Results

### Last action token

| Seed | Selected layer | C | Inner-CV BA | Test BA | Accuracy | Macro-F1 | AUROC |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 17 | 10 | 0.7945 | 0.6585 | 0.5897 | 0.5854 | 0.7043 |
| 1 | 18 | 10 | 0.7204 | 0.8455 | 0.7821 | 0.7737 | 0.8656 |
| 2 | 18 | 0.001 | 0.8115 | 0.7982 | 0.7051 | 0.6967 | 0.9056 |

Mean test balanced accuracy:

**0.7674**

Cross-seed standard deviation:

**0.0972**

### Mean action tokens

| Seed | Selected layer | C | Inner-CV BA | Test BA | Accuracy | Macro-F1 |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 21 | 1 | 0.8030 | 0.5937 | 0.6410 | 0.5879 |
| 1 | 17 | 10 | 0.7515 | 0.7787 | 0.7949 | 0.7645 |
| 2 | 20 | 0.01 | 0.7991 | 0.6015 | 0.6154 | 0.5752 |

Mean test balanced accuracy:

**0.6579**

Cross-seed standard deviation:

**0.1069**

The broad binary test set therefore shows above-chance reversibility decodability, particularly for the last-action-token representation.

---

## 6. Minimal-Pair Evaluation

The production dataset contains 112 original minimal-pair IDs.

Of these:

- 112 are complete pairs
- 62 are complete binary reversible/irreversible pairs
- the binary pairs occur across 4 scenarios
- binary pair action verbs are:
  - `transfer_money`
  - `delete_file`
  - `send_email`

The frozen scenario-disjoint test splits contain the same 5 complete binary minimal pairs, corresponding to 10 binary test records.

These pairs were already present in the production dataset; they were not artificially constructed during E2.

### Primary minimal-pair result

Last-action-token probe:

- Seed 0 BA: 0.6000
- Seed 1 BA: 0.5000
- Seed 2 BA: 0.5000
- Mean BA: **0.5333**
- SD: **0.0577**

Lexical action-text baseline:

- Mean BA: **0.5000**
- Mean accuracy: **0.5000**

Thus, after holding the action identity/action text constant within minimal pairs, the hidden-state probe provides only a small improvement over the lexical baseline.

### Important limitation

All 5 complete binary minimal pairs in the frozen test subset belong to a single scenario.

Consequently, scenario-level bootstrap uncertainty for this subset is degenerate: there is only one independent scenario unit.

The minimal-pair result is therefore interpreted as a small paired evaluation rather than as a well-powered population estimate.

---

## 7. Control Experiments

### 7.1 Majority baseline

For the binary test sets:

- Seed 0 BA: 0.5000
- Seed 1 BA: 0.5000
- Seed 2 BA: 0.5000

Mean:

**0.5000**

This establishes the chance-level balanced-accuracy reference.

### 7.2 Layer-0 control

Layer 0 inner-CV balanced accuracy:

**0.5000**

This provides a non-contextual baseline within the specified probing procedure.

### 7.3 Shuffled-label control

Twenty shuffled-label permutations were evaluated per seed using the real-label selected layer and C.

Results:

- Seed 0 shuffled BA mean: 0.5108
- Seed 1 shuffled BA mean: 0.5245
- Seed 2 shuffled BA mean: 0.4862
- Overall shuffled BA mean: **0.5071**
- Overall shuffled BA SD: **0.0826**

The real-label overall BA was approximately **0.7674**.

The shuffled-label control therefore collapses toward chance, indicating that the real-label performance is not explained simply by an arbitrary classifier fitting procedure.

This control does not establish that the learned signal is specifically reversibility-related.

### 7.4 Random fixed label per action verb

A random binary label was assigned to each action verb, with the same mapping used across training and test.

Results:

- Seed 0: mean BA **0.9217**
- Seed 1: mean BA **0.9283**
- Seed 2: mean BA **0.9379**
- Overall mean BA: **0.9285**
- Overall SD: **0.1036**

This is a strong indication that the hidden-state representation contains substantial action-identity information.

This control is important because high reversibility performance on the broad dataset can potentially be obtained through action-specific information correlated with reversibility.

### 7.5 Lexical action-text baseline

A TF-IDF word n-gram representation of action text was evaluated on the frozen minimal-pair test subset.

- n-gram range: 1–2
- classifier: L2 logistic regression
- C: 1.0
- mean BA: **0.5000**
- mean accuracy: **0.5000**

The lexical baseline cannot distinguish members of a minimal pair when the action text is held constant.

---

## 8. Scenario-Level Bootstrap

The specified bootstrap analysis used:

- 1000 resamples
- seed `12345`
- 95% percentile confidence intervals
- bootstrap unit: `scenario_id`

Cross-seed full-test balanced accuracy:

**0.7674 ± 0.0972**

The per-seed confidence intervals are wide because the number of independent test scenarios is limited.

For the minimal-pair subset, the confidence intervals are degenerate because all 5 test pairs belong to one scenario.

This is a structural limitation of the current dataset/split rather than a bootstrap implementation error.

---

## 9. Exploratory Leave-One-Scenario-Out Analysis

This analysis was performed after the frozen primary analysis and is therefore explicitly exploratory.

The binary minimal-pair dataset contains 62 pairs across 4 scenarios.

Each analysis holds out one entire pair-containing scenario and trains on the remaining scenarios.

### Last action token

Mean held-out-scenario BA:

**0.5104**

SD:

**0.0208**

Mean pair accuracy:

**0.0208**

### Mean action tokens

Mean held-out-scenario BA:

**0.5369**

SD:

**0.0477**

Mean pair accuracy:

**0.0738**

The near-chance held-out-scenario results indicate that the minimal-pair signal does not generalize reliably across scenarios.

These results are not a replacement for the frozen primary outcome.

---

## 10. Exploratory Leave-One-Action-Verb-Out Analysis

This analysis was also performed after the frozen primary analysis and is explicitly exploratory.

The three binary minimal-pair action verbs are:

- `transfer_money`
- `delete_file`
- `send_email`

Each fold holds out one complete action verb.

For the corrected analysis, layer and C selection used **GroupKFold by `pair_id`** on the training action verbs only. The held-out action verb was never used during model selection.

### Last action token

Held-out test BA:

- `transfer_money`: 0.5000
- `delete_file`: 0.5208
- `send_email`: 0.5417

Mean:

**0.5208**

SD:

**0.0208**

Mean pair accuracy:

**0.0417**

### Mean action tokens

Held-out test BA:

- `transfer_money`: 0.5000
- `delete_file`: 0.5000
- `send_email`: 0.5000

Mean:

**0.5000**

SD:

**0.0000**

Mean pair accuracy:

**0.0000**

The inner-CV scores were substantially above chance, but performance collapsed when evaluated on a completely unseen action verb.

This indicates that patterns learned for the observed action types do not reliably transfer to a new action type.

---

## 11. Overall Interpretation

The broad binary test evaluation shows that reversibility can be decoded above chance from Qwen hidden states:

> Last-action-token mean BA = 0.7674.

However, the control experiments show that the hidden states also contain very strong action-identity information:

> Random fixed action-verb labels mean BA = 0.9285.

When action identity is controlled through minimal pairs, the advantage becomes small:

> Hidden-state probe BA = 0.5333  
> Lexical action-text baseline BA = 0.5000.

Exploratory generalization analyses reinforce this pattern:

- Leave-one-scenario-out:
  - last token BA = 0.5104
  - mean tokens BA = 0.5369

- Leave-one-action-verb-out:
  - last token BA = 0.5208
  - mean tokens BA = 0.5000

Therefore, the evidence supports the following conclusion:

> Although reversibility is decodable above chance on the broad dataset, this decodability does not remain when action identity is controlled or when the probe must generalize to unseen action types. The strong action-identity control suggests that much of the broad-dataset signal may be action-specific rather than a robust, action-invariant representation of reversibility.

This should **not** be interpreted as evidence that the model has no knowledge of reversibility.

The more precise conclusion is:

> Under the tested hidden-state representations and linear-probe methodology, evidence for action-invariant reversibility encoding is limited.

---

## 12. What the Experiment Does and Does Not Establish

### Supported by the results

- Reversibility labels are decodable above chance on the broad binary dataset.
- Hidden states contain strong action-identity information.
- Performance drops substantially when action identity is controlled through minimal pairs.
- Performance is approximately chance when evaluated on unseen action verbs.
- The observed broad-dataset signal is therefore not sufficient evidence for an action-invariant reversibility representation.

### Not established

The experiment does not establish that:

- the model has no internal representation of reversibility;
- reversibility information is absent from all layers or token positions;
- the model cannot reason about reversibility;
- the model's behavioral decisions are unrelated to reversibility;
- the probe results generalize to all transformer models.

The conclusions are specific to the tested model, dataset, representations, probe methodology, and evaluation protocol.

---

## 13. Reproducibility Artifacts

Primary E2 artifacts are stored under:

`results/E2_probes/qwen2.5-7b-instruct/probe_run_v4/`

Important files include:

- `manifest.json`
- `metrics.json`
- `predictions_seed_0_last_action_token.jsonl`
- `predictions_seed_1_last_action_token.jsonl`
- `predictions_seed_2_last_action_token.jsonl`
- `predictions_seed_0_mean_action_tokens.jsonl`
- `predictions_seed_1_mean_action_tokens.jsonl`
- `predictions_seed_2_mean_action_tokens.jsonl`
- `layer_selection_seed_0_last_action_token.json`
- `layer_selection_seed_1_last_action_token.json`
- `layer_selection_seed_2_last_action_token.json`
- `layer_selection_seed_0_mean_action_tokens.json`
- `layer_selection_seed_1_mean_action_tokens.json`
- `layer_selection_seed_2_mean_action_tokens.json`
- `bootstrap_statistics.json`
- `shuffled_label_control.json`
- `random_action_verb_label_control.json`
- `lexical_action_text_baseline.json`

The extraction and probe source scripts are:

- `scripts/extract_hidden_states.py`
- `scripts/train_probes.py`

The experiment configuration is:

`configs/e2_qwen7b.yaml`

---

## 14. Post-Freeze Status

The primary analysis was performed under the frozen `analysis-plan-v1`.

The following analyses were performed after the freeze and are explicitly exploratory:

- leave-one-scenario-out minimal-pair evaluation
- leave-one-action-verb-out evaluation

These analyses do not replace the pre-specified primary outcome.

No negative or unfavorable result was discarded.

The exploratory analyses were used to characterize generalization and possible action-identity confounding rather than to select a more favorable result.

---

## 15. Limitations

1. The binary minimal-pair test subset contains only 10 records.
2. All 5 test minimal pairs belong to one scenario, preventing meaningful scenario-level uncertainty estimation for that subset.
3. The production dataset contains only 62 complete binary minimal pairs across 4 scenarios.
4. The leave-one-action-verb-out analysis contains only three action verbs.
5. ScienceWorld contributes only a small number of production records and does not contain irreversible examples sufficient for a strong cross-environment generalization claim.
6. The probe establishes linear decodability, not causal or behavioral use of the representation.
7. High action-identity decodability means broad-dataset reversibility performance may contain action-specific information.
8. The conclusions are limited to the tested model, prompt, representation, layer selection procedure, and dataset.

---

## 16. Final E2 RQ1 Statement

The primary experiment finds above-chance reversibility decodability in Qwen 2.5 7B hidden states on the broad binary dataset. However, action-identity controls and minimal-pair evaluations substantially weaken this evidence, while exploratory scenario- and action-verb-held-out evaluations show near-chance generalization.

Accordingly:

> **E2 provides limited evidence for an action-invariant representation of reversibility in the tested Qwen 2.5 7B hidden states. The broad-dataset decodability appears substantially influenced by action-specific information, and the current experiments do not establish robust generalization of reversibility information across action types or scenarios.**
