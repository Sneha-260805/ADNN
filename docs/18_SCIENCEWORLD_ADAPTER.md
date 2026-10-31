# 18 — ScienceWorld Replay and State-Capture Adapter (Phase 4C)

Owner: **Sneha (M1)**. Code: `src/adnn/scienceworld/`. Status: **implemented and tested against the pinned simulator; no restoration oracle, no labels.** Predecessors: `16_SCIENCEWORLD_FEASIBILITY.md`, `17_SCIENCEWORLD_REPRODUCIBILITY.md`.

> **Scope guardrail.** This adapter reconstructs and describes ScienceWorld states. It does **not**:
> - decide exact or partial restoration;
> - search for restorations;
> - infer irreversibility (including from mixing or object deletion);
> - generate dataset examples or minimal pairs.
>
> Those depend on OQ-03, OQ-30 and OQ-31.

## 1. Modules and public API

`import adnn.scienceworld` never imports `scienceworld`, `py4j` or starts Java (tested). ScienceWorld stays an optional dependency, and ordinary ADNN tests run without it.

| Module | Public names | Role |
|---|---|---|
| `provenance.py` | `PINNED`, `SimulatorPin`, `RuntimeConfig`, `RuntimeProvenance`, `resolve_runtime`, `ScienceWorldUnavailableError`, `UnpinnedRuntimeError` | Locate and verify the pinned runtime (no JVM launch) |
| `env.py` | `ScienceWorldSession`, `StepResult`, `classify_observation`, `ProcessLeakError`, `SessionStateError` | One JVM per session: load/reset/step/look/inventory/object tree/valid actions/moves; leak-checked close |
| `replay.py` | `ReplayRecipe`, `ReplayResult`, `replay`, `replay_in_fresh_process`, `compare_results`, `assert_reproducible`, `TraceComparison`, `FIRST_TICK_PREPARATION`, `InvalidReplayActionError`, `EpisodeTerminatedError`, `ReplayDivergenceError` | Immutable recipes, fresh-environment replay, outcome validation, divergence reports |
| `canonical.py` | `RawState`, `CanonicalState`, `CapturedState`, `capture_state`, `canonicalize`, `CANONICAL_RULES`, `CANONICAL_VERSION` | Raw diagnostic state and canonical comparison state |
| `diagnostics.py` | `raw_diff`, `canonical_diff`, `projection_diff`, `Projection`, `DISCRETE_EXPLORATION`, `StateDiff` | Difference reports with explicit ignored fields, tolerances and completeness |

## 2. Runtime setup and pinned provenance

The isolated runtime from Phase 4B (`17` §2) is selected **explicitly**. Nothing is downloaded or installed, and no global setting changes.

| Variable / field | Meaning |
|---|---|
| `ADNN_SW_JAVA_HOME` / `RuntimeConfig.java_home` | JDK directory (e.g. `%LOCALAPPDATA%\adnn-sw\jdk\jdk-21.0.13+9`) |
| `ADNN_SW_SITE_PACKAGES` / `RuntimeConfig.site_packages` | Site-packages of the isolated ScienceWorld venv (`…\venv-e8216d6\Lib\site-packages`). Appended to `sys.path` of **this process only** |

**Accepted build** (`provenance.PINNED`). Anything else raises `UnpinnedRuntimeError`, whatever the package version string says:

| Check | Required value |
|---|---|
| `scienceworld.jar` SHA-256 (the simulator) | `e77b0fee7d68abe3ca5b12e57d86e2bfe7603f20c5200da0b0f085939faeb465` |
| package version | `1.3.0` |
| source archive SHA-256 from pip's `direct_url.json` (when recorded) | `d2c1dc1e5d0d4e4a104424598dce13f64c6e80c523212936f97ea85c871bfae6` |
| source commit (identified by the above) | `e8216d6044e8e39be9fcb185e3b2dfb602584b52` |

`RuntimeProvenance` records:

- package directory and version;
- JAR SHA-256;
- source-archive hash and URL;
- Java executable and `java -version` lines;
- py4j version, gateway-JAR path and SHA-256;
- Python version and platform;
- the configured site-packages.

It is attached to every `ReplayResult`.

**Launch context.** These settings are process-local and restored right after the JVM starts:

- ScienceWorld does not pass a Java path to py4j, so the JDK's `bin` is prepended to `PATH`.
- py4j looks for its gateway JAR in the current directory first. When the interpreter is not the isolated venv's own, none of its other search paths match, so the working directory is switched to the **verified** py4j JAR's folder.

Sessions should therefore be started from one thread at a time.

## 3. Sessions and action outcomes

```python
from adnn.scienceworld import RuntimeConfig, ScienceWorldSession, capture_state

with ScienceWorldSession(RuntimeConfig.from_env()) as s:      # verifies the pin, starts one JVM
    s.load("1-1", 0, "teleportAction")                        # load + reset
    r = s.step("wait1")                                       # StepResult
    print(r.status, r.moves_before, r.moves_after, r.advanced_time)   # accepted 0 2 True
    state = capture_state(s)                                  # free actions only; no time passes
# on exit: env.close(), then wait for the JVM; a JVM that does not exit is killed -> ProcessLeakError
```

`StepResult.status` comes from the simulator's own text:

- `invalid`: starts with "No known action matches that input.";
- `ambiguous`: starts with "Ambiguous request";
- `accepted`: anything else.

The moves before and after each step are recorded, so time semantics (`17` §4.3) are visible per step.

## 4. Replay recipe schema (`sw-replay-1`)

| Field | Type | Meaning |
|---|---|---|
| `schema` | `"sw-replay-1"` | Recipe format version |
| `task` | str | Exact task identifier passed to `load` (e.g. `"1-1"`) |
| `variation` | int ≥ 0 | Variation index (never `get_random_variation_*`, which is unseeded) |
| `simplifications` | str | Normalised: comma-separated, trimmed, sorted, deduplicated |
| `preparation` | list[str] | Explicit preparation actions run first and recorded as phase `preparation`, e.g. `FIRST_TICK_PREPARATION = ["wait1"]` to pass the object-creating first tick |
| `actions` | list[str] | Ordered actions (phase `action`) |
| `step_limit` | int | Passed as `envStepLimit`; the recipe may not be longer |
| `simulator` | object | `SimulatorPin` (commit, version, JAR and archive SHA-256). Replay refuses a recipe recorded for another pin |

Recipes are frozen dataclasses. They round-trip through JSON, `from_dict` rejects unknown fields (e.g. a stray `label`), and `extend()` returns a new recipe.

**Replay semantics:**

- `replay(recipe, capture="final"|"all", strict=True)` opens a fresh session and runs `load` + `reset`.
- It captures the initial state, then runs every step and records its `StepResult`. With `"all"` it captures the full state after every step.
- With `strict=True`:
  - an `invalid`/`ambiguous` action raises `InvalidReplayActionError`;
  - an episode that ends before the last action raises `EpisodeTerminatedError`.
- `compare_results(a, b)` compares, step by step, the action, status, observation, reward, score, done flag, moves before and after, and the raw and canonical fingerprints. It reports the **first divergent step** (−1 = initial state, `len(steps)` = final state) and the divergent fields.
- `assert_reproducible([...])` raises `ReplayDivergenceError` on the first divergence.
- `replay_in_fresh_process(recipe)` runs the same replay in a new Python process (and JVM), via `python -m adnn.scienceworld.replay`, which writes its result to a file.

```python
from adnn.scienceworld import FIRST_TICK_PREPARATION, ReplayRecipe, assert_reproducible, replay, replay_in_fresh_process

recipe = ReplayRecipe("1-1", 0, "teleportAction", preparation=FIRST_TICK_PREPARATION,
                      actions=("teleport to kitchen", "activate stove"))
a = replay(recipe, capture="all")
b = replay_in_fresh_process(recipe, capture="all")
assert_reproducible([a, b])          # raises ReplayDivergenceError with the first divergent step
```

## 5. State capture and completeness limits

`capture_state(session)` uses only free calls: `getObjectTree()`, `look()`, `inventory()`, valid actions, moves. **No simulation time passes during capture** (verified: raw fingerprints are unchanged by capture plus `look around`).

**A. `RawState`** (diagnostics; everything kept):

- object tree exactly as returned;
- `look()` text;
- `inventory()` text;
- `moves`;
- sorted valid-action list.

**B. `CanonicalState`** (comparison; `CANONICAL_VERSION = "sw-canonical-1"`):

| Rule | Normalisation |
|---|---|
| R1 identity | One record per tree object, keyed by its simulator **uuid**. **No uuid-free remapping.** uuids were identical across resets and fresh processes on the pinned build (`17` §4.2, re-confirmed in §9) |
| R2 structure | Nesting → `parent` (uuid) + `path` (names, for readability) |
| R3 properties | Each `prop*` block is flattened to `<block>.<field>`; absent blocks are kept as `<block>: null`; **nothing dropped** (unit test: canonical field count = tree leaf fields + 2 per object) |
| R4 types | `propContainer.isContainer` is emitted as the string `"true"`/`"false"` → boolean. All other values keep their JSON type |
| R5 numbers | Temperatures and other floats kept **exactly** (no rounding, no tolerance) |
| R6 world | `moves`; `agent_location` = room containing the agent object (cross-checked against the `look()` header; a mismatch is recorded in `notes`) |
| R7 doors | `visible_doors` parsed from `look()` lines `A door to the <room> (that is open\|closed)`: **current room only** |
| R8 excluded (kept in raw) | `look()`/`inventory()` text, valid actions, task description, score |

**Completeness: every canonical state is marked incomplete** (`is_complete == False`), with these reasons:

- `portals_absent_from_object_tree`: doors are not tree objects (`17` §4.4);
- `doors_outside_current_room_not_observable`: door states are known only for the agent's room;
- `agent_internal_state_not_exposed(wait_counter,focus_monitor,goal_progress)`.

Consequences:

- A comparison may report `equal_on_observed_fields`, but `supports_exact_equality_claim` stays `False` while any reason applies.
- Identical text never implies identical state (tested: same `look()` text with a different tree is reported as different).

Size, measured in the kitchen of `1-1` v0: **351 objects, 6,428 canonical fields, ≈254 KB raw JSON, 2,734 valid actions.**

## 6. Comparison diagnostics

| Function | Compares | Reports |
|---|---|---|
| `raw_diff(a, b)` | Every leaf of the raw state (tree, texts, valid actions, moves) | All changed paths |
| `canonical_diff(a, b, ignore=(), tolerances={})` | Canonical fields per shared uuid, world fields, visible doors | Changes; created/deleted objects (uuid, name); **ignored patterns + count of ignored differences**; **tolerances + count within tolerance**; union of incompleteness reasons; notes (e.g. different rooms) |
| `projection_diff(a, b, projection)` | `canonical_diff` with a named `Projection` | Same, flagged `exploratory=True` |

`DISCRETE_EXPLORATION` ignores `propMaterial.temperatureC`, `propMaterial.combustionTicks` and `world.moves`, to show discrete effects. Its declared purpose: *"Exploration only … Not an approved definition of exact or partial restoration (OQ-30)."*

Example (measured, `1-1` v0, kitchen): `activate stove` under `DISCRETE_EXPLORATION` reports exactly `stove.propDevice.isActivated` and `stove.propHeatSource.curSetTemp`, with 82 ignored differences (temperatures and moves). It is reported with `supports_exact_equality_claim = False`.

## 7. Integration findings reproduced by the adapter (pinned build)

| Behaviour | Result |
|---|---|
| 10 resets in one session | identical raw and canonical fingerprints |
| 3 in-process replays of the upstream boil trace (`capture="all"`) | identical at every step; final `look()` contains "a substance called steam" |
| Fresh-process replays vs in-process | identical (2 in the test suite; 3 more in `adapter_check.py`) |
| Door open/close | object tree has no portal data; the only discrete change is `door:kitchen` closed→open→closed |
| Stove on/off | exactly `propDevice.isActivated`, `propHeatSource.curSetTemp`; off again equals the earlier off-state on discrete fields (temperatures differ: ignored and counted) |
| Timed action (`wait1`) | temperatures change; no objects created after the first tick |
| First tick | creates objects (`water`, plus terminals) |
| Mixing (`6-1` v0 gold path) | deletes `sodium chloride` and `water`, creates `salt water` (new uuid). **Recorded as a state difference only; no irreversibility inferred** |
| `look around`, invalid input | `advanced_time == False`; raw fingerprint unchanged |
| Leaks | JVM exited after normal exit, after an exception inside the session, and after a failed strict replay; `java.exe` count unchanged |
| Divergence | a tampered reference (moves at step 3) is reported as first divergence at step 3, field `moves_after`; untampered replays compare identical |

## 8. Running the tests

```bash
# unit tests (no Java / ScienceWorld needed) — part of the normal suite
.venv/Scripts/python.exe -m pytest -q tests/test_scienceworld_adapter.py

# optional integration tests against the pinned runtime (skipped with a reason otherwise)
SW="$LOCALAPPDATA/adnn-sw"
ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" \
ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
  .venv/Scripts/python.exe -m pytest -q -m scienceworld tests/test_scienceworld_integration.py

# overhead / agreement measurement (writes results/scienceworld_adapter/adapter_check.json)
ADNN_SW_JAVA_HOME=… ADNN_SW_SITE_PACKAGES=… .venv/Scripts/python.exe scripts/scienceworld/adapter_check.py
```

Results of the runs on 2026-10-31 are in §9.

## 9. Measured results (2026-10-31, Windows 11, Python 3.11.9, Temurin 21.0.13+9)

| Measurement | Value |
|---|---|
| Unit tests (`test_scienceworld_adapter.py`, no runtime) | 35 passed in 0.65 s |
| Full suite without runtime | 454 passed, 13 skipped |
| `java.exe` processes left after all runs | 0 |
| Integration tests without runtime | 13 skipped (reason: "package 'scienceworld' is not importable; set ADNN_SW_SITE_PACKAGES …") |
| Integration tests with runtime | **13 passed** (two runs: 72.1 s, 70.7 s; the second after the final lint-only refactor) |
| `adapter_check.py` agreement (two runs) | each run: 2/2 in-process (final capture), 2/2 in-process (all captures), 3/3 fresh-process vs in-process: identical |
| Replay of the 5-action boil trace | 3.28–3.87 s (final capture); 4.05–4.24 s (capture every step); JVM start 1.04–1.16 s |
| Fresh-process replay (wall clock) | 4.72–5.17 s |
| `capture_state` (kitchen) | mean 0.187–0.198 s, max 0.35–0.39 s |

## 10. Known limitations

- Door states only for the current room, and agent-internal state is not exposed, so canonical states are **incomplete by construction**.
- uuid identity is valid within one (task, variation, simplifications) on the pinned build. Comparing states where objects were *re-created* (e.g. pour back, re-mix) needs a structural mapping that is not implemented: uuids differ even if the "same" substance reappears.
- The launch context changes the process working directory and `PATH` briefly, so sessions are not thread-safe to start.
- Determinism evidence covers the tested traces (boil, door, stove, mixing, resets); it is not a proof for all tasks.
- Capture costs ≈0.19 s per state. Capturing every step of long traces is expensive.
- `wait1` advances `moves` by 2 (as observed); the exact iteration accounting is not traced in source.

## 11. Professor and team decisions still required

- **OQ-30:** restoration target under autonomous dynamics (temperatures change every tick).
- **OQ-31:** labelling without complete search (inverse-action domains + certificates).
- **OQ-03:** partial restoration in ScienceWorld.
- **OQ-35:** time semantics differ from the sandbox (invalid input costs no time here).
- **OQ-36 (new):** whether current-room door observation is acceptable for canonical state, or door actions must be excluded or handled by visiting rooms.
- **OQ-29:** pin `e8216d6`; empirical evidence in `17`; team to confirm.
