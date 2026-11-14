# ScienceWorld transfer set `adnn-sw-transfer-1.0` and Member 2 handoff

- **Status:** built and validated by Member 1 on 2026-11-04 (ADR-0011).
- **Purpose:** cross-environment transfer (REQ-ABL-04), in both directions.
- **Frozen sets:** production v1.0 and v2.0 are unchanged (records sha256 `b5a7d58f…` and
  `d03cd8f3…`, re-checked after the export).
- **Source:** the SWT pilot (docs/39, verdict GO) plus the 5 ScienceWorld records already in
  v2.0.

## 1. What it is

| | |
|---|---|
| Path | `data/transfer/sw-transfer-1.0/` (git-ignored, like `data/production/`; rebuild with §6) |
| Files | `records.jsonl`, `tool_sets.json`, `cv_folds_by_room.json`, `manifest.json` |
| Records sha256 | `cc39fd7a9e498549f34d9bb335f1bc1095fc0338da94775994d83ca0a312d06d` |
| Manifest sha256 | `bfac4d82d3042a3ebd5b7cb7d0f736f245ab2cbf9749aa6708457c5c7d36b306` |
| Size | **35 records: 20 reversible (R), 15 partially reversible (P), 0 irreversible (I)** |
| Sources | 30 from the SWT pilot (`meta.source_phase = "swt-pilot-1"`) and 5 from v2.0 (`"phase4h"`) |
| Tier | All gold (G). Labels come from the frozen `sw-admission-2` decisions. Nothing is relabelled |
| Split | None (`manifest.split = null`). `load_dataset` returns every record as `"unsplit"` |

**Loading:**

```python
from adnn.dataset.api import load_dataset

sw = load_dataset("data/transfer/sw-transfer-1.0")  # verifies file hashes; 35 records
```

**Record format.** Records use the same schema and conventions as the v2.0 ScienceWorld
records:
- prompt builder 1.1.0 and tool set `ts-scienceworld-1`;
- `render_style = "prose"`;
- `state_text` = ScienceWorld `look` + `inventory` at the start state;
- `task_text` = "You are in a house with a <room>. Work with the objects around you."

You can build prompts and extract hidden states for them exactly as for v2.0.

**Fields specific to this set** (all under `meta`):
- `source_phase`: `"swt-pilot-1"` or `"phase4h"`;
- `transfer_group`: `{room, mechanism, object}`;
- `source_dataset`: legacy records only. It gives the v2.0 records hash and which v2.0 split
  side the record was on.

## 2. Composition

| Mechanism | Label | n | Action verb |
|---|---|---|---|
| Combustion: `use lighter on X` | P | 15 | `use` |
| Container: open or close | R | 10 | `open`, `close` |
| Relocation: pick up or move | R | 4 | `pick`, `move` |
| Electrical: connect | R | 3 | `connect` |
| Device: activate | R | 3 | `activate` |

- **Rooms and groups.** The records cover 8 rooms (kitchen 12, workshop 6, art studio 5,
  bedroom 5, living room 4, bathroom 1, foundry 1, hallway 1) and 34 (room, mechanism, object)
  groups.
- **Scenario ids.** There are 31 `scenario_id` values. The 4 kitchen legacy records keep their
  v2.0 id `sw-grp-boil-kitchen`. Two pilot records (open closet and close closet) share one.
- **Restore depth.** Every witness has depth 1, so the labels are identical at h = 1, 2 and 3.
  The horizon ablation is uninformative on this set.

## 3. Compatibility and duplicate check of the 5 legacy records

- **Compatible.** They pass the unchanged v2.0 evidence check (`export.validate_record`) and
  the stock schema, prompt and uniqueness checks.
- **No exact duplicates.** No (`state_text`, `action_text`) pair repeats in the set.
- **Shared start states (expected).** Every ScienceWorld task uses the same house, so different
  actions can be judged from the same start state. Identical `state_text` occurs in these
  groups:
  - the two legacy kitchen burns;
  - legacy connect-battery and pilot r13 (pick up black wire);
  - legacy move-cup and pilot r08;
  - legacy open-fridge, pilot r05 and pilot r17;
  - pilot pairs b05/b06, b09/b11 and r07/r12.
- **Decision: include them, flagged** by `meta.source_phase = "phase4h"`. They add 2 P and 3 R,
  with their own audited evidence.
- **Leakage note.** 4 legacy records are in **v2.0 train** and 1 (connect-battery) is in
  **v2.0 test**. Do not train on v2.0 ScienceWorld records when testing on this set (§4).

## 4. How to run REQ-ABL-04

### Label task: binary R vs P

- The set has **no admitted irreversible examples**. The pilot's ScienceWorld candidates for
  I were all unresolved or not admitted (docs/39 §3 and §6), and search failure is never treated as
  irreversibility.
- The transfer task is therefore **reversible vs partially reversible**, not the R vs I task
  in REQ-M-03. Say this explicitly wherever transfer results are reported.

### Direction A: sandbox → ScienceWorld

- **Train** on v2.0 train with `environment == "sandbox"` only, keeping R and P. This excludes
  the 4 ScienceWorld records in v2.0 train.
- **Test** on all 35 records here.
- **Optional secondary:** apply a three-class or R-vs-not-R probe and report "P predicted as
  not reversible". Pre-register which you report before looking at results (REQ-STAT-04).

### Direction B: ScienceWorld → sandbox

- **Train** on the 35 records here.
- **Test** on the v2.0 test sandbox R and P records (204 P and 67 R). As a secondary test, use
  all v2.0 sandbox R and P records.
- With n = 35 for training, keep the probe strongly regularised. Choose C by
  leave-one-room-out CV on the ScienceWorld side (`cv_folds_by_room.json`), never on the
  sandbox test set.

### Within-ScienceWorld reference (optional)

Use leave-one-room-out folds (`cv_folds_by_room.json`, 8 folds). Use a room rather than a
`scenario_id` or task id as the group, because shared start states cross task ids.

### Metrics and uncertainty

- Report per layer: AUROC, balanced accuracy, per-class recall, and n with a 95% CI
  (REQ-EVAL-01). Include the layer-0, shuffled-label and majority baselines (REQ-BL-01/03/05).
- Report the ScienceWorld side with a **cluster bootstrap over rooms**, and over
  (room, mechanism, object) as a sensitivity check. The 35 records are not 35 independent
  observations.

## 5. Lexical baseline (REQ-BL-02): read this before interpreting results

- **Within ScienceWorld, the label is perfectly predictable from the action verb.** `use`
  (the lighter) is P in 15/15 cases, and every other verb is R in 20/20. Mechanism and verb are
  fully confounded with the label.
- **What this means:**
  - A bag-of-words model trained on ScienceWorld will score about 100%.
  - High within-ScienceWorld probe accuracy is **not** evidence of state understanding.
  - Direction B partly tests whether "lighter-like" action features map onto sandbox P. Its
    results must be compared against the action-text-only baseline trained the same way.
- **Direction A:** a sandbox-trained bag-of-words model sees almost no overlapping vocabulary.
  Report it anyway, as the reference the probe must beat.
- **Minimal pairs.** The REQ-BL-02 requirement that the probe beat the lexical baseline on
  minimal pairs can only be tested on the **sandbox** minimal pairs in v2.0 (439 pairs). The
  transfer set has **no minimal pairs** (`pair_id` is null).
- **Wording for the report:** "ScienceWorld transfer tests generalisation to a new environment.
  It cannot separate state reasoning from action identity."

## 6. Provenance and rebuilding

- **Pilot records.** For every pilot record the exporter:
  1. re-applies `decide()` to the stored evidence and requires the same outcome, reasons and
     witness;
  2. checks the target action against the frozen `cases.py`;
  3. requires `tier_g` in `results/swt_pilot/report.json` and witness depth ≤ 3;
  4. replays the pinned recipe twice; the S0 raw fingerprint must equal the evidence both
     times, the canonical state must be unchanged by observing, and both rebuilds must give the
     same `state_text`.
- **The manifest records:**
  - the pilot manifest sha256 (`db0620ff…`, frozen before any recovery run);
  - the pilot `report.json` sha256 and its verdict;
  - per-case evidence sha256 values;
  - the v2.0 records hash;
  - the base commit and a hash of the exporter and pilot scripts.
- **Exporter fix.** v2.0's `export.observe` re-checks the *raw* fingerprint after `look`. In
  rooms with several same-named objects (for example three wood cups), ScienceWorld re-draws
  their display aliases in the valid-action list on every query, so that raw check fails
  although nothing changed. The transfer exporter checks the canonical state instead (§6,
  step 4). `src/adnn` is untouched, so v2.0's `code_sha256` pin still holds.

**Rebuild** (needs the pinned runtime and the git-ignored `results/swt_pilot/` evidence; about
a few minutes):

```bash
export ADNN_SW_JAVA_HOME="$LOCALAPPDATA/adnn-sw/jdk/jdk-21.0.13+9"
export ADNN_SW_SITE_PACKAGES="$LOCALAPPDATA/adnn-sw/venv-e8216d6/Lib/site-packages"
.venv/Scripts/python.exe scripts/dataset/swt_transfer.py export     # refuses to overwrite
.venv/Scripts/python.exe scripts/dataset/swt_transfer.py validate   # pure; exit 1 on error
```

Validation (2026-11-04): 0 errors and 0 warnings. The checks: file hashes; schema with the
team partial policy; ScienceWorld evidence (35); provisional (35); prompt rebuild and leakage
(35); uniqueness; label consistency; builder version; fold partition.

## 7. Limitations (carry into the report)

1. **No I class.** Transfer is R vs P only.
2. **One P template.** All 15 P records are `use lighter on X` (C-BURN). The P class is one
   mechanism.
3. **One house.** All tasks share one world. Rooms differ, but the furniture vocabulary
   overlaps heavily.
4. **Depth 1 only.** Recovery is always an immediate one-step action, so horizons do not
   differ.
5. **Partial is declared, not absolute.** It is relative to the declared properties under the
   team-adopted partial rule (`SW_PARTIAL_RULE`, ADR-0006 D2; OQ-21 open).
6. **Small n.** 35 records over 8 rooms. CIs will be wide.
7. **No human annotation** (REQ-LBL-05 is open; docs/41).
