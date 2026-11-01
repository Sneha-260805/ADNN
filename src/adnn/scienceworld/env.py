"""ScienceWorld session lifecycle (docs/18 §3).

:class:`ScienceWorldSession` wraps one simulator instance (one JVM). It verifies
the pinned runtime, starts the JVM with the configured JDK on ``PATH`` for the
launch only, classifies every action outcome, and on exit checks that the JVM
process really terminated (killing it and raising :class:`ProcessLeakError`
otherwise).

A backend factory can be injected so that unit tests run without Java or
ScienceWorld. ``scienceworld`` is imported lazily, only when a real session
starts.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Protocol

from adnn.scienceworld.provenance import (
    RuntimeConfig,
    RuntimeProvenance,
    java_executable,
    resolve_runtime,
)

INVALID_PREFIX = "No known action matches that input."
AMBIGUOUS_PREFIX = "Ambiguous request"
PROCESS_EXIT_TIMEOUT_S = 15.0


class ProcessLeakError(RuntimeError):
    """The simulator's JVM did not exit after close (it has been killed)."""


class SessionStateError(RuntimeError):
    """The session was used before ``load`` or after ``close``."""


class Backend(Protocol):
    """The subset of ``scienceworld.ScienceWorldEnv`` the adapter relies on."""

    # Called positionally only, so parameter names need not match upstream's camelCase.
    def load(
        self,
        task_name: str,
        variation_idx: int = 0,
        simplification_str: str = "",
        generate_gold_path: bool = False,
    ) -> None: ...
    def reset(self) -> tuple[str, dict[str, Any]]: ...
    def step(self, input_str: str) -> tuple[str, int, bool, dict[str, Any]]: ...
    def look(self) -> str: ...
    def inventory(self) -> str: ...
    def getObjectTree(self) -> dict[str, Any]: ...  # noqa: N802 - upstream name
    def get_valid_action_object_combinations(self) -> list[str]: ...
    def get_valid_action_object_combinations_with_templates(self) -> list[dict[str, Any]]: ...
    def get_num_moves(self) -> int: ...
    def get_gold_action_sequence(self) -> list[str]: ...
    def close(self) -> None: ...


def classify_observation(observation: str) -> str:
    """``accepted`` | ``invalid`` | ``ambiguous`` from the simulator's own response text."""
    text = observation.lstrip()
    if text.startswith(INVALID_PREFIX):
        return "invalid"
    if text.startswith(AMBIGUOUS_PREFIX):
        return "ambiguous"
    return "accepted"


@dataclass(frozen=True)
class StepResult:
    action: str
    observation: str
    status: str  # accepted | invalid | ambiguous
    reward: int
    score: int
    done: bool
    moves_before: int
    moves_after: int

    @property
    def advanced_time(self) -> bool:
        return self.moves_after != self.moves_before

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "advanced_time": self.advanced_time}


@dataclass(frozen=True)
class ActionTemplate:
    """A valid action with the simulator uuids of the objects it refers to (as strings)."""

    action: str
    template_id: int
    obj_ids: tuple[str, ...]


@dataclass(frozen=True)
class LoadedTask:
    task: str
    variation: int
    simplifications: str
    resolved_task_name: str | None


@contextmanager
def _launch_context(config: RuntimeConfig, provenance: RuntimeProvenance) -> Iterator[None]:
    """Process-local settings needed only while the JVM is launched, then restored.

    * ``PATH``: the configured JDK's ``bin`` is prepended (ScienceWorld does not pass
      a Java path to py4j, so ``java`` must be resolvable).
    * working directory: py4j looks for its gateway JAR in the current directory
      first; the verified JAR's directory is used so the launch never depends on
      the interpreter's prefix. Not thread-safe: start sessions from one thread.
    """
    old_path, old_cwd = os.environ.get("PATH"), os.getcwd()
    try:
        if config.java_home is not None:
            os.environ["PATH"] = str(java_executable(config).parent) + os.pathsep + (old_path or "")
        os.chdir(os.path.dirname(provenance.py4j_jar))
        yield
    finally:
        try:
            os.chdir(old_cwd)
        finally:
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path


def _java_process(backend: object) -> Any:
    gateway = getattr(backend, "_gateway", None)
    return getattr(gateway, "java_process", None) or getattr(backend, "java_process", None)


class ScienceWorldSession:
    """One verified simulator instance. Use as a context manager."""

    def __init__(
        self,
        config: RuntimeConfig | None = None,
        *,
        step_limit: int = 100,
        backend_factory: Callable[[], Backend] | None = None,
        provenance: RuntimeProvenance | None = None,
    ) -> None:
        self._config = config or RuntimeConfig.from_env()
        self._step_limit = step_limit
        self._backend_factory = backend_factory
        self._backend: Backend | None = None
        self._process: Any = None
        self._loaded: LoadedTask | None = None
        self.provenance = provenance
        self.closed = False

    # -- lifecycle ------------------------------------------------------------------
    def __enter__(self) -> ScienceWorldSession:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close(raise_on_leak=exc is None)

    def start(self) -> None:
        if self._backend is not None:
            return
        if self._backend_factory is not None:
            self._backend = self._backend_factory()
        else:
            self.provenance = resolve_runtime(self._config)
            module = importlib.import_module("scienceworld")
            with _launch_context(self._config, self.provenance):
                self._backend = module.ScienceWorldEnv("", envStepLimit=self._step_limit)
        self._process = _java_process(self._backend)

    def close(self, *, raise_on_leak: bool = True) -> None:
        """Close the simulator and verify that its JVM exited. Idempotent."""
        if self.closed:
            return
        self.closed = True
        backend, self._backend = self._backend, None
        if backend is None:
            return
        try:
            backend.close()
        finally:
            proc = self._process
            if proc is not None:
                try:
                    proc.wait(timeout=PROCESS_EXIT_TIMEOUT_S)
                except Exception:
                    proc.kill()
                    proc.wait(timeout=PROCESS_EXIT_TIMEOUT_S)
                    if raise_on_leak:
                        raise ProcessLeakError("ScienceWorld JVM did not exit; killed") from None

    @property
    def process(self) -> Any:
        """The JVM process handle (``subprocess.Popen``), or ``None`` for fake backends."""
        return self._process

    def _require(self) -> Backend:
        if self._backend is None or self.closed:
            raise SessionStateError("session is not running")
        return self._backend

    # -- simulator access ---------------------------------------------------------------
    def load(self, task: str, variation: int, simplifications: str = "") -> LoadedTask:
        """Load a task variation and reset to its initial state."""
        backend = self._require()
        if variation < 0:
            raise ValueError("variation must be >= 0")
        backend.load(task, variation, simplifications)
        _, info = backend.reset()
        self._loaded = LoadedTask(task, variation, simplifications, info.get("taskName"))
        return self._loaded

    def reset(self) -> None:
        if self._loaded is None:
            raise SessionStateError("load a task before reset")
        self._require().reset()

    def step(self, action: str) -> StepResult:
        backend = self._require()
        if self._loaded is None:
            raise SessionStateError("load a task before stepping")
        before = backend.get_num_moves()
        observation, reward, done, info = backend.step(action)
        return StepResult(
            action=action,
            observation=observation,
            status=classify_observation(observation),
            reward=int(reward),
            score=int(info.get("score", 0)),
            done=bool(done),
            moves_before=int(before),
            moves_after=int(backend.get_num_moves()),
        )

    def look(self) -> str:
        return self._require().look()

    def inventory(self) -> str:
        return self._require().inventory()

    def object_tree(self) -> dict[str, Any]:
        return self._require().getObjectTree()

    def valid_actions(self) -> list[str]:
        return sorted(self._require().get_valid_action_object_combinations())

    def valid_action_templates(self) -> list[ActionTemplate]:
        """Valid actions with the uuids they resolve to (free call; no time passes, docs/19 §2).

        Lets callers select an action by the objects it acts on rather than by its referent
        text. Door actions carry portal uuids that do not occur in the object tree.
        """
        rows = self._require().get_valid_action_object_combinations_with_templates()
        return sorted(
            (
                ActionTemplate(
                    str(r["action"]), int(r["template_id"]), tuple(str(i) for i in r["obj_ids"])
                )
                for r in rows
            ),
            key=lambda t: (t.action, t.obj_ids),
        )

    def moves(self) -> int:
        return int(self._require().get_num_moves())

    def gold_actions(self) -> list[str]:
        return list(self._require().get_gold_action_sequence())

    def load_with_gold_path(
        self, task: str, variation: int, simplifications: str = ""
    ) -> list[str]:
        """Load with gold-path generation (exploration helper) and return the gold actions."""
        backend = self._require()
        backend.load(task, variation, simplifications, True)
        _, info = backend.reset()
        self._loaded = LoadedTask(task, variation, simplifications, info.get("taskName"))
        return self.gold_actions()

    @property
    def loaded(self) -> LoadedTask | None:
        return self._loaded
