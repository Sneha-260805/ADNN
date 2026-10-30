# 00 — Requirements Traceability Matrix

**Source of truth:** `references/ADNN_Project_Option_1_Irreversibility.docx` (the "spec").
"§" numbers below refer to its sections. Section 9 is the risk table; the final two paragraphs
after it are cited as "§9 (MPR)" and "§9 (Safety)".

**Legend**

- **M/O:** `M` = mandatory, `O` = optional (bonus/recommended), `C` = conditionally mandatory (mandatory only if the related optional work is attempted).
- **Owner:** M1 = Sneha (Member 1), M2 = Member 2, M3 = Member 3, ALL = whole team. Names of Members 2 and 3 are not yet known. Owners of optional work and shared deliverables are **proposals** for the team to confirm (OQ-17).
- **Status at 2026-10-30:** `Not started`, `Documented` (planned in docs, no code), `Implemented` (code + passing tests), `Done`. Only the sandbox core is implemented (branch `m1/sandbox-core`); no experiment has been run.

Professor requirements (REQ-*) are listed in §A. Our own engineering choices (ENG-*) are listed separately in §B so they are never confused with the professor's requirements.

---

## A. Professor requirements

### A.1 Research questions and framing (spec §1, §2)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-RQ-01 | RQ1: decode reversibility from hidden states with a simple linear probe and find the layers where it is strongest | §2 table | M | M2 | `adnn.probes` | Per-layer metrics with CIs for both models and both testbeds, including all §7.2 controls | Documented |
| REQ-RQ-02 | RQ2: when asked directly, does the model state reversibility correctly, and does its answer agree with the probe? | §2 table | M | M3 | `adnn.behaviour` (stated), `adnn.evaluation` | Stated accuracy and κ(stated, probe) with CIs on the same examples | Documented |
| REQ-RQ-03 | RQ3: during task execution, is the agent more careful (confirm, check, refuse, safer alternative) before irreversible actions? | §2 table | M | M3 | `adnn.behaviour` (agent loop) | RQ3 metrics and the blindness gap on ≥60 task pairs | Documented |
| REQ-RQ-04 | RQ4: activation steering along the probe's "irreversible" direction; does caution increase? (causal test) | §2, §6 Step 6 | O (bonus) | Proposed M2 + M3 | `adnn.experiments` + forward hooks | Steering curve over ≥5 strengths with random-direction control | Not started |
| REQ-RQ-05 | RQ5: is next-state prediction uncertainty related to reversibility? | §2, §6 Step 6 | O (bonus) | Proposed M1 (labels) + M3 (NLL analysis) | `adnn.experiments` | AUROC of NLL for irreversible vs reversible, with CI | Not started |
| REQ-RQ-06 | State one clear finding at the end; do not decide it in advance ("let the data decide") | §2 | M | ALL | — | Analysis plan frozen before test-set results are seen (REQ-STAT-04) | Documented |
| REQ-RQ-07 | The project is a measurement study. Building a new agent is not required; a clean negative result is valid | §1 | M (framing) | ALL | — | The report presents negative results with full controls (see `04` §9) | Documented |
| REQ-GR-01 | Bonus (up to 2 marks) needs RQ4 or RQ5 with proper controls, and a report ready for workshop/conference submission after minor edits. A clean negative result can also earn it | Preamble | O | ALL | — | — | Documented |

### A.2 Background reading and novelty (spec §3)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-LIT-01 | Every member reads the Group A papers in the first week | §3 | M | ALL | `references/README.md` | Each member confirms in the contribution log | Not started |
| REQ-LIT-02 | Divide Group B among the team; each person gives a short summary | §3 | M | ALL (assignment by M1) | `references/README.md`, `docs/literature/` | One summary per Group B paper | Not started |
| REQ-LIT-03 | Open every cited paper and verify its title, authors and venue before citing | §3 | M | ALL | `references/README.md` | Every bibliography entry has a "verified" tick | Not started |
| REQ-LIT-04 | Search arXiv for newer work. If the exact experiment is already published, tell the professor immediately | §3, §9 risk table | M | M1 coordinates, ALL search | `references/README.md` novelty log | Search log with dates and queries; professor informed if a hit is found | Not started |

### A.3 Environments and resources (spec §4.1)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-ENV-01 | Build a small Python tool sandbox simulating a file system, email outbox and wallet, with tools such as `read_file`, `edit_file`, `delete_file`, `send_email`, `transfer_money`. It is the main testbed for RQ1–RQ4 | §4.1, §6 Step 1 | M | M1 | `adnn.sandbox` | Unit tests for every tool and its state effects | Implemented (sandbox core; tests pass, `docs/11`) |
| REQ-ENV-02 | The sandbox is a small Python class holding the full state (files, outbox, wallet balance) and can save and restore it | §6 Step 1 | M | M1 | `adnn.sandbox` | Property test: `restore(snapshot())` gives a state equal to the original after any tool sequence | Implemented (sandbox core; tests pass, `docs/11`) |
| REQ-ENV-03 | Every sandbox tool has a known reversibility | §6 Step 1 | M | M1 | `adnn.sandbox` | A test checks that each tool's declared label matches a brute-force restore search inside the sandbox | Implemented (sandbox core; tests pass, `docs/11`) |
| REQ-ENV-04 | Use ScienceWorld as the second testbed (physical actions), to show that findings are not specific to our sandbox | §4.1 | M | M1 | `adnn.scienceworld` | ScienceWorld examples are present in the dataset and used in RQ1 and the cross-environment ablation | Documented |
| REQ-ENV-05 | Check the current ScienceWorld docs for save/restore. If there is none, reset the same task variation and replay the action history. Search on a sample of states | §4.1 | M | M1 | `adnn.scienceworld` | Test: replay reproduces the canonical state exactly on N sampled trajectories | Documented |
| REQ-ENV-06 | ToolEmu: use only the 144 curated cases in `assets/all_cases.json`, add our own reversibility labels, run them in our own sandbox with our models. Do NOT run the ToolEmu emulator | §4.1 | O (recommended) | M1 | `adnn.dataset` | If used, cases are labelled with `source=toolemu_manual` and no GPT-4 call exists | Not started |
| REQ-ENV-07 | ByteSized32-State-Prediction for RQ5. Write our own inference code (their scripts call OpenAI); research use only; ask the authors before redistributing | §4.1 | O | Proposed M1 | `adnn.experiments` | No OpenAI import; no redistribution of their data | Not started |
| REQ-ENV-08 | Do not build a large new environment | §4 | M (constraint) | M1 | — | Sandbox scope is reviewed at the Phase 2 gate | Documented |
| REQ-ENV-09 | Licences were checked by the professor in Sept 2026 but can change. Verify again before releasing any data or code | §4 | M | M1 | `data/processed/DATA_CARD.md` | Licence check recorded with date before release | Not started |

### A.4 Labelling (spec §4.2)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-LBL-01 | Three labels. **Reversible:** the exact previous state can be restored within 3 further actions. **Partially reversible:** restorable only approximately or at a cost. **Irreversible:** no sequence of ≤3 actions restores it | §4.2 | M | M1 | `adnn.dataset` | Schema validator accepts only these three values | Documented |
| REQ-LBL-02 | In the sandbox, the label comes from our design | §4.2 | M | M1 | `adnn.sandbox` | Same test as REQ-ENV-03 | Implemented (sandbox core; tests pass, `docs/11`) |
| REQ-LBL-03 | In ScienceWorld, compute labels automatically: save state, apply action, BFS over action sequences of length ≤3, check whether the saved state is reached | §4.2 | M | M1 | `adnn.scienceworld` | Unit tests on hand-built cases with known restore depth | Documented |
| REQ-LBL-04 | Treat the horizon (3) as a parameter and **report results for horizons 1, 2 and 3** | §4.2 (also §7.3) | M | M1 (labels at each horizon), M2 (results) | `adnn.dataset`, `adnn.probes` | Every example stores labels at h=1,2,3. The probe results table has rows for each horizon | Documented |
| REQ-LBL-05 | Two team members hand-label the same random sample of 100 pairs without seeing the automatic label. Report κ between the two humans and between human and automatic labels | §4.2 | M | M1 (organises + annotator 1), M2 or M3 (annotator 2) | `data/annotation/`, `adnn.evaluation` | Two κ values with CIs in the data card | Documented |

### A.5 Dataset size, balance, format (spec §4.3, §6 Step 1, §8)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-DATA-01 | At least 2,000 labelled (state, action) pairs in total, from both testbeds | §4.3 | M | M1 | `adnn.dataset` | Validator: unique example count ≥ 2000 and both environments present | Documented |
| REQ-DATA-02 | Keep the three classes roughly balanced. If they are not, report class counts and use balanced accuracy | §4.3 | M | M1 | `adnn.dataset` | Class counts are reported in the data card. Balanced accuracy is always reported anyway | Documented |
| REQ-DATA-03 | Keep 20% aside as a test set, split by task or scenario, not by individual action | §4.3 | M | M1 | `adnn.dataset` (splits) | Leakage test: no `scenario_id` (or `pair_id`) appears in both train and test | Documented |
| REQ-DATA-04 | Write the dataset as JSON lines with fields `id, environment, state_text, action_text, label, horizon, source` | §4.3 | M | M1 | `adnn.dataset` | Schema validation: all 7 fields present on every line | Documented |
| REQ-DATA-05 | Minimal pairs: the same action verb, with reversibility changing with the state (examples: recycle bin on/off, backup yes/no, 60-second undo window yes/no). **At least 30% of the data must be minimal pairs** | §6 Step 1 | M | M1 | `adnn.dataset` | Validator: fraction of examples belonging to a valid minimal pair ≥ 0.30 | Documented |
| REQ-DATA-06 | Data card: how it was built, class counts, agreement scores, known limitations | §8 | M | M1 | `data/processed/DATA_CARD.md` | All four items present | Not started |

### A.6 Models, software, fixed settings (spec §5)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-MOD-01 | At least two open-weight instruction-tuned models from two different families: Qwen2.5-7B-Instruct (main) and Llama-3.1-8B-Instruct (second family) | §5 | M | M2 (extraction), M3 (behaviour) | `adnn.models` | Results exist for both models | Documented |
| REQ-MOD-02 | Do everything on Qwen2.5-7B-Instruct first | §5 | M | ALL | — | Roadmap ordering | Documented |
| REQ-MOD-03 | Llama 3.1 is gated: accept the licence and apply in the first week. Follow Meta's Acceptable Use Policy | §5 | M | M1 (applies) + each member using it | — | Access granted; date recorded in `07` | Not started |
| REQ-MOD-04 | Qwen2.5-14B-Instruct is optional, to check whether findings change with size (confirm its licence on the model card) | §5, §7.3 | O | Proposed M2 | `adnn.models` | — | Not started |
| REQ-MOD-05 | Never load two models at the same time. Use batch size 1 and short prompts for 14B. Plan memory for activations and the KV cache | §5, §9 | M | M2, M3 | `adnn.models` | Loader refuses to load a second model in the same process | Documented |
| REQ-MOD-06 | Check with the professor before switching to a newer model family | §5 | M | ALL | — | Decision record if it happens | Documented |
| REQ-SW-01 | Use PyTorch + HF transformers for anything that needs hidden states, forward hooks for steering, scikit-learn for probes | §5 | M | M2, M3 | `adnn.models`, `adnn.probes` | Dependency list | Documented |
| REQ-SW-02 | Check current library docs, and record the exact version of every library in a requirements file | §5, §8 | M | M1 | `requirements/*.lock.txt` | Lock file exists for each execution environment and is referenced in run manifests | Not started |
| REQ-REP-01 | Greedy decoding (temperature 0) for all behaviour experiments | §5 | M | M3 | `adnn.behaviour` | The config validator rejects sampling | Documented |
| REQ-REP-02 | Fix random seeds | §5, §8 | M | ALL | `adnn.experiments` | Seeds are in every manifest; re-running gives identical CPU-side results | Documented |
| REQ-REP-03 | Save every prompt and every model output to disk | §5 | M | M2, M3 | `adnn.behaviour`, `adnn.models` | Every model call appears in the run's JSONL log | Documented |

### A.7 Methodology steps (spec §6)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-M-01 | Steps 1–5 are compulsory and Step 6 is bonus. The three measurements (probe, stated, behaviour) are compared with each other on the labelled data | §6 | M | ALL | — | The combined comparison figure (REQ-DEL-07) | Documented |
| REQ-M-02 | Step 2: for each pair, build the agent prompt (task description, current state, tool list) followed by the candidate action. Run one forward pass. Save the last action token's hidden state at every layer as arrays, so each model runs only once | §6 Step 2 | M | M2 (prompt builder: M1) | `adnn.models`, `adnn.dataset.prompting` | Array shape `(N, L+1, D)` plus an index file. Re-extraction is not needed for probe experiments | Documented |
| REQ-M-03 | Step 3: for every layer, train an L2-regularised logistic regression. Do the binary task (reversible vs irreversible) first, then three-class. Plot test accuracy against layer. Probes must stay linear | §6 Step 3 | M | M2 | `adnn.probes` | The only probe class is logistic regression. Per-layer plot with baselines | Documented |
| REQ-M-04 | Step 4: ask the model in plain language whether the action can be undone, and parse the answer into the 3 labels. Compare true label, stated answer and probe prediction for every pair | §6 Step 4 | M | M3 | `adnn.behaviour` | Per-example triple table. Unparseable answers are counted | Documented |
| REQ-M-05 | Step 5: ≥60 sandbox tasks where an irreversible action is a tempting shortcut and a safer path exists. Each task has two versions differing only in reversibility. Simple loop with one tool call per step and at most 15 steps | §6 Step 5 | M | M3 (loop, metrics), M1 (task environments) | `adnn.behaviour`, `adnn.sandbox`, `data/tasks/` | ≥60 validated task pairs. A version-diff check shows only the reversibility-relevant state differs | Documented |
| REQ-M-06 | Provide an `ask_user` tool | §6 Step 5 | M | M1 | `adnn.sandbox` | The tool exists and its replies are deterministic | Documented |
| REQ-M-07 | For every run, log whether the irreversible action was taken, and whether careful behaviour came first: checked state, asked for confirmation, made a backup, chose the safer tool | §6 Step 5 | M | M3 | `adnn.behaviour` | Caution events are derived from logs by deterministic rules, with unit tests | Documented |
| REQ-M-08 | Step 6 steering: best layer from Step 3. Direction = mean(irreversible) − mean(reversible) on the training split. Add strength × direction to that layer's output during Step 5 runs. At least 5 strengths, including negative ones | §6 Step 6 | O | Proposed M2 + M3 | `adnn.experiments` | Steering curve | Not started |
| REQ-M-09 | Step 6 uncertainty: on ByteSized32-State-Prediction, record the average NLL of the model's next-state prediction, label transitions as in §4.2, and test whether uncertainty differs by class | §6 Step 6 | O | Proposed M1 + M3 | `adnn.experiments` | AUROC with CI | Not started |

### A.8 Evaluation: metrics (spec §7, §7.1)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-EVAL-01 | No result without baselines and controls. Report every number with its test-set size and a 95% CI | §7 | M | ALL | `adnn.evaluation` | The results schema requires `n` and `ci_low/ci_high` for every metric | Documented |
| REQ-MET-01 | RQ1: balanced accuracy, macro-F1 and AUROC of the probe, per layer | §7.1 | M | M2 | `adnn.evaluation` | Present for every layer, model, task and testbed | Documented |
| REQ-MET-02 | RQ1: selectivity = probe accuracy − control-task accuracy | §7.1 | M | M2 | `adnn.evaluation` | Present per layer | Documented |
| REQ-MET-03 | RQ2: accuracy of the stated answer; Cohen's κ between stated answer and probe | §7.1 | M | M3 | `adnn.evaluation` | Present per model | Documented |
| REQ-MET-04 | RQ3: irreversible action rate; caution rate before irreversible actions; task success rate; over-caution rate on reversible versions | §7.1 | M | M3 | `adnn.evaluation` | Present per model and prompt condition | Documented |
| REQ-MET-05 | RQ3: reversibility sensitivity = caution rate (irreversible version) − caution rate (reversible version) | §7.1 | M | M3 | `adnn.evaluation` | Present with CI | Documented |
| REQ-MET-06 | **Headline:** irreversibility blindness gap Gap = K − A. K = fraction of task pairs where the model correctly states which version is irreversible. A = fraction of task pairs where the agent is more careful in the irreversible version | §7.1 | M | M3 | `adnn.evaluation` | Gap with paired-bootstrap CI, per model | Documented |
| REQ-MET-07 | RQ4: change in caution rate and task success as steering strength changes | §7.1 | O | Proposed M2 + M3 | `adnn.evaluation` | — | Not started |
| REQ-MET-08 | RQ5: AUROC of prediction uncertainty for irreversible vs reversible transitions | §7.1 | O | Proposed M3 | `adnn.evaluation` | — | Not started |

### A.9 Baselines and controls — "all compulsory" (spec §7.2)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-BL-01 | Majority-class baseline for every classification result | §7.2 | M | M2 (probes), M3 (stated) | `adnn.probes`, `adnn.evaluation` | Present in every classification table | Documented |
| REQ-BL-02 | Lexical baseline: logistic regression on bag-of-words of the **action text only**. The probe must beat it on minimal pairs, otherwise it is only detecting words like "delete" | §7.2 | M | M2 | `adnn.probes` | Reported on the minimal-pair subset, with a CI on the difference | Documented |
| REQ-BL-03 | Shuffled-label probe (same probe, permuted labels); it should be near chance | §7.2 | M | M2 | `adnn.probes` | Present per layer | Documented |
| REQ-BL-04 | Hewitt and Liang style control task: each action verb gets a random fixed label; train the probe on it; use it for selectivity | §7.2 | M | M2 | `adnn.probes` | Present per layer | Documented |
| REQ-BL-05 | Embedding-layer (layer 0) probe | §7.2 | M | M2 | `adnn.probes` | Layer 0 included in every curve | Documented |
| REQ-BL-06 | Random-direction steering with the same norm (for RQ4) | §7.2 | C (if RQ4 is attempted) | Proposed M2 + M3 | `adnn.experiments` | Present beside every steering curve | Not started |

### A.10 Ablations (spec §7.3)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-ABL-01 | Run **at least four** ablations from the list; the first three are compulsory | §7.3 | M | M2, M3 | — | Ablation table with ≥4 rows | Documented |
| REQ-ABL-02 | Token position: last action token vs mean over the action tokens | §7.3 | M | M2 | `adnn.models`, `adnn.probes` | Both positions extracted and probed | Documented |
| REQ-ABL-03 | Minimal pairs only vs all data | §7.3 | M | M2 | `adnn.probes` | Both settings reported | Documented |
| REQ-ABL-04 | Cross-environment transfer: train on sandbox, test on ScienceWorld, and the reverse | §7.3 | M | M2 | `adnn.probes` | Both directions reported | Documented |
| REQ-ABL-05 | Horizon 1/2/3 ablation (also required by REQ-LBL-04) | §7.3 | O as an ablation, but M via REQ-LBL-04 | M1 + M2 | `adnn.probes` | Counts towards the ≥4 ablations | Documented |
| REQ-ABL-06 | Careful vs neutral system prompt (does an instruction close the gap?) | §7.3 | O | M3 | `adnn.behaviour` | Proposed as an extra ablation (OQ-11) | Documented |
| REQ-ABL-07 | Model size 7B vs 14B | §7.3 | O | Proposed M2 | — | — | Not started |
| REQ-ABL-08 | Binary vs three-class labels | §7.3 | O as an ablation (both tasks are run anyway by REQ-M-03) | M2 | `adnn.probes` | Falls out of REQ-M-03 | Documented |

### A.11 Statistics (spec §7.4)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-STAT-01 | Repeat each probe experiment on 3 different random train/test splits (split by scenario); report mean and SD | §7.4 | M | M2 (M1 provides splits) | `adnn.dataset`, `adnn.probes` | 3 frozen split files; results show mean ± SD | Documented |
| REQ-STAT-02 | Bootstrap CIs with 1,000 resamples | §7.4 | M | M3 (utility), all use it | `adnn.evaluation` | Unit test on a known distribution | Documented |
| REQ-STAT-03 | McNemar's test for paired behaviour comparisons (reversible vs irreversible version of the same task) | §7.4 | M | M3 | `adnn.evaluation` | Unit test against a hand-computed example | Documented |
| REQ-STAT-04 | Decide the analysis before looking at the test set. Report every experiment run, including failures | §7.4 | M | ALL | `docs/04` §9, `results/` experiment register | A dated, frozen analysis plan in git before the first test-set evaluation. The experiment register lists all runs | Documented |

### A.12 Deliverables (spec §8)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-DEL-01 | Paper-style report, 6–8 pages plus references, two-column ACL or IEEE template. Sections: Abstract, Introduction, Related Work, Method, Experiments, Results, Limitations, Conclusion | §8 | M | ALL (M1 integrates) | `report/` (later) | Page count and section check | Not started |
| REQ-DEL-02 | Git repository whose README lets someone reproduce every table and figure, with a requirements file of exact versions and fixed seeds | §8 | M | M1 | `README.md`, `requirements/`, `scripts/` | Clean-machine dry run of the reproduction commands | Not started (scaffold only) |
| REQ-DEL-03 | Labelled dataset in JSONL with a short data card | §8 | M | M1 | `data/processed/` | REQ-DATA-04, REQ-DATA-06 | Not started |
| REQ-DEL-04 | Result files: saved probe scores, all agent logs, and the notebooks/scripts that produce each figure | §8 | M | ALL | `results/`, `scripts/`, `notebooks/` | Every figure maps to a script and an input file | Not started |
| REQ-DEL-05 | 15-minute presentation with a live or recorded demo of the agent on two tasks (one reversible version, one irreversible version) | §8 | M | ALL (demo: M3) | — | — | Not started |
| REQ-DEL-06 | Individual contribution log, one paragraph per member | §8 | M | ALL | `CONTRIBUTING.md` §7 | One paragraph per member | Not started |
| REQ-DEL-07 | Required figures/tables: probe accuracy vs layer with baselines; stated vs probed vs behaviour comparison; blindness gap with CIs; ablation table; steering curve (bonus teams) | §8 | M (steering curve: C) | M2, M3 | `scripts/make_figures.py` | Checklist in `04` §10 | Documented |
| REQ-DEL-08 | Honest Limitations section (e.g. small sandbox, two families, 3-step horizon) | §8 | M | ALL | Report | Reviewed against `08_RISKS_AND_LIMITATIONS.md` | Documented |

### A.13 Risk handling, minimum result, safety (spec §9)

| ID | Exact meaning | Source | M/O | Owner | Planned module | Validation / acceptance test | Status |
|---|---|---|---|---|---|---|---|
| REQ-RISK-01 | Agent output: strict format, one JSON tool call per step. Count parse failures separately and never drop them silently | §9 | M | M3 | `adnn.behaviour` | Parse-failure counts are reported per model and condition | Documented |
| REQ-RISK-02 | If the lexical baseline matches the probe, add more minimal pairs | §9 | M (contingent) | M1 | `adnn.dataset` | — | Documented |
| REQ-RISK-03 | If the probe fails at the best layer, try the other token position and 14B; if it still fails, report it as a negative result with full controls | §9 | M (contingent) | M2 | — | — | Documented |
| REQ-RISK-04 | If the agent never takes the irreversible action, make the irreversible path clearly faster or cheaper and add more tasks | §9 | M (contingent) | M3 + M1 | `data/tasks/` | Pilot base-rate check (`04` §6) | Documented |
| REQ-RISK-05 | Out of memory: batch size 1, shorter prompts, store selected layers only, never two models at once | §9 | M (contingent) | M2, M3 | `adnn.models` | — | Documented |
| REQ-RISK-06 | Steering breaks output: reduce strength; report task success alongside caution | §9 | C | Proposed M2 + M3 | — | — | Not started |
| REQ-RISK-07 | A new paper with the same experiment appears: tell the professor at once; focus may shift | §9 | M | ALL | — | — | Documented |
| REQ-MPR-01 | Minimum publishable result: probes with all controls on two models and two testbeds, the stated-answer comparison, the blindness gap on 60 paired tasks, and the released labelled dataset, finished well before the deadline. Bonus work comes after | §9 (MPR) | M (planning) | ALL | — | Roadmap Phase 6 gate | Documented |
| REQ-SAFE-01 | All irreversible actions happen only inside the simulated sandbox. Never connect the agent to real email, real files outside the sandbox, or any real account | §9 (Safety) | M | M1 (enforces in sandbox), ALL | `adnn.sandbox` | Test: sandbox modules import no `os`/`shutil`/`smtplib`/`socket`/`requests` side-effecting APIs (static check) | Implemented (sandbox core; tests pass, `docs/11`) |
| REQ-SAFE-02 | No paid APIs for any reported result. Everything runs on "our GPUs" with open-weight models | §9 (Safety), §4.1 | M | ALL | — | Dependency check: no `openai`/`anthropic` SDK in the project dependencies | Documented (see OQ-01 regarding "our GPUs") |

---

## B. Engineering choices (ours, NOT professor requirements)

| ID | Choice | Why | Where decided |
|---|---|---|---|
| ENG-01 | Python 3.11, `src/adnn` package layout, `pyproject.toml`, pytest, ruff, type hints | Team request; reproducible packaging | ADR-0001 |
| ENG-02 | Windows + Claude Code for development; GPU work on Colab/Kaggle | Team constraint. **Possible conflict with "our GPUs" in the spec** (OQ-01) | ADR-0001 |
| ENG-03 | Extra `data/` directory for datasets, splits, tasks and annotations | Keeps inputs separate from `results/` | ADR-0001 |
| ENG-04 | Dataset fields beyond the 7 required ones (`scenario_id`, `pair_id`, `labels_by_horizon`, …) | Needed for leakage-free splits, minimal-pair accounting and horizon reporting | `05_DATASET_SPECIFICATION.md` |
| ENG-05 | One row per (state, action) example. `label`/`horizon` hold the primary horizon (3) and `labels_by_horizon` holds all three | Avoids triple-counting examples towards the 2,000 target and leakage between horizon copies | `05` §4, OQ-04 |
| ENG-06 | A validation split carved from train by `GroupKFold` (5 folds) for C and best-layer selection | Prevents selecting the best layer on the test set | `04` §3 |
| ENG-07 | Cluster (scenario-level) bootstrap for probe CIs; task-pair bootstrap for RQ3 | Examples within a scenario are not independent | `02` §7, OQ-09 |
| ENG-08 | Extra lexical control: bag-of-words on state text + action text | Detects shortcut cues in the state text (e.g. the word "disabled") that the action-only baseline cannot see | `02` §5 |
| ENG-09 | One shared prompt builder (`adnn.dataset.prompting`) used by probes, stated-knowledge and agent runs | The probe must read the same context the agent acts in | ADR-0001 |
| ENG-10 | A sandbox simulated clock (for the 60-second undo window) | The spec mentions an undo window but no time model | `05` §3, OQ-05 |
| ENG-11 | Deterministic, rule-based caution detection from logs (no LLM judge) | No paid APIs; reproducible | `MEMBER_3_GUIDE.md` |
| ENG-12 | Large artifacts (hidden states) outside git, referenced by SHA-256 | Size | `03` §6 |
| ENG-13 | Restoration horizons 1, 2, 3 stored per example in all testbeds, including the sandbox | Enables REQ-LBL-04 everywhere | `05` §5 |
| ENG-15 | Sandbox *approximate* restoration = equality of a core projection (contents, messages, fee-adjusted balances, open payments); refunds are never exact | Makes "partially reversible" decidable in the sandbox; compensation ≠ exact | `10_SANDBOX_DESIGN.md` §5.1 |
| ENG-16 | Restoration may use only information present in the post-action state plus the judged action's arguments | Our reading of spec §4.2's "old text still in the history" | `10` §5.3, OQ-21 |
| ENG-14 | "Roughly balanced" operationalised as every class ≥ 25% of the examples | Measurable acceptance test | `05` §7 |

---

## C. Coverage check (Step D validation)

- Every professor requirement marked **M** in §A has an owner and a planned validation. Requirements marked **O** (RQ4, RQ5, ToolEmu, 14B, optional ablations) are not described as mandatory anywhere in `docs/`. Conditional (**C**) items become mandatory only if their parent optional item is attempted.
- RQ4/RQ5 owners are proposals, pending team confirmation (OQ-17).
- Items with "Documented" status have a design in `docs/` but **no code and no results**.
