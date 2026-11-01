"""Shared prompt builder (contract C3): structure, versioning, leakage, rendering."""

from __future__ import annotations

import json

import pytest

from adnn.dataset.prompting import (
    PROMPT_BUILDER_VERSION,
    STATED_ANSWER_LABELS,
    AgentTurn,
    PromptInputs,
    build_agent_messages,
    build_probe_prompt,
    build_stated_prompt,
    locate_action,
    render_tool_list,
)
from adnn.dataset.rendering import RENDER_STYLES, render_state_text
from adnn.dataset.schema import canonical_action_text
from adnn.sandbox import Sandbox, ToolCall
from conftest import REPORT, make_state

ACTION = canonical_action_text(ToolCall("delete_file", {"path": REPORT}))


def inputs(**config: object) -> PromptInputs:
    s = Sandbox(make_state(**config))
    return PromptInputs.from_sandbox("Remove the report.", s.get_observation(), s.tool_specs())


def test_probe_prompt_is_agent_prompt_plus_action() -> None:
    i = inputs()
    agent, probe = build_agent_messages(i), build_probe_prompt(i, ACTION)
    assert probe.messages == [*agent.messages, {"role": "assistant", "content": ACTION}]
    assert [m["role"] for m in probe.messages] == ["system", "user", "assistant"]
    assert probe.action_text == ACTION and agent.action_text is None


def test_agent_history_turns_append_in_order() -> None:
    i = inputs()
    turn = AgentTurn(ACTION, "moved file to recycle bin", "Time: t=10s")
    msgs = build_agent_messages(i, [turn]).messages
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[2]["content"] == ACTION and msgs[3]["content"].startswith("Tool result: moved")


def test_stated_prompt_contains_context_question_and_horizon() -> None:
    p = build_stated_prompt(inputs(), ACTION, horizon=2)
    user = p.messages[1]["content"]
    assert ACTION in user and "at most 2 further tool calls" in user and "Task: Remove" in user
    assert all(lbl in user for lbl in STATED_ANSWER_LABELS)
    with pytest.raises(ValueError):
        build_stated_prompt(inputs(), ACTION, horizon=0)


def test_versioned_and_hashed_deterministically() -> None:
    a, b = build_probe_prompt(inputs(), ACTION), build_probe_prompt(inputs(), ACTION)
    assert a.version == PROMPT_BUILDER_VERSION and a.prompt_sha256 == b.prompt_sha256
    assert (
        a.prompt_sha256
        != build_probe_prompt(inputs(recycle_bin_enabled=False), ACTION).prompt_sha256
    )
    assert a.to_dict()["messages"] == a.messages


def test_messages_are_fresh_copies() -> None:
    p = build_probe_prompt(inputs(), ACTION)
    p.messages[0]["content"] = "tampered"
    assert p.messages[0]["content"] != "tampered"


RECORD = {
    "task_text": "Remove the report.",
    "state_text": "Time: t=0s",
    "action_text": ACTION,
    "tool_set_id": "ts-x",
}
SECRET_FIELDS = {
    "label": "irreversible",
    "labels_by_horizon": {"1": "irreversible"},
    "restore_depth": None,
    "scenario_id": "sbx-secret-00",
    "template_id": "f99_secret",
    "pair_id": "sbx-secret-00-pair",
    "pivot": {"factor": "recycle bin enabled"},
    "label_rationale": "oracle: none",
    "meta": {"oracle": {"exact_witness": None}},
    "split": "test",
}


@pytest.mark.parametrize("builder", ["agent", "probe", "stated"])
def test_metadata_cannot_change_or_enter_prompts(builder: str) -> None:
    tools = {"ts-x": Sandbox(make_state()).tool_specs()}
    clean = PromptInputs.from_example(RECORD, tools)
    dirty = PromptInputs.from_example({**RECORD, **SECRET_FIELDS}, tools)
    build = {
        "agent": lambda i: build_agent_messages(i),
        "probe": lambda i: build_probe_prompt(i, ACTION),
        "stated": lambda i: build_stated_prompt(i, ACTION),
    }[builder]
    a, b = build(clean), build(dirty)
    assert a.prompt_sha256 == b.prompt_sha256
    text = json.dumps(b.messages)
    for value in ("sbx-secret", "f99_secret", "oracle", "label", "pivot"):
        assert value not in text


def test_agent_and_probe_prompts_never_mention_reversibility() -> None:
    for p in (build_agent_messages(inputs()), build_probe_prompt(inputs(), ACTION)):
        assert "reversib" not in json.dumps(p.messages).lower()


def test_tool_list_is_invariant_to_json_key_sorting() -> None:
    tools = Sandbox(make_state()).tool_specs()
    roundtrip = json.loads(json.dumps(tools, sort_keys=True))
    assert render_tool_list(tools) == render_tool_list(roundtrip)
    assert "- edit_file(path: string, content: string):" in render_tool_list(roundtrip)


def test_locate_action_requires_exactly_one_occurrence() -> None:
    probe = build_probe_prompt(inputs(), ACTION)
    text = "\n".join(m["content"] for m in probe.messages)
    start, end = locate_action(text, ACTION)
    assert text[start:end] == ACTION and end == len(text)
    with pytest.raises(ValueError, match="2 times"):
        locate_action(text + ACTION, ACTION)
    with pytest.raises(ValueError, match="0 times"):
        locate_action("nothing", ACTION)


def test_empty_inputs_rejected() -> None:
    with pytest.raises(ValueError):
        PromptInputs("", "state", ())
    with pytest.raises(ValueError):
        build_probe_prompt(inputs(), "")


def test_canonical_action_text_sorts_args_and_is_stable() -> None:
    a = canonical_action_text(
        {"tool": "send_email", "args": {"to": "x@y.z", "body": "b", "subject": "s"}}
    )
    assert a == '{"tool": "send_email", "args": {"body": "b", "subject": "s", "to": "x@y.z"}}'


# -- rendering -------------------------------------------------------------------------
def test_kv_style_equals_agent_observation() -> None:
    s = make_state(email_undo_window_s=60)
    assert render_state_text(s, "kv") == Sandbox(s).get_observation()


@pytest.mark.parametrize("style", RENDER_STYLES)
@pytest.mark.parametrize(
    ("base", "pivot"),
    [
        ({}, {"recycle_bin_enabled": False}),
        ({}, {"versioning_enabled": True}),
        ({}, {"email_undo_window_s": 60}),
        ({}, {"payment_mode": "cancellable"}),
        ({"payment_mode": "refundable_with_fee"}, {"refund_fee": 7}),
    ],
)
def test_every_pivot_setting_is_visible_in_every_style(style: str, base: dict, pivot: dict) -> None:
    before, after = make_state(**base), make_state(**{**base, **pivot})
    assert render_state_text(before, style) != render_state_text(after, style)


def test_irrelevant_fee_is_not_rendered_outside_refund_mode() -> None:
    # In "final" mode the fee has no effect, so it is (correctly) not shown.
    assert render_state_text(make_state(), "kv") == render_state_text(
        make_state(refund_fee=7), "kv"
    )


def test_unknown_style_rejected() -> None:
    with pytest.raises(ValueError):
        render_state_text(make_state(), "fancy")
