"""Freeze the RQ3 paired task set ``rq3-tasks-1.0`` (docs/42; preregistration
``docs/preregistration/rq3_tasks_v1.md``). Pure: no model, no simulator.

    .venv/Scripts/python.exe scripts/tasks/freeze_rq3_tasks.py --check   # validate, write nothing
    .venv/Scripts/python.exe scripts/tasks/freeze_rq3_tasks.py           # freeze; no overwrite
    .venv/Scripts/python.exe scripts/tasks/freeze_rq3_tasks.py --verify  # re-check a frozen set

The freeze writes ``data/tasks/rq3-tasks-1.0/``: ``tasks.jsonl`` (120 versions),
``tool_sets.json``, ``validation.json`` and ``manifest.json``. It runs every check of
:func:`adnn.tasks.rq3.validate_tasks`, including the overlap check against the frozen v1.0
and v2.0 probe records, and refuses to freeze if any check fails. ``--verify`` rebuilds
the set from code and requires it to equal the frozen file byte for byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from adnn.dataset.prompting_v11 import PROMPT_BUILDER_VERSION
from adnn.dataset.schema import read_jsonl, sha256_file, write_json, write_jsonl
from adnn.sandbox.tools import ASK_USER_REPLY, tool_specs_for
from adnn.tasks.contract import CONTRACT_VERSION, MAX_STEPS, PARSE_ERROR_MESSAGE, initial_state
from adnn.tasks.rq3 import (
    GENERATOR_VERSION,
    PILOT_SEED,
    TASK_SET_VERSION,
    build_tasks,
    pilot_pair_ids,
    validate_tasks,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = Path("data/tasks/rq3-tasks-1.0")
PROBE = {
    "adnn-dataset-1.0": Path("data/production/v1.0/records.jsonl"),
    "adnn-dataset-2.0": Path("data/production/v2.0/records.jsonl"),
}
CODE = [
    "src/adnn/tasks/contract.py",
    "src/adnn/tasks/rq3.py",
    "src/adnn/sandbox/tools.py",
    "src/adnn/sandbox/state.py",
    "src/adnn/sandbox/restoration.py",
    "scripts/tasks/freeze_rq3_tasks.py",
]


def _code_sha() -> str:
    h = hashlib.sha256()
    for rel in CODE:
        h.update(rel.encode() + b"\0" + (ROOT / rel).read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def _probe_texts() -> list[str]:
    texts: list[str] = []
    for path in PROBE.values():
        for r in read_jsonl(path):
            texts += [r["state_text"], r["action_text"], r["task_text"]]
    return texts


def _with_pilot(tasks: list[dict]) -> tuple[list[dict], list[str]]:
    by_mech: dict[str, set[str]] = {}
    for t in tasks:
        by_mech.setdefault(t["mechanism"], set()).add(t["task_pair_id"])
    pilot = pilot_pair_ids({m: sorted(v) for m, v in by_mech.items()})
    return [t | {"pilot": t["task_pair_id"] in pilot} for t in tasks], pilot


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true")
    g.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    tasks, pilot = _with_pilot(build_tasks())
    if args.verify:
        man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
        for key, entry in man["files"].items():
            if sha256_file(OUT / entry["file"]) != entry["sha256"]:
                raise SystemExit(f"{key}: hash does not match the manifest")
        if read_jsonl(OUT / "tasks.jsonl") != tasks:
            raise SystemExit("frozen tasks differ from the generator output")
        print(json.dumps({"verify": "ok", "versions": len(tasks)}))
        return 0
    report = validate_tasks(tasks, _probe_texts())
    print(json.dumps({"ok": report["ok"], "counts": report["counts"], "pilot": pilot,
                      "errors": report["errors"][:20]}, indent=1))  # fmt: skip
    if not report["ok"]:
        return 1
    if args.check:
        return 0
    if (OUT / "manifest.json").exists():
        raise SystemExit(f"{OUT} is frozen; refusing to overwrite")
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "tasks.jsonl", tasks)
    tools = tool_specs_for(initial_state(tasks[0]))
    write_json(OUT / "tool_sets.json", {tasks[0]["tool_set_id"]: tools})
    write_json(OUT / "validation.json", report)
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()  # fmt: skip
    manifest = {
        "task_set_version": TASK_SET_VERSION,
        "generator_version": GENERATOR_VERSION,
        "contract_version": CONTRACT_VERSION,
        "prompt_builder_version": PROMPT_BUILDER_VERSION,
        "state_style": "kv (render_observation_v11)",
        "max_steps": MAX_STEPS,
        "ask_user_reply": ASK_USER_REPLY,
        "parse_error_message": PARSE_ERROR_MESSAGE,
        "tool_set_id": tasks[0]["tool_set_id"],
        "counts": report["counts"],
        "pilot": {
            "seed": PILOT_SEED,
            "pair_ids": pilot,
            "policy": "pilot these 10 frozen pairs first, then rerun all 60 pairs for the "
            "final evaluation; pilot runs are reported, not pooled",
        },
        "files": {
            k: {"file": f, "sha256": sha256_file(OUT / f)}
            for k, f in (
                ("tasks", "tasks.jsonl"),
                ("tool_sets", "tool_sets.json"),
                ("validation", "validation.json"),
            )
        },
        "overlap_checked_against": {k: sha256_file(p) for k, p in PROBE.items()},
        "provenance": {"base_commit": head, "code_sha256": _code_sha(), "code_files": CODE},
        "note": "frozen before any RQ3 model run; production v1.0/v2.0 untouched",
    }
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps({"frozen": str(OUT), "versions": len(tasks)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
