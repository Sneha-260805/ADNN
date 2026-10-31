"""Phase 5C: scenario-level diversity identifiers and audit (no Java; docs/27)."""

from __future__ import annotations

import copy
from typing import Any

from adnn.feasibility import scenario_diversity as sd
from adnn.feasibility.scaling_pilot import structure_signature

CONFIG = {"recycle_bin_enabled": True, "payment_mode": "final", "refund_fee": 5}


def rec(
    path: str = "/home/user/docs/a.txt",
    other: str = "/home/user/docs/b.txt",
    content: str = "Agenda: budget.",
    backup: str | None = None,
    balance: int = 200,
    amount: int = 50,
    tool: str = "delete_file",
    config: dict[str, Any] | None = None,
    witness: list[dict[str, Any]] | None = None,
    label: str = "reversible",
    rid: str = "r",
    wording: str = "Delete",
) -> dict[str, Any]:
    files = [
        {"path": path, "content": content, "revision": 2, "history": []},
        {"path": other, "content": "Other notes.", "revision": 3, "history": []},
    ]
    args: dict[str, Any] = (
        {"path": path}
        if tool == "delete_file"
        else {"amount": amount, "from_account": "main", "to": "acme"}
    )
    return {
        "id": rid,
        "template_id": "fam",
        "label": label,
        "labels_by_horizon": {"1": label, "2": label, "3": label},
        "state_struct": {
            "config": config or CONFIG,
            "clock_s": 0,
            "counters": {"next_payment": 1},
            "files": files,
            "backups": [{"path": path, "content": backup, "revision": 1, "history": []}]
            if backup is not None
            else [],
            "accounts": [{"account_id": "main", "balance": balance}],
            "payees": ["acme"],
        },
        "action_call": {"tool": tool, "args": args},
        "state_text": f"Files: {path}, {other}. Balance {balance}.",
        "action_text": f"{wording} {path}" if tool == "delete_file" else f"Pay {amount}",
        "task_text": "Tidy up.",
        "render_style": "kv",
        "meta": {"oracle": {"exact_witness": witness or [], "approx_witness": witness or []}},
    }


RESTORE = [{"tool": "restore_file", "args": {"entry_id": "bin-0001"}}]


def ids(r: dict[str, Any]) -> tuple[str, str]:
    return sd.scenario_id(r, "strict"), sd.scenario_id(r, "coarse")


# -- identical scenarios, cosmetic changes --------------------------------------------------------
def test_changed_filenames_keep_the_scenario() -> None:
    a = rec(witness=RESTORE)
    b = rec(path="/srv/x/report.md", other="/srv/x/notes.csv", witness=RESTORE)
    assert ids(a) == ids(b)
    assert (
        sd.recovery_signature_id(a)
        == sd.recovery_signature_id(b)
        == "delete_file|exact:restore_file"
    )
    assert sd.surface_ids(a)["surface"] != sd.surface_ids(b)["surface"]


def test_list_order_does_not_change_the_scenario() -> None:
    a = rec()
    b = copy.deepcopy(a)
    b["state_struct"]["files"].reverse()
    assert ids(a) == ids(b)


def test_changed_amounts_keep_the_scenario_while_order_is_preserved() -> None:
    a = rec(tool="transfer_money", amount=50, balance=200)
    b = rec(tool="transfer_money", amount=70, balance=300)
    assert ids(a) == ids(b)
    # amount now exceeds the balance: numeric order differs, equality pattern does not
    c = rec(tool="transfer_money", amount=500, balance=200)
    assert sd.scenario_id(a, "strict") != sd.scenario_id(c, "strict")
    assert sd.scenario_id(a, "coarse") == sd.scenario_id(c, "coarse")


def test_changed_wording_keeps_scenario_and_changes_only_surface() -> None:
    a, b = rec(wording="Delete"), rec(wording="Please remove the file")
    assert ids(a) == ids(b)
    assert sd.surface_ids(a)["template"] != sd.surface_ids(b)["template"]


# -- genuinely different scenarios and recovery signatures -------------------------------------
def test_different_configuration_is_a_different_scenario_and_signature() -> None:
    on = rec(witness=RESTORE, label="reversible")
    off = rec(config={**CONFIG, "recycle_bin_enabled": False}, label="irreversible")
    assert sd.scenario_id(on, "coarse") != sd.scenario_id(off, "coarse")
    assert sd.recovery_signature_id(off) == "delete_file|none"
    assert sd.recovery_signature_id(on) != sd.recovery_signature_id(off)


def test_different_action_tool_is_a_different_recovery_signature() -> None:
    assert sd.recovery_signature_id(rec()) != sd.recovery_signature_id(rec(tool="transfer_money"))
    two_step = [{"tool": "request_cancellation", "args": {}}, {"tool": "confirm_cancellation"}]
    m = sd.recovery_signature_id(rec(tool="transfer_money", witness=two_step))
    assert m == "transfer_money|exact:request_cancellation>confirm_cancellation"


def test_approximate_route_used_only_without_exact_witness() -> None:
    r = rec(tool="transfer_money")
    r["meta"]["oracle"] = {"exact_witness": None, "approx_witness": [{"tool": "request_refund"}]}
    assert sd.recovery_signature_id(r) == "transfer_money|approx:request_refund"


def test_equality_relations_separate_scenarios_the_old_heuristic_merges() -> None:
    same = rec(backup="Agenda: budget.")  # backup equals the current file
    stale = rec(backup="Old agenda.")  # backup differs
    assert structure_signature(same) == structure_signature(stale)
    assert sd.scenario_id(same, "coarse") != sd.scenario_id(stale, "coarse")


# -- audit --------------------------------------------------------------------------------------
def test_audit_counts_cross_dataset_reuse_and_reports_conflicts() -> None:
    prior = [rec(rid="p1", witness=RESTORE)]
    later = [
        rec(rid="n1", path="/z/q.txt", witness=RESTORE),  # cosmetic copy of p1
        rec(rid="n2", config={**CONFIG, "recycle_bin_enabled": False}, label="irreversible"),
        # same canonical scenario as p1 but different label: a canonicalisation conflict
        rec(rid="n3", path="/y/w.txt", label="irreversible"),
    ]
    rep = sd.audit({"prior": prior, "later": later}, gold={"later": lambda r: r["id"] != "n3"})
    cross = rep["cross"]["later_vs_prior"]
    assert cross["scenario_coarse"]["records_reusing_prior"] == 2
    assert cross["scenario_coarse"]["gold_records_reusing_prior"] == 1
    assert cross["scenario_coarse"]["novel_ids"] == 1
    assert len(cross["pooled_conflicts"]["strict"]) == 1
    assert rep["uncertainty"]["strict_conflicts"] == 1
    check = sd.prospective_gate_values(rep, "later")
    assert check["status"].startswith("descriptive only")
    assert "passed" not in check and "triggered" not in check
    assert check["SD3_behaviourally_conflicting_groups"] == 1
    assert "SD4" in check["deferred"] and not any(k.startswith("SD4") for k in check)


def test_audit_is_deterministic() -> None:
    data = {"a": [rec(rid="1")], "b": [rec(rid="2", amount=9, tool="transfer_money")]}
    assert sd.audit(data) == sd.audit(copy.deepcopy(data))
