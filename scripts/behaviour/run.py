"""Run from repository root with PYTHONPATH=src; see docs/MEMBER3_START_HERE.md."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

from adnn.behaviour.judgment import parse_judgment
from adnn.behaviour.models import TransformersModel
from adnn.behaviour.runner import run_task
from adnn.dataset.api import load_dataset
from adnn.dataset.prompting_v11 import build_stated_prompt, inputs_from_state
from adnn.tasks import initial_state, load_tasks


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def git_info():
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL,
        ).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True))
        return {"git_commit": commit, "git_dirty": dirty}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"git_commit": None, "git_dirty": None, "source_delivery": "uploaded_bundle"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["smoke", "pilot", "full", "rq2"], required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--dataset", help="Frozen production dataset directory for RQ2")
    p.add_argument("--tasks", default="data/tasks/rq3-tasks-1.0")
    p.add_argument("--output", required=True, help="New directory; existing output is rejected")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--max-new-tokens", type=int, default=256)
    args = p.parse_args()
    if args.mode == "rq2" and not args.dataset:
        p.error("--dataset is required for RQ2")
    ds = load_dataset(args.dataset) if args.mode == "rq2" else None
    tasks = load_tasks(args.tasks) if ds is None else []
    if args.mode == "pilot":
        tasks = [t for t in tasks if t["pilot"]]
    if args.mode == "smoke":
        tasks = [t for t in tasks if t["task_pair_id"] == tasks[0]["task_pair_id"]]
    records = list(ds.iter_split("test")) if ds else tasks
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    manifest_path = Path(args.dataset if ds else args.tasks) / "manifest.json"
    config = vars(args) | {
        "python": platform.python_version(), "do_sample": False, "max_steps": 15,
        "dtype": "float16", "device_map": "auto", "quantization": None,
        **git_info(),
        "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                          for folder in ["src/adnn", "scripts/behaviour"]
                          for p in sorted(Path(folder).rglob("*.py"))},
        "rq1_checkpoint_match": "unverified_historical_revisions_unavailable",
        "dataset_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "versions": {name: importlib.metadata.version(name)
                     for name in ["torch", "transformers", "accelerate"]},
        "planned_ids": [r["id"] if ds else r["task_id"] for r in records],
    }
    save(out / "config.json", config)
    model = TransformersModel(args.model, args.revision, args.seed, args.max_new_tokens)
    with (out / "outcomes.jsonl").open("x", encoding="utf-8") as outcomes:
        for record in records:
            if ds:
                bundle = ds.stated_prompt(record)
                row = {"example_id": record["id"], "scenario_id": record["scenario_id"],
                       "pair_id": record["pair_id"], "label": record["label"],
                       "render_style": record["render_style"],
                       "environment": record["environment"],
                       "messages": bundle.messages, "prompt_sha256": bundle.prompt_sha256}
                try:
                    row["raw"] = model(bundle.messages)
                    row["prediction"] = parse_judgment(row["raw"])
                except Exception as exc:
                    row.update(raw=None, prediction="UNPARSEABLE", error=str(exc))
            else:
                # Separate stated critical-action judgments are needed for pair-level K.
                bundle = build_stated_prompt(inputs_from_state(
                    record["task_text"], initial_state(record), "kv",
                ), record["critical_action_text"])
                judgment = {"messages": bundle.messages, "prompt_sha256": bundle.prompt_sha256}
                try:
                    judgment["raw"] = model(bundle.messages)
                    judgment["prediction"] = parse_judgment(judgment["raw"])
                except Exception as exc:
                    judgment.update(raw=None, prediction="UNPARSEABLE", error=str(exc))
                with (out / (record["task_id"] + ".jsonl")).open("x", encoding="utf-8") as trace:
                    def emit(step):
                        trace.write(json.dumps(step) + "\n")
                        trace.flush()
                    row = run_task(record, model, emit)
                row.pop("trace")
                row["stated_judgment"] = judgment
            outcomes.write(json.dumps(row) + "\n")
            outcomes.flush()


if __name__ == "__main__":
    main()
