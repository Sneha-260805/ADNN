"""SWT pilot step 0: read-only enumeration of candidate worlds (no target is executed).

For each (task, variation) world it loads S0 only (``teleportAction`` simplification, no
agent action at all) and lists, per room: openable containers, activable devices, movable
objects, statically combustible objects (substance combustion point <= lighter max temp
2200 C, from the pinned MaterialProperties.scala), liquid-water holders, the lighter and
electrical parts. Output: ``results/swt_pilot/enumeration.json`` (git-ignored).

This step is used ONLY to choose which cases to pre-register; it never runs a target, a
recovery action or a lighter. Run from the repository root with the isolated runtime::

    .venv/Scripts/python.exe scripts/scienceworld/swt_pilot/enumerate_worlds.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.canonical import capture_state
from adnn.scienceworld.env import ScienceWorldSession

OUT = Path("results/swt_pilot/enumeration.json")
# Substances whose combustionPoint <= 2200 C (HeatSourcePropertiesLighter.maxTemp) in the
# pinned MaterialProperties.scala (e8216d6).
COMBUSTIBLE = {
    "wood", "paper", "sandpaper", "cloth", "rubber", "plant matter", "flower matter",
    "pollen matter", "chocolate", "sugar", "marshmallow", "soap", "flour", "jam", "dough",
    "nut", "sodium bicarbonate",
}  # fmt: skip
WORLDS = [
    (t, 0)
    for t in (
        "1-1", "1-2", "1-3", "1-4", "2-1", "2-2", "2-3", "3-1", "3-2", "3-3", "3-4",
        "4-2", "6-1", "6-2", "6-3", "9-1", "9-2", "9-3", "10-1",
    )
] + [("1-1", 1), ("1-1", 2), ("3-1", 1), ("3-1", 2), ("6-2", 1), ("9-2", 1)]  # fmt: skip


def room_of(path: str) -> str:
    parts = path.split("/")
    return parts[1] if len(parts) > 1 else "universe"


def summarise(objects: dict) -> dict:
    by_room: dict[str, dict[str, list[str]]] = {}
    names = Counter(r["name"] for r in objects.values() if not r.get("isDeleted"))
    for r in objects.values():
        if r.get("isDeleted") or r["path"].count("/") < 2:
            continue
        room = room_of(r["path"])
        rel = r["path"].split("/", 2)[2]
        d = by_room.setdefault(room, {})

        def add(key: str, rel: str = rel, d: dict = d) -> None:
            d.setdefault(key, []).append(rel)

        if r.get("propContainer.isClosable"):
            add("openable(" + ("open" if r.get("propContainer.isOpen") else "closed") + ")")
        if r.get("propDevice.isActivable"):
            add("activable(" + ("on" if r.get("propDevice.isActivated") else "off") + ")")
        if r.get("propMoveable.isMovable") and r.get("propMaterial.stateOfMatter") == "solid":
            add("movable")
        sub = r.get("propMaterial.substanceName")
        if sub in COMBUSTIBLE and r.get("propMaterial.stateOfMatter") == "solid":
            add(f"combustible[{sub}]" + ("[movable]" if r.get("propMoveable.isMovable") else ""))
        if sub == "water" and r.get("propMaterial.stateOfMatter") == "liquid":
            add("liquid_water")
        if r["name"] == "lighter":
            add("LIGHTER")
        if r["name"].startswith("terminal ") or "wire" in r["name"] or "battery" in r["name"]:
            add("electrical")
    dup = sorted(n for n, k in names.items() if k > 1)
    return {"rooms": by_room, "duplicate_names": dup}


def main() -> int:
    out = {}
    with ScienceWorldSession(RuntimeConfig.from_env()) as session:
        for task, var in WORLDS:
            try:
                session.load(task, var, "teleportAction")
            except Exception as exc:
                out[f"{task}/v{var}"] = {"error": repr(exc)}
                continue
            cs = capture_state(session).canonical
            task_text = session.step("task").observation.strip()
            out[f"{task}/v{var}"] = {"task_text": task_text, **summarise(cs.objects)}
            print(task, var, sorted(out[f"{task}/v{var}"]["rooms"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
