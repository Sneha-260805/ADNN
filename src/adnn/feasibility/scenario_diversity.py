"""Scenario-level diversity audit (Phase 5C, OQ-51; docs/27).

Three identifiers per sandbox record, from most to least abstract:

* **recovery signature** (:func:`recovery_signature_id`): the action tool plus the
  oracle-evidenced recovery route (tool sequence of the exact witness, else of the approximate
  witness, else ``none``). An operational label derived from stored oracle evidence, relative
  to D and h = 3. It is **not** a validated causal mechanism: tool names, route names and the
  absence of a route are not distinct causes (docs/27 §2).
* **canonical scenario** (:func:`canonical_scenario`): the full world state and action with
  surface strings alpha-renamed (equality relations kept, names dropped) and list order
  normalised. Two levels: ``strict`` keeps the rank order of non-configuration numbers;
  ``coarse`` keeps only numeric equality. Configuration values are kept verbatim, and so
  are (since 0.2) values of closed schema vocabularies (:data:`VOCABULARY`) and the empty
  string, which are structure, not surface names.
* **surface template** (:func:`surface_ids`): the surface-masked text signature
  (``composition.template_signature``) and the exact rendered text.

The canonical forms are heuristics, not ground truth: list-order normalisation does not solve
graph isomorphism, and rank or equality patterns may separate scenarios that behave alike or
(in principle) merge ones that do not. :func:`audit` therefore checks each canonical group
against the oracle (label at every horizon and recovery signature) and reports conflicts and the
strict-versus-coarse gap as uncertainty instead of hiding it.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from adnn.dataset.schema import sha256_text, stable_json
from adnn.feasibility.composition import template_signature
from adnn.sandbox.state import EMAIL_STATUSES, LINK_ACCESS, PAYMENT_STATUSES

# 0.2 (Phase 5D Task 3): closed-vocabulary values and "" are kept verbatim; 0.1 alpha-renamed
# every non-config string, which merged view/edit links, pending/settled payments and
# generated ("")/custom link addresses.
DIVERSITY_VERSION = "scenario-diversity-0.2"
# Fields whose values come from a closed vocabulary declared by the sandbox schema. A value is
# kept verbatim only if it belongs to the field's vocabulary; anything else stays surface.
VOCABULARY: dict[str, frozenset[str]] = {
    "access": frozenset(LINK_ACCESS),
    "status": frozenset(EMAIL_STATUSES) | frozenset(PAYMENT_STATUSES),
}
LEVELS = ("strict", "coarse")
_DROP = ("clock_s", "counters")  # simulation bookkeeping, identical at generation time

Record = Mapping[str, Any]


# -- recovery signature ---------------------------------------------------------------------
def _route(witness: Any) -> tuple[str, ...] | None:
    if not witness:
        return None
    return tuple(str(step["tool"]) for step in witness)


def recovery_signature(record: Record) -> dict[str, Any]:
    oracle = (record.get("meta") or {}).get("oracle") or {}
    exact, approx = _route(oracle.get("exact_witness")), _route(oracle.get("approx_witness"))
    return {
        "action_tool": record["action_call"]["tool"],
        "exact_route": list(exact) if exact else None,
        "approx_route": None if exact else (list(approx) if approx else None),
    }


def recovery_signature_id(record: Record) -> str:
    m = recovery_signature(record)
    route = (
        "exact:" + ">".join(m["exact_route"])
        if m["exact_route"]
        else "approx:" + ">".join(m["approx_route"])
        if m["approx_route"]
        else "none"
    )
    return f"{m['action_tool']}|{route}"


# -- canonical scenario -----------------------------------------------------------------------
def _verbatim(key: str | None, value: str) -> bool:
    """Structural strings: the empty sentinel, or a closed-vocabulary value of its field."""
    return value == "" or (key is not None and value in VOCABULARY.get(key, ()))


def _skeleton(obj: Any, linked: Mapping[str, str], key: str | None = None) -> Any:
    """Order key for list elements: shape with unlinked strings and numbers masked."""
    if isinstance(obj, dict):
        return {k: _skeleton(v, linked, k) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return sorted((_skeleton(v, linked, key) for v in obj), key=stable_json)
    if isinstance(obj, str):
        return obj if _verbatim(key, obj) else linked.get(obj, "<s>")
    if isinstance(obj, bool) or obj is None:
        return obj
    return "<n>"


def _normalise_lists(obj: Any, linked: Mapping[str, str]) -> Any:
    if isinstance(obj, dict):
        return {k: _normalise_lists(v, linked) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        items = [_normalise_lists(v, linked) for v in obj]
        return sorted(items, key=lambda v: stable_json(_skeleton(v, linked)))
    return obj


def canonical_scenario(record: Record, level: str = "strict") -> dict[str, Any]:
    """Canonical (state, action) form; see the module docstring for what it keeps."""
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    state = {k: v for k, v in record["state_struct"].items() if k not in _DROP}
    config = state.pop("config", {})
    call = record["action_call"]
    strings: dict[str, str] = {}
    numbers: list[float] = []

    def collect(obj: Any, key: str | None = None) -> None:
        if isinstance(obj, dict):
            for k in sorted(obj):
                collect(obj[k], k)
        elif isinstance(obj, list):
            for v in obj:
                collect(v, key)
        elif isinstance(obj, str):
            if not _verbatim(key, obj):
                strings.setdefault(obj, f"s{len(strings)}")
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            numbers.append(obj)

    # action arguments first, so tokens are anchored on the action, not on surface names
    collect(call.get("args", {}))
    linked = dict(strings)
    state = _normalise_lists(state, linked)
    collect(state)
    num_token: dict[float, str] = {}
    if level == "strict":  # rank order (and so equality) of all non-configuration numbers
        num_token = {v: f"n{i}" for i, v in enumerate(sorted(set(numbers)))}
    else:  # equality only, by first occurrence
        for v in numbers:
            num_token.setdefault(v, f"n{len(num_token)}")

    def rename(obj: Any, key: str | None = None) -> Any:
        if isinstance(obj, dict):
            return {k: rename(v, k) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [rename(v, key) for v in obj]
        if isinstance(obj, str):
            return obj if _verbatim(key, obj) else strings[obj]
        if isinstance(obj, bool) or obj is None:
            return obj
        return num_token[obj]

    return {
        "config": config,
        "state": rename(state),
        "action": {"tool": call["tool"], "args": rename(call.get("args", {}))},
    }


def scenario_id(record: Record, level: str = "strict") -> str:
    return sha256_text(stable_json(canonical_scenario(record, level)))[:16]


# -- surface ----------------------------------------------------------------------------------
def surface_ids(record: Record) -> dict[str, str]:
    text = stable_json(
        [record.get("task_text"), record.get("state_text"), record.get("action_text")]
    )
    return {
        "template": template_signature(record),
        "surface": sha256_text(text)[:16],
        "render_style": str(record.get("render_style")),
    }


def identifiers(record: Record) -> dict[str, Any]:
    return {
        "id": record["id"],
        "family": record["template_id"],
        "label": record["label"],
        "recovery_signature": recovery_signature_id(record),
        "scenario_strict": scenario_id(record, "strict"),
        "scenario_coarse": scenario_id(record, "coarse"),
        **surface_ids(record),
    }


# -- audit ------------------------------------------------------------------------------------
def _behaviour(record: Record) -> str:
    return stable_json(
        [record.get("labels_by_horizon") or record["label"], recovery_signature_id(record)]
    )


def _groups(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        out[r[key]].append(r)
    return out


def _within(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    g = _groups(rows, key)
    sizes = Counter(len(v) for v in g.values())
    n = len(rows)
    return {
        "n_unique": len(g),
        "unique_fraction": round(len(g) / n, 4) if n else None,
        "max_records_per_id": max((len(v) for v in g.values()), default=0),
        "ids_with_more_than_3_records": sum(len(v) > 3 for v in g.values()),
        "records_in_repeated_ids": sum(len(v) for v in g.values() if len(v) > 1),
        "size_histogram": dict(sorted(sizes.items())),
    }


def _conflicts(
    records: Mapping[str, Record], rows: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    """Canonical groups whose members behave differently: the canonicaliser merged distinct
    scenarios (a canonicalisation failure, reported as uncertainty)."""
    out = []
    for sid, members in _groups(rows, key).items():
        kinds = {_behaviour(records[m["id"]]) for m in members}
        if len(kinds) > 1:
            out.append(
                {
                    "scenario": sid,
                    "records": sorted(m["id"] for m in members)[:6],
                    "labels": sorted({m["label"] for m in members}),
                    "recovery_signatures": sorted({m["recovery_signature"] for m in members}),
                }
            )
    return out


def audit(
    datasets: Mapping[str, Iterable[Record]],
    gold: Mapping[str, Any] | None = None,
    n_examples: int = 5,
) -> dict[str, Any]:
    """Compare datasets in the given order (earlier = prior). ``gold`` maps a dataset name to a
    predicate selecting its gold-eligible records (reported separately)."""
    names = list(datasets)
    recs = {name: list(datasets[name]) for name in names}
    by_id: dict[str, Record] = {}
    rows: dict[str, list[dict[str, Any]]] = {}
    for name in names:
        rows[name] = []
        for r in recs[name]:
            key = f"{name}:{r['id']}"
            by_id[key] = r
            rows[name].append({**identifiers(r), "id": key, "dataset": name})
    keys = ("recovery_signature", "scenario_strict", "scenario_coarse", "template", "surface")
    out: dict[str, Any] = {"version": DIVERSITY_VERSION, "datasets": {}, "cross": {}}
    for name in names:
        rs = rows[name]
        is_gold = (gold or {}).get(name)
        gold_rs = [r for r in rs if is_gold and is_gold(by_id[r["id"]])]
        out["datasets"][name] = {
            "n_records": len(rs),
            "n_gold": len(gold_rs) if is_gold else None,
            "within": {k: _within(rs, k) for k in keys},
            "within_gold": {k: _within(gold_rs, k) for k in keys} if is_gold else None,
            "recovery_signatures": dict(
                sorted(Counter(r["recovery_signature"] for r in rs).items())
            ),
            "recovery_signatures_by_label": {
                lab: sorted({r["recovery_signature"] for r in rs if r["label"] == lab})
                for lab in sorted({r["label"] for r in rs})
            },
            "by_family_label": {
                f: {
                    lab: {
                        "records": sum(r["label"] == lab for r in fr),
                        "unique_strict": len(
                            {r["scenario_strict"] for r in fr if r["label"] == lab}
                        ),
                        "unique_coarse": len(
                            {r["scenario_coarse"] for r in fr if r["label"] == lab}
                        ),
                    }
                    for lab in sorted({r["label"] for r in fr})
                }
                for f, fr in sorted(_groups(rs, "family").items())
            },
            "recovery_signatures_by_family": {
                f: sorted({r["recovery_signature"] for r in fr})
                for f, fr in sorted(_groups(rs, "family").items())
            },
            "conflicts": {lvl: _conflicts(by_id, rs, f"scenario_{lvl}") for lvl in LEVELS},
        }
    for i, later in enumerate(names[1:], start=1):
        prior_rows = [r for p in names[:i] for r in rows[p]]
        later_rows = rows[later]
        is_gold = (gold or {}).get(later)
        cross: dict[str, Any] = {}
        for k in keys:
            seen = {r[k] for r in prior_rows}
            reused = [r for r in later_rows if r[k] in seen]
            gold_reused = [r for r in reused if is_gold and is_gold(by_id[r["id"]])]
            cross[k] = {
                "records_reusing_prior": len(reused),
                "fraction": round(len(reused) / len(later_rows), 4) if later_rows else None,
                "gold_records_reusing_prior": len(gold_reused) if is_gold else None,
                "novel_ids": len({r[k] for r in later_rows} - seen),
            }
        both = prior_rows + later_rows
        cross["pooled_conflicts"] = {
            lvl: _conflicts(by_id, both, f"scenario_{lvl}") for lvl in LEVELS
        }
        cross["cross_family_shared_scenarios"] = _cross_family(both, n_examples)
        cross["examples"] = _examples(by_id, prior_rows, later_rows, n_examples)
        out["cross"][f"{later}_vs_prior"] = cross
    out["uncertainty"] = _uncertainty(by_id, rows)
    return out


def _cross_family(rows: list[dict[str, Any]], n: int) -> dict[str, Any]:
    """Canonical scenarios realised by more than one declared family."""
    g = _groups(rows, "scenario_strict")
    multi = {
        sid: sorted({r["family"] for r in v})
        for sid, v in g.items()
        if len({r["family"] for r in v}) > 1
    }
    pairs = Counter(tuple(fams) for fams in multi.values())
    return {
        "n_scenarios": len(multi),
        "records": sum(len(g[s]) for s in multi),
        "family_sets": {" + ".join(k): v for k, v in pairs.most_common()},
        "examples": dict(list(multi.items())[:n]),
    }


def _examples(
    by_id: Mapping[str, Record], prior: list[dict[str, Any]], later: list[dict[str, Any]], n: int
) -> dict[str, Any]:
    prior_strict = _groups(prior, "scenario_strict")
    prior_coarse = _groups(prior, "scenario_coarse")
    exact_dupes, near_dupes = [], []
    for r in later:
        if r["scenario_strict"] in prior_strict and len(exact_dupes) < n:
            p = prior_strict[r["scenario_strict"]][0]
            exact_dupes.append(_pair(by_id, r, p))
        elif r["scenario_coarse"] in prior_coarse and len(near_dupes) < n:
            p = prior_coarse[r["scenario_coarse"]][0]
            near_dupes.append(_pair(by_id, r, p))
    return {"same_strict_scenario": exact_dupes, "same_coarse_only": near_dupes}


def _pair(by_id: Mapping[str, Record], a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    ra, rb = by_id[a["id"]], by_id[b["id"]]
    return {
        "new": a["id"],
        "prior": b["id"],
        "families": [a["family"], b["family"]],
        "labels": [a["label"], b["label"]],
        "same_template": a["template"] == b["template"],
        "action_text": [ra.get("action_text"), rb.get("action_text")],
    }


def _uncertainty(
    by_id: Mapping[str, Record], rows: Mapping[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    allr = [r for rs in rows.values() for r in rs]
    strict, coarse = _groups(allr, "scenario_strict"), _groups(allr, "scenario_coarse")
    merged = sum(len({r["scenario_strict"] for r in v}) > 1 for v in coarse.values())
    split_same_behaviour = sum(
        len({r["scenario_strict"] for r in v}) > 1
        and len({_behaviour(by_id[r["id"]]) for r in v}) == 1
        for v in coarse.values()
    )
    return {
        "n_strict": len(strict),
        "n_coarse": len(coarse),
        "coarse_groups_split_by_numeric_order": merged,
        "of_which_behaviourally_identical": split_same_behaviour,
        "strict_conflicts": len(_conflicts(by_id, allr, "scenario_strict")),
        "coarse_conflicts": len(_conflicts(by_id, allr, "scenario_coarse")),
        "note": (
            "strict vs coarse bounds the scenario count: strict may over-split on numeric "
            "order that does not matter; coarse may merge scenarios whose numeric order "
            "matters (detected only if behaviour differs, as a conflict)."
        ),
    }


# -- prospective gates (accepted for the NEXT expansion pilot; never retroactive) ------------
PROSPECTIVE_THRESHOLDS: dict[str, Any] = {
    "SD1_min_novel_coarse_fraction_of_gold_records": 0.50,
    "SD2_max_gold_records_per_coarse_scenario": 3,
    "SD3_max_behaviourally_conflicting_groups": 0,
}
DEFERRED = {
    "SD4": "deferred until an explicit, auditable mechanism taxonomy and irreversibility-cause "
    "representation exist; recovery signatures are not causal mechanisms"
}


def prospective_gate_values(report: Mapping[str, Any], later: str) -> dict[str, Any]:
    """Descriptive SD1-SD3 values (docs/27 §6). It does not pass or fail anything: the gates
    apply only to a future pilot whose frozen manifest includes them.

    SD1 is novelty against the *prior datasets* passed to :func:`audit` (record level: share of
    gold records whose coarse scenario is absent from all prior datasets). SD3 counts canonical
    groups, pooled with prior datasets, whose members behave differently (coarse level, which
    subsumes strict-level conflicts)."""
    cross = report["cross"][f"{later}_vs_prior"]["scenario_coarse"]
    ds = report["datasets"][later]
    g = ds["within_gold"] or ds["within"]
    n_gold = ds["n_gold"] if ds["n_gold"] is not None else ds["n_records"]
    reused = cross["gold_records_reusing_prior"]
    return {
        "status": "descriptive only; condition did not exist when this dataset was generated",
        "SD1_novel_coarse_fraction_of_gold": round(1 - reused / n_gold, 4)
        if reused is not None and n_gold
        else None,
        "SD2_max_gold_records_per_coarse_scenario": g["scenario_coarse"]["max_records_per_id"],
        "SD3_behaviourally_conflicting_groups": len(
            report["cross"][f"{later}_vs_prior"]["pooled_conflicts"]["coarse"]
        ),
        "thresholds_prospective": PROSPECTIVE_THRESHOLDS,
        "deferred": DEFERRED,
        "recovery_signatures_per_class_descriptive": {
            k: len(v) for k, v in ds["recovery_signatures_by_label"].items()
        },
    }
