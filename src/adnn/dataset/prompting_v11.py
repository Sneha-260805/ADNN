"""Prompt builder 1.1.0: sharing-link states (Candidate A; docs/30 §4).

Builder 1.0.0 (:mod:`adnn.dataset.prompting`) and its state renderers know nothing about
sharing links: ``render_state`` and the ``prose``/``compact`` styles omit them, so a 1.0.0
prompt for a link world would hide the very state the label depends on. 1.0.0 stays frozen
and byte-identical; this module is a separate, versioned interface.

What 1.1.0 changes, and nothing else:

* **State text.** Each 1.0.0 rendering style plus one ``Share links`` section listing every
  link record, active *and* revoked, with file, access, address and whether the address is
  custom or generated. The section is always present (``(none)`` / ``none`` / ``-``), so its
  presence never signals a link family.
* **Version stamp.** Bundles carry ``1.1.0`` and their digest covers it.

Templates, tool-list format, message structure and :class:`PromptInputs` are reused from
1.0.0 unchanged; the tool list is still ``tool_specs_for(state)``, which includes the
extension tools exactly when they are permitted. Labels, depths and witnesses never reach a
prompt: :func:`inputs_from_state` reads only the task text, the world state and its tool specs.
"""

from __future__ import annotations

from collections.abc import Sequence

from adnn.dataset.prompting import (
    AGENT_RESULT_TEMPLATE,
    AGENT_SYSTEM_TEMPLATE,
    AGENT_USER_TEMPLATE,
    STATED_SYSTEM,
    STATED_USER_TEMPLATE,
    AgentTurn,
    PromptBundle,
    PromptInputs,
    render_tool_list,
)
from adnn.dataset.rendering import RENDER_STYLES, render_state_text
from adnn.dataset.schema import PRIMARY_HORIZON, sha256_text, stable_json
from adnn.sandbox import WorldState
from adnn.sandbox.state import ShareLink
from adnn.sandbox.tools import tool_specs_for

PROMPT_BUILDER_VERSION = "1.1.0"
BASE_PROMPT_BUILDER_VERSION = "1.0.0"


# -- state text -----------------------------------------------------------------------------
def _kind(k: ShareLink) -> str:
    return "custom" if k.custom else "generated"


def _status(k: ShareLink) -> str:
    return "active" if k.active else "revoked"


def _links_kv(state: WorldState) -> str:
    items = [
        f"  {k.link_id}: {k.path}, {k.access} access, {_kind(k)} address {k.address}, {_status(k)}"
        for k in state.share_links
    ]
    return "\n".join(["Share links:", *(items or ["  (none)"])])


def _links_prose(state: WorldState) -> str:
    items = [
        f"{k.link_id} gives {k.access} access to {k.path} at the {_kind(k)} address "
        f"{k.address} ({_status(k)})"
        for k in state.share_links
    ]
    return "Share links: " + ("; ".join(items) if items else "none") + "."


def _links_compact(state: WorldState) -> str:
    items = [
        f"{k.link_id} {k.path} {k.access} {_kind(k)}:{k.address} {_status(k)}"
        for k in state.share_links
    ]
    return "links: " + (", ".join(items) if items else "-")


_LINK_SECTIONS = {"kv": _links_kv, "prose": _links_prose, "compact": _links_compact}


def render_state_text_v11(state: WorldState, style: str) -> str:
    """The 1.0.0 rendering of ``style`` followed by the share-link section."""
    if style not in RENDER_STYLES:
        raise ValueError(f"unknown render style {style!r}; expected one of {RENDER_STYLES}")
    return render_state_text(state, style) + "\n" + _LINK_SECTIONS[style](state)


def render_observation_v11(state: WorldState) -> str:
    """RQ3 observation for link worlds. ``Sandbox.get_observation()`` stays on 1.0.0."""
    return render_state_text_v11(state, "kv")


def inputs_from_state(task_text: str, state: WorldState, style: str) -> PromptInputs:
    """Prompt inputs built from the task text and the world state only (no record fields)."""
    state_text = render_state_text_v11(state, style)
    return PromptInputs(task_text, state_text, tuple(tool_specs_for(state)))


# -- builders (1.0.0 templates, 1.1.0 stamp) ------------------------------------------------
def _bundle(kind: str, messages: list[tuple[str, str]], action_text: str | None) -> PromptBundle:
    digest = sha256_text(
        stable_json({"kind": kind, "version": PROMPT_BUILDER_VERSION, "messages": messages})
    )
    return PromptBundle(kind, PROMPT_BUILDER_VERSION, tuple(messages), action_text, digest)


def build_agent_messages(inputs: PromptInputs, history: Sequence[AgentTurn] = ()) -> PromptBundle:
    msgs = [
        ("system", AGENT_SYSTEM_TEMPLATE.format(tools=render_tool_list(inputs.tools))),
        ("user", AGENT_USER_TEMPLATE.format(task=inputs.task_text, state=inputs.state_text)),
    ]
    for turn in history:
        msgs.append(("assistant", turn.action_text))
        msgs.append(
            ("user", AGENT_RESULT_TEMPLATE.format(result=turn.result_text, state=turn.observation))
        )
    return _bundle("agent", msgs, None)


def build_probe_prompt(inputs: PromptInputs, action_text: str) -> PromptBundle:
    if not action_text:
        raise ValueError("action_text must be non-empty")
    msgs = list(build_agent_messages(inputs)._messages)
    msgs.append(("assistant", action_text))
    return _bundle("probe", msgs, action_text)


def build_stated_prompt(
    inputs: PromptInputs, action_text: str, horizon: int = PRIMARY_HORIZON
) -> PromptBundle:
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    user = STATED_USER_TEMPLATE.format(
        task=inputs.task_text,
        state=inputs.state_text,
        tools=render_tool_list(inputs.tools),
        action=action_text,
        horizon=horizon,
    )
    return _bundle("stated", [("system", STATED_SYSTEM), ("user", user)], action_text)
