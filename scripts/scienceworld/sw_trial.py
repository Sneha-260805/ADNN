"""ScienceWorld installation and reproducibility trial (Phase 4B, docs/17).

Standalone measurement script: imports only the standard library and
``scienceworld``; it never imports ``adnn`` and never produces research labels.
Run it with the Python of an isolated ScienceWorld venv, with a JDK on PATH for
that command only, e.g. (Git Bash)::

    SW="$LOCALAPPDATA/adnn-sw"
    PATH="$SW/jdk/jdk-21.0.13+9/bin:$PATH" "$SW/venv-e8216d6/Scripts/python.exe" \
        scripts/scienceworld/sw_trial.py all --out results/scienceworld_trial/e8216d6

Subcommands: ``smoke``, ``resets``, ``replay`` (one process), ``fresh-replays``
(N separate processes), ``probes``, ``all``. Every subcommand writes JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import scienceworld
from scienceworld import ScienceWorldEnv

# Upstream boiling trace (tests/test_scienceworld.py::test_boiling_is_deterministic on main).
BOIL = {
    "task": "1-1",
    "variation": 0,
    "simplifications": "teleportAction",
    "actions": [
        "teleport to kitchen",
        "pour counter into sink",
        "activate sink",
        "use lighter on drawer",
        "look around",
    ],
}
UUID_KEYS = ("uuid", "connectsFrom", "connectsTo")


# -- state fingerprints ---------------------------------------------------------------
def sha(obj: Any) -> str:
    text = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def flatten(obj: Any, *, uuid_free: bool, path: str = "") -> dict[str, Any]:
    """Object tree -> {path: scalar}. ``uuid_free`` drops uuids and names children by name.

    Same-named siblings are disambiguated as ``name#i`` in **uuid order** (uuids are
    deterministic within one task/variation on 1.3.0). Ordering them by content
    instead would let temperature drift reorder siblings and fake discrete changes.
    """
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        items = list(obj.items())
        if uuid_free and (path == "contents" or path.endswith(".contents")):
            renamed: dict[str, list[Any]] = {}
            for k, v in items:
                renamed.setdefault(re.sub(r"-\d+$", "", k), []).append(v)
            items = []
            for name, children in sorted(renamed.items()):
                children.sort(key=lambda c: int(c.get("uuid", 0)) if isinstance(c, dict) else 0)
                for i, child in enumerate(children):
                    items.append((name if len(children) == 1 else f"{name}#{i}", child))
        for k, v in items:
            if uuid_free and k in UUID_KEYS:
                continue
            out.update(flatten(v, uuid_free=uuid_free, path=f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, uuid_free=uuid_free, path=f"{path}[{i}]"))
    else:
        out[path] = obj
    return out


def uuids(obj: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "uuid":
                found.add(str(v))
            found |= uuids(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= uuids(v)
    return found


def walk(obj: Any) -> Iterator[dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def temperatures(tree: Any) -> dict[str, float]:
    flat = flatten(tree, uuid_free=True)
    return {k: v for k, v in flat.items() if k.endswith(".temperatureC") and v is not None}


def diff(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def fingerprint(env: ScienceWorldEnv, obs: str) -> dict[str, Any]:
    tree = env.getObjectTree()
    valid = env.get_valid_action_object_combinations()
    return {
        "obs_sha": sha(obs),
        "look_sha": sha(env.look()),
        "inv_sha": sha(env.inventory()),
        "tree_raw_sha": sha(tree),
        "tree_uuid_free_sha": sha(flatten(tree, uuid_free=True)),
        "n_uuids": len(uuids(tree)),
        "valid_sha": sha(sorted(valid)),
        "n_valid": len(valid),
        "moves": env.get_num_moves(),
    }


def environment_info() -> dict[str, Any]:
    pkg = Path(scienceworld.__file__).parent
    jar = pkg / "scienceworld.jar"
    java = subprocess.run(["java", "-version"], capture_output=True, text=True)
    return {
        "scienceworld_version": getattr(scienceworld, "__version__", None),
        "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "java_version": (java.stderr or java.stdout).strip().splitlines()[:3],
    }


def write(out: Path, name: str, data: Any) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# -- experiments ----------------------------------------------------------------------------
def smoke(out: Path) -> dict[str, Any]:
    t0 = time.perf_counter()
    env = ScienceWorldEnv("", envStepLimit=100)
    t_start = time.perf_counter() - t0
    tasks = env.get_task_names()
    variations = {t: env.get_max_variations(t) for t in tasks}
    env.load("4-1", 0, "")
    obs, info = env.reset()
    tree = env.getObjectTree()
    valid = env.get_valid_action_object_combinations()
    harmless = "look around" if "look around" in valid else valid[0]
    obs2, reward, done, info2 = env.step(harmless)
    env.close()
    res = {
        "jvm_start_s": round(t_start, 3),
        "n_tasks": len(tasks),
        "tasks": tasks,
        "max_variations": variations,
        "loaded": "4-1 variation 0",
        "reset_obs_head": obs[:300],
        "info_keys": sorted(info),
        "tree_top_keys": sorted(tree)[:20] if isinstance(tree, dict) else type(tree).__name__,
        "tree_n_uuids": len(uuids(tree)),
        "n_valid": len(valid),
        "valid_sample": valid[:15],
        "harmless_action": harmless,
        "step_return": {"reward": reward, "done": done, "moves": info2.get("moves")},
        "obs_after_head": obs2[:200],
        "obs_mentions_score": "score" in (obs + obs2).lower(),
    }
    write(out, "smoke.json", res)
    return res


def resets(out: Path, n: int, spec: dict[str, Any]) -> dict[str, Any]:
    env = ScienceWorldEnv("", envStepLimit=100)
    env.load(spec["task"], spec["variation"], spec["simplifications"])
    prints, times = [], []
    for _ in range(n):
        t0 = time.perf_counter()
        obs, _ = env.reset()
        times.append(time.perf_counter() - t0)
        prints.append(fingerprint(env, obs))
    env.close()
    keys = [k for k in prints[0] if k != "moves"]
    res = {
        "spec": {k: spec[k] for k in ("task", "variation", "simplifications")},
        "n_resets": n,
        "identical_across_resets": {k: len({p[k] for p in prints}) == 1 for k in keys},
        "distinct_values": {k: len({p[k] for p in prints}) for k in keys},
        "reset_s": {"mean": round(statistics.mean(times), 4), "max": round(max(times), 4)},
        "first": prints[0],
    }
    write(out, "resets.json", res)
    return res


def replay_once(spec: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    env = ScienceWorldEnv("", envStepLimit=100)
    env.load(spec["task"], spec["variation"], spec["simplifications"])
    obs, _ = env.reset()
    t_ready = time.perf_counter() - t0
    trace, step_times = [fingerprint(env, obs) | {"action": None, "obs": obs}], []
    for action in spec["actions"]:
        t1 = time.perf_counter()
        obs, reward, done, _info = env.step(action)
        step_times.append(time.perf_counter() - t1)
        fp = fingerprint(env, obs)
        trace.append(fp | {"action": action, "obs": obs, "reward": reward, "done": done})
    tree = env.getObjectTree()
    env.close()
    return {
        "trace": trace,
        "final_uuids": sorted(uuids(tree), key=int),
        "final_tree_uuid_free": flatten(tree, uuid_free=True),
        "jvm_start_and_reset_s": round(t_ready, 3),
        "step_s": [round(t, 4) for t in step_times],
        "total_s": round(time.perf_counter() - t0, 3),
    }


def fresh_replays(out: Path, n: int, spec: dict[str, Any], name: str) -> dict[str, Any]:
    runs = []
    for i in range(n):
        proc = subprocess.run(
            [sys.executable, __file__, "replay", "--spec", json.dumps(spec)],
            capture_output=True,
            text=True,
            check=True,
        )
        runs.append(json.loads(proc.stdout))
        write(out / f"{name}_traces", f"run_{i}.json", runs[-1])
    step_keys = [
        "obs_sha",
        "look_sha",
        "inv_sha",
        "tree_raw_sha",
        "tree_uuid_free_sha",
        "valid_sha",
    ]
    per_key = {
        k: all([s[k] for s in r["trace"]] == [s[k] for s in runs[0]["trace"]] for r in runs)
        for k in step_keys
    }
    divergent_steps = sorted(
        {
            i
            for r in runs[1:]
            for i, (s, s0) in enumerate(zip(r["trace"], runs[0]["trace"], strict=True))
            if s["tree_uuid_free_sha"] != s0["tree_uuid_free_sha"] or s["obs_sha"] != s0["obs_sha"]
        }
    )
    final_diffs = [
        diff(runs[0]["final_tree_uuid_free"], r["final_tree_uuid_free"])[:20] for r in runs[1:]
    ]
    res = {
        "spec": spec,
        "n_processes": n,
        "identical_across_processes": per_key,
        "uuids_identical_across_processes": all(
            r["final_uuids"] == runs[0]["final_uuids"] for r in runs
        ),
        "divergent_step_indices": divergent_steps,
        "final_tree_diffs_vs_run0": final_diffs,
        "final_obs": [r["trace"][-1]["obs"] for r in runs],  # full text (no truncation)
        "n_valid_per_step": [s["n_valid"] for s in runs[0]["trace"]],
        "moves_per_step": [s["moves"] for s in runs[0]["trace"]],
        "jvm_start_and_reset_s": [r["jvm_start_and_reset_s"] for r in runs],
        "mean_step_s": round(statistics.mean(t for r in runs for t in r["step_s"]), 4),
        "process_total_s": [r["total_s"] for r in runs],
    }
    write(out, f"{name}_fresh_replays.json", res)
    return res


def _state(env: ScienceWorldEnv) -> tuple[dict[str, Any], int]:
    return flatten(env.getObjectTree(), uuid_free=True), env.get_num_moves()


def _split_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changed = diff(before, after)
    temp = [k for k in changed if k.endswith(".temperatureC")]
    discrete = [k for k in changed if not k.endswith(".temperatureC")]
    deltas = [
        abs(float(after[k]) - float(before[k]))
        for k in temp
        if isinstance(before.get(k), int | float) and isinstance(after.get(k), int | float)
    ]
    return {
        "n_changed": len(changed),
        "n_temperature_changed": len(temp),
        "max_abs_temperature_delta": round(max(deltas), 4) if deltas else 0.0,
        "n_discrete_changed": len(discrete),
        "discrete_changed": discrete[:15],
    }


def _named_uuids(tree: Any) -> dict[str, str]:
    return {str(n["uuid"]): str(n.get("name")) for n in walk(tree) if "uuid" in n}


def _act(env: ScienceWorldEnv, action: str | None) -> dict[str, Any]:
    tree0 = env.getObjectTree()
    before, m0 = flatten(tree0, uuid_free=True), env.get_num_moves()
    look0 = env.look()
    obs = env.look() if action is None else env.step(action)[0]
    tree1 = env.getObjectTree()
    after, m1 = flatten(tree1, uuid_free=True), env.get_num_moves()
    u0, u1 = _named_uuids(tree0), _named_uuids(tree1)
    return {
        "action": action or "<free look()>",
        "obs_head": obs[:160],
        "moves": [m0, m1],
        **_split_changes(before, after),
        "new_objects": sorted(u1[u] for u in set(u1) - set(u0)),
        "removed_objects": sorted(u0[u] for u in set(u0) - set(u1)),
        "look_changed": look0 != env.look(),
    }


def probes(out: Path) -> dict[str, Any]:
    res: dict[str, Any] = {}
    env = ScienceWorldEnv("", envStepLimit=100)

    # (a) time advance: free look() vs step("look around") vs invalid input vs wait1 vs wait
    env.load("1-1", 0, "")
    env.reset()
    res["time"] = [
        _act(env, a)
        for a in (None, "look around", "dance wildly with the ceiling", "wait1", "wait1", "wait")
    ]

    # (b) doors / portals and devices in the object tree
    env.reset()
    tree = env.getObjectTree()
    valid = env.get_valid_action_object_combinations()
    door_actions = [a for a in valid if a.startswith("open door")]
    obs_res: dict[str, Any] = {
        "n_tree_nodes_with_propPortal": sum(
            1 for n in walk(tree) if n.get("propPortal") not in (None, "null")
        ),
        "n_tree_nodes_with_propDevice": sum(
            1 for n in walk(tree) if n.get("propDevice") not in (None, "null")
        ),
        "door_actions_available": door_actions,
    }
    if door_actions:
        opened = _act(env, door_actions[0])
        closed = _act(env, door_actions[0].replace("open door", "close door"))
        obs_res["door_open"] = opened
        obs_res["door_close"] = closed
    env.load("1-1", 0, "teleportAction")
    env.reset()
    env.step("teleport to kitchen")
    kitchen_valid = env.get_valid_action_object_combinations()
    device = next((a for a in kitchen_valid if a == "activate stove"), None) or next(
        (a for a in kitchen_valid if a.startswith("activate ")), None
    )
    if device:
        obs_res["device_on"] = _act(env, device)
        obs_res["device_off"] = _act(env, device.replace("activate", "deactivate", 1))
    res["observability"] = obs_res

    # (c) new objects / hidden state from pouring and mixing (chemistry-mix gold path)
    env.load("6-1", 0, "", generateGoldPath=True)
    env.reset()
    gold = env.get_gold_action_sequence()
    events = []
    for act in gold:
        rec = _act(env, act)
        if rec["new_objects"] or rec["removed_objects"] or act.startswith(("pour", "mix")):
            events.append(
                {k: rec[k] for k in ("action", "obs_head", "new_objects", "removed_objects")}
            )
        if env.get_num_moves() >= 90:
            break
    res["mixing"] = {"gold_len": len(gold), "gold": gold, "object_events": events}

    # (d) branching factor across states visited on the boil trace
    env.load(BOIL["task"], BOIL["variation"], BOIL["simplifications"])
    env.reset()
    counts = [len(env.get_valid_action_object_combinations())]
    for act in BOIL["actions"]:
        env.step(act)
        counts.append(len(env.get_valid_action_object_combinations()))
    res["n_valid_on_boil_trace"] = counts

    # (e) branching factor at the start of several tasks (variation 0, no simplifications)
    res["n_valid_at_start"] = {}
    for task in ("1-1", "4-1", "6-1", "3-1"):
        env.load(task, 0, "")
        env.reset()
        res["n_valid_at_start"][task] = len(env.get_valid_action_object_combinations())
    env.close()
    write(out, "probes.json", res)
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "command", choices=["smoke", "resets", "replay", "fresh-replays", "probes", "all"]
    )
    ap.add_argument("--out", type=Path, default=Path("results/scienceworld_trial/unnamed"))
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--spec", type=str, default=json.dumps(BOIL))
    args = ap.parse_args(argv)
    spec = json.loads(args.spec)
    if args.command == "replay":  # child process mode: print the trace to stdout
        print(json.dumps(replay_once(spec)))
        return 0
    write(
        args.out,
        "environment.json",
        environment_info() | {"JAVA_HOME": os.environ.get("JAVA_HOME")},
    )
    if args.command in ("smoke", "all"):
        smoke(args.out)
    if args.command in ("resets", "all"):
        resets(args.out, max(args.n, 10), spec)
    if args.command in ("fresh-replays", "all"):
        fresh_replays(args.out, max(min(args.n, 5), 5), spec, "boil")
    if args.command in ("probes", "all"):
        probes(args.out)
    print(f"wrote results to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
