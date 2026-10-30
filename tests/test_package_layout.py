"""Scaffolding test: every planned subpackage exists and imports cleanly.

This is the only test that exists at the setup stage. It checks structure,
not behaviour; it must be replaced/extended as modules are implemented.
"""

import importlib

import pytest

import adnn


def test_version_is_string() -> None:
    assert isinstance(adnn.__version__, str)


@pytest.mark.parametrize("name", adnn.SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    module = importlib.import_module(f"adnn.{name}")
    assert module.__doc__, f"adnn.{name} must document its planned responsibility"
