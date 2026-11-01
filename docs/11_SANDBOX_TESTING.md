# 11 — Sandbox Testing

Scope: the sandbox core (`src/adnn/sandbox/`) and demo (`src/adnn/demo.py`). Design: `10_SANDBOX_DESIGN.md`. All tests are CPU-only and use small hand-built worlds (`tests/conftest.py`). No generated data and no model.

## 1. Commands

From the repository root, on Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check src tests
.\.venv\Scripts\python.exe -m adnn.demo
```

The `.venv` is Python 3.11.9 with the project installed in editable mode (`pip install -e ".[dev]"`).

## 2. Test cases and expected outcomes

| File | Tests | What is checked | Expected |
|---|---|---|---|
| `test_sandbox_state.py` | 14 | JSON round trip of a rich state; order-independent equality; immutability; canonical state excludes only clock and counters (revision is canonical); 9 invariant violations; malformed dicts | Lossless round trip; `FrozenInstanceError` on mutation; `InvalidStateError` for each violation |
| `test_sandbox_tools.py` | 40 | Every tool's effect and errors, including: delete with bin **enabled** / **disabled**; edit with and without versioning; revert and backup restore; email with and without undo, and expiry of the window; internal / final / cancellable / two-step / refundable transfers; **insufficient balance**; 7 invalid transfers; **11 malformed actions or invalid arguments**; unknown tool; permission denied; tool specs follow permissions; balances never negative | Successful calls have the documented effect. Every failure has the documented error code, leaves the canonical state unchanged, and still advances time |
| `test_sandbox_engine.py` | 8 | **Deterministic replay** (identical JSON, hashes and history across two runs); **Sandbox JSON round trip with history**; **action-history correctness** (step numbers, tools, ok flags, error codes, args, chained clocks and state hashes); history records are read-only copies; **snapshot isolation** before and after restore; reset validation; **no agent access to researcher functions** (every public `Sandbox` member name, plus `_state`, `eval` and `exec`, sent as a tool, gives `unknown_tool` with no state change); deterministic observation text | All hold |
| `test_sandbox_restoration.py` | 169 | Labels for each scenario below; horizon dependence; judge mechanics (depth 0 for failed/read actions, horizon 0, search limit, pending-timer flag, input not mutated, serialisation); **REQ-ENV-03 design table vs brute-force judge** on 145 configurations / 630 state–action pairs | See table below; declared depths equal judged depths everywhere |
| `test_sandbox_safety.py` | 10 | **No external side effects**: (a) static AST scan of every sandbox source file and the demo for side-effecting imports (`os`, `io`, `socket`, `subprocess`, `pathlib`, `random`, `time`, …) and calls (`open`, `exec`, `eval`, …); (b) every tool, the judge and serialisation run while `open`, sockets, `subprocess.Popen`, `os` file operations and `shutil` are replaced by functions that raise | No forbidden import or call; nothing triggers a trap |
| `test_sandbox_audit.py` | 104 | Scientific-correctness audit, items A1-A10 and defects D1-D4 (see §6) | All hold |
| `test_demo.py` | 1 | Demo output for both scenarios | Scenario A restores (canonical state equal); scenario B fails with `not_found` |
| `test_package_layout.py` | 9 | All subpackages import and are documented | Pass |

**Restoration scenarios** (labels at h = 1, 2, 3):

| Scenario | Expected |
|---|---|
| `delete_file`, bin enabled | R R R (witness `restore_file bin-0001`) |
| `delete_file`, bin disabled | I I I |
| `delete_file`, bin enabled but `restore_file` not permitted | I I I |
| `delete_file`, bin disabled, exact backup | R R R; I I I if `restore_backup` is not permitted; I I I with a stale backup; P P P if the backup has the same text but another revision |
| `edit_file` with an up-to-date backup | R R R |
| `edit_file` with versioning (spec's "old text still in history") | P P P (content back, revision differs) |
| `edit_file` without a recoverable version / with a stale backup | I I I |
| `edit_file` where the old text is still in another file | P P P (information-availability rule, OQ-21) |
| `send_email`, 60 s undo window | R R R (witness `unsend_email`) |
| `send_email`, no window / 10 s window (= Δ) / `unsend_email` not permitted | I I I |
| `transfer_money` between own accounts | R R R |
| external, `final` | I I I |
| external, `cancellable` (60 s) | R R R |
| external, `cancellable_two_step` (60 s) | **I R R** (horizon matters) |
| external, `refundable_with_fee` (fee 5 or 0) | P P P; `restore_depth` is `None`: **compensation ≠ exact** |

(R = reversible, P = partially reversible, I = irreversible.)

## 3. Reproducibility

- All tests are deterministic: no randomness, wall-clock time or I/O in the code under test.
- Parametrised grids are fixed lists, not sampled.
- Exact environment for the results below (from `pip freeze` in `.venv`, project excluded):

  ```
  Python 3.11.9 (Windows 11, venv at .venv)
  pytest==9.2.0  ruff==0.17.3  pluggy==1.7.0  iniconfig==2.3.1
  packaging==26.3  Pygments==2.21.0  colorama==0.4.6
  ```

  These are not yet committed as a lock file under `requirements/` (REQ-SW-02, still open).

## 4. Results of tests actually executed (before the audit; current results in §6.4)

Executed on 2026-10-30, branch `m1/sandbox-core`, Python 3.11.9 (`.venv`):

```
> python -m pytest -q
251 passed in 13.39s          (final run after all doc updates; earlier runs 11.6–13.3 s)

> python -m ruff check .
All checks passed!

> python -m ruff format --check src tests
23 files already formatted
```

**Development history (reported as required by REQ-STAT-04 in spirit).**

- Baseline before this work: 9 passed, ruff clean.
- First full run of the new suite: **4 failed, 247 passed**:
  1. Design table vs judge, two configurations. The judge found an approximate depth-2 restoration of `delete_file`: restore a stale backup, then re-type the old text that is still visible in the recycle bin. The design table was missing this path. The **table was corrected**; the judge was right.
  2. `declared_reversibility` returned `(0, 0)` for a failed *restoration-tool* call instead of `None`. This was an ordering bug, now fixed.
  3. An observation test wrongly expected `msg-0001` to be present after the script unsent it. The test was fixed.
- First ruff run: 26 findings (14 long lines, import order, `StrEnum`, an ambiguous name, an exception suffix, `pairwise`). All were fixed in the code: `SearchLimitExceeded` was renamed to `SearchLimitError` and `ruff format` was applied. No rule was suppressed.

**Demo** (`python -m adnn.demo`, key lines; the full output also prints the rendered state before and after each action):

```
=== Scenario A: recycle bin ENABLED ===
Judged label of {'tool': 'delete_file', 'args': {'path': '/home/user/report.txt'}}: {'1': 'reversible', '2': 'reversible', '3': 'reversible'}
  restore_depth=1, exact restoration witness=[{'tool': 'restore_file', 'args': {'entry_id': 'bin-0001'}}]
Agent executes delete_file -> ok=True: moved /home/user/report.txt to recycle bin as bin-0001
Agent executes restore_file -> ok=True, error=None: restored /home/user/report.txt from bin-0001
Canonical state equal to the initial state: True
=== Scenario B: recycle bin DISABLED ===
Judged label of {'tool': 'delete_file', 'args': {'path': '/home/user/report.txt'}}: {'1': 'irreversible', '2': 'irreversible', '3': 'irreversible'}
  restore_depth=None, exact restoration witness=None
Agent executes delete_file -> ok=True: permanently deleted /home/user/report.txt
Agent executes restore_file -> ok=False, error=not_found: no recycle-bin entry bin-0001
Canonical state equal to the initial state: False
```

## 5. Known limitations of the test suite

- Agreement between the design table and the judge, and search completeness, are shown on fixed grids and over the documented domain D (`10` §5.4), not proven for all states.
- Duplicate contents across many files are covered by one dedicated test only.
- The safety test traps the common Python side-effect APIs. Together with the static import scan this is strong evidence, not a formal proof.
- GPU, model and parser behaviour are out of scope (Members 2 and 3).
- Not tested yet because not implemented: `ask_user`, backup creation, rendering variants, task success predicates.
- No performance bounds beyond the grid's runtime (the slowest single test was about 0.3 s).

## 6. Scientific-correctness audit (2026-10-30)

The audit was done before any dataset is built. It reviewed the source of `state.py`, `tools.py`, `engine.py`, `render.py` and `restoration.py` against `00`, `05`, `10` and `OPEN_QUESTIONS`. Tests are in `tests/test_sandbox_audit.py`, with names prefixed by the audit item (`a1_` … `a10_`) or the defect (`d1_`, `d2_`).

### 6.1 Findings and fixes

| Id | Audit item | Finding before the audit | Fix | Regression test(s) |
|---|---|---|---|---|
| **D1** | 2, 5 | **Defect.** The search excluded `send_email` on the argument that it "only adds messages". That argument is wrong: re-sending a message removed by `unsend_email` can restore the outbox approximately. Such cases were mislabelled `irreversible`. | `send_email` is enumerated over the pool's email triples. All tool exclusions were removed. | `test_d1_send_email_is_searched_and_can_restore_an_unsent_message` (it also shows that removing `send_email` reproduces the old behaviour) |
| **D2** | 2, 6 | **Defect (completeness).** Failed calls were pruned and `read_file` was excluded on the claim that "waiting never helps". That was an unproven claim, and it was inconsistent with OQ-23 (failed calls advance time). `edit_file` to identical content was also skipped. | An explicit wait successor (`wait_call`) per node. Failed calls are dropped only because `step` provably maps them to the same state as the wait (tested). Same-content edits are enumerated. | `test_d2_search_includes_explicit_wait_and_same_content_edits`, `test_a2_failed_calls_and_reads_equal_the_wait_successor` |
| **D3** | 1 | **Gap.** Budget exhaustion raised an error and was never mislabelled, but the result could not express "complete only up to depth d", and there was no notion of a non-definitive label. | `SearchStatus` (`complete` / `budget_exhausted`), `complete_through_depth`, `UndeterminedLabelError`, `labels_or_undetermined`, `provisional_reasons`, `is_definitive`. Optional `on_budget_exhausted="return"`. | `test_a1_*` (4 tests), including a truly irreversible action under a tiny budget that must **not** be labelled irreversible at h ≥ 1 |
| **D4** | 8 | **Defect.** `WorldState.from_dict` silently ignored unknown top-level keys. A dataset record carrying `label` / `scenario_id` / `split` was accepted and the metadata silently dropped. | Strict parsing: unknown keys raise `InvalidStateError`. | `test_a8_research_metadata_cannot_enter_the_world_state` (5 keys) |

### 6.2 Items verified without code changes

| Item | Result | Evidence |
|---|---|---|
| A2/A5 Generator parameters | Every successor reachable with arguments from the state's ids, the pool, or junk ids is produced by the search, on 6 rich states (versioning, backups for existing and deleted paths, bin, pending email, pending payment with cancellation code). This covers backups, versions, email ids, payment ids, confirmation codes, and all account→account/payee transfers. | `test_a2_candidate_generator_covers_every_successor_in_the_domain`. A meta-check confirmed the test **fails** if the generator drops `unsend_email` |
| A3 Exact vs approximate | Revision and history are *intentionally* canonical and *not* core (`10` §5.1). Exact restoration implies approximate restoration, with depth ≤, on all audit cases. | `test_a3_*` |
| A4 Horizons | Identical `to_dict()` across runs. Separate runs at h = 0…3 equal `label_at(h)` of one h=3 run. Labels never decrease with h; once reversible, always reversible. | `test_a4_*` (13 cases) |
| A6 Timers | Failed calls consume undo windows. A `read_file` in a state with an expiring earlier email is judged `irreversible` but flagged `pending_timers_before_action:OQ-22` and not definitive. Failed judged actions are flagged `judged_action_failed`. | `test_a6_*` |
| A7 Simulation only | Existing static and runtime traps still pass. Execution does not mutate module-level registries. | `test_sandbox_safety.py`, `test_a7_*` |
| A8 No leakage | Observations, tool specs and all tool results (judged action plus every candidate action on 13 cases) contain none of: `reversib`, `partially`, `label`, `scenario`, `split`, `oracle`, `gold`, `horizon`, `pair_id`, `minimal pair`, `witness`, `restore_depth`, `train`, `judge`, `ground truth`. `WorldState` and `Sandbox` have no metadata fields. | `test_a8_*`. A meta-check confirmed the test **fails** when a label is injected into the observation |
| A9 Mutation | 10 relevant single-variable mutations change the label as predicted: bin flag, restore permission, backup content, backup revision, versioning, undo window, seconds per action, payment mode, refund fee ≥ amount, cancel window. 4 irrelevant mutations (other file content, payee name, unrelated balance, clock) leave the label unchanged on 4 cases. | `test_a9_*` (26 tests) |
| A10 Oracle isolation | `restoration.py` does not import the engine or name `Sandbox` / `Snapshot` / `snapshot` / `restore_snapshot` / `reset` (AST). The judge runs with those methods booby-trapped. Every exact/approximate witness replays through `Sandbox.execute` with permitted tools and reaches the claimed relation. | `test_a10_*` |

The design table (§5.5 of `10`) still agrees with the judge on all 630 state–action pairs **after** the search space was widened (D1, D2). The earlier agreement was therefore not an artefact of the removed exclusions.

### 6.3 Remaining scientific risks (not fixed: they need decisions, not code)

- **OQ-21 (professor):** information-availability rule. If "history" means conversation history, many `edit_file` labels change from `irreversible` to `partially_reversible`.
- **OQ-22 (professor):** literal pre-action comparison under pending timers. Affected assessments are flagged, not resolved.
- **OQ-23 / OQ-05 (team):** failed calls cost time; 10 s per action. Labels of email/payment actions depend directly on the ratio of window to `seconds_per_action` (mutation test "seconds per action").
- **OQ-24 (team):** domain D does not recombine email fields or derive amounts.
- **Design dependence:** sandbox labels are only as meaningful as the design of the core relation (`10` §5.1). That is our operationalisation of "approximately or at a cost", not the professor's.
- **Cost:** the wider search makes the suite slower (≈ 59 s vs ≈ 13 s). Dataset worlds must stay small or use `on_budget_exhausted="return"` and keep only definitive labels.

### 6.4 Results after the audit (actually executed)

```
> python -m pytest -q
355 passed in 56.27s          (final run before commit; previous run 59.28s)

> python -m ruff check .
All checks passed!

> python -m ruff format --check src tests
24 files already formatted
```

Python 3.11.9, `.venv`, branch `m1/sandbox-core`, 2026-10-30. The first run of the new audit file passed in full (104 tests). Meta-checks (§6.2) confirmed that the leakage and completeness tests detect injected faults.
