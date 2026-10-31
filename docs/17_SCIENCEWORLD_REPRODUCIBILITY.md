# 17 — ScienceWorld Installation and Reproducibility Trial (Phase 4B)

Owner: **Sneha (M1)**. Trial date: 2026-10-31. Repository base: `38cbf5a` (branch `m1/sandbox-core`). Scope: installation and measurement only. **No adapter, no dataset generation, no research labels.** Predecessor: `16_SCIENCEWORLD_FEASIBILITY.md`.

All numbers below come from `scripts/scienceworld/sw_trial.py`, written to `results/scienceworld_trial/<version>/*.json` (git-ignored, regenerable with the commands in §2). Timings are single-run wall-clock measurements on one laptop and are indicative only.

## 1. Versions and checksums

| Component | Value |
|---|---|
| OS | Windows 11 Home (`Windows-10-10.0.26200-SP0`), AMD64, **native Windows (no WSL)** |
| Python | 3.11.9 (separate venvs; the project `.venv` is untouched) |
| JDK | Eclipse Temurin **21.0.13+9 LTS** (`OpenJDK21U-jdk_x64_windows_hotspot_21.0.13_9.zip`, 205,421,281 bytes, SHA-256 `a4dbaa05fca4bd89d84584e58c459bd732efebb1722af80ab13c6516832004f9`, verified against the Adoptium API **and** the release's `.sha256.txt`) |
| py4j | 0.10.9.9 (wheel SHA-256 `c7c26e4158defb37b0bb124933163641a2ff6e3a3913f7811b0ddbe07ed61533`, hash-pinned) |
| ScienceWorld A | **1.2.3** from PyPI (wheel SHA-256 `e9737b9d099bfaad90ef053ad6ac1d795e2063ed320efdfc0e9d9c8b5bebf419`, hash-pinned). JAR manifest 1.2.3; JAR SHA-256 `f4e1fdce0cdabe1bab7128a7e78ea820210d9db3c28d7272bcbbc3f3a1c5f0d7` (7,784,058 bytes) |
| ScienceWorld B | Source archive of commit **`e8216d6044e8e39be9fcb185e3b2dfb602584b52`** (`archive/<sha>.zip`, 15,372,415 bytes, SHA-256 `d2c1dc1e5d0d4e4a104424598dce13f64c6e80c523212936f97ea85c871bfae6`). Installs as package **1.3.0**; JAR manifest 1.3.0; JAR SHA-256 `e77b0fee7d68abe3ca5b12e57d86e2bfe7603f20c5200da0b0f085939faeb465` (7,793,417 bytes) |

Version B is pinned by commit SHA through an immutable archive URL, not by the moving `main` branch.

## 2. Exact installation (as performed; user-local, no admin, no global PATH change)

The repository is inside OneDrive, so **all installation artifacts live outside the repository** in `%LOCALAPPDATA%\adnn-sw\` (~611 MB: JDK 330 MB, downloads 211 MB, two venvs 35 MB each). Trial outputs go to `results/scienceworld_trial/`, which is git-ignored by `results/*`.

```bash
# Git Bash
SW="$LOCALAPPDATA/adnn-sw"

# 1. JDK (download into an empty directory, verify, extract)
mkdir -p "$SW/downloads/jdk" "$SW/jdk"
URL="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/OpenJDK21U-jdk_x64_windows_hotspot_21.0.13_9.zip"
curl -sSL -o "$SW/downloads/jdk/jdk.zip" "$URL"
curl -sSL -o "$SW/downloads/jdk/jdk.zip.sha256.txt" "$URL.sha256.txt"
sha256sum "$SW/downloads/jdk/jdk.zip"          # must equal a4dbaa05…04f9
unzip -q "$SW/downloads/jdk/jdk.zip" -d "$SW/jdk"

# 2. ScienceWorld 1.2.3 (hash-pinned wheels)
printf 'scienceworld==1.2.3 --hash=sha256:e9737b9d099bfaad90ef053ad6ac1d795e2063ed320efdfc0e9d9c8b5bebf419\npy4j==0.10.9.9 --hash=sha256:c7c26e4158defb37b0bb124933163641a2ff6e3a3913f7811b0ddbe07ed61533\n' > "$SW/req-1.2.3.txt"
py -V:3.11 -m venv "$SW/venv-1.2.3"
"$SW/venv-1.2.3/Scripts/python.exe" -m pip install --require-hashes --only-binary=:all: -r "$SW/req-1.2.3.txt"

# 3. ScienceWorld at commit e8216d6 (= 1.3.0, unreleased)
SHA=e8216d6044e8e39be9fcb185e3b2dfb602584b52
mkdir -p "$SW/downloads/sw-$SHA"
curl -sSL -o "$SW/downloads/sw-$SHA/src.zip" "https://github.com/allenai/ScienceWorld/archive/$SHA.zip"
sha256sum "$SW/downloads/sw-$SHA/src.zip"      # d2c1dc1e…bfae6
py -V:3.11 -m venv "$SW/venv-e8216d6"
printf 'py4j==0.10.9.9 --hash=sha256:c7c26e4158defb37b0bb124933163641a2ff6e3a3913f7811b0ddbe07ed61533\n' > "$SW/req-py4j.txt"
"$SW/venv-e8216d6/Scripts/python.exe" -m pip install --require-hashes --only-binary=:all: -r "$SW/req-py4j.txt"
"$SW/venv-e8216d6/Scripts/python.exe" -m pip install --no-deps "$SW/downloads/sw-$SHA/src.zip"

# 4. Run the trial (JDK on PATH for this command only)
for v in e8216d6 1.2.3; do
  JAVA_HOME="$SW/jdk/jdk-21.0.13+9" PATH="$SW/jdk/jdk-21.0.13+9/bin:$PATH" \
    "$SW/venv-$v/Scripts/python.exe" scripts/scienceworld/sw_trial.py all --n 10 --out results/scienceworld_trial/$v
done
```

**Uninstall:** delete `%LOCALAPPDATA%\adnn-sw\`. Nothing else was changed on the system.

## 3. Procedures (`scripts/scienceworld/sw_trial.py`)

| Experiment | Procedure |
|---|---|
| Smoke | Start the JVM; `get_task_names()`, `get_max_variations()`; load `4-1` variation 0; `reset()`; read `info`, `getObjectTree()`, valid actions; one `step("look around")`; `close()` |
| Resets | `1-1`, variation 0, `teleportAction`: 10 × `reset()` in one process. Fingerprint each state: SHA-256 of observation, `look()`, `inventory()`, raw object tree, uuid-free object tree, sorted valid actions; uuid count; moves |
| Fresh-process replay | The upstream boiling trace (`teleport to kitchen`, `pour counter into sink`, `activate sink`, `use lighter on drawer`, `look around`; from `tests/test_scienceworld.py::test_boiling_is_deterministic` at `e8216d6`) in **5 separate OS processes / JVMs**. Fingerprint after every step and compare all processes step by step |
| Time model | In `1-1` v0: free `look()`, `step("look around")`, an invalid input, `wait1` × 2, `wait`. Compare moves and the full object tree before and after |
| Observability | Count tree nodes carrying `propPortal` / `propDevice`; `open door …` then `close door …`; `activate stove` then `deactivate stove` (kitchen); compare the tree's discrete fields and the `look()` text |
| Object creation | Gold path of `6-1` chemistry-mix v0 (`generateGoldPath=True`); log objects created/removed per step (uuid → name) |
| Branching | `len(get_valid_action_object_combinations())` at task starts and along the boil trace |

**uuid-free canonicalisation** (used for comparisons):

- uuid / portal-endpoint keys are dropped;
- `contents` children are keyed by name;
- same-named siblings become `name#i` **in uuid order**.

The first version of the script ordered duplicates by *content*. Temperature drift then reordered siblings and produced fake discrete changes. It also failed to strip uuids from top-level room keys. Both bugs were found during the trial and fixed before the final runs. A third script bug (it truncated the final observation to 400 characters, which hid "steam") was also fixed. All results below come from the corrected script.

## 4. Results

### 4.1 Smoke test (both versions)

- Runs **natively on Windows** with the user-local JDK. JVM start ≈ 1.3–1.7 s.
- 30 tasks with variation counts identical to `16` §3 (e.g. boil 30, chemistry-mix 32, find-living-thing 300, test-conductivity 900).
- `info` keys: `inv, look, moves, reward, score, simplificationStr, taskDesc, taskName, valid, variationIdx`.
- The observation text did not mention the score.
- `close()` terminates the JVM cleanly.

### 4.2 Determinism

| Test | 1.3.0 (`e8216d6`) | 1.2.3 |
|---|---|---|
| 10 resets in one process: observation, look, inventory, raw tree, uuid-free tree, valid actions, uuid count | **identical** | **identical** |
| 5 fresh processes × 6 states: observation, look, inventory, valid actions | **identical** | **identical** |
| 5 fresh processes × 6 states: raw and uuid-free object tree (two independent batches = 10 processes) | **identical** (both batches) | **diverges**: 1 of 4 comparisons in batch 1, 2 of 4 in batch 2, at **every step from step 1** |
| uuids across processes | identical | identical |
| Divergent fields (1.2.3) | — | `temperatureC` of objects in other rooms (e.g. art-studio air, drawer, paint) |
| Upstream assertion "a substance called steam" in final observation | 5/5 | 5/5 |
| Valid-action counts along the trace | 427, 2734, 2734, 2859, 2951, 2951 (both batches) | batch 1: 427, 2734, 2734, 2859, **2859, 2859**; batch 2: 427, 2734, 2734, 2859, 2951, 2951 |

**Finding.** 1.2.3 is non-deterministic in **hidden state** across JVM processes (heat transfer, consistent with upstream issue #33). Within a batch the difference was **invisible in all observation text**, but present in the object tree. Between batches it also changed the **valid-action set** at steps 4–5. A replay-based oracle on 1.2.3 would compare states that differ for reasons unrelated to the action. **1.3.0 at `e8216d6` showed no non-determinism in any measured quantity.** The two versions also produce different gold paths (`6-1` v0: 25 actions on 1.3.0 vs 20 on 1.2.3).

### 4.3 Time model

Identical on both versions:

| Action | Moves before → after | Temperatures changed | Max \|ΔT\| °C | Discrete tree fields changed | `look()` text changed |
|---|---|---|---|---|---|
| free `look()` | 0 → 0 | 0 | 0 | 0 | no |
| `step("look around")` | 0 → 0 | 0 | 0 | 0 | no |
| invalid input (`dance wildly with the ceiling`) → "No known action matches that input." | 0 → 0 | 0 | 0 | 0 | no |
| `wait1` (first tick of the episode) | 0 → 2 | 81 | 1.41 | 55 (fountain water + 2 terminals created) | no |
| `wait1` | 2 → 4 | 81 | 1.04 | 0 | no |
| `wait` | 4 → 15 | 81 | 2.66 | 0 | no |
| `open door to …` | 0 → 1 | 81 | — | 55 (same first-tick creation) | yes |

Findings:

- **`look around` and invalid inputs consume no time** in ScienceWorld. That differs from our sandbox default, where failed calls advance the clock (OQ-23). See OQ-35.
- **Every timed action ticks the whole world.** In an idle start state, 81 temperatures change per tick. The world is never static, which confirms OQ-30.
- **The first tick of an episode creates objects autonomously** (water and electrical terminals in the outside fountain), whatever the action. States at `moves = 0` are therefore special. Sampled states should be taken after at least one tick.
- `wait1` advances `moves` by 2 and `wait` by 11. One iteration plus the action itself is our reading; the source shows `setWait(1)`/`setWait(10)`.

### 4.4 State observability

| Question | Result (both versions) |
|---|---|
| Doors in the object tree? | **No.** 0 tree nodes carry `propPortal`. `close door to …` changes **no discrete tree field**; only the `look()` text of the current room shows the door state ("A door to the art studio (that is closed)") |
| Devices in the object tree? | **Yes.** 25 nodes carry `propDevice`. `activate stove` changes exactly `stove.propDevice.isActivated` and `stove.propHeatSource.curSetTemp`; `deactivate stove` reverses both discrete fields (temperatures keep drifting) |
| Object ids across equivalent runs | Identical across resets and processes (both versions) |
| Pouring / mixing creates objects? | **Yes.** `mix …` removed `sodium chloride`, `water` and 4 terminals, and created a new `salt water` object (new uuid) plus 2 terminals. `activate sink` created 2 water objects with terminals. An attempted self-pour (`pour metal pot into metal pot`) failed with "You can't move something into itself." and changed nothing |
| Hidden objects | The tree includes hidden electrical terminals of substances (`includeHidden=true`) |
| Score / task metadata in observations | Not in the observation text tested. Present in `info` (`score`, `reward`, `taskDesc`) |

### 4.5 Branching factor and runtime

| Quantity | Measurement |
|---|---|
| Valid actions at task start (hallway; `1-1`, `3-1`, `4-1`, `6-1`, v0) | **417** each |
| Valid actions in the kitchen (boil trace) | **2,734–2,951** |
| JVM start + load + reset (fresh process) | 1.30–1.89 s |
| `reset()` in a running JVM | mean ≈ 0.10–0.12 s, max 0.35 s |
| `step()` | mean ≈ 0.19 s |
| Fingerprint (tree + valid list + look + inventory) | ≈ 0.16–0.17 s per state (derived from process totals) |

**Cost estimate for complete restoration search** (no snapshot, so every candidate needs reset + replay; prefix of 5 actions; ≈ 0.115 + 6 × 0.197 + 0.17 ≈ 1.5 s per depth-1 candidate in one JVM):

| Branching b | Depth 1 | Depth 2 | Depth 3 |
|---|---|---|---|
| ≈ 420 (hallway) | ≈ 10 min | ≈ 3 days | infeasible |
| ≈ 2,800 (kitchen) | ≈ 70 min | ≈ 5 months | infeasible |

These are per judged (state, action) pair, single process, and scale at best linearly with parallel JVMs. **Complete search is infeasible beyond depth 1 and expensive even at depth 1.** This empirically confirms the OQ-31 concern.

## 5. Known limitations of this trial

- One machine, one JDK (Temurin 21.0.13), single runs per timing; no memory measurement per JVM.
- Determinism was tested on one task family (boil), one variation, a 5-action trace, 10 resets and 2 × 5 fresh processes. The 1.2.3 divergence appeared in only 1–2 of 4 comparisons per batch, so a run of identical results is not proof of determinism. 1.3.0 passing these tests (10/10 processes identical) is evidence, not proof.
- The door/device findings cover one door and one device. Other portal types (e.g. containers with doors such as fridges) were not checked separately. Container open/close is in `propContainer` per the source (`16` §3), but this was not exercised here.
- The meaning of `moves` for `wait1`/`wait` is inferred, not traced in source.
- Native Windows works for this trial, but upstream does not document Windows support.

## 6. Recommendation for building the adapter (Phase 4C)

**GO for an adapter on ScienceWorld 1.3.0 pinned to `e8216d6044e8e39be9fcb185e3b2dfb602584b52`** (JAR SHA-256 `e77b0fee…b465`), with these design constraints:

1. **Do not use 1.2.3** for any label: hidden-state non-determinism across processes (§4.2) would corrupt replay-based restoration (resolves OQ-29 empirically; team decision to confirm).
2. **State identity = replay recipe** (task, variation, simplifications, action history) + pinned commit + JAR hash + JDK version. The validator replays in a fresh JVM and requires identical fingerprints.
3. **Canonical state** = the object tree (uuids may be used for identity within one task/variation, since they are deterministic on 1.3.0; uuid-free matching only where objects are re-created) **plus door states from `look()` text**. Doors are invisible in the tree, so door actions must be either handled through the text component or excluded.
4. **Restoration oracle:**
   - complete search is infeasible beyond depth 1 (§4.5), so use **small, documented inverse-action domains** (close↔open, deactivate↔activate, move back, pick up/put down);
   - a found witness gives a sound reversible/partial label;
   - not found → **undetermined**, never irreversible;
   - irreversible only via **source-verified certificates**: object deletion by `mix` (observed in §4.4), `eat`, combustion `hasCombusted`. Each certificate needs a source citation and a test.
   - This requires professor approval (OQ-31).
5. **Autonomous dynamics:** temperatures change every tick, and objects can appear on the first tick (§4.3). The restoration target needs the OQ-30 decision (literal / counterfactual / projection with temperature tolerance). Sample states only after at least one tick.
6. **Time semantics differ between testbeds:** invalid inputs and `look around` cost no time in ScienceWorld but do in our sandbox. Decide whether to align them (OQ-35) before cross-environment comparisons (REQ-ABL-04).
7. **Runtime:** labelling must parallelise across JVM processes and keep restoration domains tiny. Native Windows works for development; bulk labelling may still be better on Linux (OQ-32).
8. Exclude `focus on`, helper commands and `wait` from judged actions; never put `score`/`taskDesc` progress into prompts (OQ-33).

**Remaining blockers before ScienceWorld labels can be gold:** professor decisions on OQ-30 and OQ-31 (and OQ-03), plus the team decision on OQ-35.
