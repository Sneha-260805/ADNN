# Member 1 completion checklist (status on 2026-11-04)

- **Basis:** the Member 1 rows of `docs/00_REQUIREMENTS_TRACEABILITY.md`, which follow the
  professor's specification.
- **What it covers:** what is in the repository now and what is still outstanding, with
  evidence for each row.
- **Deadline:** 2026-11-10. **Target:** 2026-11-05/06.
- **Not changed by this checklist:** v1.0 and v2.0 are untouched (`b5a7d58f…` and
  `d03cd8f3…`).

## A. Completed

| REQ | Requirement (short) | Evidence |
|---|---|---|
| ENV-01, ENV-02, ENV-03 | Sandbox with file, email and wallet tools; snapshot and restore; each tool's label matches a brute-force restore | `adnn.sandbox`, `docs/11`, tests pass |
| SAFE-01 | Irreversible actions happen only inside the simulated sandbox | Static import check in tests (`docs/11`) |
| LBL-01 | Exactly three labels within h ≤ 3 | Schema validator (`adnn.dataset.validation`) |
| LBL-02 | Sandbox labels come from the design | Exact BFS oracle with a tool-label consistency test |
| LBL-03 | ScienceWorld labels from automatic search, via reset and replay | `adnn.scienceworld` (label evidence, `sw-admission-2`); 210 ScienceWorld tests pass with the pinned runtime |
| LBL-04 | Labels stored at h = 1, 2 and 3 | `labels_by_horizon` on every record (v1.0, v2.0 and the transfer set) |
| ENV-04 | ScienceWorld as the second testbed | 5 records in v2.0, plus a **35-record ScienceWorld transfer set** for REQ-ABL-04 (docs/40). n is too small for per-testbed RQ1 claims |
| ENV-05 | Reset and replay restoration, checked on sampled states | Replay fingerprint checks; docs/17–19 |
| ENV-08 | No large new environment | Only the existing sandbox and pinned ScienceWorld 1.3.0 are used |
| DATA-01 | ≥ 2,000 labelled pairs from both testbeds | v2.0: 2,134 gold (2,129 sandbox and 5 ScienceWorld), docs/37–38 |
| DATA-02 | Class balance reported | I 27.0%, P 35.5%, R 37.4% (docs/38) |
| DATA-03 | 20% test set split by scenario | 425 test records (19.9%), scenario-grouped, leakage test passes |
| DATA-04 | JSONL with the 7 core fields | Validator: schema check on every record |
| DATA-05 | ≥ 30% minimal pairs | 41.1% (439 pairs, 878 records) |
| M-02 (M1 part) | Prompt builder for hidden-state extraction | `adnn.dataset.prompting_v11` (builder 1.1.0) |
| ABL-04 (M1 part) | Data for transfer in both directions | `data/transfer/sw-transfer-1.0/` (20 R / 15 P), validated with 0 errors; handoff in docs/40 |

## B. Completed with caveats

| REQ | Caveat |
|---|---|
| DATA-06 / DEL-03 (data card) | `docs/38` covers construction, class counts and limitations. It **lacks agreement scores** (blocked by LBL-05) and a **dated licence check** (ENV-09). The spec's path `data/processed/DATA_CARD.md` is not used; the card is in `docs/38` |
| ABL-04 transfer label task | No admitted irreversible ScienceWorld examples exist, so transfer is R vs P only. In ScienceWorld the action verb fully predicts the label (docs/40 §5) |
| ABL-05 / LBL-04 horizons | The data supports it, but h2 = h3 everywhere and h1 differs on only 46 v2.0 records. In the transfer set every horizon is identical |

## C. Pending (Member 1 can do these without anyone else)

| REQ | What is missing | Effort |
|---|---|---|
| ~~M-05 (M1 part)~~ | **Done 2026-11-04:** 60 pairs / 120 versions frozen in `data/tasks/rq3-tasks-1.0/` (docs/42, preregistration `rq3_tasks_v1.md`) | — |
| ~~M-06~~ | **Done 2026-11-04:** `ask_user`, `backup_file` and `finish`, a separate RQ3 tool group (OQ-06 decided) | — |
| STAT-01 (M1 provides splits) | Three frozen scenario-grouped split files. v2.0 has one split | Small (pure, no simulator) |
| ENV-09 | Re-check licences, with a date, before release | Small |
| SW-02 | Lock file of exact library versions (`ENVIRONMENT_SETUP.md`: "there is no lock file yet") | Small |
| DEL-02 | README reproduction commands, dry run on a clean machine | Medium |
| LIT-04 (M1 coordinates) | The novelty search log in `references/README.md` is empty | Small |
| MOD-03 (M1 applies) | No Llama-3.1 access approval date is recorded in `docs/07` §7 | Small |
| ADR-0008 B4 | Pre-registered secondary family-disjoint split, not produced | Small |
| Release | v2.0 and the transfer set are git-ignored. Bundle them, or `git add -f` at a release tag after ENV-09 | Small |
| DEL-01 (M1 integrates), DEL-06 | Report integration and contribution log | Later phase |

## D. Blocked

| REQ | Status | Blocker | What unblocks it |
|---|---|---|---|
| **LBL-05 human agreement (100 pairs, two annotators, κ)** | **Not started.** There is no `data/annotation/`, no sheets, no annotations and no κ. Every label is oracle-derived. None of this is fabricated or approximated | A second human annotator is needed (OQ-16 open: Member 2 or 3), plus annotator time | Assign annotator 2. Member 1 can then generate blinded sheets: 100 examples, seed 20261101, ≥ 30 ScienceWorld (now possible from the 35-record transfer set plus v2.0; docs/05 §10) |
| DATA-06: κ values | Waiting on LBL-05 | Same | Same |

**Optional (not started; not required for the minimum result):**
- ENV-06 ToolEmu cases;
- ENV-07 and RQ5 ByteSized32;
- RQ4 support.

## E. Today's deliverable (2026-11-04)

- **Code:** `scripts/dataset/swt_transfer.py` (export and validate).
- **Data:** `data/transfer/sw-transfer-1.0/` (35 records, git-ignored; hashes in docs/40).
- **Docs:** docs/39 (pilot), docs/40 (transfer set and handoff), ADR-0011, this checklist.
- **Tests:**
  - full suite: 761 passed, 37 skipped (runtime absent);
  - ScienceWorld subset with the pinned runtime: 210 passed, 2 skipped (they need a separate
    source checkout);
  - `ruff check` and `ruff format --check` are clean on all Python code. Ten pre-existing
    Markdown docs contain code samples that ruff would reformat; they were left unchanged.
