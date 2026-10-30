# notebooks/

Thin Colab/Kaggle driver notebooks. **None exist yet.**

Rules (see `docs/07_REPRODUCIBILITY.md`):
- Notebooks only install the repository at a pinned git commit and call scripts in `scripts/`
  or entry points in `adnn.experiments`. No research logic lives in notebooks.
- Figure notebooks read saved result files only; they never run a model.
- Clear outputs containing tokens or personal paths before committing.
