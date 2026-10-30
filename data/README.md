# data/

Labelled data produced by this project. **Empty at setup stage — no data has been generated yet.**

Planned layout (see `docs/05_DATASET_SPECIFICATION.md`):

| Path | Content | In git? |
|---|---|---|
| `data/raw/` | Raw ScienceWorld trajectories, BFS logs, ToolEmu case copies | No (regenerable / licence-restricted) |
| `data/interim/` | Unvalidated generated examples | No |
| `data/processed/reversibility_v<MAJOR.MINOR>.jsonl` | Released labelled dataset | Only frozen releases, added with `git add -f` at the release tag |
| `data/processed/DATA_CARD.md` | Data card (REQ-DEL-03) | Frozen versions only (`git add -f`) |
| `data/splits/split_seed{0,1,2}.json` | Frozen scenario-level splits | Frozen versions only (`git add -f`) |
| `data/tasks/agent_tasks_v<MAJOR.MINOR>.jsonl` | RQ3 paired agent tasks | Frozen versions only (`git add -f`) |
| `data/annotation/` | Blind human labels for the 100-pair agreement study | Frozen versions only (`git add -f`) |

Everything under `data/` except this README is git-ignored by default (see `.gitignore`).

Licence note: derived ScienceWorld and ToolEmu content must respect the upstream licences;
verify before release (REQ-ENV-09, OQ-15).
