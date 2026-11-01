# ADR-0009: Production dataset v1.0: grouping fix, alternative-action minimal pairs, grouped split, ScienceWorld export (research decision log)

- **Status:** *Adopted for production generation* by the research team (M1), 2026-11-01. It
  is recorded **before** the production manifest is frozen and before any production record
  is generated. **No professor approval is claimed and the professor was not contacted.**
- **Builds on and amends:** ADR-0008 (Protocol B). B1–B4 and B6 are kept; B2 and B5 are
  amended below. Also ADR-0006 D3/D5/D6/D8/D9/D11 and ADR-0005.
- **Evidence:**
  - docs/33 (Phase 5G);
  - docs/34 (Phase 5H feasibility and production);
  - `results/phase5h/feasibility.json`.
- **Does not change:**
  - the oracle or any label definition;
  - `scenario_diversity` 0.2;
  - the frozen Phase 5B and 5E manifests;
  - the Candidate A spec;
  - historical records;
  - prompt builder 1.0.0;
  - `sw-admission-2`;
  - any stored ScienceWorld evidence.

## C1: Scenario grouping fixes f13 (`production-grouping-1.0`)

**Problem.** In f13 the label of a transfer depends on whether its amount exceeds the
configured refund fee:
- fee 20, amount 15: nothing is refunded, so **irreversible**;
- fee 20, amount 35: **partially reversible**.

The fee is configuration, which canonical forms keep verbatim, so it never enters the number
relations. Behaviourally different states therefore shared a scenario (docs/33 §3).

**Fix.** The production grouping adds the order relation `amount_vs_refund_fee`, one of
`<`, `=` or `>`, to the strict, coarse and number-masked forms.

**Effect.**
- Labels are untouched.
- SD3 conflicts fall from 3 to **0**, at strict and coarse level.

## C2: Minimal pairs from existing alternative actions

**Rule.** Each legacy family already renders two Phase 5B alternative actions (edit or delete
the second file, pay the second payee, internal transfer) on its world. In production, each
alternative action is assessed at **both** pivot values.

**When it counts as a pair.** Only if both members are gold and the oracle gives them
different h3 labels. It then satisfies every ADR-0006 D6 and validator condition:
- byte-identical action and task text;
- states that differ only in the family's pivot scope;
- a visible pivot;
- opposite gold labels.

**Otherwise.** Only the member at the Phase 5B pivot position is kept, as a non-pair record.
This is the earlier behaviour.

**What is not done.** No new tool, mechanism, pivot or recovery evidence is introduced.

## C3: Cap, render styles and held-out style

- **At most 4 gold surface variants per production coarse scenario**, admitted pair-atomically.
- **`compact` stays test-only** (`TEST_ONLY_STYLES`, unchanged validator rule). Training
  scenarios render in `kv` and `prose`, test scenarios in all three styles.
- **So the per-scenario cap of ADR-0008 B2 becomes 8 records in training and 12 in test.** It
  is not raised.

## C4: Selection order

This applies prospectively and deterministically.
1. **Unit selection, before the split:**
   - first the ADR-0006 D5 family cap of ≤ 8% of units;
   - then the professor's ≥ 30% minimal-pair floor, with a 1-point margin.

   Non-pair units are dropped first (latest draw first), pairs only whole.
2. **Rendering**, with the D5 cap of ≤ 3 records per template signature. A pair member orphaned
   by D5 is dropped.
3. **Final record-level trim**, so that the family cap holds exactly.

## C5: Scenario-grouped split (replaces family-held-out for production)

**Groups.** A group is a number-masked production scenario joined with `pair_id`. A record's
`scenario_id` *is* its group.

**Assignment.** Whole groups go to test by a seeded, deterministic stratified search
targeting 20% of records overall and per class.

**Validator.** For `kind: scenario_grouped` splits it checks:
- every record is assigned;
- no group, number-masked scenario or minimal pair is on both sides;
- held-out styles appear only in test;
- no identical (`state_text`, `action_text`) appears in both splits.

**Loader.** `api.split_of` follows the split's `kind`. Family-held-out datasets are unchanged.

## C6: ScienceWorld export

**Cases.** Only the 5 candidates with complete tier-G evidence are exported:
- R5 replication;
- query-order audit;
- symmetry;
- rubric stability;
- for partials, an admissible certificate protecting the residual.

**Excluded.** `ctrl-open-cupboard` and `registry-miss-connect-v2` are not exported and not
counted.

**Labels.** Labels come from the frozen decisions. A horizon below the witness depth is
unresolved, and such a case is not exported. All 5 have witness depth 1.

**Text.** `state_text` is `look` + `inventory`, taken after a pinned replay whose S0
fingerprint must equal the evidence.

**Validation.** The validator re-checks ScienceWorld records against the stored evidence
instead of the sandbox replay.

**Split.** ScienceWorld is split by task family (ADR-0006 D9).

## C7: Production gate (amends ADR-0008 B5)

**Generation may run only if the frozen configuration passes all of these:**
- ≥ 30% strict minimal-pair records;
- every family ≤ 8%;
- SD3 = 0;
- test fraction 18–22%;
- `compact` never in train;
- 0 validator errors.

The Phase 5H feasibility check passed all of them (docs/34).

**2,000 records is the professor's target, not a gate.** If it is missed, REQ-DATA-01 is
reported **unmet**, with the achieved count (ADR-0006 D8). The cap, the family cap and the
gold rules are never relaxed to reach it.

## C8: Prompt builder and tier-P records

- **One builder.** All production records use prompt builder 1.1.0, so that one manifest holds
  legacy, link and ScienceWorld records.
- **Tier P.** OQ-21-sensitive units are written to `sensitivity_oq21.jsonl` (tier P), never to
  the gold file and never split (ADR-0006 D11).

## Amendment 1 (2026-11-01): two corrections found by the first generation run

**Why.** The first run from the original freeze (`production_manifest.json`, sha256
`39ccc1e3…`, freeze commit `1dab774`) wrote its files, but it is **not a valid dataset**.
- The full validator reported one error: in `sw-h4-open-fridge` the action text occurs twice
  in the probe prompt.
- The run then crashed in its own report step.

The sandbox records of that run matched the feasibility hash (`4033fca2…`). The run's output
was set aside and was never released.

**A1: ScienceWorld tool description.** The description of the `scienceworld_action` tool
gave the example commands `'open fridge'` and `'move cup to table'`. The first is exactly the
action of `sw-h4-open-fridge`, so the probe position could not be located uniquely.
- The description now has **no example commands**.
- The action, environment, state text, evidence, oracle and gold label are unchanged.
- Only the 5 ScienceWorld prompt hashes change.

**A2: generation report.** `production.summarise` expected `meta.scenario_keys` on every
record, and ScienceWorld records have none.
- Scenario, SD3 and diversity measures now cover the records that have scenario keys (the
  sandbox).
- ScienceWorld records are counted separately (`scienceworld_records`).
- For sandbox-only input the output is unchanged, so the feasibility result stands.

**What this amendment does not change:**
- the configuration, its sha256, gates, grouping, label rules, oracle, split rule or
  `DATASET_VERSION`;
- the professor's requirements;
- the original freeze and its sidecar, which are kept unchanged as historical artifacts and
  listed among the protected hashes.

**Procedure.**
1. Regression tests for A1 and A2 (`tests/test_production_dataset.py`) fail without the
   fixes.
2. The fixes are committed.
3. A new manifest, `production_manifest_amend1.json`, is frozen prospectively, with `amends`
   pointing to the original.
4. The dataset is regenerated once from the new manifest.

**Acceptance.** The regenerated sandbox records must hash to `4033fca2…`.
