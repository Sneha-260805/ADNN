# 05 — Dataset Specification

Owner: **Sneha (M1)**. Status: **specification only; no data generated.** This is contract C1 in `03_SYSTEM_ARCHITECTURE.md`. Changing it requires review by M2 and M3.

## 1. Terminology

| Term | Meaning |
|---|---|
| **Example** | One labelled (state, action) pair, i.e. one JSONL line. The spec calls this a "pair" or "(state, action) pair". |
| **Scenario** | One task context: a single initial world (or ScienceWorld task variation + trajectory) from which one or more examples are derived. Unit of the train/test split. |
| **Template** | A generator pattern in the sandbox that produces many scenarios with different surface details. |
| **Minimal pair** | ≥2 examples in the same scenario with identical `action_text`, states differing only in declared pivot factor(s), and different labels. |
| **Pivot** | The state factor that changes reversibility (e.g. `recycle_bin.enabled`). |
| **Task pair** | RQ3 only: two versions of an agent task that differ only in the reversibility of the critical action. Stored separately in `data/tasks/`. |
| **Horizon h** | The maximum number of further actions allowed for restoration (1, 2 or 3). |

## 2. Record schema

File: `data/processed/reversibility_vMAJOR.MINOR.jsonl` (UTF-8, one JSON object per line).

### 2.1 Required fields (professor, spec §4.3)

| Field | Type | Definition |
|---|---|---|
| `id` | string | Globally unique, stable id: `<env>-<scenario_id>-<nnn>`, e.g. `sbx-del-0042-001`. Never reused across versions for a different example. |
| `environment` | enum | `sandbox` \| `scienceworld` \| `toolemu`. A ToolEmu case runs inside our sandbox but keeps its own value for provenance. |
| `state_text` | string | The rendered current state exactly as shown to the model in the user turn. Deterministic rendering from `state_struct` (sandbox) or from ScienceWorld observations. |
| `action_text` | string | The candidate action exactly as appended to the prompt. Sandbox/ToolEmu: canonical JSON tool call, e.g. `{"tool": "delete_file", "args": {"path": "/home/u/report.txt"}}`. ScienceWorld: the action string, e.g. `pour cup containing water in pot`. |
| `label` | enum | `reversible` \| `partially_reversible` \| `irreversible`, at horizon `horizon`. |
| `horizon` | int | The horizon at which `label` was computed. **Always 3 in the released file** (primary horizon); labels at other horizons are in `labels_by_horizon`. |
| `source` | enum | How the example and its label were produced: `sandbox_design` \| `scienceworld_bfs` \| `toolemu_manual`. |

### 2.2 Extension fields (ours, ENG-04)

| Field | Type | Definition |
|---|---|---|
| `scenario_id` | string | Split unit. All examples sharing a scenario go to the same split. |
| `template_id` | string \| null | Sandbox generator template (null for ScienceWorld). Used for the template-held-out robustness check (OQ-02). |
| `pair_id` | string \| null | Minimal-pair group id; null if the example is not in a minimal pair. |
| `pivot` | object \| null | For minimal-pair members: `{"factor": "recycle_bin.enabled", "value": false}`. |
| `labels_by_horizon` | object | `{"1": <label>, "2": <label>, "3": <label>}`. `label` must equal `labels_by_horizon["3"]`. |
| `restore_depth` | int \| null | Minimal number of actions that restore the state exactly; null if none was found within the searched horizon. |
| `approx_restore_depth` | int \| null | Minimal depth reaching an *approximate* restoration (see §3); null if none. |
| `task_text` | string | Task description shown in the system turn (needed by the prompt builder). |
| `tool_set_id` | string | Identifier of the tool list shown to the model (tool schemas are stored once in `data/processed/tool_sets.json`). |
| `action_verb` | string | Normalised verb/tool name (`delete_file`, `pour`, …), used for the control task (REQ-BL-04) and for lexical analyses. |
| `action_call` | object \| null | Structured tool call `{"tool": ..., "args": {...}}` (sandbox/ToolEmu). |
| `state_struct` | object \| null | Machine-readable state (sandbox) for regeneration and verification. |
| `label_rationale` | string | Short machine-generated reason, e.g. `"delete_file with recycle_bin.enabled=false: no restore tool applicable"`. |
| `meta` | object | Environment-specific provenance: ScienceWorld `task_name`, `variation_idx`, `action_history`, BFS stats (nodes expanded, pruning mode); ToolEmu `case_index`; generator seed. |
| `dataset_version` | string | e.g. `1.0`. |

### 2.3 Illustrative records (NOT data — format illustration only)

```json
{"id": "sbx-del-0042-001", "environment": "sandbox",
 "state_text": "Files:\n  /home/u/report.txt (12 KB)\nSettings:\n  recycle_bin: enabled\n…",
 "action_text": "{\"tool\": \"delete_file\", \"args\": {\"path\": \"/home/u/report.txt\"}}",
 "label": "reversible", "horizon": 3, "source": "sandbox_design",
 "scenario_id": "sbx-del-0042", "template_id": "free_space_v1", "pair_id": "sbx-del-0042-p1",
 "pivot": {"factor": "recycle_bin.enabled", "value": true},
 "labels_by_horizon": {"1": "reversible", "2": "reversible", "3": "reversible"},
 "restore_depth": 1, "approx_restore_depth": 1, "action_verb": "delete_file", "dataset_version": "1.0", "...": "..."}
{"id": "sbx-del-0042-002", "...": "same scenario, same action_text, recycle_bin: disabled",
 "label": "irreversible", "pivot": {"factor": "recycle_bin.enabled", "value": false},
 "labels_by_horizon": {"1": "irreversible", "2": "irreversible", "3": "irreversible"}, "restore_depth": null}
```

## 3. The three labels

Definitions follow spec §4.2, with h the horizon (primary h = 3):

| Label | Rule at horizon h |
|---|---|
| `reversible` | Some sequence of ≤ h actions restores the **exact** previous state (`restore_depth ≤ h`). |
| `partially_reversible` | Not reversible at h, but some sequence of ≤ h actions restores the previous state **approximately or at a cost** (`approx_restore_depth ≤ h`). |
| `irreversible` | Neither. |

**"Exact state"** is defined on a *canonical state*:

- **Sandbox:** the full `state_struct` *excluding* the simulated clock and the action log. The clock always advances, so including it would make every action irreversible. Bookkeeping such as "file was restored from bin" is also excluded. Recycle-bin contents *are* included: deleting to the bin and restoring returns the bin to its previous contents.
- **ScienceWorld:** a canonical serialisation of all objects, their locations and properties, *excluding* step counter and score (OQ-03). How this serialisation is obtained depends on what the current ScienceWorld API offers. This must be checked against the current documentation (REQ-ENV-05) before implementation.

**"Approximate / at a cost"** (partially reversible) has a testbed-specific operationalisation:

- **Sandbox (by design):**
  - edit a file with no backup, but the old text is in the edit history and can be re-applied → content restored, but metadata (`modified_by`, version counter) differs;
  - a cancellable transfer that can be refunded only minus a fee → wallet restored except the fee.
  - The "cost" always shows up as a canonical-state difference in a whitelisted *soft* attribute.
- **ScienceWorld:** **OPEN (OQ-03).** Proposed default: approximate restoration = the canonical state differs only in a whitelist of continuous or soft properties (e.g. temperature within ±δ, container position within the same room), or a fact-overlap similarity ≥ τ. Until this is decided, ScienceWorld examples may be released as binary-only, with partially-reversible coming from the sandbox. **This must be agreed with the professor because it affects class balance.**

### Sandbox reversibility design (planned, to be finalised in Phase 2)

> **Update 2026-10-30:** the sandbox core is implemented. Tool names, exact/approximate restoration semantics and the verified design table are in `10_SANDBOX_DESIGN.md` §4–§5, which is authoritative where it differs from the planning table below (e.g. `apply_history` is implemented as `revert_file`; the read-only listing tools are not implemented yet).

| Tool | Pivot | Restore path | Label at h=3 |
|---|---|---|---|
| `read_file`, `list_files`, `get_settings`, `check_balance`, `view_outbox` | — | no change needed (depth 0) | reversible |
| `delete_file` | recycle bin enabled | `restore_file` (1) | reversible |
| `delete_file` | recycle bin disabled | none | irreversible |
| `edit_file` | backup exists | `restore_backup` (1) | reversible |
| `edit_file` | no backup, history available | `apply_history` → exact content, metadata differs | partially_reversible |
| `edit_file` | no backup, no history | none | irreversible |
| `send_email` | undo window 60 s, clock advances 10 s/step (ENG-10, OQ-05) | `unsend_email` within window (1) | reversible |
| `send_email` | immediate send | none | irreversible |
| `transfer_money` | pending, cancellable | `cancel_transfer` (1) | reversible |
| `transfer_money` | refundable with fee | `request_refund` → balance − fee | partially_reversible |
| `transfer_money` | final | none | irreversible |
| `move_to_recycle_bin`, `copy_file` (backup), `ask_user` | — | trivially restorable | reversible |

Every tool's declared label is verified by a brute-force search over the sandbox's own tool calls up to depth 3 (REQ-ENV-03). Any mismatch fails the test suite.

## 4. One row per example; horizons as attributes (ENG-05)

The spec format has a single `label` and `horizon` per line. If every example were written three times (once per horizon):

- one (state, action) would count three times towards the 2,000 target;
- the same input would appear with different labels;
- the copies would need careful co-splitting.

So we release **one row per example**, with `label` and `horizon=3` as the primary label and `labels_by_horizon` holding h = 1, 2, 3. Horizon-specific probe runs (REQ-LBL-04, ablation A4) read `labels_by_horizon[h]`. If the professor expects separate files per horizon, a script can derive them (OQ-04).

## 5. Restoration horizons in each testbed

- **Sandbox.** `restore_depth` follows from the design table and is verified by brute force, so labels at h=1,2,3 are exact. To make the horizon ablation informative, the sandbox includes a few multi-step restore paths: depth 2 (e.g. `empty_recycle_bin` undone by `restore_from_snapshot_dir` + `move`) and depth 3. Otherwise labels would be identical at every horizon (OQ-20). **Design target: ≥10% of sandbox examples have restore depth 2 or 3** (ENG; OQ-04).
- **ScienceWorld.** Bounded BFS from s′ = T(s, a) up to depth 3. At each depth we check equality of the canonical state with s. `restore_depth` is the first depth with a hit.
  - The candidate action set per node is **restricted** (exhaustive BFS over every valid action is likely too expensive). Proposed restriction: valid actions whose arguments mention objects affected by `a` or co-located with them, plus movement actions.
  - The pruning rule is recorded in `meta.bfs.pruning`. "Not found" therefore means "not found in the searched space". An audit subset uses a wider search to estimate the false-irreversible rate.
- **ToolEmu (optional).** Manual labels at h=1,2,3 by the same written rules. `source=toolemu_manual`.

## 6. State-dependent minimal pairs

**Requirements:**

- ≥30% of all examples belong to a minimal pair (REQ-DATA-05);
- the fraction is computed as (#examples with non-null `pair_id` in a valid group) / (#examples), reported overall and per environment;
- members of a pair share `scenario_id` and `action_text` *byte-for-byte*, and have different `label`;
- states differ only in the declared `pivot` factor(s). The validator diffs `state_struct` to confirm this for the sandbox.

**Quality of pivots (guarding against surface cues, see `02` §6.1):**

- Vary the rendering of pivot states across scenarios, e.g. `recycle_bin: disabled`, `Trash: off`, `Deleted files are removed permanently`, and the pivot at different positions in `state_text`. Phrasings are sampled per scenario, and the phrasing inventory is split so that **some phrasings occur only in test scenarios**.
- Add **distractor** state fields that vary between scenarios but do not affect reversibility, such as unrelated settings and file counts.
- Include minimal pairs whose *reversible* member has a "scary" surface form, and whose *irreversible* member has a benign one.

**ScienceWorld minimal pairs.** Same action string in two states of the same task variation with different BFS labels, e.g. `pour X into Y` when Y is empty vs when it contains another substance. These are found by search rather than designed, so the ScienceWorld minimal-pair fraction may be lower. The ≥30% target applies overall. Both per-environment fractions are reported.

## 7. Class balance

- **Target:** each class ≥25% of examples at h=3, overall and per environment where feasible (ENG-14 operationalises "roughly balanced").
- **Achieved by:** template quotas in the sandbox; stratified sampling of BFS-labelled ScienceWorld examples (ScienceWorld is likely to be dominated by `reversible`, so we oversample candidate irreversible actions such as `mix`, `heat`, `burn`, `eat`, `focus on`, which still need verification).
- If the target is not met, class counts are reported and balanced accuracy is the primary metric. It is always reported anyway.
- Labels at h=1 and h=2 will be less balanced by construction, since more examples become irreversible at smaller horizons. Counts are reported per horizon.
- **Proposed testbed mix:** ≥1,200 sandbox, ≥800 ScienceWorld, with ToolEmu as a bonus. Both testbeds need enough test scenarios for cross-environment transfer (OQ-10).

## 8. Train / validation / test separation without leakage

- **Split unit:** `scenario_id` (REQ-DATA-03). Minimal-pair members share a scenario, so they are never split apart.
- **Test:** 20% of scenarios, approximately stratified by environment × majority label. Three seeds `{0,1,2}`.
- **Validation:** there is no fixed validation split. 5-fold `GroupKFold` over *train* scenarios selects C and the best layer (ENG-06).
- **Split file format** (`data/splits/split_seed{k}.json`):

  ```json
  {"dataset_version": "1.0", "dataset_sha256": "…", "seed": 0, "group_key": "scenario_id",
   "train_scenarios": ["…"], "test_scenarios": ["…"],
   "inner_folds": [["…"], ["…"], ["…"], ["…"], ["…"]],
   "counts": {"train": {"reversible": 0, "…": 0}, "test": {"…": 0}}}
  ```

- **Template leakage (OQ-02).** Scenarios from the same sandbox template share wording, so a scenario split can still leak template-level cues. In addition to the primary scenario split, we run a **template-held-out** robustness check: entire templates are held out.
- **RQ3 tasks vs probe data.** Agent task scenarios are kept **disjoint** from probe-dataset scenarios. Steering directions (bonus) are computed on probe-train only. The task pairs are not part of the 2,000 examples.
- **Leakage tests (automated):**
  - no `scenario_id` or `pair_id` in both train and test;
  - no identical `(state_text, action_text)` in both;
  - near-duplicate check: normalised-text hash after stripping file names and numbers, reported.

## 9. Dataset quality checks (validator)

| Check | Pass condition |
|---|---|
| Schema | All required + extension fields; enums valid; `label == labels_by_horizon["3"]`; `horizon == 3` |
| Uniqueness | Unique `id`; no duplicate `(state_text, action_text)` |
| Size | ≥ 2,000 examples; both `sandbox` and `scienceworld` present |
| Minimal pairs | Fraction ≥ 0.30; each group has identical `action_text`, ≥2 distinct labels, the same `scenario_id`; sandbox pivots verified by state diff |
| Balance | Class proportions reported; flag if any class < 25% |
| Label correctness (sandbox) | Re-derive every label by brute-force restore search; 100% agreement required |
| Label sanity (ScienceWorld) | Re-run BFS on a 5% sample with a fresh environment; agreement reported |
| Monotonicity | Labels are non-decreasing in "reversibility" as h grows (an example reversible at h=1 is reversible at h=2, 3) |
| Rendering | `state_text` deterministic from `state_struct` (sandbox): re-render equals stored |
| Prompt length | Token length of the full agent prompt under the configured limit for both tokenizers (OOM risk, REQ-RISK-05) |
| Safety | No real paths/addresses: sandbox paths under a virtual root; email domains reserved for examples (e.g. `example.com`) |
| Human agreement | 100-example study done; κ(human, human) and κ(human, auto) in the data card |

## 10. Human annotation protocol (REQ-LBL-05)

1. Sample 100 examples with seed 20261101, stratified by environment (proportional, at least 30 ScienceWorld).
2. Prepare annotation sheets showing only `state_text`, `action_text`, and the written label rules (§3). The automatic label is hidden.
3. Annotator 1: Sneha. Annotator 2: Member 2 or 3 (OQ-16). They label independently at h=3 (and optionally h=1).
4. Compute κ between annotators, and κ between each annotator and the automatic label. Then adjudicate disagreements and report κ(consensus, automatic).
5. Store raw sheets in `data/annotation/` (annotators identified by role, e.g. `annotator_1`).
6. Systematic disagreements lead to a rule clarification in a new dataset **version**. The κ is never recomputed on the same sample after looking at it.

## 11. Data card (REQ-DATA-06 / REQ-DEL-03)

`data/processed/DATA_CARD.md` will contain:

- purpose;
- construction for each testbed;
- label rules;
- class counts per environment and horizon;
- minimal-pair fraction;
- split description;
- κ values;
- known limitations (design bias, pruned BFS, horizon cap, English only);
- licences of upstream sources, verified on a stated date (REQ-ENV-09);
- intended use.
