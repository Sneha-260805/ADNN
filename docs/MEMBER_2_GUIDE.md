# Member 2 Guide — Hidden-State Extraction and Linear Probes (RQ1)

This is a *future implementation plan*. Nothing here is implemented yet. Requirement IDs refer to `00_REQUIREMENTS_TRACEABILITY.md`.

## 0. Available now (2026-10-30): actual APIs

> **Production dataset v1.0 (2026-11-01).** For reportable work use `data/production/v1.0`; see `docs/36_MEMBER_2_LOADER_V1.md`. It has a scenario-grouped split, 621 gold records and 112 minimal pairs. The pilot snippets below are for development only.

> **Since the team handoff (`docs/15_TEAM_HANDOFF.md`), prefer `adnn.dataset.api.load_dataset`.** It verifies checksums, splits by family, rebuilds hash-checked prompts and keeps labels in `eval_metadata`. The snippet below still works but does no integrity checks.

The pilot dataset and the shared prompt builder exist (`docs/12`, `docs/13`, `docs/14`). They replace the *planned* C3 signature in §2. Build the pilot locally (it is not in git):

```powershell
.\.venv\Scripts\python.exe -m adnn.dataset.pilot --out data/pilot
.\.venv\Scripts\python.exe -m adnn.dataset.validation data/pilot      # must print "ok": true
```

Loading examples and building probe prompts:

```python
import json
from pathlib import Path
from adnn.dataset.schema import read_jsonl
from adnn.dataset.prompting import PromptInputs, build_probe_prompt, locate_action

d = Path("data/pilot")
records   = read_jsonl(d / "pilot_v0.1.jsonl")                       # 210 dicts (schema: docs/05 §2)
split     = json.loads((d / "pilot_split.json").read_text())         # train/test FAMILIES and scenarios
tool_sets = json.loads((d / "tool_sets.json").read_text())

test_families = set(split["test_families"])                         # split on template_id, never on rows
for r in records:
    bundle = build_probe_prompt(PromptInputs.from_example(r, tool_sets), r["action_text"])
    msgs = bundle.messages                     # [system, user, assistant(action_text)]
    # rendered = tokenizer.apply_chat_template(msgs, tokenize=False, ...)   # check current docs
    # start, end = locate_action(rendered, r["action_text"])               # raises unless exactly once
    # -> map [start, end) to token indices with return_offsets_mapping=True
    is_test = r["template_id"] in test_families
```

Fields you need:

- `label` / `labels_by_horizon` (h=1,2,3);
- `pair_id` (minimal pairs, ablation A2);
- `action_verb` (control task);
- `template_id` (split unit);
- `label_provisional` (filter for anything that might later be reported);
- `meta.probe_prompt_sha256`: log it next to every extracted vector. If your rebuilt prompt hash differs, stop: the prompt builder version changed.

**Pilot caveat.** Pilot results must never be reported (`docs/13`). The pilot has one family-level split (3 test families, 45 examples). The three split seeds come with the final dataset.

## 1. Scope

| You own | You do not own |
|---|---|
| `adnn.models` (loading, prompting via C3, extraction), `adnn.probes` (probes, baselines, controls, ablations), RQ1 results and figure F1, probe predictions for RQ2 | Dataset generation and splits (M1), stated-knowledge prompts and behaviour (M3), shared statistics utilities (M3; you use them) |

## 2. Input contracts (from M1)

**C1 — dataset.** `data/processed/reversibility_vX.Y.jsonl`. Fields you will use:

- `id`, `environment`, `state_text`, `action_text`, `task_text`, `tool_set_id`;
- `label` and `labels_by_horizon`;
- `scenario_id`, `template_id`, `pair_id`, `action_verb`.

Spec: `05_DATASET_SPECIFICATION.md`.

**C2 — splits.** `data/splits/split_seed{0,1,2}.json`. These contain train/test scenario lists and 5 inner folds. Always check that `dataset_sha256` matches the dataset file you load.

**C3 — prompt builder** (original plan; **superseded by §0 and docs/12**, which implement it as `PromptBundle` with `messages`, `action_text`, `prompt_sha256`):

```python
@dataclass(frozen=True)
class AgentPrompt:
    messages: list[dict[str, str]]   # [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", "content": action_text}]
    action_text: str                 # exactly the assistant content
    prompt_sha256: str

def build_agent_messages(example: dict, tool_sets: dict) -> AgentPrompt: ...
```

Your job is to turn `messages` into model input with the model's own chat template, and to find the token span of `action_text`:

1. Render the template text with the assistant message included, then find the character offset of `action_text` in the rendered string. It must appear exactly once; assert this.
2. Tokenise with `return_offsets_mapping=True` (fast tokenizer).
3. Action tokens are the tokens whose offsets overlap `[start, end)`. **Last action token** = the last of these. Never use the end-of-turn token the template appends.
4. Check the current `transformers` docs for chat-template options affecting the final assistant turn. Library APIs change (spec §5); verify against the pinned version.

## 3. Extraction plan (E1)

- Load exactly **one** model per process (REQ-MOD-05). Use the dtype decided in OQ-01; it is identical for all runs of a model. Pin the HF revision hash.
- Use `model(**inputs, output_hidden_states=True)` under `torch.no_grad()`, batch size 1 (or small, padded, with careful indexing). The `hidden_states` tuple has L+1 entries; index 0 is the embedding output.
- For each example, store:
  - `last[ℓ] = h[ℓ][last_idx]`
  - `mean[ℓ] = h[ℓ][action_idxs].mean(0)`

  These are moved to CPU immediately as float16.
- **Shards:** `hidden_states/<model_slug>/<position>/shard_{k:05d}.npy`, shape `(n_k, L+1, D)`, plus `index.jsonl` (`row`, `shard`, `example_id`, `n_prompt_tokens`, `action_token_idxs`, `prompt_sha256`). Skip shards that already exist (resumability).
- Save each prompt text once (REQ-REP-03).
- Manifest per run (`04` §8), with the SHA-256 of each shard.
- **Sanity checks** (must pass, results recorded):
  - decoded action tokens equal `action_text` for 20 random examples;
  - re-extraction of 10 examples matches within tolerance;
  - no NaN/Inf;
  - per-layer norm statistics plotted (catches indexing bugs).

**Memory.** With ~30 layers × ~4k dims, a 2,000-example float16 array is ~0.5 GB per position. Verify `num_hidden_layers` and `hidden_size` in each model's config, rather than relying on these approximations.

## 4. Probes (E2, RQ1)

For each `model × split_seed ∈ {0,1,2} × position ∈ {last, mean} × task ∈ {binary, three_class} × horizon ∈ {1,2,3} (A4) × layer ℓ ∈ {0..L}`:

- **Data.**
  - Binary task: drop `partially_reversible`.
  - Three-class: all three classes.
  - Labels: `labels_by_horizon[h]`, where h=3 is primary.
- **Pipeline.** `StandardScaler` (fit on train) → `LogisticRegression(penalty="l2", C=...)`. Choose C on 5 inner `GroupKFold` folds (balanced accuracy). Use `class_weight="balanced"` if classes are imbalanced (decide once, in the frozen plan).
- **Best layer.** Argmax of the *inner-CV* score, per (model, task, position). Never chosen on test (ENG-06).
- **Metrics on test.** Balanced accuracy, macro-F1, AUROC (binary; one-vs-rest macro for three-class), for the full test set and the minimal-pair subset. CIs via the M3 utility with scenario-level cluster bootstrap (1,000 resamples).

## 5. Baselines, controls and ablations

| ID | Implementation note |
|---|---|
| REQ-BL-01 Majority | Train-set majority class predicted on test |
| REQ-BL-02 Lexical-action | `CountVectorizer` (unigram+bigram; decide in plan) on `action_text` → logistic regression. **Must be reported on minimal pairs.** On minimal pairs, identical actions make it at most chance-level within each pair |
| ENG-08 Lexical-state+action | Same on `state_text + " " + action_text` |
| REQ-BL-03 Shuffled | Permute train labels (seeded); same pipeline, every layer |
| REQ-BL-04 Control task | Assign each `action_verb` a random fixed label drawn from the empirical label distribution (seeded, once per split seed); train and test the probe on these labels; selectivity = probe acc − control acc, per layer |
| REQ-BL-05 Layer 0 | Included in every curve |
| A1 Token position | `last` vs `mean` |
| A2 Minimal pairs only | Restrict train and test to examples with non-null `pair_id` |
| A3 Cross-environment | Train on sandbox train scenarios, test on ScienceWorld test scenarios; and the reverse |
| A4 Horizon | h ∈ {1, 2, 3} |

**Contingency** (REQ-RISK-03): if the probe fails at the best layer, try the other token position, and the 14B model if it is in scope. If it still fails, report a negative result with full controls.

## 6. Output contract to M3 (C6)

`results/E2_probes/<model_slug>/<run_id>/predictions.jsonl`, one line per (example, layer, condition):

```json
{"example_id": "…", "split_seed": 0, "position": "last", "task": "three_class", "horizon": 3,
 "layer": 14, "condition": "probe", "pred": "irreversible",
 "proba": {"reversible": 0.0, "partially_reversible": 0.0, "irreversible": 0.0}}
```

Plus `best_layers.json`: `{model, task, position, horizon} → layer`, with inner-CV scores. M3 uses the predictions at the best layer, on test examples only, for κ(stated, probe).

## 7. Tests you should write

- Action-span localisation on synthetic templates, including an action string that occurs twice (must raise).
- Shard writer/reader round trip; resume skips completed shards.
- Probe pipeline: perfectly separable toy data → accuracy 1.0; random labels → near chance.
- Control-task label assignment is deterministic per seed and constant per verb.
- No test-scenario example is ever used in fit, scaler fit or C selection (assert on ids).

## 8. Deliverables

- D6 hidden states (both models, both positions) + manifests;
- D7 predictions + best layers;
- RQ1 metrics with CIs (mean ± SD over 3 splits);
- figure F1 and the RQ1 rows of ablation table T1;
- report sections: probing method, RQ1 results.

## 9. Integration dependencies on Member 1

| Need | From M1 | Unblocks |
|---|---|---|
| Prompt builder C3 | Phase 2 (M2.3) | Any extraction |
| Pilot dataset D3 (~200 examples) | Phase 2 (M2.4) | Pipeline development and I1 |
| Frozen dataset v1.0 + splits | Phase 3 (M3.6) | Reportable E1/E2 |
| `labels_by_horizon`, `pair_id`, `action_verb` populated | Phase 3 | A2, A4, control task |
| Tool-set definitions (`tool_sets.json`) | Phase 2 | Prompt construction |
| Decision on OQ-01 (dtype/GPU) | Phase 1 | Extraction runs |
