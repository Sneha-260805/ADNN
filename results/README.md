# results/

Experiment outputs. **Empty: no experiment has been run.** Never place hand-made or
placeholder numbers here.

Layout: `results/<experiment>/<model_slug>/<run_id>/` containing `config.yaml`,
`manifest.json`, `metrics.json`, `predictions.jsonl` and logs. Hidden-state arrays are
stored outside git and referenced by SHA-256 in `manifest.json`.
Schema: `docs/04_EXPERIMENTAL_PROTOCOL.md` §8.
