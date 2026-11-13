"""Separate exploratory experiments with fixed prompt conditions and safe resume."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from adnn.behaviour.judgment import parse_judgment
from adnn.behaviour.models import TransformersModel
from adnn.behaviour.prompt_conditions import apply_condition, messages_sha256
from adnn.behaviour.runner import run_task
from adnn.dataset.api import load_dataset
from adnn.dataset.prompting_v11 import build_stated_prompt, inputs_from_state
from adnn.tasks import initial_state, load_tasks


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def package_versions():
    versions = {}
    for name in ["torch", "transformers", "accelerate"]:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def select_development(ds, count, seed):
    """Only train scenarios; never select or stratify using test outcomes."""
    records = list(ds.iter_split("train"))
    scenarios = sorted({r["scenario_id"] for r in records})
    if not 1 <= count <= len(scenarios):
        raise ValueError(f"dev-scenarios must be between 1 and {len(scenarios)}")
    random.Random(seed).shuffle(scenarios)
    chosen = sorted(scenarios[:count])
    return [r for r in records if r["scenario_id"] in chosen], chosen


def completed_rows(path):
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid outcomes line {number}; preserve it and repair explicitly") from exc
    return rows


def validate_resume(saved, requested, rows):
    if saved != requested:
        raise ValueError("Resume configuration differs; start a separate output directory")
    ids = [r.get("example_id", r.get("task_id")) for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate completed IDs")
    if not set(ids) <= set(requested["planned_ids"]):
        raise ValueError("Saved outcomes contain unexpected IDs")
    return set(ids)


def fresh_trace_path(directory, task_id):
    path = directory / f"{task_id}.jsonl"
    attempt = 1
    while path.exists():
        attempt += 1
        path = directory / f"{task_id}.attempt-{attempt}.jsonl"
    return path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["rq2-dev", "rq2-test", "smoke", "pilot", "full"], required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--dataset", type=Path, default=Path("data/production/v2.0"))
    p.add_argument("--tasks", type=Path, default=Path("data/tasks/rq3-tasks-1.0"))
    p.add_argument("--agent-condition", choices=["neutral", "format_v1", "format_careful_v1"], default="neutral")
    p.add_argument("--judgment-condition", choices=["neutral", "recovery_v1"], default="neutral")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dev-scenarios", type=int, default=10)
    p.add_argument("--max-new-tokens", type=int, default=256)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Save the plan without loading a model")
    args = p.parse_args()
    if args.max_new_tokens < 1:
        p.error("max-new-tokens must be positive")
    if len(args.revision) != 40 or any(c not in "0123456789abcdef" for c in args.revision):
        p.error("revision must be a pinned 40-character lowercase commit hash")
    rq2 = args.mode.startswith("rq2")
    if rq2 and args.agent_condition != "neutral":
        p.error("Agent conditions do not apply to RQ2")
    versions = package_versions()
    if not args.dry_run and any(value is None for value in versions.values()):
        p.error("Install the project's models dependencies before inference")
    chosen = []
    if rq2:
        ds = load_dataset(args.dataset)
        if args.mode == "rq2-dev":
            records, chosen = select_development(ds, args.dev_scenarios, args.seed)
        else:
            records = list(ds.iter_split("test"))
        manifest_path = args.dataset / "manifest.json"
    else:
        records = load_tasks(args.tasks)
        if args.mode == "pilot":
            records = [r for r in records if r["pilot"]]
        elif args.mode == "smoke":
            records = [r for r in records if r["task_pair_id"] == records[0]["task_pair_id"]]
        manifest_path = args.tasks / "manifest.json"
    config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()
              if k not in {"resume", "dry_run", "output"}}
    config.update(
        study="exploratory_followup_v1", dtype="float16", do_sample=False,
        max_steps=15, selected_development_scenarios=chosen,
        label_counts=dict(Counter(r["label"] for r in records)) if rq2 else None,
        planned_ids=[r["id"] if rq2 else r["task_id"] for r in records],
        dataset_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        source_sha256={str(f): hashlib.sha256(f.read_bytes()).hexdigest()
                       for folder in [Path("src/adnn"), Path("scripts/behaviour")]
                       for f in sorted(folder.rglob("*.py"))},
        versions=versions,
        python=platform.python_version(),
    )
    out = args.output
    if args.resume:
        saved = json.loads((out / "config.json").read_text(encoding="utf-8"))
        done = validate_resume(saved, config, completed_rows(out / "outcomes.jsonl"))
    else:
        out.mkdir(parents=True, exist_ok=False)
        write_json(out / "config.json", config)
        done = set()
    if args.dry_run:
        print(json.dumps({"planned": len(records), "completed": len(done), "config": str(out / "config.json")}))
        return
    remaining = [r for r in records if (r["id"] if rq2 else r["task_id"]) not in done]
    if not remaining:
        print("All planned outcomes already exist; nothing rerun")
        return
    model = TransformersModel(args.model, args.revision, args.seed, args.max_new_tokens)
    import torch
    write_json(out / "runtime.json", {
        "last_session_started_utc": datetime.now(timezone.utc).isoformat(),
        "requested_revision": args.revision,
        "resolved_model_revision": getattr(model.model.config, "_commit_hash", None),
        "generation_config": model.model.generation_config.to_dict(),
        "gpu_names": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
    })
    with (out / "outcomes.jsonl").open("a", encoding="utf-8") as stream:
        for record in remaining:
            if rq2:
                bundle = ds.stated_prompt(record)
            else:
                bundle = build_stated_prompt(inputs_from_state(
                    record["task_text"], initial_state(record), "kv"), record["critical_action_text"])
            messages = apply_condition(bundle.messages, judgment=args.judgment_condition)
            judgment = {"messages": messages, "base_prompt_sha256": bundle.prompt_sha256,
                        "effective_messages_sha256": messages_sha256(messages)}
            try:
                judgment["raw"] = model(messages)
                judgment["prediction"] = parse_judgment(judgment["raw"])
            except Exception as exc:
                judgment.update(raw=None, prediction="UNPARSEABLE", error=f"{type(exc).__name__}: {exc}")
            if rq2:
                row = dict(judgment, example_id=record["id"], scenario_id=record["scenario_id"],
                           pair_id=record["pair_id"], label=record["label"],
                           environment=record["environment"], render_style=record["render_style"])
            else:
                trace_path = fresh_trace_path(out, record["task_id"])
                with trace_path.open("x", encoding="utf-8") as trace:
                    def emit(step):
                        trace.write(json.dumps(step) + "\n")
                        trace.flush()
                    row = run_task(record, model, emit, agent_condition=args.agent_condition)
                row.pop("trace")
                row.update(stated_judgment=judgment, trace_file=trace_path.name)
            row.update(agent_condition=args.agent_condition, judgment_condition=args.judgment_condition)
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            done.add(record["id"] if rq2 else record["task_id"])
            write_json(out / "progress.json", {
                "completed": len(done), "planned": len(records),
                "last_completed_id": record["id"] if rq2 else record["task_id"],
                "updated_utc": datetime.now(timezone.utc).isoformat(),
            })
            print(f"Completed {len(done)}/{len(records)}", flush=True)


if __name__ == "__main__":
    main()
