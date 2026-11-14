"""ScienceWorld transfer evaluation set ``adnn-sw-transfer-1.0`` (ADR-0011; docs/40).

A separate, unsplit evaluation set for cross-environment transfer (REQ-ABL-04). It does
NOT change production v1.0 or v2.0. It holds:

* the 30 tier-G cases of the SWT pilot (docs/39; ``results/swt_pilot/report.json``);
* the 5 tier-G ScienceWorld records of v2.0, copied verbatim apart from
  ``dataset_version`` and three added ``meta`` keys.

Labels are never computed here. They are read from the frozen ``sw-admission-2`` decisions
and re-checked against the stored evidence. Records use the v2.0 ScienceWorld
conventions: schema, prompt builder 1.1.0, tool set ``ts-scienceworld-1``, ``state_text`` =
``look`` + ``inventory`` after a pinned replay whose S0 fingerprint must equal the evidence,
and ``task_text`` "You are in a house with a <room>. Work with the objects around you."

Kept outside ``src/adnn`` so that the v2.0 ``code_sha256`` pin stays valid.

    python scripts/dataset/swt_transfer.py export     # needs the pinned runtime (30 replays)
    python scripts/dataset/swt_transfer.py validate   # pure; exit 1 on any error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "scripts" / "scienceworld" / "swt_pilot")
)

from cases import SWT_PILOT_CASES

from adnn.dataset import validation as val
from adnn.dataset.prompting import PromptInputs
from adnn.dataset.prompting_v11 import (
    PROMPT_BUILDER_VERSION,
    build_probe_prompt,
    build_stated_prompt,
)
from adnn.dataset.schema import (
    HORIZONS,
    read_jsonl,
    sha256_file,
    sha256_text,
    stable_json,
    write_json,
    write_jsonl,
)
from adnn.scienceworld import export as sw_export
from adnn.scienceworld.admission import decide

ROOT = Path(__file__).resolve().parents[2]

DATASET_VERSION = "adnn-sw-transfer-1.0"
EXPORTER_VERSION = "sw-transfer-export-1.0"
OUT = Path("data/transfer/sw-transfer-1.0")
PILOT = Path("results/swt_pilot")
PILOT_MANIFEST = Path("docs/preregistration/swt_pilot/manifest.json")
PILOT_MANIFEST_SHA256 = "db0620ff14d773542eba7146e691e024d62f2a32472e4fe26e4ce17d16450751"
V2 = Path("data/production/v2.0")
V2_RECORDS_SHA256 = "d03cd8f38ad4b36ce540409e7b3062e0eb4b457d6916483a3334ebde0acdab73"
CERTS = Path("results/scienceworld_certificates")
STATE_CACHE = Path("results/swt_transfer/state")
LABEL_OF = {"R": "reversible", "P": "partially_reversible"}
BY_ID = {r.case_id: r for r in SWT_PILOT_CASES}
# transfer grouping of the 5 legacy (Phase 4H) cases: room, mechanism, object
LEGACY_GROUP = {
    "h4-open-fridge": ("kitchen", "container", "fridge"),
    "h4-move-cup-to-table": ("kitchen", "relocation", "ceramic cup"),
    "h4-connect-battery-wire": ("workshop", "electrical", "anode in battery"),
    "h4-burn-painting-water-near": ("kitchen", "combustion", "painting in kitchen"),
    "h4-burn-chair-water-near": ("kitchen", "combustion", "chair in kitchen"),
}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def task_text(room: str) -> str:
    return f"You are in a house with a {room}. Work with the objects around you."


def _reports() -> dict[str, dict]:
    reports = {}
    for p in sorted(CERTS.glob("C-*.json")):
        r = json.loads(p.read_text("utf-8"))
        reports[r["certificate_id"]] = r
    return reports


def _pilot_report() -> dict[str, Any]:
    if hashlib.sha256(PILOT_MANIFEST.read_bytes()).hexdigest() != PILOT_MANIFEST_SHA256:
        raise SystemExit("SWT pilot manifest differs from its frozen hash")
    return json.loads((PILOT / "report.json").read_text("utf-8"))


def pilot_gate(cid: str, report: dict[str, Any], reports: dict[str, dict]) -> dict[str, Any]:
    """Everything a pilot record is built from, re-derived from the stored evidence."""
    c = report["cases"][cid]
    path = PILOT / "main" / f"{cid}.json"
    doc = json.loads(path.read_text("utf-8"))
    ev, dec = doc["evidence"], doc["decision"]
    fresh = decide(ev, reports)
    spec = BY_ID[cid].spec
    depth = len(dec["witness"]["path"]) if dec["witness"] else None
    label = LABEL_OF.get(c["label"] or "")
    checks = {
        "tier_g_in_report": c["tier_g"] is True and label is not None,
        "decision_rederives": all(fresh[k] == dec[k] for k in ("outcome", "reasons", "witness")),
        "label_matches_outcome": label == sw_export.LABEL_OF.get(dec["outcome"]),
        "target_is_frozen": ev["target"]["action"] == spec.target,
        "witness_depth_le_3": depth is not None and depth <= max(HORIZONS),
    }
    return {
        "case_id": cid,
        "checks": checks,
        "passed": all(checks.values()),
        "label": label,
        "labels_by_horizon": {str(h): (label if depth and h >= depth else None) for h in HORIZONS},
        "witness_depth": depth,
        "evidence_sha256": sw_export.sha256_path(path),
        "family_id": ev["case"]["family_id"],
        "task": ev["case"]["task"],
        "target": spec.target,
        "recipe": ev["provenance"]["recipe"],
        "s0_raw_fingerprint": ev["replay"]["s0_raw_fingerprint"],
        "decision": {k: dec[k] for k in ("outcome", "witness", "certificate")},
        "group": (c["room"], c["mechanism"], c["object"]),
        "tier_g_checks": c["checks"],
    }


def observe(g: dict[str, Any]) -> str:
    """``look`` + ``inventory`` at S0, as :func:`adnn.scienceworld.export.observe`, with one
    difference. The raw fingerprint includes the valid-action list, whose display aliases for
    same-named objects (e.g. three "wood cup"s) ScienceWorld re-draws on every query. So
    after observing, this checks the *canonical* state (unchanged) rather than the raw
    fingerprint. The S0 raw fingerprint must still equal the evidence before observing, and a
    second fresh rebuild must give the same text."""
    from adnn.scienceworld.canonical import capture_state
    from adnn.scienceworld.env import ScienceWorldSession
    from adnn.scienceworld.replay import ReplayRecipe, run_recipe

    recipe = ReplayRecipe.from_dict(g["recipe"])
    texts = []
    with ScienceWorldSession(None, step_limit=recipe.step_limit) as session:
        for _ in range(2):
            run_recipe(session, recipe)
            s0 = capture_state(session)
            if s0.raw.fingerprint != g["s0_raw_fingerprint"]:
                raise RuntimeError(f"{g['case_id']}: S0 fingerprint does not match the evidence")
            texts.append(session.look().strip() + "\n" + session.inventory().strip())
            if capture_state(session).canonical != s0.canonical:
                raise RuntimeError(f"{g['case_id']}: observing changed the canonical state")
    if texts[0] != texts[1]:
        raise RuntimeError(f"{g['case_id']}: state_text differs between rebuilds")
    return texts[0]


def pilot_record(g: dict[str, Any], state_text: str) -> dict[str, Any]:
    room, mech, obj = g["group"]
    labels, w = g["labels_by_horizon"], g["decision"]["witness"]
    tt, action = task_text(room), g["target"]
    inputs = PromptInputs(tt, state_text, tuple(sw_export.SW_TOOLS))
    exact = w["canonical_level"] == "exact"
    return {
        "id": f"sw-{g['case_id']}",
        "environment": "scienceworld",
        "state_text": state_text,
        "action_text": action,
        "label": labels[str(max(HORIZONS))],
        "horizon": max(HORIZONS),
        "source": "scienceworld_bfs",
        "scenario_id": f"sw-swt-{slug(room)}-{slug(mech)}-{slug(obj)}",
        "template_id": "sw-" + g["family_id"],
        "pair_id": None,
        "pivot": None,
        "labels_by_horizon": dict(labels),
        "restore_depth": g["witness_depth"] if exact else None,
        "approx_restore_depth": g["witness_depth"],
        "task_text": tt,
        "tool_set_id": sw_export.SW_TOOL_SET_ID,
        "action_verb": action.split()[0],
        "action_call": None,
        "state_struct": None,
        "render_style": "prose",
        "label_rationale": f"{sw_export.DECISION_RULE}: {g['decision']['outcome']}; witness "
        f"{w['path']} ({w['canonical_level']}); residual {w['residual']}",
        "label_provisional": False,
        "provisional_reasons": [],
        "tier": "G",
        "sensitivity_group": None,
        "meta": {
            "domain": "scienceworld",
            "example_kind": "non_pair",
            "case_id": g["case_id"],
            "source_phase": "swt-pilot-1",
            "evidence_sha256": g["evidence_sha256"],
            "s0_raw_fingerprint": g["s0_raw_fingerprint"],
            "recipe": g["recipe"],
            "decision": g["decision"],
            "evidence_checks": g["tier_g_checks"],
            "transfer_group": {"room": room, "mechanism": mech, "object": obj},
            "partial_definition": sw_export.SW_PARTIAL_RULE,
            "exporter_version": EXPORTER_VERSION,
            "prompt_builder_version": PROMPT_BUILDER_VERSION,
            "probe_prompt_sha256": build_probe_prompt(inputs, action).prompt_sha256,
            "stated_prompt_sha256": build_stated_prompt(inputs, action).prompt_sha256,
        },
        "dataset_version": DATASET_VERSION,
    }


def legacy_records() -> list[dict[str, Any]]:
    if sha256_file(V2 / "records.jsonl") != V2_RECORDS_SHA256:
        raise SystemExit("v2.0 records.jsonl differs from its frozen hash")
    split = json.loads((V2 / "split.json").read_text("utf-8"))
    out = []
    for r in read_jsonl(V2 / "records.jsonl"):
        if r["environment"] != "scienceworld":
            continue
        room, mech, obj = LEGACY_GROUP[r["meta"]["case_id"]]
        r = json.loads(json.dumps(r))
        r["meta"]["source_phase"] = "phase4h"
        r["meta"]["source_dataset"] = {
            "dataset_version": r["dataset_version"],
            "records_sha256": V2_RECORDS_SHA256,
            "split_side": "test" if r["scenario_id"] in split["test_scenarios"] else "train",
        }
        r["meta"]["transfer_group"] = {"room": room, "mechanism": mech, "object": obj}
        r["dataset_version"] = DATASET_VERSION
        out.append(r)
    return out


def folds_by_room(records: list[dict[str, Any]]) -> dict[str, Any]:
    rooms: dict[str, list[str]] = defaultdict(list)
    for r in records:
        rooms[r["meta"]["transfer_group"]["room"]].append(r["id"])
    return {
        "kind": "leave_one_room_out",
        "note": "within-ScienceWorld reference only. All ScienceWorld tasks share one house, "
        "so a room (not a task id or scenario_id) is the most conservative group",
        "folds": {room: sorted(ids) for room, ids in sorted(rooms.items())},
    }


def _code_sha() -> str:
    h = hashlib.sha256()
    for f in [Path(__file__), *sorted((ROOT / "scripts/scienceworld/swt_pilot").glob("*.py"))]:
        h.update(f.name.encode() + b"\0" + f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def mode_export() -> None:
    if (OUT / "manifest.json").exists():
        raise SystemExit(f"{OUT} already exists; refusing to overwrite")
    report, reports = _pilot_report(), _reports()
    pilot = []
    for cid, c in report["cases"].items():
        if not c["tier_g"]:
            continue
        g = pilot_gate(cid, report, reports)
        if not g["passed"]:
            raise SystemExit(f"{cid}: gate fails {g['checks']}")
        cache = STATE_CACHE / f"{cid}.json"  # resume support (git-ignored)
        if cache.exists() and json.loads(cache.read_text("utf-8"))["fp"] == g["s0_raw_fingerprint"]:
            state = json.loads(cache.read_text("utf-8"))["state_text"]
        else:
            state = observe(g)
            cache.parent.mkdir(parents=True, exist_ok=True)
            write_json(cache, {"fp": g["s0_raw_fingerprint"], "state_text": state})
        pilot.append(pilot_record(g, state))
        print(json.dumps({"exported": pilot[-1]["id"], "label": pilot[-1]["label"]}), flush=True)
    records = sorted(legacy_records() + pilot, key=lambda r: r["id"])
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "records.jsonl", records)
    v2_tools = json.loads((V2 / "tool_sets.json").read_text("utf-8"))
    write_json(OUT / "tool_sets.json", {sw_export.SW_TOOL_SET_ID: v2_tools["ts-scienceworld-1"]})
    write_json(OUT / "cv_folds_by_room.json", folds_by_room(records))
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()  # fmt: skip
    manifest = {
        "dataset_version": DATASET_VERSION,
        "purpose": "ScienceWorld transfer evaluation set (REQ-ABL-04): binary reversible vs "
        "partially reversible; no admitted irreversible examples; gold tier only; unsplit",
        "exporter_version": EXPORTER_VERSION,
        "prompt_builder_version": PROMPT_BUILDER_VERSION,
        "partial_definition_policy": val.PARTIAL_POLICY_TEAM,
        "decision_rule": sw_export.DECISION_RULE,
        "files": {
            "dataset": {"file": "records.jsonl", "sha256": sha256_file(OUT / "records.jsonl")},
            "tool_sets": {"file": "tool_sets.json", "sha256": sha256_file(OUT / "tool_sets.json")},
            "cv_folds_by_room": {
                "file": "cv_folds_by_room.json",
                "sha256": sha256_file(OUT / "cv_folds_by_room.json"),
            },
        },
        "split": None,
        "provenance": {
            "base_commit": head,
            "code_sha256": _code_sha(),
            "pilot_manifest_sha256": PILOT_MANIFEST_SHA256,
            "pilot_report_sha256": sha256_file(PILOT / "report.json"),
            "pilot_verdict": report["verdict"],
            "pilot_evidence_sha256": {
                r["meta"]["case_id"]: r["meta"]["evidence_sha256"] for r in pilot
            },
            "legacy_source": {"dataset": "adnn-dataset-2.0", "records_sha256": V2_RECORDS_SHA256},
        },
        "records_sha256": sha256_text(stable_json(records)),
        "counts": {
            "records": len(records),
            "label": Counter(r["label"] for r in records),
            "source_phase": Counter(r["meta"]["source_phase"] for r in records),
            "scenario_ids": len({r["scenario_id"] for r in records}),
        },
    }
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps(manifest["counts"]))


def validate_dir(d: Path = OUT) -> val.ValidationReport:
    """Stock validator checks (schema, tier/partial policy, prompt rebuild and leakage,
    uniqueness, label consistency, builder version) plus evidence re-checks. Counts and
    minimal-pair thresholds are production gates and are not applied to this set."""
    man = json.loads((d / "manifest.json").read_text("utf-8"))
    rep = val.ValidationReport()
    for key, entry in man["files"].items():
        rep.checks_run["file_hashes"] += 1
        if sha256_file(d / entry["file"]) != entry["sha256"]:
            rep.error("file_hashes", f"{key} hash does not match the manifest")
    records = read_jsonl(d / man["files"]["dataset"]["file"])
    tool_sets = json.loads((d / man["files"]["tool_sets"]["file"]).read_text("utf-8"))
    if sha256_text(stable_json(records)) != man["records_sha256"]:
        rep.error("file_hashes", "records_sha256 differs")
    report, reports = _pilot_report(), _reports()
    if sha256_file(PILOT / "report.json") != man["provenance"]["pilot_report_sha256"]:
        rep.error("provenance", "pilot report.json changed since export")
    valid = [r for r in records if val._check_schema(r, rep, man["partial_definition_policy"])]
    for r in valid:
        rep.checks_run["scienceworld_evidence"] += 1
        if r["environment"] != "scienceworld" or r["dataset_version"] != DATASET_VERSION:
            rep.error("scope", f"{r['id']}: not a {DATASET_VERSION} ScienceWorld record")
        if r["label"] not in LABEL_OF.values():
            rep.error("scope", f"{r['id']}: label {r['label']} outside the R/P transfer set")
        if r["meta"]["source_phase"] == "phase4h":
            for msg in sw_export.validate_record(r):  # unchanged v2.0 evidence check
                rep.error("scienceworld", msg)
        else:
            g = pilot_gate(r["meta"]["case_id"], report, reports)
            if not g["passed"]:
                rep.error("scienceworld", f"{r['id']}: pilot gate fails {g['checks']}")
            for k in ("evidence_sha256", "s0_raw_fingerprint"):
                if r["meta"][k] != g[k]:
                    rep.error("scienceworld", f"{r['id']}: {k} differs from the evidence")
            if r["labels_by_horizon"] != g["labels_by_horizon"] or r["action_text"] != g["target"]:
                rep.error("scienceworld", f"{r['id']}: label or action differs from evidence")
        val._check_provisional(r, rep, man["partial_definition_policy"])
        val._check_prompts(r, tool_sets, rep)
    val._check_uniqueness(valid, rep)
    val._check_label_consistency(valid, rep)
    val._check_builder_versions(valid, rep, man["prompt_builder_version"])
    folds = json.loads((d / "cv_folds_by_room.json").read_text("utf-8"))["folds"]
    ids = [i for f in folds.values() for i in f]
    rep.checks_run["folds"] += 1
    if sorted(ids) != sorted(r["id"] for r in records):
        rep.error("folds", "room folds do not partition the records")
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("export", "validate"))
    args = ap.parse_args()
    if args.mode == "export":
        mode_export()
    rep = validate_dir()
    print(json.dumps(rep.to_dict(), indent=1))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
