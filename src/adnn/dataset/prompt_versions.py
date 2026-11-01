"""Prompt-builder version registry for loading and validating datasets (docs/30 §4).

A record's ``meta.prompt_builder_version`` selects how its state text was rendered and how
its prompts are rebuilt. Only the versions listed here are accepted; anything else is
rejected with :class:`UnsupportedPromptBuilderError`. 1.0.0 maps to the original, frozen
builder and renderer, so legacy datasets are handled exactly as before.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from adnn.dataset import prompting as _v10
from adnn.dataset import prompting_v11 as _v11
from adnn.dataset.rendering import render_state_text


class UnsupportedPromptBuilderError(ValueError):
    """A dataset or record names a prompt-builder version this code cannot rebuild."""


@dataclass(frozen=True)
class PromptBuilder:
    version: str
    render_state_text: Callable[[Any, str], str]
    build_agent_messages: Callable[..., _v10.PromptBundle]
    build_probe_prompt: Callable[..., _v10.PromptBundle]
    build_stated_prompt: Callable[..., _v10.PromptBundle]
    renders_share_links: bool


BUILDERS: dict[str, PromptBuilder] = {
    _v10.PROMPT_BUILDER_VERSION: PromptBuilder(
        _v10.PROMPT_BUILDER_VERSION,
        render_state_text,
        _v10.build_agent_messages,
        _v10.build_probe_prompt,
        _v10.build_stated_prompt,
        renders_share_links=False,
    ),
    _v11.PROMPT_BUILDER_VERSION: PromptBuilder(
        _v11.PROMPT_BUILDER_VERSION,
        _v11.render_state_text_v11,
        _v11.build_agent_messages,
        _v11.build_probe_prompt,
        _v11.build_stated_prompt,
        renders_share_links=True,
    ),
}
SUPPORTED_VERSIONS: tuple[str, ...] = tuple(BUILDERS)


def builder_for(version: object) -> PromptBuilder:
    if not isinstance(version, str) or version not in BUILDERS:
        raise UnsupportedPromptBuilderError(
            f"unsupported prompt builder version {version!r}; supported: {SUPPORTED_VERSIONS}"
        )
    return BUILDERS[version]
