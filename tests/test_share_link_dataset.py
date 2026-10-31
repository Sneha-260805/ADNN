"""Phase 5E Task 1: sharing-link dataset integration (docs/30). No Java, no records written."""

from __future__ import annotations

import itertools
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from adnn.dataset import prompting as p10
from adnn.dataset import prompting_v11 as p11
from adnn.dataset import share_link_family as fam
from adnn.dataset.rendering import RENDER_STYLES, render_state_text
from adnn.feasibility import share_link_diagnostics as sl
from adnn.sandbox import ToolCall, assess_reversibility, full_hash
from adnn.sandbox.restoration import (
    EXTENSION_PRIMARY_TOOLS,
    PRIMARY_TOOLS,
    declared_reversibility,
)
from adnn.sandbox.state import AGENT_TOOL_NAMES, ALL_TOOL_NAMES, EXTENSION_TOOL_NAMES

ROOT = Path(__file__).resolve().parents[1]
F1, F2 = sl.F1, sl.F2
PLANS = fam.plan_share_scenarios()


# -- declared_reversibility: design table vs brute-force judge --------------------------------
GRID_LINKS = {
    "none": (),
    "custom": (sl.custom("lnk-0001", F1, "view"),),
    "generated": (sl.generated("lnk-0001", F1, "view"),),
    "custom_revoked": (replace(sl.custom("lnk-0001", F1, "view"), active=False),),
    "custom_and_revoked_generated": (
        sl.custom("lnk-0001", F1, "view"),
        sl.generated("lnk-0002", F1, "edit", active=False),
    ),
    "older_revoked_holder": (  # outside the table for revoking lnk-0002
        replace(sl.custom("lnk-0001", F1, "view"), active=False),
        sl.custom("lnk-0002", F1, "edit"),
    ),
    "id_gap": (sl.generated("lnk-0002", F1, "view"),),  # create's next id is taken
    "id_gap_custom": (sl.custom("lnk-0002", F1, "view"),),
}
GRID_TOOLS = {
    "all": ALL_TOOL_NAMES,
    "no_create": tuple(t for t in ALL_TOOL_NAMES if t != "create_share_link"),
    "no_revoke": tuple(t for t in ALL_TOOL_NAMES if t != "revoke_share_link"),
}
GRID_ACTIONS = [
    ToolCall("revoke_share_link", {"link_id": "lnk-0001"}),
    ToolCall("revoke_share_link", {"link_id": "lnk-0002"}),
    ToolCall("create_share_link", {"path": F1, "access": "view", "address": ""}),
    ToolCall("create_share_link", {"path": F1, "access": "view", "address": "q3-board"}),
    ToolCall("create_share_link", {"path": F1, "access": "edit", "address": "q3-board"}),
    ToolCall("create_share_link", {"path": F2, "access": "view", "address": "q3-board"}),
]


@pytest.mark.parametrize(("links", "tools"), list(itertools.product(GRID_LINKS, GRID_TOOLS)))
def test_declared_share_link_rules_agree_with_the_judge(links: str, tools: str) -> None:
    state = sl.world(GRID_LINKS[links], GRID_TOOLS[tools])
    for call in GRID_ACTIONS:
        declared = declared_reversibility(state, call)
        if declared is None:  # outside the design table: judge only
            assert (links, call.args.get("link_id")) == ("older_revoked_holder", "lnk-0002")
            continue
        judged = assess_reversibility(state, call, horizon=3)
        assert judged.is_definitive or not judged.action_ok
        assert (declared.restore_depth, declared.approx_restore_depth) == (
            judged.restore_depth,
            judged.approx_restore_depth,
        ), f"{call} with {links}/{tools}"


def test_legacy_design_table_is_unchanged() -> None:
    assert PRIMARY_TOOLS == ("read_file", "edit_file", "delete_file", "send_email",
                             "transfer_money")  # fmt: skip
    assert set(EXTENSION_PRIMARY_TOOLS) == set(EXTENSION_TOOL_NAMES)
    assert not set(EXTENSION_PRIMARY_TOOLS) & set(PRIMARY_TOOLS)
    state = sl.world()
    assert declared_reversibility(state, ToolCall("restore_file", {"entry_id": "bin-0001"})) is None


# -- family: label consistency (oracle is gold; expectations are only compared) --------------
def test_planned_members_are_definitive_and_agree_with_expectation_and_declaration() -> None:
    rows = [fam.oracle_check(p, m) for p in PLANS for m in fam.pair_members(p)]
    assert rows and all(r["is_definitive"] for r in rows)
    assert [r for r in rows if not r["matches_expectation"]] == []
    assert [r for r in rows if not r["declaration_agrees"]] == []


def test_expectation_mismatch_is_reported_not_forced() -> None:
    plan = PLANS[0]
    wrong = replace(plan.family, expected={v: fam._same("irreversible")
                                           for v in plan.family.pivot_values})  # fmt: skip
    row = fam.oracle_check(replace(plan, family=wrong), fam.pair_members(plan)[0])
    assert row["matches_expectation"] is False
    assert row["oracle_labels_by_horizon"]["3"] != "irreversible"


# -- minimal pairs ------------------------------------------------------------------------------
@pytest.mark.parametrize("plan", PLANS, ids=lambda p: p.scenario_id)
def test_pair_members_share_action_task_and_background(plan: fam.ShareScenarioPlan) -> None:
    members = fam.pair_members(plan)
    assert [m.pivot_value for m in members] == list(plan.family.pivot_values)
    assert len({m.action_text for m in members}) == 1
    assert len({m.task_text for m in members}) == 1
    assert len({(m.state.config, m.state.files) for m in members}) == 1
    a, b = ({k.link_id: k for k in m.state.share_links} for m in members)
    if plan.family.family_id == "s01_link_revoke_address_kind":
        target = members[0].call.args["link_id"]
        assert a.keys() == b.keys()
        assert [i for i in a if a[i] != b[i]] == [target]
    else:  # s02 / s03: the only difference is the appended revoked record
        assert len(b) == len(a) + 1 and {i: b[i] for i in a} == a
        extra = b[max(b)]
        assert not extra.active and extra.custom
        same = extra.access == members[0].call.args["access"]
        assert same is (plan.family.family_id == "s02_link_create_history")


# -- deterministic configuration ----------------------------------------------------------------
def test_generation_configuration_is_deterministic() -> None:
    cfg = fam.GenerationConfig()
    assert cfg.sha256() == fam.GenerationConfig().sha256()
    assert json.loads(json.dumps(cfg.to_dict())) == cfg.to_dict()

    def digest(plans: list[fam.ShareScenarioPlan]) -> list[tuple[str, str, str]]:
        return [(p.scenario_id, m.action_text, full_hash(m.state))
                for p in plans for m in fam.pair_members(p)]  # fmt: skip

    assert digest(fam.plan_share_scenarios(cfg)) == digest(PLANS)
    other = replace(cfg, seed=cfg.seed + 1)
    assert other.sha256() != cfg.sha256()
    assert digest(fam.plan_share_scenarios(other)) != digest(PLANS)


def test_planned_states_are_structurally_distinct_across_the_pilot() -> None:
    from adnn.feasibility.scenario_diversity import scenario_id

    states = [fam.structure(m) for p in PLANS for m in fam.pair_members(p)]
    for level in ("strict", "coarse"):
        assert len({scenario_id(x, level) for x in states}) == len(states)


# -- prompt builder 1.1.0 -----------------------------------------------------------------------
LINKS_MIXED = (
    sl.custom("lnk-0001", F1, "view"),
    sl.generated("lnk-0002", F2, "edit", active=False),
)


@pytest.mark.parametrize("style", RENDER_STYLES)
def test_v11_renders_every_link_field_after_the_unchanged_v10_text(style: str) -> None:
    state = sl.world(LINKS_MIXED)
    text = p11.render_state_text_v11(state, style)
    assert text.startswith(render_state_text(state, style) + "\n")
    tail = text[len(render_state_text(state, style)) :]
    gen = sl.generated("lnk-0002", F2, "edit").address
    for token in ("lnk-0001", F1, "view", "q3-board", "custom", "active",
                  "lnk-0002", F2, "edit", gen, "generated", "revoked"):  # fmt: skip
        assert token in tail, (style, token)


def test_v11_link_section_is_always_present() -> None:
    empty = sl.world()
    assert p11.render_state_text_v11(empty, "kv").endswith("Share links:\n  (none)")
    assert p11.render_state_text_v11(empty, "prose").endswith("Share links: none.")
    assert p11.render_state_text_v11(empty, "compact").endswith("links: -")
    assert p11.render_observation_v11(empty) == p11.render_state_text_v11(empty, "kv")


def test_v11_tool_list_follows_permissions() -> None:
    names = lambda s: [t["name"] for t in p11.inputs_from_state("t", s, "kv").tools]  # noqa: E731
    assert names(sl.world()) == list(ALL_TOOL_NAMES)
    assert names(sl.world(tools=AGENT_TOOL_NAMES)) == list(AGENT_TOOL_NAMES)
    agent = p11.build_agent_messages(p11.inputs_from_state("t", sl.world(), "kv"))
    assert (
        "- create_share_link(path: string, access: string, address: string)"
        in (agent.messages[0]["content"])
    )


LEAK = re.compile(r"reversib|irrevers|restore_depth|witness|certificate|s0[12]_", re.I)


@pytest.mark.parametrize("plan", PLANS[::3], ids=lambda p: p.scenario_id)
def test_v11_prompts_leak_no_label_or_recovery_certificate(plan: fam.ShareScenarioPlan) -> None:
    for m in fam.pair_members(plan):
        a = assess_reversibility(m.state, m.call, horizon=3)
        witness = [json.dumps(c.to_dict()) for c in (a.exact_witness or a.approx_witness or ())]
        assert witness  # every planned member has a recovery certificate to hide
        inputs = p11.inputs_from_state(m.task_text, m.state, "kv")
        probe = p11.build_probe_prompt(inputs, m.action_text)
        stated = p11.build_stated_prompt(inputs, m.action_text)
        probe_text = "\n".join(x["content"] for x in probe.messages)
        assert not LEAK.search(probe_text)
        stated_user = stated.messages[1]["content"]
        question = stated_user[stated_user.index("Question:") :]
        assert not LEAK.search(stated_user.replace(question, ""))
        assert question == p10.STATED_USER_TEMPLATE[
            p10.STATED_USER_TEMPLATE.index("Question:") :].format(horizon=3)  # fmt: skip
        for w in witness:
            assert w not in probe_text and w not in stated_user
        for forbidden in (plan.scenario_id, plan.family.family_id, m.pivot_value + "_access"):
            assert forbidden not in probe_text


def test_pair_prompts_differ_only_in_the_state_text() -> None:
    plan = PLANS[0]
    a, b = fam.pair_members(plan)[:2]
    pa = p11.build_probe_prompt(p11.inputs_from_state(a.task_text, a.state, "kv"), a.action_text)
    pb = p11.build_probe_prompt(p11.inputs_from_state(b.task_text, b.state, "kv"), b.action_text)
    ma, mb = pa.messages, pb.messages
    assert [m["role"] for m in ma] == [m["role"] for m in mb]
    assert ma[0] == mb[0] and ma[2] == mb[2]  # tools and action text identical
    assert ma[1] != mb[1] and pa.prompt_sha256 != pb.prompt_sha256


# -- backward compatibility of builder 1.0.0 -------------------------------------------------
def test_v10_is_unchanged_and_v11_differs_only_by_version_stamp() -> None:
    assert p10.PROMPT_BUILDER_VERSION == "1.0.0" and p11.PROMPT_BUILDER_VERSION == "1.1.0"
    inputs = p10.PromptInputs("Task.", "State.", ())
    old, new = p10.build_probe_prompt(inputs, "{}"), p11.build_probe_prompt(inputs, "{}")
    assert old.messages == new.messages and old.version == "1.0.0" and new.version == "1.1.0"
    assert old.prompt_sha256 != new.prompt_sha256
    s_old, s_new = p10.build_stated_prompt(inputs, "{}"), p11.build_stated_prompt(inputs, "{}")
    assert s_old.messages == s_new.messages
    hist = (p10.AgentTurn("{}", "ok", "State."),)
    assert p10.build_agent_messages(inputs, hist).messages == (
        p11.build_agent_messages(inputs, hist).messages
    )


def test_v10_prompt_hashes_of_the_historical_pilot_still_rebuild() -> None:
    path = ROOT / "data/pilot/pilot_v0.1.jsonl"
    tool_sets = json.loads((ROOT / "data/pilot/tool_sets.json").read_text("utf-8"))
    records = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x][:20]
    for r in records:
        inputs = p10.PromptInputs.from_example(r, tool_sets)
        assert r["meta"]["prompt_builder_version"] == "1.0.0"
        probe = p10.build_probe_prompt(inputs, r["action_text"])
        assert probe.prompt_sha256 == r["meta"]["probe_prompt_sha256"]
