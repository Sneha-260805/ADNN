"""Seeded sampling and evidence collection for provisional ScienceWorld records (docs/21).

Pipeline (Phase 4E, no labels):

1. :func:`sample_family` walks verified agent-accessible histories from an explicit
   task/variation (never a random-variation API), with a per-sample RNG derived from
   ``(seed, family_id, sample_index)``. Every history action must be in the
   valid-action list, refer to exactly one template, be accepted and have an observed
   discrete effect. Load/reset is a researcher operation and is never an agent action.
   Duplicate (state, action) pairs are rejected. A *sibling* adds one contrast action
   to a sampled history and keeps the same target text, to seek candidate minimal pairs.
2. :func:`collect_evidence` reruns the Phase 4D restricted inverse diagnostic for the
   example (verified reconstruction, time-matched counterfactual, temperature
   comparisons at exact / 0.01 / 0.1 degC) and builds an evidence record.
3. :func:`run_pilot` writes records, state files, candidate pairs, rejections,
   performance and a validation report to an output directory.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from adnn.scienceworld.canonical import CapturedState, capture_state
from adnn.scienceworld.diagnostics import (
    DISCRETE_EXPLORATION,
    TEMPERATURE_SENSITIVITY,
    projection_diff,
)
from adnn.scienceworld.env import ActionTemplate, Backend, ScienceWorldSession
from adnn.scienceworld.provenance import RuntimeConfig
from adnn.scienceworld.provisional import (
    IDLE_ACTION,
    PILOT_FAMILIES,
    PREFIX_CLASSES,
    RULE_COVERED_CLASSES,
    TARGET_CLASSES,
    FamilySpec,
    HistoryStep,
    SampledExample,
    build_record,
    discover_candidate_pairs,
    discrete_fingerprint,
    door_exclusion_reason,
    jsonl_bytes,
    load_state_file,
    state_document,
    state_file_name,
    validate_dataset,
    verb_class,
)
from adnn.scienceworld.replay import (
    EpisodeTerminatedError,
    InvalidReplayActionError,
    ReplayDivergenceError,
    ReplayRecipe,
    TraceComparison,
    run_recipe,
)
from adnn.scienceworld.restoration_diagnostics import InverseExperiment, run_inverse_experiment

SAMPLER_VERSION = "sw-provisional-sampler-0.1"


@dataclass(frozen=True)
class SamplerConfig:
    seed: int = 20261031
    families: tuple[FamilySpec, ...] = PILOT_FAMILIES
    base_samples_per_family: int = 8
    max_attempts_per_family: int = 30
    max_prefix: int = 3
    target_tries: int = 3
    sibling_rate: float = 0.75
    contrast_tries: int = 3
    max_paths: int = 4
    rule_class_weight: int = 2  # classes covered by an inverse rule are drawn twice as often

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["families"] = [f.to_dict() for f in self.families]
        return d


def sample_rng(seed: int, family_id: str, index: int) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{family_id}:{index}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


@dataclass
class SamplingLog:
    rows: list[dict[str, Any]] = field(default_factory=list)

    def reject(self, family: str, index: int, stage: str, reason: str, **extra: Any) -> None:
        self.rows.append({"family_id": family, "sample_index": index, "stage": stage,
                          "reason": reason, **extra})  # fmt: skip

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.rows:
            key = f"{r['stage']}:{r['reason']}"
            out[key] = out.get(key, 0) + 1
        return dict(sorted(out.items()))


def unambiguous_templates(templates: list[ActionTemplate]) -> tuple[dict[str, ActionTemplate], int]:
    """Valid actions whose text resolves to exactly one template (and the ambiguous count)."""
    groups: dict[str, list[ActionTemplate]] = {}
    for t in templates:
        groups.setdefault(t.action, []).append(t)
    single = {a: ts[0] for a, ts in groups.items() if len({t.obj_ids for t in ts}) == 1}
    return single, len(groups) - len(single)


def _pool(
    by_text: dict[str, ActionTemplate], state: CapturedState, classes: frozenset[str]
) -> tuple[dict[str, list[str]], int]:
    """Candidate actions grouped by verb class, sorted, door/portal actions removed (RD-05)."""
    pool: dict[str, list[str]] = {}
    n_door = 0
    for action in sorted(by_text):
        cls = verb_class(action)
        if cls not in classes:
            continue
        if door_exclusion_reason(action, by_text[action].obj_ids, state.canonical):
            n_door += 1
            continue
        pool.setdefault(cls, []).append(action)
    return pool, n_door


def _effective_step(
    session: ScienceWorldSession, action: str, before: CapturedState
) -> tuple[str | None, CapturedState, int]:
    """Step ``action`` from ``before`` (already captured); return (reason or None, after, ticks).

    No query is issued between the caller's last valid-action query and the step, because a
    query can change referent text (OQ-38, docs/21 section 3.2).
    """
    result = session.step(action)
    after = capture_state(session)
    ticks = result.moves_after - result.moves_before
    if result.status != "accepted":
        return f"status_{result.status}", after, ticks
    if result.done:
        return "episode_ended", after, ticks
    effect = projection_diff(before.canonical, after.canonical, DISCRETE_EXPLORATION)
    if effect.equal_on_observed_fields:
        return "no_observed_discrete_effect", after, ticks
    return None, after, ticks


def _divergence(what: str) -> ReplayDivergenceError:
    return ReplayDivergenceError(TraceComparison(False, None, (what,), 0))


class _Sampler:
    def __init__(
        self, session: ScienceWorldSession, config: SamplerConfig, log: SamplingLog
    ) -> None:
        self.session, self.config, self.log = session, config, log
        self.seen: set[tuple[str, str]] = set()

    def _duplicate(self, state: CapturedState, action: str) -> str | None:
        exact = (f"c:{state.canonical.fingerprint}", action)
        loose = (f"d:{discrete_fingerprint(state.canonical)}", action)
        if exact in self.seen:
            return "duplicate_state_action"
        if loose in self.seen:
            return "duplicate_discrete_state_action"
        return None

    def _remember(self, state: CapturedState, action: str) -> None:
        self.seen.add((f"c:{state.canonical.fingerprint}", action))
        self.seen.add((f"d:{discrete_fingerprint(state.canonical)}", action))

    def clean_state(
        self, family: FamilySpec, recipe: ReplayRecipe, expected: CapturedState | None = None
    ) -> tuple[list[HistoryStep], CapturedState, dict[str, ActionTemplate]]:
        """Rebuild ``recipe`` under the fixed query protocol (docs/21 §3.2).

        Load, run every recipe action with no interleaved queries, then ``capture_state``,
        then ``valid_action_templates``. ScienceWorld's valid-action referent text depends
        on which free queries were made earlier in the episode, so S0, its valid-action
        list and the target text are only ever taken from this protocol, which is also
        the order used by :func:`replay` and the restoration diagnostic.
        """
        _, steps, _ = run_recipe(self.session, recipe, strict=True)
        state = capture_state(self.session)
        if expected is not None and state.raw.fingerprint != expected.raw.fingerprint:
            raise _divergence("raw_state(sampler rebuild)")
        by_text, _ = unambiguous_templates(self.session.valid_action_templates())
        n_prep, n_base = len(recipe.preparation), len(family.base_actions)
        phases = ["preparation"] * n_prep + ["base"] * n_base
        history = [
            HistoryStep(s.result.action, phases[i] if i < len(phases) else "prefix",
                        s.result.status, s.result.moves_after - s.result.moves_before)
            for i, s in enumerate(steps)
        ]  # fmt: skip
        return history, state, by_text

    def _choose_target(
        self, rng: random.Random, state: CapturedState, by_text: dict[str, ActionTemplate],
        exclude: set[str],
    ) -> tuple[ActionTemplate, str, int] | None:  # fmt: skip
        pool, n_door = _pool(by_text, state, TARGET_CLASSES)
        pool = {c: [a for a in acts if a not in exclude] for c, acts in pool.items()}
        classes = sorted(c for c, acts in pool.items() if acts)
        if not classes:
            return None
        weights = [
            self.config.rule_class_weight if c in RULE_COVERED_CLASSES else 1 for c in classes
        ]
        cls = rng.choices(classes, weights=weights)[0]
        action = rng.choice(pool[cls])
        return by_text[action], cls, n_door

    def walk(
        self, family: FamilySpec, prefix: tuple[str, ...], *, allow_idle: bool = False
    ) -> str | None:
        """Execute ``prefix`` after the base recipe; reason for rejection, or None.

        With ``allow_idle``, :data:`IDLE_ACTION` steps are tick-matching padding: they must be
        accepted and take exactly one tick, but need no observed effect (docs/22 §3).
        """
        run_recipe(self.session, family.base_recipe(), strict=True)
        state = capture_state(self.session)
        for action in prefix:
            if allow_idle and action == IDLE_ACTION:
                r = self.session.step(action)
                if r.status != "accepted" or r.moves_after - r.moves_before != 1:
                    return f"idle_padding_{r.status}"
                state = capture_state(self.session)
                continue
            reason, state, _ = _effective_step(self.session, action, state)
            if reason:
                return reason
        return None

    def sample(self, family: FamilySpec) -> list[SampledExample]:
        cfg, out, n_base = self.config, [], 0
        base = family.base_recipe()
        for index in range(cfg.max_attempts_per_family):
            if n_base >= cfg.base_samples_per_family:
                break
            rng = sample_rng(cfg.seed, family.family_id, index)
            # exploration: free queries are allowed here; S0 is re-derived cleanly below
            run_recipe(self.session, base, strict=True)
            state = capture_state(self.session)
            prefix: list[str] = []
            failure = failed_action = None
            for _ in range(rng.randint(0, cfg.max_prefix)):
                by_text, _ = unambiguous_templates(self.session.valid_action_templates())
                pool, _ = _pool(by_text, state, PREFIX_CLASSES)
                options = [a for c in sorted(pool) for a in pool[c]]
                if not options:
                    failure = "empty_prefix_pool"
                    break
                action = rng.choice(options)
                reason, state, _ = _effective_step(self.session, action, state)
                if reason:
                    failure, failed_action = f"prefix_{reason}", action
                    break
                prefix.append(action)
            if failure:
                self.log.reject(family.family_id, index, "history", failure, prefix=prefix,
                                action=failed_action)  # fmt: skip
                continue
            recipe = base.extend(*prefix)
            try:
                history, s0, by_text = self.clean_state(family, recipe)
            except (InvalidReplayActionError, EpisodeTerminatedError) as exc:
                self.log.reject(family.family_id, index, "history", "not_replayable_under_protocol",
                                prefix=prefix, detail=str(exc)[:160])  # fmt: skip
                continue
            example = self._target_for(family, index, rng, recipe, history, s0, by_text)
            if example is None:
                continue
            out.append(example)
            n_base += 1
            if rng.random() < cfg.sibling_rate:
                sibling = self._sibling(example, rng)
                if sibling is not None:
                    out.append(sibling)
        if n_base < cfg.base_samples_per_family:
            self.log.reject(family.family_id, -1, "family", "attempts_exhausted", n_base=n_base)
        return out

    def _target_for(
        self, family: FamilySpec, index: int, rng: random.Random, recipe: ReplayRecipe,
        history: list[HistoryStep], s0: CapturedState, by_text: dict[str, ActionTemplate],
    ) -> SampledExample | None:  # fmt: skip
        tried: set[str] = set()
        for attempt in range(self.config.target_tries):
            if attempt:
                self.clean_state(family, recipe, s0)
            chosen = self._choose_target(rng, s0, by_text, tried)
            if chosen is None:
                self.log.reject(family.family_id, index, "target", "empty_target_pool")
                return None
            target, cls, n_door = chosen
            tried.add(target.action)
            dup = self._duplicate(s0, target.action)
            if dup:
                self.log.reject(family.family_id, index, "target", dup, action=target.action)
                continue
            reason, _, _ = _effective_step(self.session, target.action, s0)
            if reason:
                self.log.reject(family.family_id, index, "target", reason, action=target.action)
                continue
            self._remember(s0, target.action)
            return SampledExample(
                family, recipe, tuple(history), target, cls, s0, index, "base",
                n_door_actions_excluded=n_door, seed=self.config.seed,
            )  # fmt: skip
        return None

    def _sibling(self, base: SampledExample, rng: random.Random) -> SampledExample | None:
        family, target = base.family, base.target
        fam, index = family.family_id, base.sample_index
        tried: set[str] = set()
        for _ in range(self.config.contrast_tries):
            _, s, by_text = self.clean_state(family, base.recipe, base.s0)
            pool, _ = _pool(by_text, s, PREFIX_CLASSES)
            options = [
                a for c in sorted(pool) for a in pool[c] if a != target.action and a not in tried
            ]
            if not options:
                self.log.reject(fam, index, "sibling", "empty_contrast_pool")
                return None
            related = set(target.obj_ids) | {
                str(s.canonical.objects[i].get("parent"))
                for i in target.obj_ids
                if i in s.canonical.objects
            }
            preferred = [a for a in options if set(by_text[a].obj_ids) & related]
            contrast = rng.choice(preferred or options)
            tried.add(contrast)
            reason, _, _ = _effective_step(self.session, contrast, s)
            if reason:
                self.log.reject(fam, index, "sibling", f"contrast_{reason}", action=contrast)
                continue
            recipe = base.recipe.extend(contrast)
            try:
                history, s0b, by_text_b = self.clean_state(family, recipe)
            except (InvalidReplayActionError, EpisodeTerminatedError):
                self.log.reject(
                    fam, index, "sibling", "not_replayable_under_protocol", action=contrast
                )
                continue
            history[-1] = replace(history[-1], phase="contrast")
            tb = by_text_b.get(target.action)
            if tb is None:
                self.log.reject(
                    fam, index, "sibling", "target_unavailable_after_contrast", action=contrast
                )
                continue
            if tb.obj_ids != target.obj_ids:
                self.log.reject(fam, index, "sibling", "target_referent_changed", action=contrast)
                continue
            dup = self._duplicate(s0b, target.action)
            if dup:
                self.log.reject(fam, index, "sibling", dup, action=contrast)
                continue
            reason, _, _ = _effective_step(self.session, target.action, s0b)
            if reason:
                self.log.reject(fam, index, "sibling", f"target_{reason}", action=contrast)
                continue
            self._remember(s0b, target.action)
            return SampledExample(
                family, recipe, tuple(history), tb, base.target_class, s0b, index, "sibling",
                sibling_of=base.example_id, contrast_action=contrast,
                n_door_actions_excluded=base.n_door_actions_excluded, seed=self.config.seed,
            )  # fmt: skip
        return None


def sample_examples(
    config: SamplerConfig,
    *,
    runtime: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
    log: SamplingLog | None = None,
) -> list[SampledExample]:
    """Sample every family of ``config`` in one simulator session (deterministic)."""
    log = log if log is not None else SamplingLog()
    out: list[SampledExample] = []
    with ScienceWorldSession(runtime, backend_factory=backend_factory) as session:
        sampler = _Sampler(session, config, log)
        for family in config.families:
            out.extend(sampler.sample(family))
    return out


def explicit_example(
    family: FamilySpec,
    prefix: tuple[str, ...],
    target_action: str,
    *,
    runtime: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
    seed: int = 0,
    allow_idle: bool = False,
) -> SampledExample:
    """A hand-specified example, verified under the same rules as sampled ones (role 'explicit').

    ``allow_idle`` admits :data:`IDLE_ACTION` as tick-matching padding in ``prefix``.
    """
    recipe = family.base_recipe().extend(*prefix)
    with ScienceWorldSession(runtime, backend_factory=backend_factory) as session:
        sampler = _Sampler(session, SamplerConfig(seed=seed, families=(family,)), SamplingLog())
        reason = sampler.walk(family, prefix, allow_idle=allow_idle)
        if reason:
            raise ValueError(f"history rejected: {reason}")
        history, state, by_text = sampler.clean_state(family, recipe)
        target = by_text.get(target_action)
        cls = verb_class(target_action)
        if target is None or cls is None:
            raise ValueError(f"target {target_action!r} is not a valid, unambiguous sampled class")
        if door_exclusion_reason(target_action, target.obj_ids, state.canonical):
            raise ValueError(f"target {target_action!r} is excluded by RD-05")
    return SampledExample(family, recipe, tuple(history), target, cls,
                          state, -1, "explicit", seed=seed)  # fmt: skip


def collect_evidence(
    example: SampledExample,
    *,
    runtime: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
    max_paths: int = 4,
) -> tuple[dict[str, Any], bytes, dict[str, float]]:
    """Run the restricted restoration diagnostic for one example.

    Returns the evidence record, the bytes of its state file and timings.
    """
    t0 = time.perf_counter()
    experiment = InverseExperiment(
        example.example_id, example.recipe, example.target.action, rules=None,
        idle_action=IDLE_ACTION,
        purpose=f"Phase 4E provisional evidence ({example.family.family_id})",
    )  # fmt: skip
    diagnostic = run_inverse_experiment(
        experiment,
        config=runtime,
        backend_factory=backend_factory,
        projections=(*TEMPERATURE_SENSITIVITY, DISCRETE_EXPLORATION),
        counterfactual=True,
        verify_reconstruction=True,
        max_paths=max_paths,
    )
    state_bytes = state_document(example.s0)
    record = build_record(
        example,
        diagnostic,
        state_sha256=hashlib.sha256(state_bytes).hexdigest(),
        runtime=diagnostic.provenance,
    )
    timings = {
        "evidence_s": round(time.perf_counter() - t0, 3),
        "n_paths_attempted": len(diagnostic.attempts),
    }
    return record, state_bytes, timings


@dataclass
class PilotResult:
    records: list[dict[str, Any]]
    pairs: list[dict[str, Any]]
    summary: dict[str, Any]


def run_pilot(
    out_dir: Path,
    config: SamplerConfig = SamplerConfig(),  # noqa: B008 - frozen dataclass
    *,
    runtime: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
) -> PilotResult:
    """Sample, collect evidence, discover candidate pairs, validate and write ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "states").mkdir(exist_ok=True)
    log = SamplingLog()
    t0 = time.perf_counter()
    examples = sample_examples(config, runtime=runtime, backend_factory=backend_factory, log=log)
    t_sampled = time.perf_counter()
    records, perf = [], []
    for ex in examples:
        try:
            record, state_bytes, timings = collect_evidence(
                ex, runtime=runtime, backend_factory=backend_factory, max_paths=config.max_paths
            )
        except (ReplayDivergenceError, InvalidReplayActionError, EpisodeTerminatedError) as exc:
            log.reject(ex.family.family_id, ex.sample_index, "evidence", type(exc).__name__,
                       example_id=ex.example_id, detail=str(exc)[:200])  # fmt: skip
            continue
        if not record["replay_verification"]["verified"]:
            log.reject(ex.family.family_id, ex.sample_index, "evidence", "s0_not_reproduced",
                       example_id=ex.example_id)  # fmt: skip
            continue
        (out_dir / state_file_name(ex.s0)).write_bytes(state_bytes)
        records.append(record)
        perf.append({"example_id": ex.example_id, "family_id": ex.family.family_id, **timings})
    t_evidence = time.perf_counter()
    pairs, pair_stats = discover_candidate_pairs(records, load_state_file(out_dir))
    report = validate_dataset(records, pairs, root=out_dir)
    t_end = time.perf_counter()

    (out_dir / "records.jsonl").write_bytes(jsonl_bytes(records))
    (out_dir / "candidate_pairs.jsonl").write_bytes(jsonl_bytes(pairs))
    (out_dir / "rejections.jsonl").write_bytes(jsonl_bytes(log.rows))
    (out_dir / "performance.jsonl").write_bytes(jsonl_bytes(perf))
    (out_dir / "validation.json").write_text(json.dumps(report.to_dict(), indent=1) + "\n", "utf-8")
    summary = summarise(config, examples, records, pairs, pair_stats.to_dict(), log, perf, {
        "sampling_s": round(t_sampled - t0, 2),
        "evidence_s": round(t_evidence - t_sampled, 2),
        "pairs_and_validation_s": round(t_end - t_evidence, 2),
        "total_s": round(t_end - t0, 2),
    })  # fmt: skip
    summary["validation_ok"] = report.ok
    return PilotResult(records, pairs, summary)


def summarise(
    config: SamplerConfig,
    examples: list[SampledExample],
    records: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    pair_stats: dict[str, Any],
    log: SamplingLog,
    perf: list[dict[str, Any]],
    wall: dict[str, float],
) -> dict[str, Any]:
    per_family: dict[str, dict[str, Any]] = {}
    for f in config.families:
        recs = [r for r in records if r["family_id"] == f.family_id]
        per_family[f.family_id] = {
            "sampled": sum(1 for e in examples if e.family.family_id == f.family_id),
            "usable_records": len(recs),
            "siblings": sum(1 for r in recs if r["sampling"]["role"] == "sibling"),
            "rejections": sum(1 for r in log.rows if r["family_id"] == f.family_id),
            "verb_classes": _count(r["target"]["verb_class"] for r in recs),
            "evidence_status": _count(r["restoration_evidence"]["evidence_status"] for r in recs),
            "candidate_pairs": sum(1 for p in pairs if p["family_id"] == f.family_id),
        }
    ev_times = [p["evidence_s"] for p in perf]
    n_paths = sum(p["n_paths_attempted"] for p in perf)
    attempts = len(examples) + sum(1 for r in log.rows if r["stage"] in ("history", "target"))
    dup = sum(1 for r in log.rows if r["reason"].startswith("duplicate"))
    return {
        "sampler_version": SAMPLER_VERSION,
        "config": config.to_dict(),
        "n_sampled": len(examples),
        "n_records": len(records),
        "n_candidate_pairs": len(pairs),
        "per_family": per_family,
        "evidence_status": _count(r["restoration_evidence"]["evidence_status"] for r in records),
        "rejections": log.counts(),
        "pair_discovery": pair_stats,
        "rates": {
            "sampling_attempts_incl_rejections": attempts,
            "duplicate_rejections": dup,
            "duplicate_rate": _ratio(dup, attempts, 3),
            "evidence_failures": sum(1 for r in log.rows if r["stage"] == "evidence"),
            "minimal_pair_yield_per_record": _ratio(len(pairs), len(records), 3),
        },
        "performance": {
            **wall,
            "evidence_s_per_record_mean": _ratio(sum(ev_times), len(ev_times)),
            "evidence_s_per_record_max": max(ev_times, default=None),
            "evidence_s_per_path_attempt": round(sum(ev_times) / n_paths, 2) if n_paths else None,
            "sampling_s_per_sampled_example": _ratio(wall["sampling_s"], len(examples)),
        },
    }  # fmt: skip


def _ratio(num: float, den: int, digits: int = 2) -> float | None:
    return round(num / den, digits) if den else None


def _count(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))
