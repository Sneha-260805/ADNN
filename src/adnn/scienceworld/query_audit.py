"""Query-order / measurement-dependence audit for the pinned simulator (Phase 4F, docs/22 §2).

Question: do the calls we use to *observe* the simulator (``look``, ``inventory``,
``getObjectTree``, valid-action enumeration) change what the simulator does next?

Design. A scenario is a fixed task, variation and action sequence. A *condition* is a
bundle of diagnostic queries issued before every step (A: none; B: look, inventory and
object tree; C: valid-action enumeration; D1/D2: both, in two orders). To observe the
state after step k without adding queries to condition A, each probe reloads the task,
runs the first k steps under the condition and then captures the state once, with the
same capture in every condition ("probe at k"). Step observations come from ``step``
itself and need no query. Every (condition, repeat) can run in a fresh JVM.

The audit reports differences; it never assumes measurement independence.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from adnn.scienceworld.canonical import CapturedState, capture_state, sha256_json
from adnn.scienceworld.diagnostics import canonical_diff
from adnn.scienceworld.env import Backend, ScienceWorldSession
from adnn.scienceworld.provenance import RuntimeConfig
from adnn.scienceworld.replay import FIRST_TICK_PREPARATION

AUDIT_VERSION = "sw-query-audit-1"

QUERY_KINDS = ("look", "inventory", "object_tree", "valid_actions", "valid_action_templates")
CONDITIONS: dict[str, tuple[str, ...]] = {
    "A_none": (),
    "B_observe": ("look", "inventory", "object_tree"),
    "C_enumerate": ("valid_actions", "valid_action_templates"),
    "D1_observe_then_enumerate": (
        "look",
        "inventory",
        "object_tree",
        "valid_actions",
        "valid_action_templates",
    ),
    "D2_enumerate_then_observe": (
        "valid_action_templates",
        "valid_actions",
        "object_tree",
        "inventory",
        "look",
    ),
}
BASELINE = "A_none"


@dataclass(frozen=True)
class AuditScenario:
    scenario_id: str
    task: str
    variation: int
    actions: tuple[str, ...]  # after the first-tick preparation
    simplifications: str = "teleportAction"
    stochastic: bool = False  # declared: contains an RNG-driven process (bees)
    purpose: str = ""

    @property
    def sequence(self) -> tuple[str, ...]:
        return (*FIRST_TICK_PREPARATION, *self.actions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "task": self.task,
            "variation": self.variation,
            "simplifications": self.simplifications,
            "actions": list(self.actions),
            "stochastic": self.stochastic,
            "purpose": self.purpose,
        }


IDLE = "look at agent"
AUDIT_SCENARIOS: tuple[AuditScenario, ...] = (
    AuditScenario(
        "kitchen-deterministic",
        "1-1",
        0,
        (
            "teleport to kitchen",
            "open cupboard",
            "move metal pot to sink",
            "activate sink",
            "deactivate sink",
            "activate stove",
        ),
        purpose="deterministic manipulation, heat and object creation (sink)",
    ),
    AuditScenario(
        "workshop-deterministic",
        "3-1",
        0,
        ("teleport to workshop", "open freezer", "move switch to inventory", IDLE, IDLE),
        purpose="deterministic workshop sequence",
    ),
    AuditScenario(
        "greenhouse-bees",
        "5-1",
        0,
        ("teleport to greenhouse", "open bee hive", IDLE, IDLE, IDLE),
        stochastic=True,
        purpose="bees draw from the global RNG every tick (Bee.scala:174-190)",
    ),
    AuditScenario(
        "greenhouse-ambiguous-soil-bees",
        "5-1",
        0,
        (
            "teleport to greenhouse",
            "move flower pot 1 to inventory",
            "move shovel to sink",
            "pour flower pot 2 into flower pot 1",
            "open bee hive",
            IDLE,
            IDLE,
        ),
        stochastic=True,
        purpose="referent disambiguation falls back to the RNG (docs/21 §3.2), plus bees",
    ),
)


@dataclass(frozen=True)
class Probe:
    """State after k steps under one condition (captured once, identically in all conditions)."""

    k: int
    statuses: tuple[str, ...]
    observations: tuple[str, ...]
    moves: int
    canonical_fingerprint: str
    tree_fingerprint: str
    look: str
    inventory: str
    valid_actions_fingerprint: str
    stochastic_positions: dict[str, Any]
    state: CapturedState = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "k": self.k,
            "statuses": list(self.statuses),
            "moves": self.moves,
            "observations_sha256": sha256_json(list(self.observations)),
            "canonical_fingerprint": self.canonical_fingerprint,
            "tree_fingerprint": self.tree_fingerprint,
            "look_sha256": sha256_json(self.look),
            "inventory_sha256": sha256_json(self.inventory),
            "valid_actions_fingerprint": self.valid_actions_fingerprint,
            "stochastic_positions": self.stochastic_positions,
        }


def stochastic_positions(state: CapturedState) -> dict[str, Any]:
    """Container path of every bee: the stochastic events we can observe."""
    return {
        r.get("name"): r.get("path")
        for r in sorted(state.canonical.objects.values(), key=lambda r: str(r.get("name")))
        if str(r.get("name", "")).startswith("bee ")
    }


def issue(session: ScienceWorldSession, kind: str) -> None:
    if kind == "look":
        session.look()
    elif kind == "inventory":
        session.inventory()
    elif kind == "object_tree":
        session.object_tree()
    elif kind == "valid_actions":
        session.valid_actions()
    elif kind == "valid_action_templates":
        session.valid_action_templates()
    else:
        raise ValueError(f"unknown query kind {kind!r}")


def probe(
    session: ScienceWorldSession, scenario: AuditScenario, queries: tuple[str, ...], k: int
) -> Probe:
    session.load(scenario.task, scenario.variation, scenario.simplifications)
    statuses, observations = [], []
    for action in scenario.sequence[:k]:
        for q in queries:
            issue(session, q)
        r = session.step(action)
        statuses.append(r.status)
        observations.append(r.observation)
    state = capture_state(session)
    return Probe(
        k,
        tuple(statuses),
        tuple(observations),
        state.raw.moves,
        state.canonical.fingerprint,
        sha256_json(state.raw.object_tree),
        state.raw.look,
        state.raw.inventory,
        sha256_json(list(state.raw.valid_actions)),
        stochastic_positions(state),
        state,
    )


@dataclass(frozen=True)
class ConditionRun:
    condition: str
    repeat: int
    process: str  # "fresh" | "shared"
    probes: tuple[Probe, ...]
    wall_s: float


def run_condition(
    scenario: AuditScenario,
    condition: str,
    *,
    repeat: int,
    process: str,
    session: ScienceWorldSession | None = None,
    config: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
) -> ConditionRun:
    t0 = time.perf_counter()
    ks = range(len(scenario.sequence) + 1)
    if session is None:
        with ScienceWorldSession(config, backend_factory=backend_factory) as s:
            probes = tuple(probe(s, scenario, CONDITIONS[condition], k) for k in ks)
    else:
        probes = tuple(probe(session, scenario, CONDITIONS[condition], k) for k in ks)
    return ConditionRun(condition, repeat, process, probes, round(time.perf_counter() - t0, 2))


@dataclass(frozen=True)
class ProbeComparison:
    k: int
    statuses_equal: bool
    observations_equal: bool
    transition_equal: bool  # canonical state equal
    tree_equal: bool
    look_equal: bool
    inventory_equal: bool
    valid_actions_equal: bool
    stochastic_equal: bool
    n_canonical_changes: int
    changed_objects: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "changed_objects": list(self.changed_objects)}


def compare_runs(base: ConditionRun, other: ConditionRun) -> tuple[ProbeComparison, ...]:
    out = []
    for a, b in zip(base.probes, other.probes, strict=True):
        d = canonical_diff(a.state.canonical, b.state.canonical)
        names = sorted(
            {
                str(a.state.canonical.objects.get(c.key.split(":")[0], {}).get("name"))
                for c in d.changes
                if ":" in c.key and c.key.split(":")[0] not in ("world", "door")
            }
            | {n for _, n in d.created_objects}
            | {n for _, n in d.deleted_objects}
        )
        out.append(
            ProbeComparison(
                a.k,
                a.statuses == b.statuses,
                a.observations == b.observations,
                a.canonical_fingerprint == b.canonical_fingerprint,
                a.tree_fingerprint == b.tree_fingerprint,
                a.look == b.look,
                a.inventory == b.inventory,
                a.valid_actions_fingerprint == b.valid_actions_fingerprint,
                a.stochastic_positions == b.stochastic_positions,
                len(d.changes),
                tuple(names[:12]),
            )
        )
    return tuple(out)


@dataclass(frozen=True)
class ScenarioAudit:
    scenario: AuditScenario
    runs: tuple[ConditionRun, ...]

    def baseline(self, process: str = "fresh", repeat: int = 0) -> ConditionRun:
        return next(
            r
            for r in self.runs
            if r.condition == BASELINE and r.process == process and r.repeat == repeat
        )

    def summary(self) -> dict[str, Any]:
        base = self.baseline()
        rows = []
        for r in self.runs:
            if r is base:
                continue
            comps = compare_runs(base, r)
            first = next((c.k for c in comps if not c.transition_equal), None)
            rows.append(
                {
                    "condition": r.condition,
                    "repeat": r.repeat,
                    "process": r.process,
                    "transitions_equal_all_k": all(c.transition_equal for c in comps),
                    "first_k_state_differs": first,
                    "observations_equal_all_k": all(c.observations_equal for c in comps),
                    "statuses_equal_all_k": all(c.statuses_equal for c in comps),
                    "valid_actions_equal_all_k": all(c.valid_actions_equal for c in comps),
                    "look_inventory_equal_all_k": all(
                        c.look_equal and c.inventory_equal for c in comps
                    ),
                    "stochastic_equal_all_k": all(c.stochastic_equal for c in comps),
                    "n_k_state_differs": sum(not c.transition_equal for c in comps),
                    "n_k_valid_actions_differ": sum(not c.valid_actions_equal for c in comps),
                    "per_k": [c.to_dict() for c in comps],
                    "wall_s": r.wall_s,
                }
            )
        return {
            "version": AUDIT_VERSION,
            "scenario": self.scenario.to_dict(),
            "baseline": {"condition": BASELINE, "process": "fresh", "repeat": 0},
            "comparisons": rows,
            "baseline_bee_positions_by_k": [p.stochastic_positions for p in base.probes]
            if self.scenario.stochastic
            else None,
        }


def audit_scenario(
    scenario: AuditScenario,
    *,
    repeats: int = 2,
    shared: bool = True,
    config: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
) -> ScenarioAudit:
    """Every condition ``repeats`` times in fresh JVMs, plus (optionally) all in one JVM."""
    runs = [
        run_condition(
            scenario, c, repeat=i, process="fresh", config=config, backend_factory=backend_factory
        )
        for i in range(repeats)
        for c in CONDITIONS
    ]
    if shared:
        with ScienceWorldSession(config, backend_factory=backend_factory) as s:
            runs += [
                run_condition(scenario, c, repeat=0, process="shared", session=s)
                for c in CONDITIONS
            ]
    return ScenarioAudit(scenario, tuple(runs))
