# Contributions (REQ-DEL-06)

> **Draft, compiled during integration on 2026-11-15** from git authorship, branch contents
> and each member's own handoff documents. **It is not final until each member has confirmed
> or rewritten their own paragraph.** The specification asks for one paragraph per member in
> that member's own words. No percentages or effort estimates are given, because none are
> recorded.
>
> Members recorded that they used AI assistance (Claude Code and others) in `CONTRIBUTING.md`
> §7 and in their handoff documents. This integration branch was also prepared with AI
> assistance (Claude Code).

## Summary by member

| Member | GitHub | Commits on this branch | Branches |
|---|---|---:|---|
| Member 1 (Sneha) | `Sneha-260805` | 34 | `m1/sandbox-core`, `m1/dataset-v2`, `m1/sw-transfer`, and this integration |
| Member 2 | `srija180705` | 9 (+3 on the unmerged `m2/linear-probes`) | `m2/rq1_qwen_llama` |
| Member 3 | `Ananya35p` | 3 | `m3/feat/rq2-rq3-results` |

Commit counts measure commits, not effort. Member 2's and Member 3's work was largely done in
Kaggle notebooks and uploaded as large result commits.

## Member 1: sandbox, labels, datasets, ScienceWorld, human agreement, integration

Evidence: docs 10–43, `src/adnn/{sandbox,dataset,scienceworld,tasks}`, `scripts/{dataset,scienceworld,annotation,tasks}`.

- **Sandbox.** Deterministic tool sandbox (files, email, payments, share links) with an exact
  restoration oracle and safety tests (docs/10–11).
- **Prompts and data tooling.** Shared versioned prompt builders for RQ1–RQ3 (docs/12–14);
  dataset generator, validator and consumer API.
- **ScienceWorld.** Adapter, label-evidence pipeline and conservative admission (docs/16–24).
- **Dataset audits.** Feasibility, scaling, diversity and protocol audits (docs/25–33).
- **Production datasets.** v1.0 and v2.0 (2,134 gold records), each frozen before generation
  (ADR-0009, ADR-0010; docs/34–38).
- **ScienceWorld transfer set.** `adnn-sw-transfer-1.0`, for REQ-ABL-04 (ADR-0011;
  `docs/39_SCIENCEWORLD_TRANSFER_PILOT.md`, docs/40).
- **RQ3 task set.** The paired set `rq3-tasks-1.0` and its RQ3 tools (docs/42).
- **Human agreement study (REQ-LBL-05).** Organised the study: sampling, workbooks, validation
  and agreement analysis (docs/43). The traceability matrix assigns Member 1 as annotator 1.
  The repository does not record who annotator 2 was.
- **Integration.** Repository integration and the submission documents on this branch.

## Member 2: RQ1 hidden-state probing

Evidence: `docs/39_RQ1_FINAL_RESULTS.md`, `docs/audits/`, `results/rq1_{qwen,llama,comparison}/`, `notebooks/`, `scripts/rq1/`.

- **Probing.** Hidden-state extraction and L2 logistic-regression probes for
  Qwen2.5-7B-Instruct and Llama-3.1-8B-Instruct on the frozen v2.0 split. Covered the binary
  and three-class tasks, with layer screening and inner group-CV selection.
- **Baselines and controls:** majority, layer-0, shuffled-label, TF-IDF action and state+action,
  and the random-verb control task.
- **Diagnostics:** minimal pairs, bootstrap CIs, token-pooling ablation, within-verb analysis,
  supplementary splits, robustness subset and a post-hoc rendering-style diagnostic.
- **ScienceWorld transfer.** Bidirectional sandbox ↔ ScienceWorld transfer analysis.
- **Audits.** Prediction and results-archive audits.
- **Earlier work.** A Qwen-only probe analysis on the earlier dataset, on `m2/linear-probes`;
  superseded and not merged.

## Member 3: RQ2 stated judgment, RQ3 behaviour, cross-RQ analysis

Evidence: `docs/MEMBER3_*.md`, `docs/preregistration/member3_behaviour_v1.md`, `src/adnn/behaviour/`, `scripts/behaviour/`, `results/{rq2,rq3,member3_*}/`.

- **Implementation.** RQ2 judgment parsing and metrics, plus the RQ3 agent runner on Member 1's
  frozen task contract.
- **Runs.** Ran both models with greedy decoding and kept every prompt, raw response and trace.
- **Analysis.** Classification baselines, scenario-bootstrap intervals, RQ1–RQ2 agreement (κ),
  paired RQ3 metrics with McNemar tests, and trace replay.
- **Exploratory follow-ups, labelled as exploratory.** An RQ2 recovery-guidance prompt and an
  RQ3 Llama format-guidance prompt.
- **Writing.** The paper handoff text for the RQ2 and RQ3 sections, and the proposed demo
  trace.

## Final paragraphs (each member to write or confirm)

- **Member 1:** —
- **Member 2:** —
- **Member 3:** —
