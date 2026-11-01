# Member 2 Guide — Hidden-State Knowledge with Linear Probes (RQ1)

**Scientific question.** When a model reads a state and a candidate action, do its hidden
states already encode whether that action can be undone? We test this with simple,
regularised **linear** probes on Qwen2.5-7B-Instruct and Llama-3.1-8B-Instruct.

> **Status.** Nothing in this guide is implemented yet. `src/adnn/models` and
> `src/adnn/probes` are empty placeholders. Everything marked **TODO** is yours to build.
> Results on dataset v1.0 are **preliminary**: it has 621 records, is below the 2,000 target,
> and has only 11 test scenario groups.

Setup: [ENVIRONMENT_SETUP.md](../ENVIRONMENT_SETUP.md). Dataset facts: [docs/35](35_DATA_CARD_PRODUCTION_V1.md). Loader details: [docs/36](36_MEMBER_2_LOADER_V1.md).

## 1. Work on your own branch

```bash
git switch main && git pull
git switch -c m2/feat/hidden-state-extraction
```

Never commit to `m1/sandbox-core`. See [GITHUB_HANDOFF.md](../GITHUB_HANDOFF.md).

## 2. Inputs that already exist

These APIs exist and are tested:

```python
from adnn.dataset.api import load_dataset
from adnn.dataset.prompting import locate_action

ds = load_dataset("data/production/v1.0")
train = list(ds.iter_split("train"))     # 489 records; the split is by scenario group
test = list(ds.iter_split("test"))       # 132 records; touch only for the final evaluation
bundle = ds.probe_prompt(r)              # .messages = [system, user, assistant(action_text)]
meta = ds.eval_metadata(r)               # label, labels_by_horizon, pair_id, scenario_id, ...
```

- **Use the frozen split.** Do not make your own train/test split.
- **Inner folds.** If you need folds, group them by `scenario_id` (sklearn `GroupKFold`)
  inside train.
- **One split only.** v1.0 has a single split; extra split seeds are a TODO for Member 1.

## 3. Getting the models

| Model | Hugging Face id | Access |
|---|---|---|
| Qwen2.5-7B-Instruct | `Qwen/Qwen2.5-7B-Instruct` | Open download |
| Llama-3.1-8B-Instruct | `meta-llama/Llama-3.1-8B-Instruct` | **Gated.** Accept the Llama 3.1 licence on the model page with your own HF account and wait for approval. Then log in with an HF access token (`huggingface_hub` login; check the current docs for the exact command) |

**Tokens.**
- Never put a token in code, notebooks or git. `.gitignore` already blocks `.env`, `hf_token*`
  and `*.token`.
- Use an environment variable or the HF login cache.

**Pin the revision.** Record the commit hash of the model revision you download and log it
in every run manifest.

**Hardware.** These are estimates; check them against each model's `config.json` and your GPU.
- **Memory needed:** 16-bit weights take about 2 bytes per parameter, so about 15 GB for 7B
  and 16 GB for 8B, plus activations.
- **GPUs that fit:** a 24 GB-class GPU, such as an L4, A10, RTX 3090/4090 or A100, runs them
  in bf16/fp16 at batch size 1.
- **16 GB GPUs** (a T4, as on Colab or Kaggle) are borderline. Splitting the model across
  2 GPUs (`device_map="auto"`) may work.
- **Quantisation decision.** 8-bit or 4-bit quantisation changes hidden states. If you use it,
  use the same setting for every run of a model and report it. This is part of OQ-01.
- **CPU only:** not practical for 7B–8B extraction. Develop the pipeline with a tiny model and
  fakes, then run the real models on a GPU.
- **Model storage:** keep weights in the HF cache outside the repository. `*.safetensors` and
  `hf_cache/` are ignored by git.

## 4. Building model input and locating the action (TODO)

1. **Render the chat.** Render `bundle.messages` with the model's own chat template, including
   the final assistant message (the action).
2. **Find the action span.** Find the character span with
   `locate_action(rendered, r["action_text"])`. It raises unless the action occurs exactly
   once, and the dataset validator guarantees exactly one occurrence in the raw prompt. If it
   raises on the rendered text, the template has changed the text: stop and investigate.
3. **Map to tokens.** Tokenise with `return_offsets_mapping=True` (fast tokenizer). The action
   tokens are those overlapping the span.
4. **Choose positions.**
   - **Last action token:** the last of those tokens. Never use an end-of-turn token the
     template appends.
   - **Mean:** the mean over the action tokens.
5. **Log the hash.** Store `r["meta"]["probe_prompt_sha256"]` next to every vector.

## 5. Extracting hidden states without leakage (TODO)

**Running the model.**
- Run one model per process, as a forward pass only (no generation), under
  `torch.no_grad()` with `output_hidden_states=True`.
- The `hidden_states` tuple has L+1 entries; entry 0 is the embedding output.

**What to save.**
- For **all 621 records**, save `last[layer]` and `mean[layer]` as float16 on the CPU, with an
  index that maps rows to record ids.
- Extraction itself uses no labels, so extracting test records is fine. **Leakage happens
  later**, if test rows touch any fitting or selection step.
- Save files under `results/` (git-ignored) as `.npy` or `.npz` (also ignored). Record their
  SHA-256 in the run manifest.

**Sanity checks.**
- Decoded action tokens equal `action_text` on 20 random records.
- Re-extracting 10 records reproduces the vectors.
- No NaN or Inf values.
- A per-layer norm plot looks reasonable.

## 6. Probes (TODO)

**Data.**
- **Three-class task:** all three labels. Use `labels_by_horizon["3"]`; h = 3 is primary.
- **Binary task:** reversible vs irreversible, with partial records dropped.
- **Horizons:** h = 1 and h = 2 as an ablation.

**Pipeline, fitted on train only.** `StandardScaler` → `LogisticRegression(penalty="l2")`.
- Choose `C` with `GroupKFold` over `scenario_id` inside train, scoring by balanced accuracy.
- Use `class_weight="balanced"` and decide it once.

**Best layer.** Pick it by the inner-CV score. **Never by test.**

**Test.** Evaluate on test **once**, with the selected settings.

**Required tests to write:**
- no test `id` appears in any `fit`, scaler fit or `C` selection;
- toy data that is perfectly separable gives accuracy 1.0;
- shuffled labels give accuracy near chance.

## 7. Baselines and controls (TODO)

| Baseline | Why |
|---|---|
| Majority class (from train) | Floor |
| Bag-of-words on `action_text` | Can the action wording alone solve it? On minimal pairs it cannot exceed chance within a pair |
| Bag-of-words on `state_text + action_text` | Surface-text ceiling |
| Shuffled train labels, same pipeline | Probe capacity check |
| Control task: random fixed label per `action_verb` | Selectivity = probe accuracy − control accuracy |
| Layer 0 (embeddings) | Shows whether later layers add information |

## 8. What to report

Report every metric for each model, on the test set and on the **test minimal-pair subset**
(24 pairs):
- balanced accuracy and macro-F1;
- per-class precision, recall and F1;
- the 3×3 confusion matrix.

| Analysis | Detail |
|---|---|
| Layer curves | Score at every layer, with baselines |
| Minimal pairs | Fraction of pairs where both members are correct; within-pair accuracy |
| Uncertainty | 95% bootstrap CIs resampling **`scenario_id` groups** (1,000 resamples). With 11 test groups, the CIs are wide; say so |
| By environment | Sandbox separately. ScienceWorld has 1 test record: no ScienceWorld claim |
| **Style confound** | `compact` appears only in test. Report test results by `render_style`, and on `kv` + `prose` only |

Label every v1.0 number as **preliminary**.

## 9. Output files and handoff to Member 3 (TODO; this is the contract)

| File (under `results/E2_probes/<model_slug>/<run_id>/`) | Content |
|---|---|
| `manifest.json` | Git commit, dataset `records.jsonl` sha256, model id and revision, dtype or quantisation, seeds, library versions |
| `predictions.jsonl` | One line per (record, layer, condition): `example_id`, `split`, `position`, `task`, `horizon`, `layer`, `condition` (`probe`/`majority`/`bow_action`/…), `pred`, `proba` |
| `best_layers.json` | `{model, task, position, horizon} → layer`, with inner-CV scores |
| `metrics.json` | All §8 numbers with n and CIs |
| `hidden_states/` (not in git) | Arrays and `index.jsonl` (`row`, `example_id`, `action_token_idxs`, `prompt_sha256`) |

**What Member 3 uses.** Test-set predictions at the best layer, joined on `example_id`.

**Agent tasks.** If Member 3 builds behaviour tasks, also run the **trained** probe (no
refitting) on the critical-action prompts of those tasks, so that knowledge, judgment and
behaviour can be compared on the same items.
