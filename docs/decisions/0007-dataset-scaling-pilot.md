# ADR-0007: Controlled dataset scaling pilot: frozen protocol, stop conditions, ScienceWorld stop and scaling verdict (research decision log)

- **Status:** *Adopted* by the research team (2026-11-01), including the OQ-49/OQ-50/OQ-51 decisions in P7. Full-scale generation is **not** authorised by this ADR. **No professor approval is claimed; professor contact was not required and did not happen.**
- **Date:** 2026-11-01
- **Deciders:** Sneha (M1) drafted it. M2 and M3 are to review it as consumers. M2/M3 work has not started.
- **Builds on:** ADR-0006 (D3 tiers, D5 duplicate control, D6 strict pairs, D9 splits, D10 scaling pilot, D11 OQ-47/OQ-48); docs/25 §9.
- **Evidence:** docs/26.
- **Does not change:**
  - the 210-example pilot or its checksums;
  - prompt builder 1.0.0;
  - the shared dataset API;
  - `src/adnn/sandbox`;
  - `sw-admission-2`;
  - any frozen Phase 4G/4H/5A result.
- **Does not generate** the final dataset.

## P1: Freeze before generating

- Every generation run reads a versioned, self-hashing manifest (`docs/preregistration/phase5b_manifest.json`, content hash `4b029749…`). The manifest fixes:
  - seeds;
  - label and admission rules;
  - family allocation;
  - the family-disjoint split;
  - exclusions;
  - sensitivity groups;
  - stop thresholds;
  - code hashes.
- `freeze` refuses to overwrite. `generate` refuses on a hash mismatch and writes the split before any record.
- Full-scale generation must use a new frozen manifest of the same form.

## P2: Tiers in generated sandbox data

- Records carry `tier` (G/P) and `sensitivity_group`.
- OQ-21-sensitive records are kept as tier P, sensitivity group `OQ-21`. They are excluded from gold, strict pairs and primary metrics, per ADR-0006 D11.
- The pending-partial flag is replaced by the D11 partial-definition note.

## P3: New families must be verified by design or excluded whole

- A new family declares its expected labels per pivot value.
- If any record disagrees with its declared design, the entire family is excluded. It is never patched or relabelled.

## P4: Stop conditions are executable and never relaxed

- S1–S7 (`adnn.feasibility.stop_conditions`) implement docs/25 §9 with the thresholds frozen in the manifest.
- A check whose inputs are absent is **not evaluable**, never a pass.
- Phase 5B result: S2, S4, S5, S6 and S7 were evaluated and none triggered. **S1 and S3 are recorded as NOT EVALUABLE, not as passing**: no ScienceWorld candidates exist (P5), so the ScienceWorld yield and rubric-sensitivity checks have no inputs. Nothing about ScienceWorld quality is inferred from them.
- **Proposed addition for full-scale generation:** a structure-level diversity condition. Its threshold is to be set by the team before the next manifest, not after seeing data. Reason: S5 (surface-masked effective fraction, 0.76) did not detect that 240 records realise only 37 underlying structures (docs/26 §4.5).

## P5: ScienceWorld stratum stopped, as instructed

- The existing sampler supports 7 genuinely distinct action families: move and pick_up are one relocation family, and combustion is missing.
- It has 3 task families, so the 25% task cap is unsatisfiable.
- In line with the instruction not to manufacture diversity, no ScienceWorld candidates were generated.
- Unblocking requires sampler extensions (combustion with the C-BURN path; at least 4 task families) under a new manifest. OQ-50 was deferred (P7), so the stratum remains stopped.

## P6: Scaling verdict

- **Full-scale generation is not yet justified.**
- Compute and label validity scale. For the sandbox: 0.41 s per record, 0 re-derivation failures, byte-identical replicas, three classes, 0.375 strict pairs.
- Diversity does not scale. 213 of 240 records repeat structures from the 210-example pilot, and ScienceWorld currently contributes 0 gold.
- 2,000 gold is therefore *feasible in compute, not demonstrated in diversity*.
- Prerequisites:
  - mechanistically new sandbox families (OQ-49, approved in principle; this requires extending `src/adnn/sandbox`);
  - the ScienceWorld sampler extensions (OQ-50, deferred: ScienceWorld stays at 0 gold meanwhile);
  - the structure-diversity validation (OQ-51, approved).

## P6a: Prior-scenario reuse not detected by the original stop conditions

- **213 of 240** Phase 5B records (88.75%) use an underlying state/action structure (`structure_signature`) that already occurs in the 210-example pilot. The 240 records realise only **37** distinct structures; only 9 structures (27 records) are new.
- **None of the original stop conditions S1–S7 detected this.** S5 measures a surface-masked template signature (effective fraction 0.7625, above the 0.60 threshold), which masks names and amounts but still counts structurally identical scenarios with different surface values as distinct. No condition compared against prior datasets.
- The pilot therefore "passed" its stop conditions while adding little new underlying diversity. This is recorded as a limitation of the original conditions, not as a pass on diversity.

## P7: Team decisions on OQ-49, OQ-50, OQ-51 (2026-11-01)

- **OQ-49: approved in principle.** Future sandbox extensions may add genuinely new mechanisms (new tools or state). Each new family must be brute-force-verified and is excluded whole on design mismatch (P3). No extension is made in Phase 5B; each extension will be its own reviewed change.
- **OQ-50: deferred.** No ScienceWorld sampler expansion now. The ScienceWorld stratum stays stopped (P5) and contributes 0 gold; the docs/25 projection of 400–600 ScienceWorld gold remains unsupported.
- **OQ-51: approved.** Future dataset validation must measure underlying scenario diversity: structure-level signatures, including overlap with every prior dataset. The threshold is fixed in the frozen manifest before generation, never after seeing data. Phase 5B's stop conditions are not modified retroactively.

These decisions were taken by the research team. The professor was not contacted, and no approval is implied.

## Consequences and limitations

- Docs/25's projection of 400–600 ScienceWorld gold is unsupported until P5 is resolved. Until then the sandbox carries the whole target, with the D5 caps applying.
- The verb shortcut (0.417 against a majority rate of 0.367 on the test split) must be reported next to model accuracies on the family-disjoint split.
- Only one split was evaluated. No new ScienceWorld temperature or rubric evidence exists from Phase 5B.
- The professor was not contacted, and no approval is implied.
