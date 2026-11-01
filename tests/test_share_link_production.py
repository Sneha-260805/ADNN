"""Phase 5G: production marking of sharing-link records and the manifest-declared partial
policy of the validator (ADR-0008; docs/33 §5). No Java, nothing written outside tmp_path."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from adnn.dataset import share_link_family as fam
from adnn.dataset import share_link_production as slp
from adnn.dataset.schema import (
    PROVISIONAL_OQ21,
    PROVISIONAL_PARTIAL,
    sha256_file,
    write_json,
    write_jsonl,
)
from adnn.dataset.validation import (
    PARTIAL_POLICY_PENDING,
    PARTIAL_POLICY_TEAM,
    validate_directory,
    validate_records,
)
from adnn.feasibility.scaling_pilot import PARTIAL_RULE

ROOT = Path(__file__).resolve().parents[1]
CFG = replace(fam.GenerationConfig(), scenarios_per_family=1)
PLANS = fam.plan_share_scenarios(CFG)


@pytest.fixture(scope="module")
def production() -> tuple[list[dict], dict]:
    records, tool_sets, drops = slp.build_production_records(PLANS, "test-production")
    assert not drops
    return records, tool_sets


def _provisional_errors(rep) -> list[str]:
    return [e for e in rep.errors if e.startswith("[provisional]")]


def _policy_errors(rep) -> list[str]:
    return [e for e in rep.errors if e.startswith(("[schema]", "[provisional]"))]


UNEXPECTED_TIERS = "unexpected ['sensitivity_group', 'tier']"


def test_production_records_use_the_team_adopted_marking(production) -> None:
    records, _ = production
    assert len(records) == 2 * len(PLANS)
    assert any("partially_reversible" in r["labels_by_horizon"].values() for r in records)
    for r in records:
        assert PROVISIONAL_PARTIAL not in r["provisional_reasons"]
        assert r["meta"]["partial_definition"] == PARTIAL_RULE
        assert r["meta"]["generator_version"] == slp.GENERATOR_VERSION
        assert r["dataset_version"] == "test-production"
        alt = r["meta"]["oq21_alternative_labels_by_horizon"]
        assert alt is not None  # computed, not asserted
        sensitive = alt != r["labels_by_horizon"]
        assert r["tier"] == ("P" if sensitive else "G")
        assert (PROVISIONAL_OQ21 in r["provisional_reasons"]) is sensitive
        assert r["label_provisional"] is bool(r["provisional_reasons"])


def test_the_frozen_pilot_generator_is_unchanged() -> None:
    records, _, _ = fam.build_records(PLANS)
    partial = [r for r in records if "partially_reversible" in r["labels_by_horizon"].values()]
    assert partial and all(PROVISIONAL_PARTIAL in r["provisional_reasons"] for r in partial)
    assert all(r["meta"]["oq21_alternative_labels_by_horizon"] is None for r in records)
    assert fam.GENERATOR_VERSION == "share-link-gen-0.2-draft"


def test_validator_policies_are_distinct(production) -> None:
    records, tool_sets = production
    kw = {"split": None, "tool_sets": tool_sets, "rerun_oracle": False}
    assert not _policy_errors(validate_records(records, partial_policy=PARTIAL_POLICY_TEAM, **kw))
    pending = _policy_errors(validate_records(records, **kw))  # tier fields are not allowed
    assert len(pending) == len(records) and all(UNEXPECTED_TIERS in e for e in pending)
    pilot_form, pilot_tools, _ = fam.build_records(PLANS)
    missing = _policy_errors(
        validate_records(
            pilot_form,
            split=None,
            tool_sets=pilot_tools,
            rerun_oracle=False,
            partial_policy=PARTIAL_POLICY_TEAM,
        )
    )
    assert len(missing) == len(pilot_form) and all("missing ['tier'" in e for e in missing)
    tiered = [{**r, "tier": "G", "sensitivity_group": None} for r in pilot_form]
    team = _provisional_errors(
        validate_records(
            tiered,
            split=None,
            tool_sets=pilot_tools,
            rerun_oracle=False,
            partial_policy=PARTIAL_POLICY_TEAM,
        )
    )
    assert any("obsolete pending-professor" in e for e in team)
    assert any("OQ-21 alternative not computed" in e for e in team)
    with pytest.raises(ValueError, match="unknown partial_definition_policy"):
        validate_records(records, partial_policy="anything", **kw)


def test_validator_rejects_inconsistent_tiers(production) -> None:
    records, tool_sets = production
    bad = [{**records[0], "tier": "P"}, *records[1:]]
    errors = _provisional_errors(
        validate_records(
            bad,
            split=None,
            tool_sets=tool_sets,
            rerun_oracle=False,
            partial_policy=PARTIAL_POLICY_TEAM,
        )
    )
    assert any("tier inconsistent" in e for e in errors)


def test_validate_directory_reads_the_manifest_policy(production, tmp_path: Path) -> None:
    records, tool_sets = production
    write_jsonl(tmp_path / "records.jsonl", records)
    write_json(tmp_path / "tool_sets.json", tool_sets)

    def manifest(policy: str | None) -> None:
        m = {
            "prompt_builder_version": "1.1.0",
            "split": None,
            "files": {
                "dataset": {
                    "file": "records.jsonl",
                    "sha256": sha256_file(tmp_path / "records.jsonl"),
                },
                "tool_sets": {
                    "file": "tool_sets.json",
                    "sha256": sha256_file(tmp_path / "tool_sets.json"),
                },
            },
        }
        if policy is not None:
            m["partial_definition_policy"] = policy
        write_json(tmp_path / "manifest.json", m)

    manifest(PARTIAL_POLICY_TEAM)
    assert not _policy_errors(validate_directory(tmp_path, rerun_oracle=False))
    for policy in (None, PARTIAL_POLICY_PENDING):  # absent key = the original convention
        manifest(policy)
        errors = _policy_errors(validate_directory(tmp_path, rerun_oracle=False))
        assert errors and all(UNEXPECTED_TIERS in e for e in errors)


@dataclass
class _FakeAssessment:
    is_definitive: bool
    labels: dict[str, str]

    def labels_by_horizon(self, horizons) -> dict[str, str]:
        return self.labels


def test_oq21_sensitive_records_become_tier_p_and_undetermined_pairs_drop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = PLANS[0]
    changed = {"1": "irreversible", "2": "irreversible", "3": "irreversible"}
    monkeypatch.setattr(slp, "oq21_alternative", lambda s, c: _FakeAssessment(True, changed))
    records, _, drops = slp.build_production_records([plan], "x")
    assert len(records) == 2 and not drops
    for r in records:
        assert r["tier"] == "P" and r["sensitivity_group"] == "OQ-21"
        assert PROVISIONAL_OQ21 in r["provisional_reasons"] and r["label_provisional"]
    monkeypatch.setattr(slp, "oq21_alternative", lambda s, c: _FakeAssessment(False, changed))
    records, _, drops = slp.build_production_records([plan], "x")
    assert records == [] and drops["oq21_alternative_not_definitive"] == 1


def test_frozen_phase5e_artifacts_are_untouched() -> None:
    sidecar = (ROOT / "docs/preregistration/phase5e_pilot_manifest.sha256").read_text("utf-8")
    frozen = ROOT / "docs/preregistration/phase5e_pilot_manifest.json"
    assert sha256_file(frozen) == sidecar.split()[0]
