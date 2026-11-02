# ADR-0010: Dataset v2.0: new action situations from existing sandbox mechanisms (research decision log)

- **Status:** *Accepted* (2026-11-02), with Amendment 1. The scope was approved by Sneha (M1)
  on 2026-11-01 and recorded **before** the v2.0 manifest was frozen. Sneha approved the cap-6
  feasibility result and adopted it on 2026-11-02. The frozen manifest is
  `docs/preregistration/production_manifest_v2_amend1.json`. It amends
  `production_manifest_v2.json`, which is kept unchanged, to fix the robustness-subset helper.
  The report is docs/37 and the data card docs/38.
- **No professor approval is claimed and the professor was not contacted.**
- **Builds on:**
  - ADR-0006 (D3, D5, D6, D8, D11);
  - ADR-0009, including Amendment 1;
  - docs/31 §7 (scenario supply is the binding constraint).
- **Does not change:**
  - dataset v1.0, its files, manifests or checksums. Member 2 uses it as frozen;
  - the oracle, the gold rules, the 3-step horizon or the OQ-21 handling;
  - the ≤ 3 records per template-signature cap. The surface-variant cap goes from 4 to 6
    per coarse scenario, for v2.0 only (Amendment 1);
  - the 8% family cap, the ≥ 30% strict minimal-pair floor or the scenario-grouped split.

## Context

- **The size limit.** v1.0 has 621 gold records, below the professor's target of ≥ 2,000. The
  production build rejected 13,760 candidates as `scenario_full`: the v1.0 generators keep
  producing the same scenario shapes.
- **The structural cause.** Every v1.0 world has the same shape, and the judged action is
  always one of 4 tools.
- **The probe (Phase 6A).** It tried every existing tool as the judged action, with at most
  one earlier action, under every combination of existing settings, changing one setting at a
  time. Labels used the production gold rule.

## Decision

**New families**, built only from existing tools, settings and the sandbox. They are
implemented in `src/adnn/dataset/families_v2.py` (`families-v2-1.0`).

| ID | Judged action (after) | Pivot | h3 labels | Kind |
|---|---|---|---|---|
| A1 | `restore_backup` A | backup fresh / stale | R / I | pair: new judged tool and mechanism |
| A2 | `restore_backup` A (after deleting A with the bin on) | current bin on / off | P / R | pair: new judged tool |
| B1 | edit A again (after an edit) | backup fresh / stale | R / P | pair: recombination with history |
| B2 | delete A (after an edit) | bin on / off | R / I | pair: recombination with history |
| B3 | delete B (after deleting A with the bin on) | current bin on / off | R / I | pair: recombination with history |
| B4 | pay payee 2 (after paying payee 1) | refundable / final | P / I | pair: recombination with history |
| S1 | `restore_backup` A (after an edit) | — | I | non-pair |
| S2 | `revert_file` A (after an edit) | — | I | non-pair |
| S3 | `restore_file` from the bin (after deleting A) | — | P | non-pair |

**Strict pairs.** A2 and B3 run their earlier deletion with the bin on in **both** members.
The members then differ only in `config.recycle_bin_enabled`, which satisfies D6 and the
validator's strict-pair check.

**Background settings.** Settings other than the pivot are sampled per draw, only from the
combinations the probe found gold. This is the families' only source of extra diversity.

**Not included:** C1 and C2 (payments from the second account). They are the same mechanisms
as v1.0's payment families and are deferred unless separately approved.

**Code changes to existing modules, with v1.0 behaviour unchanged:**
- `production.admit` and `production.build` accept an optional candidate source; the default
  is the v1.0 `candidate_groups`;
- `Unit` gains an optional `family_domain`.

`ProductionConfig()` and its sha256 are unchanged; this is checked against the frozen v1.0
manifest by `tests/test_families_v2.py`.

**v2.0 configuration.** Every v1.0 rule and the seed are unchanged; only the generator version
changes, to `production-gen-2.0`. v2.0 is a separate dataset, `adnn-dataset-2.0`, with its
own manifest.

**Reproducing v1.0.** Its frozen generator requires `src/adnn` to be identical to `dab91ff`.
Regenerate v1.0 from that commit, for example with a `git worktree`, and not from this branch.

## Next steps (prospective)

1. Run the oracle-labelled feasibility check (`scripts/dataset/v2_feasibility.py`).
2. If 2,000 is not reached, report the measured total and stop. No C1/C2, no relaxed caps
   (except the single cap-6 experiment of Amendment 1).
3. Freeze a v2.0 manifest, then generate and validate. This happens only after review.

**Outcome (2026-11-02).** The cap-4 run gave 1,521 sandbox records and the cap-6 run 2,134
records in total. Cap 6 was adopted, and v2.0 was frozen (`v2_freeze_manifest.py`) and then
generated (`v2_generate.py`). The first run's robustness subset split 17 minimal pairs. The
helper was fixed and the manifest re-frozen as v2 amendment 1, and the regenerated records
and split are byte-identical to the first run. See docs/37 §1.

## Amendment 1 (2026-11-02): a variant cap of 6 per scenario

- **Status:** *Accepted* (2026-11-02). It started as one feasibility experiment approved by
  Sneha (M1). Sneha reviewed the result (2,134 records, all gates and the validator passed)
  and adopted it, accepting the reversible-class imbalance in the test split (below).
- **What changes:** for v2.0, the per-coarse-scenario surface-variant cap,
  `surface_variants`, goes from 4 to 6 (`families_v2.SURFACE_VARIANTS`, used by
  `v2.config()`). v1.0 keeps 4.
- **What does not change:**
  - the gold-label criteria and the 3-step recovery horizon;
  - the ≤ 3 records per template-signature cap (D5);
  - the 8% family cap and the ≥ 30% strict minimal-pair floor;
  - the scenario-disjoint train/test split;
  - dataset v1.0, its files, manifest and checksums.
- **Why:** the cap-4 feasibility run produced 1,521 sandbox records, short of 2,000. Most
  rejections (16,272) were `scenario_full`, so the cap, not the families, is the binding
  limit.
- **Limitations:**
  - Up to 6 records can now share a coarse scenario. They are surface variants (rendering
    style, task wording, names and amounts), not new mechanisms, so the effective number of
    distinct situations grows much less than the record count.
  - Test-set metrics can be inflated by near-duplicates; the scenario-disjoint split stops
    leakage between train and test, but not within-split redundancy.
  - To support a robustness check, the report also gives the size of a **≤ 3-per-scenario
    capped subset** (pairs kept whole). Results should be checked on that subset as well.
  - The cap is changed once. If the result is short of 2,000, the measured result is reported
    and nothing more is changed: no further cap increase and no C1/C2 families without
    separate approval.
- **ScienceWorld:** the feasibility runs reused the 5 frozen v1.0 ScienceWorld records. The
  final generator re-exports them from the frozen evidence, as v1.0 did, splits them by the
  v1.0 rule and checks that they equal the v1.0 records, apart from `dataset_version`.
- **Accepted imbalance (test split).** The test split has fewer reversible records than the
  other classes. In the cap-6 run, test held 68 R, 204 P and 153 I records, so only 8.4% of
  R records against 26–27% of P and I. The gates and the validator check class shares over
  the whole dataset, not per split. Sneha accepted this: report per-class test results and
  balanced accuracy or macro-F1, and treat R test estimates as noisier.
- **Declared-rule mismatches (informational).** All 28 are the fresh-backup member of B1. The
  earlier edit leaves the file one revision ahead of the backup, so the single-step design
  rule declares no exact restore. The oracle finds an exact two-step restore
  (`restore_backup`, then re-type the earlier edit). That is within the 3-step horizon, so the
  oracle label R is correct. The label always comes from the oracle (docs/37).
