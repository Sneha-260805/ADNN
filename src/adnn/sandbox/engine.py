"""The ``Sandbox`` object: a stateful wrapper around the pure ``step`` function.

Agent-facing surface: :meth:`Sandbox.execute`, :meth:`Sandbox.get_observation`
and :meth:`Sandbox.tool_specs`. The agent can reach the world *only* through
``execute``, which dispatches exclusively to the registered agent tools.

Researcher-only surface: :meth:`reset`, :meth:`snapshot`,
:meth:`restore_snapshot`, serialisation and history access. These are Python
methods for experiment control and are never exposed as tools.

The action history is an audit log kept *outside* :class:`WorldState`, so it
never influences restoration judgements (docs/10_SANDBOX_DESIGN.md §5).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from adnn.sandbox.render import render_state
from adnn.sandbox.state import WorldState, canonical_hash, validate_state
from adnn.sandbox.tools import (
    ErrorCode,
    ToolCall,
    ToolResult,
    frozen_mapping,
    step,
    tool_specs_for,
)


@dataclass(frozen=True)
class ActionRecord:
    """One entry of the audit log."""

    step: int
    tool: str
    args: Mapping[str, Any]
    ok: bool
    error_code: str | None
    message: str
    clock_before: int
    clock_after: int
    state_hash_before: str
    state_hash_after: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", frozen_mapping(self.args))

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "tool": self.tool,
            "args": copy.deepcopy(dict(self.args)),
            "ok": self.ok,
            "error_code": self.error_code,
            "message": self.message,
            "clock_before": self.clock_before,
            "clock_after": self.clock_after,
            "state_hash_before": self.state_hash_before,
            "state_hash_after": self.state_hash_after,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> ActionRecord:
        return cls(**d)


@dataclass(frozen=True)
class Snapshot:
    """Researcher-controlled checkpoint: world state plus audit log."""

    state: WorldState
    history: tuple[ActionRecord, ...] = field(default_factory=tuple)


def _args_of(action: object) -> dict[str, Any]:
    if isinstance(action, ToolCall):
        return dict(action.args)
    if isinstance(action, Mapping) and isinstance(action.get("args"), Mapping):
        return dict(action["args"])
    return {}


class Sandbox:
    """Deterministic, fully simulated tool environment."""

    def __init__(self, initial_state: WorldState | Mapping[str, Any] | None = None) -> None:
        self._state = WorldState()
        self._history: tuple[ActionRecord, ...] = ()
        self.reset(initial_state if initial_state is not None else WorldState())

    # -- researcher-only ---------------------------------------------------------
    def reset(self, initial_state: WorldState | Mapping[str, Any]) -> None:
        """Load an initial world and clear the action history."""
        state = (
            initial_state
            if isinstance(initial_state, WorldState)
            else WorldState.from_dict(dict(initial_state))
        )
        validate_state(state)
        self._state = state
        self._history = ()

    def snapshot(self) -> Snapshot:
        return Snapshot(self._state, self._history)

    def restore_snapshot(self, snapshot: Snapshot) -> None:
        """Rewind world state and audit log to a snapshot (never an agent action)."""
        if not isinstance(snapshot, Snapshot):
            raise TypeError("restore_snapshot expects a Snapshot")
        self._state = snapshot.state
        self._history = snapshot.history

    @property
    def state(self) -> WorldState:
        """The current (immutable) world state."""
        return self._state

    def state_hash(self) -> str:
        """Hash of the canonical state (excludes clock, counters and the log)."""
        return canonical_hash(self._state)

    def get_action_history(self) -> tuple[ActionRecord, ...]:
        return self._history

    def to_json(self) -> str:
        return json.dumps(
            {
                "state": self._state.to_dict(),
                "history": [r.to_dict() for r in self._history],
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, text: str) -> Sandbox:
        data = json.loads(text)
        sandbox = cls(WorldState.from_dict(data["state"]))
        sandbox._history = tuple(ActionRecord.from_dict(r) for r in data.get("history", ()))
        return sandbox

    # -- agent-facing ------------------------------------------------------------
    def execute(self, action: ToolCall | Mapping[str, Any]) -> ToolResult:
        """Run one agent action through the tool registry and log it."""
        before = self._state
        after, result = step(before, action)
        self._state = after
        self._history = (
            *self._history,
            ActionRecord(
                step=len(self._history) + 1,
                tool=result.tool,
                args=_args_of(action),
                ok=result.ok,
                error_code=result.error_code.value if result.error_code else None,
                message=result.message,
                clock_before=before.clock_s,
                clock_after=after.clock_s,
                state_hash_before=canonical_hash(before),
                state_hash_after=canonical_hash(after),
            ),
        )
        return result

    def get_observation(self) -> str:
        """Plain-text rendering of the current world, as shown to the agent."""
        return render_state(self._state)

    def tool_specs(self) -> list[dict[str, Any]]:
        return tool_specs_for(self._state)


__all__ = ["ActionRecord", "ErrorCode", "Sandbox", "Snapshot"]
