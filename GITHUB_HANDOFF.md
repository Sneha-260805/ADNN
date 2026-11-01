# GitHub Handoff

How Member 1 publishes the repository and shares the dataset, and how Members 2 and 3 join.
**Nothing has been pushed yet.** The repository has no remote, and the `gh` CLI is not
installed, so these steps use the GitHub website and plain `git`.

## 1. Create a PRIVATE repository (owner: Member 1)

Keep it **private**:
- some docs quote short excerpts of the professor's specification, which may not be
  redistributed;
- the dataset is unpublished.

**Steps:**
1. On github.com, click **New repository**.
2. Choose a name, e.g. `adnn-irreversibility`, and set it to **Private**.
3. **Do not** add a README, `.gitignore` or licence; the repository already has them.

**Invite collaborators.**
1. Open the repository, then **Settings → Collaborators** (on some accounts: *Collaborators
   and teams*).
2. Click **Add people** and enter each teammate's GitHub username.
3. Each teammate accepts the e-mailed invitation.

**Optional.** Under **Settings → Branches**, protect `main` by requiring a pull request and
one approval. On private repositories this may need GitHub Pro, which is free with the
Student Developer Pack.

## 2. Push the current local work (run manually; nothing is pushed automatically)

Current state: `main` contains only the first commit, and all Member 1 work is on
`m1/sandbox-core`.

```bash
cd adnn-irreversibility                      # the local repository
git status                                   # must be clean
git remote add origin https://github.com/<owner>/adnn-irreversibility.git
git push -u origin main
git push -u origin m1/sandbox-core
```

**Then merge the work into `main`.**
1. On GitHub, open a **pull request from `m1/sandbox-core` into `main`**.
2. A teammate reviews it, then you merge it with **"Create a merge commit"**. This gives
   Members 2 and 3 a `main` that contains the sandbox, the loader and the docs.

**Do not use "Squash and merge" or "Rebase and merge" for this PR.** Both rewrite commit
hashes. The frozen manifests and the docs cite commits such as `dab91ff` and `59ad1c5`, and
the generator checks that HEAD descends from the frozen `base_commit`.

**Commit e-mail.** Your commit e-mail is stored in every commit and is visible to everyone
with access. See GitHub → Settings → Emails, *Keep my email address private*, if that matters
to you.

## 3. Branches and pull requests (everyone)

```bash
git clone https://github.com/<owner>/adnn-irreversibility.git
cd adnn-irreversibility
git switch main && git pull
git switch -c m2/feat/hidden-state-extraction     # Member 3: m3/feat/stated-judgment, etc.
# ... work, commit ...
git push -u origin m2/feat/hidden-state-extraction
```

Then open a pull request into `main`; at least one other member reviews it. Naming and review
rules: [CONTRIBUTING.md](CONTRIBUTING.md).

> **Warning for Members 2 and 3.** Never commit to `m1/sandbox-core`, and never branch from
> it after it has been merged. Always branch from an up-to-date `main`. Check with
> `git branch --show-current` before committing.

## 4. What to commit and what to keep out

| Commit | Keep out of git (already in `.gitignore`) |
|---|---|
| `src/`, `tests/`, `scripts/`, `configs/`, `docs/` (including frozen manifests and their `.sha256` sidecars), `README.md`, `pyproject.toml` | `data/*` and `results/*`: datasets, hidden states, run outputs (only the READMEs are tracked) |
| Small, deliberate result files for the paper (`git add -f`, after review) | `.venv/`, caches, `*.npy`/`*.npz`/`*.h5`, model weights (`*.safetensors`, `*.bin`, `*.pt`), `hf_cache/` |
| | `references/*.docx`/`*.pdf`: the professor's specification and papers |
| | `.env`, `*.token`, `hf_token*`, `kaggle.json`, `credentials*.json`, `secrets*.json` |

**Before the first push**, run these checks. Member 1 ran all of them on 2026-11-01: no
secrets, no tracked binaries or documents, no file over 1 MB, no absolute local paths, and
the specification was never committed.

```bash
git ls-files | grep -iE '\.(docx|pdf|zip|tar|gz|bin|safetensors|pt|npy)$'          # expect nothing
git grep -nIiE 'hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|BEGIN (RSA|OPENSSH) PRIVATE|password\s*='   # expect nothing
git log --all --oneline -- 'references/*.docx' 'references/*.pdf'                   # expect nothing
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' | awk '$1=="blob" && $2>1000000'   # expect nothing
```

## 5. Share the dataset separately (not through git)

The verified v1.0 dataset is git-ignored. Member 1 packs it, together with the files the
validator and the generator need, into one small archive of about 200 KB. The archive comes
with a checksum list.

**Member 1, from the repository root, in Git Bash.** These commands were tested; the archive
is written to the folder above the repository:

```bash
FILES=(
  data/production/v1.0/records.jsonl data/production/v1.0/split.json
  data/production/v1.0/tool_sets.json data/production/v1.0/sensitivity_oq21.jsonl
  data/production/v1.0/manifest.json data/production/v1.0/generation_report.json
  results/phase4h/main/h4-burn-chair-water-near.json results/phase4h/main/h4-burn-painting-water-near.json
  results/phase4h/main/h4-connect-battery-wire.json results/phase4h/main/h4-move-cup-to-table.json
  results/phase4h/main/h4-open-fridge.json results/phase4h/comparison.json
  results/phase4h/measurement_audit.json results/phase5a/symmetry_summary.json
  data/scaling_pilot/records.jsonl
)
sha256sum "${FILES[@]}" > ../adnn-v1.0-SHA256SUMS.txt
tar -czf ../adnn-dataset-v1.0.tar.gz "${FILES[@]}"
```

**Sending it.**
- Share both files through a private channel the team already uses, such as the university
  OneDrive or Google Drive restricted to the three members.
- Also post the checksum of `records.jsonl` in the team chat, so the list itself can be
  cross-checked: `b5a7d58f342fbc2ef7c0658a0dd2a9ffc99c95f8153c8aa1d79bcb70620e20dd`.

**Receivers** unpack the archive and check every file ([ENVIRONMENT_SETUP.md §3](ENVIRONMENT_SETUP.md)):

```bash
tar -xzf ../adnn-dataset-v1.0.tar.gz && sha256sum -c ../adnn-v1.0-SHA256SUMS.txt
```

Never commit the archive or its contents.

## 6. Reproducing the dataset from the frozen manifest

**Collaborators normally do not regenerate.** The checksum-verified bundle *is* the dataset.

**To audit it, regeneration needs:**
- the pinned Java/ScienceWorld runtime;
- the full bundle unpacked;
- the regenerated pilot;
- about 6 GB of free RAM.

It must run from a commit that descends from `dab91ff`, with `src/adnn` unchanged since
then.

**Steps and expected checksums:**
- [docs/MEMBER_1_GUIDE.md §8](docs/MEMBER_1_GUIDE.md);
- [docs/34 §2](docs/34_PRODUCTION_DATASET_V1.md).

The generator refuses to run if the manifest, code, configuration or protected inputs differ.
