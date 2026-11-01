# ADR-0002: ScienceWorld provisional restoration methodology (research decision log)

- **Status:** Adopted by the research team as the *proposed* working methodology for Phase 4E. **Not approved by the professor.** The project will not ask the professor for methodological clarification. The team sets, justifies and documents its own operational definitions, and the final report must present them as the team's choices.
- **Date:** 2026-10-31
- **Deciders:** Sneha (M1) drafted it. M2 and M3 review it as consumers of ScienceWorld data. This review does not make M1's ScienceWorld work depend on M2/M3 work (RD-10).
- **Scope:** ScienceWorld provisional evidence records only (`docs/21`, `adnn.scienceworld.provisional*`). It does not change:
  - the sandbox restoration semantics;
  - the 210-example pilot;
  - the prompt builder (1.0.0);
  - the gold dataset schema (C1).
- **Relation to earlier documents:** this log records how the team resolves, for now, the questions that `docs/20` (professor decision memo) prepared for the professor (OQ-03, OQ-29, OQ-30, OQ-31, OQ-36). `docs/20` remains a record of the options. Where it says "ask the professor", read "decided by the team, as recorded here".

Every decision lists its rationale, limitations and planned sensitivity analyses. A sensitivity analysis is planned, not yet run, unless stated otherwise. The Phase 4E pilot only shows that the pipeline can carry each analysis.

---

## RD-01: Time-matched counterfactual restoration is the proposed primary comparison

**Decision.** We compare the state after the target action and a candidate restoration path (S2) with a time-matched do-nothing counterfactual: S0 followed by the same number of ticks of an idle action with no discrete effect (`look at agent`, 1 tick each). We do not compare S2 with the literal pre-action state S0.

The literal comparison is still computed and stored, as a secondary comparison.

**Rationale.**
- ScienceWorld advances physics every tick: heat transfer, plant life and the move counter. Under a literal reading, almost every action that takes time can never be undone, because time itself cannot be undone (`docs/17` §4.3, `docs/19` §4).
- The counterfactual isolates the effect of the action from the passage of time.
- Tick matching was verified in every Phase 4D attempt (0 move mismatches).

**Limitations.**
- This departs from the literal wording of spec §4.2 ("the exact previous state"). The report must state the departure explicitly.
- The counterfactual is a model of "doing nothing". A different idle action, or `wait1` (2 ticks), could in principle interact with the world differently.
- The counterfactual is unavailable when the idle action is not valid or does not take exactly one tick. The record then says `counterfactual_unavailable`.

**Sensitivity analyses (planned).**
- Report every result under both the literal and the counterfactual comparison. Both are already stored per attempt.
- Repeat the analysis with a second idle action on a subsample.

## RD-02: Temperatures are compared at exact equality, 0.01 °C and 0.1 °C. They are never silently discarded.

**Decision.** Every comparison against the counterfactual is computed three times:
- exact canonical equality;
- with temperature differences of at most 0.01 °C ignored (`temperature-tolerance-0.01C-v1`);
- with temperature differences of at most 0.1 °C ignored (`temperature-tolerance-0.1C-v1`).

Temperature fields stay in every comparison. A tolerance only excuses a difference within the stated bound, and each excused difference is counted (`n_within_tolerance`).

Every other field is compared exactly, including `world.moves` and `combustionTicks`. The discrete-only projection, which does drop temperatures, is stored only as a labelled exploratory comparison. It is never used for any restoration category.

**Rationale.**
- Phase 4D found residual temperature differences of at most 0.0039 °C after otherwise-matching restorations (pour-back, refills). These are produced by heat-transfer arithmetic, not by the action.
- The two tolerances bracket that scale by about 2.5× and 25×. Exact equality keeps the strict reading available.

**Limitations.**
- The thresholds are pragmatic. They are not derived from any physical criterion.
- Larger temperature effects (an activated stove) are deliberately not excused.
- A tolerance on one field cannot express "approximately the same object".

**Sensitivity analyses (planned).**
- Report the distribution of records over the three levels.
- Report how many records change category between levels.
- Recompute the analyses at a third tolerance (1 °C) if the results change materially between 0.01 and 0.1 °C.

## RD-03: Exact restoration, partial restoration, irreversible and undetermined are distinct concepts

**Decision.** The four concepts are kept separate in code, data and reporting:
- **Exact restoration:** a witnessed agent-valid path within the horizon whose result equals the counterfactual on all observed fields.
- **Partial restoration:** a witnessed path whose result matches only under an approved approximation (a tolerance, or structural replacement, OQ-37), or matches at a cost.
- **Irreversible:** requires *positive* evidence that no path within the horizon can restore the state. That means either a complete search, or a source-backed certificate (`docs/19` §5).
- **Undetermined:** everything else.

Phase 4E records store only neutral evidence statuses, for example `counterfactual_match_within_0.01C` or `no_candidate_path_found`. They store no concept as a verdict. The validator rejects the words `reversible`, `irreversible`, `partially_reversible`, `partial` and `undetermined` as field values.

**Rationale.**
- Merging the concepts is the main way a restricted diagnostic could turn into an unjustified label.
- Keeping evidence and verdict separate lets the mapping be changed later without regenerating evidence.

**Limitations.**
- The spec has three labels (REQ-LBL-01). "Undetermined" is not a spec class. Undetermined cases will be excluded or reported separately, which may unbalance classes (REQ-DATA-02).
- The partial-restoration concept still needs a team definition of "at a cost" for ScienceWorld (OQ-03).

**Sensitivity analyses (planned).**
- Report class counts with undetermined cases excluded.
- Separately, report counts with a mapping in which undetermined cases are assigned to their most likely class. This is a robustness check only; it is never the primary analysis.

## RD-04: An unsuccessful restricted undo search is never an irreversible label

**Decision.** Phase 4E candidate paths come from the restricted Phase 4D inverse-rule registry (at most 4 paths, of 1–2 actions each). The search is therefore incomplete. If no candidate exists, none executes, or none matches, the record says so neutrally (`no_candidate_path_found`, `no_candidate_path_executed`, `counterfactual_mismatch_at_all_tolerances`). It keeps `candidate_set.exhaustive = false` and the text of `FAILED_SEARCH_MEANING`.

Under RD-03 such a case is undetermined unless a certificate or a complete search exists.

**Rationale.**
- The spec's BFS ≤ 3 is very likely infeasible over ScienceWorld's 400–2,800 valid actions per state without snapshots (OQ-31, `docs/16`).
- Absence of evidence is not evidence of absence.

**Limitations.**
- Many targets that are in fact irreversible (mix, eat, combustion) will stay undetermined until certificates are written.
- This shifts class balance towards reversible-looking evidence.

**Sensitivity analyses (planned).**
- On a subsample, widen the candidate set (all agent-valid single actions involving the target's objects) and report how often the evidence status changes.
- Report the certificate-based subset separately once certificates exist.

## RD-05: Door-based cases are excluded from the initial gold-label candidate pool

**Decision.** The sampler never chooses as a target an action whose text contains "door", or which refers to a uuid outside the object tree (portals, for example `drain to sewer`). Door rules remain in the registry for diagnostics only. The number of excluded actions is recorded per sample.

**Rationale.**
- Door state is not in the object tree.
- Only the current room's doors appear in `look()` text (OQ-36, `docs/17` §4.4, `docs/18` §5). So states that differ only in remote door states compare equal, and door effects are invisible after the agent leaves the room.

**Limitations.**
- This removes a natural, common action class.
- Door actions may still occur indirectly. They are excluded from histories too, because history actions must be one of the classes open/close (non-door), activate/deactivate, move, pick up, pour.
- Other incompletely observed state remains: agent internals, and doors as context. It is disclosed in every record (`observation_completeness`).

**Sensitivity analyses (planned).** If a door-observation procedure is built (visiting rooms, which costs actions), report door cases as a separate, clearly marked subset.

## RD-06: ScienceWorld is pinned to upstream commit e8216d6

**Decision.**
- Source commit: `e8216d6044e8e39be9fcb185e3b2dfb602584b52` (package 1.3.0).
- JAR SHA-256: `e77b0fee…b465`.
- Source archive SHA-256: `d2c1dc1e…bfae6`.

Every recipe and record carries this pin. Replay refuses another pin (`UnpinnedRuntimeError`).

**Rationale.**
- 1.3.0 has deterministic object enumeration. Replay was verified identical across processes (`docs/17`, `docs/18`).
- PyPI 1.2.3 has a reported stochastic heat-transfer issue (OQ-29).

**Limitations.**
- The commit is unreleased upstream, and trajectories differ from 1.2.x, so results are not directly comparable with work using PyPI 1.2.3.
- We must cite the commit, not a release.

**Sensitivity analyses (planned).** None required for internal validity. If time allows, report whether the pilot recipes replay on 1.2.3.

## RD-07: The research decision log is the authoritative record of methodological choices

**Decision.** This file records every ScienceWorld methodological choice: rationale, limitations and planned sensitivity analyses. Later changes are made by a new ADR that supersedes the affected RD entries. Silent edits are not allowed.

**Rationale.** No external approval exists, so traceability has to come from documentation.

**Limitations.** Documentation does not equal validity. The report must still discuss each choice.

## RD-08: No claim of professor approval

**Decision.**
- Records carry `scientific_status.professor_approved = false`, and the validator rejects any other value.
- Documents describe these choices as research-team decisions.
- `docs/20` remains a record of options and is not described as answered by the professor.

## RD-09: Phase 4E builds provisional evidence only

**Decision.** Phase 4E produces:
- provisional evidence records;
- reproducibility checks;
- *candidate* minimal pairs.

It produces no gold labels, adds nothing to the gold dataset, and does not generate the final 2,000 examples. Candidate pairs have `status = candidate_unvalidated` and `validated = false`.

**Rationale.** Labels need RD-03's mapping, certificates (RD-04), and a team decision on partial restoration (OQ-03). None of these is complete.

**Limitations.** M2/M3 cannot use ScienceWorld data for training or evaluation yet. The sandbox pilot remains their only labelled data.

## RD-10: Member 1's ScienceWorld work stays independent of Members 2 and 3

**Decision.**
- Phase 4E code lives only in `adnn.scienceworld`. It does not import from or modify probes, behaviour, models or evaluation code.
- It does not use the shared prompt builder.
- M2/M3 deliverables do not block it.

## RD-11: Pilot sampling configuration

**Decision.**
- **Simplifications.** The pilot uses the simplification `teleportAction` only, and starts each history with `teleport to <room>`, which is an agent-valid action under that simplification. Containers and doors keep their native open/closed state.
- **Families.** Three explicit task families, all at variation 0:
  - 1-1 boil, in the kitchen;
  - 3-1 power-component, in the workshop;
  - 5-1 grow-plant, in the greenhouse.
- **History.** Histories are random walks of 0–3 actions drawn from rule-covered classes.
- **Target selection.** Targets are drawn by verb class. Rule-covered classes get weight 2; eat, mix and connect get weight 1.
- **Validity.** Every history action and every target must be valid, refer to exactly one template, be accepted, and have an observed discrete effect.
- **Seeds.** Each sample's RNG is derived from `(seed, family_id, sample_index)` via SHA-256. The base seed is 20261031.

**Rationale.**
- `openContainers` (OQ-33's proposed preset) removes open/close actions, which are the clearest restorable class.
- `teleportAction` keeps histories short without door actions (RD-05).
- Requiring an observed effect removes parsed-but-refused actions. These take a tick but change nothing (`docs/19` §4).

**Limitations.**
- **Simplification preset.** It differs from OQ-33's proposed preset, and must be fixed for the final dataset.
- **Variation coverage.** Variation 0 only.
- **Shallow histories.** Random short walks under-represent long-horizon states.
- **Biased class weights.** The weights deliberately over-sample classes that have inverse rules.
- **Refused targets.** Requiring an observed effect drops targets the simulator accepts but refuses in the current state. For example, "pour glass jar" fails while the jar is closed.

**Sensitivity analyses (planned).**
- Repeat with `openContainers` added.
- Use upstream train variations other than 0.
- Use uniform class weights.

---

## Consequences

- ScienceWorld evidence can be generated reproducibly now, and labelled later by applying an RD-03 mapping to stored evidence, without re-running the simulator.
- The final report gains a "methodological choices" section built from RD-01 to RD-11.
- **Open questions:**
  - OQ-29, OQ-30, OQ-31 and OQ-36 now have team positions (RD-06, RD-01/RD-02, RD-04, RD-05).
  - OQ-03 (partial restoration in ScienceWorld) and OQ-37 (structural replacement) remain open team decisions before any label is issued.
