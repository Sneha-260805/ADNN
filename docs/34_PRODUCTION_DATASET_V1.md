# 34 — Production dataset v1.0: generation and validation report (Phase 5H)

- **Status:** generated and fully validated on 2026-11-01. Ready for Member 2.
- **Path:** `data/production/v1.0/`. It is git-ignored; reproduce it with §6.
- **Decision record:** ADR-0009, including Amendment 1.
- **Approval:** no professor approval is claimed. Labels come from the oracle; **no human
  annotation has been done.**

## 1. Provenance

| Item | Value |
|---|---|
| Frozen manifest (used) | `docs/preregistration/production_manifest_amend1.json`, sha256 `729bcd7ca17d74406f25345874623b4c422cea9c5731ed95f194d77f0bf1620d`; freeze commit `59ad1c5`, base commit `dab91ff` |
| Original freeze (historical, unchanged) | `docs/preregistration/production_manifest.json`, sha256 `39ccc1e3…`; commit `1dab774` |
| Generation config sha256 | as frozen (`generation.config_sha256`), unchanged by the amendment |
| Generator / grouping / exporter | `production-gen-1.0` / `production-grouping-1.0` / `sw-export-1.0` |
| Prompt builder | 1.1.0, for all records |
| Partial-definition policy | team-adopted (ADR-0006 D2/D11) |
| Dataset version | `adnn-dataset-1.0` |
| Generation runtime | 291 s, one foreground run, with 6.6 GB RAM available |

**History.** The first run, from the original freeze, wrote files that failed validation:
`sw-h4-open-fridge` had its action text twice in the probe prompt, and the report step crashed.
- That output was set aside unreleased in `data/production/superseded-run1-invalid/`.
- Both defects were fixed and regression-tested (ADR-0009 A1, A2), then the manifest was
  re-frozen.
- Compared with that run, only the probe and stated prompt hashes of the 5 ScienceWorld
  records changed. Every label, state text and sandbox record is identical.

## 2. Checksums (sha256)

| File | sha256 |
|---|---|
| `records.jsonl` | `b5a7d58f342fbc2ef7c0658a0dd2a9ffc99c95f8153c8aa1d79bcb70620e20dd` |
| `split.json` | `cd60ceb391e701a9e5603792baf4ad617f5594240fe6787d941de77460d90db2` |
| `tool_sets.json` | `a45f798be15a7019dca356334f83fe1be5fa99741d7d8b813cda31e9e09eba33` |
| `sensitivity_oq21.jsonl` | `8d6b8b86e672e3d5628a9bc0748f4ffa0d68c4cd6a271183343ee5d2bf372ce2` |
| `manifest.json` | `f869791d1c104eca920caa18f620af9837725032890afdba9e25d8e127971667` |
| Sandbox records (`stable_json`, id order) | `4033fca2bbc22d52ee20450ec82916a791fed2ff95c6df0331bef95a30161efc`, **identical to the Phase 5H feasibility runs** |
| ScienceWorld records | `2918735becf2e4840219d368d05470e3df577ba38aebdfb25c156cf888c7ec08` |

`generation_report.json` is not listed: it records the HEAD commit and the runtime, so its hash
differs between reproductions.

## 3. Validation

The full validator (`validate_directory`, team policy) reports **0 errors and 1 warning**. The
warning is that the irreversible class is 17.7% of records, below 25%.

| Check | Records covered |
|---|---|
| Schema | 621 |
| Provisional and tier fields | 621 |
| Prompts: hash rebuilt, action text located exactly once in the probe prompt | 621 |
| Oracle re-run (sandbox) | 616 |
| Witness replay (sandbox) | 616 |
| Share-link restoration | 36 |
| ScienceWorld evidence re-check | 5 |
| Strict minimal pairs | 112 |
| Uniqueness, label consistency, builder version, file hashes, scenario-grouped split | dataset-wide |

Independent re-checks (`results/phase5h/verification.json`):
- the loader rebuilds all 621 prompt hashes;
- every manifest checksum matches;
- the frozen manifest matches its sidecar;
- all protected artifacts are unchanged: the historical records, the Phase 5B/5D/5E freezes and
  the original production freeze.

## 4. Results

### 4.1 Counts and classes

All 621 records are gold (tier G); `label_provisional` is false for every record.

| | Records | Irreversible | Partially reversible | Reversible |
|---|---|---|---|---|
| Sandbox | 616 | 110 | 230 | 276 |
| ScienceWorld | 5 | 0 | 2 | 3 |
| **Total** | **621** | **110 (17.7%)** | **232 (37.4%)** | **279 (44.9%)** |

- **By horizon:**
  - h1: I 125, P 232, R 264;
  - h2 and h3: identical, I 110, P 232, R 279.
- **Held out from gold.** 19 OQ-21-sensitive (tier P) records are in `sensitivity_oq21.jsonl`.
  They are not gold and are not in the split.

### 4.2 Minimal pairs

There are **224 records in strict minimal pairs, 36.1% of all records** (112 pairs). Every pair
is in the sandbox.

| Pair source | Records |
|---|---|
| Primary family action | 168 |
| Share-link families | 36 |
| Alternative actions (C2) | 20 |

Each pair has byte-identical action and task text, opposite gold labels, and states that differ
only in the family pivot. The validator checks all of this.

### 4.3 Scenario-grouped split

| | Records | Groups | I | P | R |
|---|---|---|---|---|---|
| Train | 489 | 68 | 80 | 173 | 236 |
| Test | **132 (21.3%)** | 12 | 30 | 59 | 43 |

- **Test share of each class:** I 27.3%, P 25.4%, R 15.4%.
- **Leakage:** no group, number-masked scenario, minimal pair or identical input appears on
  both sides.
- **Render styles:** `compact` appears only in test (43 records). Train uses `kv` and `prose`.
- **ScienceWorld:** split by task family. `sw-grp-power-workshop` (1 record) is in test and
  `sw-grp-boil-kitchen` (4 records) in train.

### 4.4 Scenario diversity and concentration (sandbox)

| Measure | Value |
|---|---|
| Distinct scenarios: strict / coarse / number-masked | 133 / 114 / 89 |
| Effective number-masked scenarios (inverse Simpson) | 55.0 |
| Share of the top 10 number-masked scenarios | 30.7% |
| Max records per coarse / number-masked scenario | 12 / 24 |
| Max family share | 7.89% (cap 8%) |
| SD3 conflicting groups, strict / coarse | 0 / 0 |
| Declared-depth disagreements | 0 |

Per-family counts range from 6 (f14) to 49; s03 contributes no records. The full list is in
`generation_report.json`.

### 4.5 ScienceWorld

| Case | Label (h1–h3) | Split |
|---|---|---|
| h4-open-fridge | reversible | train |
| h4-move-cup-to-table | reversible | train |
| h4-connect-battery-wire | reversible | test |
| h4-burn-painting-water-near | partially reversible (certified residual) | train |
| h4-burn-chair-water-near | partially reversible (certified residual) | train |

- **Evidence.** All 5 pass every evidence check, and all have witness depth 1, so no horizon is
  unresolved.
- **Excluded and not counted:** `ctrl-open-cupboard` and `registry-miss-connect-v2`. They have
  no R5 replication, query-order audit or rubric check.

## 5. Professor requirements

| Requirement | Status |
|---|---|
| ≥ 2,000 labelled pairs from both testbeds | **Not met.** 621 records (31% of the target), of which 5 are from ScienceWorld. Reported as unmet under ADR-0006 D8; no rule was relaxed. |
| Roughly balanced classes | **Not met.** Irreversible is 17.7% of records, so class counts are reported here and balanced accuracy must be used. |
| 20% test set, split by scenario | **Met.** 21.3%, scenario-grouped. |
| ≥ 30% minimal pairs | **Met.** 36.1%. |

## 6. Reproduce

```bash
SW="$LOCALAPPDATA/adnn-sw"
ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
  .venv/Scripts/python.exe scripts/dataset/phase5h_generate.py --out data/production/v1.0
```

- **The script refuses to run** unless:
  - the amended manifest matches its sidecar;
  - HEAD descends from `dab91ff`;
  - `src/adnn` is unchanged since that commit;
  - the config, the ScienceWorld evidence and the protected hashes match.
- **Expected checksums:** those in §2.
- **Memory:** it needs about 6 GB of free RAM. The pinned ScienceWorld runtime is needed only
  for the 5 ScienceWorld state texts.
