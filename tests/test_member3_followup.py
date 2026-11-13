import importlib.util
from pathlib import Path

import pytest

from adnn.behaviour.prompt_conditions import apply_condition, messages_sha256
from adnn.behaviour.runner import run_task
from adnn.tasks import load_tasks


spec = importlib.util.spec_from_file_location(
    "followup", Path(__file__).parents[1] / "scripts/behaviour/followup.py",
)
followup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(followup)


def test_conditions_do_not_mutate_frozen_messages():
    original = [{"role": "system", "content": "Original"},
                {"role": "user", "content": "Task"}]
    modified = apply_condition(original, agent="format_v1")
    assert original[0]["content"] == "Original"
    assert modified[1] == original[1]
    assert '"args": {}' in modified[0]["content"]
    assert "safer alternative" not in modified[0]["content"]
    assert apply_condition(original) == original
    assert messages_sha256(original) != messages_sha256(modified)


def test_careful_and_format_are_distinct():
    messages = [{"role": "system", "content": "Original"}]
    careful = apply_condition(messages, agent="format_careful_v1")
    assert "safer alternative" in careful[0]["content"]
    assert '"args": {}' in careful[0]["content"]
    recovery = apply_condition(messages, judgment="recovery_v1")
    assert "executes first" in recovery[0]["content"]
    assert '"args": {}' not in recovery[0]["content"]


def test_dev_selection_never_reads_test():
    class FakeDataset:
        def iter_split(self, split):
            assert split == "train"
            return iter([{"scenario_id": s, "id": str(i)}
                         for s in ["a", "b", "c"] for i in range(2)])
    records, groups = followup.select_development(FakeDataset(), 2, 42)
    assert len(records) == 4
    assert {r["scenario_id"] for r in records} == set(groups)
    assert followup.select_development(FakeDataset(), 2, 42) == (records, groups)
    with pytest.raises(ValueError):
        followup.select_development(FakeDataset(), 0, 42)


def test_resume_checks_configuration_and_duplicates():
    config = {"planned_ids": ["a", "b"], "model": "model-one"}
    assert followup.validate_resume(config, config, [{"task_id": "a"}]) == {"a"}
    with pytest.raises(ValueError):
        followup.validate_resume(config, config | {"model": "model-two"}, [])
    with pytest.raises(ValueError):
        followup.validate_resume(config, config, [{"task_id": "a"}, {"task_id": "a"}])
    with pytest.raises(ValueError):
        followup.validate_resume(config, config, [{"task_id": "unknown"}])


def test_interrupted_trace_preserved(tmp_path):
    first = tmp_path / "task.jsonl"
    first.write_text("original partial trace")
    assert followup.fresh_trace_path(tmp_path, "task").name == "task.attempt-2.jsonl"
    assert first.read_text() == "original partial trace"


def test_malformed_outcomes_fail_explicitly(tmp_path):
    p = tmp_path / "outcomes.jsonl"
    p.write_text('{"task_id":"a"}\n{"unfinished":')
    with pytest.raises(ValueError, match="Invalid outcomes line 2"):
        followup.completed_rows(p)


def test_format_guidance_does_not_relax_parser():
    task = load_tasks("data/tasks/rq3-tasks-1.0")[0]
    seen = []
    def generate(messages):
        seen.append(messages)
        return '{"tool":"finish"}'
    outcome = run_task(task, generate, agent_condition="format_v1")
    assert outcome["parse_failures"] == 15
    assert outcome["termination"] == "step_limit"
    assert '"args": {}' in seen[0][0]["content"]
    assert all(t["state_before"] == t["state_after"] for t in outcome["trace"])
