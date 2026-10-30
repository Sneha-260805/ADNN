# 06 — Team Responsibilities

The names of Members 2 and 3 are not yet recorded. They are referred to as **M2** and **M3** until they add themselves here.

| Member | Name | Area |
|---|---|---|
| M1 | Sneha | Research setup, sandbox, dataset, reversibility labelling, ScienceWorld, documentation, repository integration |
| M2 | *TBD* | Hidden-state extraction, linear probes, probing baselines and controls |
| M3 | *TBD* | Explicit (stated) knowledge evaluation, agent behaviour, metrics, statistical analysis |

## 1. Sneha (M1): detailed ownership

**Research setup and integration**

- Maintain the traceability matrix (`00`), the open-questions list and the decision records; bring OPEN questions to the professor.
- Coordinate the novelty search (REQ-LIT-04) and the Group B reading assignment (REQ-LIT-02).
- Apply for Llama 3.1 access in week 1 (REQ-MOD-03). Each member using Llama must also accept the licence on their own HF account.
- Own `main`: final merge of PRs, release tags, `README.md` reproduction section (REQ-DEL-02), lock files (REQ-SW-02).

**Sandbox (`adnn.sandbox`)**

- State model (files, recycle bin, backups, edit history, outbox with undo window, wallet with transfer modes, simulated clock), tools with declared reversibility, `snapshot`/`restore`, `state_hash`, canonical state.
- `ask_user` tool with scripted replies (REQ-M-06).
- Brute-force reversibility verifier (REQ-ENV-03).
- Safety guarantee: no real side effects (REQ-SAFE-01) plus a static test for forbidden imports.
- Task environments and success predicates for the ≥60 RQ3 task pairs, co-designed with M3.

**Dataset (`adnn.dataset`)**

- Schema + validator (`05` §9); sandbox example generator with minimal pairs, pivot-phrasing variation and distractors; split generator; leakage tests.
- Shared prompt builder `prompting` (contract C3), co-reviewed by M2 and M3.
- Optional: ToolEmu 144-case import and labelling.
- Human-agreement study organisation and annotator 1 (REQ-LBL-05); data card (REQ-DATA-06).

**ScienceWorld (`adnn.scienceworld`)**

- Verify the current Python API and the licence (REQ-ENV-05, REQ-ENV-09).
- Restore mechanism (native or reset+replay), canonical state, bounded BFS at h=1,2,3, pruning rule, audit subset.

**Documentation:** all `docs/` files, data card, report sections on dataset and environments.

## 2. Member 2: detailed ownership

Full plan in `MEMBER_2_GUIDE.md`.

- `adnn.models`: model loading (one at a time), chat-template prompts via C3, action-token localisation, hidden-state extraction (last token + mean), resumable shards, sanity checks.
- `adnn.probes`: per-layer binary then three-class probes; inner-CV C and best-layer selection; all RQ1 baselines and controls (REQ-BL-01..05); lexical state+action control (ENG-08); ablations A1–A4.
- RQ1 metrics with CIs over 3 splits; figure F1; probe predictions for M3 (C6).
- If the bonus is attempted (proposed): steering direction and hooks for RQ4, and the 14B model.

## 3. Member 3: detailed ownership

Full plan in `MEMBER_3_GUIDE.md`.

- `adnn.behaviour`: stated-knowledge prompts and parser (RQ2); agent loop with JSON tool-call parsing, at most 15 steps, greedy decoding (RQ3); caution-event extraction rules; system-prompt ablation (A5, optional).
- RQ3 task *prompts* and the pilot base-rate check, co-designed with M1 (environments).
- `adnn.evaluation`: bootstrap CIs, McNemar, κ, all RQ2/RQ3 metrics, blindness gap; figures F2, F3.
- Owns the experiment register and the statistics section of the report; recorded demo for the presentation (REQ-DEL-05).
- If the bonus is attempted (proposed): steering runs with M2; RQ5 NLL analysis.

## 4. Shared responsibilities

| Item | Who |
|---|---|
| Group A reading in week 1 | Everyone (REQ-LIT-01) |
| Group B summaries | Divided; assignment recorded in `references/README.md` |
| Verifying every citation | Whoever cites it (REQ-LIT-03) |
| Second annotator for the 100-example study | M2 or M3 (OQ-16) |
| Analysis-plan freeze (REQ-STAT-04) | All three sign off |
| Report writing | Everyone writes their own sections; M1 integrates |
| Presentation | Everyone presents; demo by M3 |
| Contribution log | Each member writes their own paragraph (REQ-DEL-06) |

## 5. Deliverables and dependencies

| Deliverable | Producer | Needed by | Blocks |
|---|---|---|---|
| D1 Sandbox API + tool specs (C4) | M1 | M3 (agent loop), M1 (data) | RQ3, sandbox data |
| D2 Prompt builder (C3) | M1 | M2, M3 | Extraction, stated knowledge, agent |
| D3 Sandbox examples v0 (pilot, ~200) | M1 | M2 (pipeline dry run) | Early E1/E2 debugging |
| D4 Frozen dataset v1.0 + splits (C1, C2) | M1 | M2, M3 | Final E1–E3 |
| D5 Task pairs v1.0 (C5) | M1 + M3 | M3 | E4 |
| D6 Hidden states per model | M2 | M2 | E2 |
| D7 Probe predictions + best layer (C6) | M2 | M3 | E5 (κ, comparison) |
| D8 Stated answers, agent logs/outcomes | M3 | M3, M2 | E5 |
| D9 Evaluation utilities (C7) | M3 | M2, M3 | All CIs |
| D10 Figures, tables, report sections | All | — | Submission |

The critical path is D1 → D2 → D4 → D6 → D7 → E5. To avoid M2/M3 waiting on the frozen dataset, **D3 (a small pilot dataset) is released early** so the pipelines can be built and tested end-to-end. Pilot data is never used in reported results.

## 6. Review and integration process

- Every change goes through a PR with at least one reviewer who is not the author (`CONTRIBUTING.md`).
- **Contract changes** (C1–C8) need approval from *every* consumer listed in `03` §4.
- **Integration checkpoints** (short meeting + demo of the running pipeline):
  1. After D1/D2: M2 runs extraction on 10 sandbox examples; M3 runs the agent loop on 2 tasks.
  2. After D4: full dry run on Qwen with one split seed.
  3. Before the analysis-plan freeze: all three review `04`.
  4. Minimum publishable result check (REQ-MPR-01).
- Disagreements about research design go to `docs/OPEN_QUESTIONS.md`, then to a decision record, or to the professor if they touch a professor requirement.
