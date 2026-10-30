# configs/

Experiment configuration. Every experiment runner will read a YAML config and copy it into
its run directory, so each result can be traced to the exact settings that produced it.

- `defaults.yaml` — **template only, not consumed by code yet.** Each value is tagged
  `[SPEC]` (professor's requirement), `[ENG]` (our choice) or `[OPEN]` (unresolved).

Rule: never change a `[SPEC]` value without professor approval; changing an `[ENG]` value
after the analysis plan is frozen must be recorded in `docs/decisions/`.
