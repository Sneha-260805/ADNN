"""Optional Phase 4G integration tests on the pinned simulator (docs/23 §8).

Skipped unless the isolated runtime is configured (same variables as
``test_scienceworld_integration.py``). The static certificate check additionally needs
the pinned Scala source in ``ADNN_SW_SOURCE_DIR``. No labels are produced or checked:
decisions are eligibility outcomes only.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from adnn.scienceworld import (
    RuntimeConfig,
    ScienceWorldUnavailableError,
    UnpinnedRuntimeError,
    resolve_runtime,
)
from adnn.scienceworld.admission import ELIGIBLE_REVERSIBLE, UNRESOLVED, decide
from adnn.scienceworld.certificate_verification import VERIFIED, static_obligations, status_of
from adnn.scienceworld.label_cases import LABEL_CASES
from adnn.scienceworld.label_evidence import collect_case
from test_scienceworld_integration import java_process_count

CONFIG = RuntimeConfig.from_env()
try:
    resolve_runtime(CONFIG)
    SKIP_REASON = ""
except (ScienceWorldUnavailableError, UnpinnedRuntimeError) as exc:
    SKIP_REASON = f"pinned ScienceWorld runtime not available: {exc}"

pytestmark = [
    pytest.mark.scienceworld,
    pytest.mark.skipif(bool(SKIP_REASON), reason=SKIP_REASON or "runtime unavailable"),
]
CASES = {c.case_id: c for c in LABEL_CASES}


def test_reversible_control_case_is_admitted_with_a_registry_witness() -> None:
    ev = collect_case(CASES["ctrl-open-cupboard"], config=CONFIG)
    assert ev["status"] == "complete" and ev["replay"]["verified"]
    d = decide(ev, {})
    assert d["outcome"] == ELIGIBLE_REVERSIBLE and d["witness"]["source"] == "registry"
    assert d["is_gold_label"] is False


def test_door_target_is_excluded_on_the_real_simulator() -> None:
    d = decide(collect_case(CASES["adv-door"], config=CONFIG), {})
    assert d["outcome"] == UNRESOLVED
    assert "hidden_door_state" in d["reasons"] or d["reasons"][0].startswith("evidence_")


@pytest.mark.skipif(not os.environ.get("ADNN_SW_SOURCE_DIR"), reason="ADNN_SW_SOURCE_DIR not set")
def test_static_burn_obligations_discharge_on_pinned_source() -> None:
    obs = static_obligations("C-BURN", Path(os.environ["ADNN_SW_SOURCE_DIR"]))
    assert status_of(obs) == VERIFIED, [o.to_dict() for o in obs if o.status != "discharged"]


def test_no_java_processes_left_behind() -> None:
    assert java_process_count() == 0
