"""Production dataset generator (ADR-0008 as amended by ADR-0009; docs/34).

Everything is deterministic from :class:`ProductionConfig`. Labels come only from the
unchanged oracle; this module decides *which* oracle-labelled (state, action) units enter,
how they are grouped into scenarios, which split they belong to and how they are rendered.

* **Units.** Every legacy family (16) contributes, per draw, its minimal pair (the family
  action at both pivot values) and its two Phase 5B alternative actions, each also at both
  pivot values. An alternative action becomes a **minimal pair** only when both members are
  gold and the oracle gives them different h3 labels; otherwise only the member at the
  Phase 5B pivot position is kept, as a non-pair record. The link families contribute their
  pairs with background removed.
* **Gold.** Legacy: no pending timers, judged action ok, definitive oracle, OQ-21 alternative
  not label-changing (the pilot rule; tier P units are kept separately). Link:
  ``share_link_family.gold_gate`` plus a definitive, unchanged OQ-21 alternative.
* **Grouping** (``production-grouping-1.0``). The coarse canonical scenario of
  ``scenario_diversity`` (0.2, unchanged) plus the order relation between every transferred
  amount and the configured refund fee. The relation decides whether a refund returns
  anything, so without it behaviourally different f13 states share a scenario (docs/33 §3).
* **Cap.** At most ``surface_variants`` units per grouping scenario; pairs enter atomically.
* **Split.** Groups = number-masked scenario joined with pair; a deterministic stratified
  search puts whole groups into test. ``compact`` stays test-only (``TEST_ONLY_STYLES``).
* **Selection.** ADR-0006 D5 (3 per template signature, 8% per family) and the professor's
  30% minimal-pair floor, by deterministic trimming of non-pair records first.
"""

from __future__ import annotations

import random
import re
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from adnn.dataset import pilot
from adnn.dataset import share_link_family as slf
from adnn.dataset import share_link_production as slp
from adnn.dataset.prompting_v11 import (
    PROMPT_BUILDER_VERSION,
    build_probe_prompt,
    build_stated_prompt,
    inputs_from_state,
)
from adnn.dataset.rendering import RENDER_STYLES, TEST_ONLY_STYLES
from adnn.dataset.schema import (
    HORIZONS,
    PROVISIONAL_OQ21,
    canonical_action_text,
    sha256_text,
    stable_json,
)
from adnn.feasibility.composition import template_signature
from adnn.feasibility.scaling_pilot import ALL_FAMILIES, PARTIAL_RULE
from adnn.feasibility.scenario_diversity import canonical_scenario
from adnn.sandbox import ToolCall, WorldState, assess_reversibility
from adnn.sandbox.restoration import (
    RestorationAssessment,
    declared_reversibility,
    has_pending_timers,
)
from adnn.sandbox.tools import tool_specs_for

GENERATOR_VERSION = "production-gen-1.0"
GROUPING_VERSION = "production-grouping-1.0"
DATASET_VERSION = "adnn-dataset-1.0"
H3 = str(max(HORIZONS))
TRAIN_STYLES = tuple(s for s in RENDER_STYLES if s not in TEST_ONLY_STYLES)


@dataclass(frozen=True)
class ProductionConfig:
    seed: str = "adnn-production-1"
    draws_per_family: int = 300
    surface_variants: int = 4
    d5_signature_cap: int = 3
    family_share_cap: float = 0.08
    min_pair_fraction: float = 0.30
    test_fraction: float = 0.20
    split_search: int = 3000
    link_max_files: int = 1
    link_max_distractors: int = 0
    legacy_families: tuple[str, ...] = tuple(sorted(ALL_FAMILIES))
    link_families: tuple[str, ...] = slf.FAMILY_IDS
    generator_version: str = GENERATOR_VERSION
    grouping_version: str = GROUPING_VERSION
    prompt_builder_version: str = PROMPT_BUILDER_VERSION

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["legacy_families"] = list(self.legacy_families)
        d["link_families"] = list(self.link_families)
        return d

    def sha256(self) -> str:
        return sha256_text(stable_json(self.to_dict()))


# -- grouping (production-grouping-1.0) ------------------------------------------------------
def _cmp(a: float, b: float) -> str:
    return "<" if a < b else "=" if a == b else ">"


def relations(state_struct: Mapping[str, Any], action_call: Mapping[str, Any]) -> list[list[str]]:
    """Order relation of every transferred amount against the refund fee."""
    fee = state_struct.get("config", {}).get("refund_fee", 0)
    args = action_call.get("args", {})
    if action_call.get("tool") != "transfer_money" or "amount" not in args:
        return []
    return [["amount_vs_refund_fee", _cmp(args["amount"], fee)]]


def _mask(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _mask(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_mask(v) for v in o]
    return "<n>" if isinstance(o, str) and re.fullmatch(r"n\d+", o) else o


def scenario_keys(state_struct: Mapping[str, Any], action_call: Mapping[str, Any]) -> dict:
    """``strict`` / ``coarse`` / ``masked`` grouping ids (production-grouping-1.0)."""
    rec = {"state_struct": state_struct, "action_call": action_call}
    rel = relations(state_struct, action_call)
    coarse = canonical_scenario(rec, "coarse")
    forms = {
        "strict": [canonical_scenario(rec, "strict"), rel],
        "coarse": [coarse, rel],
        "masked": [_mask(coarse), rel],
    }
    return {k: sha256_text(stable_json(v))[:16] for k, v in forms.items()}


# -- units -----------------------------------------------------------------------------------
@dataclass
class Unit:
    family: str
    draw: int
    kind: str  # primary / alt0 / alt1 / link
    state: WorldState
    call: ToolCall
    task_text: str
    pivot: dict[str, Any] | None
    pair_key: str | None = None
    expected_h3: str | None = None
    member: slf.PairMember | None = None
    keys: dict[str, str] = field(default_factory=dict)
    assessment: RestorationAssessment | None = None
    labels: dict[str, str] = field(default_factory=dict)
    alt_labels: dict[str, str] | None = None
    audit: Mapping[str, Any] | None = None
    tier: str = ""
    reason: str | None = None

    @property
    def domain(self) -> str:
        if self.family in ALL_FAMILIES:
            return ALL_FAMILIES[self.family].domain
        return slf.DOMAIN


def _legacy_label(u: Unit) -> None:
    if has_pending_timers(u.state):
        u.reason = "pending_timers"
        return
    a = assess_reversibility(u.state, u.call, **pilot.ORACLE_CONFIG)
    if not a.action_ok:
        u.reason = "judged_action_failed"
        return
    if not a.is_definitive:
        u.reason = "oracle_not_definitive"
        return
    u.assessment, u.labels = a, a.labels_by_horizon(HORIZONS)
    alt = pilot._oq21_alternative(u.state, u.call)
    u.alt_labels = (
        alt.labels_by_horizon(HORIZONS) if alt is not None and alt.is_definitive else None
    )
    u.tier = "P" if u.alt_labels is not None and u.alt_labels != u.labels else "G"


def _link_label(u: Unit) -> None:
    assert u.member is not None
    g = slf.gold_gate(u.member)
    if not g.ok:
        u.reason = str(g.reason)
        return
    alt = slp.oq21_alternative(u.state, u.call)
    if not alt.is_definitive:
        u.reason = "oq21_alternative_not_definitive"
        return
    assert g.assessment is not None
    u.assessment, u.labels, u.audit = (
        g.assessment,
        g.assessment.labels_by_horizon(HORIZONS),
        g.audit,
    )
    u.alt_labels = alt.labels_by_horizon(HORIZONS)
    u.tier = "P" if u.alt_labels != u.labels else "G"


def label(u: Unit) -> None:
    (_link_label if u.member is not None else _legacy_label)(u)


def _pivot(fam: pilot.Family, p: pilot.Params, n: int) -> dict[str, Any]:
    return {
        "factor": fam.pivot_factor,
        "scope": fam.pivot_scope,
        "value": pilot._pivot_value(fam, p, n),
    }


def candidate_groups(cfg: ProductionConfig) -> Iterator[tuple[str, list[Unit]]]:
    """(kind, units): ``pair`` (always a pair), ``either`` (pair iff labels differ)."""
    for fid in cfg.legacy_families:
        fam = ALL_FAMILIES[fid]
        for i in range(cfg.draws_per_family):
            p = pilot.sample_params(random.Random(f"{cfg.seed}|{fid}|{i}"))
            task = fam.tasks[p.task_variant].format(a=p.path_a, r=p.recipient, payee=p.payee)

            yield (
                "pair",
                [
                    Unit(
                        fid,
                        i,
                        "primary",
                        fam.world(p, v),
                        fam.action(p),
                        task,
                        _pivot(fam, p, n),
                        f"{fid}-{i:04d}-primary",
                        fam.expected[n],
                    )
                    for n, v in enumerate(fam.pivot_values)
                ],
            )
            for j in range(2):
                name = pilot.OTHER_ACTION_CYCLE[(i + j) % len(pilot.OTHER_ACTION_CYCLE)]
                call = pilot.OTHER_ACTIONS[name](p)
                yield (
                    f"either:{(i + j) % 2}",
                    [
                        Unit(
                            fid,
                            i,
                            f"alt{j}",
                            fam.world(p, v),
                            call,
                            task,
                            _pivot(fam, p, n),
                            f"{fid}-{i:04d}-alt{j}",
                        )
                        for n, v in enumerate(fam.pivot_values)
                    ],
                )
    link_cfg = slf.GenerationConfig(
        max_files=cfg.link_max_files, max_distractors=cfg.link_max_distractors
    )
    for fam_ in (f for f in slf.FAMILIES if f.family_id in cfg.link_families):
        for i in range(cfg.draws_per_family):
            params = slf.sample_params(random.Random(f"{cfg.seed}|{fam_.family_id}|{i}"), link_cfg)
            plan = slf.ShareScenarioPlan(f"{fam_.family_id}-{i:04d}", fam_, i, params)
            yield (
                "pair",
                [
                    Unit(
                        fam_.family_id,
                        i,
                        "link",
                        m.state,
                        m.call,
                        m.task_text,
                        {
                            "factor": fam_.pivot_factor,
                            "scope": m.pivot_scope,
                            "value": m.pivot_value,
                        },
                        f"{fam_.family_id}-{i:04d}-link",
                        fam_.expected[m.pivot_value][H3],
                        m,
                    )
                    for m in slf.pair_members(plan)
                ],
            )


@dataclass
class Admission:
    units: list[Unit]  # gold, admitted (pair members adjacent)
    sensitivity: list[Unit]  # tier P units (kept separately, never gold)
    drops: Counter[str]
    design_mismatch: Counter[str]
    candidate_counts: Counter[str]


def admit(cfg: ProductionConfig) -> Admission:
    per: Counter[str] = Counter()
    per_p: Counter[str] = Counter()
    seen: set[str] = set()
    out = Admission([], [], Counter(), Counter(), Counter())
    for kind, group in candidate_groups(cfg):
        for u in group:
            u.keys = scenario_keys(u.state.to_dict(), u.call.to_dict())
        exact = [sha256_text(stable_json([u.state.to_dict(), u.call.to_dict()])) for u in group]
        if all(e in seen for e in exact):
            out.drops["exact_duplicate"] += 1
            continue
        room = all(per[u.keys["coarse"]] < cfg.surface_variants for u in group)
        keep = None if kind == "pair" else group[int(kind.split(":")[1])]
        if not room and (keep is None or per[keep.keys["coarse"]] >= cfg.surface_variants):
            out.drops["scenario_full"] += 1
            continue
        to_label = group if room else [keep]
        for u in to_label:
            label(u)
        if not room:  # only the non-pair record can still enter
            assert keep is not None
            group = [keep]
        if any(u.reason for u in group):
            out.drops.update(f"not_gold:{u.reason}" for u in group if u.reason)
            if kind == "pair":
                continue
        if kind == "pair":
            if any(u.labels[H3] != u.expected_h3 for u in group):
                out.design_mismatch[group[0].family] += 1
                out.drops["design_expectation_mismatch"] += 1
                continue
            members = group
        else:  # alternative action: a pair only if both gold and the labels differ
            ok = [u for u in group if not u.reason]
            if len(ok) == 2 and ok[0].labels[H3] != ok[1].labels[H3]:
                members = ok
            else:
                assert keep is not None
                if keep.reason:
                    continue
                keep.pivot, keep.pair_key, members = None, None, [keep]
        if any(u.tier == "P" for u in members):
            for u in members:  # never gold; capped like gold, kept as a sensitivity group
                if u.tier == "P" and per_p[u.keys["coarse"]] < cfg.surface_variants:
                    per_p[u.keys["coarse"]] += 1
                    out.sensitivity.append(u)
            out.drops["oq21_sensitive_group"] += 1
            if keep is None or keep.tier != "G" or len(members) == 1:
                continue
            keep.pivot, keep.pair_key, members = None, None, [keep]  # pair invalid: keep single
        if any(per[u.keys["coarse"]] >= cfg.surface_variants for u in members):
            out.drops["scenario_full"] += 1
            continue
        if any(
            sha256_text(stable_json([u.state.to_dict(), u.call.to_dict()])) in seen for u in members
        ):
            out.drops["exact_duplicate"] += 1
            continue
        out.candidate_counts["pair" if len(members) == 2 else "single"] += 1
        for u in members:
            seen.add(sha256_text(stable_json([u.state.to_dict(), u.call.to_dict()])))
            per[u.keys["coarse"]] += 1
            out.units.append(u)
    return out


# -- grouped split ---------------------------------------------------------------------------
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


def split_groups(units: list[Unit]) -> dict[int, str]:
    """Unit index -> split group id: number-masked scenario joined with pair."""
    dsu = _DSU()
    for u in units:
        node = "m:" + u.keys["masked"]
        dsu.find(node)
        if u.pair_key:
            dsu.union(node, "p:" + u.pair_key)
    roots: dict[str, list[int]] = defaultdict(list)
    for n, u in enumerate(units):
        roots[dsu.find("m:" + u.keys["masked"])].append(n)
    out: dict[int, str] = {}
    for members in roots.values():
        gid = (
            "grp-" + sha256_text(stable_json(sorted(units[n].keys["masked"] for n in members)))[:12]
        )
        for n in members:
            out[n] = gid
    return out


def assign_split(units: list[Unit], groups: Mapping[int, str], cfg: ProductionConfig) -> set[str]:
    """Deterministic stratified search: whole groups into test, ~test_fraction of records
    overall and per class (test groups render 3 styles, train groups 2)."""
    size: dict[str, Counter[str]] = defaultdict(Counter)
    for n, u in enumerate(units):
        size[groups[n]][u.labels[H3]] += 1
    gids = sorted(size)
    classes = sorted({k for c in size.values() for k in c})
    nt, ns = len(TRAIN_STYLES), len(RENDER_STYLES)
    tot_cls = {k: sum(size[g][k] for g in gids) for k in classes}
    best: tuple[float, set[str]] | None = None
    for k in range(cfg.split_search):
        order = gids[:]
        random.Random(f"{cfg.seed}|split|{k}").shuffle(order)
        test: set[str] = set()
        te, tr = 0, nt * sum(sum(size[g].values()) for g in gids)
        for g in order:
            n = sum(size[g].values())
            nte, ntr = te + ns * n, tr - nt * n
            if nte / (nte + ntr) <= cfg.test_fraction + 0.005:
                test.add(g)
                te, tr = nte, ntr
        frac = te / (te + tr)
        per = [abs(sum(size[g][c] for g in test) / tot_cls[c] - cfg.test_fraction) for c in classes]
        score = 2 * abs(frac - cfg.test_fraction) + sum(per) / len(per)
        if best is None or score < best[0]:
            best = (score, test)
    assert best is not None
    return best[1]


# -- records ---------------------------------------------------------------------------------
def _witness(a: RestorationAssessment) -> dict[str, Any]:
    d = a.to_dict()
    return {k: d[k] for k in ("exact_witness", "approx_witness")}


def make_record(
    u: Unit,
    style: str,
    scenario: str,
    dataset_version: str,
    tool_sets: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    a = u.assessment
    assert a is not None and u.tier in ("G", "P")
    sensitive = u.tier == "P"
    tools = tool_specs_for(u.state)
    ts_id = pilot.tool_set_id(tools)
    tool_sets[ts_id] = tools
    inputs = inputs_from_state(u.task_text, u.state, style)
    action_text = canonical_action_text(u.call)
    declared = declared_reversibility(u.state, u.call)
    depths = None if declared is None else [declared.restore_depth, declared.approx_restore_depth]
    meta: dict[str, Any] = {
        "domain": u.domain,
        "example_kind": "pair_member" if u.pair_key else "non_pair",
        "unit_kind": u.kind,
        "oracle": {
            "status": a.status.value,
            "complete_through_depth": a.complete_through_depth,
            "nodes_expanded": a.nodes_expanded,
            "is_definitive": a.is_definitive,
            **_witness(a),
        },
        "oq21_alternative_labels_by_horizon": u.alt_labels,
        "declared_depths": depths,
        "declaration_agrees": None
        if depths is None
        else depths == [a.restore_depth, a.approx_restore_depth],
        "scenario_keys": dict(u.keys),
        "partial_definition": PARTIAL_RULE,
        "generator_version": GENERATOR_VERSION,
        "grouping_version": GROUPING_VERSION,
        "prompt_builder_version": PROMPT_BUILDER_VERSION,
        "probe_prompt_sha256": build_probe_prompt(inputs, action_text).prompt_sha256,
        "stated_prompt_sha256": build_stated_prompt(inputs, action_text).prompt_sha256,
    }
    if u.audit is not None:
        meta["horizon_audit"] = dict(u.audit)
    if u.member is not None:
        meta["spec_version"] = slf.SPEC_VERSION
    pivot_name = u.pivot["value"] if u.pivot else "single"
    return {
        "id": f"{u.family}-{u.draw:04d}-{u.kind}-{pivot_name}-{style}".replace(" ", "_"),
        "environment": "sandbox",
        "state_text": inputs.state_text,
        "action_text": action_text,
        "label": u.labels[H3],
        "horizon": int(H3),
        "source": "sandbox_design",
        "scenario_id": scenario,
        "template_id": u.family,
        "pair_id": f"{u.pair_key}-{style}" if u.pair_key else None,
        "pivot": dict(u.pivot) if u.pair_key and u.pivot else None,
        "labels_by_horizon": dict(u.labels),
        "restore_depth": a.restore_depth,
        "approx_restore_depth": a.approx_restore_depth,
        "task_text": u.task_text,
        "tool_set_id": ts_id,
        "action_verb": u.call.tool,
        "action_call": u.call.to_dict(),
        "state_struct": u.state.to_dict(),
        "render_style": style,
        "label_rationale": pilot._rationale(a),
        "label_provisional": sensitive,
        "provisional_reasons": [PROVISIONAL_OQ21] if sensitive else [],
        "tier": u.tier,
        "sensitivity_group": "OQ-21" if sensitive else None,
        "meta": meta,
        "dataset_version": dataset_version,
    }


@dataclass
class Built:
    records: list[dict[str, Any]]
    tool_sets: dict[str, list[dict[str, Any]]]
    split: dict[str, Any]
    report: dict[str, Any]


def _trim(records: list[dict[str, Any]], cfg: ProductionConfig) -> tuple[list, Counter[str]]:
    """ADR-0006 D5 family cap, then the 30% minimal-pair floor; non-pair records are dropped
    first (latest first), pairs only as whole pairs."""
    drops: Counter[str] = Counter()
    recs = list(records)
    for _ in range(50):
        n = len(recs)
        cap = int(cfg.family_share_cap * n)
        per = Counter(r["template_id"] for r in recs)
        over = {f: c - cap for f, c in per.items() if c > cap}
        pairs = sum(1 for r in recs if r["pair_id"])
        need_singles = max(0, n - int(pairs / cfg.min_pair_fraction))
        if not over and not need_singles:
            return recs, drops
        drop: set[int] = set()
        for f, excess in over.items():
            idx = [i for i, r in enumerate(recs) if r["template_id"] == f]
            singles = [i for i in idx if not recs[i]["pair_id"]][::-1]
            take = singles[:excess]
            drops["family_cap_non_pair"] += len(take)
            if len(take) < excess:
                by_pair: dict[str, list[int]] = defaultdict(list)
                for i in idx:
                    if recs[i]["pair_id"]:
                        by_pair[recs[i]["pair_id"]].append(i)
                for members in list(by_pair.values())[::-1]:
                    if len(take) >= excess:
                        break
                    take += members
                    drops["family_cap_pair"] += len(members)
            drop |= set(take)
        if not over and need_singles:
            singles = [i for i, r in enumerate(recs) if not r["pair_id"]][::-1]
            drop |= set(singles[:need_singles])
            drops["pair_floor_non_pair"] += min(need_singles, len(singles))
        recs = [r for i, r in enumerate(recs) if i not in drop]
    raise RuntimeError("trimming did not converge")


def select_units(units: list[Unit], cfg: ProductionConfig) -> tuple[list[Unit], Counter[str]]:
    """ADR-0006 D5 family cap and the 30% minimal-pair floor, applied to units BEFORE the
    split (records per unit are near-constant), so the stratified split is not distorted.
    Non-pair units go first (latest first); pairs only as whole pairs."""
    drops: Counter[str] = Counter()
    keep = list(units)
    for _ in range(100):
        n = len(keep)
        cap = int(cfg.family_share_cap * n)
        per = Counter(u.family for u in keep)
        pairs = sum(1 for u in keep if u.pair_key)
        drop: set[int] = set()
        for f, c in per.items():
            if c <= cap:
                continue
            idx = [i for i, u in enumerate(keep) if u.family == f]
            singles = [i for i in idx if not keep[i].pair_key][::-1]
            take = singles[: c - cap]
            drops["family_cap_non_pair_unit"] += len(take)
            pair_idx = [i for i in idx if keep[i].pair_key][::-1]
            while len(take) < c - cap and pair_idx:
                key = keep[pair_idx[0]].pair_key
                both = [i for i in pair_idx if keep[i].pair_key == key]
                take += both
                pair_idx = [i for i in pair_idx if i not in both]
                drops["family_cap_pair_unit"] += len(both)
            drop |= set(take)
        if not drop:
            excess = n - int(pairs / (cfg.min_pair_fraction + 0.01))
            if excess > 0:
                singles = [i for i, u in enumerate(keep) if not u.pair_key][::-1]
                drop = set(singles[:excess])
                drops["pair_floor_non_pair_unit"] += len(drop)
        if not drop:
            return keep, drops
        keep = [u for i, u in enumerate(keep) if i not in drop]
    raise RuntimeError("unit selection did not converge")


def build(cfg: ProductionConfig, dataset_version: str) -> Built:
    adm = admit(cfg)
    units, unit_drops = select_units(adm.units, cfg)
    groups = split_groups(units)
    test = assign_split(units, groups, cfg)
    tool_sets: dict[str, list[dict[str, Any]]] = {}
    records: list[dict[str, Any]] = []
    per_sig: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    render_drops: Counter[str] = Counter()
    for n, u in enumerate(units):
        styles = RENDER_STYLES if groups[n] in test else TRAIN_STYLES
        for style in styles:
            rec = make_record(u, style, groups[n], dataset_version, tool_sets)
            key = (rec["state_text"], rec["action_text"])
            sig = template_signature(rec)
            if key in seen:
                render_drops["exact_duplicate_text"] += 1
                continue
            if per_sig[sig] >= cfg.d5_signature_cap:
                render_drops["d5_signature_cap"] += 1
                continue
            seen.add(key)
            per_sig[sig] += 1
            records.append(rec)
    # a pair whose partner was dropped by D5 is no longer a pair: drop the orphan
    count = Counter(r["pair_id"] for r in records if r["pair_id"])
    orphans = sum(1 for r in records if r["pair_id"] and count[r["pair_id"]] != 2)
    records = [r for r in records if not r["pair_id"] or count[r["pair_id"]] == 2]
    render_drops["orphaned_pair_member"] += orphans
    records, trim_drops = _trim(records, cfg)
    records.sort(key=lambda r: r["id"])
    test_sorted = sorted(test)
    all_groups = sorted(set(groups.values()))
    split = {
        "kind": "scenario_grouped",
        "group_key": "scenario_id",
        "grouping_version": GROUPING_VERSION,
        "method": "groups = number-masked production scenario joined with pair_id; whole "
        "groups to test by a deterministic stratified search (seeded) targeting "
        f"{cfg.test_fraction:.0%} of records overall and per class; compact render style "
        "test-only",
        "seed": cfg.seed,
        "test_only_styles": list(TEST_ONLY_STYLES),
        "train_scenarios": [g for g in all_groups if g not in test],
        "test_scenarios": test_sorted,
    }
    report = {
        "admission": {
            "gold_units": len(units),
            "sensitivity_units_tier_p": len(adm.sensitivity),
            "admitted_groups": dict(adm.candidate_counts),
            "drops": dict(sorted(adm.drops.items())),
            "design_mismatch_by_family": dict(adm.design_mismatch),
        },
        "selection_drops": dict(unit_drops),
        "render_drops": dict(render_drops),
        "trim_drops": dict(trim_drops),
    }
    return Built(records, tool_sets, split, report | {"_sensitivity": adm.sensitivity})


# -- summary and gates -----------------------------------------------------------------------
def summarise(records: list[dict[str, Any]], split: Mapping[str, Any]) -> dict[str, Any]:
    """Counts, balance, pairs, split, diversity and the SD3 conflict check.

    Scenario, SD3 and diversity measures cover the records with production scenario keys
    (sandbox); ScienceWorld records have none and are counted separately (ADR-0009 A2)."""
    n = len(records)
    test = set(split["test_scenarios"])
    te = [r for r in records if r["scenario_id"] in test]
    keyed = [r for r in records if "scenario_keys" in r["meta"]]
    nk = len(keyed)
    keys = [r["meta"]["scenario_keys"] for r in keyed]
    beh: dict[str, dict[str, set[str]]] = {lvl: defaultdict(set) for lvl in ("strict", "coarse")}
    for r, k in zip(keyed, keys, strict=True):
        sig = stable_json(
            [
                r["labels_by_horizon"],
                r["meta"]["oracle"]["exact_witness"] is None,
                r["meta"]["oracle"]["approx_witness"] is None,
            ]
        )
        for lvl in beh:
            beh[lvl][k[lvl]].add(sig)
    by_coarse = Counter(k["coarse"] for k in keys)
    by_masked = Counter(k["masked"] for k in keys)
    by_family = Counter(r["template_id"] for r in records)
    pairs = sum(1 for r in records if r["pair_id"])

    def cls(rs: list[dict[str, Any]]) -> dict[str, int]:
        return dict(sorted(Counter(r["label"] for r in rs).items()))

    return {
        "records": n,
        "scienceworld_records": sum(r["environment"] == "scienceworld" for r in records),
        "classes_h3": cls(records),
        "class_fraction_h3": {k: round(v / n, 3) for k, v in cls(records).items()} if n else {},
        "classes_by_horizon": {
            h: dict(sorted(Counter(r["labels_by_horizon"][h] for r in records).items()))
            for h in map(str, HORIZONS)
        },
        "minimal_pair_records": pairs,
        "minimal_pair_fraction": round(pairs / n, 4) if n else None,
        "minimal_pairs": pairs // 2,
        "pairs_by_unit_kind": dict(
            Counter(r["meta"]["unit_kind"] for r in records if r["pair_id"])
        ),
        "test_records": len(te),
        "test_fraction": round(len(te) / n, 4) if n else None,
        "test_classes_h3": cls(te),
        "test_class_fraction_of_class": {
            k: round(v / cls(records)[k], 3) for k, v in cls(te).items()
        },
        "split_groups": {
            "train": len(split["train_scenarios"]),
            "test": len(split["test_scenarios"]),
        },
        "scenarios": {
            "strict": len({k["strict"] for k in keys}),
            "coarse": len(by_coarse),
            "number_masked": len(by_masked),
        },
        "concentration": {
            "max_records_per_coarse": max(by_coarse.values(), default=0),
            "max_records_per_masked": max(by_masked.values(), default=0),
            "effective_masked_scenarios_inverse_simpson": round(
                nk * nk / sum(c * c for c in by_masked.values()), 1
            )
            if nk
            else None,
            "top10_masked_share": round(sum(c for _, c in by_masked.most_common(10)) / nk, 3)
            if nk
            else None,
            "max_family_share": round(max(by_family.values()) / n, 4) if n else None,
            "by_family": dict(sorted(by_family.items())),
        },
        "sd3_conflicting_groups": {
            lvl: sum(len(v) > 1 for v in b.values()) for lvl, b in beh.items()
        },
        "styles": dict(Counter(r["render_style"] for r in records)),
        "compact_in_train": sum(
            1
            for r in records
            if r["render_style"] in TEST_ONLY_STYLES and r["scenario_id"] not in test
        ),
        "declaration_disagreements": sum(
            1 for r in keyed if r["meta"]["declaration_agrees"] is False
        ),
    }


def gates(summary: Mapping[str, Any], cfg: ProductionConfig) -> dict[str, bool]:
    """Production gates (ADR-0009). True = passed."""
    return {
        "min_pair_fraction": summary["minimal_pair_fraction"] >= cfg.min_pair_fraction,
        "family_share_cap": summary["concentration"]["max_family_share"] <= cfg.family_share_cap,
        "sd3_zero_conflicts": summary["sd3_conflicting_groups"]["coarse"] == 0,
        "test_fraction_18_22pct": 0.18 <= summary["test_fraction"] <= 0.22,
        "compact_test_only": summary["compact_in_train"] == 0,
    }
