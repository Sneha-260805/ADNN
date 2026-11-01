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
Prompts are rebuilt with the builder version recorded in each record
(:mod:`adnn.dataset.prompt_versions`: 1.0.0 or 1.1.0); unknown versions are
rejected at load time. A dataset without a split (``"split": null`` in the
manifest, e.g. the sharing-link diagnostic pilot) loads with every record in
split ``"unsplit"``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adnn.dataset.prompt_versions import (
    PromptBuilder,
    UnsupportedPromptBuilderError,
    builder_for,
)
from adnn.dataset.prompting import PromptBundle, PromptInputs
from adnn.dataset.schema import PRIMARY_HORIZON, read_jsonl, sha256_file
from adnn.sandbox import Sandbox, ToolCall, WorldState

API_VERSION = "1.0.0"


class DatasetIntegrityError(RuntimeError):
    """A dataset file does not match its manifest, or a prompt does not match its record."""


@dataclass(frozen=True)
class EvalMetadata:
    """Everything needed to *score* a prediction. Never part of a prompt."""

    example_id: str
    split: str  # "train" | "test" ("unsplit" for a dataset without a split)
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
    split: Mapping[str, Any] | None
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
        """Split by scenario family (``template_id``), or by scenario group (``scenario_id``)
        for a ``scenario_grouped`` split (ADR-0009); never by row."""
        if self.split is None:
            return "unsplit"
        if self.split.get("kind") == "scenario_grouped":
            sid = record["scenario_id"]
            if sid in self.split["test_scenarios"]:
                return "test"
            if sid in self.split["train_scenarios"]:
                return "train"
            raise DatasetIntegrityError(f"scenario {sid} is in no split")
        fam = record["template_id"]
        if fam in self.split["test_families"]:
            return "test"
        if fam in self.split["train_families"]:
            return "train"
        raise DatasetIntegrityError(f"family {fam} is in no split")

    def iter_split(self, name: str) -> Iterator[Mapping[str, Any]]:
        if name not in ("train", "test"):
            raise ValueError("split name must be 'train' or 'test'")
        if self.split is None:
            raise DatasetIntegrityError("this dataset has no train/test split")
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

    def prompt_builder(self, record: Mapping[str, Any]) -> PromptBuilder:
        """The builder version the record was generated with (checked at load time)."""
        return builder_for(record["meta"].get("prompt_builder_version"))

    def probe_prompt(self, record: Mapping[str, Any]) -> PromptBundle:
        """RQ1 prompt, verified against the hash stored when the dataset was built."""
        build = self.prompt_builder(record).build_probe_prompt
        bundle = build(self.prompt_inputs(record), record["action_text"])
        _check_hash(record, bundle, "probe_prompt_sha256")
        return bundle

    def stated_prompt(
        self, record: Mapping[str, Any], horizon: int = PRIMARY_HORIZON
    ) -> PromptBundle:
        """RQ2 prompt. The stored hash covers the primary horizon only."""
        build = self.prompt_builder(record).build_stated_prompt
        bundle = build(self.prompt_inputs(record), record["action_text"], horizon)
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
            f"(builder {bundle.version} vs record "
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
            if entry is not None and sha256_file(d / entry["file"]) != entry["sha256"]:
                raise DatasetIntegrityError(f"{name} file does not match manifest checksum")
    records = tuple(read_jsonl(d / files["dataset"]["file"]))
    _check_builder_versions(manifest, records)
    split_entry = files["split"]
    return LoadedDataset(
        directory=d,
        manifest=manifest,
        records=records,
        split=None
        if split_entry is None
        else json.loads((d / split_entry["file"]).read_text(encoding="utf-8")),
        tool_sets=json.loads((d / files["tool_sets"]["file"]).read_text(encoding="utf-8")),
    )


def _check_builder_versions(
    manifest: Mapping[str, Any], records: tuple[Mapping[str, Any], ...]
) -> None:
    """Every version must be supported; records must agree with the manifest when it names one.

    Raises :class:`UnsupportedPromptBuilderError` for an unknown version and
    :class:`DatasetIntegrityError` for a dataset that mixes versions.
    """
    declared = manifest.get("prompt_builder_version")
    if declared is not None:
        builder_for(declared)
    for r in records:
        version = (r.get("meta") or {}).get("prompt_builder_version")
        try:
            builder_for(version)
        except UnsupportedPromptBuilderError as exc:
            raise UnsupportedPromptBuilderError(f"{r.get('id')}: {exc}") from None
        if declared is not None and version != declared:
            raise DatasetIntegrityError(
                f"{r.get('id')}: prompt builder {version} differs from the manifest's {declared}"
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
