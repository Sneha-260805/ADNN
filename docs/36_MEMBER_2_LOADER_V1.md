# 36 — Member 2: loading production dataset v1.0

This page replaces the pilot snippets in `MEMBER_2_GUIDE.md` §0 for any work that will be
reported. For the dataset's contents, see docs/35 (data card) and docs/34 (report).

## 1. Get the data

The dataset is not in git. Either copy `data/production/v1.0/` from Member 1, or regenerate it
(docs/34 §6). Then check it:

```powershell
.\.venv\Scripts\python.exe -m adnn.dataset.validation data/production/v1.0   # expect 0 errors
```

You should see one warning, about the irreversible class share; that is expected. The validator
re-runs the oracle and takes a few minutes. Do not pass `--final`: with that flag the
validator applies the 2,000-record threshold, and this dataset fails it by design (REQ-DATA-01
is unmet, docs/34 §5).

`records.jsonl` must have sha256
`b5a7d58f342fbc2ef7c0658a0dd2a9ffc99c95f8153c8aa1d79bcb70620e20dd`.

## 2. Load and split

```python
from adnn.dataset.api import load_dataset
from adnn.dataset.prompting import locate_action

ds = load_dataset("data/production/v1.0")    # verifies file checksums and builder version
train = list(ds.iter_split("train"))          # 489 records
test = list(ds.iter_split("test"))            # 132 records
```

- **Split rule.** `split.json` has `kind: "scenario_grouped"`, and `ds.split_of(r)` uses
  `r["scenario_id"]`.
- **Do not re-split by row.** Do not rebuild a split from `template_id`. If you need folds, draw
  them over `scenario_id` groups.
- **Pairs.** `ds.minimal_pairs()` returns 112 tuples of the form (member A, member B). Both
  members of a pair are always in the same split.

## 3. Prompts and the action span

```python
for r in train:
    bundle = ds.probe_prompt(r)            # RQ1; raises if the rebuilt hash differs
    msgs = bundle.messages                 # [system, user, assistant(action_text)]
    # rendered = tokenizer.apply_chat_template(msgs, tokenize=False, ...)
    # start, end = locate_action(rendered, r["action_text"])   # exactly one occurrence
    meta = ds.eval_metadata(r)             # label, labels_by_horizon, split, pair_id, ...
    log_hash = r["meta"]["probe_prompt_sha256"]   # store next to every extracted vector
```

- **RQ2.** Use `ds.stated_prompt(r, horizon=3)`. The stored hash covers h = 3 only.
- **Action span.** The action text occurs exactly once in every probe prompt. The validator
  checks this for all 621 records (ADR-0009 A1). If `locate_action` raises on your rendered
  chat template, the template has changed the text; stop and report it.

## 4. Fields

| Field | Use |
|---|---|
| `label` (= h3) and `labels_by_horizon` `{"1","2","3"}` | Targets |
| `environment` | `"sandbox"` or `"scienceworld"`; report results per environment |
| `pair_id` | Minimal pairs (ablation A2); `None` for records that are not in a pair |
| `action_verb` | Control task (tool name in the sandbox; first word of the command in ScienceWorld) |
| `render_style` | `compact` occurs only in test: stratify by it |
| `scenario_id` | Split and bootstrap unit |
| `template_id` | Family, for per-family breakdowns |
| `tier`, `label_provisional` | All records are `"G"` and `False` |

## 5. ScienceWorld records (5)

For these records:
- `state_struct` and `action_call` are `None`;
- `restore_depth` is `None`;
- `tool_set_id` is `ts-scienceworld-1`.

So **do not call** `adnn.dataset.api.sandbox_from_record` or `action_call` on them; filter on
`r["environment"] == "sandbox"` first. Their prompts load like any other record's.

## 6. Do not use as gold

- **`sensitivity_oq21.jsonl`** holds 19 tier-P records that are sensitive to the OQ-21 reading.
  `load_dataset` does not load them. Read them with `adnn.dataset.schema.read_jsonl` only for
  robustness checks.
- **`data/production/superseded-run1-invalid/`** is an invalid first run. Never use it.

## 7. Reporting reminders

- **Metrics.** Use balanced accuracy and macro-F1. Report class counts per split (docs/34
  §4.3).
- **Independence.** Report "N records over K scenarios", and bootstrap confidence intervals
  over `scenario_id`.
- **Missing analyses.** The ≤ 3-per-scenario sensitivity subset and the family-disjoint
  secondary split are not yet produced (docs/35, limitation 8). Ask Member 1 before relying on
  them.
