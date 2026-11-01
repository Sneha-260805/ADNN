"""A small fake kitchen for restoration-diagnostic unit tests (no Java, no ScienceWorld).

Mimics behaviours measured on the pinned simulator (docs/17, docs/19 §4):

* valid actions come with the uuids they refer to; door actions carry a portal
  uuid that is absent from the object tree, and door state is only in ``look()``;
* ``look around``/``inventory`` and unknown input take no time; ``wait1`` takes 2
  ticks; every other parsed action takes 1 tick, even when the simulator refuses
  it (pouring out of a closed container);
* temperatures drift every tick; an active sink adds a NEW water object (with
  hidden terminals) to each open container inside it without water, and drains
  a new water object into the sewer;
* ``mix`` deletes water + sodium chloride and creates salt water; ``eat``
  detaches the food from the tree.

Fault-injection knobs: ``noise`` (instance-dependent temperatures, i.e. replay
divergence), ``hidden`` (listed nowhere: unavailable), ``invalid`` (listed but
answered "No known action matches"), ``refuse`` (accepted text, no effect) and
``fail_on`` (raises inside ``step``).
"""

from __future__ import annotations

import copy
import itertools
from typing import Any

from scienceworld_fake import FakeGateway, FakeProcess

_instances = itertools.count()
DOOR_UUID = "90"


def _node(name: str, **props: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": name, "type": "", "isDeleted": False, "propMaterial": None,
        "propEdibility": None, "propContainer": None, "propDevice": None,
        "propHeatSource": None, "propCoolingSource": None, "propPortal": None,
        "propMoveable": {"isMovable": False}, "propElectricalConnection": None,
        "propLife": None,
    }  # fmt: skip
    base.update(props)
    return base


def _material(substance: str, temp: float = 10.0, state: str = "solid") -> dict[str, Any]:
    return {"substanceName": substance, "temperatureC": temp, "stateOfMatter": state}


def _container(*, closable: bool = False, is_open: bool = True) -> dict[str, Any]:
    return {"isContainer": "true", "isOpen": is_open, "isClosable": closable}


MOVABLE = {"isMovable": True}


class MiniKitchen:
    def __init__(
        self,
        *,
        noise: float = 0.0,
        hidden: frozenset[str] = frozenset(),
        invalid: frozenset[str] = frozenset(),
        refuse: frozenset[str] = frozenset(),
        fail_on: str | None = None,
    ) -> None:
        self.noise, self.hidden, self.invalid, self.refuse = noise, hidden, invalid, refuse
        self.fail_on = fail_on
        self._gateway = FakeGateway(FakeProcess())
        self.closed = False
        self.loaded: tuple[str, int, str] | None = None
        self.objects: dict[str, dict[str, Any]] = {}

    # -- world ------------------------------------------------------------------------
    def _add(self, parent: str | None, node: dict[str, Any], uuid: str | None = None) -> str:
        if uuid is None:
            uuid = str(self.next_uuid)
            self.next_uuid += 1
        node["uuid"], node["parent"] = uuid, parent
        self.objects[uuid] = node
        return uuid

    def _substance(self, parent: str, name: str, *, state: str = "solid") -> str:
        uuid = self._add(parent, _node(name, propMaterial=_material(name, state=state),
                                       propMoveable=dict(MOVABLE)))  # fmt: skip
        for t in ("terminal 1", "terminal 2"):
            self._add(uuid, _node(t, propElectricalConnection={"connectedTo": []}, hidden=True))
        return uuid

    def _build(self) -> None:
        self.objects, self.next_uuid, self.moves, self.door_open = {}, 100, 0, False
        self.offset = self.noise * (next(_instances) % 7)
        add = self._add
        add(None, _node("universe", propContainer=_container()), "1")
        add("1", _node("kitchen", propContainer=_container()), "2")
        add("2", _node("agent"), "3")
        add("3", _node("inventory", propContainer=_container()), "4")
        add("2", _node("cupboard", propContainer=_container(closable=True, is_open=False),
                       propMaterial=_material("wood")), "5")  # fmt: skip
        add("5", _node("ceramic cup", propContainer=_container(), propMoveable=dict(MOVABLE),
                       propMaterial=_material("ceramic")), "6")  # fmt: skip
        jar = _node("glass jar", propContainer=_container(closable=True),
                    propMoveable=dict(MOVABLE), propMaterial=_material("glass"))  # fmt: skip
        add("2", jar, "7")
        self.next_uuid = 8
        self._substance("7", "sodium chloride")  # 8, terminals 9 and 10
        add("2", _node("sink", propContainer=_container(),
                       propDevice={"isActivable": True, "isActivated": False}), "11")  # fmt: skip
        add("2", _node("sewer", propContainer=_container()), "12")
        add("2", _node("stove", propDevice={"isActivable": True, "isActivated": False}), "13")
        add("2", _node("bowl", propContainer=_container(), propMoveable=dict(MOVABLE)), "14")
        add("14", _node("apple", propEdibility={"isEdible": True}, propMoveable=dict(MOVABLE),
                        propMaterial=_material("apple")), "15")  # fmt: skip
        add("2", _node("table", propContainer=_container()), "16")
        for u in ("17", "18"):  # two indistinguishable cups
            add("16", _node("tin cup", propContainer=_container(), propMoveable=dict(MOVABLE),
                            propMaterial=_material("tin")), u)  # fmt: skip
        add("2", _node("metal pot", propContainer=_container(), propMoveable=dict(MOVABLE),
                       propMaterial=_material("steel")), "19")  # fmt: skip
        self.next_uuid = 100

    def _children(self, uuid: str) -> list[str]:
        return sorted((u for u, n in self.objects.items() if n["parent"] == uuid), key=int)

    def _descendants(self, uuid: str) -> set[str]:
        out: set[str] = set()
        for c in self._children(uuid):
            out |= {c} | self._descendants(c)
        return out

    def _is_container(self, u: str) -> bool:
        return self.objects[u]["propContainer"] is not None

    def _referent(self, u: str) -> str:
        name = self.objects[u]["name"]
        same = [v for v, n in self.objects.items() if n["name"] == name and not n.get("hidden")]
        return name if len(same) == 1 else f"{name} {u}"

    def _tick(self) -> None:
        self.moves += 1
        for n in self.objects.values():
            if n["propMaterial"] is not None:
                n["propMaterial"]["temperatureC"] = round(
                    n["propMaterial"]["temperatureC"] + 0.25 + self.offset, 6
                )
        sink = self.objects["11"]
        if sink["propDevice"]["isActivated"]:
            for c in self._children("11"):
                pc = self.objects[c]["propContainer"]
                has_water = any(self.objects[w]["name"] == "water" for w in self._children(c))
                if pc and pc["isOpen"] and not has_water:
                    self._substance(c, "water", state="liquid")
            self._substance("12", "water", state="liquid")  # drained into the sewer

    def _visible(self) -> list[str]:
        return sorted(
            (u for u in self._descendants("2") if not self.objects[u].get("hidden")), key=int
        )

    def _templates(self) -> list[dict[str, Any]]:
        out: list[tuple[str, int, tuple[str, ...]]] = []
        vis = self._visible()
        door_verb = "close" if self.door_open else "open"
        out.append((f"{door_verb} door to hallway", 0, (DOOR_UUID,)))
        for u in vis:
            n, ref = self.objects[u], self._referent(u)
            pc, pd = n["propContainer"], n["propDevice"]
            if pc and pc["isClosable"]:
                out.append((f"{'close' if pc['isOpen'] else 'open'} {ref}", 0, (u,)))
            if pd:
                out.append((f"{'deactivate' if pd['isActivated'] else 'activate'} {ref}", 6, (u,)))
            out.append((f"look at {ref}", 4, (u,)))
            if n["propEdibility"]:
                out.append((f"eat {ref}", 8, (u,)))
            if pc and len(self._children(u)) >= 2:
                out.append((f"mix {ref}", 7, (u,)))
            if n["propMoveable"]["isMovable"]:
                if n["parent"] == "4":
                    out.append((f"put down {ref}", 22, (u,)))
                else:
                    out.append((f"pick up {ref}", 21, (u,)))
                for c in dict.fromkeys([*vis, "4"]):
                    if self._is_container(c) and c != u and c not in self._descendants(u):
                        cref = "inventory" if c == "4" else self._referent(c)
                        out.append((f"move {ref} to {cref}", 9, (u, c)))
                        out.append((f"pour {ref} into {cref}", 10, (u, c)))
        rows = [
            {"action": a, "template_id": t, "obj_ids": [int(i) for i in ids], "type_ids": []}
            for a, t, ids in out
            if a not in self.hidden
        ]
        return [*rows, {"action": "wait1", "template_id": 30, "obj_ids": [], "type_ids": []}]

    # -- action effects -------------------------------------------------------------------
    def _apply(self, action: str, tid: int, ids: list[str]) -> str:
        if action in self.refuse:
            return "That can't be done right now."
        objs = [self.objects.get(i) for i in ids]
        if tid == 0 and ids == [DOOR_UUID]:
            self.door_open = action.startswith("open")
            return f"The door is now {'open' if self.door_open else 'closed'}."
        if tid == 0:
            is_open = action.startswith("open")
            objs[0]["propContainer"]["isOpen"] = is_open
            return f"The {objs[0]['name']} is now {'open' if is_open else 'closed'}."
        if tid == 6:
            on = action.startswith("activate")
            objs[0]["propDevice"]["isActivated"] = on
            return f"The {objs[0]['name']} is now {'activated' if on else 'deactivated'}."
        if tid in (9, 21, 22):
            dest = ids[1] if tid == 9 else "4" if tid == 21 else self.objects["3"]["parent"]
            objs[0]["parent"] = dest
            return f"You move the {objs[0]['name']} to the {self.objects[dest]['name']}."
        if tid == 10:
            src, dst = ids
            if self._is_container(src):
                if not self.objects[src]["propContainer"]["isOpen"]:
                    return f"The {objs[0]['name']} can't be poured out, because it's not open."
                for c in self._children(src):
                    if self.objects[c]["propMoveable"]["isMovable"]:
                        self.objects[c]["parent"] = dst
                return f"You pour the contents of the {objs[0]['name']} into the {objs[1]['name']}."
            objs[0]["parent"] = dst
            return f"You move the {objs[0]['name']} to the {objs[1]['name']}."
        if tid == 7:
            kids = {self.objects[c]["name"]: c for c in self._children(ids[0])}
            if {"water", "sodium chloride"} <= set(kids) and len(kids) == 2:
                for c in kids.values():
                    for gone in {c} | self._descendants(c):
                        del self.objects[gone]
                self._substance(ids[0], "salt water", state="liquid")
                return "Sodium chloride and water mix to produce salt water."
            return "Mixing does not appear to produce anything new."
        if tid == 8:
            objs[0]["parent"] = None  # detached, as ActionEat.removeAndResetContainer()
            return f"The {objs[0]['name']} was delicious."
        return f"You look at the {objs[0]['name']}." if objs and objs[0] else "Done."

    # -- Backend API ------------------------------------------------------------------------
    def load(self, task_name: str, variation_idx: int = 0, simplification_str: str = "",
             generate_gold_path: bool = False) -> None:  # fmt: skip
        self.loaded = (task_name, variation_idx, simplification_str)
        self._build()

    def reset(self) -> tuple[str, dict[str, Any]]:
        self._build()
        return self.look(), {"taskName": self.loaded[0] if self.loaded else None}

    def step(self, input_str: str) -> tuple[str, int, bool, dict[str, Any]]:
        a = input_str.strip()
        if a == self.fail_on:
            raise RuntimeError(f"injected failure on {a!r}")
        info = {"moves": self.moves, "score": 0}
        if a == "look around":
            return self.look(), 0, False, info
        if a == "wait1":
            self._tick()
            self._tick()
            return "You decide to wait for 1 iterations.", 0, False, {**info, "moves": self.moves}
        row = next((r for r in self._templates() if r["action"] == a), None)
        if row is None or a in self.invalid:
            return "No known action matches that input.", 0, False, info
        obs = self._apply(a, row["template_id"], [str(i) for i in row["obj_ids"]])
        self._tick()
        return obs, 0, False, {**info, "moves": self.moves}

    def look(self) -> str:
        names = [self.objects[u]["name"] for u in self._children("2")]
        return (
            "This room is called the kitchen. In it, you see: \n"
            + "".join(f"\ta {n}\n" for n in names)
            + "You also see:\n"
            + f"\tA door to the hallway (that is {'open' if self.door_open else 'closed'})\n"
        )

    def inventory(self) -> str:
        return "In your inventory, you see:\n\tnothing\n"

    def getObjectTree(self) -> dict[str, Any]:  # noqa: N802 - upstream name
        def build(u: str) -> dict[str, Any]:
            node = {k: copy.deepcopy(v) for k, v in self.objects[u].items()
                    if k not in ("parent", "hidden")}  # fmt: skip
            node["propContainer"] = (
                None if node["propContainer"] is None else dict(node["propContainer"])
            )
            node["contents"] = {f"{self.objects[c]['name']}-{c}": build(c)
                                for c in self._children(u)}  # fmt: skip
            return node

        return build("1")

    def get_valid_action_object_combinations(self) -> list[str]:
        return [r["action"] for r in self._templates()]

    def get_valid_action_object_combinations_with_templates(self) -> list[dict[str, Any]]:
        return self._templates()

    def get_num_moves(self) -> int:
        return self.moves

    def get_gold_action_sequence(self) -> list[str]:
        return []

    def close(self) -> None:
        self.closed = True
