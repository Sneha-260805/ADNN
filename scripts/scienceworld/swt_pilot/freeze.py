"""Freeze the SWT pilot pre-registrations, packets, rubric declarations and go/no-go criteria.

Run from the repository root with the isolated runtime configured, BEFORE any recovery
experiment::

    .venv/Scripts/python.exe scripts/scienceworld/swt_pilot/freeze.py --check   # writes nothing
    .venv/Scripts/python.exe scripts/scienceworld/swt_pilot/freeze.py           # freeze

For every case it builds S0 only (history replayed; the target is never executed), checks
that the target is listed exactly once and that every declared role binds, builds the
blinded packet and the ``sw-declaration-rubric-1`` declaration. ``--check`` prints problems
and role suggestions only. The freeze writes (committable) into
``docs/preregistration/swt_pilot/``: ``manifest.json`` (+ ``manifest.sha256``),
``preregistrations.json``, ``rubric_declarations.json`` and ``packets/S??.json|.md``.
It refuses to overwrite an existing manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cases import PILOT_ID, SWT_PILOT_CASES

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.canonical import capture_state, sha256_json
from adnn.scienceworld.declaration_reliability import (
    AMBIGUITIES,
    PACKET_VERSION,
    RUBRIC,
    RUBRIC_VERSION,
    build_packet,
    compare,
    role_of,
    rubric_declaration,
    rubric_to_declaration,
)
from adnn.scienceworld.env import ScienceWorldSession
from adnn.scienceworld.preregistration import manifest
from adnn.scienceworld.replay import run_recipe
from adnn.scienceworld.semantics import bind

OUT = Path("docs/preregistration/swt_pilot")

# Frozen before any result (approved in the feasibility audit, 2026-11-04). Never relaxed.
GO_NO_GO = {
    "tier_g_definition": (
        "eligible under sw-admission-2 (not quarantined, evidence complete and replay "
        "verified) AND replicated in a second fresh process AND query-order audit "
        "transitions equal under every condition AND symmetric-protocol check unaffected "
        "AND rubric-1 declaration gives the same outcome AND (for partials) an admissible "
        "certificate protects every residual property; witness depth <= 3"
    ),
    "G1": "tier-G partially reversible (C-BURN) >= 8, over >= 4 independent scenario groups",
    "G2": "tier-G reversible >= 12, over >= 4 task families",
    "G3": "replication: 100% of eligible cases replicate",
    "G4": "measurement-affected (query-order or symmetry) <= 2% of eligible cases",
    "G5": "rubric-sensitive <= 10% of cases eligible under M1 or rubric",
    "definitions": {
        "task_family": "ScienceWorld task id (e.g. '1-2'); all tasks share one house",
        "scenario_group": "(room, mechanism, target object): the independence unit reported "
        "alongside the task-family count",
        "eligible": "outcome eligible_reversible / eligible_partially_reversible / "
        "eligible_irreversible under M1",
    },
    "verdict": "GO only if G1-G5 all hold; otherwise NO-GO (reported, never re-scored)",
    "unresolved_policy": "unresolved cases stay unresolved; search failure is never "
    "irreversibility; no case is relabelled",
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _packet_ids() -> dict[str, str]:
    order = sorted(SWT_PILOT_CASES, key=lambda r: hashlib.sha256(r.case_id.encode()).hexdigest())
    return {r.case_id: f"S{i + 1:02d}" for i, r in enumerate(order)}


def _md(packet: dict) -> str:
    return "\n".join([
        f"# Declaration packet {packet['packet_id']} (SWT pilot)", "",
        f"Rubric: `{packet['rubric_version']}`. Follow `../../PHASE4H_ANNOTATOR_PROTOCOL.md`.",
        "", f"**Task:** {packet['task_description']}", "",
        "**Actions already taken (this is how the initial state was reached):** "
        f"{', '.join(packet['actions_already_taken']) or 'none'}", "",
        f"**Target action:** `{packet['target_action']}`", "",
        "## Objects named by the target action", "", "```json",
        json.dumps(packet["target_objects"], indent=1), "```", "",
        "## Room contents at the initial state", "", "```json",
        json.dumps(packet["scene"], indent=1), "```", "",
    ])  # fmt: skip


def _suggest(s0: Any, name: str) -> list[str]:
    hits = [u for u, r in s0.objects.items() if r.get("name") == name and not r.get("isDeleted")]
    return [f"{name} (parent={s0.objects.get(str(s0.objects[u]['parent']), {}).get('name')}, "
            f"role={role_of(s0, u)})" for u in hits]  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate only; write nothing")
    args = ap.parse_args()
    if (OUT / "manifest.json").exists() and not args.check:
        raise SystemExit("manifest already frozen; refusing to overwrite")
    ids = _packet_ids()
    packets, rubric_rows, problems = {}, {}, []
    with ScienceWorldSession(RuntimeConfig.from_env()) as session:
        for rec in SWT_PILOT_CASES:
            spec = rec.spec
            try:
                run_recipe(session, spec.recipe(), strict=True)
            except Exception as exc:
                problems.append(f"{spec.case_id}: history failed: {exc}")
                continue
            s0 = capture_state(session).canonical
            groups: dict[str, set] = {}
            for t in session.valid_action_templates():
                groups.setdefault(t.action, set()).add(t.obj_ids)
            matches = groups.get(spec.target, set())
            if len(matches) != 1:
                near = sorted(a for a in groups if a.split()[0] == spec.target.split()[0]
                              and spec.target.split()[-1] in a)[:8]  # fmt: skip
                problems.append(f"{spec.case_id}: target listed {len(matches)} times; near: {near}")
                continue
            target_ids = next(iter(matches))
            try:
                m1_binding = bind(spec.declaration, s0)
            except ValueError as exc:
                role = str(exc).split("'")[1] if "'" in str(exc) else ""
                problems.append(f"{spec.case_id}: {exc}; candidates: "
                                f"{_suggest(s0, role.partition(' in ')[0])}")  # fmt: skip
                continue
            agent = next(u for u, r in s0.objects.items() if r["name"] == "agent")
            room = str(s0.objects[agent]["parent"])
            task_desc = session.step("task").observation.strip()
            packet = build_packet(
                ids[spec.case_id], s0, room_uuid=room, target=spec.target,
                target_ids=target_ids, task_description=task_desc, history=spec.history,
            )  # fmt: skip
            packets[spec.case_id] = packet
            props = rubric_declaration(packet)
            if not props:
                problems.append(f"{spec.case_id}: {RUBRIC_VERSION} declares no property "
                                f"for {spec.target!r}")  # fmt: skip
                continue
            rdecl = rubric_to_declaration(
                f"{spec.case_id}@rubric", spec.declaration.definition, props
            )
            try:
                r_binding = bind(rdecl, s0)
                agreement = compare(spec.declaration, m1_binding, rdecl, r_binding)
            except ValueError as exc:
                r_binding, agreement = {}, {"error": str(exc)}
            rubric_rows[spec.case_id] = {
                "packet_id": packet["packet_id"],
                "properties": [p.__dict__ for p in props],
                "declaration": rdecl.to_dict(),
                "declaration_sha256": rdecl.sha256,
                "binding": r_binding,
                "m1_binding": m1_binding,
                "agreement_with_m1": agreement,
            }
            if args.check:
                print(json.dumps({"case": spec.case_id, "ok": True,
                                  "rubric": [f"{p.role}.{p.field}={p.weight:g}" for p in props],
                                  "target_roles": [t.get("role") for t in
                                                   packet["target_objects"]]}))  # fmt: skip
    if problems:
        print("PROBLEMS:\n" + "\n".join(problems))
        raise SystemExit(1 if not args.check else 0)
    if args.check:
        print(json.dumps({"check": "clean", "cases": len(packets)}))
        return 0
    for packet in packets.values():
        pid = packet["packet_id"]
        _write(OUT / "packets" / f"{pid}.json", json.dumps(packet, indent=1) + "\n")
        _write(OUT / "packets" / f"{pid}.md", _md(packet))
    records = [r.to_dict() | {"sha256": r.sha256} for r in SWT_PILOT_CASES]
    _write(OUT / "preregistrations.json", json.dumps(records, indent=1) + "\n")
    rubric_doc = {"rubric_version": RUBRIC_VERSION, "rubric": RUBRIC, "ambiguities": AMBIGUITIES,
                  "note": "rule-based technical comparison; NOT inter-annotator agreement",
                  "cases": rubric_rows}  # fmt: skip
    _write(OUT / "rubric_declarations.json", json.dumps(rubric_doc, indent=1) + "\n")
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()  # fmt: skip
    extra = {
        "pilot_id": PILOT_ID,
        "frozen_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_commit": head,
        "packet_version": PACKET_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "packet_ids": ids,
        "packet_sha256": {cid: p["sha256"] for cid, p in packets.items()},
        "rubric_declaration_sha256": {
            cid: r["declaration_sha256"] for cid, r in rubric_rows.items()
        },
        "rubric_document_sha256": sha256_json(rubric_doc),
        "cases_module_sha256": hashlib.sha256(
            Path(__file__).with_name("cases.py").read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "go_no_go": GO_NO_GO,
        "note": "frozen before any SWT pilot recovery experiment; v1.0/v2.0 untouched",
    }
    doc = manifest(SWT_PILOT_CASES, extra)
    text = json.dumps(doc, indent=1) + "\n"
    _write(OUT / "manifest.json", text)
    _write(OUT / "manifest.sha256",
           hashlib.sha256(text.encode()).hexdigest() + "  manifest.json\n")  # fmt: skip
    print(json.dumps({"frozen": len(records), "packets": len(packets)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
