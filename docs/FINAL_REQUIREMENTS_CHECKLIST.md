# Final requirements checklist

- **Basis:** the requirement IDs in
  [`00_REQUIREMENTS_TRACEABILITY.md`](00_REQUIREMENTS_TRACEABILITY.md), which follow the
  professor's specification. That document's "Documented" status means the requirement is
  *written down*, not that it is *met*. This checklist replaces it for the submission.
- **Branch and date:** `integration/final-submission`, 2026-11-15.
- **Evidence references:** "Repro §n" refers to [`FINAL_REPRODUCIBILITY.md`](FINAL_REPRODUCIBILITY.md).

| Status | Meaning |
|---|---|
| ✅ **Verified** | Supporting files exist **and** the claim was re-executed or recomputed during integration |
| ☑️ **Evidenced** | Supporting files exist; the claim is the team's and was not re-executed here |
| 🟡 **Partial** | Some evidence exists, but part of the requirement is unmet or unverifiable |
| ❌ **Not done** | No supporting evidence in the repository |
| ➖ **Not attempted** | Optional or bonus requirement, deliberately not done |

## Research questions and framing

| REQ | Status | Evidence / gap |
|---|---|---|
| RQ-01 RQ1 probes, layers | ✅ sandbox / 🟡 ScienceWorld | Final test metrics recomputed from predictions (Repro §5); per-layer screening in `results/rq1_*/probes/*layer_screening.json`. ScienceWorld: 35-record R-vs-P transfer only (docs/39 §9) |
| RQ-02 RQ2 stated judgment + agreement with probe | ✅ | Metrics recomputed, IDs and labels aligned (Repro §6). κ(stated, probe) in `results/member3_followups/rq1_rq2_agreement.csv` (☑️) |
| RQ-03 RQ3 behaviour, ≥ 60 pairs | ✅ | 60 pairs × 2 models; metrics recomputed; 240/240 original traces replay (Repro §7) |
| RQ-04 steering (bonus) | ➖ | — |
| RQ-05 uncertainty (bonus) | ➖ | — |
| RQ-06 one clear finding | 🟡 | Stated in README "One-sentence summary". The paper that should carry it is not in the repo |
| RQ-07 measurement study framing | ☑️ | README, docs/01 |

## Literature

| REQ | Status | Evidence / gap |
|---|---|---|
| LIT-01, LIT-02 reading / summaries | ❌ | No record in the repository |
| LIT-03 verify citations | ❌ | No verification record in `references/README.md` |
| LIT-04 novelty search | ❌ | `references/README.md` search log is empty |

## Environments and labels

| REQ | Status | Evidence / gap |
|---|---|---|
| ENV-01/02/03 sandbox, state, tool reversibility | ✅ | `src/adnn/sandbox`; tests pass; demo run (Repro §2–3) |
| ENV-04 ScienceWorld second testbed | 🟡 | 5 records in v2.0 + 35-record transfer set (checksums ✅). Too small for per-testbed claims; no irreversible examples |
| ENV-05 ScienceWorld reset/replay | ☑️ | docs/17–19. The 41 runtime tests were skipped here (no pinned runtime) |
| ENV-06 ToolEmu, ENV-07 ByteSized32 (optional) | ➖ | — |
| ENV-08 no large new environment | ✅ | Only the sandbox and pinned ScienceWorld 1.3.0 |
| ENV-09 licence re-check before release | ❌ | Not done (docs/41 §C) |
| LBL-01 three labels within h ≤ 3 | ✅ | Validator + schema tests pass |
| LBL-02 sandbox labels from design | ✅ | Oracle and tool-label consistency tests pass |
| LBL-03 ScienceWorld labels via search | ☑️ | `adnn.scienceworld`; runtime tests not executed here |
| LBL-04 report results for h = 1, 2, 3 | 🟡 | Labels stored per horizon; `results/rq1_*/ablations/*horizon_ablations.json` (binary RQ1 only); not summarised in docs/39. h2 = h3 on every v2.0 record, and h1 differs on 46 |
| LBL-05 human agreement, 100 pairs | ✅ | κ_hh 0.621, κ_h-auto 0.817 / 0.734 with CIs; analysis re-run byte-identically; archive checksum matches (Repro §8). No adjudication |

## Dataset

| REQ | Status | Evidence / gap |
|---|---|---|
| DATA-01 ≥ 2,000 pairs from both testbeds | ✅ count / 🟡 balance | 2,134 records, checksum verified. Only 5 are from ScienceWorld |
| DATA-02 class counts, balanced accuracy | ✅ | R 799 / P 758 / I 577; balanced accuracy used throughout |
| DATA-03 20% scenario-split test set | ✅ | 425/2,134 (19.9%); RQ1 and RQ2 predictions cover exactly this split (Repro §5–6) |
| DATA-04 JSONL with core fields | ✅ | Validator tests pass |
| DATA-05 ≥ 30% minimal pairs | ☑️ | 41.1% (docs/38) |
| DATA-06 data card | 🟡 | `docs/38` includes construction, counts, κ and limitations. No dated licence check |

## Models, software and reproducibility

| REQ | Status | Evidence / gap |
|---|---|---|
| MOD-01 two families | ✅ | Qwen2.5-7B-Instruct and Llama-3.1-8B-Instruct in all RQs |
| MOD-02 Qwen first | ☑️ | Commit order |
| MOD-03 Llama licence acceptance date | ❌ | Not recorded (docs/41 §C) |
| MOD-04 14B (optional) | ➖ | — |
| MOD-05 one model at a time, small batches | ☑️ | Run configs |
| SW-01 PyTorch + HF | ✅ | Run configs (versions recorded) |
| SW-02 exact versions in a requirements file | ❌ | No lock file. Versions exist only inside the run configs |
| REP-01 greedy decoding | ✅ | `do_sample: false` in all 15 Member 3 configs |
| REP-02 fixed seeds | ✅ | Seed 42 (configs); probe `random_state` 42 |
| REP-03 save prompts and outputs | ✅ RQ2/RQ3 / 🟡 RQ1 | Full messages and raw outputs in traces. RQ1 hidden states not archived |

## Method steps

| REQ | Status | Evidence / gap |
|---|---|---|
| M-01 steps 1–5 | ✅ | See the rows below |
| M-02 prompt builder for extraction | ✅ | `adnn.dataset.prompting_v11`, prompt-hash tests pass |
| M-03 per-layer L2 probes, binary + 3-class | ☑️ | Layer screening files and notebooks. Final layer metrics ✅ |
| M-04 ask the model in plain language | ✅ | RQ2 outcomes contain prompts and raw answers |
| M-05 ≥ 60 sandbox tasks | ✅ | `rq3-tasks-1.0`, checksum verified |
| M-06 `ask_user` tool | ✅ | `src/adnn/tasks`; RQ3 tool set |
| M-07 log irreversible action and caution | ✅ | Outcome fields reproduced by replay |
| M-08, M-09 (bonus) | ➖ | — |

## Metrics, baselines, ablations, statistics

| REQ | Status | Evidence / gap |
|---|---|---|
| EVAL-01 baselines, n and 95% CI for every number | ☑️ | RQ1 bootstrap CIs; RQ2 scenario bootstrap; RQ3 pair bootstrap (✅ recomputed) |
| MET-01 RQ1 bal-acc, macro-F1, AUROC per layer | ☑️ | Layer screening JSON/PNG |
| MET-02 selectivity | 🟡 | Llama only: `results/rq1_llama/baselines/llama_v2_binary_selectivity.json` (−0.105). No Qwen selectivity file. The random-verb control is 1.0 for both models |
| MET-03 RQ2 accuracy + κ with probe | ✅ / ☑️ | Accuracy recomputed; κ reported |
| MET-04 RQ3 rates | ✅ | Recomputed |
| MET-05 reversibility sensitivity | ✅ | 0.0 for both models, recomputed |
| MET-06 blindness gap K − A | ✅ | 0.0, recomputed. Interpretation in README |
| MET-07, MET-08 (bonus) | ➖ | — |
| BL-01 majority | ☑️ | `results/rq1_*/baselines`, `member3_verified_analysis/rq2_scores_and_baselines.csv` |
| BL-02 action-text lexical | ☑️ | RQ1 TF-IDF and RQ2 TF-IDF baselines |
| BL-03 shuffled-label probe | ☑️ | `*shuffled_label_control.json` |
| BL-04 control task (random verb label) | ☑️ | 1.0 for both models: action-identity confound |
| BL-05 layer-0 probe | ☑️ | docs/39 §7 |
| BL-06 (RQ4 only) | ➖ | — |
| ABL-01 ≥ 4 ablations | ☑️ | ABL-02, 03, 04, 05 and 08 below |
| ABL-02 last vs mean token | ☑️ | `results/rq1_*/ablations/*mean_action_tokens*` |
| ABL-03 minimal pairs vs all | ☑️ | docs/39 §8 |
| ABL-04 cross-environment both directions | 🟡 | Directions A and B (docs/39 §9). The transfer set is R vs P only, and per-example predictions are absent |
| ABL-05 horizon | 🟡 | See LBL-04 |
| ABL-06 careful vs neutral prompt (optional) | ❌ | Planned (`format_careful_v1`, docs/MEMBER3_FOLLOWUP_PLAN.md); no run results. The format and recovery follow-ups are different interventions |
| ABL-07 7B vs 14B (optional) | ➖ | — |
| ABL-08 binary vs 3-class | ✅ | Both tasks recomputed |
| STAT-01 3 scenario splits | 🟡 | Supplementary seeds 42/123/2026 (docs/39 §6), with hyperparameters fixed from the official split. No frozen split files from Member 1 |
| STAT-02 bootstrap 1,000 | ✅ | RQ3 CIs reproduced with 1,000 resamples |
| STAT-03 McNemar | ✅ | Recomputed (0 discordant, p = 1) |
| STAT-04 analysis fixed in advance; report all runs | 🟡 | Preregistrations exist (`docs/preregistration/`). The follow-ups were post hoc and are labelled exploratory. The rendering-style diagnostic is post hoc |

## Deliverables

| REQ | Status | Evidence / gap |
|---|---|---|
| DEL-01 paper (6–8 pages) | ❌ | Not in the repository |
| DEL-02 README reproduces every table/figure; requirements file | 🟡 | README and FINAL_REPRODUCIBILITY give CPU commands for the final-metric tables. Hidden-state tables cannot be reproduced; no lock file |
| DEL-03 labelled dataset JSONL + data card | 🟡 | Data card in repo. The dataset is git-ignored and shared as a checksummed bundle, not in a release |
| DEL-04 probe scores, agent logs, notebooks/scripts | 🟡 | Predictions, logs, traces, notebooks and scripts present. Hidden states, probe weights and executed source bundles absent |
| DEL-05 presentation + demo | ❌ | Not in the repository. A demo trace is proposed (README) |
| DEL-06 contribution log | 🟡 | `CONTRIBUTIONS.md` drafted from git history and docs. **Each member must confirm or rewrite their own paragraph** |
| DEL-07 required figures | 🟡 | Probe-vs-layer and baseline plots (`results/rq1_comparison/`); RQ2 comparison figure. No single stated-vs-probed-vs-behaviour figure found |
| DEL-08 limitations | ✅ | README, docs/39 §11, Member 3 handoff, docs/38 |

## Risks and safety

| REQ | Status | Evidence / gap |
|---|---|---|
| RISK-01 strict format, parse failures counted | ✅ | `parse_failures` reproduced by replay (Llama: 819) |
| RISK-02 … RISK-07 | ☑️ | Contingencies documented. RISK-04 did not trigger (irreversible action taken 60/60) |
| MPR-01 minimum publishable result | 🟡 | Met for the sandbox, two models, all three RQs. The "two testbeds" part is limited by ScienceWorld size |
| SAFE-01 irreversible actions sandbox-only | ✅ | Static safety tests pass |
| SAFE-02 no paid APIs | ☑️ | Open-weight HF models on Kaggle GPUs (run configs) |
