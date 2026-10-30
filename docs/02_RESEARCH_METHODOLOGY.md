# 02 — Research Methodology

This document explains *what* we measure and *why each design choice protects validity*. The step-by-step *how* is in `04_EXPERIMENTAL_PROTOCOL.md`. Requirement IDs refer to `00_REQUIREMENTS_TRACEABILITY.md`.

## 1. Pipeline overview

```
 Step 1 (M1)                Step 2 (M2)            Step 3 (M2)        Step 4 (M3)         Step 5 (M3, env: M1)
 Sandbox + ScienceWorld ─▶  Hidden-state     ─▶   Linear probes  ─▶  Stated answers ─▶  Agent behaviour on
 labelled examples          extraction             + controls         (RQ2)              ≥60 paired tasks (RQ3)
 (+ splits, + prompts)      (one forward pass)     (RQ1)                  │                   │
                                                       │                  │                   │
                                                       └────────────▶ Three-way comparison ◀──┘
                                                                     probe vs stated vs behaviour
                                                                     + blindness gap K − A
 Step 6 (bonus, NOT in initial implementation): steering (RQ4), uncertainty (RQ5)
```

The same labelled data feeds three *independent* measurements, which are then compared (spec §6). Independence matters:

- the probe never sees the model's stated answers;
- the stated-answer prompts never include the probe;
- the agent runs are scored by deterministic rules, not by the model.

## 2. Data collection and labels

### 2.1 Unit of analysis

An **example** is one labelled (state, action) pair. The spec calls these "pairs"; we say "example" to avoid confusion with *minimal pairs* and *task pairs*. Each example has a rendered `state_text`, a candidate `action_text`, and labels at horizons 1, 2 and 3. Full schema: `05_DATASET_SPECIFICATION.md`.

### 2.2 Testbeds

- **Tool sandbox (M1).** A small simulated world: files, recycle bin, backups, email outbox, wallet. Its full state can be snapshotted and restored. Labels come from the design (REQ-LBL-02) and are cross-checked by a brute-force restore search over the sandbox's own tools (REQ-ENV-03). This is the primary testbed because ground truth is exact.
- **ScienceWorld (M1).** A text-based science environment with physical actions such as heat, freeze, mix and pour. Labels are computed automatically: snapshot (or replay), apply the action, then a breadth-first search over action sequences of length ≤ h for a sequence that restores the canonical state (REQ-LBL-03). Its role is to show the findings are not specific to our sandbox.
- **ToolEmu cases (optional, recommended).** The 144 curated cases, re-labelled by us and executed in our sandbox. We never run the ToolEmu emulator (REQ-ENV-06).

### 2.3 Minimal pairs: the central design element

A minimal pair is two (or more) examples with an **identical `action_text`**, whose states differ in one controlled "pivot" factor, and whose labels differ. The spec's examples:

| Action | Pivot factor | Label A | Label B |
|---|---|---|---|
| `delete_file` | recycle bin enabled / disabled | reversible | irreversible |
| `edit_file` | backup exists / does not | reversible | partially_reversible |
| `send_email` | 60-second undo window / immediate send | reversible | irreversible |

Because the action tokens are identical within a pair, anything that only reads the action text cannot tell the pair members apart. This includes the action-only lexical baseline and, largely, the embedding layer at the action position. A probe that separates them must use information about the state that is integrated at the action position. That is why ≥30% of examples must belong to minimal pairs (REQ-DATA-05), and why the probe must beat the lexical baseline *on minimal pairs* (REQ-BL-02).

### 2.4 Human agreement

Two members independently label the same random 100 examples without seeing the automatic label (REQ-LBL-05). We report:

- Cohen's κ between the two annotators;
- κ between each annotator (and their adjudicated consensus) and the automatic label.

The sample is stratified across testbeds so ScienceWorld's automatic labels get scrutiny. Annotation guidelines are written *before* annotation starts and are frozen.

## 3. Probing (RQ1)

- **Representation.** The residual-stream hidden state at every layer ℓ = 0…L (layer 0 = token embeddings), at (a) the last token of the action, which is primary, and (b) the mean over action tokens, which is ablation REQ-ABL-02. The prompt is the shared agent prompt (task description, rendered state, tool list) followed by the candidate action, as in REQ-M-02.
- **Probe.** L2-regularised multinomial logistic regression per layer (scikit-learn). Features are standardised with statistics fitted on train only. C is chosen by grouped inner CV on train. Probes stay linear (REQ-M-03); no MLP probes, no kernel tricks.
- **Tasks.** Binary first (reversible vs irreversible; partially-reversible examples excluded), then three-class.
- **Best layer.** The best layer is chosen on **inner-CV validation**, never on the test set (ENG-06). The full test curve is still plotted for every layer.

## 4. Stated knowledge (RQ2)

The model is asked, in plain language and with the same state and action context, whether the action can be undone. It must answer with one of three fixed labels in a strict format. A deterministic parser maps the answer onto `reversible | partially_reversible | irreversible | UNPARSEABLE`. Unparseable answers are counted and reported, never dropped (REQ-RISK-01 applies by analogy). For each test example we keep the triple (true label, stated label, probe prediction at the selected layer) and compute stated accuracy and κ(stated, probe) (REQ-MET-03).

To check that the stated answer does not depend heavily on the question wording, we plan a small prompt-paraphrase robustness check (ENG; OQ-12). This is not required by the spec.

## 5. Agent behaviour (RQ3)

- **Tasks.** ≥60 sandbox tasks, each in two versions that differ *only* in reversibility (REQ-M-05). In every task, an irreversible action is a tempting shortcut and a safer path exists, e.g. "free up disk space": permanent deletion is faster, while moving files to the recycle bin is safer.
- **Loop.** The model emits exactly one JSON tool call per step, with greedy decoding and at most 15 steps (REQ-M-05, REQ-REP-01). The sandbox executes the call and returns an observation. `ask_user` gets a scripted deterministic reply (OQ-06).
- **Logging.** Every prompt, raw output, parsed call, observation and state hash is logged (REQ-REP-03).
- **Caution detection.** Deterministic rules on the log detect CHECK, CONFIRM, BACKUP, SAFER_TOOL and REFUSE events before the first *critical action*, i.e. the tempting shortcut (REQ-M-07, ENG-11). Exact rules: `MEMBER_3_GUIDE.md` §4.

## 6. Controls, ablations and validity

### 6.1 Compulsory baselines and controls (spec §7.2)

| Control | What it rules out |
|---|---|
| Majority-class baseline (every classification result) | "Accuracy" that only reflects class imbalance |
| Lexical BoW on **action text** (must be beaten on minimal pairs) | The probe merely detecting words like "delete" |
| Shuffled-label probe | Probe capacity to fit arbitrary labels (should be near chance) |
| Control task (Hewitt and Liang): random fixed label per action verb → selectivity | High accuracy that comes from probe memorisation rather than model representations |
| Layer-0 (embedding) probe | Information already present in token embeddings |
| Random-direction steering of the same norm | *RQ4 only; not in initial implementation* |

**Our additional control (ENG-08, not required by the spec):** a lexical BoW on **state text + action text**. In minimal pairs the pivot is visible in the state text (e.g. `recycle_bin: disabled`). A bag-of-words over the whole input may therefore solve the task without "understanding". If it matches the probe, the honest conclusion is "the model represents a surface cue that is predictive of reversibility". The stronger claim, "the model understands reversibility", would not be supported. Mitigations at data level: vary the surface form of pivot states (synonyms, positions, formats), and include distractor state fields that change between examples without affecting reversibility. See `05` §6.

### 6.2 Ablations (spec §7.3; ≥4, first three compulsory)

1. Token position: last action token vs mean over action tokens (**compulsory**).
2. Minimal pairs only vs all data (**compulsory**).
3. Cross-environment transfer, sandbox→ScienceWorld and the reverse (**compulsory**).
4. Horizon 1 / 2 / 3. This is our chosen fourth ablation and is *also* required by REQ-LBL-04.
5. Proposed extra: careful vs neutral system prompt for RQ3 (OQ-11).
6. Optional and not in the initial plan: binary vs three-class (falls out of Step 3 anyway); 7B vs 14B.

### 6.3 Threats to validity

| Threat | Type | Mitigation |
|---|---|---|
| Scenario leakage across splits (probe memorises scenario wording) | Internal | Split by `scenario_id`; minimal-pair members always together; leakage test in CI; additional template-held-out check (OQ-02) |
| Lexical shortcut via action verb | Construct | Minimal pairs; action-only BoW; control task; layer-0 probe |
| Lexical shortcut via state wording | Construct | State+action BoW (ENG-08); surface-form variation of pivot states |
| Label noise / ambiguity (esp. partially reversible) | Construct | Written labelling rules; human κ; report binary task first |
| Pruned BFS in ScienceWorld produces false "irreversible" labels | Construct | Document the pruning; audit a subset with a wider search; human agreement on ScienceWorld examples |
| Prompt differences between versions of a task other than reversibility | Internal | Version diff check: the two versions may differ only in declared pivot fields |
| Caution driven by task phrasing (e.g. "permanently") | Construct | Task wording identical across versions; pivot stated only in the state |
| Parse failures counted as refusal or caution | Measurement | Parse failures are a separate outcome; sensitivity analysis with and without them |
| GPU non-determinism under greedy decoding | Reliability | Log state hashes; re-run a subset to measure flip rate (OQ-14) |
| Choosing the best layer or prompt on the test set | Statistical | Selection on inner CV only; analysis plan frozen before the test set is used (REQ-STAT-04) |
| Multiple comparisons across layers, models and ablations | Statistical | Primary outcomes declared in advance; others labelled exploratory |
| Sandbox is author-designed, so labels encode our assumptions | External | ScienceWorld replication; cross-environment transfer; honest limitations |
| Small behavioural sample (≥60 pairs) | Statistical | Report CIs; do not over-interpret non-significance as absence of an effect |

## 7. Metrics and statistics

| RQ | Metrics (spec §7.1) |
|---|---|
| RQ1 | Balanced accuracy, macro-F1, AUROC (one-vs-rest macro for 3-class) per layer; selectivity = probe acc − control-task acc |
| RQ2 | Stated-answer accuracy (and balanced accuracy); Cohen's κ(stated, probe); unparseable rate |
| RQ3 | Irreversible action rate; caution rate before irreversible actions; task success rate; over-caution rate on reversible versions; reversibility sensitivity |
| Headline | Blindness gap = K − A |

**Statistics (spec §7.4):**

- each probe experiment runs on **3 scenario-level random splits**, reported as mean ± SD;
- **bootstrap 95% CIs with 1,000 resamples**, resampled at the scenario level for probe metrics (ENG-07; OQ-09) and at the task-pair level for RQ3;
- **McNemar's test** for paired reversible-vs-irreversible caution, using the exact binomial version when discordant counts are small;
- every number is reported with its test-set size $n$ (REQ-EVAL-01);
- every run is reported, including failures (REQ-STAT-04).

## 8. Reproducibility principles

- One model forward pass per example; hidden states are saved and probes are re-trained offline (REQ-M-02).
- Greedy decoding, fixed seeds, all prompts and outputs saved (REQ-REP-01..03).
- Config-driven runs with a manifest that records the git commit, library versions, dataset hash, split hash and seeds.
- Exact library versions in lock files per execution environment (REQ-SW-02).

Details: `07_REPRODUCIBILITY.md`.
