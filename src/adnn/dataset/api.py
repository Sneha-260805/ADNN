"""Stable, read-only consumer API for Members 2 and 3 (docs/15_TEAM_HANDOFF.md).

This is the only dataset module consumers need besides ``prompting`` (and
``adnn.sandbox`` for RQ3). It never imports the generator (``pilot``) or the
validator, and it keeps the two kinds of information apart:

* **model-visible input** — prompts, built only through the shared builder
  (:meth:`LoadedDataset.probe_prompt`, :meth:`LoadedDataset.stated_prompt`);
* **evaluation metadata** — labels, horizons, provisional flags, split, ids
  (:meth:`LoadedDataset.eval_metadata`), which must never be put into a prompt.

Loading verifies the files against the checksums in ``manifest.json``, so a
stale or edited dataset fails loudly instead of silently changing results.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adnn.dataset.prompting import (
    PROMPT_BUILDER_VERSION,
    PromptBundle,
    PromptInputs,
    build_probe_prompt,
    build_stated_prompt,
)
from adnn.dataset.schema import PRIMARY_HORIZON, read_jsonl, sha256_file
from adnn.sandbox import Sandbox, ToolCall, WorldState

API_VERSION = "1.0.0"


class DatasetIntegrityError(RuntimeError):
    """A dataset file does not match its manifest, or a prompt does not match its record."""


@dataclass(frozen=True)
class EvalMetadata:
    """Everything needed to *score* a prediction. Never part of a prompt."""

    example_id: str
    split: str  # "train" | "test"
    label: str  # primary horizon (3)
    labels_by_horizon: Mapping[str, str]  # {"1": ..., "2": ..., "3": ...}
    label_provisional: bool
    provisional_reasons: tuple[str, ...]
    scenario_id: str
    template_id: str  # scenario family = split unit
    pair_id: str | None
    action_verb: str
    restore_depth: int | None
    approx_restore_depth: int | None

    def label_at(self, horizon: int) -> str:
        return self.labels_by_horizon[str(horizon)]


@dataclass(frozen=True)
class LoadedDataset:
    directory: Path
    manifest: Mapping[str, Any]
    records: tuple[Mapping[str, Any], ...]
    split: Mapping[str, Any]
    tool_sets: Mapping[str, Any]

    # -- lookup ---------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.records)

    def by_id(self, example_id: str) -> Mapping[str, Any]:
        for r in self.records:
            if r["id"] == example_id:
                return r
        raise KeyError(example_id)

    def split_of(self, record: Mapping[str, Any]) -> str:
        """Split by scenario family (``template_id``), never by row."""
        fam = record["template_id"]
        if fam in self.split["test_families"]:
            return "test"
        if fam in self.split["train_families"]:
            return "train"
        raise DatasetIntegrityError(f"family {fam} is in no split")

    def iter_split(self, name: str) -> Iterator[Mapping[str, Any]]:
        if name not in ("train", "test"):
            raise ValueError("split name must be 'train' or 'test'")
        return (r for r in self.records if self.split_of(r) == name)

    def minimal_pairs(self) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
        """(pivot value A, pivot value B) member pairs, sorted by pair id."""
        groups: dict[str, list[Mapping[str, Any]]] = {}
        for r in self.records:
            if r["pair_id"]:
                groups.setdefault(r["pair_id"], []).append(r)
        return [tuple(sorted(m, key=lambda r: r["id"])) for _, m in sorted(groups.items())]  # type: ignore[misc]

    # -- model-visible input ------------------------------------------------------
    def prompt_inputs(self, record: Mapping[str, Any]) -> PromptInputs:
        return PromptInputs.from_example(record, self.tool_sets)

    def probe_prompt(self, record: Mapping[str, Any]) -> PromptBundle:
        """RQ1 prompt, verified against the hash stored when the dataset was built."""
        bundle = build_probe_prompt(self.prompt_inputs(record), record["action_text"])
        _check_hash(record, bundle, "probe_prompt_sha256")
        return bundle

    def stated_prompt(
        self, record: Mapping[str, Any], horizon: int = PRIMARY_HORIZON
    ) -> PromptBundle:
        """RQ2 prompt. The stored hash covers the primary horizon only."""
        bundle = build_stated_prompt(self.prompt_inputs(record), record["action_text"], horizon)
        if horizon == PRIMARY_HORIZON:
            _check_hash(record, bundle, "stated_prompt_sha256")
        return bundle

    # -- evaluation metadata -----------------------------------------------------------
    def eval_metadata(self, record: Mapping[str, Any]) -> EvalMetadata:
        return EvalMetadata(
            example_id=record["id"],
            split=self.split_of(record),
            label=record["label"],
            labels_by_horizon=dict(record["labels_by_horizon"]),
            label_provisional=record["label_provisional"],
            provisional_reasons=tuple(record["provisional_reasons"]),
            scenario_id=record["scenario_id"],
            template_id=record["template_id"],
            pair_id=record["pair_id"],
            action_verb=record["action_verb"],
            restore_depth=record["restore_depth"],
            approx_restore_depth=record["approx_restore_depth"],
        )


def _check_hash(record: Mapping[str, Any], bundle: PromptBundle, key: str) -> None:
    stored = record["meta"].get(key)
    if bundle.prompt_sha256 != stored:
        raise DatasetIntegrityError(
            f"{record['id']}: rebuilt {bundle.kind} prompt does not match the dataset "
            f"(builder {PROMPT_BUILDER_VERSION} vs record "
            f"{record['meta'].get('prompt_builder_version')}); regenerate the dataset"
        )


def load_dataset(directory: str | Path, *, verify: bool = True) -> LoadedDataset:
    """Load a generated dataset directory (e.g. ``data/pilot``).

    With ``verify=True`` (default) every file must match the SHA-256 recorded in
    ``manifest.json``; otherwise :class:`DatasetIntegrityError` is raised.
    """
    d = Path(directory)
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    files = {
        "dataset": manifest["files"]["dataset"],
        "tool_sets": manifest["files"]["tool_sets"],
        "split": manifest["split"],
    }
    if verify:
        for name, entry in files.items():
            if sha256_file(d / entry["file"]) != entry["sha256"]:
                raise DatasetIntegrityError(f"{name} file does not match manifest checksum")
    return LoadedDataset(
        directory=d,
        manifest=manifest,
        records=tuple(read_jsonl(d / files["dataset"]["file"])),
        split=json.loads((d / files["split"]["file"]).read_text(encoding="utf-8")),
        tool_sets=json.loads((d / files["tool_sets"]["file"]).read_text(encoding="utf-8")),
    )


def sandbox_from_record(record: Mapping[str, Any]) -> Sandbox:
    """A fresh sandbox in the record's initial state (the action is NOT applied).

    Note: ``Sandbox.get_observation()`` always uses the ``kv`` rendering; the
    record's ``state_text`` may use another style (``record["render_style"]``).
    """
    return Sandbox(WorldState.from_dict(dict(record["state_struct"])))


def action_call(record: Mapping[str, Any]) -> ToolCall:
    """The record's candidate action as a :class:`ToolCall` (for ``Sandbox.execute``)."""
    return ToolCall.from_obj(record["action_call"])
