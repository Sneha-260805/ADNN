"""Phase 5G Protocol B dry run (ADR-0008, docs/33). Run from the repository root.

    python scripts/dataset/phase5g_protocol_b_dryrun.py

Deterministic and bounded. Writes NO dataset records: states are drawn from the existing
generators (16 legacy families; the 3 link families with background removed), labelled by
the oracle, rendered in memory, and only summary statistics are written to
``results/phase5g/dryrun.json`` (git-ignored).

Protocol B as proposed (docs/32): at most 4 surface variants per coarse scenario, each
rendered in the 3 render styles, so at most 12 records per coarse scenario. A minimal pair
is admitted atomically (both members or neither). Gold follows the established rules:
legacy = definitive oracle, judged action ok, no pending timers, not OQ-21-sensitive (the
pilot rule); link = ``share_link_family.gold_gate`` plus a definitive, unchanged OQ-21
alternative (``share_link_production``). ADR-0006 D5 (at most 3 records per surface-masked
template signature) is applied, and the 8% family cap is reported.
"""

from __future__ import annotations

import json
import random
import re
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adnn.dataset import pilot
from adnn.dataset import share_link_family as slf
from adnn.dataset import share_link_production as slp
from adnn.dataset.prompting_v11 import render_state_text_v11
from adnn.dataset.rendering import RENDER_STYLES, TEST_ONLY_STYLES
from adnn.dataset.schema import (
    HORIZONS,
    canonical_action_text,
    sha256_file,
    sha256_text,
    stable_json,
    write_json,
)
from adnn.feasibility.composition import template_signature
from adnn.feasibility.scaling_pilot import ALL_FAMILIES
from adnn.feasibility.scenario_diversity import (
    canonical_scenario,
    recovery_signature_id,
    scenario_id,
)
from adnn.sandbox import ToolCall, WorldState, assess_reversibility
from adnn.sandbox.restoration import has_pending_timers

OUT = Path("results/phase5g/dryrun.json")
SEED = "phase5g-dryrun"
DRAWS = 300  # per family
SURFACE_VARIANTS = 4  # per coarse scenario
CAP = SURFACE_VARIANTS * len(RENDER_STYLES)  # 12
SENSITIVITY_CAP = 3  # one surface variant x 3 styles
D5_SIGNATURE_CAP = 3
FAMILY_SHARE_CAP = 0.08
TEST_FRACTION = 0.20
SPLIT_SEARCH = 3000
LINK_CFG = slf.GenerationConfig(max_files=1, max_distractors=0)  # background removed
PRIORS = {
    "pilot_v0.1": (
        Path("data/pilot/pilot_v0.1.jsonl"),
        "f66b98baac43faf1ece408cc22e645faf22aace13ad6aac86f1f2c83f1d3fc53",
    ),
    "phase5b_scaling_pilot": (
        Path("data/scaling_pilot/records.jsonl"),
        "bfd1175fb7e12c0f0993adb3f7079d29388dcf250d35f1ac37693af0236baa5b",
    ),
}
H3 = str(max(HORIZONS))
Comps = list[dict[str, Any]]


@dataclass
class Unit:
    """One (state, action): a surface variant. Rendered into up to 3 records."""

    family: str
    kind: str  # pa / pb / s0 / s1
    pair_id: str | None
    state: WorldState
    call: ToolCall
    expected_h3: str | None
    coarse: str = ""
    strict: str = ""
    masked: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    signature: str = ""


def _struct(state: WorldState, call: ToolCall) -> dict[str, Any]:
    return {"state_struct": state.to_dict(), "action_call": call.to_dict()}


def masked_form(record: Mapping[str, Any]) -> str:
    """Coarse canonical form with every number token masked (docs/31)."""

    def m(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: m(v) for k, v in o.items()}
        if isinstance(o, list):
            return [m(v) for v in o]
        if isinstance(o, str) and re.fullmatch(r"n\d+", o):
            return "<n>"
        return o

    return sha256_text(stable_json(m(canonical_scenario(record, "coarse"))))[:16]


def _signature(call: ToolCall, a: Any) -> str:
    d = a.to_dict()
    oracle = {"exact_witness": d["exact_witness"], "approx_witness": d["approx_witness"]}
    return recovery_signature_id({"action_call": call.to_dict(), "meta": {"oracle": oracle}})


def label_legacy(u: Unit) -> str | None:
    """Fill labels; return a drop reason or None (pilot gold rule)."""
    if has_pending_timers(u.state):
        return "pending_timers"
    a = assess_reversibility(u.state, u.call, **pilot.ORACLE_CONFIG)
    if not a.action_ok:
        return "judged_action_failed"
    if not a.is_definitive:
        return "oracle_not_definitive"
    labels = a.labels_by_horizon(HORIZONS)
    alt = pilot._oq21_alternative(u.state, u.call)
    if alt is not None and alt.is_definitive and alt.labels_by_horizon(HORIZONS) != labels:
        return "oq21_sensitive"
    u.labels, u.signature = labels, _signature(u.call, a)
    return None


OQ21_LINK: Counter[str] = Counter()


def label_link(u: Unit, member: slf.PairMember) -> str | None:
    g = slf.gold_gate(member)
    if not g.ok:
        return str(g.reason)
    alt = slp.oq21_alternative(member.state, member.call)
    labels = g.assessment.labels_by_horizon(HORIZONS)
    if not alt.is_definitive:
        OQ21_LINK["undetermined"] += 1
        return "oq21_undetermined"
    if alt.labels_by_horizon(HORIZONS) != labels:
        OQ21_LINK["changed"] += 1
        return "oq21_sensitive"
    OQ21_LINK["unchanged"] += 1
    u.labels, u.signature = labels, _signature(u.call, g.assessment)
    return None


def candidates() -> Iterable[list[tuple[Unit, slf.PairMember | None]]]:
    """Deterministic candidate groups: a pair (2 units) or a single (1 unit)."""
    for fid, fam in sorted(ALL_FAMILIES.items()):
        for i in range(DRAWS):
            p = pilot.sample_params(random.Random(f"{SEED}|{fid}|{i}"))
            pid = f"{fid}-{i:04d}-pair"
            yield [
                (Unit(fid, k, pid, fam.world(p, v), fam.action(p), fam.expected[n]), None)
                for n, (k, v) in enumerate(zip(("pa", "pb"), fam.pivot_values, strict=True))
            ]
            for j in range(2):  # the Phase 5B non-pair actions
                name = pilot.OTHER_ACTION_CYCLE[(i + j) % len(pilot.OTHER_ACTION_CYCLE)]
                state = fam.world(p, fam.pivot_values[(i + j) % 2])
                yield [(Unit(fid, f"s{j}", None, state, pilot.OTHER_ACTIONS[name](p), None), None)]
    for fam in slf.FAMILIES:
        for i in range(DRAWS):
            params = slf.sample_params(random.Random(f"{SEED}|{fam.family_id}|{i}"), LINK_CFG)
            plan = slf.ShareScenarioPlan(f"{fam.family_id}-{i:04d}", fam, i, params)
            yield [
                (
                    Unit(
                        fam.family_id,
                        m.pivot_value,
                        plan.pair_id,
                        m.state,
                        m.call,
                        fam.expected[m.pivot_value][H3],
                    ),
                    m,
                )
                for m in slf.pair_members(plan)
            ]


def admit() -> tuple[list[Unit], Counter[str], dict[str, int]]:
    """Pair-atomic admission of at most SURFACE_VARIANTS gold units per coarse scenario."""
    per_coarse: Counter[str] = Counter()
    seen: set[str] = set()
    units: list[Unit] = []
    drops: Counter[str] = Counter()
    mismatch: Counter[str] = Counter()
    for group in candidates():
        for u, _ in group:
            s = _struct(u.state, u.call)
            u.coarse, u.strict, u.masked = (
                scenario_id(s, "coarse"),
                scenario_id(s, "strict"),
                (masked_form(s)),
            )
        exact = [sha256_text(stable_json(_struct(u.state, u.call))) for u, _ in group]
        if any(e in seen for e in exact):
            drops["exact_duplicate_state_action"] += 1
            continue
        if any(per_coarse[u.coarse] >= SURFACE_VARIANTS for u, _ in group):
            drops["coarse_scenario_full"] += 1
            continue
        reasons = [label_legacy(u) if m is None else label_link(u, m) for u, m in group]
        if any(reasons):
            drops.update(f"not_gold:{r}" for r in reasons if r)
            continue
        if any(u.expected_h3 is not None and u.labels[H3] != u.expected_h3 for u, _ in group):
            mismatch[group[0][0].family] += 1
            drops["design_expectation_mismatch"] += 1
            continue
        seen.update(exact)
        for u, _ in group:
            per_coarse[u.coarse] += 1
            units.append(u)
    return units, drops, dict(mismatch)


def render(units: list[Unit]) -> tuple[list[dict[str, Any]], Counter[str], dict[str, Any]]:
    """Up to 3 records per unit; ADR-0006 D5 signature cap and exact de-duplication."""
    records: list[dict[str, Any]] = []
    drops: Counter[str] = Counter()
    per_sig: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    text: dict[tuple[int, str], str] = {}
    for n, u in enumerate(units):
        action_text = canonical_action_text(u.call)
        for style in RENDER_STYLES:
            state_text = render_state_text_v11(u.state, style)
            text[(n, style)] = state_text
            sig = template_signature({"state_text": state_text, "action_text": action_text})
            if (state_text, action_text) in seen:
                drops["exact_duplicate_text"] += 1
                continue
            if per_sig[sig] >= D5_SIGNATURE_CAP:
                drops["d5_signature_cap"] += 1
                continue
            seen.add((state_text, action_text))
            per_sig[sig] += 1
            records.append({"unit": n, "style": style, "template": sig})
    # pivot visibility: inside a pair, the two state texts must differ in every style
    members: dict[str, list[int]] = defaultdict(list)
    for n, u in enumerate(units):
        if u.pair_id:
            members[u.pair_id].append(n)
    invisible: Counter[str] = Counter()
    for a, b in (v for v in members.values() if len(v) == 2):
        for style in RENDER_STYLES:
            if text[(a, style)] == text[(b, style)]:
                invisible[f"{units[a].family}:{style}"] += 1
    return records, drops, {"pairs_checked": len(members), "pivot_invisible": dict(invisible)}


def consistency(units: list[Unit]) -> dict[str, Any]:
    """Groups whose surface variants disagree on labels (h1-h3) or recovery signature."""
    out: dict[str, Any] = {}
    for level in ("strict", "coarse", "masked"):
        groups: dict[str, list[Unit]] = defaultdict(list)
        for u in units:
            groups[getattr(u, level)].append(u)
        bad = [
            g for g in groups.values() if len({stable_json([u.labels, u.signature]) for u in g}) > 1
        ]
        out[level] = {
            "groups": len(bad),
            "label_conflicts": sum(len({stable_json(u.labels) for u in g}) > 1 for g in bad),
            "detail": [
                {
                    "families": sorted({u.family for u in g}),
                    "tools": sorted({u.call.tool for u in g}),
                    "behaviours": sorted({stable_json([u.labels, u.signature]) for u in g}),
                }
                for g in bad
            ],
        }
    return out


def joint_feasible(records: list[dict[str, Any]], units: list[Unit]) -> dict[str, Any]:
    """Largest total meeting BOTH the professor's >= 30% minimal pairs (strict, ADR-0006 D6)
    and ADR-0006 D5's 8% family cap, keeping complete pairs first, then non-pair records."""
    pair_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        u = units[r["unit"]]
        if u.pair_id:
            pair_groups[(u.pair_id, r["style"])].append(r)
    in_pair = {id(r) for g in pair_groups.values() if len(g) == 2 for r in g}
    pairs_f: Counter[str] = Counter(units[r["unit"]].family for r in records if id(r) in in_pair)
    all_f: Counter[str] = Counter(units[r["unit"]].family for r in records)
    best = 0
    for total in range(1, len(records) + 1):
        cap = int(FAMILY_SHARE_CAP * total)
        pairs = sum(min(c - c % 2, cap - cap % 2) for c in pairs_f.values())
        if sum(min(c, cap) for c in all_f.values()) >= total and pairs >= 0.30 * total:
            best = total
    cap = int(FAMILY_SHARE_CAP * best)
    sel: list[dict[str, Any]] = []
    used: Counter[str] = Counter()
    for want_pair in (True, False):  # complete pairs first, then fill with non-pair records
        for r in records:
            f = units[r["unit"]].family
            if (id(r) in in_pair) == want_pair and used[f] < cap and len(sel) < best:
                sel.append(r)
                used[f] += 1
    cls = Counter(units[r["unit"]].labels[H3] for r in sel)
    return {
        "max_total": best,
        "pair_records_available": sum(pairs_f.values()),
        "pair_records_by_family": dict(sorted(pairs_f.items())),
        "class_fraction_h3_of_selection": {
            k: round(v / len(sel), 3) for k, v in sorted(cls.items())
        }
        if sel
        else {},
    }


def stats(records: list[dict[str, Any]], units: list[Unit]) -> dict[str, Any]:
    us = [units[r["unit"]] for r in records]
    n = len(records)
    pair_groups: Counter[tuple[str, str]] = Counter(
        (u.pair_id, r["style"]) for r, u in zip(records, us, strict=True) if u.pair_id
    )
    in_pairs = 2 * sum(c == 2 for c in pair_groups.values())
    by_coarse = Counter(u.coarse for u in us)
    by_masked = Counter(u.masked for u in us)
    by_family = Counter(u.family for u in us)
    top10 = sum(c for _, c in by_masked.most_common(10))
    return {
        "records": n,
        "classes_by_horizon": {
            h: dict(sorted(Counter(u.labels[h] for u in us).items())) for h in map(str, HORIZONS)
        },
        "class_fraction_h3": {
            k: round(v / n, 3) for k, v in sorted(Counter(u.labels[H3] for u in us).items())
        },
        "scenarios": {
            "strict": len({u.strict for u in us}),
            "coarse": len(by_coarse),
            "number_masked": len(by_masked),
        },
        "strict_minimal_pairs": in_pairs // 2,
        "minimal_pair_record_fraction": round(in_pairs / n, 3) if n else None,
        "concentration": {
            "max_records_per_coarse": max(by_coarse.values(), default=0),
            "max_records_per_masked": max(by_masked.values(), default=0),
            "top10_masked_share": round(top10 / n, 3) if n else None,
            "effective_masked_scenarios_inverse_simpson": round(
                n * n / sum(c * c for c in by_masked.values()), 1
            )
            if n
            else None,
            "records_per_coarse_histogram": dict(sorted(Counter(by_coarse.values()).items())),
            "max_family_share": round(max(by_family.values()) / n, 3) if n else None,
            "by_family": dict(sorted(by_family.items())),
        },
        "recovery_signatures": len({u.signature for u in us}),
        "labels_by_style": {
            s: dict(
                Counter(u.labels[H3] for r, u in zip(records, us, strict=True) if r["style"] == s)
            )
            for s in RENDER_STYLES
        },
    }


def family_capped_total(by_family: Mapping[str, int]) -> int:
    """Largest total with every family at most FAMILY_SHARE_CAP of it (ADR-0006 D5)."""
    total = sum(by_family.values())
    for _ in range(100):
        cap = int(FAMILY_SHARE_CAP * total)
        new = sum(min(c, cap) for c in by_family.values())
        if new == total:
            break
        total = new
    return total


def sensitivity_subset(records: list[dict[str, Any]], units: list[Unit]) -> list[dict[str, Any]]:
    """At most SENSITIVITY_CAP per coarse scenario: one unit (3 styles), pair-atomic."""
    keep: set[int] = set()
    used: set[str] = set()
    by_pair: dict[str, list[int]] = defaultdict(list)
    for n, u in enumerate(units):
        if u.pair_id:
            by_pair[u.pair_id].append(n)
    for n, u in enumerate(units):
        if n in keep:
            continue
        group = by_pair[u.pair_id] if u.pair_id else [n]
        if all(units[m].coarse not in used for m in group):
            keep.update(group)
            used.update(units[m].coarse for m in group)
    out, per = [], Counter()
    for r in records:
        c = units[r["unit"]].coarse
        if r["unit"] in keep and per[c] < SENSITIVITY_CAP:
            per[c] += 1
            out.append(r)
    return out


class _DSU:
    def __init__(self) -> None:
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        self.p[self.find(a)] = self.find(b)


def components(records: list[dict[str, Any]], units: list[Unit], by: str) -> list[dict[str, Any]]:
    """Split groups. ``masked_pair``: number-masked scenario joined with pair_id;
    ``family``: template family joined with number-masked scenario (families can share
    a masked shape through the generic non-pair actions)."""
    dsu = _DSU()
    for r in records:
        u = units[r["unit"]]
        node = f"m:{u.masked}"
        dsu.union(node, f"p:{u.pair_id}" if by == "masked_pair" and u.pair_id else node)
        if by == "family":
            dsu.union(node, f"f:{u.family}")
    comp: dict[str, dict[str, Any]] = {}
    for r in records:
        u = units[r["unit"]]
        c = comp.setdefault(
            dsu.find(f"m:{u.masked}"),
            {"n": 0, "cls": Counter(), "train_n": 0, "masked": set(), "coarse": set()},
        )
        c["n"] += 1
        c["cls"][u.labels[H3]] += 1
        c["train_n"] += r["style"] not in TEST_ONLY_STYLES  # if this group goes to train
        c["masked"].add(u.masked)
        c["coarse"].add(u.coarse)
    return sorted(comp.values(), key=lambda c: (-c["n"], sorted(c["masked"])[0]))


def best_split(comps: list[dict[str, Any]], compact_test_only: bool) -> dict[str, Any]:
    """Deterministic randomized greedy search for a test set of whole groups closest to
    TEST_FRACTION of records overall and per class. With ``compact_test_only`` the
    held-out render style is removed from training groups (the existing validator rule)."""
    classes = sorted({k for c in comps for k in c["cls"]})
    train_size = [c["train_n"] if compact_test_only else c["n"] for c in comps]
    best: tuple[float, list[int]] | None = None
    for k in range(SPLIT_SEARCH):
        order = list(range(len(comps)))
        random.Random(f"{SEED}|split|{k}").shuffle(order)
        test: list[int] = []
        te, tr = 0, sum(train_size)
        for i in order:  # moving a group to test adds all its records, removes its train size
            nte, ntr = te + comps[i]["n"], tr - train_size[i]
            if nte / (nte + ntr) <= TEST_FRACTION + 0.005:
                test.append(i)
                te, tr = nte, ntr
        score = _score(comps, set(test), classes, compact_test_only)
        if best is None or score[0] < best[0]:
            best = (score[0], test)
    assert best is not None
    return _describe(comps, set(best[1]), classes, compact_test_only)


def _sizes(comps: Comps, test: set[int], compact_test_only: bool) -> tuple[int, int]:
    te = sum(comps[i]["n"] for i in test)
    tr = sum(
        (c["train_n"] if compact_test_only else c["n"])
        for i, c in enumerate(comps)
        if i not in test
    )
    return te, tr


def _score(
    comps: Comps, test: set[int], classes: list[str], compact_test_only: bool
) -> tuple[float, float]:
    te, tr = _sizes(comps, test, compact_test_only)
    frac = te / (te + tr)
    per = []
    for k in classes:
        tk = sum(comps[i]["cls"][k] for i in test)
        ak = sum(c["cls"][k] for c in comps)
        per.append(abs(tk / ak - TEST_FRACTION) if ak else 0)
    return (abs(frac - TEST_FRACTION) * 2 + sum(per) / len(per), frac)


def _describe(
    comps: Comps, test: set[int], classes: list[str], compact_test_only: bool
) -> dict[str, Any]:
    te, tr = _sizes(comps, test, compact_test_only)
    return {
        "test_records": te,
        "train_records": tr,
        "test_fraction": round(te / (te + tr), 4),
        "test_class_fraction_of_class": {
            k: round(
                sum(comps[i]["cls"][k] for i in test) / max(1, sum(c["cls"][k] for c in comps)), 3
            )
            for k in classes
        },
        "test_groups": len(test),
        "test_masked_scenarios": len(set().union(*(comps[i]["masked"] for i in test))),
        "test_coarse_scenarios": len(set().union(*(comps[i]["coarse"] for i in test))),
    }


def split_report(records: list[dict[str, Any]], units: list[Unit], by: str) -> dict[str, Any]:
    comps = components(records, units, by)
    n = len(records)
    return {
        "group_key": by,
        "groups": len(comps),
        "largest_group_share": round(comps[0]["n"] / n, 3) if comps else None,
        "group_size_top5": [c["n"] for c in comps[:5]],
        "all_styles_everywhere": best_split(comps, compact_test_only=False),
        "compact_test_only": best_split(comps, compact_test_only=True),
    }


def prior_coarse() -> set[str]:
    out: set[str] = set()
    for path, sha in PRIORS.values():
        if sha256_file(path) != sha:
            raise SystemExit(f"{path}: checksum mismatch")
        for line in path.read_text("utf-8").splitlines():
            if line:
                out.add(scenario_id(json.loads(line), "coarse"))
    return out


def main() -> int:
    t0 = time.perf_counter()
    units, admit_drops, mismatch = admit()
    t_label = time.perf_counter() - t0
    records, render_drops, visibility = render(units)
    full = stats(records, units)
    capped = family_capped_total(full["concentration"]["by_family"])
    subset = sensitivity_subset(records, units)
    priors = prior_coarse()
    result = {
        "config": {
            "seed": SEED,
            "draws_per_family": DRAWS,
            "surface_variants": SURFACE_VARIANTS,
            "styles": list(RENDER_STYLES),
            "cap_per_coarse": CAP,
            "sensitivity_cap": SENSITIVITY_CAP,
            "d5_signature_cap": D5_SIGNATURE_CAP,
            "family_share_cap": FAMILY_SHARE_CAP,
            "link_config": LINK_CFG.to_dict(),
            "prompt_builder": "1.1.0 (render_state_text_v11) for every record",
        },
        "admission": {
            "gold_units": len(units),
            "drops": dict(sorted(admit_drops.items())),
            "design_mismatch_by_family": mismatch,
            "link_oq21_alternative": dict(OQ21_LINK),
        },
        "label_consistency_conflicts": consistency(units),
        "render": {"drops": dict(render_drops), **visibility},
        "protocol_b": full,
        "family_cap_compliant_total": capped,
        "joint_pairs_and_family_cap": joint_feasible(records, units),
        "sensitivity_subset_cap3": stats(subset, units),
        "coarse_scenarios_already_in_priors": len(
            {units[r["unit"]].coarse for r in records} & priors
        ),
        "split_masked_pair": split_report(records, units, "masked_pair"),
        "split_family": split_report(records, units, "family"),
    }
    result["determinism_sha256"] = sha256_text(stable_json(result))
    result["runtime_s"] = {
        "admit_and_label": round(t_label, 1),
        "total": round(time.perf_counter() - t0, 1),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUT, result)
    keys = (
        "admission",
        "label_consistency_conflicts",
        "render",
        "family_cap_compliant_total",
        "determinism_sha256",
        "runtime_s",
    )
    print(json.dumps({k: result[k] for k in keys}, indent=1))
    pb = {k: v for k, v in full.items() if k != "concentration"}
    print(
        json.dumps(
            {
                "protocol_b": pb,
                "concentration": {
                    k: v for k, v in full["concentration"].items() if k != "by_family"
                },
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
