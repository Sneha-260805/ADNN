# scripts/

Command-line entry points. **None exist yet.** Each script will correspond to one step in
`docs/04_EXPERIMENTAL_PROTOCOL.md` and take `--config configs/<file>.yaml`.

Available now as module entry points: `python -m adnn.dataset.pilot --out data/pilot` and `python -m adnn.dataset.validation data/pilot` (docs/13, docs/14).

Planned (names provisional): `build_sandbox_dataset.py`, `label_scienceworld.py`,
`make_splits.py`, `validate_dataset.py`, `extract_hidden_states.py`, `train_probes.py`,
`ask_stated.py`, `run_agent.py`, `analyse.py`, `make_figures.py`.
