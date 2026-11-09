# Member 3 judgment and behaviour results

## Scope and method

We evaluated Qwen2.5 7B Instruct and Llama 3.1 8B Instruct using float16 inference,
greedy decoding and seed 42. The recorded revisions were
`a09a35458c702b33eeacc393d103063234e8bc28` for Qwen and
`0e9e39f249a16976918f6564b8830bc894c89659` for Llama. The runs recorded
PyTorch 2.11.0+cu130, Transformers 5.20.2 and Accelerate 1.15.0. Exact matching
to Member 2's historical RQ1 checkpoints remains unverified. Llama's revision
matches the revision recorded in its supplied RQ1 extraction metadata, but the
historical loading call did not explicitly pin that revision.

For RQ2 we used the frozen v2.0 scenario-grouped test split of 425 records,
containing 68 reversible, 204 partially reversible and 153 irreversible examples.
The existing stated prompt asked whether the proposed action could be undone in
at most three further tool calls. Ground truth was used for evaluation only.
The first answer line was parsed according to the frozen label contract.

For RQ3 each model ran 60 matched task pairs, or 120 versions, with four task
mechanisms and a maximum of 15 model replies per run. Each pair differed only in
a reversibility-related state setting. The 10-pair pilot was kept separate.
Successful executed tool calls before the first successful critical action
determined caution. Completion was evaluated from the final sandbox state.
Parse failures consumed steps and did not advance sandbox time.

## Results

| Measure | Qwen | Llama |
|---|---:|---:|
| RQ2 accuracy | 26.35 percent | 48.00 percent |
| RQ2 balanced accuracy | 28.49 percent | 33.33 percent |
| RQ2 macro F1 | 0.2209 | 0.2162 |
| RQ2 unparseable answers | 0 | 0 |
| RQ3 successful final states | 119 of 120 | 87 of 120 |
| Caution on irreversible versions | 15 of 60 | 30 of 60 |
| Caution on reversible versions | 15 of 60 | 30 of 60 |
| Irreversible execution on irreversible versions | 60 of 60 | 60 of 60 |
| Greater binary caution on irreversible version | 0 of 60 pairs | 0 of 60 pairs |
| Agent parsing failures | 5 | 819 |
| Step limit terminations | 12 | 120 |

Llama predicted partially reversible on every RQ2 record. Its 48 percent
accuracy therefore equals an always partially reversible classifier on this
test set, and does not demonstrate three-class discrimination. Qwen predicted
irreversible for 337 examples, partially reversible for 27, and reversible for 61.

The separate initial critical-action judgments on the RQ3 tasks were constant:
Qwen predicted irreversible on all 120 versions and Llama predicted partially
reversible on all 120 versions. No task pair was correctly judged on both sides.
Thus K was zero, as was A, the proportion of pairs with greater binary caution
on the irreversible version. Their difference was zero for both models. This
does not support a claim that the models correctly distinguished paired
reversibility while failing to act on that knowledge.

Qwen's measured caution occurred on all email tasks in both conditions. Llama's
measured caution occurred on all email and payment tasks in both conditions.
Neither model had a positive paired caution difference. The exact McNemar test
on caution had no discordant pairs and p equal to 1 for each model.

## Execution failure and interpretation

All 819 Llama parsing failures were the response `{"tool": "finish"}`. The
contract requires `{"tool": "finish", "args": {}}`; the strict parser therefore
rejected them correctly. Every Llama run reached the step limit. Continued
execution after attempted finishes can alter or undo completed actions, so the
final-state success comparison is confounded by output-format compliance.
Post-critical checks or backups do not count as pre-critical caution.

The saved traces for all 120 full-run versions of each model were replayed in
the sandbox. Replayed completion, critical actions, irreversible actions,
caution events, step counts, parsing counts and termination reasons matched
the recorded outcomes. The RQ2 IDs, labels and saved messages matched the frozen
test set and rebuilt stated prompts.

## Analysis outputs and remaining integration

Run `scripts/behaviour/analyze_uploaded.py` with the original backup directory
to regenerate the tables under `results/member3_verified_analysis`.
RQ2 score intervals use 1000 scenario-group bootstrap resamples with seed 42.
RQ3 intervals use 1000 task-pair resamples. Per-class macro metrics use the
three fixed labels. Bootstrap samples missing a class assign its recall zero
under this implementation. Constant empirical outcomes yield degenerate
percentile bootstrap intervals, which must not be described as population certainty.

The analysis includes the majority label selected from training data, fixed-label
classifiers, and TF IDF action-text logistic regression trained only on training
records with fixed C equal to 1. This baseline was added after the model runs
and is a post hoc descriptive control, not a preregistered analysis. No model
prompts or frozen test labels were changed to improve performance.

The script joins the supplied three-class probe predictions to stated answers
using record IDs. Probe versus behaviour on the separate RQ3 task prompts still
requires predictions from Member 2's frozen probes. Existing RQ1 hidden states
cover different items and cannot replace these task-specific predictions.

## Limitations

The sandbox has four task templates and two model families. Binary caution
cannot distinguish the amount of caution once both versions show an event.
The test split is class-imbalanced and includes one ScienceWorld test record,
so it does not support a broad ScienceWorld judgment claim. Frozen restoration
labels reflect the sandbox's operational three-action definition. Strict formatting
failures substantially affect Llama's behaviour results. The original runs must
be preserved; any changed-prompt or parser experiment must be labelled separately.

## Suggested contribution paragraph for review

I implemented the RQ2 stated-judgment evaluation and RQ3 agent execution workflow,
ran Qwen and Llama on the frozen test set and matched sandbox tasks, and preserved
configurations and raw outputs. I analysed reversibility judgments, pre-action
caution, irreversible execution and task completion, and documented the effects
of parsing failures. I used coding and analysis assistance and reviewed the
resulting implementation and outputs.

Edit this paragraph to reflect the work personally reviewed and completed, and
follow the course policy for disclosing assistance. This file is a draft for
team review and integration, not a finished project paper.
