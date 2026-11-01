# Member 1 Guide — Testbeds, Oracle Labels and the v1.0 Dataset

Member 1 (Sneha) built everything Members 2 and 3 consume: two testbeds, a reversibility
oracle, the labelled dataset, its validator and loader, and the frozen protocol around them.
This page is the overview. The details live in the linked phase reports.

## 1. Why it was built this way

To measure whether a model knows that an action is irreversible, we need labels that are
**correct by construction**, not opinions.

- **Sandbox.** A small simulated world where reversibility can be computed exactly.
- **ScienceWorld.** A second, independent testbed, where labels come from a bounded search
  plus audited evidence.
- **Minimal pairs.** The same action shown in two states with different labels. They stop a
  probe from scoring well just by reading the action's wording.

## 2. Testbeds

| Testbed | What it is | Code | Docs |
|---|---|---|---|
| Tool sandbox | Deterministic simulated files, email, payments and share links. 13 agent tools (`delete_file`, `send_email`, `transfer_money`, …) plus 2 share-link tools. Settings such as recycle bin, versioning, undo windows and refund fees decide recoverability. Never touches the real system | `src/adnn/sandbox/` | docs/10, docs/11, docs/29 |
| ScienceWorld | Text simulation of science tasks (Java), pinned to commit `e8216d6`. Used for 5 audited cases | `src/adnn/scienceworld/` | docs/16–24 |

Try the sandbox: `.venv/Scripts/python.exe -m adnn.demo`.

## 3. Oracle and labels

**Sandbox.** `adnn.sandbox.assess_reversibility(state, call)` runs an exact breadth-first
search over tool sequences after the action.

| Label at horizon h | Meaning |
|---|---|
| reversible | the previous state can be restored exactly within h steps |
| partially reversible | it can only be restored approximately or at a cost (`scaling_pilot.PARTIAL_RULE`, team-adopted, ADR-0006 D11) |
| irreversible | it cannot be restored |

Horizons are h = 1, 2, 3, and h = 3 is primary.

**Gold tier.** A record is gold only if:
- the search was complete;
- the action succeeded;
- no timers were pending;
- the label does not change under the alternative reading OQ-21.

OQ-21-sensitive records (tier P) are kept out of the gold set.

**ScienceWorld.** Labels come from the frozen `sw-admission-2` decisions. Each case also has
R5 replication, a query-order audit, a symmetry check and a rubric check. Partially reversible
cases also have a certified residual.

**No human annotation has been done.**

## 4. Minimal pairs

- **Construction.** Each sandbox family has one pivot condition, for example the recycle bin
  on or off, or the amount compared with the refund fee. A pair shows the **byte-identical
  action and task** in the two pivot states.
- **Acceptance.** A pair is kept only if the oracle gives the two states different gold labels.
- **Alternative actions** already present in a family form a pair only when the oracle labels
  differ (ADR-0009 C2).
- **Not invented.** No recovery evidence or new mechanism was created to produce pairs.

## 5. Generation, validation and freezing

| Step | What | Where |
|---|---|---|
| Decide | Rule changes recorded before use | `docs/decisions/0006`–`0009` |
| Freeze | Configuration, gates and protected hashes written and committed **before** generation | `docs/preregistration/production_manifest_amend1.json` (+ `.sha256`) |
| Generate | `scripts/dataset/phase5h_generate.py`. It refuses to run if code, config or protected inputs changed | `src/adnn/dataset/production.py`, `src/adnn/scienceworld/export.py` |
| Validate | Schema, oracle re-run, witness replay, prompt hashes, action located exactly once, pairs, split leakage, ScienceWorld evidence | `src/adnn/dataset/validation.py` |
| Load | Checksums and prompt hashes verified at load time | `src/adnn/dataset/api.py` |

**Earlier freezes stay as historical artifacts:**
- `production_manifest.json`;
- `phase5b`, `phase5d` and `phase5e` manifests.

ADR-0009 Amendment 1 explains why v1.0 was regenerated once.

## 6. v1.0 results

| | I | P | R | Total |
|---|---|---|---|---|
| Sandbox | 110 | 230 | 276 | 616 |
| ScienceWorld | 0 | 2 | 3 | 5 |
| **All** | **110 (17.7%)** | **232 (37.4%)** | **279 (44.9%)** | **621** |

- **Minimal pairs:** 224 records in 112 pairs (36.1%).
- **Split:**
  - train: 489 records in 65 scenario groups with records;
  - test: 132 records (21.3%) in 11 groups, holding 24 pairs and 1 ScienceWorld record.
- **Render styles:** `compact` appears in test only.
- **Excluded from gold:**
  - 2 ScienceWorld cases with incomplete evidence;
  - 19 OQ-21-sensitive records, in `sensitivity_oq21.jsonl`.
- **Checksum:** `records.jsonl` sha256 `b5a7d58f342fbc2ef7c0658a0dd2a9ffc99c95f8153c8aa1d79bcb70620e20dd`.

Full tables: [docs/34](34_PRODUCTION_DATASET_V1.md). Data card: [docs/35](35_DATA_CARD_PRODUCTION_V1.md).

## 7. Known limitations

1. **Below the size target.** 621 records against the professor's ≥ 2,000. The limit is the
   ≤ 8% per-family cap with few scenario shapes.
2. **ScienceWorld is token-sized.** Only 5 ScienceWorld records, with 1 in test.
3. **Class imbalance.** Irreversible records are 17.7%, so use balanced accuracy.
4. **No human annotation.** Labels come from the oracle and the audited evidence.
5. **Style confound.** `compact` appears only in test, so the test set changes style as well
   as scenario.
6. **OQ-21 unresolved.** The professor has not confirmed the partial definition.
7. **Few test clusters.** Only 11 test scenario groups, so confidence intervals will be wide.
8. **Pre-registered but not produced** (ADR-0008 B3/B4):
   - a subset with at most 3 records per scenario;
   - a secondary family-disjoint split.

## 8. Verify and reproduce

All of these commands were run successfully. Setup comes first ([ENVIRONMENT_SETUP.md](../ENVIRONMENT_SETUP.md)).

```bash
# Verify a received copy (needs the dataset bundle, incl. the 8 ScienceWorld evidence files)
sha256sum -c ../adnn-v1.0-SHA256SUMS.txt
.venv/Scripts/python.exe -m adnn.dataset.validation data/production/v1.0   # "ok": true, 1 warning

# Regenerate the historical pilot (byte-identical, sha256 f66b98ba…; needed by 3 tests)
.venv/Scripts/python.exe -m adnn.dataset.pilot --out data/pilot

# Regenerate v1.0 from the frozen manifest (about 5 min, about 6 GB free RAM, pinned ScienceWorld runtime)
SW="$LOCALAPPDATA/adnn-sw"
ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
  .venv/Scripts/python.exe scripts/dataset/phase5h_generate.py --out data/production/v1.0
```

**What regeneration needs:**
- the ScienceWorld evidence files and `data/scaling_pilot/records.jsonl` from the bundle,
  because they are protected inputs;
- `data/pilot/pilot_v0.1.jsonl`, regenerated as above.

Expected checksums are in docs/34 §2.
