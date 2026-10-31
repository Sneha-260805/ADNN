"""Freeze the Phase 4H pre-registrations, packets and rubric declarations (docs/24 §3, §5).

Run once, from the repository root with the isolated runtime configured, BEFORE any
recovery experiment::

    .venv/Scripts/python.exe scripts/scienceworld/phase4h_freeze.py

For every case it builds S0 only (the target is never executed), checks that the
target is listed exactly once and that every declared role binds, builds the blinded
packet and the rubric declaration, and writes (all committed, none git-ignored)::

    docs/preregistration/phase4h_manifest.json          hashes + packet-id mapping
    docs/preregistration/phase4h_preregistrations.json  full frozen records
    docs/preregistration/phase4h_rubric_declarations.json  rule-based comparison
    docs/preregistration/packets/P??.json and P??.md      blinded annotator packets

It refuses to overwrite an existing manifest unless ``--force`` is given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.canonical import capture_state, sha256_json
from adnn.scienceworld.declaration_reliability import (
    AMBIGUITIES,
    PACKET_VERSION,
    RUBRIC,
    RUBRIC_VERSION,
    build_packet,
    compare,
    rubric_declaration,
    rubric_to_declaration,
)
from adnn.scienceworld.env import ScienceWorldSession
from adnn.scienceworld.phase4h_cases import PHASE4H_CASES
from adnn.scienceworld.preregistration import manifest
from adnn.scienceworld.replay import run_recipe
from adnn.scienceworld.semantics import bind

OUT = Path("docs/preregistration")


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _packet_ids() -> dict[str, str]:
    order = sorted(PHASE4H_CASES, key=lambda r: hashlib.sha256(r.case_id.encode()).hexdigest())
    return {r.case_id: f"P{i + 1:02d}" for i, r in enumerate(order)}


def _md(packet: dict) -> str:
    lines = [
        f"# Declaration packet {packet['packet_id']}",
        "",
        f"Rubric: `{packet['rubric_version']}`. Follow `../PHASE4H_ANNOTATOR_PROTOCOL.md`.",
        "",
        f"**Task:** {packet['task_description']}",
        "",
        f"**Actions already taken (this is how the initial state was reached):** "
        f"{', '.join(packet['actions_already_taken']) or 'none'}",
        "",
        f"**Target action:** `{packet['target_action']}`",
        "",
        "## Objects named by the target action",
        "",
        "```json",
        json.dumps(packet["target_objects"], indent=1),
        "```",
        "",
        "## Room contents at the initial state",
        "",
        "```json",
        json.dumps(packet["scene"], indent=1),
        "```",
        "",
        "## Your declaration (fill in the JSON packet's `form`)",
        "",
        "List each property as role, field, weight (1 = task-relevant, 0 = recorded only) "
        "and a one-line reason citing the rubric rule.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if (OUT / "phase4h_manifest.json").exists() and not args.force:
        raise SystemExit("manifest already frozen; refusing to overwrite (use --force only "
                         "before any recovery experiment has run)")  # fmt: skip
    (OUT / "packets").mkdir(parents=True, exist_ok=True)
    ids = _packet_ids()
    packets, rubric_rows, problems = {}, {}, []
    with ScienceWorldSession(RuntimeConfig.from_env()) as session:
        for rec in PHASE4H_CASES:
            spec = rec.spec
            run_recipe(session, spec.recipe(), strict=True)
            s0 = capture_state(session).canonical
            groups: dict[str, set] = {}
            for t in session.valid_action_templates():
                groups.setdefault(t.action, set()).add(t.obj_ids)
            matches = groups.get(spec.target, set())
            if len(matches) != 1:
                problems.append(f"{spec.case_id}: target listed {len(matches)} times")
                continue
            target_ids = next(iter(matches))
            try:
                m1_binding = bind(spec.declaration, s0)
            except ValueError as exc:
                problems.append(f"{spec.case_id}: {exc}")
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
    if problems:
        raise SystemExit("not frozen; fix before freezing:\n" + "\n".join(problems))
    for packet in packets.values():
        pid = packet["packet_id"]
        _write(OUT / "packets" / f"{pid}.json", json.dumps(packet, indent=1) + "\n")
        _write(OUT / "packets" / f"{pid}.md", _md(packet))
    records = [r.to_dict() | {"sha256": r.sha256} for r in PHASE4H_CASES]
    _write(OUT / "phase4h_preregistrations.json", json.dumps(records, indent=1) + "\n")
    rubric_doc = {"rubric_version": RUBRIC_VERSION, "rubric": RUBRIC, "ambiguities": AMBIGUITIES,
                  "note": "rule-based technical comparison; NOT inter-annotator agreement",
                  "cases": rubric_rows}  # fmt: skip
    _write(OUT / "phase4h_rubric_declarations.json", json.dumps(rubric_doc, indent=1) + "\n")
    extra = {
        "frozen_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "packet_version": PACKET_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "packet_ids": ids,
        "packet_sha256": {cid: p["sha256"] for cid, p in packets.items()},
        "rubric_declaration_sha256": {
            cid: r["declaration_sha256"] for cid, r in rubric_rows.items()
        },
        "rubric_document_sha256": sha256_json(rubric_doc),
        "note": "frozen before any Phase 4H recovery experiment; see docs/24 §3",
    }
    doc = manifest(PHASE4H_CASES, extra)
    _write(OUT / "phase4h_manifest.json", json.dumps(doc, indent=1) + "\n")
    print(json.dumps({"frozen": len(records), "packets": len(packets)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
