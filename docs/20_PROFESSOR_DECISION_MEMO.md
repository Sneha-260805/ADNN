# 20 — Professor Decision Memo: Restoration and Labels in ScienceWorld

From: **Sneha (M1)**, for the ADNN team. Date: 2026-10-31. Evidence: `19_SCIENCEWORLD_RESTORATION_DIAGNOSTICS.md` (experiments E01–E11 on ScienceWorld pinned to commit `e8216d6`), `17` (reproducibility), `16` (feasibility).

**Purpose.** The project specification defines labels by whether the previous state can be restored within *h* further actions (reversible), restored approximately or at a cost (partially reversible), or neither (irreversible). In ScienceWorld these definitions cannot be applied without four decisions that are yours to make. Nothing has been labelled. Our recommendations are below; each section ends with the exact question we need answered.

## Decisions requested at a glance

| # | Question | Our recommendation | Blocks |
|---|---|---|---|
| Q1 (OQ-30) | What counts as restoration when the world changes every tick? | **B: time-matched counterfactual**, with a small declared tolerance for temperatures and a sensitivity report at tolerance 0 | All ScienceWorld labels |
| Q2 (OQ-31) | What evidence may establish `irreversible` when complete search is infeasible? | **Witness → reversible/partial; approved source-backed certificate → irreversible; anything else → undetermined (excluded and counted)** | `irreversible` in ScienceWorld |
| Q3 (OQ-03) | What is "partially reversible" operationally? | **Four tiers: exact / approximate (declared properties + unique structural replacement) / compensation-only (does not count) / unknown** | `partially_reversible` in ScienceWorld |
| Q4 (OQ-36) | How to handle door states that are only partly observable? | **A: exclude door actions from gold-labelled examples** (option B is viable later, see §4) | Door examples |

Two related team questions are affected (§5): OQ-29 (simulator version) and OQ-35 (time semantics).

## Background in four facts

1. **The world never stands still.** Every timed action advances the whole simulation one tick. In the kitchen of task 1-1, about 81 temperatures change per tick. Living things consume water, and sinks and fountains create water, without any agent action.
2. **Ticks are exact and countable.** The move counter equals the number of world ticks (checked in the source). Most actions are one tick, `wait` is 11 ticks, `look around` is zero. An action the simulator refuses still costs a tick.
3. **The observed state is incomplete.** The object tree (≈350 objects, ≈6,400 fields in the kitchen) does not contain doors. A door's state is visible only in the text of the room the agent is in, and some agent-internal variables are never exposed.
4. **Complete search is infeasible.** About 2,700–2,950 valid actions in the kitchen, and no snapshot facility, so each candidate needs a replay (≈1.5 s). Depth 1 ≈ 70 min per (state, action) pair; depth 2 ≈ months; depth 3 is out of reach.

## Q1 (OQ-30): What counts as restoration in a world that changes with time?

Write S0 for the state before the target action, and S2 for the state after the target plus *k* restoring actions.

| Option | Restored means | Concrete result (`19` §4) |
|---|---|---|
| **A. Literal** | S2 equals S0 | `open cupboard` → `close cupboard`: **differs** (81 temperatures + move counter). The same happens for every timed path: **nothing in ScienceWorld is ever restored** |
| **B. Time-matched counterfactual** | S2 equals C, where C is S0 after the same number of ticks with no action (we use `look at agent`, one tick, no effect) | Cupboard, stove, apple moved/picked up and returned, door: **0 differences in all ≈6,400 fields**. Pour salt out and back: **19 temperatures differ, max 0.0015 °C** (moving matter changed heat exchange). Sink on/off: **differs** (sink created new water in the sewer) |
| **C. Task-relevant properties** | Selected properties of S2 equal S0 (or C), continuous ones within a tolerance | With "all discrete fields exact, temperature ±2 °C": cupboard, stove, apple, salt pour-back all **match**; sink and mixing **differ** |

**Trade-offs:**

- **A** follows the specification's wording literally, but it labels time, not actions. Every timed action becomes irreversible, which is an artefact that would dominate the ScienceWorld data and make probe results uninterpretable.
- **B** isolates the action's own effect and is principled: "would the world look as if I had done nothing?". It generalises the do-nothing baseline already discussed for the sandbox (OQ-22). Our runs show it removes drift *exactly*.
  - Cost: one extra replay per check (measured 5–10 s per experiment in total).
  - Strictness: real but tiny thermal traces (≤ 0.004 °C in our runs) make it very strict. Pouring something out and back would not be "exact".
- **C** is intuitive and cheap, but the choice of properties and tolerances is a modelling decision that becomes part of the dataset definition. Too loose a tolerance could hide genuine thermal irreversibility (e.g. cooling something in the freezer).

**Recommendation:**

- **"Exact" = B** on all observed fields, with temperatures compared within a declared tolerance δ. We propose δ = 0.01 °C: about 2.5× the largest residue we measured (0.0039 °C), and far below one tick of drift (up to ≈0.45 °C per tick in the kitchen).
- Every ScienceWorld label is also reported at δ = 0, so the effect of δ is visible.
- Option C is used only for "approximate" (Q3).
- In addition, `wait`/`wait1` are excluded from judged actions and from restoration paths. Otherwise one "action" can hide 11 ticks of autonomous change inside a horizon of 3.

**Decision needed:**

1. A, B or C as the definition of exact restoration?
2. If B: accept a tolerance δ for temperatures (our proposal 0.01 °C, with a δ = 0 sensitivity report), or require strict equality?
3. Confirm that horizons count agent actions, with `wait`/`wait1` excluded.

**Consequences for the dataset:**

- **A** yields almost only `irreversible` ScienceWorld labels, which we recommend against.
- **B** roughly doubles labelling cost and needs the idle-action counterfactual recorded per example.
- **C** adds a property list and tolerances to the dataset specification (`05`), and these must be fixed before any labelling.

## Q2 (OQ-31): How can we justify `irreversible` when exhaustive search is infeasible?

| Method | What it is | Can establish… |
|---|---|---|
| **A. Complete bounded search** | Try every valid action sequence up to depth *h* | Any label. **Infeasible** here beyond depth 1, and expensive even at depth 1 (fact 4) |
| **B. Source-backed impossibility certificate** | An invariant read from the pinned simulator source shows that no action sequence can restore a property, plus a per-state check of its preconditions | `irreversible`, **only** for the certified class and **only** under the restoration definitions it was proven for |
| **C. Restricted candidate search** | Try a small, documented set of hypothesised inverses (our registry: close↔open, deactivate↔activate, move back, pour back) | **Found and verified** → `reversible`/`partially_reversible` (a witness is sound). **Not found** → **undetermined**, never `irreversible` |

**Certificate candidates found so far** (`19` §6):

- **Mixing water + sodium chloride → salt water.** No code path running during an episode can ever create sodium chloride again; it is created only when the world is built. If no other sodium chloride exists anywhere in the world, it can never reappear.
  - Status: a manual source audit, not a formal proof.
  - Caveat: the deleted *water* can be replaced (sinks create water), so deletion alone proves nothing.
- **Combustion.** The flag `hasCombusted` is only ever set to true, and the burn counter only ever decreases (exhaustive search of the source). An object that has caught fire can never be restored to its unburned state.
  - Status: invariant holds by source inspection; not run in an experiment yet.
  - Caveat: under a structural definition, an unburned look-alike could exist or grow (wood, fruit).
- **Eating.** The eaten object is detached and can never be referred to again. But fruit can regrow from trees over many ticks, so this is **not** a general certificate.

**Which methods can legitimately establish a label:**

- **Reversible or partially reversible:** any executed, re-verified witness path under the approved definition. Restricted search (C) suffices.
- **Irreversible:** only complete search (A, infeasible) or an approved certificate (B).
- **A failed restricted search (C) can never establish `irreversible`.** Such cases are reported as undetermined, excluded from the labelled data and counted in the data card.

**Recommendation.** Adopt this policy. Approve certificate classes one at a time, each with a source citation, a precondition checker and a test.

**Decision needed:**

1. Do you accept certificates as sufficient evidence for `irreversible`?
2. Do you accept that undetermined cases are excluded (and reported) rather than labelled?
3. Which certificate classes (mixing, combustion, others) should we develop?

**Consequences for the dataset:**

- ScienceWorld `irreversible` examples will come only from certified classes: mixing, burning, possibly consumption. That limits variety and risks a verb shortcut ("mix" ⇒ irreversible). To counter it we would build minimal pairs in which the same action string is reversible in one state and certified-irreversible in another (e.g. `mix` when a second salt jar exists).
- ScienceWorld may not reach the proposed 800-example share (OQ-10), so the sandbox may need to carry more of the 2,000.

## Q3 (OQ-03): What is "partially reversible"?

The specification says "approximately or at a cost". Our experiments show three different situations that all look "partial", so we propose an operational definition with four tiers. Each tier is judged against the Q1 reference state R (C under option B) within horizon *h*.

| Tier | Operational definition | Example (`19` §4–5) | Label effect |
|---|---|---|---|
| **1. Exact restoration** | Some path of ≤ *h* agent actions gives S2 equal to R on **all observed fields**, with every object matched by its simulator identity (within δ for temperatures, Q1) | `open cupboard` → `close cupboard` | `reversible` |
| **2. Approximate restoration of declared properties** | Not tier 1, but some path gives S2 equal to R on a **declared property set** P (all discrete properties of the objects involved), continuous properties within a declared tolerance τ, and every object involved either kept by identity or replaced by a **unique** structurally identical object in the same container. Residual differences are recorded | Pour salt out and back with a 0.0015 °C thermal trace (tier 2 if δ = 0); refilling a cup when the original water is gone and the replacement is unique | `partially_reversible` |
| **3. Compensation only** | A path achieves something useful but leaves declared objects deleted or elsewhere, or creates objects that remain (e.g. salt water stays, extra water in the sewer) | Mix salt + water, then refill water: the water is replaced, the salt never returns. Sink on/off: the toggle is restored but the created water remains | Does **not** count as restoration: handled as in Q2 (certificate → irreversible, else undetermined) |
| **4. Unknown** | Insufficient observability, no candidate path, a structural match is ambiguous, or the counterfactual is unavailable | Door actions; `eat banana` with no candidate | Undetermined, excluded and counted |

**Why we recommend these boundaries:**

- Tier 2 makes "approximately" precise without letting compensation masquerade as restoration.
- Requiring a *unique* structural replacement prevents silently identifying different objects. In our runs, ignoring containers made the waters ambiguous, and the prototype refused to match them.
- "At a cost" in the sandbox (fees) has no direct ScienceWorld analogue. Treating resource loss as tier 3 keeps the two testbeds consistent: a cost leaves a residue.

**Decision needed:**

1. Do you accept the four tiers?
2. Does a unique structural replacement (new simulator identity, same properties, same container) count as *approximate* restoration?
3. Should compensation-only outcomes stay out of `partially_reversible`?

If you prefer not to define partial reversibility for ScienceWorld at all, our fallback (the existing OQ-03 default) is: **ScienceWorld binary-only; partial labels come from the sandbox**, stated as a limitation.

**Consequences for the dataset:** Tier 2 requires the property set P and tolerance τ to be fixed in the dataset specification before labelling. Our open sub-question: when the original object still exists somewhere unreachable (e.g. water drained into the sewer) and an identical replacement sits in its place, our prototype currently reports *relocated + extra*, not restoration.

## Q4 (OQ-36): How should we handle door states that are not fully observable?

Facts:

- Doors are not in the object tree.
- A door action refers to an object id that never appears in the tree.
- The door's state appears only in the text description of the agent's current room.
- In experiment E05, opening and closing a door left **no** difference against the counterfactual in anything we can observe.
- By source, open/close changes only the targeted door's own open flag.

| Option | Description | Assessment |
|---|---|---|
| **A. Exclude** | No door action as a judged action in gold-labelled examples; doors may still appear as background state | Sound and simple. Loses a natural reversible category (other toggles, such as cupboards and devices, remain) |
| **B. Restrict to the current room** | Allow door actions when target and restoration happen in the same room, relying on the source fact that open/close changes only that door and the door is visible from that room | Defensible with a source citation, and E05 supports it. But it depends on a manual audit, and claims must say "observed from the current room" |
| **C. Instrumentation** | Expose door states through modified simulator code, kept separate from what the agent sees | Requires changing the simulator or the interface JAR, which breaks the pinned-build provenance (OQ-29). It also yields researcher-only information that the agent never sees. Not recommended |

**Recommendation.** **A** for the first labelled release. **B** later, if ScienceWorld needs more reversible variety, with the audit cited in the data card. C is not recommended.

**Decision needed.** A, B or C? And if B: is a manual source audit acceptable evidence that door actions have no effect outside the observed room?

**Consequences for the dataset.** Under A, door actions are filtered out when examples are sampled (the counts are reported). With the `teleportAction` simplification, moving between rooms never requires opening a door, so restoration paths do not depend on door actions.

## 5. Interactions with OQ-29 and OQ-35

- **OQ-29 (simulator version).**
  - Every measurement, invariant and certificate above is specific to commit `e8216d6`, verified by the simulator JAR's checksum.
  - Option B (counterfactual) *requires* deterministic replays. The previous release 1.2.3 showed hidden non-determinism across processes (`17` §4.2), which would make B unusable.
  - Changing version later invalidates the certificates (they must be re-audited) and all labels.
  - So Q1-B and Q2-B both depend on confirming the pin.
- **OQ-35 (time semantics across testbeds).**
  - New finding: in ScienceWorld, an action the simulator *understands but refuses* still costs a tick. Only input it cannot parse is free.
  - The sandbox advances its clock on failed tool calls (OQ-23), so the two testbeds are closer than we thought.
  - Proposal: count horizons in agent actions in both testbeds, excluding unparsable input, and measure counterfactual time in ticks.
  - This is a team decision we will record. We mention it because it affects how "within *h* actions" reads across testbeds.

## 6. What happens after your answers

Phase 4E (labelling infrastructure) can start before the answers, but it will not emit gold labels until Q1–Q3 are decided (Q4 only affects door examples). With answers in hand, we will:

1. encode the approved definitions as versioned comparison rules (replacing the exploratory projections);
2. implement the approved certificate checkers with tests;
3. sample states and actions;
4. run the restricted witness search;
5. report undetermined counts;
6. record everything in the data card.

The experiments, code and full reports are reproducible from the repository (`19` §8).
