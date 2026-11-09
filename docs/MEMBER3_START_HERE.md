# Your Member 3 work

This is the original setup guide. Qwen and Llama experiments have since finished.
See MEMBER3_GITHUB_HANDOFF.md and MEMBER3_RESULTS_DRAFT.md for current status.

Your question is whether AI models understand which actions can be undone and whether
that understanding changes their behaviour. Member 1 supplies the simulated environment
and labelled tasks. Member 2 studies information inside the models. You measure what
the models say and do, then compare with Member 2's predictions.

## What RQ2 means

Show a model a state and a proposed action. Ask whether it is reversible, partially
reversible, or irreversible within three further tool calls. For example, deleting a
file with the recycle bin enabled may be reversible; deleting it without recovery may
be irreversible. Use existing labels as the answer key, never inside the model prompt.
Evaluate on the frozen test split. Save the prompt, original answer and parsed label.

## What RQ3 means

Let the model complete a task by choosing one simulated tool action at a time. Compare
two versions of the same task that differ in reversibility. Observe whether it checks
the relevant file, asks a question, makes a backup, abstains, or takes the critical action.
Measure task completion separately. A model that refuses everything may be cautious
but unhelpful. A backup can let it complete a task without an irreversible action.

There are 60 pairs and 120 versions. Running both models means 240 final agent runs,
plus separate pilot runs and initial critical-action judgment calls. Fifteen replies
per agent run gives an upper bound of 3600 final agent generations, excluding judgments.
Do not assume the run will fit one free GPU session; benchmark the pilot first.

## Implemented in this workspace

- src/adnn/behaviour/runner.py: strict existing parser, 15-step loop, executed-event
  scoring, pre-action oracle assessment and final-state task success.
- src/adnn/behaviour/models.py: local Hugging Face inference, greedy decoding, one model.
- src/adnn/behaviour/judgment.py: stated-answer parsing and classification metrics.
- src/adnn/behaviour/analysis.py: pair-level K, A, gap, rates, bootstrap and McNemar.
- scripts/behaviour/run.py: smoke, pilot, full and frozen-test RQ2 execution.
- scripts/behaviour/summarize.py: regenerate JSON metrics and PNG figures from logs.
- tests/test_member3_behaviour.py: scripted execution and calculation checks.

The scripts are an initial implementation, not completed research results. They have
not yet been validated with Qwen or Llama. Frozen datasets and environment code are unchanged.
See preregistration/member3_behaviour_v1.md for the operational scoring definitions.

## What to obtain from your teammates

1. Member 2: exact Qwen and Llama model IDs, immutable revision hashes, tokenizer
   settings, dtype or quantisation, package versions, and the production dataset version.
   The supplied adapter currently uses float16 without quantisation. Match this with
   Member 2 before using it for final inference; do not silently change settings.
2. Member 1 or Member 2: the frozen production dataset folder including manifest,
   dataset JSONL, tool sets and frozen split. Only RQ3 tasks are present locally.
3. Member 2: held-out probe predictions with example_id, selected layer and predictions
   for the same RQ2 records; and probe predictions on RQ3 critical-action prompts.
4. Confirm Llama access is approved for the Hugging Face account used in Colab or Kaggle.
   Store access tokens in the platform's secret manager, never in committed notebooks.

## Run in Colab or Kaggle

Use a GPU runtime. Mount Google Drive in Colab or use persistent Kaggle output storage.
Save results in persistent storage after every session. Clone your own branch after
the local changes have been committed and pushed, or upload this workspace as a zip.
The current local changes are not automatically present on GitHub.

```python
%pip install -e ".[models,probes,dev]"
```

Run the following from the repository root. Replace MODEL and REVISION with confirmed
values. OUTPUT must be a fresh directory. In notebook cells prefix commands with !.

```text
python scripts/behaviour/run.py --mode smoke --model MODEL --revision REVISION --output results/rq3/model-smoke
python scripts/behaviour/run.py --mode pilot --model MODEL --revision REVISION --output results/rq3/model-pilot
python scripts/behaviour/summarize.py results/rq3/model-pilot
python scripts/behaviour/run.py --mode full --model MODEL --revision REVISION --output results/rq3/model-full
python scripts/behaviour/summarize.py results/rq3/model-full
python scripts/behaviour/run.py --mode rq2 --dataset data/production/VERSION --model MODEL --revision REVISION --output results/rq2/model-test
python scripts/behaviour/summarize.py results/rq2/model-test
```

Run sequentially, first Qwen then Llama. Restart the runtime between models to release
GPU memory. Smoke should contain two versions, pilot 20, full 120 for each model.
Inspect errors and full traces before proceeding beyond the pilot. If no shortcuts
are taken, consult Member 1; never modify the frozen tasks directly.

Configuration records package versions, model revision, decoding settings, seed,
dataset manifest hash, Git commit and whether the working tree had changes. Commit
the reviewed implementation before final runs so the source can be recovered exactly.
Outputs refuse an existing directory to prevent accidental overwriting. There is no
resume support yet; preserve interrupted outputs and clearly label any fresh rerun.

## Still needed before final submission

- Real smoke, pilot, full and RQ2 runs on both models, with raw logs preserved.
- RQ2 grouped bootstrap intervals by scenario; majority and constant baselines;
  action-text lexical baseline trained on train only; metrics by environment,
  rendering and matched minimal-pair subset. Current RQ2 summaries are aggregate only.
- Join Member 2's predictions by example_id; calculate agreement and Cohen kappa.
- Report mechanism-specific RQ3 results, failed runs and a comparison of the two models.
  Current summaries calculate aggregate metrics for one run directory at a time.
- Add CSV report tables and a short methodology and results section using observed
  numbers. Do not fill in results before experiments finish.
- Verify the data freeze, pin the GPU environment, update the contribution log with
  work you have reviewed, then share code and logs with your team.

The project brief prohibits paid API results and real-world irreversible actions.
All tools here operate on simulated files, email and payments inside the sandbox.
No model results or report findings have been invented.
