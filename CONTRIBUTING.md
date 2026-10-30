# Contributing

Rules for the three-person team. When in doubt, open an issue or add an entry to `docs/OPEN_QUESTIONS.md`.

## 1. Git workflow

- `main` is always in a working state: tests pass, docs consistent. **No direct pushes to `main`** after the initial commit. Everything goes through pull requests.
- Short-lived feature branches off `main`; rebase or merge `main` frequently.
- Tags:
  - `data-vX.Y` — frozen dataset releases;
  - `analysis-plan-v1` — frozen protocol (REQ-STAT-04);
  - `submission` — final.
- Never commit secrets (HF tokens), large hidden-state arrays, or data with licence restrictions (see `.gitignore`).
- Reported results must come from a **clean, committed** state (`git_dirty: false` in the manifest).

## 2. Branch naming

`<member>/<type>/<short-description>`

- member: `m1`, `m2`, `m3`;
- type: `feat`, `fix`, `docs`, `exp` (experiment configs/results), `data`, `refactor`, `test`.

Examples: `m1/feat/sandbox-recycle-bin`, `m2/feat/hidden-state-extraction`, `m3/exp/qwen-agent-neutral`.

Commit messages: imperative, short subject (≤ 72 chars), with a body explaining *why* when it isn't obvious. Reference requirement IDs where relevant, e.g. `Add brute-force restore verifier (REQ-ENV-03)`.

## 3. Pull request reviews

- At least **one approving review from another member**.
- **Contract changes** (C1–C8 in `docs/03_SYSTEM_ARCHITECTURE.md` §4: dataset schema, splits format, prompt builder, sandbox API, task format, probe predictions, evaluation API, manifests) require approval from **every consumer** of that contract.
- Changes to anything tagged `[SPEC]` in configs, or to a professor requirement's interpretation, need a note in `docs/OPEN_QUESTIONS.md` or a decision record. They may need professor approval.
- After the analysis plan is frozen, any change to metrics, caution rules, best-layer selection or primary outcomes needs a decision record and an `exploratory` label on affected analyses.

PR template (include in the description):

```
What: …
Why (requirement IDs): …
Contracts touched: none | C…
Tests: added/updated …; `pytest` + `ruff check .` pass locally? yes/no
Docs updated: …
Results affected: none | which runs must be redone
```

## 4. Coding standards

- Python 3.11; `src/adnn` package; type hints on all public functions. Code must pass `ruff check .` (config in `pyproject.toml`).
- Pure functions for data transformations and metrics; side effects (I/O, model calls) kept at the edges (scripts/experiments).
- No research logic in notebooks. Notebooks call package code.
- Every randomness source takes an explicit seed from the config.
- Sandbox code must never touch the real file system, network, email or accounts (REQ-SAFE-01). Enforced by a test.
- No paid-API SDKs (`openai`, `anthropic`, …) anywhere in the project dependencies (REQ-SAFE-02).
- Log every prompt and model output (REQ-REP-03).

## 5. Documentation requirements

- A PR that changes behaviour updates the relevant doc in `docs/` in the same PR.
- New design decisions → `docs/decisions/NNNN-title.md` (context, decision, alternatives, consequences).
- Update the **Status** column of `docs/00_REQUIREMENTS_TRACEABILITY.md` when a requirement is implemented or validated.
- Never write results, numbers or "tested" commands into docs that have not actually been produced or run.
- Citations: only papers someone has opened and verified (REQ-LIT-03). Record verification in `references/README.md`.

## 6. Test expectations

- `pytest` must pass before merge. New modules come with unit tests. The guides (`docs/MEMBER_2_GUIDE.md` §7, `docs/MEMBER_3_GUIDE.md` §7) list the minimum tests.
- Bug fixes include a regression test.
- Tests run on CPU without model downloads. GPU-dependent code paths are tested with tiny fakes or mocks.
- Dataset changes must pass the validator (`docs/05_DATASET_SPECIFICATION.md` §9).

## 7. Contribution log (REQ-DEL-06)

The spec requires an individual contribution log with one paragraph per member in the final submission. Keep a running log here; summarise it into the paragraphs at the end.

| Date | Member | Contribution | PR / commit |
|---|---|---|---|
| 2026-10-30 | Sneha (M1) | Repository scaffold and initial documentation (requirements traceability, methodology, protocol, dataset spec, architecture, guides). Drafted with AI assistance (Claude Code); **pending Sneha's review** | 0016c9c |
| 2026-10-30 | Sneha (M1) | Deterministic sandbox core (state model, 13 tools, restoration judge, design table, demo), scientific-correctness audit (4 defects fixed), 346 new tests, docs 10–11. Drafted with AI assistance (Claude Code); **pending Sneha's review** | — (uncommitted, `m1/sandbox-core`) |

### Final paragraphs (to be written at the end)

- **Sneha (M1):** —
- **Member 2:** —
- **Member 3:** —
