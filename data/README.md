# data/

Generated datasets. **Everything here except this README is git-ignored.** A git clone
therefore contains no data. Get the verified v1.0 bundle from Member 1 and check its
checksums ([GITHUB_HANDOFF.md §5](../GITHUB_HANDOFF.md)).

| Path | Content | How to get it |
|---|---|---|
| `production/v1.0/` | **Production dataset v1.0**: 621 gold records, split, tool sets, manifest, OQ-21 sensitivity file (docs/34, docs/35) | Bundle from Member 1 (checksum-verified); regeneration only for audits |
| `pilot/` | Historical 210-record pilot (development only; never report results on it) | `python -m adnn.dataset.pilot --out data/pilot` (deterministic) |
| `scaling_pilot/` | Phase 5B scaling pilot; a protected input of the production generator | Bundle from Member 1 |
| `production/superseded-run1-invalid/` | Invalid first production run (ADR-0009 Amendment 1); Member 1's machine only | Do not use |
| `tasks/` | RQ3 paired agent tasks | **Not created yet** (Member 3 with Member 1) |

**Licence note.** Derived ScienceWorld content must respect the upstream licence. Check it
before any public release (REQ-ENV-09, OQ-15).
