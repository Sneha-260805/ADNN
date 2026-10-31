"""Phase 5F dataset capacity audit (docs/31). Run from the repository root.

    python scripts/dataset/phase5f_capacity_audit.py

Read-only with respect to data: loads the three generated datasets (checksum-verified),
counts gold under the established tier rules, and dry-runs every sandbox generator's
*structural* capacity by canonicalising planned states (no labels, no records). Writes
``results/phase5f/capacity_audit.json`` (git-ignored).

Gold rules (ADR-0006 D3, Phase 5B manifest; the user's Phase 5F instruction):
* ``pilot_v0.1`` keeps its original flags (ADR-0006 D2): only records with no provisional
  reason count; partials flagged pending-professor and OQ-21-sensitive records do not.
* Phase 5B: ``tier == "G"``.
* Phase 5E link pilot: a diagnostic pilot kept separate by decision, and its partials carry the
  pending-professor flag, so it contributes 0 production gold (reported descriptively).
* ScienceWorld: no gold record exists (stratum stopped; OQ-50 deferred).
"""

from __future__ import annotations

import json
import random
import re
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from adnn.dataset import pilot
from adnn.dataset import share_link_family as slf
from adnn.dataset.schema import HORIZONS, sha256_file, write_json
from adnn.feasibility.scaling_pilot import ALL_FAMILIES
from adnn.feasibility.scenario_diversity import (
    canonical_scenario,
    recovery_signature_id,
    scenario_id,
)
from adnn.sandbox import assess_reversibility
from adnn.sandbox.restoration import has_pending_timers

OUT = Path("results/phase5f/capacity_audit.json")
DATASETS = {
    "pilot_v0.1": (
        Path("data/pilot/pilot_v0.1.jsonl"),
        "f66b98baac43faf1ece408cc22e645faf22aace13ad6aac86f1f2c83f1d3fc53",
    ),
    "phase5b_scaling_pilot": (
        Path("data/scaling_pilot/records.jsonl"),
        "bfd1175fb7e12c0f0993adb3f7079d29388dcf250d35f1ac37693af0236baa5b",
    ),
    "phase5e_link_pilot": (
        Path("results/phase5e/pilot/run1/records.jsonl"),
        "a78646e1069e4172c770ad30a72bdc1c6abae1dbe0e82728711c062d44fa7efe",
    ),
}
GOLD: dict[str, Callable[[Mapping[str, Any]], bool]] = {
    "pilot_v0.1": lambda r: not r["provisional_reasons"],
    "phase5b_scaling_pilot": lambda r: r.get("tier") == "G",
    "phase5e_link_pilot": lambda r: False,  # diagnostic, separate, partials flagged
}
SD2_CAP = 3
DRAWS = 100  # dry-run draws per generator family


def _load(path: Path, sha: str) -> list[dict[str, Any]]:
    if sha256_file(path) != sha:
        raise SystemExit(f"{path}: checksum mismatch")
    return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x]


def _strict_pairs(records: list[dict[str, Any]], gold: set[str]) -> int:
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        if r["pair_id"]:
            groups.setdefault(r["pair_id"], []).append(r)
    return sum(
        len(m) == 2
        and all(x["id"] in gold for x in m)
        and m[0]["labels_by_horizon"]["3"] != m[1]["labels_by_horizon"]["3"]
        for m in groups.values()
    )


def _sd2_admissible(records: Iterable[Mapping[str, Any]]) -> int:
    """Largest number of records keepable with at most SD2_CAP per coarse scenario."""
    per = Counter(scenario_id(r, "coarse") for r in records)
    return sum(min(n, SD2_CAP) for n in per.values())


def dataset_stats(records: list[dict[str, Any]], is_gold: Callable[..., bool]) -> dict[str, Any]:
    gold = [r for r in records if is_gold(r)]
    gold_ids = {r["id"] for r in gold}

    def classes(rs: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        return {str(h): dict(Counter(r["labels_by_horizon"][str(h)] for r in rs)) for h in HORIZONS}

    pairs = _strict_pairs(records, gold_ids)
    return {
        "total_records": len(records),
        "gold_records": len(gold),
        "classes_all": classes(records),
        "classes_gold": classes(gold),
        "provisional_reasons": dict(
            Counter(reason for r in records for reason in r["provisional_reasons"])
        ),
        "distinct_scenarios": {
            lvl: {
                "all": len({scenario_id(r, lvl) for r in records}),
                "gold": len({scenario_id(r, lvl) for r in gold}),
            }
            for lvl in ("strict", "coarse")
        },
        "max_gold_per_coarse_scenario": max(
            Counter(scenario_id(r, "coarse") for r in gold).values(), default=0
        ),
        "sd2_admissible_gold": _sd2_admissible(gold),
        "recovery_signatures": {
            "all": len({recovery_signature_id(r) for r in records}),
            "gold": len({recovery_signature_id(r) for r in gold}),
            "gold_by_h3_label": {
                lab: sorted(
                    {recovery_signature_id(r) for r in gold if r["labels_by_horizon"]["3"] == lab}
                )
                for lab in sorted({r["labels_by_horizon"]["3"] for r in gold})
            },
        },
        "strict_minimal_pairs_gold": pairs,
        "strict_pair_fraction_of_gold": round(2 * pairs / len(gold), 4) if gold else None,
    }


def _struct(state: Any, call: Any) -> dict[str, Any]:
    return {"state_struct": state.to_dict(), "action_call": call.to_dict()}


def masked_form(record: Mapping[str, Any]) -> str:
    """Coarse canonical form with every number token masked: novelty that survives this is
    structural, not an equality coincidence among sampled numbers."""

    def m(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: m(v) for k, v in o.items()}
        if isinstance(o, list):
            return [m(v) for v in o]
        if isinstance(o, str) and re.fullmatch(r"n\d+", o):
            return "<n>"
        return o

    return json.dumps(m(canonical_scenario(record, "coarse")), sort_keys=True)


def legacy_behaviour(priors: list[dict[str, Any]]) -> dict[str, Any]:
    """Oracle-label one representative per number-masked shape that is new against the priors,
    and test whether any shows a recovery behaviour absent from the priors."""
    prior_masked = {masked_form(r) for r in priors}
    prior_sigs = {recovery_signature_id(r) for r in priors}
    prior_beh = {
        (json.dumps(r["labels_by_horizon"], sort_keys=True), recovery_signature_id(r))
        for r in priors
    }
    reps: dict[str, tuple[str, str, Any, Any]] = {}
    for fid, fam in sorted(ALL_FAMILIES.items()):
        for i in range(DRAWS):
            p = pilot.sample_params(random.Random(f"phase5f-audit|{fid}|{i}"))
            other = pilot.OTHER_ACTIONS[pilot.OTHER_ACTION_CYCLE[i % len(pilot.OTHER_ACTION_CYCLE)]]
            cands = [(fam.world(p, v), fam.action(p), "pair") for v in fam.pivot_values]
            cands.append((fam.world(p, fam.pivot_values[i % 2]), other(p), "single"))
            for state, call, kind in cands:
                key = masked_form(_struct(state, call))
                if key not in prior_masked and key not in reps:
                    reps[key] = (fid, kind, state, call)
    outcome: Counter[str] = Counter()
    by_family: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    new_sigs: Counter[str] = Counter()
    new_behaviours = 0
    for fid, kind, state, call in reps.values():
        kinds[kind] += 1
        if has_pending_timers(state):
            outcome["pending_timers"] += 1
            continue
        a = assess_reversibility(state, call, **pilot.ORACLE_CONFIG)
        if not a.action_ok or not a.is_definitive:
            outcome["not_definitive_or_failed"] += 1
            continue
        labels = a.labels_by_horizon(HORIZONS)
        alt = pilot._oq21_alternative(state, call)
        if alt is not None and alt.is_definitive and alt.labels_by_horizon(HORIZONS) != labels:
            outcome["oq21_sensitive"] += 1
            continue
        d = a.to_dict()
        witnesses = {"exact_witness": d["exact_witness"], "approx_witness": d["approx_witness"]}
        sig = recovery_signature_id({"action_call": call.to_dict(), "meta": {"oracle": witnesses}})
        outcome["gold_eligible"] += 1
        by_family[fid] += 1
        if sig not in prior_sigs:
            new_sigs[sig] += 1
        if (json.dumps(labels, sort_keys=True), sig) not in prior_beh:
            new_behaviours += 1
    return {
        "number_masked_new_shapes": len(reps),
        "by_kind": dict(kinds),
        "outcome": dict(outcome),
        "gold_eligible_by_family": dict(sorted(by_family.items())),
        "new_recovery_signatures": dict(new_sigs),
        "new_label_signature_behaviours": new_behaviours,
    }


def legacy_capacity(prior_coarse: set[str]) -> dict[str, Any]:
    """Distinct coarse scenarios each legacy family can produce, and how many are new."""
    out: dict[str, Any] = {}
    for fid, fam in sorted(ALL_FAMILIES.items()):
        seen: list[str] = []
        curve = {}
        for i in range(DRAWS):
            p = pilot.sample_params(random.Random(f"phase5f-audit|{fid}|{i}"))
            call = fam.action(p)
            seen += [
                scenario_id(_struct(fam.world(p, v), call), "coarse") for v in fam.pivot_values
            ]
            other = pilot.OTHER_ACTIONS[pilot.OTHER_ACTION_CYCLE[i % len(pilot.OTHER_ACTION_CYCLE)]]
            seen.append(
                scenario_id(_struct(fam.world(p, fam.pivot_values[i % 2]), other(p)), "coarse")
            )
            if i + 1 in (10, 25, 50, 100):
                curve[str(i + 1)] = len(set(seen))
        distinct = set(seen)
        out[fid] = {
            "states_drawn": len(seen),
            "distinct_coarse": len(distinct),
            "saturation_curve": curve,
            "new_vs_priors": len(distinct - prior_coarse),
        }
    return out


def _ablate(member: slf.PairMember) -> dict[str, Any]:
    """Keep the target file and only the links the action touches (background removed)."""
    s, call = member.state.to_dict(), member.call
    links = s.get("share_links", [])
    if call.tool == "revoke_share_link":  # to_dict sorts files, so take the path from the action
        keep = [k for k in links if k["link_id"] == call.args["link_id"]]
        target = keep[0]["path"]
    else:
        keep = [k for k in links if k["address"] == call.args["address"]]
        target = call.args["path"]
    s["files"] = [f for f in s["files"] if f["path"] == target]
    if keep:
        s["share_links"] = keep
    else:
        s.pop("share_links", None)
    return {"state_struct": s, "action_call": call.to_dict()}


def link_capacity(prior_coarse: set[str], cfg: slf.GenerationConfig) -> dict[str, Any]:
    out: dict[str, Any] = {}
    all_ablated: set[str] = set()
    for fam in slf.FAMILIES:
        raw: set[str] = set()
        ablated: set[str] = set()
        for i in range(DRAWS):
            params = slf.sample_params(random.Random(f"phase5f-audit|{fam.family_id}|{i}"), cfg)
            plan = slf.ShareScenarioPlan(f"{fam.family_id}-audit-{i}", fam, i, params)
            for m in slf.pair_members(plan):
                raw.add(scenario_id(slf.structure(m), "coarse"))
                ablated.add(scenario_id(_ablate(m), "coarse"))
        all_ablated |= ablated
        out[fam.family_id] = {
            "states_drawn": 2 * DRAWS,
            "distinct_coarse_with_background": len(raw),
            "new_vs_priors_with_background": len(raw - prior_coarse),
            "distinct_coarse_background_ablated": len(ablated),
        }
    out["distinct_background_ablated_all_families"] = len(all_ablated)
    out["recovery_signatures"] = 5
    return out


SCIENCEWORLD = {
    "gold_records": 0,
    "source": "docs/25 section 3, docs/26 section 6, ADR-0007 (OQ-50 deferred)",
    "constructed_cases": 27,
    "tier_G_candidates_not_records": {"reversible": 5, "partial_certificate_backed": 2},
    "tier_S_search_relative_partial": 3,
    "unresolved_or_excluded": 17,
    "eligible_irreversible": 0,
    "stratum_status": "stopped: sampler supports 7 distinct physical families, 8 required; "
    "combustion not sampled; expansion deferred (OQ-50)",
}


def main() -> int:
    t0 = time.perf_counter()
    data = {name: _load(p, sha) for name, (p, sha) in DATASETS.items()}
    stats = {name: dataset_stats(recs, GOLD[name]) for name, recs in data.items()}
    production_gold = [r for name, recs in data.items() for r in recs if GOLD[name](r)]
    prior_coarse = {scenario_id(r, "coarse") for recs in data.values() for r in recs}
    pooled = {
        "production_gold_records": len(production_gold),
        "distinct_coarse_gold": len({scenario_id(r, "coarse") for r in production_gold}),
        "distinct_strict_gold": len({scenario_id(r, "strict") for r in production_gold}),
        "sd2_admissible_gold": _sd2_admissible(production_gold),
        "recovery_signatures_gold": len({recovery_signature_id(r) for r in production_gold}),
        "classes_gold_h3": dict(Counter(r["labels_by_horizon"]["3"] for r in production_gold)),
        "distinct_coarse_all_records_all_datasets": len(prior_coarse),
    }
    legacy = legacy_capacity(prior_coarse)
    behaviour = legacy_behaviour([r for recs in data.values() for r in recs])
    link = link_capacity(prior_coarse, slf.GenerationConfig())
    legacy_new = sum(v["new_vs_priors"] for v in legacy.values())
    requirement = {
        "target_gold": 2000,
        "sd2_cap": SD2_CAP,
        "min_distinct_coarse_gold_for_2000": -(-2000 // SD2_CAP),
        "first_batch_target": 500,
        "min_distinct_coarse_for_500": -(-500 // SD2_CAP),
        "min_records_new_vs_priors_for_500_sd1": 250,
        "min_strict_pair_fraction": 0.30,
    }
    doc = {
        "datasets": stats,
        "pooled_production_gold": pooled,
        "scienceworld": SCIENCEWORLD,
        "generator_capacity": {
            "draws_per_family": DRAWS,
            "legacy_sandbox_families": legacy,
            "legacy_total_new_coarse_vs_priors": legacy_new,
            "legacy_number_masked_and_behaviour": behaviour,
            "link_families": link,
        },
        "requirements": requirement,
        "runtime_s": round(time.perf_counter() - t0, 1),
    }
    write_json(OUT, doc)
    print(
        json.dumps(
            {
                "pooled": pooled,
                "legacy_new": legacy_new,
                "behaviour": behaviour,
                "link": link,
                "requirements": requirement,
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
