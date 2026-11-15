# Do AI Agents Know Which Actions Cannot Be Undone?

This is a three-person research project for the ADNN course (Project Option 1). It is a
measurement study of open-weight LLM agents. We ask whether they:
1. know internally,
2. state correctly, and
3. act as if they know

that an action cannot be undone.

> **Status (2026-11-15, integration branch `integration/final-submission`).** All three
> research questions have completed experiments on two model families. The paper, the
> presentation and the recorded demo are **not** in this repository. Each number below
> links to its source file. [`docs/FINAL_REPRODUCIBILITY.md`](docs/FINAL_REPRODUCIBILITY.md)
> marks which numbers were **independently recomputed** during integration and which are
> **reported by the team only**.

## Why this matters

LLM agents now edit files, send emails and move money. Some actions can be undone: a file
moved to a recycle bin, or a payment that can still be cancelled. Others cannot: a file
deleted with no backup, or a final transfer. A model that *says* "deleting is permanent" but
deletes anyway shows what we call **irreversibility blindness**.

## Research questions

| | Question | Owner |
|---|---|---|
| **Knowledge** (RQ1) | Can reversibility be read from the model's hidden states with a linear probe, and at which layers? | Member 2 |
| **Judgment** (RQ2) | When asked directly, does the model classify an action as reversible, partially reversible or irreversible correctly? Does it agree with the probe? | Member 3 |
| **Behaviour** (RQ3) | When acting as an agent, is the model more careful before irreversible actions than before matched reversible ones? | Member 3 |

- **Models:**
  - Qwen2.5-7B-Instruct, revision `a09a3545…` for RQ2/RQ3;
  - Llama-3.1-8B-Instruct, revision `0e9e39f2…`.
- **Labels:** reversible (R), partially reversible (P) or irreversible (I). The recovery
  horizon is h = 1, 2 or 3 further actions; h = 3 is primary.
- **Optional RQ4 (steering) and RQ5 (uncertainty):** not attempted.

## Benchmark artifacts

| Artifact | Version | Size | Where | Integrity |
|---|---|---|---|---|
| Production dataset | `adnn-dataset-2.0` | 2,134 gold records (2,129 sandbox + 5 ScienceWorld); R 799 / P 758 / I 577; 41.1% in minimal pairs | `data/production/v2.0/` (**git-ignored**; bundle from Member 1) | `records.jsonl` sha256 `d03cd8f3…`; split `110d1b6a…` |
| Official split | scenario-grouped | train 1,709 / test 425 (test: R 68 / P 204 / I 153; 25 scenarios with records) | `split.json` in the bundle | verified, see below |
| ScienceWorld transfer set | `adnn-sw-transfer-1.0` | 35 records (R 20 / P 15; **no irreversible**) | `data/transfer/sw-transfer-1.0/` (git-ignored) | `records.jsonl` sha256 `cc39fd7a…` |
| RQ3 paired task set | `rq3-tasks-1.0` | 60 pairs = 120 task versions (deletion, overwrite, email, payment) | [`data/tasks/rq3-tasks-1.0/`](data/tasks/rq3-tasks-1.0/) (tracked) | `tasks.jsonl` sha256 `978a58a0…` |
| Human agreement study (REQ-LBL-05) | 100 minimal pairs, 2 annotators | 200 examples | `data/annotation/human_100_pairs/` + `results/human_annotation/` (git-ignored); archive ZIP | ZIP sha256 `1db30ace…` |

Details:
- dataset: [docs/37](docs/37_PRODUCTION_DATASET_V2.md), data card [docs/38](docs/38_DATA_CARD_PRODUCTION_V2.md);
- transfer set: [docs/40](docs/40_SW_TRANSFER_SET_AND_MEMBER2_HANDOFF.md);
- RQ3 tasks: [docs/42](docs/42_RQ3_TASKS_AND_MEMBER3_HANDOFF.md);
- human agreement: [docs/43](docs/43_HUMAN_ANNOTATION_RESULTS.md).

## Findings

### Label quality (REQ-LBL-05; Member 1)

Two humans labelled 200 examples (100 minimal pairs) blind to the automatic label. No
adjudication was done. Agreement:

| Comparison | Cohen's κ (95% CI) |
|---|---|
| Annotator 1 vs Annotator 2 | **0.621** [0.506, 0.729] |
| Annotator 1 vs automatic | 0.817 [0.743, 0.880] |
| Annotator 2 vs automatic | 0.734 [0.643, 0.821] |

All 51 R/P disagreements are file-revision/backup scenarios. Source:
[docs/43](docs/43_HUMAN_ANNOTATION_RESULTS.md).

### RQ1: probing (Member 2)

Official frozen v2.0 test split (n = 425), last-action-token representation, L2 logistic
regression:

| Task | Model | Layer | Balanced acc. | Macro-F1 | AUROC |
|---|---|---:|---:|---:|---:|
| 3-class | Qwen | 20 | 0.9216 | 0.9209 | 0.9951 |
| 3-class | Llama | 17 | 0.9074 | 0.9249 | 0.9918 |
| Binary (I vs not I) | Qwen | 18 | 0.9118 | 0.8838 | 0.9864 |
| Binary (I vs not I) | Llama | 16 | 0.9099 | 0.8815 | 0.9930 |

Controls and diagnostics for the binary task, from docs/39:
- Action-text TF-IDF reaches balanced accuracy 0.744.
- State+action TF-IDF reaches 0.844.
- The random action-verb control reaches **1.000**. This is a serious action-identity
  confound.
- On the canonical minimal pairs, pair accuracy drops to 0.347 (Qwen) and 0.542 (Llama).

**Interpretation.** Hidden states contain information that predicts the dataset's labels.
The evidence does **not** show that they encode irreversibility independently of action
identity. Source: [docs/39_RQ1_FINAL_RESULTS.md](docs/39_RQ1_FINAL_RESULTS.md),
[results/rq1_comparison/](results/rq1_comparison/).

### RQ2: stated judgment (Member 3)

Same 425 test examples, greedy decoding:

| | Accuracy | Balanced acc. | Macro-F1 |
|---|---:|---:|---:|
| Qwen | 26.35% | 28.49% | 0.221 |
| Llama | 48.00% | 33.33% | 0.216 |
| Action-text TF-IDF baseline | 76.00% | 72.88% | 0.716 |

- **Answer patterns.** Llama answered "partially reversible" for all 425 examples. Qwen
  answered "irreversible" for 337.
- **Agreement with the RQ1 probe.** Cohen's κ is −0.141 for Qwen and 0.000 for Llama.
- **Recovery-guidance prompt.** This follow-up was exploratory and run after the original
  results were inspected. It did **not** raise test balanced accuracy.

Source: [docs/MEMBER3_PAPER_HANDOFF.md](docs/MEMBER3_PAPER_HANDOFF.md),
[results/rq2/](results/rq2/), [results/member3_verified_analysis/](results/member3_verified_analysis/).

### RQ3: behaviour (Member 3)

60 matched task pairs per model:

| | Qwen | Llama | Llama + format guidance (follow-up) |
|---|---:|---:|---:|
| Successful final states | 119/120 | 87/120 | 117/120 |
| Caution, reversible versions | 15/60 | 30/60 | 30/60 |
| Caution, irreversible versions | 15/60 | 30/60 | 30/60 |
| Irreversible action taken on irreversible versions | 60/60 | 60/60 | 60/60 |
| Parse failures | 5 | 819 | 0 |

- **Reversibility sensitivity is zero.** Both models were exactly as cautious on the
  irreversible version as on the reversible version (McNemar: 0 discordant pairs, p = 1).
- **Blindness gap.** The headline gap K − A is 0. This reflects zero paired discrimination in
  **both** stated judgment and behaviour. It is not "knowing but acting blindly".

Source: [docs/MEMBER3_PAPER_HANDOFF.md](docs/MEMBER3_PAPER_HANDOFF.md),
[results/rq3/](results/rq3/), [results/member3_followups/](results/member3_followups/).

### One-sentence summary

Linear probes recover the labels from hidden states, though entangled with action identity.
The same models cannot state the labels and do not change their behaviour between matched
reversible and irreversible tasks.

## Repository layout

| Path | Content |
|---|---|
| `src/adnn/sandbox/` | Deterministic simulated tool world (files, email, payments, share links) and reversibility oracle |
| `src/adnn/dataset/` | Prompt builders, dataset generator, validator, loader (`api.py`), annotation tools |
| `src/adnn/scienceworld/` | ScienceWorld adapter, label evidence, exporter |
| `src/adnn/tasks/` | RQ3 task contract and frozen task generator |
| `src/adnn/behaviour/` | RQ2 judgment parsing/metrics, RQ3 agent runner, prompt conditions (Member 3) |
| `scripts/rq1/` | RQ1 probe selection/training, robustness and ScienceWorld transfer scripts (Member 2) |
| `scripts/behaviour/` | RQ2/RQ3 run, follow-up and summary scripts (Member 3) |
| `scripts/validation/` | Read-only integration checks: checksums, metric recomputation, RQ3 replay |
| `notebooks/` | Kaggle notebooks for RQ1 extraction and probing (Member 2) |
| `results/rq1_*`, `results/rq2`, `results/rq3` | **Original** experiment outputs. Do not edit |
| `results/member3_followups/` | **Exploratory** follow-up experiments, kept separate from the originals |
| `docs/` | Design docs, phase reports, decision records (`decisions/`), frozen manifests (`preregistration/`), audits |
| `artifacts/MANIFEST.md` | Inventory of every research artifact, with location and checksum |

## Installation

Python 3.11. These commands were tested on Windows during integration. The CI workflow
(`.github/workflows/ci.yml`, Ubuntu) has been dry-run locally but has not run on GitHub yet.

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev,data,probes,annotation]"   # Linux/macOS: .venv/bin/python
.venv/Scripts/python.exe -m adnn.demo                                        # sandbox demo
.venv/Scripts/python.exe -m pytest -q
```

GPU extras (`.[models]`) are needed only to rerun model inference. ScienceWorld integration
tests need the pinned isolated runtime ([`ENVIRONMENT_SETUP.md`](ENVIRONMENT_SETUP.md)).

## Reproducing the reported numbers

These checks run on CPU without models. They write nothing under `results/` or `data/`:

```bash
python scripts/validation/verify_frozen_artifacts.py      # SHA-256 of dataset, transfer set, tasks, annotation
python scripts/validation/recompute_saved_metrics.py      # RQ1/RQ2/RQ3 metrics from saved predictions + RQ3 replay
```

- **Without the git-ignored bundle.** RQ2/RQ3 recomputation and the RQ3 replay still run,
  because the task set is tracked. RQ1 metrics are recomputed from the saved predictions, but
  the test-split membership check is skipped.
- **Do not run `scripts/behaviour/summarize.py` on an original run directory.** It
  overwrites that directory's `metrics.json`.

Rerunning models, re-extracting hidden states and regenerating the dataset are documented,
with their current blockers, in
[`docs/FINAL_REPRODUCIBILITY.md`](docs/FINAL_REPRODUCIBILITY.md).

## Limitations

- **Action-identity confound (RQ1).** A random per-verb label is perfectly predictable, and
  minimal-pair accuracy is low. The probes do not establish action-independent encoding.
- **Test split.** The test split is imbalanced (68 reversible records) and concentrated: 25
  scenarios have records, and one scenario contributes 102. The `compact` rendering style
  appears only in the test set.
- **ScienceWorld.** There are only 5 ScienceWorld records in v2.0, and the 35-record transfer
  set has no irreversible examples. In ScienceWorld the action verb predicts the label
  perfectly.
- **Human agreement is moderate.** Human–human κ is 0.62, and disagreements were not
  adjudicated. The partial-reversibility definition (OQ-21) was not confirmed by the
  professor.
- **Exploratory follow-ups.** The RQ2 recovery prompt and the RQ3 format prompt were run after
  inspecting the original results.
- **Provenance gaps:**
  - Hidden-state arrays and probe weights are not archived with checksums.
  - The Qwen RQ1 model revision was not recorded, and the Llama RQ1 loading was unpinned.
  - Member 3's inference ran from uploaded source bundles. The committed `runner.py` and
    `run.py` are the reviewed post-inference versions; the RQ3 replay still reproduces every
    trace with them.
- **Missing release steps.** There is no library lock file (REQ-SW-02), no dated licence
  re-check (REQ-ENV-09) and no novelty search log (REQ-LIT-04).
- **Scope.** The study covers two 7–8B model families, four sandbox mechanisms and a
  three-step horizon.

## Team and documents

See [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md) for what each member did, and these documents:
- [`docs/FINAL_REQUIREMENTS_CHECKLIST.md`](docs/FINAL_REQUIREMENTS_CHECKLIST.md): requirement
  status with evidence;
- [`docs/INTEGRATION_REPORT.md`](docs/INTEGRATION_REPORT.md): how the branches were
  integrated;
- [`CONTRIBUTING.md`](CONTRIBUTING.md): workflow;
- [`GITHUB_HANDOFF.md`](GITHUB_HANDOFF.md): dataset sharing.

**Paper and demo:** not in this repository yet. The demo trace that Member 3 proposes is
[`results/rq3/llama/full/rq3-email-send-01-irr.jsonl`](results/rq3/llama/full/rq3-email-send-01-irr.jsonl).
