"""Phase 4H certificate audit: deeper source scans and simulator experiments (docs/24 §4).

Source-relative, not proof (ADR-0004 C2). Three additions over Phase 4G:

1. **Reattachment (O2 for consumption).** ``ActionEat`` only detaches the food
   (``removeAndResetContainer``); it is not deleted. Agent referents are collected by
   walking the object tree (``InputParser.collectAccessibleObjects``) and ticks recurse
   from the universe root, so a detached object can return only through a runtime
   ``addObject(x)`` whose ``x`` is a reference obtained outside the tree.
   :func:`add_object_sites` classifies every runtime ``addObject`` call: mechanically
   when the argument is freshly constructed or the receiver itself, otherwise from a
   reviewed table with a justification. Any unreviewed site leaves O2 failed.
2. **Plant closure (O8 for a world-conditional consumption claim).** Fruit is
   constructed at runtime only by ``PlantReproduction.createFruit``, which is called only
   from ``Flower.tick`` (and a debug ``main``); flowers and pollen require a live
   ``Plant``; plants are constructed at runtime only by ``createFruit``/``createSeed``,
   and ``createSeed`` only at task construction. :func:`plant_closure` checks this.
3. **Combustion pathways.** Every write of ``isCombusting``/``hasCombusted`` and every
   caller of ``putOutFire`` (water in the same container, or inside the object).

The world-conditional claim ``C-EAT/structural-plantless`` is reported here only. It is
NOT registered with the admission rule (``sw-admission-2`` is unchanged; ADR-0005 R6).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from adnn.scienceworld.canonical import CanonicalState, capture_state
from adnn.scienceworld.certificate_verification import (
    CONSTRUCTION_DIRS,
    Obligation,
    _code,
    _rel,
    constructor_sites,
    method_callers,
    obligation,
    occurrences,
    scala_files,
    scopes,
)
from adnn.scienceworld.certificates import (
    MET,
    NOT_APPLICABLE,
    NOT_MET,
    CertificateCheck,
    check_burn,
    check_mix_salt,
)
from adnn.scienceworld.env import Backend, ScienceWorldSession
from adnn.scienceworld.expanded_search import candidate_pool, select_candidates
from adnn.scienceworld.provenance import RuntimeConfig
from adnn.scienceworld.provisional import IDLE_ACTION, FamilySpec
from adnn.scienceworld.replay import run_recipe

AUDIT_VERSION = "sw-cert-audit-4h-1"
PLANTLESS_ID = "C-EAT/structural-plantless"
FRUIT_CLASSES = (
    "Apple", "Avocado", "Banana", "Cherry", "Lemon", "Orange", "Peach", "Apricot",
    "Grapefruit", "Pear",
)  # fmt: skip
PLANT_LIKE = ("tree", "plant", "flower", "pollen", "seed")
ALLOWED_CATEGORIES = (
    "fresh", "self_move", "constructor_body", "agent", "referent", "tree_contents",
    "pass_through",
)  # fmt: skip
# Reviewed runtime addObject sites in the pinned source (e8216d6). Each argument is a
# reference obtained from the tree, a parsed referent, the agent or a pass-through.
REVIEWED_SITES: dict[str, tuple[str, str]] = {
    "actions/ActionMoveObject.scala:32": ("referent", "objToMove = assignments(\"obj\")"),
    "actions/ActionMoveObject.scala:334": ("tree_contents", "contents of a referent"),
    "actions/ActionMoveObject.scala:346": ("referent", "objToMove = assignments(\"obj\")"),
    "actions/ActionMoveObject.scala:491": ("tree_contents", "liquids inside a referent"),
    "actions/ActionMoveToLocation.scala:39": ("agent", "the agent moves"),
    "actions/ActionMoveToLocation.scala:55": ("agent", "the agent moves"),
    "actions/ActionTeleport.scala:33": ("agent", "the agent moves"),
    "objects/environmentoutside/Ground.scala:20": ("tree_contents", "contents of the ground"),
    "objects/portal/Portal.scala:206": ("tree_contents", "liquids in the drain's container"),
    "objects/livingthing/animals/Bee.scala:150": ("tree_contents", "pollen in the bee's location"),
    "objects/misc/InclinedPlane.scala:77": ("pass_through", "override forwarding its argument"),
    "struct/EnvObject.scala:47": ("constructor_body", "terminal built by the constructor"),
    "struct/EnvObject.scala:48": ("constructor_body", "terminal built by the constructor"),
    "struct/EnvObject.scala:291": ("tree_contents", "contents of this object"),
    "runtime/AgentInterface.scala:29": ("constructor_body", "task objects at initialisation"),
    "processes/lifestage/AdultForeverLifeStage.scala:41": ("tree_contents", "animal contents"),
    "processes/lifestage/AnimalLifeStage.scala:142": ("tree_contents", "dying animal's contents"),
    "processes/lifestage/BirdLifeStage.scala:183": ("tree_contents", "dying animal's contents"),
    "processes/lifestage/ButterflyLifeStage.scala:185": ("tree_contents", "animal contents"),
    "processes/lifestage/FrogLifeStage.scala:145": ("tree_contents", "dying animal's contents"),
    "processes/lifestage/PlantLifeStage.scala:327": ("tree_contents", "dying plant's contents"),
    "processes/lifestage/TortoiseLifeStage.scala:182": ("tree_contents", "dying animal's contents"),
}  # fmt: skip
_ADD = re.compile(r"\.addObject\(\s*(.*)\)\s*$")
_FRESH_ASSIGN = r"\b(?:val|var)\s+{0}\b\s*=\s*(?:new\b|\w+\.(?:create\w*|mk\w*)\()"


# -- static audits ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AddSite:
    site: str
    text: str
    in_def: bool
    category: str
    justification: str


def add_object_sites(root: Path) -> list[AddSite]:
    """Classify every ``addObject`` call outside world/task construction directories."""
    out = []
    for p in scala_files(root):
        rel = _rel(root, p)
        if rel.startswith(CONSTRUCTION_DIRS):
            continue
        lines = p.read_text("utf-8", errors="replace").splitlines()
        sc = scopes("\n".join(lines))
        for i, line in enumerate(lines):
            code = _code(line).strip()
            m = _ADD.search(code)
            if not m or code.startswith(("def ", "override def ")):
                continue
            arg = m.group(1).strip()
            site = f"{rel}:{i + 1}"
            ident = re.match(r"^(\w+)(?:\.get)?$", arg)
            window = "\n".join(lines[max(0, i - 15) : i])
            if arg.startswith("new ") or re.match(r"^\w+\.(?:create|mk)\w*\(", arg):
                cat, why = "fresh", "argument constructed in place"
            elif ident and re.search(_FRESH_ASSIGN.format(ident.group(1)), window):
                cat, why = "fresh", f"{ident.group(1)} assigned from a constructor/factory above"
            elif arg == "this":
                cat, why = "self_move", "the receiver moves itself"
            elif site in REVIEWED_SITES:
                cat, why = REVIEWED_SITES[site]
            else:
                cat, why = "unreviewed", "argument provenance not established"
            out.append(AddSite(site, code, sc[i].in_def, cat, why))
    return out


def reattachment_obligation(root: Path) -> Obligation:
    sites = add_object_sites(root)
    bad = [s for s in sites if s.category not in ALLOWED_CATEGORIES]
    stale = sorted(set(REVIEWED_SITES) - {s.site for s in sites})
    counts: dict[str, int] = {}
    for s in sites:
        counts[s.category] = counts.get(s.category, 0) + 1
    return obligation(
        "O2", "a detached object is never re-attached: every runtime addObject argument is "
        "fresh, the receiver, the agent, a parsed referent, tree contents or a pass-through",
        not bad and not stale,
        {"n_sites": len(sites), "categories": counts,
         "unreviewed": [asdict(s) for s in bad], "stale_reviews": stale,
         "referents_are_tree_walks": "input/InputParser.scala:742 collectAccessibleObjects",
         "ticks_are_tree_walks": "struct/EnvObject.scala:543 containedObj.tick()",
         "eat_detaches_only": "actions/ActionEat.scala removeAndResetContainer()"},
    )  # fmt: skip


def _class_parents(root: Path) -> dict[str, str]:
    rx = re.compile(r"\bclass\s+(\w+)\b[^{\n]*?\bextends\s+(\w+)")
    out = {}
    for p in scala_files(root):
        for m in rx.finditer(p.read_text("utf-8", errors="replace")):
            out[m.group(1)] = m.group(2)
    return out


def descendants(root: Path, base: str) -> list[str]:
    parents = _class_parents(root)

    def is_sub(c: str) -> bool:
        seen = set()
        while c in parents and c not in seen:
            seen.add(c)
            c = parents[c]
            if c == base:
                return True
        return False

    return sorted(c for c in parents if is_sub(c))


def fruit_names(root: Path) -> dict[str, str]:
    """Default display name of each audited fruit class (``this.name = "..."``)."""
    out = {}
    for p in scala_files(root):
        text = p.read_text("utf-8", errors="replace")
        for cls in FRUIT_CLASSES:
            m = re.search(rf"\bclass\s+{cls}\b[^{{]*\{{(.*?)\n\}}", text, re.S)
            if m:
                n = re.search(r'this\.name\s*=\s*"([^"]+)"', m.group(1))
                if n:
                    out[n.group(1)] = cls
    return out


def _runtime_methods(sites: dict[str, list[str]]) -> set[str]:
    return {m.group(1) for s in sites["runtime"] for m in [re.search(r"\(in (\w+),", s)] if m}


def plant_closure(root: Path) -> Obligation:
    fruit = {c: constructor_sites(root, c) for c in FRUIT_CLASSES}
    plants = {c: constructor_sites(root, c) for c in descendants(root, "Plant")}
    flower, pollen = constructor_sites(root, "Flower"), constructor_sites(root, "Pollen")
    create_fruit = method_callers(root, "createFruit")
    create_seed = method_callers(root, "createSeed")
    checks = {
        "fruit_runtime_only_in_createFruit": all(
            _runtime_methods(s) <= {"createFruit"} and not s["unresolved"] for s in fruit.values()
        ),
        "createFruit_called_from_flower_tick_or_debug_main": all(
            c.startswith("objects/livingthing/plant/Plant.scala")
            or c.startswith("tasks/specifictasks/TaskMendelianGenetics2.scala")
            for c in create_fruit
        ),
        "plants_runtime_only_in_createFruit_or_createSeed": all(
            _runtime_methods(s) <= {"createFruit", "createSeed"} and not s["unresolved"]
            for s in plants.values()
        ),
        "createSeed_only_at_task_construction": all(
            c.startswith(CONSTRUCTION_DIRS) for c in create_seed
        ),
        "flower_runtime_only_in_plant_lifestage": _runtime_methods(flower) <= {"tick"}
        and all("PlantLifeStage" in s for s in flower["runtime"]),
        "pollen_needs_a_plant": all(
            "objects/livingthing/plant/Plant.scala" in s for s in pollen["runtime"]
        ),
    }
    return obligation(
        "O8", "in a world with no plant, flower, pollen or seed, no fruit and no plant is ever "
        "constructed at runtime (createFruit needs a flower; flowers need a live plant)",
        all(checks.values()),
        {"checks": checks, "fruit_sites": fruit, "plant_classes": sorted(plants),
         "plant_runtime_sites": {c: s["runtime"] for c, s in plants.items() if s["runtime"]},
         "flower_sites": flower, "pollen_sites": pollen, "createFruit_callers": create_fruit,
         "createSeed_callers": create_seed,
         "debug_main_note": "TaskMendelianGenetics2.scala createFruit call is inside "
                            "`def main(args)`, never invoked by the simulator"},
        counterexample=True,
    )  # fmt: skip


def combustion_pathways(root: Path) -> dict[str, Any]:
    return {
        **{
            f: [o.to_dict() for o in occurrences(root, f) if o.kind == "write"]
            for f in ("isCombusting", "hasCombusted")
        },
        "putOutFire_callers": method_callers(root, "putOutFire"),
        "extinguish_condition": "processes/Combustion.scala: liquid water among the burning "
        "object's contents or its container's contents puts the fire out (putOutFire)",
        "burn_out": "processes/Combustion.scala: combustionTicks == 0 -> isCombusting=false, "
        "new Ash in the container, obj.delete(expelContents = true)",
    }  # fmt: skip


# -- the world-conditional consumption checker -----------------------------------------------
def _live(state: CanonicalState) -> dict[str, dict[str, Any]]:
    return {u: dict(r) for u, r in state.objects.items() if not r.get("isDeleted")}


def plant_like(state: CanonicalState) -> list[str]:
    return sorted(
        f"{r['name']} ({u})"
        for u, r in _live(state).items()
        if any(k in str(r["name"]) for k in PLANT_LIKE)
        or "plant" in str(r.get("propLife.lifeformType") or "")
    )


def check_eat_plantless(
    s0: CanonicalState,
    target: str,
    s1: CanonicalState,
    target_ids: Sequence[str],
    names: dict[str, str],
) -> CertificateCheck:
    """Precondition of ``C-EAT/structural-plantless`` (report only; not in admission)."""
    if not target.startswith("eat "):
        return CertificateCheck(PLANTLESS_ID, NOT_APPLICABLE, ("target is not an eat action",))
    gone = [u for u in target_ids if u in s0.objects and u not in _live(s1)]
    if not gone:
        return CertificateCheck(PLANTLESS_ID, NOT_MET, ("eaten object still in the tree",))
    name = s0.objects[gone[0]]["name"]
    if name not in names:
        return CertificateCheck(
            PLANTLESS_ID, NOT_MET, (f"{name!r} is not an audited fruit class",), tuple(gone)
        )
    same = sorted(u for u, r in _live(s1).items() if r["name"] == name)
    if same:
        return CertificateCheck(
            PLANTLESS_ID, NOT_MET, (f"another {name} exists in S1",), tuple(same)
        )
    plants = plant_like(s1)
    if plants:
        return CertificateCheck(PLANTLESS_ID, NOT_MET, ("plant-like objects exist",), tuple(plants))
    return CertificateCheck(
        PLANTLESS_ID, MET, (f"last {name} eaten; no plant, flower, pollen or seed",), tuple(gone),
        ("object-tree completeness is assumed (canonical state is incomplete)",),
    )  # fmt: skip


# -- simulator experiments -------------------------------------------------------------------
class Lab:
    def __init__(self, session: ScienceWorldSession) -> None:
        self.s = session

    def at(self, family: FamilySpec, *history: str) -> CanonicalState:
        run_recipe(self.s, family.base_recipe(step_limit=400).extend(*history), strict=True)
        return capture_state(self.s).canonical

    def do(self, action: str) -> str:
        return self.s.step(action).status

    def state(self) -> CanonicalState:
        return capture_state(self.s).canonical

    def ids(self, action: str) -> tuple[str, ...]:
        return next(t.obj_ids for t in self.s.valid_action_templates() if t.action == action)

    def idle(self, n: int) -> None:
        for _ in range(n):
            self.s.step(IDLE_ACTION)

    def candidates(
        self, s0: CanonicalState, s1: CanonicalState, ids: tuple[str, ...], n: int
    ) -> list[str]:
        local, _ = candidate_pool(self.s.valid_action_templates(), s0, s1, ids)
        return select_candidates(local, [], n, seed=0)


def _one(state: CanonicalState, name: str, parent: str) -> str:
    live = _live(state)
    hits = [
        u
        for u, r in live.items()
        if r["name"] == name and live.get(str(r.get("parent")), {}).get("name") == parent
    ]
    if len(hits) != 1:
        raise RuntimeError(f"{name} in {parent}: {len(hits)} matches")
    return hits[0]


def _flags(state: CanonicalState, uuid: str) -> dict[str, Any] | None:
    r = _live(state).get(uuid)
    if r is None:
        return None
    return {
        k: r.get(f"propMaterial.{k}") for k in ("isCombusting", "hasCombusted", "combustionTicks")
    }


def burn_experiments(lab: Lab, kitchen: FamilySpec, fill_pot: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, extinguish in (("pour_into_chair", "pour metal pot into chair"),
                              ("pour_into_kitchen", "pour metal pot into kitchen")):  # fmt: skip
        s0 = lab.at(kitchen, *fill_pot)
        chair = _one(s0, "chair", "kitchen")
        status = [lab.do("use lighter on chair")]
        lit = _flags(lab.state(), chair)
        status.append(lab.do(extinguish))
        after = _flags(lab.state(), chair)
        lab.idle(3)
        later = _flags(lab.state(), chair)
        status.append(lab.do("use lighter on chair"))
        relit = _flags(lab.state(), chair)
        out[label] = {"statuses": status, "lit": lit, "after_extinguish": after,
                      "three_ticks_later": later, "relit": relit,
                      "extinguished": bool(after and after["isCombusting"] is False
                                           and after["hasCombusted"] is True)}  # fmt: skip
    s0 = lab.at(kitchen)
    chair = _one(s0, "chair", "kitchen")
    lab.do("use lighter on chair")
    trace, gone_at, ash = [], None, None
    for tick in range(10, 160, 10):
        lab.idle(10)
        st = lab.state()
        f = _flags(st, chair)
        trace.append({"tick": tick, "flags": f})
        if f is None:
            gone_at = tick
            ash = sorted(r["name"] for r in _live(st).values() if r["name"] == "ash")
            break
    ticks = [t["flags"]["combustionTicks"] for t in trace if t["flags"]]
    out["burn_out"] = {
        "trace": trace, "deleted_by_tick": gone_at, "ash_objects": ash,
        "hasCombusted_true_while_present": all(
            t["flags"]["hasCombusted"] for t in trace if t["flags"]
        ),
        "combustionTicks_non_increasing": all(a >= b for a, b in pairwise(ticks)),
    }  # fmt: skip
    s0 = lab.at(kitchen, *fill_pot)
    painting = _one(s0, "painting", "kitchen")
    status = [lab.do("use lighter on painting"), lab.do("move painting to metal pot")]
    out["painting_into_pot"] = {"statuses": status, "after": _flags(lab.state(), painting)}
    s1 = lab.at(kitchen, *fill_pot, "use lighter on chair")
    out["check_burn_after_chair_ignition"] = check_burn(s0, "use lighter on chair", s1).to_dict()
    return out


def salt_experiments(
    lab: Lab, two_salt: FamilySpec, single: FamilySpec, salt_in_pot: tuple[str, ...]
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, fam in (("two_salt_world", two_salt), ("single_salt_world", single)):
        s0 = lab.at(fam, *salt_in_pot)
        status = lab.do("mix metal pot")
        s1 = lab.state()
        salts = sorted(
            r.get("path") for r in _live(s1).values()
            if r.get("propMaterial.substanceName") == "sodium chloride"
        )  # fmt: skip
        out[label] = {"status": status, "salt_after_mix": salts,
                      "check": check_mix_salt(s0, "mix metal pot", s1).to_dict()}  # fmt: skip
    return out


def eat_experiments(
    lab: Lab, kitchen: FamilySpec, plant_world: FamilySpec, names: dict[str, str], budget: int
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, fam, food in (("plantless_world", kitchen, "banana"),
                             ("plant_world", plant_world, "apple")):  # fmt: skip
        s0 = lab.at(fam)
        action = f"eat {food}"
        ids = lab.ids(action)
        lab.do(action)
        s1 = lab.state()
        row: dict[str, Any] = {
            "check": check_eat_plantless(s0, action, s1, ids, names).to_dict(),
            "plant_like_in_s1": plant_like(s1)[:12],
        }
        if label == "plantless_world":
            seen = []
            for _ in range(10):
                lab.idle(10)
                st = lab.state()
                seen.append(sorted(u for u, r in _live(st).items() if r["name"] == food))
            row["same_name_objects_over_100_ticks"] = seen
            cands = lab.candidates(s0, s1, ids, budget)
            returns = []
            for a in cands:
                lab.at(fam, action)
                lab.do(a)
                st = lab.state()
                if any(r["name"] == food for r in _live(st).values()) or ids[0] in _live(st):
                    returns.append(a)
            row["bounded_search"] = {"candidates": cands, "returns": returns}
        out[label] = row
    return out


def run_experiments(
    *,
    families: dict[str, FamilySpec],
    histories: dict[str, tuple[str, ...]],
    names: dict[str, str],
    budget: int = 25,
    config: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
) -> dict[str, Any]:
    with ScienceWorldSession(config, step_limit=400, backend_factory=backend_factory) as s:
        lab = Lab(s)
        return {
            "burn": burn_experiments(lab, families["kitchen"], histories["fill_pot"]),
            "salt": salt_experiments(
                lab, families["two_salt"], families["kitchen"], histories["salt_in_pot"]
            ),
            "eat": eat_experiments(
                lab, families["kitchen"], families["plant_world"], names, budget
            ),
        }
