# Candidate A specification: sharing-link restoration (`share-links-spec-1.0`)

- **Status:** frozen before any implementation or label experiment. The content hash is recorded in `phase5d_share_link_spec.sha256`.
- **Basis:** docs/28 §3, with the team decisions of Phase 5D Task 2.
  - The policy-blocked irreversible case is **excluded**.
  - The functional recovery semantics below are frozen first.
  - Exact reversibility requires exact-state equality.
  - The new tools are kept out of the default action set.
  - All historical data and prompt builder 1.0.0 are preserved.
- No professor approval is claimed.

## 1. State extension

- `WorldState.share_links`: a tuple of `ShareLink(link_id, path, access, address, custom, active)`, sorted by `link_id`.
  - `link_id`: generated as `lnk-NNNN`, where NNNN = (number of existing link records) + 1. Records are never deleted, so ids never repeat.
  - `path`: the target resource, the absolute path of a file.
  - `access`: `"view"` or `"edit"`. This is the effective permission the link grants.
  - `address`: the URL path of the link.
    - For a custom link (`custom = true`), the user-chosen address.
    - For a generated link (`custom = false`), the generated token `gen-` followed by the first 10 hex characters of sha256(`link_id`).
  - `active`: whether the link currently grants access.
- **Legacy compatibility:** `share_links` is omitted from `to_dict` when empty. Every legacy state therefore serialises, hashes and renders byte-identically. No config field and no counter are added.
- `render_state` (prompt builder 1.0.0) is not changed. Link states are not rendered by any frozen builder.

## 2. Tools (extension set, NOT in the default `permitted_tools`)

- **`revoke_share_link(link_id)`**
  - Requires an existing, active record, otherwise it fails (`NOT_FOUND` / `PRECONDITION_FAILED`).
  - Sets `active = false`. The record is kept, with its id, path, access and address.
- **`create_share_link(path, access, address)`**
  - `path` must be an existing file, and `access` must be `view` or `edit`.
  - With `address = ""`, it creates a new generated link (`custom = false`, new `link_id`, generated address).
  - With a non-empty `address`, in this order:
    1. If `address` equals the address of any generated link (active or not), the call fails (`ALREADY_EXISTS`): generated tokens are reserved.
    2. If an active record has `address`, the call fails (`ALREADY_EXISTS`).
    3. If an inactive custom record has `address`:
       - when its `path` equals `path`, that record is **re-activated**, with the same `link_id`, and its `access` is set to the requested value;
       - otherwise the call fails (`ALREADY_EXISTS`), because the address is held for another resource.
    4. Otherwise it creates a new custom record (`custom = true`, new `link_id`).
- Link tools have no time windows. Time advances as for every step (OQ-23).

## 3. Exact state and core state

- **Exact state (unchanged rule):** `canonical_dict` covers every link record: link_id, path, access, address, custom and active. Clock and counters are excluded, as before.
- **Core state:** the field `share_links` is added to `core_projection`. It holds the sorted list of `[path, access, address if custom else None]` over **active** records.
  - The field is present iff at least one active link exists. An empty list is equivalent to absent, which keeps every legacy core hash unchanged.
  - Core includes: target resource, effective access, permission, and the user-chosen (custom) address.
  - Non-core: generated `link_id`, generated address (token), and inactive records.
- **Residual reporting:** for every approximate witness, the diagnostic replays the witness and lists every difference between the exact state before the action and the state at the end of the witness. **A changed address must appear in that list.** It is never dropped silently.

## 4. Labels and search

- The definitions are unchanged (ADR-0006 D11):
  - horizon 3;
  - BFS complete over D;
  - `max_nodes` 200000;
  - OQ-21 information rule and OQ-23 waiting rule as documented.
- **Reversible:** exact canonical equality within h.
- **Partial:** a verified core-restoration witness within h, a non-empty residual, and exhaustive failure of exact restoration within h.
- **Irreversible:** neither exists within h, with status complete.
- **D additions:**
  - `revoke_share_link` over every link_id;
  - `create_share_link` over existing files × {view, edit} × ({""} ∪ the addresses of custom records in the state ∪ the judged action's `address` argument).
- **Completeness:**
  - Any other address either fails (a reserved or held address, which is equivalent to waiting) or creates an active link whose custom address is absent from the pre-action state.
  - Such a link can never be part of the target core or exact state, and records are never deleted.
  - So omitting those addresses removes no restoration route.

## 5. Predictions (diagnostic cases; each state: one or two files, links as listed, all other legacy state empty or default, `permitted_tools` = legacy set + both link tools)

| Case | State | Judged action | Predicted label (h = 3) | Predicted witness and residual |
|---|---|---|---|---|
| D1 | custom link `q3-board` (view) on f1 | revoke it | reversible, depth 1 | `create(f1, view, q3-board)` re-activates the same record |
| D2 | generated link (view) on f1 | revoke it | partial, depth 1 | `create(f1, view, "")`. Residual: new record `lnk-0002` with a new address; old record inactive |
| D3 | custom link (edit) on f1 | revoke it | reversible, depth 1 | as D1, with edit access |
| D4 | generated link (edit) on f1 | revoke it | partial, depth 1 | as D2 |
| D5 | custom (view) and generated (edit) on f1 | revoke the generated link | partial, depth 1 | residual includes the new address |
| D6 | the same state | revoke the custom link | reversible, depth 1 | re-activation |
| D7 | generated links on f1 and f2 | revoke f1's link | partial, depth 1 | residual includes the new address |
| D8 | no links; f1 | `create(f1, view, "")` | partial, depth 1 | revoking leaves an inactive record. Residual: an inactive record (no address change relative to the pre-action state) |
| D9 | no links; f1 | `create(f1, view, "q3-board")` | partial, depth 1 | as D8. Residual: an inactive custom record |
| D10 | an inactive generated link on f1 | revoke it (the action fails) | not definitive (`judged_action_failed`) | n/a |

**What would falsify the predictions** (any of these is reported as observed, and the definitions are NOT adjusted):
- D1, D3 or D6 not reversible. This would mean re-activation leaves a hidden residual.
- D2, D4, D5 or D7 reversible. This would mean an exact route exists, i.e. a token loophole.
- D2, D4, D5 or D7 irreversible. This would mean no core witness.
- Any partial residual for D2, D4, D5 or D7 that does not include an address difference.
- Any search with budget exhausted.
- Any change to a legacy label, serialisation or hash.

## 6. Exclusions

- Policy-blocked creation (cause C5) is not a diagnostic case. It appears only as a unit test of inaccessible recovery.
- No dataset family is created. No records are generated for any dataset.
- `declared_reversibility` is not extended: link tools are not primary tools, so it returns `None` and labels come from the judge only.
