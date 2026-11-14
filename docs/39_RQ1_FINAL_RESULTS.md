# ADNN — RQ1: Hidden-State Probing for Action Irreversibility

## 1. Project overview

> **Evidence and scope note.** This file is the detailed RQ1 results and handoff record. The official v2.0 frozen-split results are primary; supplementary splits, robustness, rendering-style diagnostics, and ScienceWorld transfer are secondary or exploratory. High probe scores establish predictive linear decodability on these evaluations, not action-independent reasoning or behavioural use.


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

- Test scenarios: 27 listed in split metadata; 25 contain records

Class distribution across the full dataset:

- Reversible: 799

- Partially reversible: 758

- Irreversible: 577

Official train/test class distribution:

| Label | Train | Test |
|---|---:|---:|
| Reversible | 731 | 68 |
| Partially reversible | 554 | 204 |
| Irreversible | 424 | 153 |

The test set therefore contains only 68 reversible records (16.0%), compared
with 731/1,709 (42.8%) in training. Report balanced accuracy and Macro-F1;
accuracy alone can conceal this distribution shift.

Scenario support: 124 training scenarios and 25 test scenarios containing
records. The test set has one large scenario contributing 102 records, so
scenario-cluster uncertainty estimates are based on a small number of
unequal-sized clusters.

Rendering style is also split-confounded: compact rendering is test-only
(142 test, zero train); key-value rendering has 858 train and 141 test
records; prose rendering has 851 train and 142 test records. Compact-style
results must therefore be interpreted as a test-only formatting condition,
not as an ordinary in-distribution subgroup.

Minimal-pair structure:

- 878 records are pair members (41.14%).

- 439 unique pair IDs.

- Each pair contains exactly two records with the same action verb and

  different labels. The canonical audit verified that all 439 pairs remain

  intact within a single split; no pair crosses train/test.

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



### Last-token versus mean-action-token pooling

The saved binary mean-action-token ablations at the selected Qwen and Llama
binary layers are:

| Model | Representation | Layer | Accuracy | Balanced accuracy | Macro-F1 | AUROC |
|---|---|---:|---:|---:|---:|---:|
| Qwen | Mean action tokens | 18 | 0.8729 | 0.9007 | 0.8699 | 0.9883 |
| Llama | Mean action tokens | 18 | 0.8118 | 0.8515 | 0.8100 | 0.9765 |

These are binary comparisons at the saved selected layers, not a complete
mean-pooling layer sweep. The last-action-token representation remains the
primary representation for the headline results.

### Within-action-verb analysis

Only two action verbs in the official binary test set contain both

binary classes: restore_backup and transfer_money.

This analysis is limited and does not establish generalisation across

action verbs.

### Cross-environment analysis

The final exploratory ScienceWorld transfer set contains 35 records (20
reversible, 15 partially reversible and no irreversible examples). This
supersedes an earlier one-record pilot analysis. The transfer results are
reported separately in Section 9 and must not be interpreted as strong
three-class generalisation evidence. The archived extraction index does not
fully document split membership for all 35 records, so exact example-level
leakage checks remain an open reproducibility limitation.

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



### Rendering-style diagnostic (post-hoc; supplementary)

A post-hoc diagnostic evaluated the frozen predictions separately by the
three rendering styles. No model was retrained, no layer or regularisation
parameter was changed, and the official train/test split was preserved.
This analysis is supplementary and was not part of the original
preregistered selection procedure.

The official test set contains 142 compact, 141 key-value (KV), and 142
prose-rendered records. Compact rendering has no training examples and is
therefore a test-only formatting condition.

#### Per-style test performance

| Model / task | Style | N | Accuracy | Balanced accuracy | Macro-F1 | AUROC |
|---|---|---:|---:|---:|---:|---:|
| Qwen 3-class | Compact | 142 | 0.8944 | 0.9057 | 0.8904 | 0.9932 |
| Qwen 3-class | KV | 141 | 0.9645 | 0.9415 | 0.9457 | 0.9988 |
| Qwen 3-class | Prose | 142 | 0.9507 | 0.9177 | 0.9258 | 0.9966 |
| Qwen binary | Compact | 142 | 0.8451 | 0.8791 | 0.8425 | 0.9832 |
| Qwen binary | KV | 141 | 0.9220 | 0.9389 | 0.9188 | 0.9937 |
| Qwen binary | Prose | 142 | 0.8944 | 0.9176 | 0.8910 | 0.9950 |
| Llama binary | Compact | 142 | 0.8239 | 0.8626 | 0.8220 | 0.9804 |
| Llama binary | KV | 141 | 0.9220 | 0.9389 | 0.9188 | 0.9991 |
| Llama binary | Prose | 142 | 0.9085 | 0.9286 | 0.9050 | 0.9987 |

Each style has the same label support: R=23, P=68, I=51. Verb frequencies
and within-verb label counts are also nearly identical. 24 of 25 test
scenarios appear in all three styles; 26/28 scenario × verb × label groups
have equal counts across styles, while two groups differ by one record.

#### Exact content-matched comparison

To reduce composition differences, an exact content fingerprint was
constructed from scenario, action verb, label, action_call, state_struct,
and task_text. This yielded 141 keys with exactly one record in each style
(423 records total).

| Model / task | Compact BA | KV BA | Prose BA |
|---|---:|---:|---:|
| Qwen 3-class | 0.9043 | 0.9415 | 0.9296 |
| Qwen binary | 0.8833 | 0.9389 | 0.9167 |
| Llama binary | 0.8611 | 0.9389 | 0.9333 |

The compact-style disadvantage persists on this content-matched subset.
Paired exact McNemar tests with Holm correction across nine model/style
comparisons found three significant comparisons: Qwen binary compact vs
KV (adjusted p=0.015625), Llama binary compact vs KV (0.004669), and
Llama binary compact vs prose (0.030975). The other six comparisons were
not significant after correction.

#### Paired scenario-cluster bootstrap

A paired scenario-cluster bootstrap requested 10,000 repetitions on the
141 matched keys (24 scenarios; cluster sizes 3–102). Valid replicates
were 9,996 for Qwen 3-class, 9,998 for Qwen binary, and 10,000 for Llama
binary.

| Model / task | Comparison | BA difference | 95% cluster-bootstrap CI |
|---|---|---:|---:|
| Qwen 3-class | Compact − KV | −0.0326 | [−0.1044, 0.0234] |
| Qwen 3-class | Compact − prose | −0.0251 | [−0.0980, 0.0417] |
| Qwen binary | Compact − KV | −0.0501 | [−0.1443, 0.0000] |
| Qwen binary | Compact − prose | −0.0300 | [−0.0866, 0.0000] |
| Llama binary | Compact − KV | −0.0751 | [−0.1439, −0.0151] |
| Llama binary | Compact − prose | −0.0702 | [−0.1333, −0.0132] |
| Llama binary | KV − prose | +0.0050 | [−0.0152, 0.0222] |

Only the two Llama binary compact comparisons have 95% cluster-bootstrap
intervals excluding zero. The Qwen intervals include zero; the Qwen
binary upper bounds are exactly zero and therefore do not exclude zero.
These bootstrap intervals are exploratory and are not multiplicity
adjusted. The small number of clusters and unequal cluster sizes limit
inferential strength.

**Interpretation.** The diagnostic indicates sensitivity to rendering
format, with compact-rendered examples generally harder for the probes.
Exact content matching reduces, but does not eliminate, concerns about
composition. Because this was post-hoc, compact is test-only, and
scenario-level support is limited, this is not evidence of a causal
formatting effect. Do not use the style results to retune the probes or
replace the primary frozen-split results.

## 9. ScienceWorld cross-environment transfer (exploratory)

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

### 9.1 Dataset and split

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

**Experiment chronology and final-run clarification.** The initial v2.0
extraction contained only five ScienceWorld records. Those five were saved
at that stage, but the five-record set was not the final cross-environment
transfer evaluation. After the separate ScienceWorld transfer set was
expanded to 35 records, the bidirectional transfer experiments were run on
the expanded 35-record set. The five previously extracted records were
retained and their existing hidden-state representations reused; the other
30 records were newly extracted using the same prompt and token-alignment
procedure. All Section 9 transfer metrics below refer to this expanded
35-record evaluation, not to a five-record evaluation.

### 9.2 Extraction and probe methodology

The existing model extraction setup was reused:
- Qwen2.5-7B-Instruct: 29 hidden-state positions (embedding plus 28
  transformer layers), hidden size 3,584.
- Llama-3.1-8B-Instruct: 33 hidden-state positions (embedding plus 32
  transformer layers), hidden size 4,096.
- Primary representation: last action token.
- The five records saved during the initial v2.0 extraction reused their
  existing hidden-state representations; they were not treated as the complete
  transfer set. After the transfer dataset was expanded, 30 additional records
  were extracted and the final transfer analysis used all 35 records.
- The remaining 30 records were extracted using the same prompt format, chat
  template and exact action-token alignment procedure as the original
  extraction.
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

### 9.3 Cross-environment probe results

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

### 9.4 Text and action-verb baselines

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

### 9.5 Interpretation

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

### 9.6 ScienceWorld-specific limitations

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
8. **Room-fold caveat:** the saved aggregate transfer outputs do not include
   fold-level predictions or diagnostics, so the reported single-label fold
   warning cannot be independently checked from the handoff artifacts. The
   mean CV score of 1.0 should in any case be interpreted cautiously, given
   the action-verb confound.
9. **Per-example transfer artifacts:** the handoff does not include complete
   per-example prediction JSONL files for both directions. The reported
   transfer metrics are traceable to saved aggregate result files, but cannot
   be independently recomputed from per-example transfer predictions here.
10. **Legacy-record provenance:** five records originated in v2.0 (four were
    on its train side and one on its test side). Direction A excludes all
    ScienceWorld records from source training and evaluates all 35 separately;
    Direction B trains on the 35-record transfer set and evaluates on the
    official Sandbox test records. Preserve this distinction when describing
    split handling; do not imply the five legacy records were newly extracted.
11. **No causal separation:** the experiment cannot disentangle state
    reasoning from action identity.

Required interpretation:
**ScienceWorld transfer tests generalisation to a new environment. It cannot
separate state reasoning from action identity.**


## 10. Main findings

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

7\. The post-hoc rendering-style diagnostic shows lower performance on compact-rendered test examples, including on exact content-matched records; this is supplementary evidence of rendering sensitivity, not a causal result.

8\. Supplementary split results show variation across scenario splits.

## 11. Limitations and interpretation

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
- The cross-environment BoW baselines are weak and do not establish
  robust action-independent transfer.

- Supplementary splits reuse official-split hyperparameters and are

  not independently retuned.

- Three-class supplementary AUROC was not calculated.

- Bootstrap intervals overlap substantially; model superiority is

  not established.
- The post-hoc rendering-style diagnostic suggests compact-rendering

  sensitivity, but compact is test-only and the matched-cluster bootstrap

  supports a difference only for Llama binary comparisons. This is not a

  preregistered causal result.
- Test class proportions differ from training, and only 25 test scenarios

  contain records; one scenario contributes 102 records. This limits

  effective independent test support and the interpretation of cluster

  confidence intervals.


## 12. Reproducibility and handoff notes

The model folders contain extracted hidden states, extraction metadata,

probe results, predictions, baselines and diagnostic outputs.

The `COMPARISON/` folder contains cross-model summaries, plots, tables,

and supplementary split outputs.

The original dataset files are not copied into this handoff. The dataset

used was ADNN v2.0, and the original dataset location and split metadata

should be retained separately by the receiving researcher.

The hidden-state arrays are not included in the uploaded results ZIP.
They are expected to be stored separately (for example, in the model
activation archive or Kaggle output archive). Their exact archive location
and checksums must be included in the final handoff README.



### Reproducibility gaps identified in the results archive

The accompanying results ZIP does not contain the hidden-state `.npy` arrays,
trained probe weight files, complete extraction/probe-training/evaluation
scripts, or per-example ScienceWorld transfer predictions. These must be
archived separately with checksums and regeneration instructions.

Configuration evidence is incomplete:
- Llama's extraction checkpoint metadata records revision
  `0e9e39f249a16976918f6564b8830bc894c89659`, but the saved model-loading
  configuration does not pin a revision; runtime enforcement is therefore
  not established by the archive.
- The Qwen model revision is not recorded in the included configuration.
- Tokenizer revision and prompt-builder version are not recorded.
- The canonical frozen dataset and split file, dataset checksum, and full
  split membership evidence are not included in the results ZIP.
- Qwen has a full environment/package snapshot; a comparable Llama
  environment snapshot is not present in this archive.
- The Llama three-class robustness aggregate is present, but its
  per-example robustness prediction JSONL is absent. Its metrics cannot be
  independently recomputed from per-example predictions from this archive.
- The ScienceWorld combined extraction index contains 35 IDs, but 30 rows
  lack split and row-index metadata. Only five legacy rows have explicit
  row indices (1270–1274). The canonical production dataset is needed to
  verify the five-record overlap and establish the no-leakage claim.

The ZIP contains result tables, metrics, plots, prediction files and a small
number of validation scripts; it is a results archive, not a complete
standalone reproduction package.

## 13. Interpretation summary

The results show that information predictive of the action-reversibility

labels is linearly decodable on the unrestricted frozen test set. However,

the perfect random action-verb control, strong lexical baselines and weaker

controlled minimal-pair results indicate that this decodability is

entangled with action identity and other contextual cues. The post-hoc

rendering analysis also indicates sensitivity to input format.

The safest conclusion is that the models' hidden states contain

information predictive of the dataset's reversibility labels, but the

current evidence does not establish action-independent encoding of

irreversibility, general state-sensitive reversibility reasoning, or a

causal effect of rendering format.
