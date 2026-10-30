"""The demo shows the same delete_file action with different reversibility."""

from __future__ import annotations

import pytest

from adnn import demo


def test_demo_output(capsys: pytest.CaptureFixture[str]) -> None:
    demo.main()
    out = capsys.readouterr().out
    a, b = out.split("=== Scenario B")
    assert "'3': 'reversible'" in a and "restore_file -> ok=True" in a
    assert "Canonical state equal to the initial state: True" in a
    assert "'3': 'irreversible'" in b and "error=not_found" in b
    assert "Canonical state equal to the initial state: False" in b
