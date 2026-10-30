# 01 — Problem Statement

## 1. Background and motivation

LLM-based agents now take real actions: they run commands, edit files, send messages, move money and call tools. Some of these actions can be undone and some cannot (spec §1). Opening a file changes nothing that matters. Editing a file can be undone if a backup exists. Deleting a file without a recycle bin, sending an email, or completing a bank transfer cannot be taken back.

A careful human treats these actions differently. Before an irreversible step we slow down, check again, make a backup or ask for confirmation. If agents do not do the same, any mistake they make on an irreversible action is permanent. That makes reversibility awareness a basic, measurable safety property of agents.

Two separate questions are hidden in "does the agent know?":

1. **Representation.** Does the model internally encode whether a candidate action is reversible *in the current state*?
2. **Use.** If it does, does that knowledge reach action selection, so that the agent behaves more carefully before irreversible actions?

These can come apart. A model may say "deleting is permanent" when asked, and still delete without hesitation when acting.

## 2. Formal problem statement

**Environment.** An environment has a state space $S$, an action set $A$ and a deterministic transition function $T: S \times A \to S$. The project uses two such environments: our tool sandbox and ScienceWorld.

**Restoration depth.** For a state $s$ and action $a$, let $s' = T(s,a)$. The restoration depth $d(s,a)$ is the length of the shortest action sequence $(a_1,\dots,a_k)$ that takes $s'$ back to a state equal to $s$. If no such sequence exists, $d(s,a) = \infty$.

**Labels at horizon $h$** (spec §4.2, $h \in \{1,2,3\}$, primary $h=3$):

- $\text{reversible}_h$ if $d(s,a) \le h$;
- $\text{partially\_reversible}_h$ if not reversible within $h$, but some sequence of length $\le h$ reaches a state *approximately* equal to $s$, or restores $s$ only at a cost. The exact approximation criterion is testbed-specific and partly open (OQ-03);
- $\text{irreversible}_h$ otherwise.

**Model and measurements.** Let $M$ be an instruction-tuned LLM. Given an agent prompt $x(s, a)$ (task, rendered state, tool list, candidate action $a$), let $\mathbf{h}_\ell(x) \in \mathbb{R}^D$ be the residual-stream hidden state at layer $\ell$ for the last token of $a$. The project measures three things on the same labelled data:

- **Probed knowledge (RQ1).** How well a linear classifier $g_\ell(\mathbf{h}_\ell) = \text{softmax}(W\mathbf{h}_\ell + b)$ predicts $y_h(s,a)$. Compare against controls that rule out lexical shortcuts and probe memorisation.
- **Stated knowledge (RQ2).** The label $\hat y^{\text{stated}}$ parsed from $M$'s answer to the plain question "can this action be undone?", and its agreement with $y$ and with the probe.
- **Behaviour (RQ3).** In paired tasks $(\tau^{\text{rev}}, \tau^{\text{irr}})$ that differ only in the reversibility of a tempting shortcut action, whether $M$ acting as an agent shows caution (check, confirm, backup, safer tool, refuse) more often in $\tau^{\text{irr}}$.

## 3. Irreversibility blindness

The spec (§1) defines **irreversibility blindness** as the case where the model can state that an action is permanent, but still takes it without hesitation when acting. It is quantified by the headline metric (spec §7.1):

$$\text{Gap} = K - A$$

- $K$: the fraction of task pairs in which the model correctly states which version is irreversible;
- $A$: the fraction of task pairs in which the agent is actually more careful in the irreversible version.

A large positive gap means the model knows but does not act on it. A gap near zero is compatible with two very different situations: the model knows and acts (both high), or neither knows nor acts (both low). So $K$ and $A$ are always reported alongside the gap. The precise operationalisation of "correctly states which version is irreversible" and "more careful" is in `04_EXPERIMENTAL_PROTOCOL.md` §6. The open choices are in OQ-07 and OQ-08.

## 4. Research gap — as proposed by the professor (REQUIRES VERIFICATION)

> **Status: NOT VERIFIED BY US.** The text below restates the professor's claim. We have not yet done the literature search required by REQ-LIT-04. Do not repeat this claim in the report until the novelty search log in `references/README.md` is complete.

According to the spec (§1, §3):

- Reversibility has been studied in classical reinforcement learning. The spec cites Grinsztajn et al. (NeurIPS 2021) and, in Group B, side-effect penalties (Krakovna et al.; Turner et al.).
- Agent safety benchmarks such as ToolEmu and SafeAgentBench test risky actions *in general*.
- The spec calls Tang et al., "LM Agents May Fail to Act on Their Own Risk Knowledge" (COLM 2025) the closest work. Per the spec, it shows a knowledge–action gap for risky actions in general, **not** for reversibility specifically.
- The professor states, "to the best of my knowledge", that no published work tests whether LLM agents *internally* distinguish reversible from irreversible actions and whether this reaches action selection.

Our candidate contributions, if the gap holds up:

1. a reversibility dataset with state-dependent minimal pairs;
2. probing with full controls;
3. a three-way comparison of probed, stated and enacted knowledge.

None of these has been checked against the literature yet. If an identical experiment is found, the professor must be told immediately (REQ-LIT-04, REQ-RISK-07). The spec suggests the focus may then shift to the minimal-pair design or the steering result.

## 5. Research questions

| RQ | Question (spec §2) | Status in this project |
|---|---|---|
| RQ1 | Can reversibility be decoded from the model's hidden states with a simple linear probe? At which layers is it strongest? | **Compulsory** |
| RQ2 | When asked directly, does the model correctly say whether an action is reversible? Does this stated answer agree with the probe? | **Compulsory** |
| RQ3 | During task execution, does the model behave more carefully before irreversible actions (confirming, checking, refusing, choosing a safer alternative)? | **Compulsory** |
| RQ4 | If we push the hidden state along the probe's "irreversible" direction (activation steering), does the agent become more careful? (causal test) | **Optional — bonus only**; not part of the initial implementation |
| RQ5 | Is the model's uncertainty about the next state related to how reversible the action is? | **Optional — bonus only**; not part of the initial implementation |

## 6. Hypotheses and possible negative findings

These hypotheses are **not** predictions we are committed to. The spec says: "Do not decide the finding in advance. Let the data decide." Every hypothesis below has a pre-stated "negative" reading that will be reported just as fully as a positive one.

| ID | Hypothesis | Evidence that supports it | Negative / alternative finding we would report |
|---|---|---|---|
| H1a | Binary reversibility is linearly decodable above all controls at some layer | Balanced accuracy CI above the majority, shuffled-label and layer-0 baselines; positive selectivity; probe beats the action-only lexical baseline **on minimal pairs** | Probe ≈ lexical baseline on minimal pairs, meaning it only detects verbs. Or the probe fails at every layer even after the REQ-RISK-03 fallbacks |
| H1b | Decodability peaks at middle layers rather than at layer 0 or the final layer | Per-layer curve shape across 3 splits and both models | The peak is at the embedding layer (lexical) or is flat/noisy across layers |
| H1c | The representation transfers across testbeds | Cross-environment probe above chance in both directions | Transfer fails, so the encoding is environment-specific |
| H2 | The model states reversibility correctly more often than chance, and its stated answer agrees with the probe ($\kappa > 0$) | Stated accuracy CI above majority; κ CI excludes 0 | The model states correctly but κ with the probe ≈ 0, or the model fails at stating while the probe succeeds |
| H3 | Agent caution is higher in irreversible versions (positive reversibility sensitivity) | Sensitivity CI above 0; McNemar significant | No difference: behaviour ignores reversibility |
| H4 | Blindness: $K > A$ | Gap CI above 0 | Gap ≈ 0 with K, A both high (no blindness), or both low (no knowledge either) |

**Possible confounders that could produce false positives**, all addressed in `02_RESEARCH_METHODOLOGY.md` §6:

- lexical cues in the action text;
- lexical cues in the state text (e.g. "recycle bin: disabled");
- scenario memorisation through split leakage;
- caution that is caused by task phrasing rather than by reversibility;
- parse failures being mistaken for refusals.

## 7. Scope and limitations

**In scope:**

- RQ1–RQ3 on Qwen2.5-7B-Instruct, then Llama-3.1-8B-Instruct;
- our sandbox and ScienceWorld;
- ≥2,000 labelled examples with ≥30% minimal pairs;
- ≥60 paired agent tasks;
- all controls in spec §7.2 (except the RQ4-only control) and at least four ablations.

**Out of scope for the initial implementation:**

- RQ4 (steering) and RQ5 (uncertainty);
- the 14B model;
- ToolEmu case labelling (recommended, optional);
- building a new agent architecture or a large new environment (spec §4);
- any real external action or paid API (spec §9 Safety).

**Known limitations, stated in advance** (spec §8 asks for honesty here):

- a small, hand-designed sandbox whose labels reflect our design choices;
- only two model families of similar size;
- a maximum restoration horizon of 3;
- ScienceWorld labels computed by a *bounded, possibly pruned* search, so "irreversible" there means "not restored within the searched space" (see `08` §4);
- greedy decoding means one trajectory per task version, which limits the behavioural sample size to the number of task pairs;
- linear probes test only for *linearly accessible* information. The spec reminds us (Othello-GPT note) that some world representations are non-linear, so a negative probe result does not prove absence of the information.
