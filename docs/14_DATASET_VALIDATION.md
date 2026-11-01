# 14 — Dataset Validation

Code: `src/adnn/dataset/validation.py`. Command: `python -m adnn.dataset.validation <dir> [--final]` (exit 0 = valid). The validator applies to the pilot and, with `--final` thresholds, to the final dataset.

**Principle:** stored fields are never trusted. Each check re-derives the fact by replaying the action from the serialised initial state, re-running the oracle, re-rendering text, or rebuilding prompts.

## 1. Inputs

The directory must contain:

- `manifest.json`;
- the dataset JSONL;
- the split file;
- `tool_sets.json`.

The manifest's SHA-256 values for the dataset, split and tool sets are checked first (`file_hashes`).

## 2. Checks

| Check | What is verified | Severity |
|---|---|---|
| `file_hashes` | Dataset, split and tool-set files match the manifest hashes | error |
| `schema` | Exactly the fields of `schema.ALL_FIELDS` (no missing, **no unknown**); valid vocabularies; `horizon == 3`; `labels_by_horizon` has keys 1, 2, 3 and `label == labels_by_horizon["3"]`; known render style | error |
| `replay` | `state_struct` parses strictly and has **no pending timers**; `action_text == canonical_action_text(action_call)`; `action_verb` matches; **the action replays successfully** with `step`; `state_text` equals the re-rendering in `render_style`; `tool_set_id` equals the state's permitted tool specs | error |
| `oracle` | Re-run `assess_reversibility(..., on_budget_exhausted="return")`: must be `is_definitive`; labels at h=1,2,3 and both restore depths must equal the stored values | error |
| `provisional` | Every record with a partial label at any horizon carries the partial-definition reason; every record whose OQ-21 alternative labels differ carries the OQ-21 reason; `label_provisional == bool(reasons)` | error |
| `prompts` | Prompt-builder version matches; probe and stated prompt hashes match the rebuild; the action text occurs exactly once in the probe prompt | error |
| `leakage` | No forbidden token or record id/scenario/family/pair id in any prompt (`12` §5) | error |
| `uniqueness` | Unique ids; unique `(state_text, action_text)` | error |
| `pairs` | Exactly 2 members; **byte-identical `action_text`**; same scenario, family, task text, render style and tool set; **different h=3 labels**; **different `state_text`** (pivot visible); same pivot factor and scope with different values; `state_struct` differences non-empty and **all inside `pivot.scope`** | error |
| `label_consistency` | Identical model-visible input (task, state, action) never has different labels | error |
| `split` | No family or scenario in both splits; every record's family and scenario agree on the split; families never span splits; test-only render styles never appear in train | error |
| `counts` | Size ≥ threshold; minimal-pair fraction ≥ 0.30 | error |
| `counts` | Each class ≥ 25% at h=3 | warning |

Thresholds:

| | Pilot (`PILOT_THRESHOLDS`) | Final (`--final`) |
|---|---|---|
| Minimum examples | 150 | 2,000 |
| Minimum minimal-pair fraction | 0.30 | 0.30 |
| Minimum class fraction (warning) | 0.25 | 0.25 |

## 3. Fault-injection tests

`tests/test_dataset_pilot.py` builds a small pilot (1 scenario per family, 42 examples) and shows that the validator **fails** with the expected check for each injected fault:

| Fault injected | Detected by |
|---|---|
| A pair member's label flipped | `oracle` |
| One pair member's action text gets a trailing space | `pairs` (not byte-identical) |
| `state_text` edited | `replay` |
| A second config field changed in one pair member | `pairs` (difference outside the pivot scope) |
| A pending email inserted into an initial state | `replay` |
| `(label: reversible)` appended to a task text | `leakage` |
| A record's family moved to a test family | `split` |
| A partial label's provisional flag removed | `provisional` |
| A `split` field added to a record | `schema` |
| A byte appended to the dataset file | `file_hashes` |
| Too few examples / only non-pair examples | `counts` |

Other tests check that the build is byte-deterministic, that the split file exists before rendering starts, that design expectations are enforced, and that every record satisfies the safeguards.

## 4. Result on the pilot (actually executed)

`python -m adnn.dataset.validation data/pilot` on 2026-10-30 (Python 3.11.9), after the final rebuild:

```
ok: true, n_errors: 0, n_warnings: 0
checks_run: schema 210, replay 210, oracle 210, provisional 210, prompts 210,
            uniqueness 1, pairs 70, label_consistency 1, split 1, counts 1, file_hashes 3
```

**Defects found by the validator during development (fixed before release):**

1. All 210 records failed `prompts`. The tool list's argument order followed dict key order, and that order changed after `tool_sets.json` was written with sorted keys. The builder now uses the `required` list (`12` §6).
2. In the design phase, before any code: two families would have produced identical state texts with different labels, because backup content is not rendered. This was resolved by the observability rule (`13` §2). The `label_consistency` check was added so the problem cannot recur unnoticed.

## 5. What the validator does not check

- Semantic quality of the task texts, or whether a non-pair action is sensible for the task.
- Lexical shortcuts (verb ↔ label correlations). That is measured by the lexical baselines in RQ1 (`02` §6), not prevented here.
- Human agreement (REQ-LBL-05), which is a separate study.
- Correctness of the oracle's semantics themselves. That is covered by the sandbox audit (`11` §6).
