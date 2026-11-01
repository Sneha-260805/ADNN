"""Production marking for sharing-link records (ADR-0008; docs/33 §5).

The frozen Phase 5E pilot generator (:mod:`adnn.dataset.share_link_family`,
``share-link-gen-0.2-draft``) flags every partial with the obsolete pending-professor reason
and records ``oq21_alternative_labels_by_horizon = None`` ("not applicable to link tools")
without measuring it. It is left unchanged so the frozen pilot stays reproducible from its
base commit. Production records are built from the same plans, gates and oracle, then marked
as Phase 5B marks sandbox records (ADR-0006 D2, D3, D11):

* the team-adopted partial rule (``scaling_pilot.PARTIAL_RULE``) replaces the pending flag;
* the OQ-21 alternative is **computed**, never asserted: every pre-action file/backup content
  and every pre-action link address is added to the argument pool (the link alternative of
  docs/29 §7.4, :func:`adnn.feasibility.share_link_diagnostics.oq21_alternative`);
* a changed label makes the record tier P (sensitivity group OQ-21, never gold); a
  non-definitive alternative leaves sensitivity undetermined, so the pair is dropped (tier X);
  otherwise tier G.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from adnn.dataset import share_link_family as fam
from adnn.dataset.pilot import ORACLE_CONFIG
from adnn.dataset.schema import HORIZONS, PROVISIONAL_OQ21, PROVISIONAL_PARTIAL
from adnn.feasibility.scaling_pilot import PARTIAL_RULE
from adnn.sandbox import ToolCall, WorldState, assess_reversibility
from adnn.sandbox.restoration import RestorationAssessment

GENERATOR_VERSION = "share-link-gen-0.3"


def oq21_alternative(state: WorldState, call: ToolCall) -> RestorationAssessment:
    """Re-label assuming the agent also remembers the pre-action state (sensitivity only)."""
    contents = tuple(sorted({f.content for f in (*state.files, *state.backups)}))
    addresses = tuple(sorted({k.address for k in state.share_links}))
    return assess_reversibility(
        state, call, extra_contents=contents, extra_addresses=addresses, **ORACLE_CONFIG
    )


def mark(record: dict[str, Any], member: fam.PairMember) -> dict[str, Any] | None:
    """The production form of a pilot-schema record; ``None`` if OQ-21 is undetermined."""
    alt = oq21_alternative(member.state, member.call)
    if not alt.is_definitive:
        return None
    alt_labels = alt.labels_by_horizon(HORIZONS)
    reasons = [r for r in record["provisional_reasons"] if r != PROVISIONAL_PARTIAL]
    sensitive = alt_labels != record["labels_by_horizon"]
    if sensitive:
        reasons.append(PROVISIONAL_OQ21)
    meta = {
        **record["meta"],
        "oq21_alternative_labels_by_horizon": alt_labels,
        "partial_definition": PARTIAL_RULE,
        "generator_version": GENERATOR_VERSION,
    }
    return {
        **record,
        "provisional_reasons": reasons,
        "label_provisional": bool(reasons),
        "tier": "P" if sensitive else "G",
        "sensitivity_group": "OQ-21" if sensitive else None,
        "meta": meta,
    }


def build_production_records(
    plans: list[fam.ShareScenarioPlan], dataset_version: str
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], Counter[str]]:
    """Gate, label and mark in memory. A pair enters only if both members pass every gate and
    both OQ-21 alternatives are definitive."""
    records: list[dict[str, Any]] = []
    tool_sets: dict[str, list[dict[str, Any]]] = {}
    drops: Counter[str] = Counter()
    for plan in plans:
        members = fam.pair_members(plan)
        gates = [fam.gold_gate(m) for m in members]
        failed = [g.reason for g in gates if not g.ok]
        if failed:
            drops.update(str(r) for r in failed)
            drops["pairs_dropped"] += 1
            continue
        marked = [
            mark(fam.make_record(plan, m, g, tool_sets), m)
            for m, g in zip(members, gates, strict=True)
        ]
        if any(r is None for r in marked):
            drops["oq21_alternative_not_definitive"] += 1
            drops["pairs_dropped"] += 1
            continue
        records.extend({**r, "dataset_version": dataset_version} for r in marked if r)
    return records, tool_sets, drops
