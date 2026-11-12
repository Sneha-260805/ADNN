# ADNN RQ1 reproducible scripts

These scripts are companion implementations for the completed Qwen/Llama RQ1
notebooks. They operate on the saved hidden-state arrays; they do not download
models or repeat expensive activation extraction.

## Environment

Python 3.10+ recommended.

```bash
pip install numpy scikit-learn
```

Run commands from the repository root so `scripts.rq1.common` resolves.

## 1. Reproduce a fixed probe evaluation

```bash
python scripts/rq1/probes/train_probe.py \
  --records data/production/v2.0/records.jsonl \
  --split results/rq1_comparison/supplementary_splits/scenario_split_seed_2026.json \
  --hidden-states results/rq1_qwen/hidden_states/last_action_token.npy \
  --model Qwen --task 3class --layer 20 --C 0.1 \
  --output results/rq1_qwen/probes/reproduced_3class.json
```

Replace the model, hidden-state path, task, layer and C with the relevant
notebook configuration. For the primary experiment, point `--split` to the
official frozen split JSON. The selected settings are documented in the RQ1
results handoff.

## 2. Evaluate the 707-record robustness subset

```bash
python scripts/rq1/robustness/evaluate_robustness.py \
  --records data/production/v2.0/records.jsonl \
  --split results/rq1_comparison/official_frozen_split.json \
  --hidden-states results/rq1_qwen/hidden_states/last_action_token.npy \
  --subset data/robustness_subset_le3.json \
  --model Qwen --task 3class --layer 20 --C 0.1 \
  --output results/rq1_qwen/probes/reproduced_robustness_3class.json
```

The split path and subset path above are examples: use the exact filenames
already present in your repository. The script trains on the original
training indices and evaluates only subset IDs that belong to the official
test partition. It does not train on the 707 subset.

## 3. ScienceWorld cross-environment transfer

The records JSONL must include an `environment` field and have exactly the
same row order as the supplied hidden-state array.

```bash
python scripts/rq1/scienceworld/cross_environment_transfer.py \
  --records data/combined_records.jsonl \
  --hidden-states results/combined_hidden_states/last_action_token.npy \
  --source sandbox --target scienceworld --layer 20 --C 0.01 \
  --output results/rq1_qwen/analysis/sandbox_to_scienceworld_reproduced.json
```

Run the reverse direction by swapping `--source` and `--target` and using
the corresponding preselected layer/C from the experiment configuration.
Do not tune hyperparameters on target-environment labels.

## Scope and reproducibility notes

- `train_probe.py` reproduces fixed-configuration probe fitting/evaluation.
  Layer/C selection is intentionally separate: use the notebook's
  GroupKFold-by-scenario screening/selection results and record the selected
  settings explicitly.
- `evaluate_robustness.py` preserves the original-train / held-out-subset
  protocol.
- `cross_environment_transfer.py` performs binary R/P transfer; I-labelled
  records are excluded because ScienceWorld contains no irreversible class.
- Hidden-state extraction remains in the model-specific notebooks. Their
  prompt construction, chat template, action-token span alignment and model
  loading are tightly coupled to each model and the completed extraction
  manifests. Do not replace that extraction with a generic script unless
  those exact settings are moved into a tested shared module.
- These companion scripts are provided for reproducibility and are not a
  claim that the experiments were rerun. The authoritative reported metrics
  remain those in the completed notebooks and saved result JSON files.
