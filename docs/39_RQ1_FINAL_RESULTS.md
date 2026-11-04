# ADNN — RQ1: Hidden-State Probing for Action Irreversibility

## 1. Project overview

This handoff contains the completed RQ1 experiments comparing:

- Qwen2.5-7B-Instruct
- Llama-3.1-8B-Instruct

The objective is to investigate whether information related to action
reversibility is decodable from transformer hidden-state representations.

The experiments include three-class classification and binary
irreversibility classification, along with text baselines, controls,
minimal-pair diagnostics, robustness evaluation and supplementary splits.

## 2. Folder structure

- `ADNN_RQ1_Qwen_v2/` — Qwen extraction, probes, baselines, analysis and plots.
- `ADNN_RQ1_Llama_v2/` — Llama extraction, probes, baselines, analysis and plots.
- `COMPARISON/` — cross-model comparisons, result tables, figures and
  supplementary scenario-grouped split results.

Each model folder contains:
- `hidden_states/` — extracted hidden-state arrays and extraction metadata.
- `probes/` — trained probe results, predictions and layer screening.
- `baselines/` — majority, layer-zero, text and action-verb controls.
- `analysis/` — diagnostic analyses and model summaries.
- `plots/` — figures in PNG and PDF formats.
- `ablations/` and `config/` — additional experiment and configuration files.

## 3. Dataset and split

Dataset version: ADNN v2.0

Total records: 2,134

Official frozen scenario-grouped split:
- Training: 1,709 records
- Test: 425 records
- Training scenarios: 124
- Test scenarios: 27 (25 containing records)

Class distribution across the full dataset:
- Reversible: 799
- Partially reversible: 758
- Irreversible: 577

Minimal-pair structure:
- 878 records are pair members (41.14%).
- 439 unique pair IDs.
- Each pair contains two records with the same action verb and
  different labels and pivots.

The official frozen split is the primary evaluation split.

## 4. Experimental methodology

### Hidden-state extraction

Two representations were extracted:
- Last action token
- Mean action tokens

Qwen:
- 28 transformer layers plus embedding state (29 states).
- Hidden size: 3,584.

Llama:
- 32 transformer layers plus embedding state (33 states).
- Hidden size: 4,096.

### Probe classifier

Pipeline:
1. StandardScaler
2. L2-regularized Logistic Regression

Class weighting: balanced.

Hyperparameter selection:
- GroupKFold grouped by scenario_id.
- Balanced accuracy used for model selection.
- Layer selection and regularization selection performed using training data.

### Classification tasks

Three-class:
- Reversible
- Partially reversible
- Irreversible

Binary:
- Non-irreversible (reversible + partially reversible)
- Irreversible

The binary task excludes neither of the first two classes; they are combined.

## 5. Official frozen-split results

All metrics below are from the 425-record official test set.

### Three-class classification

| Metric | Qwen | Llama |
|---|---:|---:|
| Selected layer | 20 | 17 |
| Selected C | 0.1 | 1.0 |
| Accuracy | 0.9365 | 0.9412 |
| Balanced accuracy | 0.9216 | 0.9074 |
| Macro F1 | 0.9209 | 0.9249 |
| Macro AUROC | 0.9951 | 0.9918 |

### Binary classification

| Metric | Qwen | Llama |
|---|---:|---:|
| Selected layer | 18 | 16 |
| Selected C | 0.01 | 0.1 |
| Accuracy | 0.8871 | 0.8847 |
| Balanced accuracy | 0.9118 | 0.9099 |
| Macro F1 | 0.8838 | 0.8815 |
| AUROC | 0.9864 | 0.9930 |

## 6. Supplementary scenario-grouped splits

Three additional scenario-grouped splits were evaluated:
- Seed 42
- Seed 123
- Seed 2026

These are supplementary evaluations, not replacements for the official
frozen split.

For computational feasibility, the selected layer and C from the official
split were held fixed. Hyperparameters were not retuned independently
for each supplementary split.

Mean ± sample standard deviation:

### Three-class

| Metric | Qwen | Llama |
|---|---:|---:|
| Accuracy | 0.8970 ± 0.0740 | 0.8961 ± 0.0806 |
| Balanced accuracy | 0.9037 ± 0.0694 | 0.9010 ± 0.0791 |
| Macro F1 | 0.8975 ± 0.0741 | 0.8963 ± 0.0802 |

Three-class supplementary AUROC was not calculated.

### Binary

| Metric | Qwen | Llama |
|---|---:|---:|
| Accuracy | 0.9144 ± 0.0337 | 0.9365 ± 0.0424 |
| Balanced accuracy | 0.9192 ± 0.0415 | 0.9305 ± 0.0457 |
| Macro F1 | 0.9016 ± 0.0365 | 0.9258 ± 0.0484 |
| AUROC | 0.9695 ± 0.0203 | 0.9605 ± 0.0423 |

Test sizes vary because scenario sizes are unequal.

## 7. Baselines and controls

Official binary test-set results:

| Experiment | Accuracy | Balanced accuracy | Macro F1 | AUROC |
|---|---:|---:|---:|---:|
| Qwen Majority | 0.6400 | 0.5000 | 0.3902 | — |
| Qwen Layer 0 | 0.3624 | 0.5018 | 0.2688 | 0.5018 |
| Qwen Shuffled | 0.5035 | 0.5263 | 0.5014 | 0.5510 |
| Qwen TF-IDF Action | 0.7600 | 0.7439 | 0.7417 | 0.8710 |
| Qwen TF-IDF State + Action | 0.8424 | 0.8440 | 0.8335 | 0.9400 |
| Qwen Random Verb | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Llama Majority | 0.6400 | 0.5000 | 0.3902 | — |
| Llama Layer 0 | 0.3624 | 0.5018 | 0.2688 | 0.5018 |
| Llama Shuffled | 0.5200 | 0.4835 | 0.4835 | 0.5128 |
| Llama TF-IDF Action | 0.7600 | 0.7439 | 0.7417 | 0.8710 |
| Llama TF-IDF State + Action | 0.8424 | 0.8440 | 0.8335 | 0.9401 |
| Llama Random Verb | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

The random action-verb control assigns a fixed random label to each
action verb. Its perfect performance indicates a serious action-verb
confound. Action identity is highly predictive of the labels in this
dataset.

This is not proof of data leakage, but it prevents interpreting the
probe results as evidence that hidden states isolate irreversibility
independently of action identity.

## 8. Diagnostic analyses

### Minimal pairs

Canonical 24-family minimal-pair evaluation:
- Qwen: 25/72 correct pair-render instances; pair accuracy 0.3472.
- Llama: 39/72 correct pair-render instances; pair accuracy 0.5417.

Both models performed best on key-value rendering and worst on compact
rendering.

The Llama TF-IDF canonical minimal-pair baseline achieved 0/72 correct
pair-render instances. These results are diagnostic and should not be
confused with full-test-set baseline metrics.

### Bootstrap confidence intervals

Binary probe metrics were bootstrapped using 1,000 scenario-level
resamples.

Qwen:
- Balanced accuracy: 0.9118 [0.8111, 1.0000]
- Macro F1: 0.8838 [0.7865, 1.0000]
- AUROC: 0.9864 [0.9424, 1.0000]

Llama:
- Balanced accuracy: 0.9099 [0.8202, 0.9931]
- Macro F1: 0.8815 [0.7767, 0.9866]
- AUROC: 0.9930 [0.9839, 1.0000]

The confidence intervals overlap substantially. Do not claim statistically
significant superiority of one model based on these results.

### Within-action-verb analysis

Only two action verbs in the official binary test set contain both
binary classes: restore_backup and transfer_money.

This analysis is limited and does not establish generalisation across
action verbs.

### Cross-environment analysis

ScienceWorld has insufficient test records for reliable cross-environment
generalisation conclusions. In particular, one official test record is
not enough to support a transfer claim.

## 9. Main findings

1. Both models achieve strong aggregate performance on the official
   three-class and binary test sets.
2. Qwen has slightly higher official balanced accuracy in both tasks.
3. Llama has slightly higher official three-class macro F1 and binary
   AUROC.
4. State + action TF-IDF performs better than action-only TF-IDF.
5. Both random action-verb controls achieve perfect performance,
   revealing a serious action-identity confound.
6. Minimal-pair performance is substantially lower than aggregate
   performance, especially for Qwen.
7. Rendering style affects minimal-pair performance.
8. Supplementary split results show variation across scenario splits.

## 10. Limitations and interpretation

- Action-verb identity is a major confound.
- Aggregate performance does not prove that representations encode
  irreversibility independently of action identity.
- Minimal-pair results are weaker than aggregate results.
- Only two action verbs support within-verb binary evaluation on the
  official test set.
- ScienceWorld test coverage is insufficient for transfer claims.
- Supplementary splits reuse official-split hyperparameters and are
  not independently retuned.
- Three-class supplementary AUROC was not calculated.
- Bootstrap intervals overlap substantially; model superiority is
  not established.

## 11. Reproducibility and handoff notes

The model folders contain extracted hidden states, extraction metadata,
probe results, predictions, baselines and diagnostic outputs.

The `COMPARISON/` folder contains cross-model summaries, plots, tables,
and supplementary split outputs.

The original dataset files are not copied into this handoff. The dataset
used was ADNN v2.0, and the original dataset location and split metadata
should be retained separately by the receiving researcher.

The hidden-state arrays are included to avoid requiring model extraction
again. They are large files and may be stored separately if storage
constraints require it.

## 12. Interpretation summary

The results show that action reversibility is highly decodable in the
evaluated dataset. However, the perfect random action-verb control and
the weaker minimal-pair results indicate that this decodability is
entangled with action identity and other contextual cues.

The safest conclusion is that the models' hidden states contain
information predictive of the dataset's reversibility labels, but the
current evidence does not establish action-independent encoding of
irreversibility.
