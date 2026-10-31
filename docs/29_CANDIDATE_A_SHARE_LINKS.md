# 29: Candidate A, sharing-link restoration: implementation and diagnostics (Phase 5D, Task 2)

- **Status:** diagnostic validation report, committed with the implementation (Phase 5D, Task 4). This is **diagnostic evidence, not dataset-scale evidence** (§8).
  - No dataset records were generated.
  - No historical data or frozen manifest was changed.
  - Candidates B and C were not implemented.
  - No professor approval is claimed.
- **Base:** `4167dcff92ac1d3c7ac1a1793b429f96ecee5062`. Design in docs/28 §3.
- **Frozen specification:** `docs/preregistration/phase5d_share_link_spec.md` (`share-links-spec-1.0`).
  - sha256 `5da475c50cf6f472014e3d2e4a5d53d9120f765915751126f4a3c9d09858e137`;
  - frozen 2026-10-31T19:47:42Z, before any mechanism code was written or any link label observed;
  - recorded in `phase5d_share_link_spec.sha256`;
  - verified by the diagnostic script before every run.
- **Code:**
  - `src/adnn/sandbox/{state,tools,restoration}.py` (extension);
  - `src/adnn/feasibility/share_link_diagnostics.py`;
  - `scripts/dataset/phase5d_share_links.py`;
  - `tests/test_share_links.py`.
- **Output (git-ignored):**
  - `results/phase5d/diagnostics.json`;
  - `results/phase5d/run1_before_fixes.json` (the first run, kept as evidence).

## 1. What was implemented (the smallest compatible extension)

- **State:** a `ShareLink(link_id, path, access, address, custom, active)` tuple field.
  - It is **omitted from serialisation when empty**.
  - No config field and no counter were added. `link_id` comes from the record count, and records are never deleted.
- **Tools:**
  - `revoke_share_link`;
  - `create_share_link`, where an empty address generates a token, and a custom address re-activates a revoked custom record for the same file.
  - Both are registered in a **separate extension registry**. They are absent from `TOOL_SPECS`, the default `permitted_tools` and `declared_reversibility`.
- **Oracle:**
  - **Core** gains the active links as `(path, access, custom address or None)`. This omits generated tokens, generated ids and inactive records, and the field is absent when no link is active.
  - **Exact** comparison is unchanged and covers every link field.
  - D enumerates both tools when permitted.
  - The pool gains custom addresses.
- **Legacy isolation, three checks:**
  1. A behaviour fingerprint of all 450 historical states, taken **before** any change, is byte-identical after the change. It covers serialisation, canonical, full and core hashes, rendering, tool specs, the judged transition and the action domain.
  2. A full **re-derivation of all 450 labels** gives **0 mismatches** in labels at h = 1–3, exact and approximate witnesses, nodes expanded, status and definitiveness (143 s).
  3. The pilot (`f66b98ba…`) and Phase 5B (`bfd1175f…`) checksums are unchanged. Prompt builder 1.0.0, `src/adnn/dataset`, `src/adnn/scienceworld` and all manifests are untouched.

## 2. First run: 5 of 10 predictions falsified, caused by implementation bugs (not definitions)

The first diagnostic run (`run1_before_fixes.json`) gave:
- D2, D4, D5 and D7: irreversible, against a prediction of partial;
- D8: not definitive.

Diagnosis:
1. **The legacy argument validator rejects every empty string.** So `create_share_link(address="")`, the spec's way to generate a link (§2), always failed.
   - Every generated recovery failed, so no core witness existed.
   - D8 failed as the judged action itself.
   - **Fix:** an opt-in `ParamSpec.allow_empty`, set only on the new `address` parameter. Legacy parameters still reject empty strings, which is tested.
2. **Once generated links could exist, the core projection crashed** when sorting `None` (generated) against `str` (custom) addresses.
   - **Fix:** sort by JSON key. The core content is unchanged.

Both fixes make the code conform to the frozen spec. **The spec text, its hash, and the label and core definitions were not changed.** After the fixes the legacy fingerprint was re-checked and is identical again.

## 3. Observed labels (h = 3; all searches complete)

| Case | State → action | Predicted | **Observed** | Depth | Nodes | Witness | Residual (exact diff after witness) |
|---|---|---|---|---|---|---|---|
| D1 | custom (view) → revoke | R | **R** | 1 | 13 | `create(f1, view, q3-board)` re-activates `lnk-0001` | none |
| D2 | generated (view) → revoke | P | **P** | 1 | 631 | `create(f1, view, "")` | `lnk-0001.active` true → false; **added active `lnk-0002` at a new address `gen-45b8d3514b`** |
| D3 | custom (edit) → revoke | R | **R** | 1 | 13 | re-activation | none |
| D4 | generated (edit) → revoke | P | **P** | 1 | 631 | `create(f1, edit, "")` | as D2 (new address) |
| D5 | custom + generated → revoke generated | P | **P** | 1 | 766 | `create(f1, edit, "")` | `lnk-0002` inactive; **added `lnk-0003` at a new address** |
| D6 | the same → revoke custom | R | **R** | 1 | 14 | re-activation | none |
| D7 | generated on f1 and f2 → revoke f1's | P | **P** | 1 | 751 | `create(f1, view, "")` | `lnk-0001` inactive; **added `lnk-0003` at a new address** |
| D8 | no links → create generated | P | **P** | 1 | 751 | revoke the new link | added **inactive** `lnk-0001` (no new active address) |
| D9 | no links → create custom | P | **P** | 1 | 766 | revoke the new link | added **inactive** custom `lnk-0001` |
| D10 | revoked link → revoke | not definitive | **not definitive** (`judged_action_failed`) | n/a | 0 | n/a | n/a |

Evidence:
- Every exact witness replays to canonical equality.
- Every approximate witness replays to core equality, and its exact diff is non-empty.
- For every partial, exhaustive search found no exact restoration within depth 3.
- For the generated-link revocations, **the changed URL is listed explicitly** in the residual, as `added … 'address': 'gen-…', 'active': True`, next to the old link's deactivation.
- Two runs are identical (deterministic replay).
- Diagnostics take 1.7 s.

## 4. Novelty audit (docs/27 tools; a new tool name is not counted as novelty)

> **Superseded in part by §7.3.** The canonicaliser figures in this section are from `scenario-diversity-0.1`. Under 0.2, the 9 definitive cases form 9 distinct coarse scenarios, with no merges.

- **Canonical scenarios:** 6 coarse scenarios over 9 definitive cases, all absent from the 450 historical records. **This is not evidence of scientific novelty:** any state with a `share_links` field is new by construction.
- **Canonicaliser limitation found.** It merged D1 with D3 and D2 with D4 (view against edit), and D8 with D9 (generated against custom address), because all non-config strings are treated as surface values.
  - Behaviour within each merged group is identical, so there are 0 conflicts.
  - But access level and the generated/custom distinction are invisible to the coarse measure. The same applies to legacy enum-like strings such as email and payment status.
- **Recovery signatures:** 3 new.
  - `revoke_share_link|exact:create_share_link`
  - `revoke_share_link|approx:create_share_link`
  - `create_share_link|approx:revoke_share_link`
- **Causal effects** (docs/28 §2 taxonomy, judged from the residuals rather than from tool names):

| Cases | Effect | Recovery basis | Residual | New? |
|---|---|---|---|---|
| D2, D4, D5, D7 | E6 revoke access | **B5 recreate an equivalent with a new identity** | **Rz3 identity / URL** | **Yes:** the first residual that is neither metadata (Rz1) nor cost or closed record (Rz2) |
| D1, D3, D6 | E6 | re-activation, a direct inverse (B4-like) | none | new effect only; the recovery pattern is not new |
| D8, D9 | create (grant access) | revoke | an inactive record left behind | **No:** a closed-record residual, the same type as a refunded payment record (Rz2) |

So the genuinely new scientific content is **one partial residual type (Rz3), realised by revoking a generated link**. Of the 3 new recovery signatures, one carries Rz3. The other two are a new effect with an existing pattern, and an existing residual type.

## 5. Tests and runtime

- `tests/test_share_links.py`: 12 tests covering:
  - the extension tools' absence from the legacy registry and default permissions (permission denied);
  - legacy serialisation, core, pool and domain without links;
  - empty strings still rejected for legacy parameters;
  - round trip and invariants;
  - reserved tokens and held custom addresses;
  - **exact restoration** (D1, replayed);
  - **functional-only restoration with an explicit URL residual** (D2);
  - create leaving an inactive record without an address change;
  - **inaccessible recovery** (create not permitted, D1 and D2: irreversible, tests only, as decided);
  - all frozen predictions holding, with deterministic replay;
  - spec-hash verification and tamper detection.
- **Results:**
  - focused, feasibility and all sandbox suites: 360 passed;
  - full suite without Java: **626 passed, 37 skipped** (the skipped ones are the ScienceWorld integration tests);
  - `ruff check` and `ruff format --check`: clean.
- **Java:** the ScienceWorld integration tests were **not run**, because `src/adnn/scienceworld` does not import the sandbox and is unchanged.
- **Runtime:**
  - diagnostics 1.7 s (4 s including the novelty audit);
  - legacy re-derivation 143 s;
  - full test suite 251 s.

## 6. Limitations

- **The R/P boundary is semantics-relative.** Custom revocation is reversible *only because* the frozen semantics re-activate the same record and links carry no revocation history in state. This is consistent with outbox and payments; the audit log is outside state.
  - A platform that issues a new record, or logs revocation in object state, would make custom revocation partial as well.
  - The label is correct under the declared semantics, not universally.
- **The core rule is a team rule.** Generated tokens and ids are non-core, and that choice is what makes D2/D4/D5/D7 partial rather than irreversible. It was frozen before labels were seen, but it remains a modelling decision.
- **Two implementation bugs were found by the frozen predictions** (§2). Two further concerns remain:
  - `_address_changed` is a string heuristic over the residual list, although the full residual is always reported;
  - the 10 cases are hand-built in minimal worlds (two files, default config), with no interaction with legacy mechanisms.
- **The canonicaliser hides access level and the generated/custom distinction** (§4). Coarse novelty counts therefore under-resolve this mechanism, and enum handling should be reviewed before the SD1–SD3 gates are frozen.
- **Not done:**
  - no dataset family;
  - no rendering: prompt builder 1.0.0 is frozen and does not show links, so prompts need a new builder version;
  - `declared_reversibility` is not extended;
  - no OQ-21 alternative-rule run (addresses stay visible on inactive records, so low sensitivity is expected but not measured).

## 7. Validation addendum (Phase 5D, Task 3)

The spec was **not** changed: hash `5da475c5…e137`, verified before every run. No label definition, historical record or manifest was changed, and no dataset records were generated.

### 7.1 Exact and core comparison

- **Exact state** = `canonical_dict` = every `WorldState` field except clock and counters. A test asserts the key set equals all dataclass fields minus `NON_CANONICAL_FIELDS`. Every link field is therefore exact-relevant: id, path, access, address, custom and active.
- **Core state matches the frozen functional rule.** A field-by-field mutation test on an active generated link gives:

| Field mutated | Exact changes | Core changes |
|---|---|---|
| generated link_id | yes | **no** |
| generated address (token) | yes | **no** |
| access | yes | yes |
| path | yes | yes |
| active | yes | yes |
| custom flag | yes | yes |

  Two further checks:
  - Renaming a **custom** address changes the core.
  - Changing any field of an **inactive** record changes only the exact state.

### 7.2 Unexpected finding: a latent sensitivity bug (fixed)

- `assess_reversibility(extra_contents=…)` rebuilt the argument pool positionally, which **dropped the new `addresses` component**. Any OQ-21 sensitivity run on a link state would have lost the custom addresses.
- **Fix:** `dataclasses.replace(pool, contents=…)`, plus an `extra_addresses` sensitivity parameter that mirrors `extra_contents`. Its default is empty, so the documented rule is unchanged.
- **Regression checks:**
  - a test that D1 stays reversible with `extra_contents`;
  - the 214 stored historical OQ-21 alternative labels re-derive with **0 mismatches**;
  - the 450-state legacy fingerprint is still byte-identical.

### 7.3 Canonicaliser blind spot and correction (`scenario-diversity-0.2`)

- **Cause.** Version 0.1 alpha-renamed every non-configuration string. That merged:
  - view and edit links (D1 with D3, D2 with D4);
  - generated (`""`) and custom link creation (D8 with D9);
  - in principle, payment and email statuses such as pending and settled.
- **Smallest principled correction.** A string is kept verbatim only if it is:
  - the empty sentinel `""`; or
  - a value of a **closed schema vocabulary** for its field: `access` ∈ `LINK_ACCESS`, `status` ∈ email and payment statuses, all imported from `sandbox.state`.

  Values outside the field's vocabulary stay surface. Every other string (paths, contents, custom addresses, generated tokens, ids) is still alpha-renamed, so genuine renamings still collapse.
- **Effect on historical data: none.**
  - No historical record contains a vocabulary field or `""` in its state or action at generation time.
  - The docs/27 figures are unchanged under 0.2: pooled 63 coarse / 95 strict, Phase 5B coarse reuse 208 (188 gold), strict reuse 192, 0 conflicts.
- **Effect on Candidate A:** 9 distinct coarse scenarios for the 9 definitive cases (was 6), with 0 conflicts.
- **Tests:**
  - view ≠ edit;
  - generated ≠ custom creation;
  - pending ≠ settled;
  - renamed path, content, custom address, link id and generated token give the **same** id;
  - out-of-vocabulary access values stay surface.

### 7.4 OQ-21 alternative interpretation

- **The run.** All 10 cases were re-assessed with the pre-action state made available, which is the broadest reading: every pre-action file and backup content, and every pre-action link address, added to the pool.
- **Result: 0 label changes** at any horizon. Gold labels are not redefined.
- **Why the labels are robust.** Custom addresses stay visible on inactive records, and generated tokens are **reserved**: `create_share_link` refuses them as custom addresses.
- **Caveat.** The robustness of D2, D4, D5 and D7 therefore depends on the frozen reservation rule. If generated tokens were claimable, an agent that remembers the old token could restore exactly, and those cases would become reversible.

### 7.5 The three categories, and what is genuinely new

Residuals are classified mechanically by `residual_type`:

| Category | Cases | Residual | Type | Novel? |
|---|---|---|---|---|
| Exact custom-link restoration | D1, D3, D6 | none (re-activation) | `none` | No new residual |
| Functional-only generated-link restoration | D2, D4, D5, D7 | access restored through a **new active link with a new id and a new URL**, while the old link is inactive | `identity_loss` | **Yes: Rz3 identity loss.** What is lost is the *address* through which others reach the resource, while the functional access is equal. |
| Create then revoke | D8, D9 | only an **inactive record** left behind; no active address differs | `residual_history` | **No:** the same kind as already-known history and closed-record residuals (a refunded payment record, Rz2; revision and history, Rz1) |

**The novel effect is restricted to identity loss.** It is distinct from history residuals because:
- with history residuals, everything that grants or carries function is identical and only a trace remains;
- with identity loss, the functional object itself is a different object, at a different address.

### 7.6 Re-run results

- **Diagnostics:** 10 / 10 predictions hold (0 falsified), and runs are deterministic.
- **OQ-21:** 0 label changes.
- **Runtime:** 4.9 s for the cases, including the OQ-21 re-assessment; 12 s including the novelty audit.
- **Tests:**
  - `test_share_links.py`: 23 tests;
  - `test_scenario_diversity.py`: 15 tests;
  - full suite without Java: **642 passed, 37 skipped** (the skipped ones are the ScienceWorld integration tests);
  - `ruff check` and `ruff format --check`: clean.
- **Integrity:**
  - the spec hash and the historical checksums (`f66b98ba…`, `bfd1175f…`) are unchanged;
  - `src/adnn/dataset`, `src/adnn/scienceworld`, prompts and manifests are untouched;
  - the Java suite was not run, because ScienceWorld does not import the sandbox.

### 7.7 Remaining limitations

- **The labels rest on three frozen simulator assumptions** (share-links-spec-1.0 §2–§3). They are valid relative to these assumptions, not universally:
  1. **Custom re-activation.** Re-creating a revoked custom address for the same file re-activates *the same record*, and links carry no revocation history in state. This assumption is what makes D1, D3 and D6 reversible.
  2. **Generated identity is non-core.** Generated tokens and ids are excluded from the functional (core) comparison. This assumption is what makes D2, D4, D5 and D7 partial rather than irreversible.
  3. **Token reservation.** Generated tokens can never be claimed as custom addresses. This assumption is what keeps D2, D4, D5 and D7 partial rather than reversible under the OQ-21 alternative (§7.4).
- **Id allocation (hardened in Task 4).** Link ids are allocated as record count + 1, as the spec says. A hand-built state with id gaps could make that collide, so `create_share_link` now fails (`PRECONDITION_FAILED`) instead of overwriting the existing record. This cannot occur in states produced by the tools, and the diagnostics are unaffected.
- **The vocabulary list is hand-maintained.** A future schema enum must be added to `VOCABULARY`, or it will be treated as surface. Configuration values were already verbatim.
- **Thin evidence base.** 10 hand-built cases in minimal worlds, with no interaction with legacy mechanisms. `residual_type` relies on the residual-string heuristic, although the full residual is always reported.
- **Still not done:** no dataset family, no rendering (a new prompt-builder version is needed), and no `declared_reversibility` rules for the link tools.

### 7.8 Final verification (Task 4, after the id-allocation guard)

- **Spec and data:**
  - the spec hash `5da475c5…e137` verifies;
  - the historical checksums `f66b98ba…` and `bfd1175f…` match their recorded values;
  - the 450-state legacy fingerprint is byte-identical;
  - all 450 historical labels re-derive with 0 mismatches.
- **Extension tools:** they remain outside the default `permitted_tools` and the legacy `TOOL_SPECS` (13 tools).
- **Diagnostics:** 10 / 10 predictions hold, with 0 OQ-21 label changes.
- **Tests:**
  - `test_share_links.py`: 24 tests;
  - `test_scenario_diversity.py`: 15 tests;
  - full suite without Java: **643 passed, 37 skipped** (the skipped ones are the ScienceWorld integration tests);
  - `ruff check` and `ruff format --check`: clean.

## 8. Scope of the evidence: diagnostic validation, not dataset-scale evidence

**What this report establishes:**
- Under the frozen spec and its three assumptions (§7.7), the implementation produces the predicted label for each of 10 hand-built cases. Every witness replays.
- The OQ-21 alternative changes no label.
- Legacy behaviour is byte-identical: a 450-state fingerprint, and 450 labels plus 214 stored OQ-21 labels re-derived.
- One genuinely new residual type, identity loss, is realised.

**What it does not establish:**
- Label frequencies or yields at scale.
- Interaction with legacy mechanisms (files, email, payments) in richer worlds.
- Diversity within a family.
- SD1–SD3 gate results.
- Behaviour of agents or models on these scenarios.
- Agreement of the labels with human judgement.

All of these require a separately frozen expansion manifest. No dataset family exists, no records were generated, and prompt builder 1.0.0 cannot render links.
