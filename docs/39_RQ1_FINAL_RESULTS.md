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

1\. StandardScaler

2\. L2-regularized Logistic Regression

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

\| Metric | Qwen | Llama |

\|---|---:|---:|

\| Selected layer | 20 | 17 |

\| Selected C | 0.1 | 1.0 |

\| Accuracy | 0.9365 | 0.9412 |

\| Balanced accuracy | 0.9216 | 0.9074 |

\| Macro F1 | 0.9209 | 0.9249 |

\| Macro AUROC | 0.9951 | 0.9918 |

### Binary classification

\| Metric | Qwen | Llama |

\|---|---:|---:|

\| Selected layer | 18 | 16 |

\| Selected C | 0.01 | 0.1 |

\| Accuracy | 0.8871 | 0.8847 |

\| Balanced accuracy | 0.9118 | 0.9099 |

\| Macro F1 | 0.8838 | 0.8815 |

\| AUROC | 0.9864 | 0.9930 |

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

\| Metric | Qwen | Llama |

\|---|---:|---:|

\| Accuracy | 0.8970 ± 0.0740 | 0.8961 ± 0.0806 |

\| Balanced accuracy | 0.9037 ± 0.0694 | 0.9010 ± 0.0791 |

\| Macro F1 | 0.8975 ± 0.0741 | 0.8963 ± 0.0802 |

Three-class supplementary AUROC was not calculated.

### Binary

\| Metric | Qwen | Llama |

\|---|---:|---:|

\| Accuracy | 0.9144 ± 0.0337 | 0.9365 ± 0.0424 |

\| Balanced accuracy | 0.9192 ± 0.0415 | 0.9305 ± 0.0457 |

\| Macro F1 | 0.9016 ± 0.0365 | 0.9258 ± 0.0484 |

\| AUROC | 0.9695 ± 0.0203 | 0.9605 ± 0.0423 |

Test sizes vary because scenario sizes are unequal.

## 7. Baselines and controls

Official binary test-set results:

\| Experiment | Accuracy | Balanced accuracy | Macro F1 | AUROC |

\|---|---:|---:|---:|---:|

\| Qwen Majority | 0.6400 | 0.5000 | 0.3902 | — |

\| Qwen Layer 0 | 0.3624 | 0.5018 | 0.2688 | 0.5018 |

\| Qwen Shuffled | 0.5035 | 0.5263 | 0.5014 | 0.5510 |

\| Qwen TF-IDF Action | 0.7600 | 0.7439 | 0.7417 | 0.8710 |

\| Qwen TF-IDF State + Action | 0.8424 | 0.8440 | 0.8335 | 0.9400 |

\| Qwen Random Verb | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

\| Llama Majority | 0.6400 | 0.5000 | 0.3902 | — |

\| Llama Layer 0 | 0.3624 | 0.5018 | 0.2688 | 0.5018 |

\| Llama Shuffled | 0.5200 | 0.4835 | 0.4835 | 0.5128 |

\| Llama TF-IDF Action | 0.7600 | 0.7439 | 0.7417 | 0.8710 |

\| Llama TF-IDF State + Action | 0.8424 | 0.8440 | 0.8335 | 0.9401 |

\| Llama Random Verb | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

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

### Robustness-subset evaluation (707 records)

A separate robustness evaluation was completed on the 707-record subset
`robustness_subset_le3.json`. The subset contains 178 irreversible (I),
253 partially reversible (P), and 276 reversible (R) records. It contains
580 training records and 127 official test records. The subset includes
136 complete minimal pairs, with no pair split across train and test.

The official robustness test support is I = 39, P = 60, and R = 28
(127 records total). For the binary task, the test support is 88
non-irreversible records and 39 irreversible records.

**Evaluation protocol.** The probes were trained using the original
1,709-record training partition and evaluated on the 127 records in the
robustness subset's official test partition. The probes were not retrained
on the 707-record subset. This preserves the original training protocol
while evaluating performance on the designated robustness subset.

#### Three-class classification

| Metric | Qwen2.5-7B-Instruct | Llama-3.1-8B-Instruct |
|---|---:|---:|
| Selected layer | 20 | 17 |
| Regularisation C | 0.1 | 1.0 |
| Accuracy | 0.9291 | 0.9291 |
| Balanced accuracy | 0.9280 | 0.9123 |
| Macro-F1 | 0.9238 | 0.9210 |

#### Binary irreversibility classification

| Metric | Qwen2.5-7B-Instruct | Llama-3.1-8B-Instruct |
|---|---:|---:|
| Selected layer | 18 | 16 |
| Regularisation C | 0.01 | 0.1 |
| Accuracy | 0.8661 | 0.8504 |
| Balanced accuracy | 0.9034 | 0.8920 |
| Macro-F1 | 0.8571 | 0.8416 |
| AUROC | 0.9875 | 0.9924 |

**Interpretation.** Both models retain strong three-class performance on
the 127-record robustness test set. Binary accuracy is lower than the
three-class accuracy, while balanced accuracy and AUROC remain high. The
results indicate that the learned representations remain predictive on
this designated subset; they do not, by themselves, establish
action-independent reasoning about reversibility.

**Saved outputs.** The result JSON files and per-record prediction JSONL
files are stored separately in each model's `probes/` directory:

- Qwen: `qwen_v2_3class_robustness_subset.json` and
  `qwen_v2_3class_robustness_predictions.jsonl`;
  `qwen_v2_binary_robustness_subset.json` and
  `qwen_v2_binary_robustness_predictions.jsonl`.
- Llama: `llama_v2_3class_robustness_subset.json` and
  `llama_v2_3class_robustness_predictions.jsonl`;
  `llama_v2_binary_robustness_subset.json` and
  `llama_v2_binary_robustness_predictions.jsonl`.
- Cross-model summaries and robustness comparison figures are stored in
  `COMPARISON/`, including
  `ADNN_RQ1_robustness_model_comparison.json`.

The plots are separate deliverables and are not embedded in this Markdown
file.

## 9. Main findings

1\. Both models achieve strong aggregate performance on the official

   three-class and binary test sets.

2\. Qwen has slightly higher official balanced accuracy in both tasks.

3\. Llama has slightly higher official three-class macro F1 and binary

   AUROC.

4\. State + action TF-IDF performs better than action-only TF-IDF.

5\. Both random action-verb controls achieve perfect performance,

   revealing a serious action-identity confound.

6\. Minimal-pair performance is substantially lower than aggregate

   performance, especially for Qwen.

7\. Rendering style affects minimal-pair performance.

8\. Supplementary split results show variation across scenario splits.

## 10. Limitations and interpretation

- Action-verb identity is a major confound.

- Aggregate performance does not prove that representations encode

  irreversibility independently of action identity.

- Minimal-pair results are weaker than aggregate results.

- Only two action verbs support within-verb binary evaluation on the

  official test set.

- The ScienceWorld extension contains only 35 records, with no irreversible
  examples, and therefore supports only a limited binary transfer analysis.
- ScienceWorld action identity perfectly predicts the binary labels in this
  sample; the action-verb baseline reaches 1.0000 balanced accuracy and
  Macro-F1. This is a severe confound, not proof of data leakage.
- The ScienceWorld partially reversible class uses one dominant action
  pattern (`use lighter on X`), while the reversible class uses other verbs.
- ScienceWorld coverage is limited to one house, depth 1, 8 rooms and 35
  records; the labels have not been independently human-annotated.
- Leave-one-room-out validation includes folds with a single class, so its
  perfect mean score must be interpreted cautiously.
- The cross-environment BoW baselines are weak; they do not provide evidence
  of robust action-independent transfer.

- Supplementary splits reuse official-split hyperparameters and are

  not independently retuned.

- Three-class supplementary AUROC was not calculated.

- Bootstrap intervals overlap substantially; model superiority is

  not established.

  ### 9.1 Purpose and scope

A separate cross-environment transfer extension was conducted using the
ScienceWorld transfer dataset. The original RQ1 results above remain unchanged.
This extension asks whether binary reversibility information learned in one
environment transfers to the other:

1. **Sandbox → ScienceWorld:** train on the official Sandbox training split
   and test on ScienceWorld.
2. **ScienceWorld → Sandbox:** train on ScienceWorld and test on the official
   Sandbox test split.

Only two labels are present in the ScienceWorld extension:
- Reversible (0)
- Partially reversible (1)

ScienceWorld contains no irreversible examples, so this extension is a
binary reversible / partially reversible experiment and must not be described
as three-class irreversibility classification.

### 9.2 Dataset and split

ScienceWorld:
- Total records: 35
- Reversible: 20
- Partially reversible: 15
- Irreversible: 0
- Newly extracted pilot records: 30 (`swt-pilot-1`)
- Legacy records already present in the original v2.0 extraction: 5
  (`phase4h`)
- Room coverage: 8 rooms

Sandbox:
- Direction A training set: 1,281 records
  - Reversible: 729
  - Partially reversible: 552
- Direction B test set: 271 records
  - Reversible: 67
  - Partially reversible: 204

The official scenario-grouped v2.0 split was retained. Direction A used only
the Sandbox training records for fitting and model selection, with all 35
ScienceWorld records held out for final evaluation. Direction B used all 35
ScienceWorld records for training and the 271 official Sandbox test records
for final evaluation.

### 9.3 Extraction and probe methodology

The existing model extraction setup was reused:
- Qwen2.5-7B-Instruct: 29 hidden-state positions (embedding plus 28
  transformer layers), hidden size 3,584.
- Llama-3.1-8B-Instruct: 33 hidden-state positions (embedding plus 32
  transformer layers), hidden size 4,096.
- Primary representation: last action token.
- The 5 legacy ScienceWorld records reused their existing original v2.0
  hidden-state representations. The remaining 30 records were extracted
  using the same prompt format, chat template and exact action-token alignment
  procedure as the original extraction.
- The original 2,134 Sandbox representations were not modified.

The probe was StandardScaler followed by balanced L2-regularized Logistic
Regression. Layer and C were selected independently for each direction.

Direction A:
- Five-fold StratifiedGroupKFold on Sandbox training data, grouped by
  `scenario_id`.
- Candidate layers: all available model layers.
- Candidate C values: 0.001, 0.01, 0.1, 1, 10.
- Selection metric: mean validation balanced accuracy.

Direction B:
- Leave-one-room-out cross-validation on the 35 ScienceWorld records,
  using the eight room folds in `cv_folds_by_room.json`.
- The Sandbox test set was not used for layer or C selection.
- Candidate layers and C values were the same as Direction A.

### 9.4 Cross-environment probe results

| Direction | Model | Layer | C | Source CV BA | Target Test BA | Target Macro-F1 | Target AUROC |
|---|---|---:|---:|---:|---:|---:|---:|
| Sandbox → ScienceWorld | Qwen | 20 | 0.01 | 0.9132 | 0.6333 | 0.6329 | 0.6533 |
| Sandbox → ScienceWorld | Llama | 11 | 1.00 | 0.9152 | 0.5750 | 0.4496 | 0.7533 |
| ScienceWorld → Sandbox | Qwen | 14 | 0.001 | 1.0000 | 0.5000 | 0.1982 | 0.4837 |
| ScienceWorld → Sandbox | Llama | 13 | 0.01 | 1.0000 | 0.5000 | 0.1982 | 0.3295 |

Balanced accuracy (BA) is the primary metric. Source CV BA is the model-selection
score within the training environment; target Test BA is the held-out
cross-environment result.

Direction A details:
- Qwen predicted 24 reversible and 11 partially reversible records
  (true counts: 20 and 15).
- Llama confusion matrix (true rows, predicted columns; label order
  reversible, partially reversible): `[[3, 17], [0, 15]]`.
- Llama predicted 3 reversible and 32 partially reversible records. It
  recovered all 15 partially reversible examples but classified only 3 of
  the 20 reversible examples correctly.

Direction B details:
- Qwen predicted all 271 Sandbox test records as reversible.
- Llama also predicted all 271 Sandbox test records as reversible.
- For both models, the confusion matrix (true rows, predicted columns;
  label order reversible, partially reversible) was
  `[[67, 0], [204, 0]]`.
- Both therefore achieved 0.5000 balanced accuracy and 0.1982 Macro-F1.
  Qwen AUROC was 0.4837; Llama AUROC was 0.3295.

### 9.5 Text and action-verb baselines

A TF-IDF word/bi-gram baseline was trained on the source environment's
`action_text` and evaluated on the target environment.

| Direction | Balanced Accuracy | Macro-F1 | AUROC |
|---|---:|---:|---:|
| Sandbox → ScienceWorld | 0.1083 | 0.1114 | 0.2000 |
| ScienceWorld → Sandbox | 0.5000 | 0.1982 | 0.5174 |

A simple action-verb rule on the 35 ScienceWorld records achieved:

| Baseline | Balanced Accuracy | Macro-F1 |
|---|---:|---:|
| `use` → partially reversible; every other verb → reversible | 1.0000 | 1.0000 |

ScienceWorld action-verb distribution:
- `use`: 15
- `open`: 8
- `connect`: 3
- `activate`: 3
- `move`: 2
- `close`: 2
- `pick`: 2

This rule correctly classified all 20 reversible and all 15 partially
reversible ScienceWorld records. It exposes a perfect action-identity
association in this sample. Consequently, the perfect ScienceWorld
leave-one-room-out scores cannot be interpreted as evidence of state
reasoning or action-independent reversibility encoding.

### 9.6 Interpretation

- **Sandbox → ScienceWorld:** Qwen achieved higher target balanced accuracy
  and Macro-F1 than Llama. Llama achieved higher AUROC, indicating better
  ranking of examples despite weaker classification at the default threshold.
- **ScienceWorld → Sandbox:** both models failed to transfer meaningfully.
  Each predicted every Sandbox test record as reversible, missing all 204
  partially reversible examples.
- The perfect ScienceWorld source CV scores did not translate into Sandbox
  target performance.
- The BoW baselines were weak in both directions, indicating that action-text
  lexical patterns alone did not provide robust cross-environment transfer.
- The perfect action-verb rule on ScienceWorld demonstrates that action
  identity is a severe confound for this particular sample.

These findings support a cautious conclusion: the probes can exploit
environment-specific predictive structure, but the extension does not
establish that hidden states represent reversibility independently of action
identity or state context.

### 9.7 ScienceWorld-specific limitations

1. **No irreversible class:** ScienceWorld contains only reversible and
   partially reversible records. The extension cannot test transfer of the
   irreversible class or support a three-class claim.
2. **Small sample:** only 35 records are available across eight rooms.
3. **Action-identity confound:** `use` identifies every partially reversible
   record in this sample, while all other observed verbs identify reversible
   records. The action-verb baseline is perfect.
4. **Template concentration:** the partially reversible examples use one
   dominant pattern, `use lighter on X`.
5. **Narrow environment coverage:** the records come from one house and
   use depth 1.
6. **Partial reversibility definition:** the label is relative to declared
   properties and the supplied witness/residual evidence.
7. **No human annotation:** the labels are generated by the dataset's
   declared admission/evidence procedure and have not been independently
   human-annotated.
8. **Room-fold caveat:** at least one leave-one-room-out validation fold
   produced a single-label warning. The mean CV score of 1.0 should therefore
   be interpreted cautiously, especially given the action-verb confound.
9. **No causal separation:** the experiment cannot disentangle state
   reasoning from action identity.

Required interpretation:
**ScienceWorld transfer tests generalisation to a new environment. It cannot
separate state reasoning from action identity.**

## 10. Reproducibility and handoff notes

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

## 11. Interpretation summary

The results show that action reversibility is highly decodable in the

evaluated dataset. However, the perfect random action-verb control and

the weaker minimal-pair results indicate that this decodability is

entangled with action identity and other contextual cues.

The safest conclusion is that the models' hidden states contain

information predictive of the dataset's reversibility labels, but the

current evidence does not establish action-independent encoding of

irreversibility.