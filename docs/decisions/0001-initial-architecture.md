# ADR-0001: Initial repository architecture

- **Status:** Proposed. The team accepts it once M2 and M3 have reviewed it.
- **Date:** 2026-10-30
- **Deciders:** Sneha (M1); M2 and M3 to confirm.

## Context

Three MSc students must deliver, within one semester, a measurement study with three interlocking measurements (probe, stated answer, behaviour) on two models and two testbeds. The spec requires:

- exact library versions, fixed seeds, saved prompts and outputs;
- a README that reproduces every table and figure;
- scenario-level splits;
- no paid APIs and no real side effects.

Development happens on Windows with Claude Code. GPU work happens on time-limited Colab/Kaggle sessions (or course GPUs; OQ-01). Members work largely in parallel, so the interfaces between them are the main integration risk.

## Decision

1. **A single installable Python package** `adnn` (src layout, `pyproject.toml`, Python 3.11) with subpackages per responsibility: `sandbox`, `dataset`, `scienceworld`, `models`, `probes`, `behaviour`, `evaluation`, `experiments`. pytest + ruff + type hints.
2. **Stage separation by hardware.** GPU stages (extraction, stated answers, agent runs) only produce raw artifacts. Everything else (labelling, probes, statistics, figures) runs on CPU from saved artifacts. Each model runs once per example for probing (spec §6 Step 2).
3. **Explicit contracts (C1–C8)** between members, documented in `03_SYSTEM_ARCHITECTURE.md` §4. Changing one requires review by every consumer.
4. **One shared prompt builder** (`adnn.dataset.prompting`). The probe reads hidden states in the same context the agent acts in, and stated-knowledge prompts reuse the same state rendering.
5. **JSONL** as the interchange format for examples, tasks, logs and predictions. **NumPy float16 shards + index** for hidden states.
6. **A `data/` directory** for inputs (dataset, splits, tasks, annotations), separate from `results/` for outputs. This was not in the initial directory list; it is added so that inputs and outputs are never mixed.
7. **Config-driven runs with manifests.** Every run writes its config, git commit, dataset/split hashes, model revision, lock file and seeds.
8. **Large artifacts outside git**, referenced by SHA-256.
9. **Docs-first.** The requirements traceability matrix and the protocol precede code. The analysis plan is frozen before any test-set evaluation.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Notebook-centric workflow (all logic in Colab notebooks) | Hard to review, test, diff and reproduce; hidden state; conflicts with REQ-DEL-02 |
| Separate repositories per member | Contract drift; harder integration and single-README reproduction |
| Flat scripts without a package | No shared, tested code between stages; duplicated prompt logic would break the probe/behaviour comparison |
| Store hidden states in HDF5 / safetensors | Viable. NumPy shards were chosen for simplicity and resumability, and can be revisited (low switching cost) |
| Store hidden states in git (LFS) | Size and quota; OneDrive sync issues |
| Use an existing agent framework | The spec needs a *simple* one-tool-call-per-step loop with full logging; frameworks add hidden prompting |
| LLM-as-judge for caution detection | Introduces model dependence and possibly paid APIs; deterministic rules are reproducible |

## Trade-offs

- More upfront structure (contracts, manifests) costs time in Phase 1–2, but saves integration time later and makes the report reproducible.
- CPU/GPU stage separation means storing ~0.5 GB of hidden states per model and position. This is acceptable compared with re-running models.
- A single shared prompt builder couples M2 and M3 to M1's code. This is mitigated by contract review and a pilot dataset released early.
- Python 3.11 is not the newest interpreter (the local machine has 3.14). It is chosen for compatibility with the ML stack and cloud runtimes, which still need verification at lock time.

## Consequences

- M1 must deliver D1/D2/D3 early (Phase 2), or M2/M3 are blocked.
- Every result is traceable but needs manifest discipline. Results without manifests are not reported.
- Future changes to any of these points require a new ADR (`docs/decisions/NNNN-title.md`) that supersedes this one.
