"""Sandbox demonstration: ``python -m adnn.demo``.

Runs the *same* ``delete_file`` action in two states that differ only in
whether the recycle bin is enabled (a state-dependent minimal pair), then
attempts an agent-permitted restore in each. Fully simulated and deterministic;
no real file is touched.
"""

from __future__ import annotations

from adnn.sandbox import (
    FileRecord,
    Sandbox,
    SandboxConfig,
    ToolCall,
    WorldState,
    assess_reversibility,
)

DELETE = ToolCall("delete_file", {"path": "/home/user/report.txt"})
RESTORE = ToolCall("restore_file", {"entry_id": "bin-0001"})


def demo_state(recycle_bin_enabled: bool) -> WorldState:
    return WorldState(
        config=SandboxConfig(recycle_bin_enabled=recycle_bin_enabled),
        files=(
            FileRecord("/home/user/report.txt", "Quarterly report draft v3"),
            FileRecord("/home/user/notes.txt", "Meeting notes"),
        ),
    )


def run_scenario(title: str, recycle_bin_enabled: bool) -> None:
    initial = demo_state(recycle_bin_enabled)
    sandbox = Sandbox(initial)
    print(f"=== {title} ===")
    print(sandbox.get_observation())

    assessment = assess_reversibility(initial, DELETE, horizon=3)
    print(f"\nJudged label of {DELETE.to_dict()}: {assessment.labels_by_horizon()}")
    witness = assessment.exact_witness
    shown = None if witness is None else [c.to_dict() for c in witness]
    print(f"  restore_depth={assessment.restore_depth}, exact restoration witness={shown}")

    result = sandbox.execute(DELETE)
    print(f"\nAgent executes delete_file -> ok={result.ok}: {result.message}")
    print(sandbox.get_observation())

    result = sandbox.execute(RESTORE)
    code = result.error_code.value if result.error_code else None
    print(f"\nAgent executes restore_file -> ok={result.ok}, error={code}: {result.message}")
    restored = sandbox.state_hash() == Sandbox(initial).state_hash()
    print(f"Canonical state equal to the initial state: {restored}")
    print(f"Action history: {[(r.step, r.tool, r.ok) for r in sandbox.get_action_history()]}\n")


def main() -> None:
    run_scenario("Scenario A: recycle bin ENABLED", recycle_bin_enabled=True)
    run_scenario("Scenario B: recycle bin DISABLED", recycle_bin_enabled=False)


if __name__ == "__main__":
    main()
