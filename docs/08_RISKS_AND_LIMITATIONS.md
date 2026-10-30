# 08 — Risks and Limitations

Likelihood (L) and impact (I) are our estimates: H/M/L. Risks in the spec's own table (§9) are marked **[SPEC §9]**, and their spec-prescribed handling is included.

## 1. Dataset leakage — L: M, I: H

**Risk.** If examples from one scenario (or template) appear in both train and test, the probe can memorise scenario wording and inflate accuracy (spec §4.3).

**Mitigation:**

- split by `scenario_id`, with minimal-pair members always in the same scenario;
- automated leakage tests (shared ids, identical inputs, near-duplicates);
- a template-held-out robustness check;
- RQ3 task scenarios kept disjoint from probe data.

**Detection signal.** Shuffled-label probe above chance; a large gap between template-held-out and scenario-held-out accuracy.

**Fallback.** Re-split by template; report both.

## 2. Probe memorisation and lexical shortcuts — L: H, I: H

**Risk.** The probe reads surface features: the verb "delete" in the action, or the word "disabled" in the state. It then looks like "knowledge of reversibility". **[SPEC §9]**: "the probe works, but so does the lexical baseline".

**Mitigation:**

- ≥30% minimal pairs with byte-identical actions;
- action-only BoW (required) and state+action BoW (ours);
- control task with selectivity;
- layer-0 probe;
- surface-form variation of pivots, with held-out phrasings in test;
- linear probes only.

**Fallback** (spec): add more minimal pairs where the same verb has different reversibility. If the state+action BoW still matches the probe, report the weaker claim (`04` §9).

## 3. Label ambiguity — L: H (partial class), I: M

**Risk.**

- "Partially reversible" ("approximately or at a cost") is the least well-defined label.
- Canonical-state choices (which attributes count) change labels.
- The horizon cap of 3 turns long-but-possible restorations into "irreversible".

**Mitigation:**

- written rules (`05` §3) frozen before annotation;
- κ with two blind annotators;
- binary task reported first;
- every label carries `label_rationale`;
- horizon results at 1/2/3 show how much the cap matters.

**Fallback.** If κ for the partial class is poor, report three-class results as secondary and say so. Never re-define labels after seeing test results.

## 4. ScienceWorld restore/replay complexity — L: H, I: H

**Risks:**

1. No native save/restore. Reset+replay costs O(history length) per BFS node.
2. The branching factor (number of valid actions) makes exhaustive depth-3 BFS very expensive.
3. "Exact previous state" is ill-defined if the world has time-dependent processes (e.g. temperatures changing every tick) or score/step counters.
4. Java dependency; possibly no native Windows support.
5. The API may have changed. We have not checked it yet (REQ-ENV-05).

**Mitigation:**

- check the current API first;
- cache replays by action-prefix;
- restrict candidate actions per node (objects touched by the action + movement) and record the rule;
- run on a *sample* of states, as the spec suggests;
- a canonical state excluding counters and with tolerance for continuous properties (OQ-03);
- run on Linux/WSL2/CPU cloud;
- parallelise over processes.

**Consequence for claims.** ScienceWorld "irreversible" means "no restoring sequence was found in the pruned search". The false-irreversible rate is estimated on an audit subset with a wider search, and through human agreement.

**Fallback.** If BFS is too slow:

- reduce to horizons 1–2 for ScienceWorld, report the cap, and ask the professor;
- reduce ScienceWorld's share of the dataset (it must still be present).

## 5. GPU memory limitations — L: H on Colab/Kaggle, I: H — **[SPEC §9]**

**Risk.** A 7–8B model in 16-bit needs ~15–16 GB for weights (spec §5), plus activations and KV cache. Saving all layers' hidden states adds memory pressure.

**Mitigation** (spec): batch size 1, shorter prompts, store selected layers only if needed, never two models at once. Also ours: move hidden states to CPU per example; float16 storage; prompt-length check in the validator.

**Open.** Course GPU vs Colab/Kaggle (OQ-01). Quantisation is avoided for primary results.

## 6. Runtime interruption — L: H, I: M

**Risk.** Colab/Kaggle sessions end (time limits, idle timeouts, quota), losing hours of work.

**Mitigation:**

- resumable shards (extraction) and per-run JSONL (agent);
- outputs written to persistent storage immediately;
- idempotent scripts that skip completed work;
- manifests with `status: interrupted`.

**Fallback.** Split jobs by model and dataset shard across sessions/accounts. Never mix library versions within one model's results.

## 7. Model output parsing — L: H, I: M — **[SPEC §9]**

**Risk.** The agent emits malformed JSON, multiple tool calls, prose, or calls unknown tools. Stated answers do not match the three labels.

**Mitigation** (spec): strict format with one JSON tool call per step; parse failures counted separately, never silently dropped. Also ours:

- a precise format instruction with one example call;
- extraction of the first well-formed JSON object only, under a documented rule;
- the parse failure is returned to the model as an error observation;
- per-model parse-failure rates reported;
- sensitivity analysis excluding runs with failures.

Parse failures are **not** counted as caution or refusal.

## 8. Agent never takes the irreversible action — L: M, I: H — **[SPEC §9]**

**Mitigation** (spec): make the irreversible path clearly faster or cheaper in the task description; add more tasks. Ours: a pilot on 10 task pairs before the full run (`04` §6). Pilot data is excluded from the final analysis.

## 9. Research novelty verification — L: M, I: H — **[SPEC §3, §9]**

**Risk.** Somebody has published (or will publish during the semester) the same experiment. The professor's novelty claim is "to the best of my knowledge" and we have not verified it.

**Mitigation:**

- a novelty search with a dated log in `references/README.md`, repeated monthly;
- read the closest work listed in the spec (Tang et al., COLM 2025) early;
- if a match is found, **tell the professor at once**.

**Fallback** (spec): shift the focus, e.g. to the minimal-pair design or the steering result. We never claim novelty in the report without the completed search.

## 10. Other risks

| Risk | L/I | Mitigation |
|---|---|---|
| Llama access approval delayed | M/H | Apply in week 1 (REQ-MOD-03); do everything on Qwen first; record dates |
| Steering breaks output **[SPEC §9]** | — | Bonus only: reduce strength; report task success with caution |
| Small behavioural sample (≥60 pairs, one greedy run each) | H/M | Report CIs; avoid claims of "no effect"; more pairs if time allows |
| Team member unavailable | M/H | Contracts + guides let others take over; pilot data enables early integration |
| Sandbox design bias (we set the labels) | H/M | ScienceWorld replication; honest limitations |
| Tokeniser/chat-template quirks shift the action-token index | M/H | Span-based localisation via offsets; human-checked decoded tokens (`04` §3) |
| Accidentally using a paid API | L/H | No OpenAI/Anthropic SDK in dependencies; review checklist |

## 11. Limitations we expect to report (spec §8 asks for honesty)

- Small, author-designed sandbox. Labels reflect our design decisions.
- Two model families of similar size (14B optional).
- Restoration horizon capped at 3. Pruned search in ScienceWorld.
- Partially-reversible definition is testbed-specific.
- English-only, text-rendered states.
- Linear probes test linear accessibility only. Negative probe results do not prove absence.
- Greedy single-trajectory behaviour per task version.
- Correlational RQ1–RQ3. Only RQ4 (bonus) gives causal evidence.
