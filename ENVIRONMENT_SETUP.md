# Environment Setup

**Tested on:**
- Windows 11, with Git Bash and Windows PowerShell 5.1, and Python 3.11.9;
- a fresh clone of branch `m1/sandbox-core` on 2026-11-01.

On Linux or macOS, replace `.venv/Scripts/` with `.venv/bin/`. That route has not been tested
by the team.

> **A git clone does NOT contain:**
> - the dataset (`data/` is git-ignored);
> - the ScienceWorld evidence (`results/` is git-ignored);
> - the Java and ScienceWorld runtime;
> - model weights;
> - the professor's specification.
>
> Absolute paths in Member 1's docs (e.g. `%LOCALAPPDATA%\adnn-sw`) refer to Member 1's
> machine; create your own.

## 1. Clone and branch

```bash
git clone <repo-url> adnn-irreversibility
cd adnn-irreversibility
git switch -c m2/feat/<topic>     # or m3/feat/<topic>; never work on m1/sandbox-core
```

Workflow details: [GITHUB_HANDOFF.md](GITHUB_HANDOFF.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## 2. Python 3.11 and the virtual environment

**Check Python.** `py -V:3.11 --version` (Windows launcher) must show 3.11.x. Otherwise install
Python 3.11 from python.org.

**Git Bash:**

```bash
py -V:3.11 -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"     # editable install + pytest + ruff
```

**PowerShell:**

```powershell
py -V:3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

- **Dependencies.** The core package has no third-party dependencies. All extras are
  declared in `pyproject.toml`; there is no lock file yet.
- **Extras for later work.** `data`, `probes` (numpy, scikit-learn, scipy, matplotlib) and
  `models` (torch, transformers, accelerate) are declared but **not yet tested** by the team.
  Install them when you start that work, e.g. `pip install -e ".[dev,probes]"`, and record
  the versions you get.

## 3. Get the dataset

Ask Member 1 for two files:
- `adnn-dataset-v1.0.tar.gz`;
- `adnn-v1.0-SHA256SUMS.txt`.

Put them in the folder **above** the repository, so they cannot be committed by accident.
Then, from the repository root:

```bash
tar -xzf ../adnn-dataset-v1.0.tar.gz          # Git Bash or PowerShell (Windows has tar built in)
sha256sum -c ../adnn-v1.0-SHA256SUMS.txt      # Git Bash: every line must say OK
```

PowerShell has no `sha256sum`. Use this loop; it must print `mismatches: 0`:

```powershell
$bad = 0; Get-Content ..\adnn-v1.0-SHA256SUMS.txt | ForEach-Object { $h, $p = $_ -split '\s+\*?', 2; if ((Get-FileHash $p -Algorithm SHA256).Hash.ToLower() -ne $h) { "MISMATCH $p"; $bad++ } }; "mismatches: $bad"
```

**What the bundle contains:**
- `data/production/v1.0/`;
- 8 small ScienceWorld evidence files under `results/phase4h/` and `results/phase5a/`, which
  the validator needs;
- `data/scaling_pilot/records.jsonl`, needed only for regeneration.

## 4. Load and validate

```bash
.venv/Scripts/python.exe -c "from adnn.dataset.api import load_dataset; ds = load_dataset('data/production/v1.0'); print(len(ds))"   # 621
.venv/Scripts/python.exe -m adnn.dataset.validation data/production/v1.0    # "ok": true, 1 warning; takes a few minutes
```

- **Expected warning.** The single warning is the irreversible class share (17.7%); it is
  expected.
- **Do not pass `--final`.** It applies the 2,000-record threshold, which v1.0 does not meet.

## 5. Tests and lint

```bash
.venv/Scripts/python.exe -m pytest -q tests/test_package_layout.py tests/test_production_dataset.py   # quick
.venv/Scripts/python.exe -m pytest -q          # full suite, about 2–4 min on CPU
.venv/Scripts/ruff.exe check .
```

On a fresh clone the full suite gives **3 failures** until you regenerate the historical pilot,
which those tests read. Regenerating it is deterministic, with sha256 `f66b98ba…`:

```bash
.venv/Scripts/python.exe -m adnn.dataset.pilot --out data/pilot
```

About 37 ScienceWorld integration tests are **skipped** unless the runtime in §6 is
configured. That is normal.

## 6. Java 21 and the pinned ScienceWorld runtime (Member 1 only; optional for others)

You need this only to regenerate the dataset or to run ScienceWorld tests. Members 2 and 3 do
not need it to use v1.0.

- **Installation.** The exact user-level installation is in
  [docs/17 §2](docs/17_SCIENCEWORLD_REPRODUCIBILITY.md). It sets up:
  - a Temurin JDK 21.0.13+9 zip;
  - an isolated venv with ScienceWorld at commit `e8216d6`.

  All of it goes in `%LOCALAPPDATA%\adnn-sw`, outside the repository, and needs no admin
  rights.
- **Pointing the code at it.** Set two environment variables per command, without changing
  the global PATH:

```bash
SW="$LOCALAPPDATA/adnn-sw"
export ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9"
export ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages"
```

- **PowerShell:**

```powershell
$env:ADNN_SW_JAVA_HOME = "$env:LOCALAPPDATA\adnn-sw\jdk\jdk-21.0.13+9"
$env:ADNN_SW_SITE_PACKAGES = "$env:LOCALAPPDATA\adnn-sw\venv-e8216d6\Lib\site-packages"
```

- **Running tests without ScienceWorld:** `env -u ADNN_SW_SITE_PACKAGES -u ADNN_SW_JAVA_HOME
  .venv/Scripts/python.exe -m pytest -q`.

## 7. GPU and models (Members 2 and 3)

- **Where to run.** A GPU is needed for Qwen2.5-7B-Instruct and Llama-3.1-8B-Instruct.
  Typical choices are a 24 GB-class GPU, or Colab/Kaggle, where 16 GB T4s are borderline.
  Access, gating and memory estimates: [docs/MEMBER_2_GUIDE.md §3](docs/MEMBER_2_GUIDE.md).
- **Hugging Face login.** Llama requires accepting Meta's licence on Hugging Face and an HF
  token. **Never commit tokens**; `.env`, `*.token` and `hf_token*` are git-ignored.
- **Notebooks.** Keep them thin: clone the repo at a pinned commit, `pip install -e`, and
  call package code. `notebooks/` is empty so far.
- **Large files.** Keep model weights and hidden-state arrays outside git. `*.safetensors`,
  `*.npy`, `*.npz` and `results/*` are ignored.

**CPU-only limits.**
- **Works on CPU:** everything from Member 1 (loading, validation, tests, demo) and probe
  *training* on saved hidden states.
- **Needs a GPU:** running 7B–8B models. On a 16 GB laptop, develop with a tiny model or fakes,
  then run the real extraction or generation on a GPU.

## 8. Common problems

| Symptom | Fix |
|---|---|
| `py: no Python 3.11 found` | Install Python 3.11; check with `py -0` |
| `FileNotFoundError: data/production/v1.0/...` | The dataset is not in git. Do §3 |
| Validator: `FileNotFoundError: results\phase4h\main\...json` | The ScienceWorld evidence files are missing. Unpack the full bundle (§3) |
| 3 test failures mentioning `data/pilot/...` | Regenerate the pilot (§5) |
| `DatasetIntegrityError` / hash mismatch on load | The files were changed or are incomplete. Re-copy them and re-run the checksum check |
| Git Bash `tar: Cannot connect to C: resolve failed` | GNU tar treats `C:` as a host. Use relative paths (as in §3) or add `--force-local` |
| `scienceworld is not importable` (tests skipped) | Expected without §6 |
| Generator says `src/adnn differs from base_commit` | Regeneration only runs on unchanged code from the frozen commit. Use a checkout of that commit |
| Out-of-memory during regeneration | It needs about 6 GB of free RAM. Close other apps; do not disable safety checks |

## 9. Regenerating the data (only if necessary)

**Do not regenerate to "get" the dataset.** Use the verified bundle. Regeneration is for
audits only.

**Requirements:**
- §6 configured;
- the full bundle unpacked;
- the pilot regenerated (§5);
- about 6 GB of free RAM.

**Command and checks:** see [docs/MEMBER_1_GUIDE.md §8](docs/MEMBER_1_GUIDE.md). The expected
checksums are in [docs/34 §2](docs/34_PRODUCTION_DATASET_V1.md).
