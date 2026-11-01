"""Pinned ScienceWorld runtime: identity verification and provenance (docs/18 §2).

Only ScienceWorld built from commit ``e8216d6`` is accepted. Identity is proven
by the SHA-256 of the bundled ``scienceworld.jar`` (the simulator itself), not
by the package version string. When pip recorded it, the source-archive hash in
``direct_url.json`` must match as well.

Nothing here downloads or installs anything, and nothing changes the global
environment. An isolated runtime is selected explicitly through
:class:`RuntimeConfig` (or the ``ADNN_SW_*`` environment variables):
``site_packages`` is appended to ``sys.path`` of *this process only*, and the JDK
is put on ``PATH`` only while a JVM is being launched (``env.py``).

Importing this module never imports ``scienceworld`` or ``py4j``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class ScienceWorldUnavailableError(RuntimeError):
    """The isolated ScienceWorld runtime (package or Java) cannot be found or run."""


class UnpinnedRuntimeError(RuntimeError):
    """A ScienceWorld runtime was found, but it is not the pinned build."""


@dataclass(frozen=True)
class SimulatorPin:
    """Identity of the only accepted simulator build."""

    source_commit: str
    package_version: str
    jar_sha256: str
    source_archive_sha256: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SimulatorPin:
        return cls(**d)


PINNED = SimulatorPin(
    source_commit="e8216d6044e8e39be9fcb185e3b2dfb602584b52",
    package_version="1.3.0",
    jar_sha256="e77b0fee7d68abe3ca5b12e57d86e2bfe7603f20c5200da0b0f085939faeb465",
    source_archive_sha256="d2c1dc1e5d0d4e4a104424598dce13f64c6e80c523212936f97ea85c871bfae6",
)

ENV_JAVA_HOME = "ADNN_SW_JAVA_HOME"
ENV_SITE_PACKAGES = "ADNN_SW_SITE_PACKAGES"


@dataclass(frozen=True)
class RuntimeConfig:
    """Where the isolated runtime lives. ``None`` means "use this process as it is"."""

    java_home: Path | None = None
    site_packages: Path | None = None

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        def path(name: str) -> Path | None:
            value = os.environ.get(name)
            return Path(value) if value else None

        return cls(java_home=path(ENV_JAVA_HOME), site_packages=path(ENV_SITE_PACKAGES))


@dataclass(frozen=True)
class RuntimeProvenance:
    """Everything needed to say exactly which simulator produced a result."""

    pin: SimulatorPin
    package_version: str
    package_dir: str
    jar_sha256: str
    source_archive_sha256: str | None
    source_archive_url: str | None
    java_executable: str
    java_version: tuple[str, ...]
    py4j_version: str
    py4j_jar: str
    py4j_jar_sha256: str
    python_version: str
    platform: str
    site_packages: str | None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["java_version"] = list(self.java_version)
        return d


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def java_executable(config: RuntimeConfig) -> Path:
    if config.java_home is not None:
        name = "java.exe" if os.name == "nt" else "java"
        exe = config.java_home / "bin" / name
        if not exe.is_file():
            raise ScienceWorldUnavailableError(f"no Java executable at {exe}")
        return exe
    found = shutil.which("java")
    if found is None:
        raise ScienceWorldUnavailableError(
            f"Java not found: set {ENV_JAVA_HOME} to a JDK directory (nothing is installed "
            "automatically)"
        )
    return Path(found)


def ensure_importable(config: RuntimeConfig) -> None:
    """Make the isolated site-packages importable in this process only (opt-in)."""
    if config.site_packages is None:
        return
    if not config.site_packages.is_dir():
        raise ScienceWorldUnavailableError(f"{ENV_SITE_PACKAGES} is not a directory")
    entry = str(config.site_packages)
    if entry not in sys.path:
        sys.path.append(entry)


def resolve_runtime(
    config: RuntimeConfig | None = None, *, pin: SimulatorPin = PINNED
) -> RuntimeProvenance:
    """Locate and verify the runtime without launching a JVM.

    Raises :class:`ScienceWorldUnavailableError` if the package or Java is
    missing, and :class:`UnpinnedRuntimeError` if the build is not ``pin``.
    """
    config = config or RuntimeConfig.from_env()
    ensure_importable(config)
    spec = importlib.util.find_spec("scienceworld")
    if spec is None or spec.origin is None:
        raise ScienceWorldUnavailableError(
            f"package 'scienceworld' is not importable; set {ENV_SITE_PACKAGES} to the "
            "site-packages of the isolated ScienceWorld venv"
        )
    package_dir = Path(spec.origin).parent
    jar = package_dir / "scienceworld.jar"
    if not jar.is_file():
        raise UnpinnedRuntimeError(f"no scienceworld.jar in {package_dir}")
    jar_sha = sha256_file(jar)
    if jar_sha != pin.jar_sha256:
        raise UnpinnedRuntimeError(
            f"scienceworld.jar SHA-256 {jar_sha} is not the pinned build {pin.jar_sha256} "
            f"(commit {pin.source_commit[:7]})"
        )

    version, archive_sha, archive_url = _dist_info(package_dir.parent)
    if version != pin.package_version:
        raise UnpinnedRuntimeError(f"package version {version!r} != {pin.package_version!r}")
    if archive_sha is not None and archive_sha != pin.source_archive_sha256:
        raise UnpinnedRuntimeError(
            f"installed from source archive {archive_sha}, expected {pin.source_archive_sha256}"
        )

    py4j_version, py4j_jar = locate_py4j_jar()

    exe = java_executable(config)
    try:
        proc = subprocess.run([str(exe), "-version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ScienceWorldUnavailableError(f"cannot run {exe}: {exc}") from exc
    java_version = tuple((proc.stderr or proc.stdout).strip().splitlines()[:3])
    if proc.returncode != 0 or not java_version:
        raise ScienceWorldUnavailableError(f"{exe} -version failed")

    return RuntimeProvenance(
        pin=pin,
        package_version=version,
        package_dir=str(package_dir),
        jar_sha256=jar_sha,
        source_archive_sha256=archive_sha,
        source_archive_url=archive_url,
        java_executable=str(exe),
        java_version=java_version,
        py4j_version=py4j_version,
        py4j_jar=str(py4j_jar),
        py4j_jar_sha256=sha256_file(py4j_jar),
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        site_packages=str(config.site_packages) if config.site_packages else None,
    )


def locate_py4j_jar() -> tuple[str, Path]:
    """Find the py4j gateway JAR that belongs to the importable ``py4j`` package.

    py4j searches the current directory, ``sys.prefix/share/py4j`` and a few fixed
    relative paths. When this interpreter is not the isolated venv's own (e.g. the
    project ``.venv`` with ``site_packages`` configured), none of those match, so the
    JAR is located here explicitly and handed to the launch (``env.py``).
    """
    spec = importlib.util.find_spec("py4j")
    if spec is None or spec.origin is None:
        raise ScienceWorldUnavailableError("package 'py4j' is not importable")
    pkg = Path(spec.origin).parent
    match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", (pkg / "version.py").read_text("utf-8"))
    if match is None:
        raise ScienceWorldUnavailableError("cannot read the py4j version")
    version = match.group(1)
    name = f"py4j{version}.jar"
    candidates = [
        pkg.parent.parent.parent / "share" / "py4j" / name,  # Windows venv: Lib/site-packages
        pkg.parent.parent.parent.parent
        / "share"
        / "py4j"
        / name,  # POSIX: lib/pythonX/site-packages
        Path(sys.prefix) / "share" / "py4j" / name,
    ]
    for c in candidates:
        if c.is_file():
            return version, c
    raise ScienceWorldUnavailableError(f"py4j gateway JAR {name} not found near {pkg}")


def _dist_info(site_dir: Path) -> tuple[str | None, str | None, str | None]:
    infos = sorted(site_dir.glob("scienceworld-*.dist-info"))
    if len(infos) != 1:
        return None, None, None
    info = infos[0]
    version = None
    for line in (info / "METADATA").read_text(encoding="utf-8").splitlines():
        if line.startswith("Version:"):
            version = line.split(":", 1)[1].strip()
            break
    archive_sha = archive_url = None
    direct = info / "direct_url.json"
    if direct.is_file():
        data = json.loads(direct.read_text(encoding="utf-8"))
        archive_url = data.get("url")
        archive_sha = (data.get("archive_info") or {}).get("hashes", {}).get("sha256")
    return version, archive_sha, archive_url
