# Member 3 paper handoff

## Contribution and scope

Member 3 implemented the RQ2 stated-judgment evaluation and RQ3 sandbox agent
runner, ran both models, and preserved the prompts, raw responses, configurations,
and tool traces. The analysis covers classification results, agreement with
Member 2's RQ1 probes, paired behavior, and the follow-up prompt experiments.

## Methods

We used Qwen2.5-7B-Instruct and Llama-3.1-8B-Instruct with float16 inference,
greedy decoding, a 256-token generation limit, and seed 42. The model revisions
were `a09a35458c702b33eeacc393d103063234e8bc28` and
`0e9e39f249a16976918f6564b8830bc894c89659`, respectively. The run
configurations record PyTorch 2.11.0+cu130, Transformers 5.20.2, and Accelerate
1.15.0.

**RQ2.** Each model judged whether the proposed action could be undone within
three further tool calls. We parsed its first answer line into reversible,
partially reversible, or irreversible. The frozen v2.0 test split contained
425 examples across 25 scenarios, with 68 reversible, 204 partially reversible,
and 153 irreversible examples. Ground-truth labels were used for scoring.
Balanced accuracy is the mean of the three class recalls. We also report
macro-F1 and an exploratory action-text TF-IDF logistic regression baseline
fitted on the training split with C = 1.

**RQ3.** Each model ran 60 matched task pairs covering deletion, overwrite,
email, and payment. Each pair used two versions that differed in a
reversibility-related state setting. An agent had up to 15 replies and could
terminate with a valid finish call. The strict tool parser counted invalid
responses against the reply budget. We evaluated task success from the final
sandbox state. The binary caution measure marks any qualifying check,
confirmation, backup, safer tool, or finish before a successful critical action.
We compared caution within task pairs using an exact McNemar test. The
10-pair pilots are reported independently of the full runs.

## RQ2 and the RQ1 comparison

| Model and setting | Accuracy | Balanced accuracy | Macro-F1 |
|---|---:|---:|---:|
| Qwen original | 26.35% | 28.49% | 0.221 |
| Llama original | 48.00% | 33.33% | 0.216 |
| Training-majority baseline | 16.00% | 33.33% | 0.092 |
| Action-text TF-IDF baseline | 76.00% | 72.88% | 0.716 |
| Qwen recovery guidance | 21.65% | 24.78% | 0.209 |
| Llama recovery guidance | 35.06% | 32.68% | 0.326 |

The original Qwen prompt elicited irreversible judgments on 337 of 425
examples. Llama predicted partially reversible on all 425, making its 48.00%
accuracy equal to the frequency of that class. Both runs had zero unparseable
answers. The strong action-text baseline indicates that action wording carries
predictive information in this split.

The exploratory recovery prompt clarified that recovery starts after the
proposed action. On 142 training examples drawn from 10 development scenarios,
balanced accuracy rose from 41.53% to 53.81% for Qwen and from 34.62% to 49.21%
for Llama. On the frozen test examples, balanced accuracy declined for both
models. Llama's macro-F1 rose, reflecting a change in its class predictions.
The test comparison was performed after inspection of the original results.

| Model | RQ1 probe accuracy | Agreement with original RQ2 (κ) | Agreement with recovery RQ2 (κ) |
|---|---:|---:|---:|
| Qwen | 93.65% | 116/425 (27.29%, −0.141) | 95/425 (22.35%, −0.195) |
| Llama | 94.12% | 206/425 (48.47%, 0.000) | 154/425 (36.24%, 0.018) |

All example IDs, scenario IDs, and labels matched Member 2's official
three-class prediction files. Those files were byte-identical to the copies used
in the comparison. The probes performed substantially better than the stated
judgments on these examples. The comparison covers two elicitation methods.
Historical checkpoint equivalence remains unverified because Qwen's RQ1
revision was unrecorded and Llama's RQ1 loading call was unpinned.
[Member 2 prediction audit](https://github.com/Sneha-260805/ADNN/blob/650f176b2a52c87da23ae3c3043f77bf29ed180d/docs/audits/ADNN_RQ1_official_prediction_audit.md)

## RQ3 and Llama formatting follow-up

| Full-run outcome | Qwen original | Llama original | Llama format guidance |
|---|---:|---:|---:|
| Successful final states | 119/120 | 87/120 | 117/120 |
| Caution on reversible versions | 15/60 | 30/60 | 30/60 |
| Caution on irreversible versions | 15/60 | 30/60 | 30/60 |
| Irreversible execution on irreversible versions | 60/60 | 60/60 | 60/60 |
| Parsing failures | 5 | 819 | 0 |
| Step-limit terminations | 12/120 | 120/120 | 0/120 |

For each model, every paired binary caution flag agreed across its reversible
and irreversible versions. The paired caution difference was zero percentage
points and the exact McNemar test had zero discordant pairs (p = 1).
The original caution rates were 25% for Qwen (95% pair-bootstrap interval
15.0–36.7%) and 50% for Llama (36.7–61.7%) in each version. Every irreversible
version still included an irreversible action. Initial stated judgments on
the RQ3 tasks also failed to distinguish the paired versions. The resulting
zero blindness-gap score reflects zero paired discrimination in both measured
judgment and behavior.

A post hoc trace check compared ordered caution events and the first
successful critical-action step within each pair. Qwen matched on both
measures across all 60 pairs. Llama differed on each measure in 5 of 60
pairs. The binary scores therefore hide some differences in how Llama
approached the paired tasks.

The 819 original Llama parsing failures were finish calls missing the required
`args` field. The additional formatting prompt showed
`{"tool": "finish", "args": {}}` explicitly. Under this prompt, all 120 runs
terminated with valid finishes. On matching task IDs, 31 failures became
successes and one success became a failure. Binary caution and irreversible
execution agreed on every ID across the original and formatting runs.
The formatting smoke test (2 versions) and pilot (20 versions) also had valid
finishes and successful final states throughout.

## Interpretation and limitations

The RQ1 probe results show that supervised predictions from hidden states can
recover labels on the evaluated examples. The RQ2 answer distributions show
that eliciting those labels in text was much less reliable. RQ3 tests behaviour
on separate sandbox tasks, so the three research questions support a comparison
of overall patterns. The measured pre-action caution rates apply to the binary
event definition and can miss differences in event type, timing, and repetition.
The four task mechanisms, two model families, imbalanced test set, and
three-call recovery horizon limit generalization. RQ2 includes one ScienceWorld
test example. Constant outcomes can yield degenerate bootstrap intervals.

## Reproduction and handoff files

For the demo, use Llama's original irreversible email task. At step 1 the
agent reads the contacts file and earns a pre-action CHECK. At step 2 it
sends the email and records the critical irreversible action. The trace
illustrates how the same run can exhibit caution and still execute an
irreversible action.
[Illustrative trace](../results/rq3/llama/full/rq3-email-send-01-irr.jsonl)

- [Original configurations, answers and traces](../results/) under
  `rq2/{qwen,llama}/test` and `rq3/{qwen,llama}/{pilot,full}`.
- [Original metric tables](../results/member3_verified_analysis/), including
  classification baselines, scenario-bootstrap intervals, and paired RQ3 scores.
- [Follow-up outputs and checksums](../results/member3_followups/), including
  both recovery test sets and all three Llama formatting runs.
- [RQ1–RQ2 agreement data](../results/member3_followups/rq1_rq2_agreement.csv).
- [Execution and analysis commands](MEMBER3_GITHUB_HANDOFF.md) and
  [follow-up commands](MEMBER3_FOLLOWUP_PLAN.md).

The original 240 full-run trajectories were replayed in the sandbox and
reproduced the recorded outcomes. The follow-up archive manifest links the raw
outputs to their Kaggle source bundles by SHA-256. The Git commits record the
reviewed files after inference. Source hashes and saved configurations identify
the files used during inference.
