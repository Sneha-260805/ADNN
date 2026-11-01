"""Replay recipes and deterministic fresh-environment replay (docs/18 §4).

A ScienceWorld state has no snapshot; it is *defined* by an immutable
:class:`ReplayRecipe` (task, variation, simplifications, explicit preparation
steps, ordered actions, step limit, simulator pin). :func:`replay` rebuilds it
in a fresh simulator and validates every action outcome. :func:`compare_results`
reports the first divergence step by step. :func:`replay_in_fresh_process` runs
the same replay in a separate OS process (and JVM).

No restoration search, no labels: this module only reconstructs and records.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adnn.scienceworld.canonical import CapturedState, RawState, canonicalize, capture_state
from adnn.scienceworld.env import Backend, ScienceWorldSession, StepResult
from adnn.scienceworld.provenance import (
    ENV_JAVA_HOME,
    ENV_SITE_PACKAGES,
    PINNED,
    RuntimeConfig,
    SimulatorPin,
    UnpinnedRuntimeError,
)

RECIPE_SCHEMA = "sw-replay-1"
FIRST_TICK_PREPARATION: tuple[str, ...] = ("wait1",)
CAPTURE_MODES = ("final", "all")


class InvalidReplayActionError(RuntimeError):
    """A recipe action was not accepted by the simulator (invalid or ambiguous)."""


class EpisodeTerminatedError(RuntimeError):
    """The episode ended (step limit or negative score) before the recipe finished."""


class ReplayDivergenceError(RuntimeError):
    """Two replays of the same recipe differ."""

    def __init__(self, comparison: TraceComparison) -> None:
        super().__init__(
            f"replay diverged at step {comparison.first_divergent_step}: "
            f"{', '.join(comparison.divergent_fields)}"
        )
        self.comparison = comparison


def normalise_simplifications(value: str) -> str:
    parts = sorted({p.strip() for p in value.split(",") if p.strip()})
    return ",".join(parts)


@dataclass(frozen=True)
class ReplayRecipe:
    """Everything needed to reconstruct one ScienceWorld state deterministically."""

    task: str
    variation: int
    simplifications: str = ""
    preparation: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    step_limit: int = 100
    simulator: SimulatorPin = PINNED
    schema: str = RECIPE_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "simplifications", normalise_simplifications(self.simplifications))
        object.__setattr__(self, "preparation", tuple(self.preparation))
        object.__setattr__(self, "actions", tuple(self.actions))
        if not self.task or not isinstance(self.task, str):
            raise ValueError("task must be a non-empty string")
        if not isinstance(self.variation, int) or isinstance(self.variation, bool):
            raise ValueError("variation must be an int")
        if self.variation < 0:
            raise ValueError("variation must be >= 0")
        for a in (*self.preparation, *self.actions):
            if not isinstance(a, str) or not a.strip():
                raise ValueError("actions must be non-empty strings")
        if len(self.preparation) + len(self.actions) > self.step_limit:
            raise ValueError("recipe is longer than its step limit")
        if self.schema != RECIPE_SCHEMA:
            raise ValueError(f"unknown recipe schema {self.schema!r}")

    @property
    def all_actions(self) -> tuple[tuple[str, str], ...]:
        return tuple(("preparation", a) for a in self.preparation) + tuple(
            ("action", a) for a in self.actions
        )

    def extend(self, *actions: str) -> ReplayRecipe:
        """A new recipe with ``actions`` appended (recipes are immutable)."""
        return ReplayRecipe(
            self.task,
            self.variation,
            self.simplifications,
            self.preparation,
            (*self.actions, *actions),
            self.step_limit,
            self.simulator,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "task": self.task,
            "variation": self.variation,
            "simplifications": self.simplifications,
            "preparation": list(self.preparation),
            "actions": list(self.actions),
            "step_limit": self.step_limit,
            "simulator": self.simulator.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReplayRecipe:
        allowed = {
            "schema", "task", "variation", "simplifications", "preparation", "actions",
            "step_limit", "simulator",
        }  # fmt: skip
        unknown = set(d) - allowed
        if unknown:
            raise ValueError(f"unknown recipe fields: {sorted(unknown)}")
        return cls(
            task=d["task"],
            variation=d["variation"],
            simplifications=d.get("simplifications", ""),
            preparation=tuple(d.get("preparation", ())),
            actions=tuple(d.get("actions", ())),
            step_limit=d.get("step_limit", 100),
            simulator=SimulatorPin.from_dict(d["simulator"]),
            schema=d.get("schema", RECIPE_SCHEMA),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> ReplayRecipe:
        return cls.from_dict(json.loads(text))


@dataclass(frozen=True)
class StepRecord:
    index: int
    phase: str  # "preparation" | "action"
    result: StepResult
    state: CapturedState | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "phase": self.phase,
            "result": self.result.to_dict(),
            "state_raw": self.state.raw.to_dict() if self.state else None,
            "canonical_fingerprint": self.state.canonical.fingerprint if self.state else None,
        }


def _state_from(raw: dict[str, Any] | None, fingerprint: str | None) -> CapturedState | None:
    if raw is None:
        return None
    r = RawState.from_dict(raw)
    state = CapturedState(r, canonicalize(r))
    if fingerprint is not None and state.canonical.fingerprint != fingerprint:
        raise ValueError("stored canonical fingerprint does not match the stored raw state")
    return state


def _step_result(d: dict[str, Any]) -> StepResult:
    return StepResult(**{k: v for k, v in d.items() if k != "advanced_time"})


@dataclass(frozen=True)
class ReplayResult:
    recipe: ReplayRecipe
    provenance: dict[str, Any] | None
    initial: CapturedState
    steps: tuple[StepRecord, ...]
    final: CapturedState
    timings: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe": self.recipe.to_dict(),
            "provenance": self.provenance,
            "initial_raw": self.initial.raw.to_dict(),
            "initial_canonical_fingerprint": self.initial.canonical.fingerprint,
            "steps": [s.to_dict() for s in self.steps],
            "final_raw": self.final.raw.to_dict(),
            "final_canonical_fingerprint": self.final.canonical.fingerprint,
            "timings": self.timings,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReplayResult:
        initial = _state_from(d["initial_raw"], d["initial_canonical_fingerprint"])
        final = _state_from(d["final_raw"], d["final_canonical_fingerprint"])
        assert initial is not None and final is not None
        steps = tuple(
            StepRecord(
                s["index"],
                s["phase"],
                _step_result(s["result"]),
                _state_from(s["state_raw"], s["canonical_fingerprint"]),
            )
            for s in d["steps"]
        )
        return cls(
            ReplayRecipe.from_dict(d["recipe"]),
            d.get("provenance"),
            initial,
            steps,
            final,
            dict(d.get("timings", {})),
        )


def run_recipe(
    session: ScienceWorldSession,
    recipe: ReplayRecipe,
    *,
    capture: str = "final",
    strict: bool = True,
) -> tuple[CapturedState, tuple[StepRecord, ...], float]:
    """Load ``recipe`` into a running session and execute it (shared by :func:`replay`).

    Returns the initial state, the step records and the ``perf_counter`` time at which
    load + reset + initial capture finished. The session is left in the recipe's final
    state, so a caller may continue stepping (e.g. restoration diagnostics, docs/19).
    """
    if capture not in CAPTURE_MODES:
        raise ValueError(f"capture must be one of {CAPTURE_MODES}")
    session.load(recipe.task, recipe.variation, recipe.simplifications)
    initial = capture_state(session)
    t_loaded = time.perf_counter()
    steps: list[StepRecord] = []
    sequence = recipe.all_actions
    for i, (phase, action) in enumerate(sequence):
        result = session.step(action)
        if strict and result.status != "accepted":
            raise InvalidReplayActionError(
                f"step {i} ({phase}) {action!r} was {result.status}: {result.observation[:120]!r}"
            )
        if strict and result.done and i < len(sequence) - 1:
            raise EpisodeTerminatedError(f"episode ended at step {i} ({action!r})")
        state = capture_state(session) if capture == "all" else None
        steps.append(StepRecord(i, phase, result, state))
    return initial, tuple(steps), t_loaded


def replay(
    recipe: ReplayRecipe,
    *,
    config: RuntimeConfig | None = None,
    capture: str = "final",
    strict: bool = True,
    backend_factory: Callable[[], Backend] | None = None,
    pin: SimulatorPin = PINNED,
) -> ReplayResult:
    """Rebuild ``recipe`` in a fresh simulator and record every action outcome.

    With ``strict=True`` an invalid or ambiguous action raises
    :class:`InvalidReplayActionError`, and an episode that ends early raises
    :class:`EpisodeTerminatedError`. ``capture="all"`` captures the full state
    after every step (≈0.17 s each); ``"final"`` captures only start and end.
    """
    if capture not in CAPTURE_MODES:
        raise ValueError(f"capture must be one of {CAPTURE_MODES}")
    if recipe.simulator != pin:
        raise UnpinnedRuntimeError("recipe was recorded with a different simulator pin")
    t0 = time.perf_counter()
    with ScienceWorldSession(
        config, step_limit=recipe.step_limit, backend_factory=backend_factory
    ) as session:
        t_started = time.perf_counter()
        initial, steps, t_loaded = run_recipe(session, recipe, capture=capture, strict=strict)
        final = capture_state(session)
        provenance = session.provenance.to_dict() if session.provenance else None
    t_end = time.perf_counter()
    return ReplayResult(
        recipe=recipe,
        provenance=provenance,
        initial=initial,
        steps=steps,
        final=final,
        timings={
            "start_s": round(t_started - t0, 4),
            "load_reset_capture_s": round(t_loaded - t_started, 4),
            "steps_and_captures_s": round(t_end - t_loaded, 4),
            "total_s": round(t_end - t0, 4),
        },
    )


@dataclass(frozen=True)
class TraceComparison:
    identical: bool
    first_divergent_step: int | None  # -1 = initial state, len(steps) = final state
    divergent_fields: tuple[str, ...]
    n_steps_compared: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "identical": self.identical,
            "first_divergent_step": self.first_divergent_step,
            "divergent_fields": list(self.divergent_fields),
            "n_steps_compared": self.n_steps_compared,
        }


_STEP_FIELDS = (
    "action",
    "status",
    "observation",
    "reward",
    "score",
    "done",
    "moves_before",
    "moves_after",
)


def compare_results(a: ReplayResult, b: ReplayResult) -> TraceComparison:
    """Compare two replays of the same recipe: outcomes and captured states, step by step."""
    if a.recipe != b.recipe:
        raise ValueError("cannot compare replays of different recipes")

    def state_fields(sa: CapturedState | None, sb: CapturedState | None) -> list[str]:
        if sa is None or sb is None:
            return []
        out = []
        if sa.raw.fingerprint != sb.raw.fingerprint:
            out.append("raw_state")
        if sa.canonical.fingerprint != sb.canonical.fingerprint:
            out.append("canonical_state")
        return out

    first = state_fields(a.initial, b.initial)
    if first:
        return TraceComparison(False, -1, tuple(first), 0)
    for sa, sb in zip(a.steps, b.steps, strict=True):
        fields = [f for f in _STEP_FIELDS if getattr(sa.result, f) != getattr(sb.result, f)]
        fields += state_fields(sa.state, sb.state)
        if fields:
            return TraceComparison(False, sa.index, tuple(fields), sa.index + 1)
    last = state_fields(a.final, b.final)
    if last:
        return TraceComparison(False, len(a.steps), tuple(last), len(a.steps))
    return TraceComparison(True, None, (), len(a.steps))


def assert_reproducible(results: list[ReplayResult]) -> None:
    for other in results[1:]:
        cmp = compare_results(results[0], other)
        if not cmp.identical:
            raise ReplayDivergenceError(cmp)


def replay_in_fresh_process(
    recipe: ReplayRecipe,
    *,
    config: RuntimeConfig | None = None,
    capture: str = "final",
    timeout_s: float = 900.0,
) -> ReplayResult:
    """Run :func:`replay` in a new Python process (and therefore a new JVM)."""
    config = config or RuntimeConfig.from_env()
    env = dict(os.environ)
    if config.java_home is not None:
        env[ENV_JAVA_HOME] = str(config.java_home)
    if config.site_packages is not None:
        env[ENV_SITE_PACKAGES] = str(config.site_packages)
    with tempfile.TemporaryDirectory() as tmp:
        recipe_path, out_path = Path(tmp) / "recipe.json", Path(tmp) / "result.json"
        recipe_path.write_text(recipe.to_json(), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "adnn.scienceworld.replay",
                "--recipe",
                str(recipe_path),
                "--out",
                str(out_path),
                "--capture",
                capture,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"replay worker failed ({proc.returncode}): {proc.stderr[-2000:]}")
        return ReplayResult.from_dict(json.loads(out_path.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay one ScienceWorld recipe (worker)")
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--capture", choices=CAPTURE_MODES, default="final")
    args = ap.parse_args(argv)
    recipe = ReplayRecipe.from_json(args.recipe.read_text(encoding="utf-8"))
    result = replay(recipe, capture=args.capture)
    args.out.write_text(json.dumps(result.to_dict()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
