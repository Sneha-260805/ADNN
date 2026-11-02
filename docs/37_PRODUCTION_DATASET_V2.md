# 37 — Production dataset v2.0: generation and validation report

- **Status:** generated and fully validated on 2026-11-03, from the amended v2 manifest.
  Awaiting Member 1 review before it is committed and shared.
- **Path:** `data/production/v2.0/`. It is git-ignored; get the bundle (§8) or reproduce it (§9).
- **Decision record:** ADR-0010, including Amendment 1 (variant cap 6).
- **v1.0 is unchanged.** It stays frozen (docs/34, docs/35); v2.0 is a separate dataset,
  `adnn-dataset-2.0`.
- **Approval:** no professor approval is claimed. Labels come from the oracle; **no human
  annotation has been done.**

## 1. Provenance

| Item | Value |
|---|---|
| Frozen manifest (used) | `docs/preregistration/production_manifest_v2_amend1.json`, sha256 `432e73445d48e7867d1e32a7dde8e90e744c38efcda064cdc7afb147deb6160c` |
| Original v2 freeze (historical, unchanged) | `docs/preregistration/production_manifest_v2.json`, sha256 `ed7b24a1b04add4b1662be8703c35d7540f7e62b168f2b46766636a324fca585` |
| Code pin | base commit `4ae4cd4` + `code_sha256` `a4cf1a523d6b70cc63144b62bc8ef2af74fc6bcdc311fc6ea36dbe2826639f3c` (all `src/adnn/**/*.py`, LF-normalised) |
| Generation config | v1.0 config with `generator_version` `production-gen-2.0` and `surface_variants` 6 (v1.0: 4); nothing else differs (tested) |
| Families | v1.0 families + nine ADR-0010 families (`families-v2-1.0`) |
| Grouping / exporter / prompt builder | `production-grouping-1.0` / `sw-export-1.0` / 1.1.0 |
| Partial-definition policy | team-adopted (ADR-0006 D2/D11) |
| Generation runtime | 1,255 s, one run, with 6.7 GB RAM available |

**Why the code is pinned by hash.** v1.0 froze its manifest at a commit. v2.0 was frozen
before the v2 code was committed, at Member 1's request. So the manifest pins `base_commit`
and a hash of the source files instead. The generator refuses to run if either differs. The
hash ignores line endings, so it stays valid after the code is committed.

**History: amendment A1.** The first run, from the original v2 freeze, passed every gate and
the validator. But its robustness subset (§6) split 17 minimal pairs.
- **Cause:** a bug in `families_v2.capped_subset`. The two members of a pair always have
  different coarse scenario keys, because the pivot setting is part of the key. The helper
  grouped records by (coarse key, pair), so it treated the two members separately.
- **Fix:** a pair is admitted only if both members' scenarios have room. A regression test
  covers pairs whose members have different coarse keys.
- **Re-freeze:** the manifest was re-frozen as amendment 1. Only the subset rule text and the
  code hash changed. The amendment also records the first run's `records.jsonl` and
  `split.json` hashes, and the generator checks them.
- **Outcome:** compared with the first run, `records.jsonl`, `split.json`, `tool_sets.json` and
  `sensitivity_oq21.jsonl` are **byte-identical**. Only `robustness_subset_le3.json` (719 to
  707 records) and `manifest.json` changed.
- **Old output:** the first run's output is kept, unreleased, in
  `data/production/superseded-v2.0-run1-subset-defect/`.

## 2. Checksums (sha256)

| File | sha256 |
|---|---|
| `records.jsonl` | `d03cd8f38ad4b36ce540409e7b3062e0eb4b457d6916483a3334ebde0acdab73` |
| `split.json` | `110d1b6ae9b704987f95df328a10b6473c6a71993488674fcf6e4f3865c94d3e` |
| `tool_sets.json` | `a45f798be15a7019dca356334f83fe1be5fa99741d7d8b813cda31e9e09eba33` (same as v1.0) |
| `sensitivity_oq21.jsonl` | `3406198c52593e5786bab93014f223a1ba6ded8d2946813f8ebab1aeac2de852` |
| `robustness_subset_le3.json` | `10039b1be789f83e9e1a5e91da8289399163106c622497e135eff277d5e1dfe5` |
| `manifest.json` | `0346dcaaac58bf4727f8806e8fa3bffee4fee69d63af50e092e900f9e14e9cd8` |
| Sandbox records (`stable_json`, id order) | `a2e9c63025bab43de430a9c21d3c78d5576ed8ff421a58931121d9375e45a857` |
| ScienceWorld records | `f48c5ea8d1634292d3748c1f0f8da75ad735631e0905067864d207d42fb229b1` (equal to v1.0's apart from `dataset_version`) |
| All records (`stable_json`, id order) | `df02d4a4020e4f75e44368e69d2b215a2b664e48fc33ffea3ffa5079df295210`, **identical to the cap-6 feasibility run** |

`generation_report.json` is not listed: it records the HEAD commit and the runtime.

## 3. Validation

- **Generator gates, all 13 pass:**
  - minimal pairs ≥ 30%;
  - family share ≤ 8%;
  - zero same-scenario label conflicts (SD3);
  - test fraction 18–22%;
  - `compact` style in test only;
  - 0 validator errors;
  - loader rebuilds every prompt hash;
  - train + test counts equal the dataset;
  - ScienceWorld records equal v1.0's;
  - records identical to the first run;
  - split identical to the first run;
  - subset pairs atomic;
  - subset cap respected.
- **Full validator.** `python -m adnn.dataset.validation data/production/v2.0` (team policy,
  production thresholds) reports **0 errors and 0 warnings**.

| Check | Records covered |
|---|---|
| Schema, provisional and tier fields, prompts (hash rebuilt, action located once) | 2,134 |
| Oracle re-run and witness replay (sandbox) | 2,129 |
| Share-link restoration | 42 |
| ScienceWorld evidence re-check | 5 |
| Strict minimal pairs | 439 |
| Uniqueness, label consistency, builder version, 3 file hashes, scenario-grouped split | dataset-wide |

**Integrity of earlier artifacts.** The amended manifest protects 17 files. The generator
verified that all are unchanged:
- all six `data/production/v1.0` files;
- both v1.0 frozen manifests and their sidecars;
- the original v2 freeze and its sidecar;
- the earlier pilots and freezes.

## 4. Results

### 4.1 Counts and classes

All 2,134 records are gold (tier G); `label_provisional` is false for every record.

| | Records | Irreversible | Partially reversible | Reversible |
|---|---|---|---|---|
| Sandbox | 2,129 | 577 | 756 | 796 |
| ScienceWorld | 5 | 0 | 2 | 3 |
| **Total** | **2,134** | **577 (27.0%)** | **758 (35.5%)** | **799 (37.4%)** |

- **By horizon:**
  - h1: I 595, P 786, R 753;
  - h2 and h3: identical. h1 differs from h3 on 46 records.
- **From the ADR-0010 families:** 859 records (I 403, P 235, R 221). The rest come from the
  v1.0 families and ScienceWorld.
- **Held out from gold:** 26 OQ-21-sensitive (tier P) records are in
  `sensitivity_oq21.jsonl`. They are not gold and are not in the split.

### 4.2 Minimal pairs

**878 records in strict minimal pairs, 41.1%** (439 pairs). All pairs are in the sandbox.

| Pair source | Records |
|---|---|
| Primary family action (v1.0 and ADR-0010 families) | 812 |
| Share-link families | 42 |
| Alternative actions (C2) | 24 |

### 4.3 Scenario-grouped split

| | Records | Groups | I | P | R |
|---|---|---|---|---|---|
| Train | 1,709 | 124 | 424 | 554 | 731 |
| Test | **425 (19.9%)** | 27 | 153 | 204 | 68 |

- **Leakage:** no group crosses the split, and no minimal pair crosses it (81 pairs are in
  test).
- **Render styles:** `compact` (142 records) appears only in test.
- **ScienceWorld:** split by task family. `sw-grp-power-workshop` (1 record) is in test.
- **Families not in test:** A2, B1, B2, B3 and S3 have no test records. Whole scenario groups
  are assigned to test, so not every family can be represented there.

**Test-set class imbalance (accepted by Member 1, ADR-0010 Amendment 1).**
- Reversible records are 16% of the test set, but 37% of the dataset.
- Only 8.5% of all R records are in test, against 26.5% of I and 26.9% of P.
- The gates and the validator check class shares over the whole dataset, not per split. The
  seeded split search targets 20% per class but did not reach it for R with whole groups.
- **Consequences for reporting:**
  - report per-class test results and balanced accuracy or macro-F1;
  - treat R test estimates as noisier (68 records);
  - bootstrap over scenario groups.

### 4.4 Scenario diversity and concentration (sandbox)

| Measure | v2.0 | v1.0 |
|---|---|---|
| Distinct scenarios: strict / coarse / number-masked | 323 / 253 / 183 | 133 / 114 / 89 |
| Effective number-masked scenarios (inverse Simpson) | 123.8 | 55.0 |
| Share of the top 10 number-masked scenarios | 16.5% | 30.7% |
| Max records per coarse / number-masked scenario | 18 / 51 | 12 / 24 |
| Max family share | 7.97% (cap 8%) | 7.89% |
| SD3 conflicting groups, strict / coarse | 0 / 0 | 0 / 0 |
| Declared-depth disagreements | 28 (§5) | 0 |

- **Coarse scenarios can exceed the cap of 6.** The cap applies to admitted units per coarse
  scenario. Each unit is then rendered in up to three styles, minus template-signature drops,
  so a coarse scenario can hold more than 6 records.
- **Build drops:**
  - 15,988 candidates were dropped as `scenario_full`;
  - 102 renders hit the template-signature cap (≤ 3);
  - 247 units or records were removed by the family cap.

Per-family counts are in `generation_report.json`.

## 5. The 28 declared-rule mismatches (oracle labels remain valid)

`meta.declaration_agrees` compares the oracle's restore depths with the depths declared by the
single-step design rules (`declared_reversibility`). It is informational only: **the label
always comes from the oracle.**

| | Count | Declared (exact, approx) | Oracle (exact, approx) | Label (h3) |
|---|---|---|---|---|
| Family B1, fresh-backup member | 28 | (none, 1) | (2, 1) | reversible |

- **Who is affected.** All 28 mismatches are the fresh-backup member of B1 (edit A again after
  an earlier edit). The stale-backup members all agree with the declared rule.
- **Why the declared rule differs.** The earlier edit moves the file one revision ahead of its
  "fresh" backup. The declared rule grants an exact one-step restore only when the backup
  equals the current file, and it ignores earlier actions. So it declares no exact restore.
- **What the oracle finds.** An exact two-step restore: `restore_backup` brings back the
  pre-edit file, then `edit_file` re-types the earlier edit's text, which is visible in the
  state. This was reproduced directly in the sandbox.
- **Why the label is right.** Depth 2 is within the 3-step horizon, so R at h3 is correct (at
  h1 the record is P). The stale member has no exact restore and is P, so the pair flips R/P as
  ADR-0010 designed. Both methods agree on the approximate depth (1).
- **Not a labeling bug.** The validator re-ran the oracle and replayed every witness without
  error.

## 6. Robustness subset (≤ 3 per scenario)

Up to 6 surface variants can now share a coarse scenario. To check that results are not driven
by this redundancy, `robustness_subset_le3.json` lists a deterministic subset.

- **Rule (`families_v2.capped_subset`):**
  - at most 3 records per coarse scenario; each ScienceWorld record counts as its own scenario;
  - a minimal pair is one unit and enters only if **both** members' scenarios have room;
  - units are taken smallest first, then by pair id or record id.
- **Result:** **707 records** (I 178, P 253, R 276) over 256 coarse scenarios, of which 580 are
  in train and 127 in test.
  - 136 complete minimal pairs (38.5% of records) and **0 split pairs**;
  - at most 3 records in any coarse scenario.
- **Test part of the subset:** I 39, P 60, R 28.
- **Use:** filter `records.jsonl` by `ids` and keep the given split. Report the main metrics on
  the full dataset and on the subset.
- **Recompute it** with `families_v2.capped_subset(records)`. The generator checks that the
  file equals a fresh computation.

## 7. Professor requirements

| Requirement | Status |
|---|---|
| ≥ 2,000 labelled pairs from both testbeds | **Met.** 2,134 records, of which 5 are from ScienceWorld. The robustness subset has 707. |
| Roughly balanced classes | **Met overall** (27.0 / 35.5 / 37.4%). The test split is imbalanced (R 16%); report balanced accuracy. |
| 20% test set, split by scenario | **Met.** 19.9%, scenario-grouped. |
| ≥ 30% minimal pairs | **Met.** 41.1% (subset: 38.5%). |

## 8. Loading v2.0 (for Member 2)

The loader needs no change: `load_dataset` reads v2.0 exactly as it reads v1.0. v1.0 stays
where it is, so both can be used side by side.

```python
import json

from adnn.dataset.api import load_dataset

ds = load_dataset("data/production/v2.0")   # verifies checksums and builder version
train = list(ds.iter_split("train"))         # 1,709 records
test = list(ds.iter_split("test"))           # 425 records
pairs = ds.minimal_pairs()                   # 439 pairs
subset = set(json.load(open("data/production/v2.0/robustness_subset_le3.json"))["ids"])  # 707
```

- **Getting the data.** Unpack the team bundle and verify it:

  ```bash
  tar -xzf adnn-dataset-v2.0.tar.gz && sha256sum -c adnn-v2.0-SHA256SUMS.txt
  ```

  The bundle holds the dataset, the 8 ScienceWorld evidence files the validator re-checks, and
  `data/scaling_pilot/records.jsonl` (a protected input).
- **Validate the copy:** `python -m adnn.dataset.validation data/production/v2.0` should
  report 0 errors and 0 warnings. It takes several minutes, because it re-runs the oracle.
- **Same rules as v1.0:**
  - do not re-split by row;
  - draw any folds over `scenario_id` groups.

## 9. Reproduce

```bash
SW="$LOCALAPPDATA/adnn-sw"
ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
  .venv/Scripts/python.exe scripts/dataset/v2_generate.py --out data/production/v2.0
```

- **The script refuses to run** unless:
  - the amended manifest matches its sidecar;
  - HEAD descends from `4ae4cd4`;
  - `src/adnn` matches `code_sha256`;
  - the config, the ScienceWorld evidence and the 17 protected hashes match.
- **Expected checksums:** those in §2.
- **Requirements:** about 6 GB of free RAM and about 20 minutes. The pinned ScienceWorld
  runtime is needed for the 5 ScienceWorld state texts.
- **Reproducing v1.0:** use its own generator from a checkout of `dab91ff` (docs/34 §6).
