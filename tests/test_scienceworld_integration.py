"""Optional integration tests against the real, pinned ScienceWorld (docs/18 §8).

Skipped unless the isolated runtime is configured, e.g. (Git Bash)::

    SW="$LOCALAPPDATA/adnn-sw"
    ADNN_SW_JAVA_HOME="$SW/jdk/jdk-21.0.13+9" \
    ADNN_SW_SITE_PACKAGES="$SW/venv-e8216d6/Lib/site-packages" \
        .venv/Scripts/python.exe -m pytest -m scienceworld -q

These tests check simulator behaviour and adapter guarantees. They do not
produce or check reversibility labels.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess

import pytest

from adnn.scienceworld import (
    DISCRETE_EXPLORATION,
    FIRST_TICK_PREPARATION,
    InvalidReplayActionError,
    ReplayDivergenceError,
    ReplayRecipe,
    RuntimeConfig,
    ScienceWorldSession,
    ScienceWorldUnavailableError,
    UnpinnedRuntimeError,
    assert_reproducible,
    canonical_diff,
    capture_state,
    compare_results,
    projection_diff,
    replay,
    replay_in_fresh_process,
    resolve_runtime,
)

CONFIG = RuntimeConfig.from_env()
try:
    PROVENANCE = resolve_runtime(CONFIG)
    SKIP_REASON = ""
except (ScienceWorldUnavailableError, UnpinnedRuntimeError) as exc:
    PROVENANCE = None
    SKIP_REASON = f"pinned ScienceWorld runtime not available: {exc}"

pytestmark = [
    pytest.mark.scienceworld,
    pytest.mark.skipif(PROVENANCE is None, reason=SKIP_REASON or "runtime unavailable"),
]

# Upstream determinism trace (tests/test_scienceworld.py @ e8216d6).
BOIL = ReplayRecipe(
    "1-1",
    0,
    "teleportAction",
    actions=(
        "teleport to kitchen",
        "pour counter into sink",
        "activate sink",
        "use lighter on drawer",
        "look around",
    ),
)


def java_process_count() -> int | None:
    if os.name != "nt":
        return None
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq java.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
    ).stdout
    return sum(1 for line in out.splitlines() if line.startswith('"java.exe"'))


def session() -> ScienceWorldSession:
    return ScienceWorldSession(CONFIG)


def test_provenance_is_the_pinned_build() -> None:
    assert PROVENANCE is not None
    assert PROVENANCE.jar_sha256 == PROVENANCE.pin.jar_sha256
    assert PROVENANCE.source_archive_sha256 == PROVENANCE.pin.source_archive_sha256
    assert PROVENANCE.package_version == "1.3.0" and PROVENANCE.java_version


def test_repeated_reset_gives_identical_states() -> None:
    with session() as s:
        s.load("1-1", 0, "teleportAction")
        first = capture_state(s)
        for _ in range(10):
            s.reset()
            again = capture_state(s)
            assert again.raw.fingerprint == first.raw.fingerprint
            assert again.canonical.fingerprint == first.canonical.fingerprint


def test_repeated_in_process_replays_agree() -> None:
    runs = [replay(BOIL, config=CONFIG, capture="all") for _ in range(3)]
    assert_reproducible(runs)
    assert "a substance called steam" in runs[0].final.raw.look


def test_fresh_process_replays_agree() -> None:
    local = replay(BOIL, config=CONFIG, capture="all")
    fresh = [replay_in_fresh_process(BOIL, config=CONFIG, capture="all") for _ in range(2)]
    assert_reproducible([local, *fresh])
    assert (
        fresh[0].provenance is not None
        and fresh[0].provenance["jar_sha256"] == PROVENANCE.jar_sha256
    )


def test_door_state_only_in_look_text_and_marked_incomplete() -> None:
    with session() as s:
        s.load("1-1", 0, "")
        s.step("wait1")  # past the first tick
        before = capture_state(s)
        opened = s.step("open door to kitchen")
        after_open = capture_state(s)
        s.step("close door to kitchen")
        after_close = capture_state(s)
    assert opened.status == "accepted"
    assert not any(
        v is not None
        for o in before.canonical.objects.values()
        for k, v in o.items()
        if k == "propPortal"
    )
    d_open = projection_diff(before.canonical, after_open.canonical, DISCRETE_EXPLORATION)
    assert [c.key for c in d_open.changes] == ["door:kitchen"]
    assert (d_open.changes[0].before, d_open.changes[0].after) == ("closed", "open")
    d_close = projection_diff(after_open.canonical, after_close.canonical, DISCRETE_EXPLORATION)
    assert [(c.key, c.after) for c in d_close.changes] == [("door:kitchen", "closed")]
    assert not d_close.supports_exact_equality_claim and not after_close.canonical.is_complete


def test_device_activation_and_deactivation() -> None:
    with session() as s:
        s.load("1-1", 0, "teleportAction")
        s.step("wait1")
        s.step("teleport to kitchen")
        off = capture_state(s)
        s.step("activate stove")
        on = capture_state(s)
        s.step("deactivate stove")
        off_again = capture_state(s)
    on_d = projection_diff(off.canonical, on.canonical, DISCRETE_EXPLORATION)
    assert sorted(c.key.split(":", 1)[1] for c in on_d.changes) == [
        "propDevice.isActivated",
        "propHeatSource.curSetTemp",
    ]
    back = projection_diff(off.canonical, off_again.canonical, DISCRETE_EXPLORATION)
    assert back.equal_on_observed_fields and back.n_ignored_differences > 0


def test_timed_actions_change_temperatures() -> None:
    with session() as s:
        s.load("1-1", 0, "")
        s.step("wait1")
        a = capture_state(s)
        s.step("wait1")
        b = capture_state(s)
    d = canonical_diff(a.canonical, b.canonical)
    n_temp = sum(c.key.endswith("propMaterial.temperatureC") for c in d.changes)
    assert n_temp > 0
    assert not d.created_objects and not d.deleted_objects


def test_first_tick_creates_objects() -> None:
    with session() as s:
        s.load("1-1", 0, "")
        start = capture_state(s)
        s.step("wait1")
        ticked = capture_state(s)
    created = [
        name for _, name in canonical_diff(start.canonical, ticked.canonical).created_objects
    ]
    assert "water" in created


def test_mixing_creates_and_deletes_objects() -> None:
    with session() as s:
        gold = s.load_with_gold_path("6-1", 0, "")
        mix_index = next(i for i, a in enumerate(gold) if a.startswith("mix"))
        for action in gold[:mix_index]:
            assert s.step(action).status == "accepted"
        before = capture_state(s)
        assert s.step(gold[mix_index]).status == "accepted"
        after = capture_state(s)
    d = canonical_diff(before.canonical, after.canonical)
    deleted = {name for _, name in d.deleted_objects}
    created = {name for _, name in d.created_objects}
    assert {"sodium chloride", "water"} <= deleted and "salt water" in created


def test_invalid_actions_and_look_around_do_not_advance_time() -> None:
    with session() as s:
        s.load("1-1", 0, "")
        s.step("wait1")
        a = capture_state(s)
        look = s.step("look around")
        bad = s.step("dance wildly with the ceiling")
        b = capture_state(s)
    assert not look.advanced_time and not bad.advanced_time and bad.status == "invalid"
    assert a.raw.fingerprint == b.raw.fingerprint


def test_no_java_process_leak_after_normal_exit_or_failure() -> None:
    before = java_process_count()
    with session() as s:
        s.load("1-1", 0, "")
        proc = s.process
    assert proc.poll() is not None
    with pytest.raises(RuntimeError, match="deliberate"), session() as s2:
        s2.load("1-1", 0, "")
        proc2 = s2.process
        raise RuntimeError("deliberate failure")
    assert proc2.poll() is not None
    with pytest.raises(InvalidReplayActionError):
        replay(BOIL.extend("dance wildly with the ceiling"), config=CONFIG)
    if before is not None:
        assert java_process_count() == before


def test_unexpected_divergence_is_reported() -> None:
    reference = replay(BOIL, config=CONFIG, capture="all")
    tampered_step = dataclasses.replace(
        reference.steps[3], result=dataclasses.replace(reference.steps[3].result, moves_after=99)
    )
    tampered = dataclasses.replace(
        reference, steps=(*reference.steps[:3], tampered_step, *reference.steps[4:])
    )
    fresh = replay(BOIL, config=CONFIG, capture="all")
    cmp = compare_results(tampered, fresh)
    assert (cmp.first_divergent_step, cmp.divergent_fields) == (3, ("moves_after",))
    with pytest.raises(ReplayDivergenceError, match="step 3"):
        assert_reproducible([tampered, fresh])
    assert compare_results(reference, fresh).identical


def test_first_tick_preparation_is_explicit_in_the_recipe() -> None:
    prepared = dataclasses.replace(BOIL, preparation=FIRST_TICK_PREPARATION)
    res = replay(prepared, config=CONFIG)
    assert res.steps[0].phase == "preparation" and res.steps[0].result.action == "wait1"
    assert res.steps[0].result.moves_after == 2
