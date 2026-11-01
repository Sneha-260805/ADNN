"""Phase 5B controlled scaling pilot: frozen design and sandbox generation (docs/26).

The pilot generator (``adnn.dataset.pilot``) is imported, never modified. Its world
builders, actions, oracle configuration and ``make_record`` are reused, so labels come
from exactly the same oracle. This module adds:

* :func:`build_manifest`: the frozen, hashed design. It holds the seeds, the family
  allocation (10 existing families chosen by seed per domain, plus 2 new payment-window
  families on existing tools), the family-disjoint split, the label rules
  (ADR-0006 D11), the exclusions and sensitivity groups, the stop-condition thresholds
  and the ScienceWorld sampler assessment;
* :func:`generate`: the sandbox stratum, driven only by a verified manifest;
* :func:`sw_sampler_assessment`: whether the existing ScienceWorld sampler supports
  eight genuinely distinct action families (docs/26 §3).

Nothing here touches the 210-example pilot or its files.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from adnn.dataset import pilot
from adnn.dataset.pilot import (
    FAMILIES,
    IRR,
    OTHER_ACTION_CYCLE,
    OTHER_ACTIONS,
    Family,
    Params,
    R,
    ScenarioPlan,
    act_pay,
    build_world,
    make_record,
    sample_params,
)
from adnn.dataset.rendering import RENDER_STYLES, TRAIN_STYLES
from adnn.dataset.schema import PROVISIONAL_OQ21, PROVISIONAL_PARTIAL, sha256_text, stable_json
from adnn.feasibility.stop_conditions import THRESHOLDS
from adnn.sandbox import WorldState

SCALING_VERSION = "scaling-pilot-0.1"
GENERATOR_VERSION = "scaling-pilot-gen-0.1"
SEED = 20261101
SCENARIOS_PER_FAMILY = 5
NON_PAIRS_PER_SCENARIO = 2
EXISTING_PER_DOMAIN = {"files": 4, "email": 2, "money": 4}
PARTIAL_RULE = (
    "team-adopted (ADR-0006 D11): partially_reversible at h=3 iff a verified approximate "
    "restoration within D exists and exact restoration fails exhaustively within D and h=3; "
    "horizon- and domain-relative, never a claim of universal irreversibility"
)


def _window_world(p: Params, window: int, mode: str) -> WorldState:
    w = build_world(p, mode=mode)
    return replace(w, config=replace(w.config, payment_cancel_window_s=window))


NEW_FAMILIES: tuple[Family, ...] = (
    Family("n01_pay_cancel_window", "money", "payment cancel window length",
           "config.payment_cancel_window_s", (60, 10),
           lambda p, v: _window_world(p, v, "cancellable"), act_pay, (R, IRR),
           ("Pay {payee} what we owe.", "Send the payment for {payee}.")),
    Family("n02_pay_two_step_window", "money", "two-step cancel window length",
           "config.payment_cancel_window_s", (60, 20),
           lambda p, v: _window_world(p, v, "cancellable_two_step"), act_pay, (R, IRR),
           ("Wire the amount to {payee}.", "Transfer the balance due to {payee}.")),
)  # fmt: skip
ALL_FAMILIES: dict[str, Family] = {f.family_id: f for f in (*FAMILIES, *NEW_FAMILIES)}


# -- ScienceWorld sampler assessment ---------------------------------------------------------
SW_PHYSICAL_FAMILY: dict[str, str] = {
    "open_close": "container",
    "activate_deactivate": "device",
    "move": "relocation",
    "pick_up": "relocation",  # moving an object into the agent's inventory
    "pour": "liquid_transfer",
    "eat": "consumption",
    "mix": "chemistry",
    "connect": "electrical",
}
SW_REQUIRED_FAMILIES = 8
SW_MAX_TASK_SHARE = 0.25


def sw_sampler_assessment() -> dict[str, Any]:
    from adnn.scienceworld.provisional import PILOT_FAMILIES, VERB_CLASSES

    classes = [c for c, _ in VERB_CLASSES]
    unmapped = [c for c in classes if c not in SW_PHYSICAL_FAMILY]
    if unmapped:
        raise ValueError(f"unmapped sampler verb classes: {unmapped}")
    distinct = sorted({SW_PHYSICAL_FAMILY[c] for c in classes})
    tasks = sorted({f.task for f in PILOT_FAMILIES})
    min_share = round(1 / len(tasks), 4) if tasks else None
    ok = len(distinct) >= SW_REQUIRED_FAMILIES
    return {
        "sampler_verb_classes": classes,
        "physical_family_of_class": {c: SW_PHYSICAL_FAMILY[c] for c in classes},
        "distinct_physical_families": distinct,
        "n_distinct": len(distinct),
        "required": SW_REQUIRED_FAMILIES,
        "not_supported_by_sampler": ["combustion (use lighter on X)"],
        "configured_task_families": tasks,
        "min_possible_max_task_share": min_share,
        "task_cap_satisfiable": min_share is not None and min_share <= SW_MAX_TASK_SHARE,
        "decision": "run" if ok else "stop: fewer than 8 genuinely distinct action families",
    }


# -- frozen design ---------------------------------------------------------------------------
def select_existing(seed: int) -> list[str]:
    rng = random.Random(f"{seed}|families")
    out: list[str] = []
    for domain, k in EXISTING_PER_DOMAIN.items():
        ids = sorted(f.family_id for f in FAMILIES if f.domain == domain)
        out += sorted(rng.sample(ids, k))
    return out


def freeze_split(family_ids: Iterable[str], seed: int) -> dict[str, list[str]]:
    rng = random.Random(f"{seed}|split")
    ids = sorted(family_ids)
    test = sorted(
        rng.choice(sorted(i for i in ids if ALL_FAMILIES[i].domain == d))
        for d in ("files", "email", "money")
    )
    return {"train_families": [i for i in ids if i not in test], "test_families": test}


def build_manifest(
    base_commit: str, sw_assessment: Mapping[str, Any], code_sha256: Mapping[str, str] | None = None
) -> dict[str, Any]:
    fams = [*select_existing(SEED), *(f.family_id for f in NEW_FAMILIES)]
    doc: dict[str, Any] = {
        "version": SCALING_VERSION,
        "generator_version": GENERATOR_VERSION,
        "base_commit": base_commit,
        "code_sha256": dict(code_sha256 or {}),
        "seeds": {"sampling": SEED, "family_selection": f"{SEED}|families",
                  "split": f"{SEED}|split", "params": f"{SEED}|params|<scenario_id>|<attempt>",
                  "style": f"{SEED}|style|<scenario_id>"},
        "sandbox": {
            "families": [
                {"family_id": i, "domain": ALL_FAMILIES[i].domain,
                 "new": i in {f.family_id for f in NEW_FAMILIES},
                 "pivot_factor": ALL_FAMILIES[i].pivot_factor,
                 "pivot_scope": ALL_FAMILIES[i].pivot_scope,
                 "pivot_values": [str(v) for v in ALL_FAMILIES[i].pivot_values],
                 "design_expected_h3": list(ALL_FAMILIES[i].expected)}
                for i in fams
            ],
            "scenarios_per_family": SCENARIOS_PER_FAMILY,
            "examples_per_scenario": {"pair_members": 2, "non_pair": NON_PAIRS_PER_SCENARIO},
            "planned_examples": len(fams) * SCENARIOS_PER_FAMILY * (2 + NON_PAIRS_PER_SCENARIO),
            "non_pair_actions": "OTHER_ACTION_CYCLE[(index + j) % 5] for j in 0..1, state "
                                "pivot value (index + j) % 2",
            "non_pair_cycle": list(OTHER_ACTION_CYCLE),
            "render_styles": {"train": list(TRAIN_STYLES), "test": list(RENDER_STYLES)},
            "split": {"group_key": "template_id", **freeze_split(fams, SEED),
                      "method": "one test family per domain, chosen by seed from family ids "
                                "only, before any text is rendered"},
            "oracle": dict(pilot.ORACLE_PROVENANCE, partial_definition=PARTIAL_RULE),
        },
        "label_rules": {
            "tier_G": "oracle definitive (complete search, action ok, no pending timers), "
                      "re-derived by the audit, not OQ-21-sensitive",
            "tier_P": "OQ-21-sensitive: label changes under the alternative information rule; "
                      "kept as a separate sensitivity group, never converted to gold",
            "partial": PARTIAL_RULE,
            "irreversible": "complete bounded search over D to h=3 with no exact or approximate "
                            "restoration; horizon- and domain-relative",
        },
        "exclusions": [
            "pending timers in the initial state",
            "judged action failed",
            "oracle not definitive (budget exhausted)",
            "duplicate (state_text, action_text) within the pilot or identical to a record of "
            "the existing 210-example pilot",
            "a family whose oracle pair labels disagree with its frozen design expectation in "
            "any scenario is excluded in full (never re-specified)",
        ],
        "sensitivity_groups": {
            "OQ-21": "alternative labels stored per record; tier P",
            "OQ-24": "widened action-domain re-labelling of every non-reversible record",
            "horizons": "labels at h=1,2,3",
        },
        "stop_conditions": {"thresholds": THRESHOLDS,
                            "S6_checkpoint": "after the complete sandbox stratum",
                            "S1_checkpoint": "after 80 ScienceWorld candidates"},
        "scienceworld": dict(sw_assessment),
        "no_gold_export": True,
    }  # fmt: skip
    doc["sha256"] = sha256_text(stable_json({k: v for k, v in doc.items() if k != "sha256"}))
    return doc


def verify_manifest(doc: Mapping[str, Any]) -> bool:
    return doc.get("sha256") == sha256_text(
        stable_json({k: v for k, v in doc.items() if k != "sha256"})
    )


# -- generation ------------------------------------------------------------------------------
def plan(manifest: Mapping[str, Any]) -> list[ScenarioPlan]:
    seed = manifest["seeds"]["sampling"]
    plans, seen = [], set()
    for row in manifest["sandbox"]["families"]:
        fam = ALL_FAMILIES[row["family_id"]]
        for k in range(manifest["sandbox"]["scenarios_per_family"]):
            sid = f"sp-{fam.family_id}-{k:02d}"
            attempt = 0
            while True:
                p = sample_params(random.Random(f"{seed}|params|{sid}|{attempt}"))
                key = (fam.family_id, p.path_a, p.path_b, p.content_a, p.recipient, p.payee)
                if key not in seen:
                    seen.add(key)
                    break
                attempt += 1
            plans.append(ScenarioPlan(sid, fam, k, p))
    return plans


def _finish(rec: dict[str, Any]) -> dict[str, Any]:
    reasons = [r for r in rec["provisional_reasons"] if r != PROVISIONAL_PARTIAL]
    oq21 = PROVISIONAL_OQ21 in reasons
    rec.update(
        dataset_version=SCALING_VERSION,
        provisional_reasons=reasons,
        label_provisional=bool(reasons),
        tier="P" if oq21 else "G",
        sensitivity_group="OQ-21" if oq21 else None,
    )
    rec["meta"] = {**rec["meta"], "generator_version": GENERATOR_VERSION,
                   "partial_definition": PARTIAL_RULE}  # fmt: skip
    return rec


def generate(
    manifest: Mapping[str, Any], existing_inputs: set[tuple[str, str]] | None = None
) -> dict[str, Any]:
    """The sandbox stratum. Returns records, tool sets and an exclusion report."""
    if not verify_manifest(manifest):
        raise ValueError("manifest hash mismatch: refusing to generate")
    seed = manifest["seeds"]["sampling"]
    test = set(manifest["sandbox"]["split"]["test_families"])
    existing = existing_inputs or set()
    records: list[dict[str, Any]] = []
    tool_sets: dict[str, list[dict[str, Any]]] = {}
    drops: Counter[str] = Counter()
    mismatched: dict[str, list[Any]] = {}
    by_family: dict[str, list[dict[str, Any]]] = {}
    for sp in plan(manifest):
        fam, p = sp.family, sp.params
        styles = RENDER_STYLES if fam.family_id in test else TRAIN_STYLES
        style = random.Random(f"{seed}|style|{sp.scenario_id}").choice(styles)
        task = fam.tasks[p.task_variant].format(a=p.path_a, r=p.recipient, payee=p.payee)
        common = {"plan": sp, "style": style, "task_text": task, "tool_sets": tool_sets,
                  "drops": drops}  # fmt: skip
        pair_id = f"{sp.scenario_id}-pair"
        members = [
            make_record(state=fam.world(p, fam.pivot_values[i]), call=fam.action(p), kind=kind,
                        pivot={"factor": fam.pivot_factor, "scope": fam.pivot_scope,
                               "value": pilot._pivot_value(fam, p, i)},
                        pair_id=pair_id, **common)
            for i, kind in enumerate(("pa", "pb"))
        ]  # fmt: skip
        out = by_family.setdefault(fam.family_id, [])
        if any(m is None for m in members):
            drops["pair_dropped_member_missing"] += 1
        else:
            got = tuple(m["label"] for m in members if m is not None)
            if got != fam.expected:
                mismatched.setdefault(fam.family_id, []).append([sp.scenario_id, list(got)])
            out.extend(m for m in members if m is not None)
        for j in range(NON_PAIRS_PER_SCENARIO):
            name = OTHER_ACTION_CYCLE[(sp.index + j) % len(OTHER_ACTION_CYCLE)]
            rec = make_record(state=fam.world(p, fam.pivot_values[(sp.index + j) % 2]),
                              call=OTHER_ACTIONS[name](p), kind=f"s{j}", pivot=None,
                              pair_id=None, **common)  # fmt: skip
            if rec is not None:
                out.append(rec)
    seen: set[tuple[str, str]] = set()
    for fid, recs in by_family.items():
        if fid in mismatched:
            drops["family_excluded_design_mismatch"] += len(recs)
            continue
        for rec in recs:
            key = (rec["state_text"], rec["action_text"])
            if key in seen:
                drops["duplicate_input_within_pilot"] += 1
                continue
            if key in existing:
                drops["duplicate_of_existing_210_pilot"] += 1
                continue
            seen.add(key)
            records.append(_finish(rec))
    records.sort(key=lambda r: r["id"])
    return {"records": records, "tool_sets": tool_sets, "dropped": dict(drops),
            "excluded_families": mismatched}  # fmt: skip


def existing_inputs(path: Path) -> set[tuple[str, str]] | None:
    """(state_text, action_text) of the existing pilot, read-only; None if absent."""
    if not path.exists():
        return None
    import json

    with open(path, encoding="utf-8") as fh:
        return {
            (r["state_text"], r["action_text"]) for r in (json.loads(x) for x in fh if x.strip())
        }


# -- structural uniqueness -------------------------------------------------------------------
def structure_signature(record: Mapping[str, Any]) -> str:
    """Underlying scenario shape: state structure and configuration with surface values
    (names, paths, texts, amounts) masked, plus the action tool. Cosmetic rewordings and
    re-sampled surface values share a signature."""

    def mask(obj: Any, under_config: bool = False) -> Any:
        if isinstance(obj, dict):
            return {k: mask(v, under_config or k == "config") for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [mask(v, under_config) for v in obj]
        if under_config or isinstance(obj, bool) or obj is None:
            return obj
        return "<v>"

    st = dict(record["state_struct"])
    st.pop("clock_s", None)
    st.pop("counters", None)
    key = stable_json([mask(st), record["action_call"]["tool"]])
    return sha256_text(key)[:16]
