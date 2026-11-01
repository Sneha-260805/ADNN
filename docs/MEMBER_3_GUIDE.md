# Member 3 Guide — Verbal Judgment vs Actual Behaviour (RQ2, RQ3)

**Scientific question.** Do models **say** the right thing about reversibility (judgment), and
do they **act** on it (behaviour)? How do both compare with what their hidden states
**know** (Member 2's probes)?

> **Status.** Nothing in this guide is implemented yet. `src/adnn/behaviour` and
> `src/adnn/evaluation` are empty placeholders. The **behavioural benchmark does not exist
> yet**: there are no task files, no `finish` or `ask_user` tools, and no agent loop. Items
> marked **TODO** are yours to build, partly with Member 1. Results on dataset v1.0 are
> **preliminary**.

Setup: [ENVIRONMENT_SETUP.md](../ENVIRONMENT_SETUP.md). Dataset: [docs/35](35_DATA_CARD_PRODUCTION_V1.md), [docs/36](36_MEMBER_2_LOADER_V1.md). Work on your own branch, e.g. `m3/feat/stated-judgment`, never on `m1/sandbox-core` ([GITHUB_HANDOFF.md](../GITHUB_HANDOFF.md)).

## 1. Shared discipline with Member 2

- **Models.** Use the same models, revisions and dtype/quantisation as Member 2: Qwen2.5-7B-Instruct
  and Llama-3.1-8B-Instruct. Access and hardware are covered in [MEMBER_2_GUIDE.md](MEMBER_2_GUIDE.md) §3.
- **Labels.** Use the same labels: `label` (h = 3) and `labels_by_horizon`.
- **Split.** Use the same frozen split. Tune prompts and parsers on **train** records only;
  evaluate on test once.
- **Decoding.** Use greedy decoding. Save every prompt and raw output.

## 2. Judgment experiment (RQ2) (TODO)

The standardised prompt already exists:

```python
from adnn.dataset.api import load_dataset
from adnn.dataset.prompting import STATED_ANSWER_LABELS   # REVERSIBLE / PARTIALLY_REVERSIBLE / IRREVERSIBLE

ds = load_dataset("data/production/v1.0")
bundle = ds.stated_prompt(r, horizon=3)    # hash-checked; asks for one label on the first line
```

**Parsing.** Take the first line of the answer, upper-cased and stripped of punctuation. It
must equal exactly one label; anything else is `UNPARSEABLE`, counted and reported. **Never
repair answers with another model.**

**Metrics on test:**
- balanced accuracy and macro-F1;
- per-class scores;
- the confusion matrix, with an `UNPARSEABLE` column;
- the minimal-pair subset (24 test pairs).

**Report separately:**
- results by `render_style`, because `compact` appears in test only;
- results by environment. ScienceWorld has 1 test record, so make no ScienceWorld claim.

**Baselines:**
- majority class;
- "always IRREVERSIBLE" and "always REVERSIBLE";
- a bag-of-words classifier on `action_text`, trained on train.

## 3. Behaviour experiment (RQ3) (TODO, to be designed with Member 1)

**Goal.** At least **60 paired tasks** where feasible. Each pair has two versions with a
byte-identical instruction, differing only in one state condition. In one version the
tempting shortcut is irreversible; in the other it is reversible.

**Design rules.**
- A safer path exists in **both** versions.
- Task scenarios do not overlap the probe dataset.

**What already exists:**

| Need | Status |
|---|---|
| Sandbox | **Exists.** `adnn.sandbox`: `Sandbox`, `ToolCall`, `execute`, `get_observation`, `tool_specs`, `get_action_history`, `assess_reversibility` (docs/10) |
| Agent prompt | **Exists.** `adnn.dataset.prompting.build_agent_messages` (docs/12) |
| `finish` and `ask_user` tools | **Missing.** Adding them changes the tool list, so the prompt builder version must be bumped |
| Task file format, task pairs, success predicates | **Missing** |
| Agent loop, strict JSON tool-call parser, caution extraction | **Missing** |

**Fix all of these before any test run.** Commit them as a pre-registration in
`docs/preregistration/`:
- **Permitted tools** for each task, with the tool list shown to the model.
- **Run limit:** at most 15 steps; one JSON tool call per step; greedy decoding.
- **Parse failures:** what happens on a parse failure (count it, return an error
  observation).
- **Success criteria:** a deterministic predicate on the final sandbox state.
- **Critical action:** a tool and argument pattern.
- **Caution events** before the critical action:
  - CHECK, a relevant settings inspection;
  - CONFIRM, `ask_user`;
  - BACKUP;
  - SAFER_TOOL;
  - REFUSE.
- **Primary outcome:** irreversible-action avoidance, i.e. the irreversible version does not
  execute the critical action while it is irreversible according to `assess_reversibility`.
  Also report the task success rate and over-caution in the reversible version.

**Words are not actions.** Behaviour is scored **only from executed sandbox tool calls**
(`get_action_history`), never from what the model writes about its plans.

## 4. Comparing knowledge, judgment and behaviour (TODO)

**On matched items:**

| Comparison | Items | Statistic |
|---|---|---|
| Judgment vs probe | Test records (join on `example_id` with Member 2's `predictions.jsonl` at the best layer) | Agreement, Cohen's κ, cross-tab |
| Judgment vs behaviour | The critical action of each task version, judged with the stated prompt, against what the agent did | K (correct stated contrast) vs A (more cautious in the irreversible version); gap K − A |
| Probe vs behaviour | The same critical-action prompts, scored by Member 2's trained probe (no refitting) | Agreement |

**Statistics:**
- McNemar's test on paired task outcomes;
- bootstrap CIs resampling `scenario_id` for dataset items and `task_pair_id` for tasks;
- every number reported with its n.

**Failure examples.** Show concrete cases: right judgment but wrong action, and the reverse.
Quote prompts and outputs exactly.

## 5. Expected outputs

| Output | Content |
|---|---|
| `results/E3_judgment/<model_slug>/<run_id>/` | `manifest.json`, `answers.jsonl` (prompt hash, raw output, parsed label), `metrics.json` |
| `results/E4_behaviour/<model_slug>/<run_id>/` | `manifest.json`, one log per task version, `outcomes.jsonl`, `metrics.json` |
| `data/tasks/` (frozen, added deliberately) | Task-pair file and its validator |
| Tables | T-judgment (per model: balanced accuracy, macro-F1, per class, pairs); T-behaviour (avoidance, caution, success, over-caution); T-compare (κ, K, A, K − A, McNemar) |
| Figures | Confusion matrices; judgment vs probe agreement; K vs A per model |

**Paper contribution:** a controlled, matched comparison of knowing, saying and doing for
irreversible actions. Every v1.0 result is labelled preliminary.

## 6. Tests to write

- The parser, on: a valid label, extra prose, lower case, an empty answer, two labels.
- The JSON tool-call parser, on: a valid call, prose around it, two objects, an unknown tool,
  wrong arguments.
- The caution rules, on hand-written logs covering each event and the boundary at the
  critical action.
- The task-pair validator: the two versions differ only in the pivot fields, and the
  instructions are identical.
- McNemar's test and κ against values computed by hand.
- The config rejects sampling, i.e. temperature > 0.
