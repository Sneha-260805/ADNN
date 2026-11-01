# Do AI Agents Know Which Actions Cannot Be Undone?

This is the repository of a three-person undergraduate research project for the ADNN course
(Project Option 1). It is a measurement study of open-weight LLM agents, and asks whether
they:
1. know internally,
2. say correctly, and
3. act as if they know

that an action cannot be undone.

> **Status (2026-11-01).**
> - **Member 1 (dataset, sandbox, ScienceWorld labels):** done. A validated *preliminary*
>   dataset, v1.0, exists.
> - **Member 2 (probes) and Member 3 (judgment and behaviour):** not started. No model has
>   been run and no result exists.
>
> Nothing in this repository is a research finding yet.

## Why this matters

LLM agents now edit files, send emails and move money. Some actions can be undone: a file
moved to a recycle bin, or a payment that can still be cancelled. Others cannot: a file
deleted with no backup, or a final transfer. A careful human slows down before an
irreversible step.

We want to know whether models represent this difference, can state it, and act on it. A
model that *says* "deleting is permanent" but deletes anyway shows what we call
**irreversibility blindness**.

## Three research questions

| | Question | Owner |
|---|---|---|
| **Knowledge** (RQ1) | Can reversibility be read from the model's hidden states with a simple linear probe, and at which layers? | Member 2 |
| **Judgment** (RQ2) | When asked directly, does the model classify an action as reversible, partially reversible or irreversible correctly? Does it agree with the probe? | Member 3 |
| **Behaviour** (RQ3) | When acting as an agent, does the model avoid irreversible actions, or check first, when a safer path exists? | Member 3 |

- **Models:** Qwen2.5-7B-Instruct (main) and Llama-3.1-8B-Instruct (second family).
- **Labels:** reversible, partially reversible, or irreversible within h = 1, 2 or 3 recovery
  steps; h = 3 is primary.

## Team

| Member | Responsibility | Instructions |
|---|---|---|
| Member 1 (Sneha) | Sandbox, oracle labels, ScienceWorld, dataset, validation, repository integration | [`docs/MEMBER_1_GUIDE.md`](docs/MEMBER_1_GUIDE.md) |
| Member 2 | Hidden-state extraction and linear probes (RQ1) | [`docs/MEMBER_2_GUIDE.md`](docs/MEMBER_2_GUIDE.md) |
| Member 3 | Verbal judgment, agent behaviour, statistics (RQ2, RQ3) | [`docs/MEMBER_3_GUIDE.md`](docs/MEMBER_3_GUIDE.md) |

## Architecture

```
Tool sandbox + ScienceWorld ──► oracle labels ──► dataset v1.0 + scenario split + prompts   (M1, CPU)
                                                         │
                     ┌───────────────────────────────────┼─────────────────────────┐
                     ▼                                   ▼                         ▼
          hidden states + linear probes        verbal judgment prompts      agent tasks in the sandbox
          (M2, GPU then CPU)                   (M3, GPU)                    (M3, GPU; not built yet)
                     └──────────────► compare knowledge / judgment / behaviour (M3) ◄──┘
```

| Path | Content |
|---|---|
| `src/adnn/sandbox/` | Deterministic simulated tool world: files, email, payments, share links; reversibility oracle |
| `src/adnn/dataset/` | Prompt builders, dataset generator, validator, loader (`api.py`) |
| `src/adnn/scienceworld/` | ScienceWorld adapter, label evidence, exporter |
| `src/adnn/models`, `probes`, `behaviour`, `evaluation`, `experiments` | **Empty placeholders** for Members 2 and 3 |
| `scripts/dataset/`, `scripts/scienceworld/` | Command-line scripts for each Member 1 phase |
| `tests/` | pytest suite; runs on CPU without models |
| `docs/` | Design docs (`01`–`09`), phase reports (`10`–`36`), decision records (`decisions/`), frozen manifests (`preregistration/`) |
| `data/`, `results/` | Git-ignored: generated data and outputs; only the READMEs are tracked |
| `references/` | Reading list. The professor's specification is kept **locally only** and never committed |

## Quick start

These commands were tested on a clean clone with Windows and Git Bash. Full instructions,
including PowerShell, Java and GPUs, are in [`ENVIRONMENT_SETUP.md`](ENVIRONMENT_SETUP.md).

```bash
git clone <repo-url> adnn-irreversibility && cd adnn-irreversibility
py -V:3.11 -m venv .venv                     # Python 3.11 (see .python-version)
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m adnn.demo        # prints a small sandbox demo
.venv/Scripts/python.exe -m pytest -q tests/test_package_layout.py tests/test_production_dataset.py
```

**The dataset is not in git.** Get the v1.0 bundle from Member 1 and verify its SHA-256
checksums ([`GITHUB_HANDOFF.md`](GITHUB_HANDOFF.md) §5). Then load it:

```python
from adnn.dataset.api import load_dataset
ds = load_dataset("data/production/v1.0")    # 621 records; checks file hashes
train, test = list(ds.iter_split("train")), list(ds.iter_split("test"))   # 489 / 132
```

## Dataset v1.0 in one paragraph

- **Size and classes.** 621 gold records: 616 from the sandbox and 5 from ScienceWorld.
  Reversible 279, partially reversible 232, irreversible 110.
- **Minimal pairs.** 36.1% of records are in minimal pairs: the same action in two states
  that differ in one condition, with different labels.
- **Split.** A 21.3% test set, split by scenario group.

| Professor target | v1.0 |
|---|---|
| ≥ 2,000 records from both testbeds | **Not met:** 621, only 5 from ScienceWorld |
| Roughly balanced classes | **Not met:** irreversible 17.7%, so use balanced accuracy |
| ≥ 30% minimal pairs | Met |
| 20% scenario-level test set | Met |

All labels come from the oracle; **no human annotation has been done**.

Details:
- [data card (docs/35)](docs/35_DATA_CARD_PRODUCTION_V1.md);
- [generation report (docs/34)](docs/34_PRODUCTION_DATASET_V1.md);
- [loader guide (docs/36)](docs/36_MEMBER_2_LOADER_V1.md).

## Versioning and reproducibility

- **Frozen before generation.** Every dataset is generated from a frozen manifest committed
  before generation. For v1.0 this is
  `docs/preregistration/production_manifest_amend1.json`, sha256 `729bcd7c…`.
- **Generator safeguards.** The generator refuses to run if code, configuration or protected
  inputs have changed.
- **Checksums.** Files are verified by SHA-256: `records.jsonl` is `b5a7d58f…`.
- **Prompt hashes.** The loader re-checks every prompt hash, so a changed prompt builder is
  caught.
- **Design changes** are recorded in `docs/decisions/` (ADR-0006 to ADR-0009) before they take
  effect.
- **Planned, not built.** Run manifests and lock files for model experiments are planned
  (`docs/07_REPRODUCIBILITY.md`) but not built.

## Current limitations

- The dataset is below the professor's size target (621 of 2,000) and is imbalanced.
- ScienceWorld contributes only 5 records, with 1 in test.
- The `compact` state rendering appears only in the test set, which confounds style with the
  split.
- The definition of "partially reversible" was adopted by the team. The professor has not
  confirmed it (open question OQ-21).
- Members 2 and 3 have no code yet. The agent-behaviour benchmark does not exist yet.

## Contributing

- **Workflow.** Use a private GitHub repository, one feature branch per task, and pull
  requests reviewed by another member. Never commit data, model weights, tokens or the
  professor's document.
- **Guides:**
  - [`GITHUB_HANDOFF.md`](GITHUB_HANDOFF.md): publishing and transferring the dataset;
  - [`CONTRIBUTING.md`](CONTRIBUTING.md): branch names, reviews, coding standards, contribution
    log.
