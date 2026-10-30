# Open Questions

Unresolved research-design questions. Each has a **proposed default** so that work can proceed. A default is not a decision: when resolved, record the outcome here and, where it changes the design, in `docs/decisions/`.

**Ask** column:

- **Prof** — touches a professor requirement or interpretation of the spec; must be asked;
- **Team** — our engineering choice.

**Blocks** — the phase or milestone that cannot finish without an answer.

| ID | Question | Why it matters | Proposed default | Ask | Blocks | Status |
|---|---|---|---|---|---|---|
| OQ-01 | **Compute.** The spec says "our GPUs have about 50 GB" and "everything must run on our GPUs". We planned Colab/Kaggle. Do we have course-GPU access? Is Colab/Kaggle acceptable for reported results? | A 7–8B model in 16-bit (~15–16 GB weights) does not fit a single 16 GB GPU with activations. Dtype/quantisation choices change hidden states | Ask for course-GPU access. Otherwise use a multi-GPU or larger-GPU session in 16-bit. No quantisation for primary results | Prof | P4, P5 | Open |
| OQ-02 | Is `scenario_id` the right split unit, or should sandbox splits hold out whole templates? | Template-level wording can leak through scenario splits | Primary: scenario split (as in spec). Robustness: template-held-out | Team (inform Prof) | P3 | Open |
| OQ-03 | How is "partially reversible" (approximately / at a cost) computed in **ScienceWorld**? What is the canonical state (excluding counters, time-evolving properties)? | Without a rule, ScienceWorld can only produce binary labels; class balance and three-class results depend on it | Whitelist of soft properties + tolerance; if infeasible, ScienceWorld binary-only and partial from the sandbox, stated as a limitation | Prof | P3 | Open |
| OQ-04 | Release one row per example with `labels_by_horizon` (our choice), or one row per (example, horizon)? How many sandbox examples need restore depth 2–3 for the horizon ablation to be informative? | Format compliance with spec §4.3; ≥2,000 counting | One row per example, `horizon=3`; derived per-horizon files on request; ≥10% of sandbox examples with depth 2–3 | Prof (format), Team (depth) | P3 | Open |
| OQ-05 | Sandbox time model for the "60-second undo window" | One "action" must map to simulated time for the window to be meaningful within the horizon | Simulated clock, +10 s per tool call; window open for 60 s; clock excluded from the canonical state | Team | P2 | Default implemented as parameter `seconds_per_action=10` (not final) |
| OQ-06 | What does `ask_user` reply? | The reply affects success and subsequent behaviour; it must not reveal the version | Fixed neutral reply, identical across versions | Team | P5 | Open |
| OQ-07 | Exact definition of K ("correctly states which version is irreversible"). How are PARTIALLY_REVERSIBLE answers handled in the binary/task setting? | Headline metric | Per-version independent stated query. Correct iff irr→IRREVERSIBLE and rev→not IRREVERSIBLE. Alternative (side-by-side "which version?") as a secondary analysis | Prof | Plan freeze | Open |
| OQ-08 | Exact caution rule: does generic state inspection count as CHECK? How is over-caution defined? | Lenient rules inflate caution in both versions and compress sensitivity | Primary: CHECK only for pivot-relevant inspection; strict variant reported. Over-caution = caution on reversible version (+ strict CONFIRM/REFUSE variant) | Team (inform Prof) | Plan freeze | Open |
| OQ-09 | Should bootstrap CIs resample scenarios (clusters) or individual examples? | Examples within a scenario (esp. minimal pairs) are correlated; example-level CIs would be too narrow | Cluster bootstrap by `scenario_id`; task-pair bootstrap for RQ3 | Team | Plan freeze | Open |
| OQ-10 | Minimum share per testbed within the 2,000 examples | Cross-environment transfer needs enough test scenarios in both | ≥1,200 sandbox, ≥800 ScienceWorld | Prof | P3 | Open |
| OQ-11 | Which ablations beyond the 3 compulsory? | Spec requires ≥4 | A4 horizon (also required by REQ-LBL-04). Also A5 careful-vs-neutral prompt if GPU time allows | Team | Plan freeze | Open |
| OQ-12 | Should stated-knowledge results be checked over several question paraphrases? | Single-wording results may be fragile | Optional: 3 paraphrases on one split seed, reported as robustness | Team | — | Open |
| OQ-13 | After a parse failure, does the run continue? Is there a cap? | Affects step counts and outcomes | Continue with an error observation; abort after 3 consecutive failures; the outcome is recorded as `aborted_parse` | Team | P5 | Open |
| OQ-14 | How do we handle GPU non-determinism under greedy decoding? | Repeatability claim | Re-run 10% of agent runs; report the flip rate | Team | P5 | Open |
| OQ-15 | Licence for our code and dataset; constraints from ScienceWorld/ToolEmu/Llama outputs | Release (REQ-ENV-09) | Decide after verifying upstream licences | Team (+Prof) | P7 | Open |
| OQ-16 | Who is the second annotator for the 100-example study? | REQ-LBL-05 | M2 or M3, whoever is less loaded in P3 | Team | P3 | Open |
| OQ-17 | Owners for bonus RQ4/RQ5, if attempted | Planning | RQ4: M2 + M3; RQ5: M1 (labels) + M3 | Team | After MPR | Open |
| OQ-18 | Course deadline and intermediate check-ins | Roadmap dates | — | Prof | Roadmap | Open |
| OQ-19 | Does "at least 60 tasks" mean 60 task *pairs* (120 versions)? | Sample size for RQ3 | 60 task pairs (each with two versions) | Prof (confirm) | P3 | Open |
| OQ-20 | Is the "60-second undo window" example in the spec meant to stay reversible at horizon 1 only? Should restore depths >1 be designed for email/money too? | Horizon ablation informativeness | Design some depth-2/3 restore paths across tools | Team | P2 | Open |
| OQ-21 | Spec §4.2 example "edit a file when no backup exists but the old text is still in the history": is "history" the file's version history (sandbox state) or the agent's conversation history? | Determines what a restoration may use; the second reading would make most edits partially reversible whenever the agent read the file first | Implemented: version history in the state; restoration may use only post-action state + the judged action's args (`10` §5.3). Single switch point: `argument_pool` | Prof | Dataset (P2/P3) | Open |
| OQ-22 | When undo/cancel windows from *earlier* actions are pending, the world changes over time regardless of the judged action. Compare with the literal pre-action state (spec) or with a "do nothing" baseline? | Labels of unrelated actions in such states | Literal comparison; such assessments are flagged `pending_timers_before=True`; dataset avoids or separately reports them | Prof | P3 | Open |
| OQ-23 | Do failed tool calls consume logical time? | Undo windows can expire through failed calls | Yes: every agent step advances the clock | Team | P5 | Open |
| OQ-24 | The restoration action domain D does not recombine email fields across messages and takes amounts only from payments and the judged action | Restorations needing such values are reported as not found (counted as irreversible/partial) | Keep D as documented. Revisit if pilot data contain cases where this matters | Team | P3 | Open |

| OQ-25 | What counts as a "paraphrase" for the held-out phrasing requirement (05 §6)? | Lexical robustness of probes | Pilot: 3 deterministic state-rendering styles (`compact` test-only) + 2 task-text templates per family; no free-form paraphrasing | Team | Final dataset | Open |
| OQ-26 | RQ2 question wording and fixed answer-option order (REVERSIBLE, PARTIALLY_REVERSIBLE, IRREVERSIBLE) | Position bias and wording sensitivity of stated answers | Fixed in prompt builder 1.0.0; a paraphrase/order robustness check is optional (see OQ-12) | Team (M3) | Plan freeze | Open |
| OQ-27 | Tool descriptions disclose sandbox mechanics ("Goes to the recycle bin only if the bin is enabled", "a fee is deducted") | They give world knowledge that can help both stated answers and behaviour; identical within pairs | Keep (a real tool API would document this); revisit if the professor prefers neutral descriptions | Prof | Plan freeze | Open |
| OQ-28 | Non-pair pilot examples use a fixed action cycle that may be unrelated to the task text, so verb partly predicts label | Lexical shortcuts; ecological validity of candidate actions | Acceptable for the pilot (lexical baselines will expose it); the final dataset should sample candidate actions per scenario and balance verb x label | Team | Final dataset | Open |

## Resolved

*(none yet)*
