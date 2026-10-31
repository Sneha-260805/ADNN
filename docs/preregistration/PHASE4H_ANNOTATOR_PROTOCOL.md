# Phase 4H blinded declaration protocol (for a future human annotator)

Status: protocol only. **No human annotator has used it yet.** Every agreement number in
docs/24 compares the team's own declarations (M1) with a rule-based generator. That
comparison is a technical consistency check. It is not inter-annotator agreement and not
human validation.

Rubric version: `sw-declaration-rubric-1`. Packet version: `sw-declaration-packet-1`.
The hashes of the packets, the rubric document and the generator's declarations are in
`phase4h_manifest.json`.

## 1. What you receive

You receive one packet per case, `packets/P01.json` to `packets/P12.json`, with a readable
`.md` copy of each. A packet contains only:

- the task description, as the simulator prints it;
- the actions already taken to reach the initial state;
- the target action;
- the objects the target action names, each with its container;
- the contents of the current room at the initial state, to depth 3.

A packet never contains the team's declaration, the case name, any expected outcome, a
certificate or a restoration result. The packet ids are ordered by a hash of the case id,
so they carry no information either.

## 2. What you must not do

- Do not open `phase4h_preregistrations.json`, `phase4h_rubric_declarations.json`, the
  `results/` directory, docs/23, docs/24 or any packet's case mapping before you finish.
- Do not run the simulator.
- Do not talk to anyone else who is annotating until all packets are submitted.
- Do not revise a submitted packet.

## 3. Procedure (do it the same way for every packet)

1. Read the task description, then the target action.
2. Identify the **designed effect** of the target verb (rule R1 below). Declare it with
   weight 1.
3. Ask whether the action places an object into a heating or cooling container or
   device, opens or activates one, or activates a water source. If it does, declare the
   practical consequences listed in R2 with weight 1.
4. List the side effects you want recorded (R3) with weight 0. If you list none, write
   "none" in `notes`.
5. For every property, write a role that names **exactly one** object in the packet
   (rule R4). Use the `role` strings shown in the packet. If an object has no role
   (`null`), it is ambiguous and cannot be declared. Say so in `notes`.
6. Fill in `form.properties` as a list of
   `{"role": ..., "field": ..., "weight": 0 or 1, "rule": "R1".."R3", "reason": "..."}`.
   For each ambiguity A1 to A6 that you met, write its id and your choice in `notes`.
7. Record the time you spent. Submit the JSON with its packet id unchanged.

The allowed fields are `location`, `contents`, `present`, `propContainer.isOpen`,
`propDevice.isActivated`, `propMaterial.temperatureC`, `propMaterial.stateOfMatter`,
`propMaterial.hasCombusted`, `propMaterial.isCombusting` and
`propElectricalConnection.connectedTo`.

## 4. Rubric

- **R1, designed effect (weight 1).** The property the verb is defined to change:
  - open or close: `isOpen`;
  - activate or deactivate: `isActivated`;
  - move or pick up: the `location` of the moved object;
  - pour: the `contents` of the poured container and `present` for each poured
    substance;
  - mix: `present` for each substance in the mixed container;
  - use lighter on X: X `hasCombusted`, `isCombusting` and `present`;
  - eat X: X `present`;
  - connect A to B: `connectedTo` of both terminals;
  - teleport: the agent's `location`.
- **R2, practical consequence (weight 1).** The temperature, and for liquids the state of
  matter, of objects placed into or exposed by opening or activating a heating or
  cooling container or device. Also the contents of containers inside an activated
  water source.
- **R3, recorded only (weight 0).** Containers whose contents change as a side effect:
  the destination of a pour, the container of an eaten object and a mixed container's
  contents.
- **R4, identity.** Every property refers to the object as it is at the initial state.
  Objects created by the action cannot be declared.
- **R5.** Never consult restoration results, recovery paths or another declaration.

## 5. Known ambiguities: record your choice, do not resolve silently

| Id | Question |
|---|---|
| A1 | Small temperature changes from a thermal device: practical consequence or not? |
| A2 | Combustion: is the eventual deletion (`present`) designed (R1) or recorded (R3)? |
| A3 | Pour or mix: is the designed effect the container's `contents` or the substances' `present`? |
| A4 | Is the location of objects inside a container that is opened relevant? |
| A5 | Electrical connections: both terminals or only the first? |
| A6 | Which recorded side effects to list at all? |

## 6. How agreement will be computed (fixed in advance)

- Each property is mapped to its S0 (uuid, field) pair by the same binder that admission
  uses.
- For each packet and each pair of declarers, three numbers are reported:
  - the Jaccard index over all pairs;
  - the Jaccard index over the weight-1 pairs;
  - the share of shared pairs on whose weight flag the declarers agree.
- Metrics are reported per packet and per ambiguity, never as a single pooled score.
- With fewer than two human annotators, no inter-annotator statistic is reported.
- A chance-corrected coefficient is not defined here, because the space of possible
  properties is open. Any such statistic must be pre-registered separately before the
  annotations are collected.
