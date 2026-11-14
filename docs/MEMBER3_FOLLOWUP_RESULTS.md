# Member 3 follow-up results

The exploratory RQ2 recovery prompt was tested on the same 425 frozen examples
as each model's original run. The development runs used 142 training examples
per condition. Development, test, smoke and pilot artifacts retain their run
names under `results/member3_followups/`.

| Model | Test condition | Accuracy | Balanced accuracy | Macro-F1 |
|---|---|---:|---:|---:|
| Qwen | Original | 26.35% | 28.49% | 0.221 |
| Qwen | Recovery | 21.65% | 24.78% | 0.209 |
| Llama | Original | 48.00% | 33.33% | 0.216 |
| Llama | Recovery | 35.06% | 32.68% | 0.326 |

The RQ1 comparison joins supplied probe predictions to each RQ2 condition by
example ID and verifies ground-truth label agreement. Probe accuracy is
93.65% for Qwen and 94.12% for Llama. Probe-to-answer agreement was 27.29%
original and 22.35% with recovery for Qwen, and 48.47% original and 36.24%
with recovery for Llama. The CSV includes Cohen's kappa. Historical RQ1
checkpoint equivalence remains unverified. RQ3 uses a separate task set,
so comparisons with RQ1 are at the level of overall patterns.

## Llama RQ3 formatting diagnostic

The original strict parser rejected 819 finish responses missing the required
`args` field. The format follow-up explicitly showed
`{"tool": "finish", "args": {}}`. It used the same 120 task IDs, task manifest,
checkpoint, seed, precision, package versions, decoding limit and step limit.
The smoke test and pilot finished successfully on all 2 and 20 versions.

| Full-run outcome | Original | Format guidance |
|---|---:|---:|
| Valid finishes | 0/120 | 120/120 |
| Parsing failures | 819 | 0 |
| Step-limit terminations | 120/120 | 0/120 |
| Successful final states | 87/120 | 117/120 |
| Caution on reversible versions | 30/60 | 30/60 |
| Caution on irreversible versions | 30/60 | 30/60 |
| Irreversible actions on irreversible versions | 60/60 | 60/60 |

On matching IDs, 31 failures became successes and one success became a failure.
The binary caution and irreversible-action flags matched on all 120 IDs.

The archive manifest records the five input ZIP checksums and both source
bundle checksums. Every source hash recorded by the follow-up runs matches
the original run package with the follow-up update applied. The Git commit
records the reviewed files after inference. Use the saved run configurations
and source bundles to identify the execution source.
