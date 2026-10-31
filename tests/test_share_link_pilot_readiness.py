"""Phase 5E Task 2: sharing-link pilot readiness (docs/30). No Java; no dataset generated.

End-to-end fixtures are built in memory from one scenario per family and written only to
pytest's temporary directory to exercise ``load_dataset`` / ``validate_directory``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from adnn.dataset import share_link_family as fam
from adnn.dataset.api import DatasetIntegrityError, load_dataset
from adnn.dataset.prompt_versions import SUPPORTED_VERSIONS, UnsupportedPromptBuilderError
from adnn.dataset.schema import sha256_file, write_json, write_jsonl
from adnn.dataset.validation import validate_directory, validate_records
from adnn.feasibility import share_link_diagnostics as sl
from adnn.sandbox import ToolCall
from adnn.sandbox.state import ShareLink

ROOT = Path(__file__).resolve().parents[1]
PLANS = fam.plan_share_scenarios()
FIRST = [next(p for p in PLANS if p.family.family_id == f) for f in fam.FAMILY_IDS]
FROZEN = ROOT / "docs/preregistration/phase5e_pilot_manifest.json"
FROZEN_SHA = ROOT / "docs/preregistration/phase5e_pilot_manifest.sha256"


@pytest.fixture(scope="module")
def built() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records, tool_sets, drops = fam.build_records(FIRST)
    assert not drops
    return records, tool_sets


def _write(
    d: Path, records: list[dict[str, Any]], tool_sets: dict[str, Any], version: str = "1.1.0"
) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    write_jsonl(d / "records.jsonl", records)
    write_json(d / "tool_sets.json", tool_sets)
    files = {
        k: {"file": f, "sha256": sha256_file(d / f)}
        for k, f in (("dataset", "records.jsonl"), ("tool_sets", "tool_sets.json"))
    }
    write_json(
        d / "manifest.json", {"prompt_builder_version": version, "files": files, "split": None}
    )
    return d


# -- A: counts ----------------------------------------------------------------------------------
def test_planned_counts_are_unambiguous_and_match_the_frozen_manifest() -> None:
    counts = fam.planned_counts(PLANS)
    assert (
        counts["families"],
        counts["base_scenarios"],
        counts["minimal_pairs"],
        counts["states"],
        counts["records_if_all_pass_gates"],
    ) == (3, 21, 21, 42, 42)
    assert all(
        v == {"scenarios": 7, "pairs": 7, "states": 14} for v in counts["by_family"].values()
    )
    assert sha256_file(FROZEN) == FROZEN_SHA.read_text("utf-8").split()[0]
    frozen = json.loads(FROZEN.read_text("utf-8"))
    assert frozen["frozen_at_utc"] and frozen["status"].startswith("FROZEN")
    assert frozen["generation"]["planned_counts"] == counts
    assert frozen["generation"]["config_sha256"] == fam.GenerationConfig().sha256()
    confirmed = frozen["freeze_confirmation"]
    assert (confirmed["families"], confirmed["minimal_pairs"], confirmed["records"]) == (3, 21, 42)


# -- B/C: version-aware loading, end to end ---------------------------------------------------
def test_v11_dataset_loads_and_prompts_rebuild_end_to_end(built: Any, tmp_path: Path) -> None:
    records, tool_sets = built
    ds = load_dataset(_write(tmp_path / "ds", records, tool_sets))
    assert len(ds) == 6 and len(ds.minimal_pairs()) == 3
    for r in ds.records:
        assert ds.prompt_builder(r).version == "1.1.0"
        probe = ds.probe_prompt(r)  # hash-checked against the record
        stated = ds.stated_prompt(r)
        assert probe.version == stated.version == "1.1.0"
        assert ds.eval_metadata(r).split == "unsplit"
        system, user = probe.messages[0]["content"], probe.messages[1]["content"]
        assert "create_share_link(" in system and "revoke_share_link(" in system
        if not r["state_struct"].get("share_links"):
            assert "Share links:" in user or "links: -" in user
        for k in r["state_struct"].get("share_links", []):
            assert k["link_id"] in user and k["address"] in user and k["access"] in user
            assert ("custom" if k["custom"] else "generated") in user
            assert ("active" if k["active"] else "revoked") in user
        oracle = r["meta"]["oracle"]
        for w in (oracle["exact_witness"] or []) + (oracle["approx_witness"] or []):
            call = json.dumps(w)
            assert call not in user and call not in stated.messages[1]["content"]
        assert "reversib" not in "\n".join(m["content"] for m in probe.messages).lower()
    with pytest.raises(DatasetIntegrityError, match="no train/test split"):
        list(ds.iter_split("train"))


def test_v11_records_pass_the_validator_including_leakage(built: Any, tmp_path: Path) -> None:
    records, tool_sets = built
    d = _write(tmp_path / "ds", records, tool_sets)
    rep = validate_directory(d, thresholds=fam.LINK_PILOT_THRESHOLDS)
    assert rep.errors == []
    assert rep.checks_run["share_links"] == 6 and rep.checks_run["pairs"] == 3
    assert any("no train/test split" in w for w in rep.warnings)


@pytest.mark.parametrize(
    ("where", "version", "error", "match"),
    [
        ("record", "9.9.9", UnsupportedPromptBuilderError, "unsupported prompt builder version"),
        ("record", None, UnsupportedPromptBuilderError, "unsupported prompt builder version"),
        ("manifest", "2.0.0", UnsupportedPromptBuilderError, "unsupported prompt builder version"),
        ("record", "1.0.0", DatasetIntegrityError, "differs from the manifest"),
    ],
)
def test_loader_rejects_unknown_or_mixed_versions(
    built: Any, tmp_path: Path, where: str, version: str | None, error: type, match: str
) -> None:
    records, tool_sets = copy.deepcopy(built)
    if where == "record":
        records[0]["meta"]["prompt_builder_version"] = version
        d = _write(tmp_path / "ds", records, tool_sets)
    else:
        d = _write(tmp_path / "ds", records, tool_sets, version=str(version))
    with pytest.raises(error, match=match):
        load_dataset(d)


def test_legacy_pilot_loads_exactly_as_before() -> None:
    ds = load_dataset(ROOT / "data/pilot")
    assert SUPPORTED_VERSIONS == ("1.0.0", "1.1.0")
    assert {r["meta"]["prompt_builder_version"] for r in ds.records} == {"1.0.0"}
    assert (len(list(ds.iter_split("train"))), len(list(ds.iter_split("test")))) == (165, 45)
    for r in ds.records[:15]:
        assert ds.prompt_builder(r).version == "1.0.0"
        assert ds.probe_prompt(r).prompt_sha256 == r["meta"]["probe_prompt_sha256"]
        assert ds.stated_prompt(r).prompt_sha256 == r["meta"]["stated_prompt_sha256"]


# -- E: malformed states and allocation failures never enter gold data --------------------------
def test_validator_flags_hidden_links_id_gaps_and_bad_witnesses(built: Any) -> None:
    records, tool_sets = built

    def errors(mutate: Any) -> list[str]:
        rs = copy.deepcopy(records)
        mutate(rs)
        return validate_records(
            rs,
            split=None,
            tool_sets=tool_sets,
            rerun_oracle=False,
            thresholds=fam.LINK_PILOT_THRESHOLDS,
        ).errors

    def as_v10(rs: list[dict[str, Any]]) -> None:
        rs[0]["meta"]["prompt_builder_version"] = "1.0.0"

    def id_gap(rs: list[dict[str, Any]]) -> None:
        rs[0]["state_struct"]["share_links"][-1]["link_id"] = "lnk-0099"

    def bad_witness(rs: list[dict[str, Any]]) -> None:
        r = next(x for x in rs if x["label"] == "partially_reversible")
        r["meta"]["oracle"]["approx_witness"] = []

    def mixed(rs: list[dict[str, Any]]) -> None:
        rs[1]["meta"]["prompt_builder_version"] = "1.0.0"

    assert errors(lambda rs: None) == []
    assert any("mixes prompt builder versions" in e for e in errors(mixed))
    assert any("cannot render share links" in e for e in errors(as_v10))
    assert any("not contiguous" in e for e in errors(id_gap))
    assert any("approx_witness does not restore" in e for e in errors(bad_witness))


def _member(links: tuple[ShareLink, ...], call: ToolCall) -> fam.PairMember:
    return fam.PairMember("x", sl.world(links), call, "Task.", "share_links")


def test_gate_rejects_malformed_and_gapped_states() -> None:
    dup = (sl.custom("lnk-0001", sl.F1, "view"), sl.custom("lnk-0002", sl.F2, "view"))
    revoke = ToolCall("revoke_share_link", {"link_id": "lnk-0001"})
    reason = fam.gold_gate(_member(dup, revoke)).reason
    assert reason is not None and reason.startswith("malformed_state: invalid_state")
    gap = (sl.generated("lnk-0002", sl.F1, "view"),)
    revoke2 = ToolCall("revoke_share_link", {"link_id": "lnk-0002"})
    assert fam.gold_gate(_member(gap, revoke2)).reason == "malformed_state: link_ids_not_contiguous"


def test_allocation_failure_is_named_even_if_the_shape_check_is_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fam, "malformed_reason", lambda state: None)
    gap = (sl.generated("lnk-0002", sl.F1, "view"),)
    create = ToolCall("create_share_link", {"path": sl.F1, "access": "view", "address": ""})
    assert fam.gold_gate(_member(gap, create)).reason == "link_id_allocation_failed"


def test_a_failing_member_drops_its_whole_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    real = fam.gold_gate
    monkeypatch.setattr(
        fam,
        "gold_gate",
        lambda m: fam.GateResult(False, "forced") if m.pivot_value == "generated" else real(m),
    )
    records, _, drops = fam.build_records(FIRST)
    assert {r["template_id"] for r in records} == set(fam.FAMILY_IDS[1:])
    assert drops == {"forced": 1, "pairs_dropped": 1}


# -- D: per-horizon evidence for the horizon-sensitive family ---------------------------------
S03 = [p for p in PLANS if p.family.family_id == "s03_link_create_access_history"]


@pytest.mark.parametrize("plan", S03, ids=lambda p: p.scenario_id)
def test_s03_other_access_evidence_at_each_horizon(plan: fam.ShareScenarioPlan) -> None:
    member = fam.pair_members(plan)[1]
    assert member.pivot_value == "other_access"
    audit = fam.horizon_audit(member.state, member.call)
    assert audit["evidence_ok"]
    rows = audit["by_horizon"]
    for h in ("1", "2"):
        row = rows[h]
        assert row["label"] == "partially_reversible"
        assert 1 <= len(row["approx_witness"]) <= int(h)
        assert row["exact_absent_within_h"] and row["exhaustive_through_h"]
        assert row["residual"] and all("access" in d for d in row["residual"])
    assert rows["3"]["label"] == "reversible" and len(rows["3"]["exact_witness"]) == 3


# -- F: within-pilot diversity and concentration --------------------------------------------
def test_pilot_diversity_reports_both_levels_and_flags_sd1_inflation(built: Any) -> None:
    records, _ = built
    prior = [
        json.loads(x)
        for x in (ROOT / "data/pilot/pilot_v0.1.jsonl").read_text("utf-8").splitlines()
        if x
    ]
    diag = [{"state_struct": c.state.to_dict(), "action_call": c.action} for c in sl.cases()]
    rep = fam.pilot_diversity(records, {"pilot_v0.1": prior}, diag)
    assert rep == fam.pilot_diversity(records, {"pilot_v0.1": prior}, diag)
    assert set(rep["levels"]) == {"strict", "coarse"}
    gates = rep["gates_descriptive"]
    assert gates["SD1_mechanically_inflated"] is True
    assert gates["SD1_novel_coarse_fraction_vs_named_priors"] == 1.0
    assert gates["SD2_max_records_per_coarse_scenario"] == 1
    assert gates["SD3_conflicting_coarse_groups_pooled_with_priors"] == 0
    for c in rep["concentration"].values():
        assert 1 <= c["effective_number"] <= c["distinct"] and 0 < c["max_share"] <= 1
    assert rep["concentration"]["family"]["distinct"] == 3
