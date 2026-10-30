# Do AI Agents Know Which Actions Cannot Be Undone?

ADNN MSc AI semester project (Project Option 1). A measurement study of whether open-weight LLM agents (1) internally represent whether an action is reversible, (2) say so correctly when asked, and (3) act more carefully before irreversible actions.

> **Status (2026-10-30): setup, planning and the sandbox core (branch `m1/sandbox-core`).**
> The repository contains documentation, the package scaffold and the deterministic tool sandbox with tests. **No dataset, model run or result exists yet.** Nothing in this repository should be read as a finding.

## Motivation

LLM agents edit files, send messages and move money. Some actions can be undone (moving a file to a recycle bin) and some cannot (deleting without a bin, sending an email). Careful humans slow down before irreversible steps.

If a model can say "deleting is permanent" but still deletes without hesitation when acting, the specification calls this **irreversibility blindness**. We measure it with the gap **K − A**:

- K = how often the model correctly states which version of a task is irreversible;
- A = how often the agent is actually more careful in that version.

## Research questions

| RQ | Question | Required |
|---|---|---|
| RQ1 | Can reversibility be linearly decoded from hidden states, and at which layers? | Yes |
| RQ2 | Does the model correctly *state* reversibility, and does that agree with the probe? | Yes |
| RQ3 | Does agent behaviour become more cautious before irreversible actions? | Yes |
| RQ4 | Does steering along the probe direction increase caution? (causal) | Bonus, not in the initial plan |
| RQ5 | Is next-state uncertainty related to reversibility? | Bonus, not in the initial plan |

**Models:** Qwen2.5-7B-Instruct (main), then Llama-3.1-8B-Instruct (second family).

**Testbeds:** our own Python tool sandbox (exact reversibility by design) and ScienceWorld (labels by bounded search over restoring action sequences, horizons 1/2/3).

**Data targets** (spec):

- ≥2,000 labelled (state, action) examples with three labels (reversible, partially reversible, irreversible);
- ≥30% state-dependent minimal pairs;
- 20% scenario-level held-out test set;
- ≥60 paired agent tasks.

## Architecture

```
Sandbox + ScienceWorld ──▶ labelled dataset + splits + shared prompts  (CPU, Member 1)
                               │
          ┌────────────────────┼──────────────────────┐
          ▼                    ▼                      ▼
  hidden-state extraction   stated-knowledge      agent loop (≤15 steps,
  (GPU, Member 2)           prompts (GPU, M3)     JSON tool calls; GPU, M3)
          ▼                    │                      │
  linear probes + controls     └──────────┬───────────┘
  (CPU, Member 2) ────────────────────────▶ evaluation: metrics, CIs, McNemar,
                                             blindness gap (CPU, Member 3)
```

Details and the Mermaid diagram: [`docs/03_SYSTEM_ARCHITECTURE.md`](docs/03_SYSTEM_ARCHITECTURE.md).

## Team ownership

| Member | Area |
|---|---|
| Sneha (M1) | Research setup, sandbox, dataset, reversibility labelling, ScienceWorld, documentation, repository integration |
| Member 2 (name TBD) | Hidden-state extraction, linear probes, baselines and controls |
| Member 3 (name TBD) | Stated-knowledge evaluation, agent behaviour, metrics, statistics |

See [`docs/06_TEAM_RESPONSIBILITIES.md`](docs/06_TEAM_RESPONSIBILITIES.md).

## Environments

- **Development:** Windows + Claude Code; Python **3.11** (target); pytest, ruff.
- **GPU inference:** Colab/Kaggle notebooks that call package scripts at a pinned commit. Course GPUs may be used instead; this is an open question (OQ-01).
- **ScienceWorld:** needs Java ≥ 1.8. Recommended under WSL2/Linux.
- **Never:** paid inference APIs for results, or any real external side effect (all irreversible actions are simulated).

## Repository navigation

| Path | Content |
|---|---|
| `src/adnn/` | Package. Subpackages `sandbox`, `dataset`, `scienceworld`, `models`, `probes`, `behaviour`, `evaluation`, `experiments` (docstring placeholders only) |
| `tests/` | pytest suite (currently a package-layout test only) |
| `configs/` | Experiment configs (`defaults.yaml` is a tagged template) |
| `data/` | Dataset, splits, agent tasks, annotations (empty) |
| `results/` | Run outputs with manifests (empty) |
| `notebooks/` | Thin Colab/Kaggle drivers (none yet) |
| `scripts/` | CLI entry points (none yet) |
| `references/` | Project specification (authoritative) + reading list and novelty log |
| `docs/00_REQUIREMENTS_TRACEABILITY.md` | Every professor requirement → owner, module, acceptance test, status |
| `docs/01`–`09` | Problem, methodology, architecture, protocol, dataset, team, reproducibility, risks, roadmap |
| `docs/MEMBER_2_GUIDE.md`, `docs/MEMBER_3_GUIDE.md` | Implementation plans and contracts for Members 2 and 3 |
| `docs/OPEN_QUESTIONS.md` | Unresolved design decisions (several need the professor) |
| `docs/decisions/` | Architecture decision records |
| `CONTRIBUTING.md` | Git workflow, reviews, standards, contribution log |

## Current implementation status

| Component | Status |
|---|---|
| Requirements analysis and documentation | Drafted, pending team review |
| Package scaffold, `pyproject.toml`, layout test | Created; passing under Python 3.11.9 |
| Sandbox core (`adnn.sandbox`, `python -m adnn.demo`) | Implemented and audited; 355 tests pass, ruff clean (`docs/10`, `docs/11`) |
| Dataset, ScienceWorld labelling | Not started |
| Extraction, probes | Not started |
| Stated knowledge, agent loop, evaluation | Not started |
| Results | None |

## Reproducibility

The planned procedure is in [`docs/07_REPRODUCIBILITY.md`](docs/07_REPRODUCIBILITY.md). In short:

- config-driven runs;
- a manifest per run (git commit, dataset/split hashes, model revision, lock file, seeds);
- greedy decoding;
- all prompts and outputs saved;
- exact versions in lock files.

The command table for reproducing every table and figure will be filled in, and tested on a clean checkout, as the implementation lands.

Setup *(planned, not yet tested)*:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,data,probes]"
pytest
```
