# Member 3 RQ2 and RQ3 handoff

This branch contains Member 3's experiment implementation, automated tests,
original Qwen and Llama results, comparison tables and a report draft.
It builds on Member 1's m1/sw-transfer handoff. No frozen tasks, production
dataset records, prompt builders or sandbox implementation were changed.

## Files to review

- `src/adnn/behaviour/`: model adapter, stated-label parsing, agent loop and metrics.
- `scripts/behaviour/`: experiment runner, summaries and uploaded-result analysis.
- `tests/test_member3_behaviour.py`: execution and statistical checks.
- `results/rq2/{qwen,llama}/test/`: original 425-answer test runs per model.
- `results/rq3/{qwen,llama}/{pilot,full}/`: separate pilot and 120-version full runs.
- `results/member3_reference_predictions/`: supplied Member 2 three-class predictions.
- `results/member3_verified_analysis/`: regenerated CSVs, metrics, figure and checksums.
- `docs/MEMBER3_RESULTS_DRAFT.md`: methodology, results, limitations and contribution draft.
- `docs/preregistration/member3_behaviour_v1.md`: operational scoring specification.

Results retain their original configuration files. Git metadata in uploaded-bundle
runs is unavailable; recorded source-file hashes identify their execution source.
The later Git commit does not retroactively make these clean-commit experiments.
Historical RQ1 checkpoint equivalence remains unverified. Llama's recorded new-run
revision matches the value in its supplied RQ1 metadata, but the earlier loading
call was unpinned.

## Reproduce summaries

Install with `python -m pip install -e ".[models,probes,dev]"`.
From the repository root, for example:

```text
python scripts/behaviour/summarize.py results/rq2/qwen/test
python scripts/behaviour/summarize.py results/rq3/qwen/full
python scripts/behaviour/summarize.py results/rq2/llama/test
python scripts/behaviour/summarize.py results/rq3/llama/full
```

The production dataset is excluded from this branch. Obtain the frozen v2.0
bundle from Member 1 and verify it using the existing loader. Regenerating the
expanded uploaded-result analysis currently requires the backup ZIPs named in
`raw_archive_manifest.json`, the supplied Llama prediction file, and the Member 2
remote branch. Example:

```text
python scripts/behaviour/analyze_uploaded.py --downloads PATH_TO_BACKUPS
```

The reference predictions are included here for review and record-ID alignment.
Original backups remain preserved outside Git; their checksums are recorded.
No model weights, hidden-state arrays, access tokens or dataset bundles are included.

## Validation and outstanding work

Both complete 120-version traces were replayed and matched recorded outcomes.
Both RQ2 runs contain exactly the frozen 425 test IDs with matching labels and
stated prompts. Never pool pilots with full runs. Llama's 819 malformed finish
calls are preserved and discussed; they are not silently corrected.

The action-text baseline and expanded analyses were added after model runs and
are explicitly post hoc. The document labelled preregistration is a specification
prepared locally earlier in the workflow; it was not committed before inference,
so this branch does not establish independently timestamped preregistration.

Remaining team work: review the analysis and contribution paragraph, integrate
the results into the paper and presentation, and obtain frozen-probe predictions
on the separate RQ3 critical-action prompts for probe-versus-behaviour comparison.
No such task-specific probe predictions are claimed here.
