# ADR-0011: ScienceWorld transfer evaluation set `adnn-sw-transfer-1.0`

- **Status:** *Accepted* (2026-11-04) by Sneha (M1). It follows the SWT pilot GO (docs/39).
  No professor approval is claimed.
- **Does not change:** dataset v1.0 or v2.0, their manifests or checksums; `src/adnn`, so
  v2.0's `code_sha256` pin still holds; the pilot pre-registration, `cases.py`, the go/no-go
  criteria, or any gold label.

## Decision

1. **A separate, unsplit evaluation set.** The 30 tier-G SWT pilot cases are not merged into
   v2.0. They are exported as a separate, unsplit evaluation set for REQ-ABL-04, in v2.0's
   ScienceWorld record format (prompt builder 1.1.0, `ts-scienceworld-1`).
2. **The 5 v2.0 ScienceWorld records are included verbatim.** Only `dataset_version` changes,
   plus three added `meta` keys. They are flagged `meta.source_phase = "phase4h"` and their
   v2.0 split side is recorded. Training for direction A must exclude v2.0 ScienceWorld
   records.
3. **Binary R vs P only.** There are no admitted irreversible ScienceWorld examples, and
   unresolved cases are not relabelled.
4. **State observation (exporter only).** The S0 raw fingerprint must equal the evidence. After
   `look` and `inventory`, the canonical state is checked rather than the raw fingerprint,
   because ScienceWorld re-draws display aliases of same-named objects in the valid-action list
   on every query. Two fresh rebuilds must give identical `state_text`.
5. **Room-level grouping.** Leave-one-room-out folds and room-cluster bootstrap are the
   recommended grouping, because start states are shared across task ids.

## Consequences

- **Transfer results** must state the R vs P scope and the verb/label confound (docs/40 §5).
- **Within ScienceWorld, the lexical baseline is trivially perfect.** REQ-BL-02 minimal-pair
  comparisons remain sandbox-only.
