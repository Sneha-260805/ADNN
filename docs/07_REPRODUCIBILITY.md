# 07 — Reproducibility

Status: **no environment has been built and no command below has been tested.** Commands marked *(planned)* will be filled in and verified when the corresponding code exists. Do not copy them into the report until they have been run.

## 1. Local Windows setup (development)

Facts observed on Sneha's machine on 2026-10-30:

- the system Python is 3.14;
- pytest, ruff and Java are **not installed**.

The project targets **Python 3.11** (ENG-01). A 3.11 interpreter must be installed (e.g. from python.org, or `py install 3.11` with the Python install manager, if available).

*(planned, untested)*

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,data,probes]"
pytest
ruff check .
```

Notes:

- The heavy GPU dependencies (`.[models]`) are not needed locally. Model work runs on Colab/Kaggle.
- **ScienceWorld** needs Java ≥ 1.8 (spec §4.1). We have not verified that ScienceWorld runs on native Windows. Recommendation: run ScienceWorld labelling under **WSL2 (Ubuntu)** or on a Colab/Kaggle CPU runtime. Record the Java version in the manifest.
- Line endings are normalised to LF by `.gitattributes`.
- The repository sits inside OneDrive. Large artifacts (hidden states) must not be written into the repo folder, or OneDrive will sync gigabytes. Use a path outside OneDrive or `results/**/hidden_states/` (git-ignored) with OneDrive sync excluded.

## 2. Colab and Kaggle execution

Detailed in `03_SYSTEM_ARCHITECTURE.md` §5. Procedure *(planned)*:

1. Start a GPU session. Record the GPU type (`nvidia-smi`) into the manifest automatically.
2. `git clone` the repo and `git checkout <commit>`. Results are only valid from a clean, committed state (`git_dirty: false`).
3. `pip install -e ".[models]"`, then `pip freeze > requirements/<platform>-<date>.lock.txt` on the first run of each environment. Commit the lock file.
4. Set the HF token from platform secrets: Colab "Secrets" or Kaggle "Add-ons → Secrets". Never put it in a notebook cell, config or commit.
5. Mount persistent storage (Google Drive, or Kaggle output/Datasets) for hidden states and logs.
6. Run one script with one config. Scripts are resumable (shards / per-run JSONL).
7. Copy small result files back into `results/` via a PR. Large files stay external with their SHA-256 recorded.

Platform quotas, session limits and available GPU types change over time. Check the current limits on each platform rather than relying on numbers written here.

**Compute decision pending (OQ-01).** The spec assumes course GPUs with ~50 GB. Whether we use those or Colab/Kaggle determines dtype and memory strategy. Whatever is chosen, the same model must run with the same dtype and library versions for all its reported results.

## 3. Configuration and environment management

- All run parameters live in YAML under `configs/` (template: `configs/defaults.yaml`). Every value is tagged `[SPEC]`/`[ENG]`/`[OPEN]`.
- A run copies its resolved config into its run directory.
- **CLI overrides are not allowed for reported runs.** Create a config file instead, so that every reported number traces back to a committed file.
- Model identity is pinned by the HF **revision hash**, not just the model name, because model repos can be updated.

## 4. Dependency pinning

- `pyproject.toml` declares dependency *names* (ranges only); see the comment there.
- Exact versions are captured per execution environment as lock files: `requirements/local-cpu.lock.txt`, `requirements/kaggle-gpu.lock.txt`, `requirements/colab-gpu.lock.txt`. **None exist yet.**
- The spec requires "a requirements file with exact versions" (REQ-SW-02, REQ-DEL-02). The final submission includes the lock files actually used for reported results, referenced from each manifest.
- Library APIs (transformers chat templates, hidden-state outputs, ScienceWorld API) are checked against the documentation of the *pinned* version (spec §5).

## 5. Deterministic seeds

Seed values are in `04_EXPERIMENTAL_PROTOCOL.md` §7. Each run will call a single `set_seed(seed)` that sets Python `random`, NumPy and PyTorch (CPU + CUDA) seeds, plus deterministic settings where available.

Caveats:

- greedy decoding removes sampling randomness, but GPU kernels can still be non-deterministic across hardware and library versions;
- we log state hashes per step and re-run a subset to measure the flip rate (OQ-14);
- CPU-side work (splits, probes, bootstrap) must be bit-for-bit reproducible.

## 6. Data and result provenance

Every result file can be traced to:

- the git commit and dirty flag;
- the config;
- the dataset version + SHA-256 and the split file SHA-256;
- the model id + HF revision + dtype;
- the lock file;
- the platform and GPU;
- the seeds;
- start/end time and status.

All of these are in `manifest.json` (`04` §8). `results/register.csv` lists every run ever started, including failed ones (REQ-STAT-04). Figures are produced only by scripts from saved results. Each figure has a JSON file with the exact numbers plotted.

## 7. Model licences and access

| Model | Licence / access (per spec §5, checked by the professor Sept 2026) | Our action |
|---|---|---|
| Qwen2.5-7B-Instruct | Apache-2.0, not gated | Re-check the model card before release |
| Llama-3.1-8B-Instruct | Llama 3.1 Community License; **gated**; Acceptable Use Policy applies | Each member applies on HF in week 1; record approval date here: — |
| Qwen2.5-14B-Instruct (optional) | Apache-2.0 per a secondary listing; **confirm on model card** | Only if the size ablation is run |

Datasets and environments:

- ScienceWorld: check the LICENSE file in the repo; the README does not state it.
- ToolEmu: Apache-2.0.
- ByteSized32-State-Prediction: no licence file shown; research use only; ask the authors before redistributing.

All must be re-verified before any data or code release (REQ-ENV-09).

No paid inference APIs are used for any reported result (REQ-SAFE-02).

## 8. Commands to reproduce tables and figures

*(To be filled in when implementation exists. Each line must be tested on a clean checkout before submission.)*

| Output | Command | Input | Status |
|---|---|---|---|
| Dataset v1.0 | `python scripts/build_sandbox_dataset.py --config …` / `scripts/label_scienceworld.py` | — | not implemented |
| Splits | `python scripts/make_splits.py --config …` | dataset | not implemented |
| Hidden states | `python scripts/extract_hidden_states.py --config …` | dataset | not implemented |
| F1, T1 | `python scripts/train_probes.py …` → `scripts/make_figures.py F1` | hidden states | not implemented |
| F2 | `scripts/ask_stated.py`, `scripts/analyse.py` | dataset, probes | not implemented |
| F3 | `scripts/run_agent.py`, `scripts/analyse.py` | tasks | not implemented |
