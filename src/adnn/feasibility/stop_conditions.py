"""Executable stop conditions for the scaling pilot (docs/25 §9, ADR-0007).

Each check returns a :class:`StopCheck`. ``triggered=True`` halts scaling for review. It
never relaxes a rule. ``evaluable=False`` means the inputs do not exist, e.g. the
ScienceWorld stratum was not run. That is reported as such, never as a pass.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

THRESHOLDS: dict[str, Any] = {
    "S1_sw_min_gold_yield": 0.10,
    "S1_sw_checkpoint_candidates": 80,
    "S2_max_replication_failures": 0,
    "S2_max_measurement_affected_fraction": 0.02,
    "S3_max_rubric_sensitive_fraction": 0.10,
    "S4_max_family_share_of_class": 0.40,
    "S5_min_effective_fraction": 0.60,
    "S6_min_strict_pair_fraction": 0.30,
    "S7_max_rederivation_failures": 0,
}


@dataclass(frozen=True)
class StopCheck:
    condition: str
    description: str
    evaluable: bool
    triggered: bool
    value: Any
    threshold: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _na(cid: str, desc: str, threshold: Any, why: str) -> StopCheck:
    return StopCheck(cid, desc, False, False, f"not evaluable: {why}", threshold)


def s1_sw_yield(n_candidates: int | None, n_gold: int | None) -> StopCheck:
    desc = "ScienceWorld gold yield below threshold after the candidate checkpoint"
    t, k = THRESHOLDS["S1_sw_min_gold_yield"], THRESHOLDS["S1_sw_checkpoint_candidates"]
    if not n_candidates or n_gold is None:
        return _na("S1", desc, t, "no ScienceWorld candidates")
    if n_candidates < k:
        return _na("S1", desc, t, f"checkpoint not reached ({n_candidates} < {k})")
    y = n_gold / n_candidates
    return StopCheck("S1", desc, True, y < t, round(y, 4), t)


def s2_replication(n_failures: int | None, n_affected: int | None = None,
                   n_cases: int | None = None) -> StopCheck:  # fmt: skip
    desc = "any replication failure, or measurement-affected fraction above threshold"
    t = THRESHOLDS["S2_max_replication_failures"]
    if n_failures is None:
        return _na("S2", desc, t, "no replication run")
    frac = (n_affected / n_cases) if n_affected is not None and n_cases else 0.0
    trig = n_failures > t or frac > THRESHOLDS["S2_max_measurement_affected_fraction"]
    return StopCheck("S2", desc, True, trig,
                     {"replication_failures": n_failures, "affected_fraction": round(frac, 4)},
                     t)  # fmt: skip


def s3_rubric_sensitivity(n_changed: int | None, n_eligible: int | None) -> StopCheck:
    desc = "rubric (property-choice) sensitivity changes too many eligible outcomes"
    t = THRESHOLDS["S3_max_rubric_sensitive_fraction"]
    if not n_eligible or n_changed is None:
        return _na("S3", desc, t, "no eligible ScienceWorld outcomes")
    f = n_changed / n_eligible
    return StopCheck("S3", desc, True, f > t, round(f, 4), t)


def s4_family_concentration(records: Iterable[Mapping[str, Any]],
                            family_key: str = "template_id") -> StopCheck:  # fmt: skip
    desc = "one family supplies more than the threshold share of any class"
    t = THRESHOLDS["S4_max_family_share_of_class"]
    by_class: dict[str, Counter[str]] = defaultdict(Counter)
    for r in records:
        by_class[r["label"]][str(r[family_key])] += 1
    if not by_class:
        return _na("S4", desc, t, "no records")
    worst = {
        lab: (c.most_common(1)[0][0], round(c.most_common(1)[0][1] / sum(c.values()), 4))
        for lab, c in by_class.items()
    }
    return StopCheck("S4", desc, True, any(s > t for _, s in worst.values()), worst, t)


def s5_effective_fraction(effective_fraction: float | None) -> StopCheck:
    desc = "surface-masked effective fraction below threshold"
    t = THRESHOLDS["S5_min_effective_fraction"]
    if effective_fraction is None:
        return _na("S5", desc, t, "no records")
    return StopCheck("S5", desc, True, effective_fraction < t, effective_fraction, t)


def s6_strict_pairs(fraction: float | None) -> StopCheck:
    desc = "strict genuine minimal-pair fraction below threshold at the checkpoint"
    t = THRESHOLDS["S6_min_strict_pair_fraction"]
    if fraction is None:
        return _na("S6", desc, t, "no records")
    return StopCheck("S6", desc, True, fraction < t, fraction, t)


def s7_rederivation(n_failures: int | None) -> StopCheck:
    desc = "any sandbox label fails re-derivation"
    t = THRESHOLDS["S7_max_rederivation_failures"]
    if n_failures is None:
        return _na("S7", desc, t, "no audit")
    return StopCheck("S7", desc, True, n_failures > t, n_failures, t)


def summary(checks: Iterable[StopCheck]) -> dict[str, Any]:
    rows = [c.to_dict() for c in checks]
    return {
        "triggered": [r["condition"] for r in rows if r["triggered"]],
        "not_evaluable": [r["condition"] for r in rows if not r["evaluable"]],
        "checks": rows,
    }
