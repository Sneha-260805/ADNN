# 39 — ScienceWorld transfer feasibility pilot (40 pre-registered cases)

- **Status:** pilot complete on 2026-11-04. It is awaiting team review.
  - **No dataset record was exported.** No gold label was written.
  - No scale-up was started. Nothing was committed or pushed.
- **Purpose:** test whether a ScienceWorld set for cross-environment transfer (REQ-ABL-04,
  ADR-0006 D11) can be built with the existing labelling pipeline.
- **Unchanged:**
  - production v1.0 and v2.0 (records sha256 `b5a7d58f…` / `d03cd8f3…`);
  - every frozen manifest;
  - `src/adnn` (the v2 `code_sha256` pin still matches);
  - `sw-admission-2`, the certificate reports and rubric `sw-declaration-rubric-1`.
- **Approval:** the professor was not contacted. **No human annotation was done.**

## 1. Provenance

| Item | Value |
|---|---|
| Pre-registration | `docs/preregistration/swt_pilot/manifest.json`, sha256 `db0620ff14d773542eba7146e691e024d62f2a32472e4fe26e4ce17d16450751` (sidecar `manifest.sha256`) |
| Frozen at | 2026-11-04T12:41:49Z, before any recovery experiment. Base commit `e2230f1` |
| Cases module | `scripts/scienceworld/swt_pilot/cases.py`, sha256 `89d652b7…` (pinned in the manifest) |
| Go/no-go criteria | G1–G5, frozen inside the manifest (`go_no_go`) |
| Rule / semantics / evidence | `sw-admission-2` / `sw-restoration-semantics-1` / `sw-label-evidence-0.1`; ScienceWorld `e8216d6` |
| Code | `scripts/scienceworld/swt_pilot/{enumerate_worlds,freeze,run}.py`. It sits outside `src/adnn`, so the v2.0 code hash is untouched |
| Results (git-ignored) | `results/swt_pilot/`, about 11 MB, including `report.json` |

**Why the code lives in `scripts/`.** The v2.0 manifest pins a hash of every
`src/adnn/**/*.py` file. Pilot code under `src/adnn` would make v2.0 irreproducible from the
working tree.

### 1.1 What happened before the freeze (disclosed)

1. **Read-only enumeration.** `enumerate_worlds.py` loaded the S0 state of 25 task
   variations. It ran no agent action, no target and no lighter.
   - All tasks share **one 11-room house**. They differ only in a few task-specific
     objects; variations mostly swap decorations (painting, drawing, book shelf).
   - The **lighter exists only in the kitchen**. Combustion elsewhere therefore needs the
     agent to carry the lighter and a pot of water.
2. **Combustibility.** It was decided statically from the pinned `MaterialProperties.scala`:
   a substance's combustion point must be at or below the lighter's 2200 °C.
3. **Dry checks (`freeze.py --check`).** Each check built S0 and listed valid actions only.
   Fifteen drafts were renamed to ScienceWorld's own action texts, for example
   `open cupboard` for the large cupboard and `move cup to sink`.
   - Objects whose action text hides their identity (`cloth sittable`, `object`) were
     replaced by named objects.
   - One case, `disconnect battery`, was **replaced**. Rubric 1 has no `disconnect` rule, so
     its rubric-stability check could never run (§6.5).
   - No target was executed and no recovery was tried before the freeze.
4. **Selection.** Unlike Phase 4H, the pilot is **targeted**: 20 likely-reversible cases,
   15 combustion cases with water within one action, and 5 controls. The yields below are
   therefore yields of a deliberately favourable design, not rates for ScienceWorld actions
   in general.

### 1.2 Interruption and resume

- **Interruption.** The first main run was stopped by Claude Code's host memory-pressure
  watchdog after 12 of 40 cases. Free RAM had fallen to about 0.8 GB because of other
  applications. It was resumed with about 7 GB free.
- **Resume option in `run.py`.** A case is skipped only if three conditions hold:
  1. its stored M1 and rubric evidence parse;
  2. both match the frozen definition (case id, family, task, variation, history, target and
     declaration hash);
  3. the stored decision equals a fresh `decide()` on the stored evidence.
- **Other safeguards:**
  - files are written atomically;
  - free RAM is checked before every JVM launch, with a clean stop below 1.5 GB;
  - `--limit` allows short foreground chunks, with one JVM at a time.
- **Result of the check:** all 12 stored cases passed and none needed rerunning. Unit checks
  confirmed that a wrong hash, a wrong case or a missing file is rejected.
- **One later interruption.** One audit chunk was cut off by its own shell timeout. The
  interrupted case was simply rerun, because the audit and symmetry stages keep per-case
  files.

## 2. Verdict (frozen criteria, not re-scored)

| Criterion (frozen) | Result | Pass |
|---|---|---|
| G1: tier-G partial ≥ 8 over ≥ 4 independent scenario groups | **13** partial over **13** groups | ✅ |
| G2: tier-G reversible ≥ 12 over ≥ 4 task families | **17** reversible over **14** task families (16 scenario groups) | ✅ |
| G3: 100% of eligible cases replicate | **30 / 30** | ✅ |
| G4: measurement-affected ≤ 2% of eligible | **0 / 30** (query-order 0, symmetry 0) | ✅ |
| G5: rubric-sensitive ≤ 10% | **0 / 30** | ✅ |

**Verdict: GO under the frozen criteria.** §6 lists what this verdict does *not* establish.
Those limits matter more for the transfer claim than the counts do.

**Tier G** here means all of the following:
- eligible under `sw-admission-2`;
- replicated in a fresh process;
- query-order transitions equal under every condition;
- symmetric protocol unaffected;
- the rubric gives the same outcome;
- witness depth ≤ 3;
- for partials, every residual is protected by the admissible C-BURN certificate.

## 3. Outcomes

| Group | n | Tier-G reversible | Tier-G partial | Unresolved |
|---|---|---|---|---|
| Likely reversible (r01–r20) | 20 | 16 | 0 | 4 |
| Combustion with water (b01–b15) | 15 | 0 | 13 | 2 |
| Controls (c01–c05) | 5 | 1 (c05) | 0 | 4 |
| **Total** | **40** | **17** | **13** | **10** |

- Every eligible case is tier G. No case was eligible but failed a later check.
- **No case is labelled irreversible.** The 10 unresolved cases stay unresolved. None was
  relabelled.

### 3.1 Admitted reversible (17)

| Case | World | Room | Mechanism | Witness (1 step) | Level |
|---|---|---|---|---|---|
| r01 open drawer | 1-2 | living room | container | close drawer | exact |
| r02 open closet | 1-3 | bedroom | container | close closet | exact |
| r03 open cupboard (large) | 6-1 | art studio | container | close cupboard | exact |
| r04 open glass jar | 2-2 | kitchen | container | close glass jar | exact |
| r05 open freezer | 1-3 | kitchen | container (cooling) | close freezer | exact |
| r06 open freezer (ULT) | 3-3 | workshop | container (cooling) | close freezer | exact |
| r07 open paint cupboard | 6-2 | art studio | container | close paint cupboard | exact |
| r08 close cupboard | 1-4 | kitchen | container | open cupboard | exact |
| r09 close closet | 1-1 v1 | bedroom | container | open closet | exact |
| r12 pick up jug | 6-3 | art studio | relocation | move jug to table | within 0.01 °C |
| r13 pick up black wire | 3-2 | workshop | relocation | move black wire to table | within 0.01 °C |
| r14 move bowl to table | 4-2 | kitchen | relocation | move bowl to counter | within 0.01 °C |
| r17 activate stopwatch | 1-2 | kitchen | device | deactivate stopwatch | exact |
| r18 activate switch | 3-4 | workshop | device | deactivate switch | exact |
| r19 connect battery cathode to red wire t1 | 3-1 v1 | workshop | electrical | disconnect battery | exact |
| r20 connect blue wire t2 to orange wire t1 | 9-1 | workshop | electrical | disconnect blue wire | exact |
| c05 activate blast furnace (control) | 1-2 | foundry | device | deactivate blast furnace | exact |

### 3.2 Admitted partially reversible (13), all C-BURN

- **Shared pattern.** For every case:
  - the witness extinguishes the fire, so `isCombusting` is restored;
  - the residual is `hasCombusted`, which the admissible C-BURN certificate protects;
  - the canonical level is `none`, because the object stays hot and wet (§6.2).
- **Spread.** The 13 cases cover 13 objects in 6 rooms, made of wood or paper.

| Case | World | Room | Object | Witness |
|---|---|---|---|---|
| b01 | 1-2 | kitchen | table | pour metal pot into table |
| b02 | 2-3 | kitchen | bowl | pour metal pot into bowl |
| b03 | 6-1 | kitchen | cupboard | pour metal pot into cupboard |
| b05 | 1-1 | bedroom | painting | move painting to metal pot |
| b06 | 1-3 | bedroom | table | pour metal pot into table |
| b08 | 2-2 | bedroom | closet | pour metal pot into closet |
| b09 | 1-1 | living room | chair | pour metal pot into chair |
| b10 | 2-1 | living room | desk | pour metal pot into desk |
| b11 | 3-2 | living room | painting | move painting to metal pot |
| b12 | 6-2 | art studio | table | pour metal pot into table |
| b13 | 1-2 | art studio | large cupboard | pour metal pot into cupboard |
| b14 | 1-1 | hallway | picture | move picture to metal pot |
| b15 | 1-3 | bathroom | drawing | move drawing to metal pot |

### 3.3 Unresolved / excluded (10, never relabelled)

| Case | Reason | Explanation |
|---|---|---|
| r10 move painting to table (bedroom) | `temperature_sensitive` | The witness `move painting to bedroom` gives partial at 0.01 °C but reversible at 0.1 °C, so the case is quarantined |
| r11 move painting to chair (living room) | `temperature_sensitive` | Same pattern |
| r15 pick up drawing (hallway) | `temperature_sensitive` | Same pattern; the return goes to the room floor |
| r16 move cup to sink (bathroom) | `temperature_sensitive` | Same pattern |
| b04 burn soap | no witness; C-BURN does not cover `isCombusting` | Burning turns the soap into `liquid soap`. Its name and state of matter change, so the declared path `move soap to metal pot` no longer parses |
| b07 burn finger painting | no witness; same coverage reason | The declared move into the water pot executed, but the object was still burning one tick later. **Unexplained:** the same path worked for b05, b11, b14 and b15. Not probed further, since probing now would be post hoc |
| c01 activate stove (control) | `no_op_target` | The stove is broken in task 1-1 variation 1 |
| c02 pour pot into sink (control) | no witness | Liquid transfer, as expected |
| c03 eat apple (control) | no witness | Consumption, as expected |
| c04 burn bed, no water (control) | no witness; coverage | Combustion cannot be put out without water, as expected |

**Rejected by mechanism:**
- relocation that returns an object to the room floor: 4 of 4 temperature-sensitive;
- liquid transfer, consumption and combustion without water: 0 eligible.

## 4. Scenario diversity

- **Task families:** reversible cases come from 14 task ids, partial cases from 9. **This
  overstates independence.** All tasks share one house (§1.1), so the task-family count in
  G2 is a weak measure.
- **Scenario groups (room | mechanism | object):** 16 reversible, 13 partial.
  - r02 (open closet) and r09 (close closet) share a group.
- **Reversible mechanisms:**

  | Mechanism | Cases |
  |---|---|
  | container | 9 |
  | device | 3 (including the c05 control) |
  | relocation | 3 |
  | electrical | 2 |

  The reversible cases span 6 rooms (art studio, bedroom, foundry, kitchen, living room,
  workshop).
- **Partial mechanisms:** **one**, combustion, with one action template (`use lighter on X`).
  - 13 objects in 6 rooms;
  - materials: wood 9, paper 4.
- **Lexical concentration:** every tier-G partial action begins with `use lighter on`. No
  reversible action does.

## 5. Replication, measurement and rubric sensitivity

- **Replication (G3):** 30 of 30 eligible cases replicated in a fresh process. The checks
  were S0 fingerprint, target, every attempt's levels and concepts, certificate checks,
  outcome, reasons, witness and stochastic-exposure signals.
- **Query-order audit:** 30 of 30 cases had equal transitions under every condition. The
  conditions were B (observe), C (enumerate), D1 and D2, with 0 state-differing steps.
- **Symmetric protocol:** 0 of 30 cases affected. Outcomes, witnesses and attempt levels were
  equal, and the counterfactual transitions were equal.
- **Rubric sensitivity (G5):** 0 of 30 outcomes changed, and 0 of 40 overall. **Caveat:** the
  test has little power here.
  - For open/close, toggle and connect cases, rubric 1 declares exactly what M1 declares.
  - For burns, the only difference is the weight on `present` (A2), and `present` never
    changes within the window.
  - For moves, M1 additionally records temperature at weight 0.
  - A rubric that disagreed more would be a stronger test.

## 6. What a GO does *not* establish (labelling ambiguities)

1. **Reversibility relative to time.**
   - Every witness is a single recovery step taken immediately.
   - The c05 control was expected to be partial, yet it is reversible. Deactivating the
     furnace one tick later restores everything, because no heat has accumulated yet.
   - The freezer cases (r05, r06) are reversible for the same reason.
   - These are correct under `sw-admission-2` and its immediate-recovery horizon (docs/24
     H2). They are not claims about delayed actions.
2. **Scope of the partial residual.**
   - The partial label rests on the declared property set (`hasCombusted`, `isCombusting`).
   - Extinguishing leaves the object at its combustion point minus 10 °C and full of water.
     That is why the canonical level is `none`.
   - "Partial" means: the designed property was restored, and the certified residual
     `hasCombusted` remains. It does not mean the rest of the state is close to the
     counterfactual.
3. **One template for the whole P class.** All 13 partials are `use lighter on X`. Within
   ScienceWorld, the verb alone predicts the label perfectly. Any ScienceWorld→Sandbox
   transfer, or within-ScienceWorld probe, must be read against an action-only lexical
   baseline and the sandbox minimal-pair control.
4. **Independence.** One house, a few rooms, repeated object types (three burnt tables, two
   burnt paintings). The effective number of independent scenarios is at most about 29
   (16 + 13 groups) and arguably lower.
5. **Rubric coverage gap.** Rubric 1 cannot declare `disconnect`. Any disconnect case would
   fail the rubric check by construction.
6. **Unexplained b07.** It is not admitted and not relabelled. It should be probed in a
   pre-registered follow-up before any finger-painting or paint-material case is used.
7. **No human validation.** Declarations are the team's (M1) plus a rule-based rubric. That
   is not inter-annotator agreement.

## 7. Runtime and resources

| Stage | Collections | Compute |
|---|---|---|
| Main (M1) + rubric | 80 | 2,034 s summed per-case evidence time (mean 25.4 s per collection) |
| Replication | 30 | 626 s (mean 20.9 s) |
| Query-order audit (4 conditions plus baseline) | 30 | about 900–1,100 s wall (burn cases about 60 s each) |
| Symmetric protocol | 30 | 640 s wall |
| **Total** | | **about 75 minutes of compute**, one JVM, about 0.5–1 GB RAM |

Wall time was longer because of the memory interruption and chunking. Results take about
11 MB. Manual work was about half a day: case design, renaming during the dry check, and the
audit of outcomes.

## 8. Implications for the scale-up decision (not started)

- **Yield of targeted designs.**
  - Reversible: 16 of 20, or 80% (85% counting the control).
  - Certificate-backed partial: 13 of 15, or 87%.
  - Compare Phase 4G/4H, where about 19% and 7% were representative.
- **Remaining room.** The binding limit is now distinct scenarios, not yield.
  - **Reversible groups left:** openable containers (oven, fridge, drawers, book shelf),
    device toggles (oven, sink, which has side effects) and further wire pairs. A rough
    estimate is 15–25 more groups.
  - **Partial groups left:** about 15–20 more combustible objects across rooms (pillows,
    couch, mattress, bed, chairs, books, wood cups). Note that cloth items appear only as
    `cloth sittable` in action text.
  - So **40–80 tier-G records in total looks achievable.** Beyond that, cases would
    increasingly repeat (room, object type) combinations.
- **What scale-up would not fix:** the single P template, the absence of an I class, and
  identical house layouts. These limit the transfer claim to binary R vs P, with lexical
  controls (docs/25 §7, ADR-0006 D11).
- **Before any scale-up, the team should decide:**
  1. whether a transfer claim can rest on a one-template P class;
  2. whether to fix rubric coverage (a rubric 2 would need its own pre-registration);
  3. a new ADR and frozen manifest for the transfer set, as a separate artifact that leaves
     v2.0 untouched;
  4. an exporter generalisation (`sw-export-1.1`).

## 9. Reproduce

```bash
export ADNN_SW_JAVA_HOME="$LOCALAPPDATA/adnn-sw/jdk/jdk-21.0.13+9"
export ADNN_SW_SITE_PACKAGES="$LOCALAPPDATA/adnn-sw/venv-e8216d6/Lib/site-packages"
for m in main replica audit symmetry compare gate; do
  .venv/Scripts/python.exe scripts/scienceworld/swt_pilot/run.py $m   # add --limit N to chunk
done
```

Every mode verifies the manifest, its sidecar, the record hashes, the cases-module hash and
the rubric declaration hashes. It refuses to run on any mismatch.
