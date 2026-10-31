"""Read-only evidence audit of the 210-example sandbox pilot (docs/25 §2).

For every record the oracle is re-run from ``state_struct`` and the label's support is
classified by what the search actually establishes:

* ``reversible``: an exact witness, replayed independently of the search, returns the
  canonical state (``verified_exact_witness``);
* ``partially_reversible``: an approximate witness replays to the core projection AND the
  search was complete to the horizon without an exact hit
  (``verified_approx_witness_complete_exact_exclusion``);
* ``irreversible``: the search was complete to the horizon over the action domain D with
  neither hit (``complete_bounded_impossibility``). This is an exhaustive argument
  relative to D, the horizon and the sandbox rules, not a statement about the world.

Sensitivity to two documented assumptions is measured, never applied: OQ-21 (the
generator's stored alternative labels) and OQ-24 (a widened argument pool). The pilot
file is opened read-only and never written.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from itertools import combinations
from pathlib import Path
from typing import Any

import adnn.sandbox.restoration as restoration
from adnn.sandbox.restoration import ArgumentPool, SearchStatus, assess_reversibility, core_hash
from adnn.sandbox.state import WorldState, canonical_hash
from adnn.sandbox.tools import ToolCall, step

AUDIT_VERSION = "pilot-audit-1"
VERIFIED_EXACT = "verified_exact_witness"
VERIFIED_APPROX = "verified_approx_witness_complete_exact_exclusion"
COMPLETE_IMPOSSIBILITY = "complete_bounded_impossibility"
UNSUPPORTED = "unsupported"


def load_records(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _replay(s1: WorldState, witness: Iterable[ToolCall]) -> WorldState:
    state = s1
    for call in witness:
        state, _ = step(state, call)
    return state


def support(record: Mapping[str, Any], horizon: int = 3) -> dict[str, Any]:
    """Re-derive the label and classify the evidence behind it."""
    s0 = WorldState.from_dict(dict(record["state_struct"]))
    call = ToolCall.from_obj(record["action_call"])
    a = assess_reversibility(s0, call, horizon=horizon, on_budget_exhausted="return")
    s1, _ = step(s0, call)
    complete = a.status == SearchStatus.COMPLETE and a.complete_through_depth == horizon
    label = a.label_at(horizon).value if a.is_determined(horizon) else "undetermined"
    exact_ok = a.exact_witness is not None and canonical_hash(
        _replay(s1, a.exact_witness)
    ) == canonical_hash(s0)
    approx_ok = a.approx_witness is not None and core_hash(
        _replay(s1, a.approx_witness)
    ) == core_hash(s0)
    if label == "reversible" and exact_ok:
        kind = VERIFIED_EXACT
    elif label == "partially_reversible" and approx_ok and complete and a.restore_depth is None:
        kind = VERIFIED_APPROX
    elif label == "irreversible" and complete and a.approx_restore_depth is None:
        kind = COMPLETE_IMPOSSIBILITY
    else:
        kind = UNSUPPORTED
    return {
        "id": record["id"],
        "stored_label": record["label"],
        "rederived_label": label,
        "agrees": label == record["label"],
        "support": kind,
        "search_complete": complete,
        "nodes": a.nodes_expanded,
        "action_ok": a.action_ok,
        "pending_timers_before": a.pending_timers_before,
        "labels_by_horizon": a.labels_by_horizon(),
    }


# -- OQ-24 sensitivity: a wider action domain ------------------------------------------------
def widened_pool(state: WorldState, judged: ToolCall) -> ArgumentPool:
    """The documented pool plus positive account balances, pairwise sums of the documented
    amounts and email fields recombined across messages (OQ-24 alternative; analysis
    only). Differences and higher-order combinations are not added (search cost)."""
    base = _ORIGINAL_POOL(state, judged)
    amounts = set(base.amounts) | {a.balance for a in state.accounts if a.balance > 0}
    amounts |= {x + y for x, y in combinations(sorted(base.amounts), 2)}
    tos = {e[0] for e in base.emails}
    subjects = {e[1] for e in base.emails}
    bodies = {e[2] for e in base.emails}
    emails = {(t, s, b) for t in tos for s in subjects for b in bodies}
    return ArgumentPool(base.contents, tuple(sorted(emails)), tuple(sorted(amounts)))


_ORIGINAL_POOL = restoration.argument_pool


@contextmanager
def oq24_widened() -> Iterator[None]:
    restoration.argument_pool = widened_pool
    try:
        yield
    finally:
        restoration.argument_pool = _ORIGINAL_POOL


def audit(records: list[dict[str, Any]], *, oq24: bool = True) -> dict[str, Any]:
    rows = [support(r) for r in records]
    by_id = {r["id"]: r for r in records}
    for row in rows:
        rec = by_id[row["id"]]
        row["provisional_reasons"] = list(rec.get("provisional_reasons", []))
        alt = ((rec.get("meta") or {}).get("oq21_alternative_labels_by_horizon") or {}).get("3")
        row["oq21_alternative_label"] = alt
        row["oq21_changes_label"] = alt is not None and alt != rec["label"]
    if oq24:
        with oq24_widened():
            for row in rows:
                if row["stored_label"] != "reversible":
                    wide = support(by_id[row["id"]])
                    row["oq24_widened_label"] = wide["rederived_label"]
                    row["oq24_changes_label"] = wide["rederived_label"] != row["stored_label"]
    return {"version": AUDIT_VERSION, "rows": rows, "summary": summarise(rows)}


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clean = [
        r
        for r in rows
        if r["support"] != UNSUPPORTED
        and not r["provisional_reasons"]
        and not r.get("oq24_changes_label")
    ]
    return {
        "n": len(rows),
        "agreement": sum(r["agrees"] for r in rows),
        "support": dict(Counter(r["support"] for r in rows)),
        "by_label_support": dict(Counter(f"{r['stored_label']}|{r['support']}" for r in rows)),
        "provisional": sum(bool(r["provisional_reasons"]) for r in rows),
        "provisional_reasons": dict(Counter(x for r in rows for x in r["provisional_reasons"])),
        "oq21_label_changes": sum(r["oq21_changes_label"] for r in rows),
        "oq24_label_changes": sum(bool(r.get("oq24_changes_label")) for r in rows),
        "oq24_changed_ids": sorted(r["id"] for r in rows if r.get("oq24_changes_label")),
        "fully_supported_non_provisional": len(clean),
        "fully_supported_non_provisional_by_label": dict(Counter(r["stored_label"] for r in clean)),
    }
