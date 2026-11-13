# Kaggle follow up experiment plan

## Purpose

Evaluate whether weak judgments and agent execution reflect sensitivity to
instruction wording and output formatting. Higher accuracy is not guaranteed
and is not the criterion for publishing results. Preserve all original runs.
This is an exploratory follow up because the original test results have been seen.
The conditions and analyses should be reviewed and frozen before new inference.

## Separate questions and conditions

RQ2 compares the original neutral stated prompt with recovery_v1, which clarifies
that recovery begins after the proposed action. It provides no ground truth,
task-specific recovery sequence, or test example. First compare both conditions
on exactly the same 10 scenario groups selected from the training split with
seed 42. Check class counts and report all three labels and invalid answers.
Do not choose demonstrations, wording or settings using the existing test labels.
Freeze the prompt before evaluating the existing test set again; report that
evaluation as exploratory rather than an untouched confirmatory test.

RQ3 compares neutral with format_v1, which explicitly illustrates finish with
empty args and changes no safety instruction. Compare format_v1 with
format_careful_v1 to estimate the additional effect of a general caution
instruction while holding format guidance fixed. Do not attribute the combined
neutral versus format_careful_v1 difference solely to caution guidance.
Judgment condition is independently configurable. Hold it fixed when comparing
agent prompt conditions. The strict parser and frozen tasks remain unchanged.

Run Qwen first, then Llama, keeping each checkpoint, precision, generation limit,
tools and scoring rules fixed. Use the original neutral runs as the baseline,
and optionally repeat neutral smoke checks to confirm the new harness. Greedy
decoding repetitions with unchanged inputs are not independent samples.

## Added engineering

- Versioned condition strings outside frozen prompt builders.
- Actual effective message hashes as well as original prompt hashes.
- Training-only grouped development selection recorded in config.
- Plan-only dry run before loading model weights.
- Resume skips saved complete outcomes only and rejects changed configurations.
- An interrupted task restarts from its initial state with a separately named
  trace; incomplete traces remain preserved. Exact in-task continuation is not
  claimed. Existing failed complete outcomes are retained, not silently retried.
- Corrupt or partially written outcomes lines fail explicitly for manual review.
- Model revision, runtime GPU names and generation configuration recorded.
- Per-item progress saved and flushed.

Copy the entire output directory to persistent storage or download it after each
session. Kaggle working storage alone is not a permanent backup. Resume requires
the same code hashes, model, data, configuration and relevant package versions.
Do not edit the runner between interrupted sessions of the same run.

## Suggested budget

Start with two training-only RQ2 conditions on Qwen and a two-version format_v1
agent smoke test. Then run the 20-version format_v1 pilot. If valid finishes are
still absent, inspect the raw calls rather than relaxing the strict contract.
Run full conditions only after a documented review of implementation health,
not because pilot accuracy is high. Pilot and full outcomes remain separate.

## Reporting

Report original and follow-up conditions side by side. Primary RQ2 metrics are
balanced accuracy, macro F1, per-class recall, and scenario-bootstrap intervals.
Report prediction distributions to expose constant-label collapse. For RQ3
report formatting compliance, successful finish rate, step-limit rate, task
completion, irreversible action execution and caution separately. Use matched
task-pair resampling and paired tests for comparisons, with the number of prompt
conditions and all attempted runs disclosed. A smaller parsing-failure rate
does not by itself demonstrate improved reversibility understanding.

Do not train on the 60 behavioral task pairs or fit an oracle rule into the
model's answer path. The oracle remains an evaluation tool. A new untouched
task set requires a separately frozen version, Member 1 coordination and
leakage checks; never edit rq3-tasks-1.0 in place.
