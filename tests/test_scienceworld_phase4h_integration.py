"""Optional Phase 4H integration tests on the pinned simulator (docs/24).

Skipped unless the isolated runtime is configured. The source audits additionally need
the pinned Scala source in ``ADNN_SW_SOURCE_DIR``. Nothing here produces a label.
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
from adnn.scienceworld.certificate_audit import (
    Lab,
    _flags,
    _one,
    check_eat_plantless,
    plant_closure,
    reattachment_obligation,
)
from adnn.scienceworld.certificates import MET, NOT_MET
from adnn.scienceworld.env import ScienceWorldSession
from adnn.scienceworld.phase4h_cases import FILL_POT, KITCHEN, PLANT_WORLD
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
NAMES = {"banana": "Banana", "apple": "Apple"}


def test_chair_fire_is_put_out_by_pouring_water_and_has_combusted_stays_true() -> None:
    with ScienceWorldSession(CONFIG) as session:
        lab = Lab(session)
        s0 = lab.at(KITCHEN, *FILL_POT)
        chair = _one(s0, "chair", "kitchen")
        assert lab.do("use lighter on chair") == "accepted"
        assert _flags(lab.state(), chair)["isCombusting"] is True
        assert lab.do("pour metal pot into chair") == "accepted"
        flags = _flags(lab.state(), chair)
        assert flags["isCombusting"] is False and flags["hasCombusted"] is True


def test_plantless_precondition_met_for_banana_and_not_with_an_apple_tree() -> None:
    with ScienceWorldSession(CONFIG) as session:
        lab = Lab(session)
        for fam, food, expected in ((KITCHEN, "banana", MET), (PLANT_WORLD, "apple", NOT_MET)):
            s0 = lab.at(fam)
            ids = lab.ids(f"eat {food}")
            lab.do(f"eat {food}")
            check = check_eat_plantless(s0, f"eat {food}", lab.state(), ids, NAMES)
            assert check.status == expected, check


@pytest.mark.skipif(not os.environ.get("ADNN_SW_SOURCE_DIR"), reason="ADNN_SW_SOURCE_DIR not set")
def test_reattachment_and_plant_closure_discharge_on_pinned_source() -> None:
    root = Path(os.environ["ADNN_SW_SOURCE_DIR"])
    assert reattachment_obligation(root).status == "discharged"
    assert plant_closure(root).status == "discharged"


def test_no_java_processes_left_behind() -> None:
    assert java_process_count() == 0
