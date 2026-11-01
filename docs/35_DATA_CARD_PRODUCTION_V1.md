# Data card: ADNN production dataset v1.0 (`adnn-dataset-1.0`)

## Summary

- **Purpose.** Each record pairs an agent state with a candidate tool action. The task is to
  label the action **reversible**, **partially reversible** or **irreversible** within a
  recovery horizon h = 1–3; h3 is primary.
- **Uses.** It serves RQ1 (linear probes on hidden states) and RQ2 (stated judgments).
- **Size.** 621 gold records: 616 from the tool-use sandbox and 5 from ScienceWorld.
- **Report.** Full generation and validation details are in docs/34.

| Path | `data/production/v1.0/` (git-ignored; reproducible, see docs/34 §6) |
|---|---|
| Records file sha256 | `b5a7d58f342fbc2ef7c0658a0dd2a9ffc99c95f8153c8aa1d79bcb70620e20dd` |
| Frozen manifest | `docs/preregistration/production_manifest_amend1.json` (`729bcd7c…`) |
| Created | 2026-11-01, by Member 1 (sandbox core) |

## Composition

| | I | P | R | Total |
|---|---|---|---|---|
| Sandbox | 110 | 230 | 276 | 616 |
| ScienceWorld | 0 | 2 | 3 | 5 |
| **All** | **110 (17.7%)** | **232 (37.4%)** | **279 (44.9%)** | **621** |

**Sandbox families.** There are 18 families with records:
- file delete or edit;
- email undo;
- payment cancel, refund or two-step;
- share links.

No family exceeds 8% of records. The sandbox covers 89 number-masked scenarios (55 effective).

**Minimal pairs.** 112 pairs, which is 224 records (36.1%). Within each pair the action text is
identical, the state differs in one pivot condition, and the gold labels are opposite.

**ScienceWorld.** There are 5 hand-audited cases from 2 task families:
- open fridge;
- move cup;
- connect battery wire;
- two burn cases with a certified residual.

**Render styles.** `kv` 289, `prose` 289 and `compact` 43; `compact` is used only in the test
set.

## Labels

- **Sandbox.** An exact breadth-first oracle searches for a recovery within h steps.
  - A record is gold only if the search is complete, the judged action succeeds, no timers are
    pending, and the label does not change under the OQ-21 alternative reading.
  - Partial reversibility follows `scaling_pilot.PARTIAL_RULE` (team-adopted, ADR-0006 D11).
- **ScienceWorld.** Labels come from the frozen `sw-admission-2` decisions. Each case also has:
  - R5 replication;
  - a query-order audit;
  - a symmetry check;
  - a rubric stability check;
  - for the partially reversible cases, an admissible certificate for the residual.
- **No human annotation has been done.** All labels are oracle-derived.
- **Not gold.** 19 OQ-21-sensitive records are in `sensitivity_oq21.jsonl`, tier P. They are
  never gold and are for robustness analysis only.

## Split

- **Assignment.** A 20% test set is drawn by scenario group: a number-masked scenario together
  with its pair. The result is 132 test records (21.3%) in 12 groups, and 489 train records in
  68 groups.
- **Kept together.** Minimal pairs and near-duplicate surface variants never cross the split.
- **ScienceWorld** is split by task family: 1 record in test.

## Intended use

- **For:**
  - training and evaluating probes and classifiers on train/test as given;
  - minimal-pair analyses;
  - stated-versus-internal comparisons.
- **Reporting:**
  - report balanced accuracy, since the classes are imbalanced;
  - report "N records over K scenarios", because records within a scenario are not
    independent;
  - bootstrap over scenario groups.
- **Not for:**
  - claims about real-world tools or environments beyond these simulated families;
  - per-testbed claims about ScienceWorld (n = 5, 1 in test).

## Limitations

1. **Below the size target.** 621 records against the professor's target of ≥ 2,000
   (REQ-DATA-01 not met). The limit is the adopted ≤ 8% per-family cap combined with the limited
   scenario shapes of the families.
2. **Class imbalance.** Irreversible records are 17.7% of the total (30 in test).
3. **ScienceWorld is token-sized.** 5 records (0.8%), none of them in minimal pairs.
4. **Scenario concentration.** 616 sandbox records cover 89 masked scenarios, and the top 10
   hold 30.7% of records.
5. **Held-out style.** `compact` appears only in test, so the test set mixes a scenario shift
   with a style shift. Analyses can be stratified by `render_style`.
6. **Horizons barely differ.** h2 and h3 labels are identical, and h1 differs on 15 records.
7. **Team decisions.** The partial definition and the ADR-0008/0009 production rules were
   adopted by the team and are not professor-approved (OQ-21 is open).
8. **Not yet produced.** ADR-0008 pre-registered two items that are not materialised as files:
   - the ≤ 3-per-scenario sensitivity subset (B3);
   - a secondary family-disjoint split (B4).
