"""Controlled measurement-symmetry check for label evidence (docs/25 §4).

The frozen evidence protocol (``label_evidence``, ADR-0003 D8) is asymmetric. On the
attempt branch, the session enumerates valid actions right after the target, before the
recovery path. The time-matched counterfactual branch only idles (rebuild, then idle
ticks). This module provides a symmetric variant: the counterfactual enumerates valid
actions at the same tick offset (after the target's ticks) before idling the remaining
ticks. For every counterfactual it also records the hash of the asymmetric state, so a
transition difference is measured directly, not inferred from outcomes.

Nothing here changes the frozen protocol. :func:`symmetric_protocol` swaps the runner
only inside its ``with`` block.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import adnn.scienceworld.label_evidence as label_evidence
from adnn.scienceworld.canonical import CanonicalState, capture_state, sha256_json

SYMMETRY_VERSION = "sw-measurement-symmetry-1"


def state_hash(state: CanonicalState | None) -> str | None:
    return None if state is None else sha256_json(state.to_dict())


@dataclass
class SymmetricRun(label_evidence._Run):
    """``_Run`` whose counterfactual enumerates valid actions after the target's ticks.

    ``collect_case`` first asks for ``counterfactual(ticks_t)``, where ``ticks_t`` is the
    number of ticks the target took. That first request fixes the enumeration offset.
    """

    target_ticks: int | None = None
    pairs: list[dict[str, Any]] = field(default_factory=list)

    def _asymmetric(self, ticks: int) -> CanonicalState | None:
        self.rebuild()
        ok = self._idle(ticks)
        return capture_state(self.session).canonical if ok else None

    def counterfactual(self, ticks: int) -> CanonicalState | None:
        if self.target_ticks is None:
            self.target_ticks = ticks
        if ticks not in self.cf:
            self.rebuild()
            first = min(ticks, self.target_ticks)
            ok = self._idle(first)
            enumerated = ticks > self.target_ticks
            if enumerated:
                self.session.valid_action_templates()
                ok = self._idle(ticks - first) and ok
            sym = capture_state(self.session).canonical if ok else None
            asym = self._asymmetric(ticks) if enumerated else sym
            self.pairs.append({
                "ticks": ticks, "enumerated_at": self.target_ticks if enumerated else None,
                "symmetric": state_hash(sym), "asymmetric": state_hash(asym),
                "equal": state_hash(sym) == state_hash(asym),
            })  # fmt: skip
            self.cf[ticks] = sym
        return self.cf[ticks]


@contextmanager
def symmetric_protocol() -> Iterator[list[SymmetricRun]]:
    """Within the block, ``collect_case`` uses :class:`SymmetricRun`; yields the runs."""
    runs: list[SymmetricRun] = []
    original = label_evidence._Run

    def factory(*args: Any, **kwargs: Any) -> SymmetricRun:
        run = SymmetricRun(*args, **kwargs)
        runs.append(run)
        return run

    label_evidence._Run = factory  # type: ignore[assignment,misc]
    try:
        yield runs
    finally:
        label_evidence._Run = original  # type: ignore[misc]


def compare_protocols(
    asym: dict[str, Any], sym: dict[str, Any], pairs: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compare two evidence/decision documents of the same case under both protocols."""

    def levels(doc: dict[str, Any]) -> list[Any]:
        return [
            (tuple(a["path"]), tuple(sorted(
                (t, x["canonical_level"], tuple(x["concepts"]))
                for t, x in (a.get("assessments") or {}).items())))
            for a in doc["evidence"].get("attempts", [])
        ]  # fmt: skip

    return {
        "cf_transitions_equal": all(p["equal"] for p in pairs),
        "n_counterfactuals_with_enumeration": sum(p["enumerated_at"] is not None for p in pairs),
        "attempt_levels_equal": levels(asym) == levels(sym),
        "outcome": [asym["decision"]["outcome"], sym["decision"]["outcome"]],
        "outcome_equal": asym["decision"]["outcome"] == sym["decision"]["outcome"],
        "witness_equal": asym["decision"]["witness"] == sym["decision"]["witness"],
        "affected": not (
            all(p["equal"] for p in pairs)
            and levels(asym) == levels(sym)
            and asym["decision"]["outcome"] == sym["decision"]["outcome"]
        ),
    }
