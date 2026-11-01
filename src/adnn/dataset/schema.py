"""Dataset record schema (contract C1, docs/05_DATASET_SPECIFICATION.md §2).

Records are plain JSON objects (one per JSONL line). This module defines the
field names, vocabularies and the canonical action text, and nothing else.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from adnn.sandbox import ToolCall

LABELS: tuple[str, ...] = ("reversible", "partially_reversible", "irreversible")
HORIZONS: tuple[int, ...] = (1, 2, 3)
PRIMARY_HORIZON = 3
ENVIRONMENTS: tuple[str, ...] = ("sandbox", "scienceworld", "toolemu")
SOURCES: tuple[str, ...] = ("sandbox_design", "scienceworld_bfs", "toolemu_manual")

REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "environment",
    "state_text",
    "action_text",
    "label",
    "horizon",
    "source",
)
EXTENSION_FIELDS: tuple[str, ...] = (
    "scenario_id",
    "template_id",
    "pair_id",
    "pivot",
    "labels_by_horizon",
    "restore_depth",
    "approx_restore_depth",
    "task_text",
    "tool_set_id",
    "action_verb",
    "action_call",
    "state_struct",
    "render_style",
    "label_rationale",
    "label_provisional",
    "provisional_reasons",
    "meta",
    "dataset_version",
)
ALL_FIELDS: tuple[str, ...] = REQUIRED_FIELDS + EXTENSION_FIELDS

# Fields that a prompt may be built from. Everything else is research metadata
# and must never influence model input (enforced by adnn.dataset.prompting).
PROMPT_INPUT_FIELDS: tuple[str, ...] = ("task_text", "state_text", "action_text", "tool_set_id")

# Reasons a label is provisional (docs/13_PILOT_DATASET.md §5).
PROVISIONAL_PARTIAL = "partial_reversibility_definition_pending_professor"
PROVISIONAL_OQ21 = "label_changes_under_alternative_information_rule:OQ-21"


def canonical_action_text(call: ToolCall | Mapping[str, Any]) -> str:
    """The exact action string shown to models: ``{"tool": ..., "args": {...}}``.

    Key order is fixed (``tool`` then ``args``; argument names sorted), with
    JSON default separators. Minimal-pair members must be byte-identical here.
    """
    c = ToolCall.from_obj(call)
    payload = {"tool": c.tool, "args": {k: c.args[k] for k in sorted(c.args)}}
    return json.dumps(payload, ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in records:
            fh.write(stable_json(r) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
