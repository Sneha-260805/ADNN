"""ScienceWorld replay and state-capture adapter (owner: Member 1, Sneha). docs/18.

Scope (Phase 4C): verified pinned runtime, deterministic fresh-environment
replay of immutable recipes, raw and canonical state capture, and difference
diagnostics. Phase 4D (docs/19): restricted inverse-action restoration
diagnostics and exploratory structural object matching. Phase 4E (docs/21):
provisional evidence records, seeded sampling and candidate minimal pairs in the
submodules ``provisional`` and ``provisional_sampling``, under the research
team's decision log (docs/decisions/0002; not professor-approved). **No
exhaustive restoration search and no reversibility labels.**

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
    TEMPERATURE_SENSITIVITY,
    TEMPERATURE_TOLERANCE_001,
    TEMPERATURE_TOLERANCE_01,
    TEMPERATURE_TOLERANCE_EXPLORATION,
    Projection,
    StateDiff,
    canonical_diff,
    projection_diff,
    raw_diff,
)
from adnn.scienceworld.env import (
    ActionTemplate,
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
    run_recipe,
)
from adnn.scienceworld.restoration_diagnostics import (
    OUTCOMES,
    REGISTRY,
    ExplicitPath,
    InverseExperiment,
    InverseRule,
    PathAttempt,
    RestorationDiagnostic,
    phase4d_experiments,
    run_inverse_experiment,
)
from adnn.scienceworld.structural import StructuralReport, structural_match

__all__ = [
    "CANONICAL_RULES",
    "CANONICAL_VERSION",
    "DISCRETE_EXPLORATION",
    "FIRST_TICK_PREPARATION",
    "OUTCOMES",
    "PINNED",
    "REGISTRY",
    "TEMPERATURE_SENSITIVITY",
    "TEMPERATURE_TOLERANCE_001",
    "TEMPERATURE_TOLERANCE_01",
    "TEMPERATURE_TOLERANCE_EXPLORATION",
    "ActionTemplate",
    "CanonicalState",
    "CapturedState",
    "EpisodeTerminatedError",
    "ExplicitPath",
    "InvalidReplayActionError",
    "InverseExperiment",
    "InverseRule",
    "PathAttempt",
    "ProcessLeakError",
    "Projection",
    "RawState",
    "ReplayDivergenceError",
    "ReplayRecipe",
    "ReplayResult",
    "RestorationDiagnostic",
    "RuntimeConfig",
    "RuntimeProvenance",
    "ScienceWorldSession",
    "ScienceWorldUnavailableError",
    "SessionStateError",
    "SimulatorPin",
    "StateDiff",
    "StepResult",
    "StructuralReport",
    "TraceComparison",
    "UnpinnedRuntimeError",
    "assert_reproducible",
    "canonical_diff",
    "canonicalize",
    "capture_state",
    "classify_observation",
    "compare_results",
    "phase4d_experiments",
    "projection_diff",
    "raw_diff",
    "replay",
    "replay_in_fresh_process",
    "resolve_runtime",
    "run_inverse_experiment",
    "run_recipe",
    "structural_match",
]
