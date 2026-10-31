"""A small fake ScienceWorld backend for unit tests (no Java, no ScienceWorld).

It mimics the behaviours measured on the real simulator in Phase 4B (docs/17):
``look around`` and invalid input do not advance time; timed actions advance
``moves`` and change temperatures; ``wait1`` advances moves by 2; the first
tick creates objects; doors are visible only in ``look()`` text, never in the
object tree; ``mix`` deletes inputs and creates a new object; ambiguous input
returns an "Ambiguous request" prompt. ``noise`` makes temperatures depend on
the instance, to simulate hidden non-determinism.
"""

from __future__ import annotations

import copy
import itertools
import subprocess
from typing import Any

_counter = itertools.count(1000)


def _obj(name: str, uuid: int, *, temp: float | None = None, **props: Any) -> dict[str, Any]:
    node: dict[str, Any] = {
        "uuid": str(uuid), "name": name, "type": "", "isDeleted": False,
        "propMaterial": None, "propEdibility": None, "propContainer": None, "propDevice": None,
        "propHeatSource": None, "propCoolingSource": None, "propPortal": None,
        "propMoveable": {"isMovable": True}, "propElectricalConnection": None, "propLife": None,
        "contents": {},
    }  # fmt: skip
    if temp is not None:
        node["propMaterial"] = {
            "substanceName": name,
            "temperatureC": temp,
            "stateOfMatter": "solid",
        }
    node.update(props)
    return node


class FakeProcess:
    def __init__(self, *, hangs: bool = False) -> None:
        self.hangs = hangs
        self.killed = False
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        if self.hangs and not self.killed:
            raise subprocess.TimeoutExpired("java", timeout or 0)
        self.returncode = self.returncode if self.returncode is not None else 0
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class FakeGateway:
    def __init__(self, process: FakeProcess) -> None:
        self.java_process = process


class FakeScienceWorld:
    def __init__(
        self, *, noise: float = 0.0, hangs: bool = False, terminate_after: int | None = None
    ) -> None:
        self.noise = noise
        self.terminate_after = terminate_after
        self._gateway = FakeGateway(FakeProcess(hangs=hangs))
        self.closed = False
        self.loaded: tuple[str, int, str] | None = None

    # -- world --------------------------------------------------------------------
    def _build(self) -> None:
        self.moves = 0
        self.first_tick_done = False
        self.door_open = False
        self.instance_offset = self.noise * (next(_counter) % 7)
        hallway = _obj(
            "hallway", 2, propContainer={"isContainer": "true", "isOpen": True, "isClosable": False}
        )
        kitchen = _obj(
            "kitchen", 3, propContainer={"isContainer": "true", "isOpen": True, "isClosable": False}
        )
        agent = _obj("agent", 4)
        agent["contents"]["inventory-5"] = _obj("inventory", 5)
        hallway["contents"]["agent-4"] = agent
        stove = _obj("stove", 6, temp=20.0, propDevice={"isActivable": True, "isActivated": False})
        cup = _obj("cup", 7, temp=20.0)
        cup["contents"]["salt-8"] = _obj("sodium chloride", 8, temp=20.0)
        cup["contents"]["water-9"] = _obj("water", 9, temp=20.0)
        kitchen["contents"]["stove-6"] = stove
        kitchen["contents"]["cup-7"] = cup
        hallway["contents"]["air-10"] = _obj("air", 10, temp=20.0)
        self.tree = _obj("universe", 1)
        self.tree["contents"] = {"hallway-2": hallway, "kitchen-3": kitchen}
        self.next_uuid = 100

    def _walk(self, node: dict[str, Any]) -> Any:
        yield node
        for child in node["contents"].values():
            yield from self._walk(child)

    def _find(self, name: str) -> dict[str, Any]:
        return next(n for n in self._walk(self.tree) if n["name"] == name)

    def _tick(self, n: int = 1) -> None:
        for _ in range(n):
            if not self.first_tick_done:
                self.first_tick_done = True
                self.tree["contents"]["kitchen-3"]["contents"][f"water-{self.next_uuid}"] = _obj(
                    "water", self.next_uuid, temp=15.0
                )
                self.next_uuid += 1
            for node in self._walk(self.tree):
                mat = node["propMaterial"]
                if mat is not None:
                    heat = (
                        2.0
                        if node["name"] == "stove" and node["propDevice"]["isActivated"]
                        else 0.0
                    )
                    mat["temperatureC"] = round(
                        mat["temperatureC"] + 0.5 + heat + self.instance_offset, 6
                    )

    # -- API --------------------------------------------------------------------------
    def load(
        self,
        task_name: str,
        variation_idx: int = 0,
        simplification_str: str = "",
        generate_gold_path: bool = False,
    ) -> None:
        self.loaded = (task_name, variation_idx, simplification_str)
        self._build()

    def reset(self) -> tuple[str, dict[str, Any]]:
        self._build()
        obs, _, _, info = self.step("look around")
        return obs, info

    def step(self, input_str: str) -> tuple[str, int, bool, dict[str, Any]]:
        a = input_str.strip()
        if a == "look around":
            obs = self.look()
        elif a == "wait1":
            self._tick()
            self.moves += 2
            obs = "You decide to wait for 1 iterations."
        elif a in ("open door to kitchen", "close door to kitchen"):
            self.door_open = a.startswith("open")
            self._tick()
            self.moves += 1
            obs = f"The door is now {'open' if self.door_open else 'closed'}."
        elif a in ("activate stove", "deactivate stove"):
            self._find("stove")["propDevice"]["isActivated"] = a.startswith("activate")
            self._tick()
            self.moves += 1
            obs = f"The stove is now {'activated' if a.startswith('activate') else 'deactivated'}."
        elif a == "mix cup":
            cup = self._find("cup")
            cup["contents"] = {
                f"salt water-{self.next_uuid}": _obj("salt water", self.next_uuid, temp=20.0)
            }
            self.next_uuid += 1
            self._tick()
            self.moves += 1
            obs = "Sodium chloride and water mix to produce salt water."
        elif a == "pick up thing":
            obs = (
                "Ambiguous request: Please enter the number for the action you intended:"
                "\n0: a\n1: b"
            )
        else:
            obs = "No known action matches that input."
        done = self.terminate_after is not None and self.moves >= self.terminate_after
        return (
            obs,
            0,
            done,
            {"moves": self.moves, "score": 0, "taskName": self.loaded[0] if self.loaded else None},
        )

    def look(self) -> str:
        state = "open" if self.door_open else "closed"
        return (
            "This room is called the hallway. In it, you see: \n"
            "\tthe agent\n\ta substance called air\n"
            f"You also see:\n\tA door to the kitchen (that is {state})\n"
        )

    def inventory(self) -> str:
        return "In your inventory, you see:\n\tnothing\n"

    def getObjectTree(self) -> dict[str, Any]:  # noqa: N802
        return copy.deepcopy(self.tree)

    def get_valid_action_object_combinations(self) -> list[str]:
        return ["activate stove", "look around", "mix cup", "open door to kitchen", "wait1"]

    def get_num_moves(self) -> int:
        return self.moves

    def get_gold_action_sequence(self) -> list[str]:
        return ["activate stove", "mix cup"]

    def close(self) -> None:
        self.closed = True
