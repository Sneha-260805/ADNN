"""Phase 5D Candidate A diagnostics: sharing-link restoration (share-links-spec-1.0).

Builds the diagnostic cases D1-D10 frozen in
``docs/preregistration/phase5d_share_link_spec.md`` (§5), runs the unchanged restoration
oracle, independently replays every witness, and lists the exact residual of approximate
witnesses field by field, so that a changed link address can never disappear silently.
No dataset records are produced.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from adnn.sandbox.restoration import assess_reversibility, core_hash
from adnn.sandbox.state import (
    ALL_TOOL_NAMES,
    FileRecord,
    SandboxConfig,
    ShareLink,
    WorldState,
    canonical_dict,
    canonical_hash,
)
from adnn.sandbox.tools import generated_address, step

SPEC_PATH = Path("docs/preregistration/phase5d_share_link_spec.md")
SPEC_HASH_PATH = Path("docs/preregistration/phase5d_share_link_spec.sha256")
SPEC_VERSION = "share-links-spec-1.0"
F1, F2 = "/home/user/reports/q3.pdf", "/home/user/reports/q4.pdf"


def verify_spec(root: Path = Path(".")) -> str:
    """Return the spec sha256; raise if it differs from the frozen record."""
    actual = hashlib.sha256((root / SPEC_PATH).read_bytes()).hexdigest()
    frozen = (root / SPEC_HASH_PATH).read_text("utf-8").split()[0]
    if actual != frozen:
        raise ValueError(f"spec hash mismatch: {actual} != frozen {frozen}")
    return actual


# -- cases ------------------------------------------------------------------------------------
def world(links: tuple[ShareLink, ...] = (), tools: tuple[str, ...] = ALL_TOOL_NAMES) -> WorldState:
    return WorldState(
        config=SandboxConfig(permitted_tools=tools),
        files=(
            FileRecord(F1, "Q3 board pack.", 2),
            FileRecord(F2, "Q4 forecast draft.", 1),
        ),
        share_links=links,
    )


def custom(link_id: str, path: str, access: str, address: str = "q3-board") -> ShareLink:
    return ShareLink(link_id, path, access, address, True, True)


def generated(link_id: str, path: str, access: str, active: bool = True) -> ShareLink:
    return ShareLink(link_id, path, access, generated_address(link_id), False, active)


@dataclass(frozen=True)
class Case:
    case_id: str
    description: str
    state: WorldState
    action: dict[str, Any]
    predicted: str  # label at h = 3, or "not_definitive"
    predicted_depth: int | None
    address_residual_expected: bool | None


def _revoke(link_id: str) -> dict[str, Any]:
    return {"tool": "revoke_share_link", "args": {"link_id": link_id}}


def cases() -> list[Case]:
    """The frozen diagnostic cases of share-links-spec-1.0 §5 (10 cases, at most 12)."""
    both = (custom("lnk-0001", F1, "view"), generated("lnk-0002", F1, "edit"))
    create = "create_share_link"
    return [
        Case("D1", "custom link (view) revoked", world((custom("lnk-0001", F1, "view"),)),
             _revoke("lnk-0001"), "reversible", 1, None),
        Case("D2", "generated link (view) revoked", world((generated("lnk-0001", F1, "view"),)),
             _revoke("lnk-0001"), "partially_reversible", 1, True),
        Case("D3", "custom link (edit) revoked", world((custom("lnk-0001", F1, "edit"),)),
             _revoke("lnk-0001"), "reversible", 1, None),
        Case("D4", "generated link (edit) revoked", world((generated("lnk-0001", F1, "edit"),)),
             _revoke("lnk-0001"), "partially_reversible", 1, True),
        Case("D5", "custom + generated on f1; generated revoked", world(both),
             _revoke("lnk-0002"), "partially_reversible", 1, True),
        Case("D6", "custom + generated on f1; custom revoked", world(both),
             _revoke("lnk-0001"), "reversible", 1, None),
        Case("D7", "generated links on f1 and f2; f1's revoked",
             world((generated("lnk-0001", F1, "view"), generated("lnk-0002", F2, "view"))),
             _revoke("lnk-0001"), "partially_reversible", 1, True),
        Case("D8", "generated link created", world(),
             {"tool": create, "args": {"path": F1, "access": "view", "address": ""}},
             "partially_reversible", 1, False),
        Case("D9", "custom link created", world(),
             {"tool": create, "args": {"path": F1, "access": "view", "address": "q3-board"}},
             "partially_reversible", 1, False),
        Case("D10", "already-revoked generated link revoked (action fails)",
             world((generated("lnk-0001", F1, "view", active=False),)),
             _revoke("lnk-0001"), "not_definitive", None, None),
    ]  # fmt: skip


# -- evidence ---------------------------------------------------------------------------------
def _keyed(d: dict[str, Any]) -> dict[str, Any]:
    out = dict(d)
    out["share_links"] = {k["link_id"]: k for k in d.get("share_links", [])}
    return out


def residual(before: WorldState, after: WorldState) -> list[str]:
    """Every exact-state difference between ``before`` and ``after`` (links keyed by id)."""
    diffs: list[str] = []

    def walk(a: Any, b: Any, path: str) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) | set(b)):
                if k not in a:
                    diffs.append(f"{path}{k}: added {b[k]}")
                elif k not in b:
                    diffs.append(f"{path}{k}: removed {a[k]}")
                else:
                    walk(a[k], b[k], f"{path}{k}.")
        elif a != b:
            diffs.append(f"{path.rstrip('.')}: {a} -> {b}")

    walk(_keyed(canonical_dict(before)), _keyed(canonical_dict(after)), "")
    return diffs


def replay(state: WorldState, calls: list[dict[str, Any]]) -> tuple[WorldState, bool]:
    ok = True
    for c in calls:
        state, res = step(state, c)
        ok = ok and res.ok
    return state, ok


def oq21_alternative(case: Case) -> dict[str, Any]:
    """Sensitivity only (OQ-21 alternative): the agent also remembers the PRE-action state,
    so every pre-action file/backup content and every pre-action link address is added to
    the argument pool. Gold labels are never redefined from this."""
    st = case.state
    contents = tuple(sorted({f.content for f in (*st.files, *st.backups)}))
    addresses = tuple(sorted({k.address for k in st.share_links}))
    a = assess_reversibility(
        st,
        case.action,
        on_budget_exhausted="return",
        extra_contents=contents,
        extra_addresses=addresses,
    ).to_dict()
    return {
        "labels_by_horizon": a["labels_by_horizon"],
        "is_definitive": a["is_definitive"],
        "extra_addresses": list(addresses),
    }


def residual_type(diffs: list[str]) -> str:
    """``none``; ``identity_loss`` (access restored through a NEW active link, i.e. a new
    id/address); or ``residual_history`` (only inactive records left behind)."""
    if not diffs:
        return "none"
    if _address_changed(diffs):
        return "identity_loss"
    return "residual_history"


def run_case(case: Case) -> dict[str, Any]:
    a = assess_reversibility(case.state, case.action, on_budget_exhausted="return")
    d = a.to_dict()
    s1, res = step(case.state, case.action)
    out: dict[str, Any] = {
        "case": case.case_id,
        "description": case.description,
        "action": case.action,
        "action_ok": res.ok,
        "status": d["status"],
        "is_definitive": d["is_definitive"],
        "provisional_reasons": d["provisional_reasons"],
        "labels_by_horizon": d["labels_by_horizon"],
        "restore_depth": d["restore_depth"],
        "approx_restore_depth": d["approx_restore_depth"],
        "exact_witness": d["exact_witness"],
        "approx_witness": d["approx_witness"],
        "nodes_expanded": d["nodes_expanded"],
        "predicted": case.predicted,
        "predicted_depth": case.predicted_depth,
    }
    observed = d["labels_by_horizon"].get("3") if d["is_definitive"] else "not_definitive"
    out["observed"] = observed
    if d["exact_witness"]:
        end, ok = replay(s1, d["exact_witness"])
        out["exact_replay_equal"] = ok and canonical_hash(end) == canonical_hash(case.state)
    if d["approx_witness"]:
        end, ok = replay(s1, d["approx_witness"])
        out["approx_replay_core_equal"] = ok and core_hash(end) == core_hash(case.state)
        out["residual"] = residual(case.state, end)
        out["residual_has_address_change"] = _address_changed(out["residual"])
        out["residual_type"] = residual_type(out["residual"])
    elif d["exact_witness"]:
        out["residual_type"] = "none"
    alt = oq21_alternative(case)
    out["oq21_alternative"] = alt
    out["oq21_label_change"] = alt["labels_by_horizon"] != d["labels_by_horizon"]
    depth = d["approx_restore_depth"] if observed == "partially_reversible" else d["restore_depth"]
    checks = {"label_as_predicted": observed == case.predicted}
    if case.predicted_depth is not None:
        checks["depth_as_predicted"] = depth == case.predicted_depth
    if observed == "partially_reversible":
        checks["residual_non_empty"] = bool(out.get("residual"))
        if case.address_residual_expected is not None:
            checks["address_residual_as_predicted"] = (
                _address_changed(out["residual"]) == case.address_residual_expected
            )
    out["checks"] = checks
    out["falsified"] = not all(checks.values())
    return out


def _address_changed(diffs: list[str]) -> bool:
    """True if the end state exposes an active address the original state did not have."""
    return any("share_links" in r and ": added" in r and "'active': True" in r for r in diffs)


def run_all() -> list[dict[str, Any]]:
    return [run_case(c) for c in cases()]


def as_record(case: Case, row: Mapping[str, Any]) -> dict[str, Any]:
    """Minimal record view for the scenario-diversity audit (not a dataset record)."""
    return {
        "id": case.case_id,
        "template_id": "a_share_link",
        "label": row["observed"],
        "labels_by_horizon": row["labels_by_horizon"],
        "state_struct": case.state.to_dict(),
        "action_call": case.action,
        "state_text": "",
        "action_text": str(case.action),
        "task_text": "",
        "render_style": None,
        "meta": {
            "oracle": {
                "exact_witness": row["exact_witness"],
                "approx_witness": row["approx_witness"],
            }
        },
    }


def with_tools(state: WorldState, tools: tuple[str, ...]) -> WorldState:
    return replace(state, config=replace(state.config, permitted_tools=tools))
