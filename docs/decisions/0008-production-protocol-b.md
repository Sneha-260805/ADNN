# ADR-0008: Production protocol B: scenario cap, sensitivity subset, split grouping and the team-adopted partial marker (research decision log)

- **Status:** *Proposed* (2026-11-01); **amended and superseded for production by ADR-0009** (B2 cap with `compact` test-only, B5 gate). It is **not adopted for production generation**: the
  Phase 5G dry run (docs/33) fails the professor's minimal-pair requirement at full size
  (B5). No production manifest is frozen and no production record is generated.
  **No professor approval is claimed and the professor was not contacted.**
- **Date:** 2026-11-01
- **Deciders:** Sneha (M1) drafted it. M2 and M3 are to review it as consumers. M2/M3 work
  has not started.
- **Builds on:**
  - ADR-0006 (D2, D3, D5, D6, D8, D9, D11);
  - ADR-0007;
  - docs/27 §6 (SD1–SD3);
  - docs/31 (capacity audit);
  - docs/32 (protocol memo).
- **Does not change:**
  - the frozen Phase 5B and Phase 5E manifests, their sidecars or their gates (SD1–SD3 stay
    in force for the Phase 5E pilot);
  - the Candidate A spec;
  - `pilot_v0.1` or any generated record;
  - prompt builder 1.0.0;
  - label definitions;
  - the oracle;
  - `sw-admission-2`.

## B1: Professor requirements versus team production rules

**Professor requirements** (specification §4.2, §4.3, §6 Step 1; REQ-DATA-01/02/03/05). These
are binding:

| Requirement | Text |
|---|---|
| Size | "Target at least 2,000 labelled (state, action) pairs in total, from both testbeds" |
| Balance | "Keep the three classes roughly balanced; if they are not, report the class counts and use balanced accuracy" |
| Split | "Keep 20% aside as a test set, split by task or scenario, not by individual action" |
| Minimal pairs | "At least 30% of your data must be minimal pairs" |

**Team rules for production.** This ADR proposes the following; they apply only after
adoption, and only prospectively:

| Team rule | Production status under this ADR |
|---|---|
| SD1 (≥ 50% of records in coarse scenarios new against priors) | **Superseded for production.** It measures expansion against earlier pilots, but production regenerates the whole dataset. Novelty against the priors is *reported*, not gated. |
| SD2 (≤ 3 records per coarse scenario) | **Superseded for production** by B2. The ≤ 3 form becomes a sensitivity subset (B3). |
| SD3 (0 behaviourally conflicting groups) | **Kept** as a hard gate, at coarse level. |
| ADR-0006 D3 tiers, D6 strict pairs, D11 partial rule | **Kept.** |
| ADR-0006 D5: ≤ 3 per surface-masked template signature | **Kept.** |
| ADR-0006 D5: ≤ 8% per family | **Kept.** |
| ADR-0006 D5: effective fraction ≥ 0.6 | **Kept**, as reported. |

## B2: Scenario cap

- **At most 12 gold records per coarse scenario:** at most 4 surface variants (distinct
  (state, action) draws with the same coarse canonical form), each rendered in the 3 render
  styles.
- **The cap is fixed before generation and is never raised after seeing yield.**
- If yield is short, ADR-0006 D8 applies: REQ-DATA-01 is reported as unmet.

## B3: Sensitivity subset

- RQ1 and RQ2 are re-analysed on a pre-registered subset with at most 3 records per coarse
  scenario: one surface variant in 3 styles, with minimal pairs kept atomic.
- A material difference between the full set and the subset is reported as evidence of
  scenario memorisation.

## B4: Split grouping and inference unit

**Primary split.**
- It is scenario-disjoint at the record level, with 20% of records in the test set.
- Groups are the union of number-masked coarse scenarios and `pair_id`, so near-duplicates and
  both members of a minimal pair always fall on the same side.

**Secondary split.** The ADR-0006 D9 family-disjoint split is reported where it is feasible.

**Statistics.** Scenarios are the inference unit: confidence intervals use a bootstrap over
scenario groups, and the paper reports "N records over K scenarios".

**Held-out render style.** The existing design keeps the `compact` style for test families
only (`rendering.TEST_ONLY_STYLES`, validator rule). Keeping it under B4 cuts training records
by one third. This ADR leaves the rule **unchanged**, and the team must decide it explicitly
(docs/33 §4).

## B5: Dry-run gate before any production manifest

**A production manifest may be frozen only after a deterministic dry run shows all of the
following at the planned size:**
- ≥ 30% of records in strict minimal pairs;
- every family ≤ 8%;
- SD3 = 0, with any within-scenario label conflict explained or excluded;
- a feasible 20% grouped split;
- the class mix reported.

**The Phase 5G dry run fails the first condition** (docs/33 §2). That is why this ADR stays
*Proposed*.

## B6: Partial-definition marker for production

- **Manifest declaration.** Production manifests declare
  `partial_definition_policy: "team-adopted (ADR-0006 D2)"`.
- **What the validator then requires:**
  - no pending-professor flag;
  - `meta.partial_definition == scaling_pilot.PARTIAL_RULE`;
  - `tier` and `sensitivity_group` consistent with OQ-21;
  - for link tools, a computed OQ-21 alternative.
- **Datasets without the key** (`pilot_v0.1`, the Phase 5E pilot) keep the original
  convention.
- **Link records** are marked by `adnn.dataset.share_link_production`
  (`share-link-gen-0.3`). The frozen pilot generator is unchanged.
- **Reproducing the Phase 5E pilot.** Its runner refuses to run once `src/adnn` differs from
  base commit `43339db`, which is intended. It must be run from that commit, for example in a
  git worktree.

## Consequences

- REQ-DATA-01 is not yet attainable with ≥ 30% strict pairs (docs/33 §2). The next decision is
  between more minimal-pair supply (new pair families: design work) and reporting
  REQ-DATA-01 as unmet (ADR-0006 D8).
- **Prerequisites before any production generator** (code, not done here):
  - the validator and API split model must support scenario-grouped splits, because today
    they enforce family-held-out splits;
  - legacy records must be rendered with prompt builder 1.1.0 so that one manifest can hold
    legacy and link records, because the loader rejects mixed builder versions.
