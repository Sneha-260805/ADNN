"""ScienceWorld adapter unit tests: no Java and no ScienceWorld required (docs/18 §8)."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from adnn.scienceworld import (
    DISCRETE_EXPLORATION,
    FIRST_TICK_PREPARATION,
    PINNED,
    EpisodeTerminatedError,
    InvalidReplayActionError,
    ProcessLeakError,
    RawState,
    ReplayDivergenceError,
    ReplayRecipe,
    ReplayResult,
    RuntimeConfig,
    ScienceWorldSession,
    ScienceWorldUnavailableError,
    SessionStateError,
    SimulatorPin,
    UnpinnedRuntimeError,
    assert_reproducible,
    canonical_diff,
    canonicalize,
    capture_state,
    classify_observation,
    compare_results,
    projection_diff,
    raw_diff,
    replay,
    resolve_runtime,
)
from adnn.scienceworld.canonical import BASE_INCOMPLETE_REASONS
from adnn.scienceworld.env import _launch_context
from scienceworld_fake import FakeScienceWorld


def fake(**kw: object) -> FakeScienceWorld:
    return FakeScienceWorld(**kw)  # type: ignore[arg-type]


RECIPE = ReplayRecipe(
    "1-1", 0, "teleportAction", preparation=FIRST_TICK_PREPARATION,
    actions=("activate stove", "open door to kitchen", "mix cup"),
)  # fmt: skip


# -- optional dependency ---------------------------------------------------------------
def test_import_does_not_load_scienceworld_py4j_or_java() -> None:
    code = (
        "import sys, adnn, adnn.scienceworld, adnn.sandbox, adnn.dataset.api;"
        "print(sorted(m for m in ('scienceworld','py4j') if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


# -- provenance ------------------------------------------------------------------------
def _fake_site(
    tmp: Path, *, jar: bytes = b"jar", version: str = "1.3.0", archive: str | None = None
) -> Path:
    site = tmp / "Lib" / "site-packages"
    (site / "scienceworld").mkdir(parents=True)
    (site / "scienceworld" / "__init__.py").write_text("")
    (site / "scienceworld" / "scienceworld.jar").write_bytes(jar)
    info = site / "scienceworld-1.3.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(f"Name: scienceworld\nVersion: {version}\n")
    if archive:
        url = {"url": "file:///x.zip", "archive_info": {"hashes": {"sha256": archive}}}
        (info / "direct_url.json").write_text(json.dumps(url))
    (site / "py4j").mkdir()
    (site / "py4j" / "__init__.py").write_text("")
    (site / "py4j" / "version.py").write_text("__version__ = '0.10.9.9'\n")
    (tmp / "share" / "py4j").mkdir(parents=True)
    (tmp / "share" / "py4j" / "py4j0.10.9.9.jar").write_bytes(b"py4j")
    return site


@pytest.fixture
def isolated_import(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("scienceworld", "py4j"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "path", [p for p in sys.path if "adnn-sw" not in p])
    importlib.invalidate_caches()


def _pin(jar: bytes = b"jar", archive: str = "a" * 64) -> SimulatorPin:
    return dataclasses.replace(
        PINNED, jar_sha256=hashlib.sha256(jar).hexdigest(), source_archive_sha256=archive
    )


@pytest.mark.usefixtures("isolated_import")
def test_missing_package_is_unavailable(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ScienceWorldUnavailableError, match="not importable"):
        resolve_runtime(RuntimeConfig(site_packages=empty))


@pytest.mark.usefixtures("isolated_import")
def test_jar_checksum_is_required_not_just_the_version(tmp_path: Path) -> None:
    site = _fake_site(tmp_path, jar=b"some other build")  # version string is 1.3.0
    with pytest.raises(UnpinnedRuntimeError, match=r"scienceworld\.jar SHA-256"):
        resolve_runtime(RuntimeConfig(site_packages=site))


@pytest.mark.usefixtures("isolated_import")
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [({"version": "1.2.3"}, "package version"), ({"archive": "b" * 64}, "source archive")],
)
def test_version_and_source_archive_are_checked(tmp_path: Path, kwargs: dict, match: str) -> None:
    site = _fake_site(tmp_path, **kwargs)
    with pytest.raises(UnpinnedRuntimeError, match=match):
        resolve_runtime(RuntimeConfig(site_packages=site), pin=_pin())


@pytest.mark.usefixtures("isolated_import")
def test_missing_java_is_unavailable(tmp_path: Path) -> None:
    site = _fake_site(tmp_path, archive="a" * 64)
    no_jdk = tmp_path / "jdk"
    no_jdk.mkdir()
    with pytest.raises(ScienceWorldUnavailableError, match="no Java executable"):
        resolve_runtime(RuntimeConfig(java_home=no_jdk, site_packages=site), pin=_pin())


# -- recipe ----------------------------------------------------------------------------
def test_recipe_is_immutable_normalised_and_round_trips() -> None:
    r = ReplayRecipe(
        "1-1", 0, " teleportAction, openDoors ,teleportAction", actions=("look around",)
    )
    assert r.simplifications == "openDoors,teleportAction"
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.variation = 1  # type: ignore[misc]
    assert ReplayRecipe.from_json(r.to_json()) == r
    assert r.extend("wait1").actions == ("look around", "wait1") and r.actions == ("look around",)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"task": "", "variation": 0},
        {"task": "1-1", "variation": -1},
        {"task": "1-1", "variation": True},
        {"task": "1-1", "variation": 0, "actions": ("",)},
        {"task": "1-1", "variation": 0, "actions": ("a",) * 3, "step_limit": 2},
    ],
)
def test_recipe_validation(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        ReplayRecipe(**kwargs)


def test_recipe_rejects_unknown_fields_and_foreign_pins() -> None:
    d = RECIPE.to_dict()
    with pytest.raises(ValueError, match="unknown recipe fields"):
        ReplayRecipe.from_dict({**d, "label": "irreversible"})
    foreign = dataclasses.replace(
        RECIPE, simulator=dataclasses.replace(PINNED, jar_sha256="0" * 64)
    )
    with pytest.raises(UnpinnedRuntimeError):
        replay(foreign, backend_factory=fake)


# -- session lifecycle -----------------------------------------------------------------
def test_session_lifecycle_and_state_errors() -> None:
    backend = fake()
    session = ScienceWorldSession(backend_factory=lambda: backend)
    with session as s:
        with pytest.raises(SessionStateError):
            s.step("look around")
        s.load("1-1", 0)
        assert s.step("wait1").advanced_time
    assert backend.closed and session.closed and s.process.poll() == 0
    session.close()  # idempotent
    with pytest.raises(SessionStateError):
        s.look()


def test_session_closes_on_exception() -> None:
    backend = fake()
    with (
        pytest.raises(RuntimeError, match="boom"),
        ScienceWorldSession(backend_factory=lambda: backend),
    ):
        raise RuntimeError("boom")
    assert backend.closed and backend._gateway.java_process.poll() == 0


def test_hanging_jvm_is_killed_and_reported() -> None:
    backend = fake(hangs=True)
    with pytest.raises(ProcessLeakError), ScienceWorldSession(backend_factory=lambda: backend) as s:
        s.load("1-1", 0)
    assert backend._gateway.java_process.killed


def test_leak_is_killed_without_masking_the_original_error() -> None:
    backend = fake(hangs=True)
    with pytest.raises(KeyError), ScienceWorldSession(backend_factory=lambda: backend):
        raise KeyError("original")
    assert backend._gateway.java_process.killed


def _jdk(tmp: Path) -> Path:
    (tmp / "jdk" / "bin").mkdir(parents=True)
    (tmp / "jdk" / "bin" / ("java.exe" if os.name == "nt" else "java")).write_bytes(b"")
    return tmp / "jdk"


@pytest.mark.parametrize("path_was_set", [True, False])
def test_launch_context_restores_path_and_cwd_on_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_was_set: bool
) -> None:
    if path_was_set:
        monkeypatch.setenv("PATH", "original")
    else:
        monkeypatch.delenv("PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    config = RuntimeConfig(java_home=_jdk(tmp_path))
    jar_dir = tmp_path / "share"
    jar_dir.mkdir()
    provenance = SimpleNamespace(py4j_jar=str(jar_dir / "py4j.jar"))
    with pytest.raises(RuntimeError, match="boom"), _launch_context(config, provenance):  # type: ignore[arg-type]
        assert Path.cwd() == jar_dir
        assert os.environ["PATH"].startswith(str(config.java_home / "bin") + os.pathsep)
        raise RuntimeError("boom")
    assert Path.cwd() == tmp_path
    assert os.environ.get("PATH") == ("original" if path_was_set else None)


def test_launch_context_restores_path_when_chdir_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "original")
    monkeypatch.chdir(tmp_path)
    config = RuntimeConfig(java_home=_jdk(tmp_path))
    provenance = SimpleNamespace(py4j_jar=str(tmp_path / "missing" / "py4j.jar"))
    with pytest.raises(OSError), _launch_context(config, provenance):  # type: ignore[arg-type]
        pass
    assert Path.cwd() == tmp_path and os.environ["PATH"] == "original"


@pytest.mark.parametrize(
    ("obs", "status"),
    [
        ("No known action matches that input.", "invalid"),
        ("Ambiguous request: Please enter the number", "ambiguous"),
        ("The door is now open.", "accepted"),
    ],
)
def test_classify_observation(obs: str, status: str) -> None:
    assert classify_observation(obs) == status


def test_time_semantics_are_recorded_per_step() -> None:
    with ScienceWorldSession(backend_factory=fake) as s:
        s.load("1-1", 0)
        look, bad, wait = s.step("look around"), s.step("dance"), s.step("wait1")
    assert not look.advanced_time and not bad.advanced_time and bad.status == "invalid"
    assert (wait.moves_before, wait.moves_after) == (0, 2)


# -- canonical state -------------------------------------------------------------------
def _states() -> tuple:
    with ScienceWorldSession(backend_factory=fake) as s:
        s.load("1-1", 0)
        a = capture_state(s)
        s.step("wait1")
        b = capture_state(s)
        s.step("open door to kitchen")
        c = capture_state(s)
        s.step("mix cup")
        d = capture_state(s)
    return a, b, c, d


def test_canonical_keeps_every_field_and_uuid_identity() -> None:
    a, *_ = _states()
    tree_objects = 0
    expected_fields = 0

    def walk(n: dict) -> None:
        nonlocal tree_objects, expected_fields
        tree_objects += 1
        for k, v in n.items():
            if k in ("uuid", "contents"):
                continue
            expected_fields += len(v) if (k.startswith("prop") and isinstance(v, dict)) else 1
        for c in n["contents"].values():
            walk(c)

    walk(a.raw.object_tree)
    assert len(a.canonical.objects) == tree_objects
    assert a.canonical.field_count() == expected_fields + 2 * tree_objects  # + parent, path
    assert set(a.canonical.objects) == {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}
    assert a.canonical.objects["2"]["propContainer.isContainer"] is True  # R4 "true" -> True
    assert a.canonical.objects["6"]["propMaterial.temperatureC"] == 20.0  # R5 exact float
    assert a.canonical.world == {"moves": 0, "agent_location": "hallway"}
    assert a.canonical.visible_doors == {"kitchen": "closed"}


def test_canonical_state_is_explicitly_incomplete() -> None:
    a, *_ = _states()
    assert not a.canonical.is_complete
    assert a.canonical.incomplete_reasons == BASE_INCOMPLETE_REASONS


def test_duplicate_uuid_is_rejected() -> None:
    a, *_ = _states()
    tree = json.loads(json.dumps(a.raw.object_tree))
    tree["contents"]["kitchen-3"]["uuid"] = "2"
    with pytest.raises(ValueError, match="duplicate uuid"):
        canonicalize(dataclasses.replace(a.raw, object_tree=tree))


# -- diagnostics -----------------------------------------------------------------------
def test_canonical_diff_reports_temperatures_creation_and_doors() -> None:
    a, b, c, d = _states()
    first_tick = canonical_diff(a.canonical, b.canonical)
    assert [n for _, n in first_tick.created_objects] == ["water"]
    assert any(ch.key.endswith("propMaterial.temperatureC") for ch in first_tick.changes)
    door = canonical_diff(b.canonical, c.canonical)
    assert any(ch.key == "door:kitchen" and ch.after == "open" for ch in door.changes)
    mix = canonical_diff(c.canonical, d.canonical)
    assert sorted(n for _, n in mix.deleted_objects) == ["sodium chloride", "water"]
    assert [n for _, n in mix.created_objects] == ["salt water"]


def test_ignored_fields_and_tolerances_are_reported_not_hidden() -> None:
    _, b, c, _ = _states()
    full = canonical_diff(b.canonical, c.canonical)
    tol = canonical_diff(b.canonical, c.canonical, tolerances={"propMaterial.temperatureC": 1.0})
    ign = canonical_diff(
        b.canonical, c.canonical, ignore=("propMaterial.temperatureC", "world.moves")
    )
    n_temp = sum(ch.key.endswith("temperatureC") for ch in full.changes)
    assert tol.n_within_tolerance == n_temp and tol.tolerances == {"propMaterial.temperatureC": 1.0}
    assert ign.n_ignored_differences == n_temp + 1 and "world.moves" in ign.ignored_patterns
    assert [ch.key for ch in ign.changes] == ["door:kitchen"]


def test_projection_is_exploratory_and_never_an_exact_equality_claim() -> None:
    a, *_ = _states()
    same = projection_diff(a.canonical, a.canonical, DISCRETE_EXPLORATION)
    assert same.equal_on_observed_fields and same.exploratory
    assert not same.supports_exact_equality_claim  # state representation is incomplete
    assert "Exploration only" in DISCRETE_EXPLORATION.purpose


def test_identical_text_does_not_imply_identical_state() -> None:
    a, b, *_ = _states()
    hybrid = dataclasses.replace(b.raw, look=a.raw.look, inventory=a.raw.inventory)
    assert hybrid.look == a.raw.look
    assert not canonical_diff(a.canonical, canonicalize(hybrid)).equal_on_observed_fields
    assert raw_diff(a.raw, hybrid).changes


# -- replay ----------------------------------------------------------------------------
def test_deterministic_replays_compare_identical() -> None:
    runs = [replay(RECIPE, backend_factory=fake, capture="all") for _ in range(3)]
    assert_reproducible(runs)
    assert [s.result.status for s in runs[0].steps] == ["accepted"] * 4
    assert runs[0].steps[0].phase == "preparation" and runs[0].steps[1].phase == "action"


def test_hidden_divergence_is_detected_with_its_first_step() -> None:
    a = replay(RECIPE, backend_factory=lambda: fake(noise=0.01), capture="all")
    b = replay(RECIPE, backend_factory=lambda: fake(noise=0.01), capture="all")
    cmp = compare_results(a, b)
    assert not cmp.identical and cmp.first_divergent_step == 0
    assert "canonical_state" in cmp.divergent_fields and "observation" not in cmp.divergent_fields
    with pytest.raises(ReplayDivergenceError, match="step 0"):
        assert_reproducible([a, b])


def test_outcome_divergence_is_detected_even_without_state_capture() -> None:
    a = replay(RECIPE, backend_factory=fake)
    tampered = dataclasses.replace(
        a,
        steps=(
            *a.steps[:2],
            dataclasses.replace(
                a.steps[2], result=dataclasses.replace(a.steps[2].result, observation="x")
            ),
            *a.steps[3:],
        ),
    )
    cmp = compare_results(a, tampered)
    assert (cmp.first_divergent_step, cmp.divergent_fields) == (2, ("observation",))


@pytest.mark.parametrize(
    ("action", "status"), [("dance", "invalid"), ("pick up thing", "ambiguous")]
)
def test_invalid_or_ambiguous_recipe_actions_fail(action: str, status: str) -> None:
    with pytest.raises(InvalidReplayActionError, match=status):
        replay(RECIPE.extend(action), backend_factory=fake)
    lax = replay(RECIPE.extend(action), backend_factory=fake, strict=False)
    assert lax.steps[-1].result.status == status


def test_early_episode_end_fails() -> None:
    with pytest.raises(EpisodeTerminatedError):
        replay(RECIPE, backend_factory=lambda: fake(terminate_after=2))


def test_result_round_trip_and_tamper_detection() -> None:
    res = replay(RECIPE, backend_factory=fake, capture="all")
    back = ReplayResult.from_dict(json.loads(json.dumps(res.to_dict())))
    assert compare_results(res, back).identical
    d = res.to_dict()
    d["final_raw"]["moves"] = 999
    with pytest.raises(ValueError, match="fingerprint"):
        ReplayResult.from_dict(d)
    assert isinstance(RawState.from_dict(res.to_dict()["final_raw"]), RawState)
