# ADR-0003: ScienceWorld operational restoration definitions and exclusion rules (research decision log)

- **Status:** Adopted by the research team as the proposed operational definitions for ScienceWorld evidence (Phase 4F). These are team decisions. **No claim of professor approval is made** (RD-08). No gold labels are issued by this record.
- **Date:** 2026-10-31
- **Deciders:** Sneha (M1) drafted it. M2 and M3 review it as consumers of ScienceWorld data (RD-10).
- **Builds on:** ADR-0002 (RD-01 to RD-11). Where this record is more specific, it refines ADR-0002 and does not contradict it.
- **Does not change:**
  - the sandbox or its restoration semantics;
  - the 210-example pilot or any of its labels;
  - the dataset schema and API;
  - prompt builder 1.0.0.
  - The Phase 4E provisional records keep their recorded evidence statuses; nothing is relabelled.
- **Evidence base:** `docs/22` (Phase 4F measurements). Every decision cites the measurement behind it.

---

## D1: Four restoration outcomes

All outcomes compare S2 with the time-matched counterfactual (D2).

S2 is the state after the target action plus a candidate restoration path.

| Outcome | Definition | Current evidence status(es) |
|---|---|---|
| **Exact** | Canonical equality on every observed field, including exact temperatures | `counterfactual_match_exact` |
| **Approximate** | Equal on every observed field except temperatures, and every temperature within the declared tolerance (0.01 °C or 0.1 °C; see D4) | `counterfactual_match_within_0.01C`, `counterfactual_match_within_0.1C` |
| **Partial** | The fields and objects the target changed are restored, but other discrete differences remain (e.g. sink water left in a returned container) | *Not yet computed automatically.* It is currently reported inside `counterfactual_mismatch_at_all_tolerances` |
| **Unknown** | No comparable evidence:<br>• no candidate path;<br>• no path executed;<br>• counterfactual unavailable;<br>• an exclusion rule applies (D7). | `no_candidate_path_found`, `no_candidate_path_executed`, `counterfactual_unavailable` |

A mismatch at all tolerances is **not** an irreversible outcome. It is evidence only about the paths that were tried (RD-04; `docs/22` §5 shows the expanded search changes some outcomes).

**Rationale.** RD-03 kept these concepts apart in vocabulary. This decision fixes their operational tests so that records from different phases are comparable.

**Limitation.** "Partial" needs a declared notion of "the fields the target changed". Until it is implemented and tested, partial cases remain inside the mismatch status, and the report must say so.

## D2: Time-matched counterfactual (precise definition)

Given a replayable S0 (recipe R), a target action T taking *t* ticks, and a candidate path P taking *p* ticks, the counterfactual is:

1. replay R in a fresh episode;
2. apply `look at agent` exactly *t + p* times;
3. require each application to be accepted, to take exactly one tick, and to change no discrete field (the Phase 4D requirement);
4. capture the state with the canonical observation protocol (D8).

If any step fails, the outcome is *unknown* (`counterfactual_unavailable`).

The counterfactual is computed per total tick count and reused across paths with the same count (`expanded_search.py`).

The literal comparison with S0 is still stored as a secondary comparison (RD-01).

## D3: Recreated objects

**Primary comparison.** It is identity-based: an object recreated with a new uuid is a different object.

- Refilling a cup with fresh sink water therefore does not restore the original water.
- Draining removes it, and the sink then creates new water objects.

**Structural matching.** This matches objects by name, type, container path and properties, ignoring uuids (`docs/19` §5). It is computed as an **exploratory secondary analysis only**.

**No label may depend on structural matching** until the team has run its own sensitivity analysis. That analysis is planned and not yet run.

**Rationale.**
- Identity-based comparison is what the canonical state measures directly.
- Structural matching needs a declared object-correspondence rule, and its choice changes outcomes. Example: is "a water in the cup" the same as "the water in the cup"?

**Limitation.** Under identity-based comparison, every deletion is permanent (`docs/19` §6). Identity-based comparison therefore cannot distinguish eating an apple from emptying a cup. This is why D5 does not let identity-based permanence alone support an "irreversible" label.

## D4: Temperature sensitivity at 0, 0.01 and 0.1 °C

Every comparison is reported at all three thresholds (RD-02).

**Decision.** A restoration result supports a label only if it is **stable across 0.01 °C and 0.1 °C**: the outcome must be the same at both. Otherwise the case is *temperature-sensitive*, and is excluded from gold-label generation until the team adopts a single threshold with a physical justification.

Exact (0 °C) results are always reported. They are not used alone, because almost every action that takes time leaves sub-0.01 °C heat-transfer residuals.

**Evidence (`docs/22` §3–4).**
- Pick-up/return residuals are 0.0138–0.0144 °C (Phase 4E). These match at 0.1 °C but not at 0.01 °C, so the 0.01 °C and 0.1 °C results differ.
- In the targeted contrasts, several source/device pairs are restoration-contrast candidates only under the tolerance methods. Under exact comparison, both variants fail.
- So the threshold changes which pairs count as contrasts. This is a measured effect, not a hypothetical one.

## D5: When restoration evidence can support a label

- **Reversible (under the declared definition).** Supported by a found and executed path whose outcome is *exact* or *approximate*, and stable under D4. A found path is sufficient evidence because it is a constructive witness.
- **Irreversible.** **Never** supported by restoration search, however large (RD-04). It is supported only if all three of these hold:
  1. a source-backed certificate (D6) applies;
  2. its precondition checker returns `precondition_met` for the specific (S0, T, S1, counterfactual);
  3. the certificate's holds-under list includes the declared restoration definition.
- **Otherwise: unknown.** Unknown cases are excluded from gold-label generation, not guessed.

This record issues no labels. It defines what evidence a future gold-label phase would need.

## D6: Limitations of source-backed certificates

The certificates are C-MIX-SALT, C-BURN and C-EAT (`adnn.scienceworld.certificates`, `docs/22` §6).

1. **Manual audit only.** Each is a manual audit of the pinned source text at commit e8216d6: exhaustive text searches for write sites and constructors. Each is **not** a formal or machine-checked proof.
2. **Assumes no hidden mutation.** It assumes nothing mutates state outside the searched Scala code (reflection, Python-side calls, other JVM entry points). It must be re-audited if the pin changes (RD-06).
3. **Scope is the agent action set.** The certificate covers the agent action set (`actions/*.scala` plus processes run by `tick`). Researcher operations (`load`, `reset`) are outside the agent action set and outside its scope.
4. **Preconditions are per-state.**
   - C-MIX-SALT fails if any other sodium-chloride object exists anywhere in the tree.
   - C-BURN does not apply if the counterfactual also ignites the object.
   - The checker reads the canonical state, which is explicitly incomplete. Tree completeness is therefore an assumption, recorded as a caveat in every check.
5. **C-EAT's structural part is a hypothesis.** Its identity part is equally true of any deletion, so on its own it does not support an irreversible label (D3, D5).
6. **No combustion experiment has been run.** C-BURN is supported by source only (`docs/22` §6).

## D7: Exclusion rules

A case is excluded from the gold-label candidate pool, with the reason recorded, if any of the following holds:

1. **Hidden door state** (RD-05, refined). The action names a door, or refers to a uuid outside the object tree. Door states are only partly observable (`visible_doors` covers the current room only).
2. **Uncontrolled stochastic process.**
   - In any compared state (S0, S1 or the counterfactual), an RNG-driven agent (`bee N`) is outside a closed container.
   - Or the target, history or path opens the bee hive.
   - **Evidence:** valid-action enumeration consumes global randomness and changes bee transitions (`docs/22` §2). Different branches issue different query and action sequences, so their bee trajectories are not comparable.
   - Bees inside the closed hive also draw randomness every tick (`Bee.scala:174-190`). No observable effect was measured while the hive stayed closed (`docs/22` §2), so closed-hive states are **not** excluded.
3. **Plant reproduction.** Pollination, seeds or fruiting within the horizon. Plant genetics draw randomness (`Chromosomes.scala:201,268`). This exclusion is untested so far and is applied conservatively.
4. **Ambiguous referents.** Ambiguous referents in the target or path: more than one template with the same text (RD-11). For such states, the valid-action text itself depends on prior enumeration (`docs/22` §2.3).
5. **Temperature-sensitive cases** (D4) and **unknown outcomes** (D5).

## D8: Canonical observation protocol

Every branch (sampling, verification replay, counterfactual, restoration path, expanded search) uses the same schedule:

1. `load`;
2. recipe actions with **no** interleaved queries;
3. `capture_state` (object tree, look, inventory, moves, valid actions);
4. `valid_action_templates`;
5. then the next action.

A branch never issues extra enumeration calls between actions.

**Rationale.** The measurements in `docs/22` §2 show:
- look, inventory and object-tree queries had no measured effect on transitions;
- enumeration changed transitions whenever an RNG consumer was active, and changed valid-action text in ambiguous-referent states.

A fixed schedule makes those effects identical across repeats and processes.

**Limitations.**
- The protocol makes measurement **consistent**, not **neutral**: the simulator is not measurement-independent.
- Branches that differ in length still differ in their number of enumeration calls. This is why D7.2 excludes stochastic cases instead of trying to correct for them.
- The protocol does not reveal state the canonical state does not observe (e.g. RNG state, closed-room doors).

## D9: Existing labels are not changed

No existing label is changed by this record. The 210-example sandbox pilot and its labels are untouched.

The Phase 4E ScienceWorld records carry evidence statuses only; they were never labels. Their bee-related candidate pairs are not meaningful evidence under D7.2, and remain documented as such (`docs/21` §7.6).

---

## Consequences

- **Gold-label generation for ScienceWorld is not yet possible.** D1 "partial" is not computed. D3's structural sensitivity analysis has not been run. D5's irreversible route has only three certificate candidates, none verified empirically end to end.
- **Contrast generation needs a stability filter.** It should keep only deterministic, bee-free, unambiguous states and report D4 stability per pair (`docs/22` §4).
- **Revisiting.** Any change to the pin, the idle action, the canonical projection or the query protocol requires re-running `scripts/scienceworld/query_order_audit.py` and updating this record.
