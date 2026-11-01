# ADR-0006: Final dataset design: composition, label tiers, minimal pairs, splits, scaling pilot and fallbacks (research decision log)

- **Status:** *Adopted* by the research team (Phase 5A), including the OQ-47 and OQ-48 decisions in D11. These are team decisions with explicit limitations. **No professor approval is claimed and the professor was not contacted** (RD-08).
- **Date:** 2026-10-31
- **Deciders:** Sneha (M1) drafted it. M2 and M3 are to review it as consumers (RD-10). M2/M3 work has not started.
- **Builds on:**
  - ADR-0002 to ADR-0005, in particular ADR-0005 R9 (OQ-46 accepted, OQ-44 deferred);
  - docs/05 (dataset specification);
  - docs/25 (evidence).
- **Does not change:**
  - the 210-example pilot (its records and flags);
  - prompt builder 1.0.0;
  - the shared dataset API;
  - `sw-admission-2`;
  - any frozen Phase 4G/4H result.
- **Does not generate** the final dataset.

## D1: Testbed roles

- **The sandbox supplies all three classes**, including every irreversible example.
- **ScienceWorld supplies reversible and partially reversible examples only.**
- Three-class balance is a property of the combined dataset and of the sandbox. It is not forced in ScienceWorld (ADR-0005 R9).

## D2: Sandbox partial definition adopted as a team rule

- The documented sandbox definition is adopted by the team for the final dataset: core-projection equality with refund fees added back (docs/10 §5.1, ENG-15).
- Final-dataset records carry `partial_definition: "team-adopted (ADR-0006 D2)"` instead of a pending-professor flag.
- The pilot keeps its original flags.
- OQ-21 remains: the documented state-only information rule is the default. Records whose label changes under the alternative reading remain tier P (D3).

## D3: Label tiers

| Tier | Requirement | Counted toward 2,000? |
|---|---|---|
| G | Sandbox: verified witness or complete bounded impossibility over D at h = 3, not OQ-21-sensitive. ScienceWorld: eligible reversible, or eligible partial with a certificate-protected residual, plus two-process replication, symmetric-protocol stability (D7) and rubric stability (ADR-0005 R7). | Yes |
| S | ScienceWorld eligible partial with a residual not protected by any certificate (search-relative) | No, unless a later ADR decides otherwise; reported separately |
| P | Changes under a documented alternative rule (OQ-21) or a pending definition | No; kept and flagged |
| X | Unresolved, excluded, quarantined, non-replicating or measurement-affected | No; counts reported |

A search failure is never irreversibility, in either testbed.

## D4: Composition targets (research targets, not quotas that override D3)

- **Sandbox:** 1,400–1,600, from at least 28 families (14 existing plus at least 14 new, each verified by brute force before inclusion), roughly ⅓ per class.
- **ScienceWorld:** 400–600 tier G, as measured yield allows, plus tier S separately.
- **Combined:** at least 2,000 tier G.
- If any target is missed, D8 applies. Labels are never created or re-declared to fill a quota.

## D5: Independence and duplicate control

- The unit of diversity is the surface-masked template signature (`adnn.feasibility.composition.template_signature`).
- Per family: at most 8% of a testbed's examples.
- Per signature: at most 3 examples.
- The effective fraction (signatures over records) is reported per testbed and must be at least 0.6.

## D6: Strict minimal pairs

- A genuine pair has the same `scenario_id`, a byte-identical `action_text`, and at least two distinct labels, all of them tier G.
- Different immediate effects alone do not qualify.
- The ≥30% target is evaluated on this strict definition. The spec's looser definition is reported alongside it.

## D7: Measurement-symmetry quarantine

- ScienceWorld evidence uses the frozen asymmetric protocol (ADR-0003 D8).
- Every candidate must also pass the symmetric-counterfactual check (`measurement_symmetry`): identical counterfactual states, attempt levels and outcome.
- Any difference quarantines the case (tier X).
- The Phase 5A result over the 27 constructed cases is in docs/25 §4.

## D8: Fallbacks

These are applied explicitly, with the revised target named (docs/25 §10):
- the OQ-10 testbed minimum is relaxed before REQ-DATA-01 is touched;
- REQ-DATA-01 is reported as unmet rather than met with tier S or P labels;
- REQ-ABL-04 is narrowed to reversible versus certificate-supported partial for any transfer involving ScienceWorld (D11);
- REQ-LBL-05 is reported as unmet if no human annotators exist.

## D9: Splits

- Scenario-level splits with three frozen seeds are kept (REQ-DATA-03, REQ-STAT-01).
- Family-disjoint (template-held-out) splits are added and proposed as the primary basis for generalisation claims.
- ScienceWorld splits are by task family.
- Leakage checks run on every split: group-disjointness, exact and normalised overlap, and the verb shortcut (`composition.split_leakage`).

## D10: Scaling pilot before generation

- The scaling pilot in docs/25 §9 runs first: 240 sandbox examples and 160+40 ScienceWorld candidates.
- Its stop conditions halt scaling for review. They never relax rules.

## D11: Team decisions on OQ-47 and OQ-48 (2026-10-31)

### OQ-47 adopted: sandbox partial restoration as a declared team rule

- **Rule.** A sandbox example is `partially_reversible` at h = 3 only if both conditions hold:
  1. a **verified approximate restoration** exists: a replayed sequence of at most 3 actions in D that restores the core projection (refund fees added back; ENG-15);
  2. **exact restoration fails exhaustively** within the same declared domain D and horizon 3. The search must have status complete, with no budget exhaustion.
- **Scope.** The rule is relative to h = 3 and to D:
  - the label claims nothing about restoration beyond 3 steps or outside D;
  - no sandbox label (partial or irreversible) is a claim of universal irreversibility.
- **Assumptions.**
  - The sandbox transition rules (`tools.step`) are correct.
  - D is as documented, including the OQ-24 limitations.
  - OQ-23: failed calls cost time.
  - The core projection is the declared notion of "approximately".
- **Sensitivity requirements for every generated sandbox dataset:**
  - report the OQ-24 widened-domain label changes (`pilot_audit.oq24_widened`);
  - report the OQ-21 alternative labels;
  - report per-horizon labels (h = 1, 2, 3).
- **OQ-21-sensitive records.** These are records whose label changes under the alternative information rule (17 in the pilot).
  - They are **kept separately as a sensitivity group**, tier P.
  - They are never silently converted to gold.
  - They are excluded from strict minimal pairs and primary metrics.
  - They are reported in sensitivity analyses.
- The pilot's records and flags are unchanged. The rule applies to datasets generated after this ADR.

### OQ-48 adopted: transfer claims limited to reversible versus certificate-supported partial

- ScienceWorld has no admitted irreversible class.
- Cross-environment transfer claims involving ScienceWorld are therefore limited to **reversible versus certificate-supported partial** (tier G partials whose residual is protected by an admitted certificate; currently only C-BURN `hasCombusted`).
- Search-relative ScienceWorld partials (tier S) may appear only in clearly separated secondary analyses, never in a transfer claim.
- No three-class transfer claim to or from ScienceWorld is made.
- Consequence: the ScienceWorld partial class for transfer is currently tiny (2 candidates in 27 constructed cases). Transfer experiments may be underpowered, and this must be reported.

These decisions were taken by the research team. The professor was not contacted, and no approval is implied.

## Consequences and limitations

- ScienceWorld's share of the dataset will probably be well below half.
- ScienceWorld contributes no irreversible examples, and almost no strict minimal pairs.
- Three-class cross-environment transfer cannot be evaluated toward ScienceWorld.
- The number of sandbox families must double, which is design work for Phase 5B.
- Human reliability remains unmeasured until annotators exist.
