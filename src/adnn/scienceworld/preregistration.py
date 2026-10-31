"""Frozen pre-registration records for Phase 4H cases (docs/24 §3, ADR-0005 R1).

A :class:`Preregistration` wraps a :class:`~adnn.scienceworld.label_evidence.CaseSpec` with
everything Part 2 requires to be fixed *before* any recovery experiment: why each
property matters, identity requirements, horizon, restoration criterion, expected
observation limitations, the expected category and the selection rationale. Each record
is pinned to the Phase 4G commit and the rule/semantics versions it will be judged by.

The SHA-256 of every record is written to a committed manifest
(``docs/preregistration/phase4h_manifest.json``) by ``scripts/scienceworld/phase4h_freeze.py``;
``verify_manifest`` refuses to proceed if any record differs from its frozen hash.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adnn.scienceworld.admission import DECISION_RULE_VERSION
from adnn.scienceworld.canonical import sha256_json
from adnn.scienceworld.label_evidence import EVIDENCE_VERSION, CaseSpec
from adnn.scienceworld.semantics import SEMANTICS_VERSION

PREREGISTRATION_VERSION = "sw-prereg-1"
PHASE4G_COMMIT = "5b74630929f80e4f4a5973019e2fb2286142fbd2"
CATEGORIES = ("likely_reversible", "likely_partial", "potentially_irreversible", "unknown")
DEFAULT_HORIZON = (
    "recovery starts immediately after the target; permitted paths are the inverse-registry "
    "1-step actions, the declared paths and up to 20 object-local verb-stratified 1-step "
    "actions; wait/look/focus/inventory/read/task/reset are never recovery actions"
)
DEFAULT_CRITERION = (
    "definition B (time-matched counterfactual), identity primary; exact or within 0.01 degC "
    "for restoration, stability required at 0.1 degC; partial = meaningful restoration plus a "
    "declared residual (ADR-0004 B1)"
)
BASE_LIMITATIONS = (
    "canonical state is incomplete: portals, doors outside the room and agent internals "
    "(wait counter, focus, goal progress) are not observed",
    "objects created by the target do not exist in S0 and cannot be declared",
)


@dataclass(frozen=True)
class Preregistration:
    spec: CaseSpec
    property_rationale: tuple[tuple[str, str], ...]  # (PropertyRef.key, why it matters)
    identity_requirements: str
    expected_category: str
    selection_rationale: str
    observation_limitations: tuple[str, ...] = ()
    horizon: str = DEFAULT_HORIZON
    restoration_criterion: str = DEFAULT_CRITERION

    def __post_init__(self) -> None:
        if self.expected_category not in CATEGORIES:
            raise ValueError(f"unknown category {self.expected_category!r}")
        keys = [r.key for r in self.spec.declaration.required]
        explained = [k for k, _ in self.property_rationale]
        if sorted(keys) != sorted(explained):
            raise ValueError(f"{self.spec.case_id}: every declared property needs a rationale")

    @property
    def case_id(self) -> str:
        return self.spec.case_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": PREREGISTRATION_VERSION,
            "pinned": {
                "phase4g_commit": PHASE4G_COMMIT,
                "decision_rule": DECISION_RULE_VERSION,
                "semantics": SEMANTICS_VERSION,
                "evidence": EVIDENCE_VERSION,
            },
            "case": self.spec.to_dict(),
            "family": self.spec.family.to_dict(),
            "declaration": self.spec.declaration.to_dict(),
            "declaration_sha256": self.spec.declaration.sha256,
            "property_rationale": [list(p) for p in self.property_rationale],
            "identity_requirements": self.identity_requirements,
            "horizon": self.horizon,
            "restoration_criterion": self.restoration_criterion,
            "observation_limitations": [*BASE_LIMITATIONS, *self.observation_limitations],
            "expected_category": self.expected_category,
            "selection_rationale": self.selection_rationale,
        }

    @property
    def sha256(self) -> str:
        return sha256_json(self.to_dict())


def manifest(records: Iterable[Preregistration], extra: Mapping[str, Any]) -> dict[str, Any]:
    rows = [{"case_id": r.case_id, "sha256": r.sha256} for r in records]
    if len({r["case_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate case ids")
    return {
        "version": PREREGISTRATION_VERSION,
        "phase4g_commit": PHASE4G_COMMIT,
        "decision_rule": DECISION_RULE_VERSION,
        "records": rows,
        **extra,
    }


def verify_manifest(records: Iterable[Preregistration], path: Path) -> list[str]:
    """Return the ids whose record differs from (or is missing in) the frozen manifest."""
    frozen = {r["case_id"]: r["sha256"] for r in json.loads(path.read_text("utf-8"))["records"]}
    current = {r.case_id: r.sha256 for r in records}
    bad = [cid for cid, h in current.items() if frozen.get(cid) != h]
    bad += [cid for cid in frozen if cid not in current]
    return sorted(set(bad))
