"""Simulator tests and counterexample searches for the certificates (O6, O7; docs/23 §4).

Every probe runs in the kitchen world of task 1-1 (variation 0, ``teleportAction``):
one sodium-chloride object, no plants or seeds anywhere in the universe (checked and
recorded by each probe). Counterexample searches are bounded (object-local 1-step
candidates plus a few long physical processes), so a clean search discharges O7 only as
"no counterexample found within the stated budget", never as proof.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise
from typing import Any

from adnn.scienceworld.canonical import CanonicalState, capture_state
from adnn.scienceworld.certificate_verification import Obligation, obligation
from adnn.scienceworld.env import Backend, ScienceWorldSession
from adnn.scienceworld.expanded_search import candidate_pool, select_candidates
from adnn.scienceworld.provenance import RuntimeConfig
from adnn.scienceworld.provisional import IDLE_ACTION, PILOT_FAMILIES
from adnn.scienceworld.replay import run_recipe

KITCHEN = PILOT_FAMILIES[0]
FILL_POT = (
    "open cupboard", "move metal pot to sink", "activate sink", "deactivate sink",
    "move metal pot to table",
)  # fmt: skip
SALT_IN_POT = (*FILL_POT, "open glass jar", "move sodium chloride to metal pot")
FLAMMABLE_MOVABLE = ("painting", "soap", "tin cup", "wood cup")


class _Probe:
    def __init__(self, session: ScienceWorldSession) -> None:
        self.s = session

    def at(self, *history: str) -> CanonicalState:
        run_recipe(self.s, KITCHEN.base_recipe().extend(*history), strict=True)
        return capture_state(self.s).canonical

    def do(self, *actions: str) -> list[str]:
        out = []
        for a in actions:
            out.append(self.s.step(a).status)
        return out

    def idle(self, n: int, every: int = 1) -> list[CanonicalState]:
        states = []
        for i in range(1, n + 1):
            self.s.step(IDLE_ACTION)
            if i % every == 0:
                states.append(capture_state(self.s).canonical)
        return states

    def state(self) -> CanonicalState:
        return capture_state(self.s).canonical

    def local_candidates(
        self, before: CanonicalState, after: CanonicalState, ids: tuple[str, ...], n: int
    ) -> list[str]:
        local, _ = candidate_pool(self.s.valid_action_templates(), before, after, ids)
        return select_candidates(local, [], n, seed=0)


def _uuid(state: CanonicalState, name: str, parent: str | None = None) -> str | None:
    hits = [
        u
        for u, r in state.objects.items()
        if r.get("name") == name
        and not r.get("isDeleted")
        and (
            parent is None or str(state.objects.get(str(r.get("parent")), {}).get("name")) == parent
        )
    ]
    return hits[0] if len(hits) == 1 else None


def _salt(state: CanonicalState) -> list[str]:
    return sorted(
        u
        for u, r in state.objects.items()
        if not r.get("isDeleted") and r.get("propMaterial.substanceName") == "sodium chloride"
    )


def world_facts(state: CanonicalState) -> dict[str, Any]:
    names = [str(r.get("name")) for r in state.objects.values() if not r.get("isDeleted")]
    return {
        "sodium_chloride_objects": len(_salt(state)),
        "living_non_bee": sorted(
            {
                str(r.get("name"))
                for r in state.objects.values()
                if r.get("propLife.lifeformType") and not str(r.get("name")).startswith("bee")
            }
        ),
        "seed_like": sorted({n for n in names if "seed" in n}),
        "apples": names.count("apple"),
    }


def _ids(p: _Probe, action: str) -> tuple[str, ...]:
    return next((t.obj_ids for t in p.s.valid_action_templates() if t.action == action), ())


def probe_burn(p: _Probe, budget: int) -> tuple[list[Obligation], dict[str, Any]]:
    s0 = p.at()
    chair = _uuid(s0, "chair", "kitchen")
    if chair is None:
        raise RuntimeError("kitchen chair not found exactly once")
    log: dict[str, Any] = {"world": world_facts(s0), "object": "chair", "uuid": chair}
    ids = _ids(p, "use lighter on chair")
    status = p.do("use lighter on chair")
    s1 = p.state()
    series = [s1, *p.idle(12)]
    hc = [s.objects.get(chair, {}).get("propMaterial.hasCombusted") for s in series]
    ticks = [s.objects.get(chair, {}).get("propMaterial.combustionTicks") for s in series]
    t1 = (
        status == ["accepted"]
        and s0.objects[chair].get("propMaterial.hasCombusted") is False
        and all(v is True for v in hc if v is not None)
        and all(a >= b for a, b in pairwise(ticks) if a is not None and b is not None)
    )
    log["T1_ignite_and_wait"] = {"status": status, "hasCombusted": hc, "combustionTicks": ticks}

    # T2: put a burning movable object out with water; hasCombusted must stay true
    t2: bool | None = None
    for obj in FLAMMABLE_MOVABLE:
        base = p.at(*FILL_POT)
        u = _uuid(base, obj, "kitchen")
        if u is None or f"use lighter on {obj}" not in {
            t.action for t in p.s.valid_action_templates()
        }:
            continue
        p.do(f"use lighter on {obj}")
        lit = p.state()
        if lit.objects.get(u, {}).get("propMaterial.isCombusting") is not True:
            continue
        st = p.do(f"move {obj} to metal pot")
        after = [p.state(), *p.idle(5)]
        flags = [(s.objects.get(u, {}).get("propMaterial.isCombusting"),
                  s.objects.get(u, {}).get("propMaterial.hasCombusted"))
          for s in after]  # fmt: skip
        out = flags[0][0] is False
        t2 = out and all(h is True for _, h in flags if h is not None)
        log["T2_extinguish"] = {"object": obj, "move_status": st, "extinguished": out,
                                "isCombusting_hasCombusted": flags}  # fmt: skip
        if out:
            break
    if t2 is None:
        log["T2_extinguish"] = "no flammable movable object could be ignited and extinguished"

    # T3: bounded counterexample search from the ignited state
    p.at()
    p.do("use lighter on chair")
    s1 = p.state()
    cands = p.local_candidates(s0, s1, ids, budget)
    violations = []
    for a in cands:
        p.at()
        p.do("use lighter on chair")
        st = p.do(a)
        s2 = p.state()
        r = s2.objects.get(chair)
        if (
            r is not None
            and not r.get("isDeleted")
            and (
                r.get("propMaterial.hasCombusted") is not True
                or r.get("propMaterial.combustionTicks", 0)
                > s1.objects[chair]["propMaterial.combustionTicks"]
            )
        ):
            violations.append({"action": a, "status": st})
    log["T3_search"] = {"candidates": cands, "violations": violations}
    obs = [
        obligation("O6", "simulator: ignition sets hasCombusted, it persists for 12 ticks, "
                   "combustionTicks never increases; extinguishing keeps hasCombusted",
                   (t1 and t2) if t2 is not None else (None if t1 else False),
                   {"T1": t1, "T2": t2}, counterexample=True),
        obligation("O7", f"bounded counterexample search ({len(cands)} object-local 1-step "
                   "actions after ignition) finds no violation", not violations,
                   violations, counterexample=True),
    ]  # fmt: skip
    return obs, log


def probe_mix_salt(p: _Probe, budget: int) -> tuple[list[Obligation], dict[str, Any]]:
    s0 = p.at(*SALT_IN_POT)
    log: dict[str, Any] = {"world": world_facts(s0), "salt_before": _salt(s0)}
    ids = _ids(p, "mix metal pot")
    st = p.do("mix metal pot")
    s1 = p.state()
    names_in_pot = sorted(
        str(r.get("name")) for r in s1.objects.values()
        if not r.get("isDeleted")
        and str(s1.objects.get(str(r.get("parent")), {}).get("name")) == "metal pot"
        and not str(r.get("name")).startswith("terminal")
    )  # fmt: skip
    t1 = (
        st == ["accepted"]
        and len(_salt(s0)) == 1
        and not _salt(s1)
        and "salt water" in names_in_pot
    )
    log["T1_mix"] = {"status": st, "pot_contents_after": names_in_pot, "salt_after": _salt(s1)}
    processes = {
        "heat_on_stove": ("move metal pot to stove", "activate stove"),
        "cool_in_freezer": ("open freezer", "move metal pot to freezer", "close freezer"),
    }
    proc_log = {}
    reappeared = []
    for name, acts in processes.items():
        p.at(*SALT_IN_POT)
        p.do("mix metal pot")
        sts = p.do(*acts)
        states = p.idle(40, every=5)
        seen = sorted({str(r.get("name")) for s in states for r in s.objects.values()
                       if s.objects and str(r.get("name", "")).find("salt") >= 0})  # fmt: skip
        found = any(_salt(s) for s in states)
        proc_log[name] = {"statuses": sts, "ticks": 40, "salt_like_names_seen": seen,
                          "sodium_chloride_found": found}  # fmt: skip
        if found:
            reappeared.append(name)
    log["T2_processes"] = proc_log
    p.at(*SALT_IN_POT)
    p.do("mix metal pot")
    cands = p.local_candidates(s0, s1, ids, budget)
    violations = []
    for a in cands:
        p.at(*SALT_IN_POT)
        p.do("mix metal pot")
        st2 = p.do(a)
        if _salt(p.state()):
            violations.append({"action": a, "status": st2})
    log["T3_search"] = {"candidates": cands, "violations": violations}
    obs = [
        obligation("O6", "simulator: mixing consumes the only sodium chloride and creates salt "
                   "water; 40 ticks of heating or freezing never recreate sodium chloride",
                   t1 and not reappeared, {"T1": t1, "reappeared_in": reappeared},
                   counterexample=bool(reappeared)),
        obligation("O7", f"bounded counterexample search ({len(cands)} object-local 1-step "
                   "actions after mixing) finds no sodium chloride", not violations, violations,
                   counterexample=True),
    ]  # fmt: skip
    return obs, log


def probe_eat(p: _Probe, budget: int) -> tuple[list[Obligation], dict[str, Any]]:
    s0 = p.at()
    apple = _uuid(s0, "apple")
    if apple is None:
        raise RuntimeError("apple not found exactly once")
    log: dict[str, Any] = {"world": world_facts(s0), "uuid": apple}
    ids = _ids(p, "eat apple")
    st = p.do("eat apple")
    s1 = p.state()
    later = p.idle(20, every=5)
    gone = [apple not in s.objects or s.objects[apple].get("isDeleted") for s in (s1, *later)]
    new_apples = [world_facts(s)["apples"] for s in (s1, *later)]
    t1 = st == ["accepted"] and all(gone) and all(n == 0 for n in new_apples)
    log["T1_eat_and_wait"] = {"status": st, "uuid_absent": gone, "apples_in_world": new_apples}
    cands = p.local_candidates(s0, s1, ids, budget)
    back = []
    for a in cands:
        p.at()
        p.do("eat apple")
        st2 = p.do(a)
        s2 = p.state()
        if (apple in s2.objects and not s2.objects[apple].get("isDeleted")) or world_facts(s2)[
            "apples"
        ]:
            back.append({"action": a, "status": st2})
    log["T3_search"] = {"candidates": cands, "returns": back}
    obs = [
        obligation("O6", "simulator: the eaten uuid and any apple stay absent for 20 ticks",
                   t1, {"T1": t1}, counterexample=True),
        obligation("O7", f"bounded search ({len(cands)} object-local 1-step actions) never "
                   "brings the uuid or an apple back", not back, back, counterexample=True),
    ]  # fmt: skip
    return obs, log


def run_probes(
    *,
    budget: int = 25,
    config: RuntimeConfig | None = None,
    backend_factory: Callable[[], Backend] | None = None,
) -> dict[str, tuple[list[Obligation], dict[str, Any]]]:
    with ScienceWorldSession(config, backend_factory=backend_factory) as session:
        p = _Probe(session)
        return {
            "C-BURN": probe_burn(p, budget),
            "C-MIX-SALT": probe_mix_salt(p, budget),
            "C-EAT": probe_eat(p, budget),
        }
