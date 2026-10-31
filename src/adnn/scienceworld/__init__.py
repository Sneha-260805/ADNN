"""ScienceWorld replay and state-capture adapter (owner: Member 1, Sneha). docs/18.

Scope (Phase 4C): verified pinned runtime, deterministic fresh-environment
replay of immutable recipes, raw and canonical state capture, and difference
diagnostics. **No restoration search and no reversibility labels** — those
depend on open professor decisions (OQ-03, OQ-30, OQ-31).

ScienceWorld is an optional dependency: importing this package never imports
``scienceworld``, ``py4j`` or starts Java. A real simulator is only started by
:class:`ScienceWorldSession` (directly or via :func:`replay`), after the pinned
build has been verified (:func:`resolve_runtime`).
"""

from adnn.scienceworld.canonical import (
    CANONICAL_RULES,
    CANONICAL_VERSION,
    CanonicalState,
    CapturedState,
    RawState,
    canonicalize,
    capture_state,
)
from adnn.scienceworld.diagnostics import (
    DISCRETE_EXPLORATION,
    Projection,
    StateDiff,
    canonical_diff,
    projection_diff,
    raw_diff,
)
from adnn.scienceworld.env import (
    ProcessLeakError,
    ScienceWorldSession,
    SessionStateError,
    StepResult,
    classify_observation,
)
from adnn.scienceworld.provenance import (
    PINNED,
    RuntimeConfig,
    RuntimeProvenance,
    ScienceWorldUnavailableError,
    SimulatorPin,
    UnpinnedRuntimeError,
    resolve_runtime,
)
from adnn.scienceworld.replay import (
    FIRST_TICK_PREPARATION,
    EpisodeTerminatedError,
    InvalidReplayActionError,
    ReplayDivergenceError,
    ReplayRecipe,
    ReplayResult,
    TraceComparison,
    assert_reproducible,
    compare_results,
    replay,
    replay_in_fresh_process,
)

__all__ = [
    "CANONICAL_RULES",
    "CANONICAL_VERSION",
    "DISCRETE_EXPLORATION",
    "FIRST_TICK_PREPARATION",
    "PINNED",
    "CanonicalState",
    "CapturedState",
    "EpisodeTerminatedError",
    "InvalidReplayActionError",
    "ProcessLeakError",
    "Projection",
    "RawState",
    "ReplayDivergenceError",
    "ReplayRecipe",
    "ReplayResult",
    "RuntimeConfig",
    "RuntimeProvenance",
    "ScienceWorldSession",
    "ScienceWorldUnavailableError",
    "SessionStateError",
    "SimulatorPin",
    "StateDiff",
    "StepResult",
    "TraceComparison",
    "UnpinnedRuntimeError",
    "assert_reproducible",
    "canonical_diff",
    "canonicalize",
    "capture_state",
    "classify_observation",
    "compare_results",
    "projection_diff",
    "raw_diff",
    "replay",
    "replay_in_fresh_process",
    "resolve_runtime",
]
