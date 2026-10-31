"""Dataset validator (docs/14_DATASET_VALIDATION.md).

Every check re-derives facts from first principles rather than trusting the
stored fields: actions are replayed from the serialised initial state, the
oracle is re-run, text is re-rendered and prompts are rebuilt.

Run: ``python -m adnn.dataset.validation data/pilot``. Exit status 1 on any error.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adnn.dataset.prompt_versions import (
    PromptBuilder,
    UnsupportedPromptBuilderError,
    builder_for,
)
from adnn.dataset.prompting import PromptInputs, locate_action
from adnn.dataset.rendering import RENDER_STYLES, TEST_ONLY_STYLES
from adnn.dataset.schema import (
    ALL_FIELDS,
    ENVIRONMENTS,
    HORIZONS,
    LABELS,
    PRIMARY_HORIZON,
    PROVISIONAL_OQ21,
    PROVISIONAL_PARTIAL,
    SOURCES,
    canonical_action_text,
    read_jsonl,
    sha256_file,
)
from adnn.sandbox import (
    InvalidStateError,
    ToolCall,
    WorldState,
    assess_reversibility,
    canonical_hash,
    step,
)
from adnn.sandbox.restoration import core_hash, has_pending_timers
from adnn.sandbox.state import EXTENSION_TOOL_NAMES

# Tokens that must never appear in any prompt (metadata / oracle vocabulary).
FORBIDDEN_IN_ANY_PROMPT: tuple[str, ...] = (
    "label", "scenario", "split", "train", "oracle", "pivot", "family", "template",
    "witness", "gold", "ground truth", "restore_depth", "pair_id", "sbx-", "provisional",
)  # fmt: skip
# Additionally forbidden in RQ1/RQ3 prompts (the RQ2 question legitimately names the labels).
FORBIDDEN_IN_AGENT_PROMPTS: tuple[str, ...] = ("reversib",)

PILOT_THRESHOLDS = {"min_examples": 150, "min_pair_fraction": 0.30, "min_class_fraction": 0.25}
FINAL_THRESHOLDS = {"min_examples": 2000, "min_pair_fraction": 0.30, "min_class_fraction": 0.25}


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks_run: Counter[str] = field(default_factory=Counter)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, check: str, msg: str) -> None:
        self.errors.append(f"[{check}] {msg}")

    def warn(self, check: str, msg: str) -> None:
        self.warnings.append(f"[{check}] {msg}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "n_errors": len(self.errors),
            "n_warnings": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "checks_run": dict(self.checks_run),
        }


def flat_diff(a: Any, b: Any, path: str = "") -> list[str]:
    """Paths where two JSON values differ; lists of different length differ as a whole."""
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[str] = []
        for k in sorted(set(a) | set(b)):
            sub = f"{path}.{k}" if path else k
            if k not in a or k not in b:
                out.append(sub)
            else:
                out.extend(flat_diff(a[k], b[k], sub))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [path]
        return [
            p
            for i, (x, y) in enumerate(zip(a, b, strict=True))
            for p in flat_diff(x, y, f"{path}[{i}]")
        ]
    return [] if a == b else [path]


def _within(path: str, scope: str) -> bool:
    return path == scope or path.startswith(scope + ".") or path.startswith(scope + "[")


# -- per-record checks --------------------------------------------------------------------
def _builder(r: Mapping[str, Any], rep: ValidationReport, check: str) -> PromptBuilder | None:
    try:
        return builder_for(r["meta"].get("prompt_builder_version"))
    except UnsupportedPromptBuilderError as exc:
        rep.error(check, f"{r['id']}: {exc}")
        return None


def _check_schema(r: Mapping[str, Any], rep: ValidationReport) -> bool:
    rep.checks_run["schema"] += 1
    rid = r.get("id", "<no id>")
    missing = [f for f in ALL_FIELDS if f not in r]
    extra = sorted(set(r) - set(ALL_FIELDS))
    if missing or extra:
        rep.error("schema", f"{rid}: missing {missing}, unexpected {extra}")
        return False
    ok = True
    for name, allowed in (("environment", ENVIRONMENTS), ("source", SOURCES), ("label", LABELS)):
        if r[name] not in allowed:
            rep.error("schema", f"{rid}: {name}={r[name]!r} not in {allowed}")
            ok = False
    if r["horizon"] != PRIMARY_HORIZON:
        rep.error("schema", f"{rid}: horizon must be {PRIMARY_HORIZON}")
        ok = False
    lbh = r["labels_by_horizon"]
    if set(lbh) != {str(h) for h in HORIZONS} or any(v not in LABELS for v in lbh.values()):
        rep.error("schema", f"{rid}: labels_by_horizon must map 1,2,3 to valid labels")
        ok = False
    elif lbh[str(PRIMARY_HORIZON)] != r["label"]:
        rep.error("schema", f"{rid}: label != labels_by_horizon['3']")
        ok = False
    if r["render_style"] not in RENDER_STYLES:
        rep.error("schema", f"{rid}: unknown render_style")
        ok = False
    return ok


def _check_replay(
    r: Mapping[str, Any], tool_sets: Mapping[str, Any], rep: ValidationReport, rerun_oracle: bool
) -> None:
    rid = r["id"]
    rep.checks_run["replay"] += 1
    try:
        state = WorldState.from_dict(r["state_struct"])
    except InvalidStateError as exc:
        rep.error("replay", f"{rid}: state_struct invalid: {exc}")
        return
    if has_pending_timers(state):
        rep.error("replay", f"{rid}: initial state has pending timers (must be excluded)")
    call = ToolCall.from_obj(r["action_call"])
    if canonical_action_text(call) != r["action_text"]:
        rep.error("replay", f"{rid}: action_text is not canonical_action_text(action_call)")
    if call.tool != r["action_verb"]:
        rep.error("replay", f"{rid}: action_verb != action_call.tool")
    _, result = step(state, call)
    if not result.ok:
        rep.error("replay", f"{rid}: replayed action failed: {result.message}")
    builder = _builder(r, rep, "replay")
    if builder is not None:
        if state.share_links and not builder.renders_share_links:
            rep.error("replay", f"{rid}: builder {builder.version} cannot render share links")
        if builder.render_state_text(state, r["render_style"]) != r["state_text"]:
            rep.error("replay", f"{rid}: state_text differs from re-rendering")
    from adnn.sandbox.tools import tool_specs_for  # local: avoids a cycle at import time

    if tool_sets.get(r["tool_set_id"]) != tool_specs_for(state):
        rep.error("replay", f"{rid}: tool_set_id does not match the state's permitted tools")
    if rerun_oracle:
        rep.checks_run["oracle"] += 1
        a = assess_reversibility(state, call, horizon=PRIMARY_HORIZON, on_budget_exhausted="return")
        if not a.is_definitive:
            rep.error("oracle", f"{rid}: oracle not definitive on replay ({a.provisional_reasons})")
            return
        if a.labels_by_horizon(HORIZONS) != r["labels_by_horizon"]:
            rep.error("oracle", f"{rid}: labels differ on replay")
        if (a.restore_depth, a.approx_restore_depth) != (
            r["restore_depth"],
            r["approx_restore_depth"],
        ):
            rep.error("oracle", f"{rid}: restore depths differ on replay")


def _check_provisional(r: Mapping[str, Any], rep: ValidationReport) -> None:
    rep.checks_run["provisional"] += 1
    rid, reasons = r["id"], r["provisional_reasons"]
    has_partial = "partially_reversible" in r["labels_by_horizon"].values()
    if has_partial and PROVISIONAL_PARTIAL not in reasons:
        rep.error("provisional", f"{rid}: partial label not flagged provisional")
    alt = r["meta"].get("oq21_alternative_labels_by_horizon")
    if alt is not None and alt != r["labels_by_horizon"] and PROVISIONAL_OQ21 not in reasons:
        rep.error("provisional", f"{rid}: OQ-21-sensitive label not flagged")
    if r["label_provisional"] != bool(reasons):
        rep.error("provisional", f"{rid}: label_provisional inconsistent with reasons")


def _check_prompts(
    r: Mapping[str, Any], tool_sets: Mapping[str, Any], rep: ValidationReport
) -> None:
    rep.checks_run["prompts"] += 1
    rid = r["id"]
    builder = _builder(r, rep, "prompts")
    if builder is None:
        return
    inputs = PromptInputs.from_example(r, tool_sets)
    probe = builder.build_probe_prompt(inputs, r["action_text"])
    stated = builder.build_stated_prompt(inputs, r["action_text"])
    agent = builder.build_agent_messages(inputs)
    meta = r["meta"]
    if probe.prompt_sha256 != meta.get("probe_prompt_sha256"):
        rep.error("prompts", f"{rid}: probe prompt hash differs on rebuild")
    if stated.prompt_sha256 != meta.get("stated_prompt_sha256"):
        rep.error("prompts", f"{rid}: stated prompt hash differs on rebuild")
    probe_text = "\n".join(m["content"] for m in probe.messages)
    try:
        locate_action(probe_text, r["action_text"])
    except ValueError as exc:
        rep.error("prompts", f"{rid}: action text not uniquely locatable in probe prompt: {exc}")
    secrets = [r["id"], r["scenario_id"], r["template_id"], r["pair_id"] or ""]
    for bundle in (probe, stated, agent):
        text = "\n".join(m["content"] for m in bundle.messages)
        low = text.lower()
        tokens = FORBIDDEN_IN_ANY_PROMPT + (
            () if bundle.kind == "stated" else FORBIDDEN_IN_AGENT_PROMPTS
        )
        leaked = [t for t in tokens if t in low] + [s for s in secrets if s and s in text]
        if leaked:
            rep.error("leakage", f"{rid}: {bundle.kind} prompt contains {leaked}")


def _check_share_links(r: Mapping[str, Any], rep: ValidationReport) -> None:
    """Link records (a link in the state or a link action): well-formed ids, replayable witnesses.

    Identifiers must be ``lnk-0001 .. lnk-<n>`` without gaps: ``create_share_link`` allocates
    ``lnk-<n + 1>`` and refuses when it is taken, so a gap would silently turn recoveries into
    failures. Every stored witness must restore the pre-action state from the post-action state
    (exactly, or in the core projection); an exact witness has exactly ``restore_depth`` steps.
    """
    try:
        state = WorldState.from_dict(r["state_struct"])
    except InvalidStateError:
        return  # reported by _check_replay
    call = ToolCall.from_obj(r["action_call"])
    if not state.share_links and call.tool not in EXTENSION_TOOL_NAMES:
        return
    rid = r["id"]
    rep.checks_run["share_links"] += 1
    ids = [k.link_id for k in state.share_links]
    if ids != [f"lnk-{i + 1:04d}" for i in range(len(ids))]:
        rep.error("share_links", f"{rid}: link ids are not contiguous from lnk-0001: {ids}")
    after, result = step(state, call)
    if not result.ok:
        return  # reported by _check_replay
    oracle = r["meta"].get("oracle") or {}
    for key, depth_key, digest in (
        ("exact_witness", "restore_depth", canonical_hash),
        ("approx_witness", "approx_restore_depth", core_hash),
    ):
        witness, depth = oracle.get(key), r[depth_key]
        if witness is None:
            if depth is not None:
                rep.error("share_links", f"{rid}: {depth_key}={depth} without {key}")
            continue
        s = after
        for c in witness:
            s, _ = step(s, ToolCall.from_obj(c))
        if digest(s) != digest(state):
            rep.error("share_links", f"{rid}: {key} does not restore the pre-action state")
        if key == "exact_witness" and len(witness) != depth:
            rep.error("share_links", f"{rid}: {key} has {len(witness)} steps, depth {depth}")


# -- dataset-level checks -------------------------------------------------------------------
def _check_uniqueness(records: list[dict[str, Any]], rep: ValidationReport) -> None:
    rep.checks_run["uniqueness"] += 1
    ids = Counter(r["id"] for r in records)
    for rid, n in ids.items():
        if n > 1:
            rep.error("uniqueness", f"duplicate id {rid}")
    seen: dict[tuple[str, str], str] = {}
    for r in records:
        key = (r["state_text"], r["action_text"])
        if key in seen:
            rep.error(
                "uniqueness", f"{r['id']} duplicates (state_text, action_text) of {seen[key]}"
            )
        seen[key] = r["id"]


def _check_pairs(records: list[dict[str, Any]], rep: ValidationReport) -> None:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        if r["pair_id"]:
            groups[r["pair_id"]].append(r)
        elif r["pivot"] is not None:
            rep.error("pairs", f"{r['id']}: pivot set on a non-pair example")
    for pid, members in sorted(groups.items()):
        rep.checks_run["pairs"] += 1
        if len(members) != 2:
            rep.error("pairs", f"{pid}: expected 2 members, found {len(members)}")
            continue
        a, b = members
        if a["action_text"].encode() != b["action_text"].encode():
            rep.error("pairs", f"{pid}: action_text not byte-identical")
        if a["scenario_id"] != b["scenario_id"] or a["template_id"] != b["template_id"]:
            rep.error("pairs", f"{pid}: members from different scenarios/families")
        if (a["task_text"], a["render_style"], a["tool_set_id"]) != (
            b["task_text"],
            b["render_style"],
            b["tool_set_id"],
        ):
            rep.error("pairs", f"{pid}: task text, render style or tool set differ")
        if a["label"] == b["label"]:
            rep.error("pairs", f"{pid}: labels at h=3 are equal")
        if a["state_text"] == b["state_text"]:
            rep.error("pairs", f"{pid}: pivot is not visible (identical state_text)")
        pa, pb = a["pivot"], b["pivot"]
        if not pa or not pb or (pa["factor"], pa["scope"]) != (pb["factor"], pb["scope"]):
            rep.error("pairs", f"{pid}: pivot missing or inconsistent")
            continue
        if pa["value"] == pb["value"]:
            rep.error("pairs", f"{pid}: pivot values are equal")
        diff = flat_diff(a["state_struct"], b["state_struct"])
        outside = [p for p in diff if not _within(p, pa["scope"])]
        if not diff or outside:
            rep.error(
                "pairs",
                f"{pid}: states differ outside pivot scope {pa['scope']}: {outside or diff}",
            )


def _check_builder_versions(
    records: list[dict[str, Any]], rep: ValidationReport, declared: str | None = None
) -> None:
    """One prompt-builder version per dataset, equal to the manifest's when it names one."""
    rep.checks_run["builder_versions"] += 1
    versions = sorted({str(r["meta"].get("prompt_builder_version")) for r in records})
    if len(versions) > 1:
        rep.error("builder_versions", f"dataset mixes prompt builder versions {versions}")
    if declared is not None and versions and versions != [declared]:
        rep.error("builder_versions", f"records use {versions}, manifest declares {declared}")


def _check_label_consistency(records: list[dict[str, Any]], rep: ValidationReport) -> None:
    """Identical model-visible input must never carry different labels."""
    rep.checks_run["label_consistency"] += 1
    seen: dict[tuple[str, str, str], tuple[str, str]] = {}
    for r in records:
        key = (r["task_text"], r["state_text"], r["action_text"])
        if key in seen and seen[key][1] != r["label"]:
            rep.error(
                "label_consistency", f"{r['id']} vs {seen[key][0]}: same input, different label"
            )
        seen.setdefault(key, (r["id"], r["label"]))


def _check_split(
    records: list[dict[str, Any]], split: Mapping[str, Any], rep: ValidationReport
) -> None:
    rep.checks_run["split"] += 1
    train_f, test_f = set(split["train_families"]), set(split["test_families"])
    if train_f & test_f:
        rep.error("split", f"families in both splits: {sorted(train_f & test_f)}")
    train_s, test_s = set(split["train_scenarios"]), set(split["test_scenarios"])
    if train_s & test_s:
        rep.error("split", f"scenarios in both splits: {sorted(train_s & test_s)}")
    fam_split: dict[str, set[str]] = defaultdict(set)
    for r in records:
        fam, sid = r["template_id"], r["scenario_id"]
        in_f = "test" if fam in test_f else "train" if fam in train_f else None
        in_s = "test" if sid in test_s else "train" if sid in train_s else None
        if in_f is None or in_s is None:
            rep.error("split", f"{r['id']}: family or scenario not assigned to a split")
            continue
        if in_f != in_s:
            rep.error("split", f"{r['id']}: scenario split {in_s} != family split {in_f}")
        fam_split[fam].add(in_f)
        if in_f == "train" and r["render_style"] in TEST_ONLY_STYLES:
            rep.error("split", f"{r['id']}: test-only render style used in train")
    for fam, splits in fam_split.items():
        if len(splits) > 1:
            rep.error("split", f"family {fam} spans splits")


def _check_counts(
    records: list[dict[str, Any]], rep: ValidationReport, thresholds: Mapping[str, float]
) -> None:
    rep.checks_run["counts"] += 1
    n = len(records)
    if n < thresholds["min_examples"]:
        rep.error("counts", f"{n} examples < {thresholds['min_examples']}")
    if not n:
        return
    in_pairs = sum(1 for r in records if r["pair_id"])
    if in_pairs / n < thresholds["min_pair_fraction"]:
        rep.error(
            "counts",
            f"minimal-pair fraction {in_pairs / n:.3f} < {thresholds['min_pair_fraction']}",
        )
    for label in LABELS:
        frac = sum(r["label"] == label for r in records) / n
        if frac < thresholds["min_class_fraction"]:
            rep.warn(
                "counts",
                f"class {label} is {frac:.3f} of examples (< {thresholds['min_class_fraction']})",
            )


def validate_records(
    records: list[dict[str, Any]],
    *,
    split: Mapping[str, Any] | None,
    tool_sets: Mapping[str, Any],
    thresholds: Mapping[str, float] = PILOT_THRESHOLDS,
    rerun_oracle: bool = True,
    declared_builder_version: str | None = None,
) -> ValidationReport:
    """``split=None`` only for datasets without a train/test split (docs/30 §4)."""
    rep = ValidationReport()
    valid = [r for r in records if _check_schema(r, rep)]
    for r in valid:
        _check_replay(r, tool_sets, rep, rerun_oracle)
        _check_provisional(r, rep)
        _check_prompts(r, tool_sets, rep)
        _check_share_links(r, rep)
    _check_uniqueness(valid, rep)
    _check_pairs(valid, rep)
    _check_label_consistency(valid, rep)
    _check_builder_versions(valid, rep, declared_builder_version)
    if split is None:
        rep.warn("split", "no train/test split: split checks skipped")
    else:
        _check_split(valid, split, rep)
    _check_counts(valid, rep, thresholds)
    return rep


def validate_directory(
    directory: Path,
    *,
    thresholds: Mapping[str, float] = PILOT_THRESHOLDS,
    rerun_oracle: bool = True,
) -> ValidationReport:
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    rep_pre = ValidationReport()
    for key, rel in (
        ("dataset", files["dataset"]),
        ("tool_sets", files["tool_sets"]),
        ("split", manifest["split"]),
    ):
        if rel is None:  # no split
            continue
        rep_pre.checks_run["file_hashes"] += 1
        if sha256_file(directory / rel["file"]) != rel["sha256"]:
            rep_pre.error("file_hashes", f"{key} file hash does not match manifest")
    records = read_jsonl(directory / files["dataset"]["file"])
    split_entry = manifest["split"]
    split = (
        None
        if split_entry is None
        else json.loads((directory / split_entry["file"]).read_text(encoding="utf-8"))
    )
    tool_sets = json.loads((directory / files["tool_sets"]["file"]).read_text(encoding="utf-8"))
    rep = validate_records(
        records,
        split=split,
        tool_sets=tool_sets,
        thresholds=thresholds,
        rerun_oracle=rerun_oracle,
        declared_builder_version=manifest.get("prompt_builder_version"),
    )
    rep.errors[:0] = rep_pre.errors
    rep.checks_run.update(rep_pre.checks_run)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("directory", type=Path)
    ap.add_argument("--final", action="store_true", help="use final-dataset thresholds")
    args = ap.parse_args(argv)
    rep = validate_directory(
        args.directory, thresholds=FINAL_THRESHOLDS if args.final else PILOT_THRESHOLDS
    )
    print(json.dumps(rep.to_dict(), indent=2))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
