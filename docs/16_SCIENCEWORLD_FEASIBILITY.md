# 16 — ScienceWorld Feasibility and API Audit (Phase 4A)

Owner: **Sneha (M1)**. Date: 2026-10-30. Base commit: `38cbf5a` (branch `m1/sandbox-core`). Status: **desk audit only.** ScienceWorld is **not installed** on this machine and **no ScienceWorld code has been run**. Nothing in this document is an experimental result.

## 0. Evidence tags

| Tag | Meaning |
|---|---|
| **[SRC]** | Verified by reading upstream source on `allenai/ScienceWorld` `main` (latest commit `e8216d6044e8e39be9fcb185e3b2dfb602584b52`), fetched 2026-10-30 |
| **[DOC]** | Stated in upstream README / PyPI metadata / paper, not verified in code |
| **[LOCAL]** | Observed on this machine on 2026-10-30 |
| **[ASSUME]** | Our inference; must be verified empirically in Phase 4B |
| **[OPEN]** | Unresolved; listed in §10 and `OPEN_QUESTIONS.md` |

Upstream files read:

- `README.md`
- `setup.py`
- `CHANGELOG.md`
- `LICENSE`
- `scienceworld/scienceworld.py`
- `tests/test_scienceworld.py`
- `simulator/src/main/scala/scienceworld/runtime/pythonapi/PythonInterface.scala`
- `simulator/src/main/scala/scienceworld/runtime/AgentInterface.scala`
- `simulator/src/main/scala/scienceworld/struct/EnvObject.scala`
- `simulator/src/main/scala/scienceworld/properties/{MaterialProperties,ContainerProperties,PortalProperties}.scala`
- `simulator/src/main/scala/scienceworld/actions/{ActionWait,ActionFocus}.scala`

Also consulted:

- the tag and release lists, and the commit log;
- the PyPI JSON API;
- issue #33 ("Heat transfer is stochastic");
- the paper (Wang, Jansen, Côté, Ammanabrolu, *ScienceWorld: Is your Agent Smarter than a 5th Grader?*, EMNLP 2022, arXiv:2203.07540).

## 1. ScienceWorld requirements in our project

| Requirement | Source | What it demands of ScienceWorld |
|---|---|---|
| REQ-ENV-04 | spec §4.1 | Second, compulsory testbed with physical actions (heat, freeze, mix, pour) |
| REQ-ENV-05 | spec §4.1 | Check the API for save/restore. Otherwise use reset + replay, on a *sample* of states |
| REQ-LBL-03 | spec §4.2 | Automatic labels: save state, apply action, BFS over sequences of length ≤ 3, check whether the saved state is reached |
| REQ-LBL-04 | spec §4.2 | Report results for horizons 1, 2, 3 |
| REQ-LBL-05 | spec §4.2 | Human agreement on 100 examples, ≥30 from ScienceWorld (`05` §10) |
| REQ-DATA-01/05 | spec §4.3, §6 | ≥2,000 examples from **both** testbeds; ≥30% minimal pairs overall |
| REQ-DATA-03 | spec §4.3 | Split by task/scenario, not by action |
| REQ-ABL-04 | spec §7.3 | Cross-environment transfer: sandbox ↔ ScienceWorld (compulsory ablation) |
| REQ-ENV-09 | spec §4 | Verify the licence before release |
| OQ-03, OQ-10 | ours | ScienceWorld partial-restoration definition; testbed mix |

**How ScienceWorld differs from our sandbox:**

| Aspect | Sandbox (`10`) | ScienceWorld |
|---|---|---|
| State access | Complete, immutable `WorldState` | Partial: JSON object tree [SRC]; doors may be missing (§3.8) |
| Snapshot / restore | Free (immutable values) | **None** [SRC]; reset + replay only |
| World dynamics | Static except our undo timers | **Autonomous**: every timed action ticks heat transfer and life processes [SRC]/[DOC] |
| Action space | 13 tools, small finite pool | ~25 actions, ~200k template combinations; valid list per state from the current room [SRC]/[DOC] |
| Labels | Designed + verified by complete search | Must be **computed**. Complete search is expensive (§5.4) |
| Minimal pairs | Designed pivots | Must be constructed or found (§6) |
| Runtime | Pure Python | Java JVM via py4j, ~7 MB JAR [SRC]/[DOC] |

## 2. Versions, dependencies, licence

| Item | Finding | Tag |
|---|---|---|
| Latest PyPI release | **1.2.3**, uploaded 2025-07-13; wheel 7,284,687 bytes; `requires_python >=3.7`; `requires_dist: py4j` | [DOC] PyPI JSON; [LOCAL] `pip index versions scienceworld` → 1.2.3 |
| Latest git tag / release | **1.2.3**. **No 1.3.x tag or release** | [DOC] tags/releases pages |
| `main` branch | Version bumped to **1.3.0** in `ad4f284` (2026-08-19). Determinism fixes `784b2dc`, `ae39d37`, `e7395e7`, `9045cb2`, `9cf9a30` (2026-08-04). Heat-transfer fix PR #88. Door-referent fix PR #87 (`e8216d6`, which also updates `scienceworld/scienceworld.jar`) | [DOC] commit log |
| CHANGELOG.md | Stale: last entry 1.1.3 | [SRC] |
| Python | `setup.py`: `python_requires='>=3.7'`; README: "Python 3.8+". The pure-Python wrapper + py4j should work with our **3.11** | [SRC]/[DOC]; 3.11 itself [ASSUME] |
| Java | README: "Java 1.8+"; example `sudo apt-get install openjdk-21-jdk`. `setup.py` performs **no** Java check | [DOC]/[SRC] |
| Bridge | `py4j` `launch_gateway(classpath=JAR, die_on_exit=True, return_proc=True)` on a dynamic port; one JVM per `ScienceWorldEnv` (`test_multiple_instances`) | [SRC] |
| Licence | **Apache License 2.0**, "Copyright 2022 Cognitive AI Lab and Allen Institute for Artificial Intelligence" | [SRC] `LICENSE`; satisfies REQ-ENV-09 for use; re-check at release |
| Native Windows | Not mentioned anywhere upstream; CI targets Ubuntu | [DOC]; Windows support [OPEN] |

**Version decision is scientifically important (OQ-29).**

- The README states that 1.3.0 makes object enumeration deterministic and "fixes stochastic simulation outcomes", but "can change physics trajectories, ambiguous action resolution, gold paths, and observation/JSON ordering compared with 1.2.x" [DOC].
- Issue #33 reports that in 1.2.x the same command sequence sometimes produces steam and sometimes not. It attributes this to `EnvObject` storing contents in an unordered `Set` [DOC].
- On `main`, `getContainedObjects` returns `uuidOrderedSet(...)` (a `TreeSet` ordered by uuid), and `tick()` sorts by uuid [SRC].
- **Replay-based restoration requires determinism, so the released 1.2.3 is a poor fit unless replay determinism is demonstrated empirically.**

## 3. Verified API (answers to the 14 audit questions)

1. **Python / install.** `pip install scienceworld` (PyPI 1.2.3), or from git (`pip install .`). Python ≥3.7/3.8 [DOC/SRC].
2. **Java.** A JVM is required; 1.8+ is stated and OpenJDK 21 is the upstream example [DOC]. **Not present locally** [LOCAL].
3. **Initialise.** `from scienceworld import ScienceWorldEnv`; `env = ScienceWorldEnv(taskName=None, serverPath=None, envStepLimit=100)` starts the JVM gateway [SRC]. Close with `env.close()` (also called from `__del__`) [SRC].
4. **Tasks and variations.** 30 tasks, ids "1-1" … "10-2" (e.g. `1-1 boil` 30 variations, `6-1 chemistry-mix` 32, `3-3 test-conductivity` 900) [DOC]. API:
   - `get_task_names()`;
   - `get_max_variations(task_name)`;
   - `get_variations_train/dev/test()` (pairwise disjoint: upstream `test_variation_sets_are_disjoint`) [SRC];
   - `get_random_variation_*()` uses **unseeded** `scala.util.Random.nextInt` [SRC], so **we must never use it**. Always pass explicit variation indices.
5. **Deterministic reset.**
   - `load(taskName, variationIdx=0, simplificationStr="", generateGoldPath=False)`.
   - `reset()` re-runs the full `load(...)` with the stored task/variation/simplifications [SRC].
   - `doLoad` resets `UniqueIdentifier`, calls `Random.setSeed(variationIdx)` and `mkKitchenEnvironment(seed = variationIdx)` [SRC].
   - On `main`, `test_observation_is_deterministic` asserts identical observations across **30 resets**, and `test_object_tree_is_uuid_ordered` asserts identical object trees across **8 resets** [SRC]. Not tested upstream for 1.2.3.
6. **Observations and actions.**
   - `reset()` returns `(obs, info)`; `step(action_str)` returns `(obs, reward, isCompleted, info)`.
   - `info` keys: `moves, score, reward, look, inv, taskDesc, valid, variationIdx, taskName, simplificationStr` [SRC].
   - Free (no-tick) helpers: `look()`, `inventory()`, `taskdescription()` [SRC].
   - Valid actions: `get_valid_action_object_combinations()` (sorted list of strings) and `info["valid"]` [SRC].
7. **Execute and interpret.**
   - `reward` = change in score (score scaled to 0–100).
   - `isCompleted` is true when moves exceed `envStepLimit` **or the score is negative** [SRC].
   - A parse failure or ambiguous reference returns early **without a tick**. Ambiguity yields a numbered choice prompt that the next input must answer [SRC, `AgentInterface.processUserInput`].
8. **Complete internal state?** **Partially.**
   - `getObjectTree()` serialises `universe.toJSON()` [SRC]: per object `uuid, name, type, isDeleted`, and property blocks `propMaterial` (substanceName, color, **temperatureC as Double**, stateOfMatter, boiling/melting point, isCombusting, hasCombusted, combustionTicks, …), `propContainer` (isContainer, isOpen, isClosable), `propDevice`, `propHeatSource`, `propCoolingSource`, `propPortal`, `propMoveable`, `propElectricalConnection`, `propLife`, plus nested `contents` [SRC].
   - Not serialised:
     - `nameInStateOfMatter`, `combustionPoint` (commented out / absent) [SRC];
     - **portals are not reached through `contents`** (`getContainedObjects` excludes portals) [SRC], so **door open/closed state may be absent from the tree** [OPEN, verify in 4B];
     - agent wait counters, the focus monitor (`ObjMonitor`) and goal-sequence progress are task/agent state, not tree state [SRC].
9. **Snapshots / clone / serialisation?** **None.** There is no save/load/clone/getState/setState. Persistence exists only for run histories [SRC].
10. **Identical initial worlds on reset?** Yes by construction on `main` (seeded `Random`, reset `UniqueIdentifier`, upstream tests) [SRC]. For 1.2.3 [OPEN] (issue #33 shows divergence during *simulation*, not necessarily at load).
11. **Same action, different consequences?** Yes. Outcomes depend on object properties, containment and temperature (e.g. pouring into an empty vs filled container, activating a heat source with or without an object on it) [DOC paper §3; ASSUME for specific cases].
12. **Complete enumeration for bounded search?**
    - Per state, the agent-accessible valid list is finite and sorted, built from **objects visible in the agent's current room** (`AgentInterface.getValidActionObjectCombinations`, comment: "Currently just returns the current room") [SRC].
    - The template space is ~200k combinations per step [DOC paper §3]; the valid-list size is unknown [OPEN, measure in 4B].
    - **Complete BFS to depth 3 is very likely infeasible** (§5.4).
13. **Hidden labels / metadata in observations?**
    - `info` contains `score`, `reward`, `taskDesc`, and goal progress is available through `get_goal_progress()` [SRC]. These are task-progress signals and **must never enter model-visible prompts**.
    - `taskDesc` contains task instructions (e.g. to "focus on" a substance).
    - The plain observation text (`look`, `inv`) is world description only [ASSUME].
14. **Actions suitable for all three labels?** Plausibly yes [ASSUME]:
    - *reversible*: open/close, move object between containers, activate/deactivate a device with nothing temperature-sensitive attached, teleport/move location;
    - *partially reversible*: actions whose discrete effects can be undone but whose continuous effects (temperature) only drift back;
    - *irreversible*: `eat`, `mix` (creates a new substance from inputs), combustion (`hasCombusted` is a one-way flag [ASSUME, verify that no action resets it]), pouring liquids together.

**Time model** [SRC, `AgentInterface.step`, `ActionWait`]:

- every timed action runs `universe.tick()` once;
- `wait` = 10 iterations and `wait1` = 1 iteration;
- free actions don't tick.

Whether `step("look around")` is timed is decided by `doQueuedActionsTakeTime()` (not read) [OPEN]. **Ticks drive heat transfer** ("Rooms also transfer ambient heat energy to/from the objects they contain", paper §3) and life processes [DOC]. The world therefore changes even when the agent does nothing.

## 4. Proposed adapter architecture (for Phase 4B; not implemented)

```
adnn.scienceworld
├── env.py         ScienceWorldAdapter: owns one ScienceWorldEnv (one JVM); context manager; close()
│                  load(task, variation, simplifications); replay(history) -> Trace; step(action) -> StepRecord
├── canonical.py   canonical_state(object_tree, extra) -> dict  (uuid-free, sorted, documented projection)
│                  core_projection(...) for approximate restoration (OQ-03, OQ-30)
├── restoration.py bounded search over agent-valid actions via reset+replay, with prefix cache,
│                  budget, SearchStatus/complete_through_depth, irreversibility certificates (§5.5)
├── sampling.py    state sampling along gold paths / scripted prefixes (explicit variation indices only)
└── pairs.py       minimal-pair construction from scripted prefixes in the same variation
```

**Contracts carried over from the sandbox** (`10`, `14`): `Label`, `label_from_depths`, `SearchStatus`, `complete_through_depth`, `is_definitive`, `provisional_reasons`, `UndeterminedLabelError`. The dataset schema and validator stay the same, with `environment="scienceworld"` and `source="scienceworld_bfs"`. The prompt builder is unchanged: ScienceWorld examples supply `task_text`, `state_text` and `action_text`, and the tool list becomes a text description of ScienceWorld's action templates (requires a new `tool_set_id`, **no version bump** unless the wording of existing prompts changes).

**State identity = replay recipe.** A ScienceWorld state is `(task, variation, simplifications, action_history)` plus the pinned ScienceWorld commit and JVM version. Each example stores this recipe, so validation can re-derive everything (`14`).

**Execution.**

- One JVM per worker process.
- Parallelise across states, not within a search.
- Cache replays by action-prefix.
- All labelling runs on CPU, so Linux or WSL2 is preferred (§8).

**What is reused from the sandbox judge:** the label semantics, status and determinacy reporting, provisional flags, the validator and the prompt builder. **What is not reused:** the sandbox BFS itself (`assess_reversibility` is typed to `WorldState` and `step`). A generic search over an `Environment` protocol could serve both, but refactoring the sandbox judge would risk changing its audited semantics. Recommendation: a ScienceWorld-specific search that mirrors the same reporting contract, with cross-checks on the shared semantics.

## 5. Restoration feasibility

### 5.1 Exact vs approximate restoration

- **Exact equality of the full object tree is unsuitable as the default.** Every timed action ticks heat transfer and life processes, so `temperatureC` (a `Double`) and `propLife` change even under `wait1` [SRC/DOC]. Literal comparison with the pre-action state (spec §4.2) would label almost every timed action irreversible. That would be an artefact of time, not of the action.
- **UUIDs are not stable identities across restorations.** `UniqueIdentifier.getNextID()` is a creation counter [SRC]. Objects created during an episode (e.g. steam, mixtures) get new uuids. The canonical state must therefore be **uuid-free**: (name, type, selected properties, containment path), sorted.
- **Candidate definitions** (professor decision, OQ-30):

| Option | Exact restoration means | Pros | Cons |
|---|---|---|---|
| A. Literal pre-action state (spec text) | Full uuid-free tree equals the tree before the action | Faithful to spec wording | Time drift makes nearly everything irreversible |
| B. Do-nothing counterfactual | The state after action + k restoring steps equals the state after k+1 `wait1` steps from the pre-action state | Separates the action's effect from autonomous dynamics; generalises OQ-22 | Departs from the literal wording; doubles replay cost |
| C. Discrete projection | Equality on discrete, agent-controllable facts (existence, location/containment, open/closed, activated, stateOfMatter, combustion flags); temperature compared with tolerance → *approximate* | Cheap, interpretable, aligns with OQ-03 "approximate" | Projection choice is a modelling decision; may hide genuine thermal irreversibility |

**Recommendation: B for exact restoration, C's tolerance rule for approximate restoration. Both are pending professor approval.**

### 5.2 Agent-accessible vs researcher-only

- **Restoration sequences may only use actions in the agent-valid list** at each state. `reset()`, `load()`, replay and variation changes are researcher-only.
- Simplification `teleportAction` makes movement a single action. Whether it is enabled changes horizons, so it must be **fixed per dataset and recorded**.
- `focus on` changes only the task monitor [SRC] and can end the episode via the score. It is task bookkeeping: **exclude it from judged actions and from restoration domains** (OQ-33). The same applies to `task`/`inventory`/`look` helper commands.

### 5.3 Horizons 1, 2, 3

- One horizon step = one agent action = one tick. That's the same unit as the sandbox, where one step = one action.
- `wait` (10 ticks) still counts as one action for the horizon. It must either be excluded from restoration domains or counted as one step, documented (OQ-30).
- The horizon-specific labels follow `label_from_depths` exactly as in the sandbox.

### 5.4 Search completeness and unknown outcomes

**Cost model** [ASSUME until measured]: with b valid actions per state, a complete depth-h search needs ≈ bʰ replays. With no snapshot, each replay costs a reset plus (prefix + h) steps through the JVM.

| Valid actions b (unmeasured) | h = 1 | h = 2 | h = 3 |
|---|---|---|---|
| 50 | 50 | 2,500 | 125,000 |
| 200 | 200 | 40,000 | 8,000,000 |

Implications:

- **Complete search at h = 1 is feasible. h = 2 is feasible only for small b with caching. h = 3 is almost certainly infeasible** for complete search over the full valid list.

Therefore, as for the sandbox (`11` §6):

1. **Witness found** → `reversible` / `partially_reversible` at that depth. This is sound, and the witness replays.
2. **Complete search over the agent-valid domain, no witness** → `irreversible` at that horizon.
3. **Incomplete search** (relevance-restricted domain or budget exhausted) → **`undetermined`**, never `irreversible`. Such examples are excluded and counted.
4. **Irreversibility certificates** (optional, sound): an invariant proven from the source shows no action can undo an effect. Examples: an `isDeleted` object never returns; `hasCombusted` is never reset; mixture inputs are deleted. Each certificate must cite the code that proves it and is unit-tested. This is the only way to label `irreversible` at h = 3 without complete search (OQ-31).

### 5.5 Reproducible action histories

- Every example stores its replay recipe (§4).
- The validator replays twice in fresh JVMs and requires identical uuid-free canonical states and observations. Any divergence fails the example.
- ScienceWorld commit, JAR checksum and JVM version are recorded in the manifest.

### 5.6 Scenario-level leakage

- Unit of split: **task family** (e.g. hold out whole tasks) or **task × upstream split** (train/dev/test variations are disjoint upstream) (OQ-34).
- All states sampled from one (task, variation) and all members of a minimal pair stay in one split. This is the same rule as the sandbox families (`13` §3).
- Task descriptions are near-identical within a task, which is another reason to keep tasks unsplit.

## 6. Minimal-pair feasibility

**Feasible in principle [ASSUME].** In one (task, variation), two scripted prefixes reach states A and B that differ in one documented fact. The same action string is then judged in both.

Example: `pour cup into pot` when the pot is empty versus when the pot already holds water.

Requirements, mirroring the pilot validator:

- the action string is byte-identical and **valid in both states**;
- the uuid-free canonical diff between A and B is confined to a declared scope;
- both labels are definitive and differ;
- the state texts differ, so the pivot is visible.

Risks:

- prefixes also advance time (drift), so A and B differ in temperatures too. Option B or C handles this.
- ambiguity prompts can make an action string resolve differently in A and B. Reject pairs with ambiguity.
- ScienceWorld pairs are found, not designed, so their share will be lower than in the sandbox. The ≥30% target applies to the whole dataset (`05` §6).

## 7. Recommended initial task families (Phase 4B spike)

| Priority | Tasks (ids) | Why | Expected label range |
|---|---|---|---|
| 1 | 4-1…4-4 find-* (living/non-living/plant/animal) | Mostly discrete moves between containers/rooms | reversible (move back), irreversible via `eat` |
| 1 | 6-1 chemistry-mix, 6-2/6-3 paint mixing | Mixing is a clean one-way operation with discrete effects | irreversible (mix), reversible (move/open) |
| 2 | 1-1…1-4 boil/melt/freeze/change-state | Core heat physics; spec examples "heat, freeze" | depends on OQ-30; partial/irreversible |
| 2 | 3-1 power-component, 3-3 test-conductivity | Connect/disconnect, activate/deactivate | reversible (disconnect), state-dependent |
| Later | 5-x grow, 7-x lifespan, 8-x life stages, 10-x genetics | Continuous life processes dominate drift | Only after OQ-30 |
| Avoid | 2-x thermometer measurements, 9-x inclined plane | Measurement/physics tasks with few state-changing actions | — |

Use **explicit variation indices** from `get_variations_train/dev/test()`. Use a fixed simplification preset (proposal: `easy` + `openContainers`, recorded; OQ-33). Use gold paths (`generateGoldPath=True`) to sample realistic states.

## 8. Local environment and installation

**Observed on this machine [LOCAL]:**

- Windows 11 Home;
- `.venv` Python 3.11.9;
- **no Java** (`java` not on PATH, no `JAVA_HOME`, no JDK directories);
- **WSL not installed** (`wsl --status`: "not installed");
- virtualization support present;
- ScienceWorld **not installed**;
- PyPI reachable (`pip index versions scienceworld` → 1.2.3; `py4j` 0.10.9.9);
- git 2.55.

No smoke test was possible. Nothing was installed.

**Options** (each needs Sneha's approval before anything is run):

| Option | Steps | Approval needed for | Pros / cons |
|---|---|---|---|
| **A. Native Windows, user-level JDK (recommended first spike)** | 1. Download a JDK 21 zip (e.g. Eclipse Temurin; ~200 MB) into a user folder, e.g. `%LOCALAPPDATA%\Programs\jdk-21`; no installer, no admin. 2. In the session only: `$env:JAVA_HOME = "<path>"; $env:PATH = "$env:JAVA_HOME\bin;$env:PATH"`. 3. `.\.venv\Scripts\python.exe -m pip install "scienceworld @ git+https://github.com/allenai/ScienceWorld@e8216d6044e8e39be9fcb185e3b2dfb602584b52"` (pinned 1.3.0-dev), or `scienceworld==1.2.3` (OQ-29). 4. Smoke test (§9) | JDK download/extract; package install into `.venv` | Smallest footprint; **native Windows support is unverified upstream** |
| B. WSL2 Ubuntu | `wsl --install -d Ubuntu` (admin, reboot), then `sudo apt-get install openjdk-21-jdk python3.11-venv`, clone the repo, create a venv, `pip install -e ".[dev]"`, install ScienceWorld as above | System change (WSL feature, reboot), ~1–2 GB | Matches upstream's Linux CI; recommended in `07` |
| C. Colab/Kaggle CPU runtime | `apt-get install -y openjdk-21-jdk-headless` if Java is absent, then `pip install` as above | None locally | Good for bulk labelling; sessions are interruptible (resumable shards) |

Pinning to a git commit installs the JAR committed in the repository (`scienceworld/scienceworld.jar` was updated in `e8216d6`). Whether that JAR contains all 1.3.0 fixes must be checked in 4B (JAR manifest `Specification-Version`, which `setup.py` reads). Record the JAR SHA-256 in the manifest.

## 9. Phase 4B entry tests (proposed spike, ~1 day after installation)

1. Start and close an environment; list tasks; load `1-1` variation 0.
2. **Determinism:** 10 resets give identical `look` text and uuid-free object trees. Replay the upstream boiling trace 5× in fresh JVMs and require identical traces.
3. **Tick model:** check whether `step("look around")` and failed or ambiguous inputs advance `moves`/temperatures. Measure the temperature drift of an idle state over 1/2/3 `wait1`s.
4. **Door state:** does the object tree change after `open door to …`? If not, add a free `look()` text component for doors to the canonical state.
5. **UUID stability:** pour or mix creates new objects. Confirm that a uuid-free canonicalisation equates semantically identical states.
6. **Action-space size and latency:** distribution of `len(valid actions)` and seconds per step/reset over 3 tasks. This produces the real cost table for §5.4.
7. **Leakage:** confirm observations/`look` contain no score or goal-progress text.
8. Compare **1.2.3 vs pinned main** on items 2–3 to settle OQ-29.

## 10. Open questions (new ones added to `OPEN_QUESTIONS.md` as OQ-29 … OQ-34)

- **OQ-29:** which ScienceWorld version (PyPI 1.2.3, known stochastic heat transfer) versus unreleased `main` 1.3.0 (deterministic enumeration)?
- **OQ-30:** restoration target under autonomous dynamics: literal / counterfactual / projection (§5.1). Also `wait` (10 ticks) in restoration domains.
- **OQ-31:** horizon 3 without complete search: allow certificate-based irreversibility; otherwise label `undetermined`.
- **OQ-32:** execution platform (native Windows + user JDK / WSL2 / Colab-Kaggle).
- **OQ-33:** exclude `focus on` and task/helper commands from judged actions and restoration domains; fixed simplification preset; never put score/goal progress into prompts.
- **OQ-34:** ScienceWorld split unit (task-held-out vs upstream variation splits).
- Existing: **OQ-03** (ScienceWorld partial restoration), **OQ-10** (testbed mix), **OQ-22** (generalised by OQ-30).

## 11. Recommendation: **CONDITIONAL GO**

ScienceWorld is usable as the second testbed:

- its licence permits use;
- its reset is seeded per variation;
- `main` has upstream determinism tests;
- a structured object tree exposes most physical state;
- a finite, agent-accessible valid-action list exists per state.

It is **not** a drop-in for our sandbox judge:

- there is no snapshot;
- the world evolves autonomously each tick;
- uuids are creation counters;
- doors may be invisible in the tree;
- complete depth-3 search is very likely infeasible.

**Conditions for Phase 4B:**

1. **Approval to install** a user-level JDK and a pinned ScienceWorld into `.venv` (option A), or to use WSL2/Colab (OQ-32).
2. **Entry tests §9 pass**, especially replay determinism (2) and the measured action-space cost (6).
3. **Professor input on OQ-30 and OQ-31** (and OQ-03) before any ScienceWorld label is treated as gold. Until then, ScienceWorld labels are provisional, as the sandbox partial labels are.
4. Labels follow the sound-witness / complete-search / certificate rule (§5.4); **"no recovery found" by an incomplete search is never labelled irreversible.**

**NO-GO triggers** (fallback: report ScienceWorld scope reduction to the professor, per spec §9):

- replay is not deterministic on the pinned version;
- per-step latency makes even h = 1 complete search infeasible on the target state sample;
- the canonical state cannot capture door/device state reliably.
