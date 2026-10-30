"""Restoration semantics: exact vs approximate restoration vs irreversible effects.

Formal definitions (docs/10_SANDBOX_DESIGN.md §5). For a state ``s`` and an
agent action ``a`` with ``s1 = step(s, a)``:

* ``restore_depth`` = the smallest ``k`` such that some sequence of ``k`` agent
  actions from the finite action domain ``D`` (§5.3) leads from ``s1`` to a
  state whose **canonical state** equals that of ``s``. The canonical state
  excludes only the clock and the id/step counters; the audit log is not part
  of the state at all.
* ``approx_restore_depth`` = the same with the weaker **core relation**: file
  contents, backup contents, outbox messages, cost-adjusted balances, open
  payments, payees and configuration must match; revision numbers, version
  history, recycle-bin contents and closed (refunded) payment records may
  differ. Refund fees are added back to balances, so restoring money *at a
  documented cost* counts as approximate, and compensation never counts as
  exact.

Label at horizon ``h``: ``reversible`` if ``restore_depth <= h``;
``partially_reversible`` else if ``approx_restore_depth <= h``;
``irreversible`` otherwise.

The breadth-first search is **complete over D up to the horizon**: every
permitted tool is enumerated over its full argument domain, and one explicit
*wait* successor stands for every action that changes nothing but time
(failed calls and ``read_file``), which ``step`` maps to the identical state.
Running out of node budget is reported as ``SearchStatus.BUDGET_EXHAUSTED``
and never as a label beyond the fully searched depth.

This module defines the *sandbox* semantics only. The ScienceWorld definition
of approximate restoration is open (OQ-03) and is not implied by this code.
The definitions marked provisional in docs/10 §5 (OQ-21, OQ-22, OQ-23) are
implemented as documented defaults, not as settled decisions.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from adnn.sandbox.state import WorldState, canonical_hash, full_hash
from adnn.sandbox.tools import ToolCall, step


class Label(StrEnum):
    REVERSIBLE = "reversible"
    PARTIALLY_REVERSIBLE = "partially_reversible"
    IRREVERSIBLE = "irreversible"


class SearchStatus(StrEnum):
    COMPLETE = "complete"  # all of D up to the horizon (or the first exact hit) searched
    BUDGET_EXHAUSTED = "budget_exhausted"  # stopped early; see complete_through_depth


DEFAULT_HORIZONS: tuple[int, ...] = (1, 2, 3)
UNDETERMINED = "undetermined"

PROVISIONAL_ACTION_FAILED = "judged_action_failed"
PROVISIONAL_PENDING_TIMERS = "pending_timers_before_action:OQ-22"


class SearchLimitError(RuntimeError):
    """The restoration search expanded more nodes than allowed."""


class UndeterminedLabelError(RuntimeError):
    """The label at this horizon was not determined (search budget exhausted)."""


def label_from_depths(restore_depth: int | None, approx_depth: int | None, horizon: int) -> Label:
    if restore_depth is not None and restore_depth <= horizon:
        return Label.REVERSIBLE
    if approx_depth is not None and approx_depth <= horizon:
        return Label.PARTIALLY_REVERSIBLE
    return Label.IRREVERSIBLE


# -- core (approximate) relation --------------------------------------------------
def core_projection(state: WorldState) -> dict[str, Any]:
    """The part of the state that must match for *approximate* restoration."""
    fees: dict[str, int] = {}
    for p in state.payments:
        if p.status == "refunded":
            fees[p.from_account] = fees.get(p.from_account, 0) + p.fee_charged
    return {
        "config": asdict(state.config),
        "files": {f.path: f.content for f in state.files},
        "backups": {b.path: b.content for b in state.backups},
        "outbox": sorted([m.to, m.subject, m.body, m.status] for m in state.outbox),
        "accounts": {a.account_id: a.balance + fees.get(a.account_id, 0) for a in state.accounts},
        "payees": list(state.payees),
        "open_payments": sorted(
            [p.from_account, p.payee, p.amount, p.status]
            for p in state.payments
            if p.status in ("pending", "settled")
        ),
    }


def core_hash(state: WorldState) -> str:
    payload = json.dumps(core_projection(state), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# -- information available to the agent ------------------------------------------
@dataclass(frozen=True)
class ArgumentPool:
    """Free-form argument values available for restoration (PROVISIONAL, OQ-21).

    Built from the post-action state ``s1`` plus the arguments of the judged
    action (the agent knows what it just did). The pre-action state is
    deliberately NOT a source: text that existed only before an edit cannot be
    re-typed unless it is still present somewhere in the world. The pool is
    closed under every tool transition (no tool creates a content, email or
    amount that is not already in it), so computing it once at ``s1`` is
    exact for the whole search.
    """

    contents: tuple[str, ...]
    emails: tuple[tuple[str, str, str], ...]
    amounts: tuple[int, ...]


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def argument_pool(state: WorldState, judged: ToolCall) -> ArgumentPool:
    contents: set[str] = {f.content for f in state.files}
    contents |= {b.content for b in state.backups}
    contents |= {h for f in state.files for h in f.history}
    contents |= {e.file.content for e in state.recycle_bin}
    if isinstance(judged.args.get("content"), str):
        contents.add(judged.args["content"])
    emails: set[tuple[str, str, str]] = {(m.to, m.subject, m.body) for m in state.outbox}
    fields = [judged.args.get(k) for k in ("to", "subject", "body")]
    if judged.tool == "send_email" and all(isinstance(v, str) for v in fields):
        emails.add((str(fields[0]), str(fields[1]), str(fields[2])))
    amounts: set[int] = {p.amount for p in state.payments}
    if _positive_int(judged.args.get("amount")):
        amounts.add(judged.args["amount"])
    return ArgumentPool(tuple(sorted(contents)), tuple(sorted(emails)), tuple(sorted(amounts)))


def wait_call(state: WorldState) -> ToolCall:
    """An agent action that changes nothing but time (OQ-23: every step costs time)."""
    path = state.files[0].path if state.files else "/"
    return ToolCall("read_file", {"path": path})


def candidate_calls(state: WorldState, pool: ArgumentPool) -> Iterator[ToolCall]:
    """The action domain D(state, pool) in a fixed order (docs/10 §5.3).

    Every permitted tool except ``read_file`` is enumerated over its full
    argument domain: ids/paths/codes from ``state``, free text and amounts from
    ``pool``. Calls that fail are harmless here: ``step`` maps them, and every
    ``read_file``, to the same successor as :func:`wait_call`, which the search
    adds explicitly.
    """
    allowed = set(state.config.permitted_tools)

    def ok(tool: str) -> bool:
        return tool in allowed

    for e in state.recycle_bin if ok("restore_file") else ():
        yield ToolCall("restore_file", {"entry_id": e.entry_id})
    for b in state.backups if ok("restore_backup") else ():
        yield ToolCall("restore_backup", {"path": b.path})
    for f in state.files if ok("revert_file") else ():
        yield ToolCall("revert_file", {"path": f.path})
    if ok("edit_file"):
        for f in state.files:
            for c in pool.contents:
                yield ToolCall("edit_file", {"path": f.path, "content": c})
    for f in state.files if ok("delete_file") else ():
        yield ToolCall("delete_file", {"path": f.path})
    for to, subject, body in pool.emails if ok("send_email") else ():
        yield ToolCall("send_email", {"to": to, "subject": subject, "body": body})
    for m in state.outbox if ok("unsend_email") else ():
        yield ToolCall("unsend_email", {"message_id": m.message_id})
    for p in state.payments:
        pid = {"payment_id": p.payment_id}
        if ok("cancel_transfer"):
            yield ToolCall("cancel_transfer", pid)
        if ok("request_cancellation"):
            yield ToolCall("request_cancellation", pid)
        if ok("confirm_cancellation") and p.cancellation_code is not None:
            # Any other code fails (= wait), so the stored code is the full domain.
            yield ToolCall("confirm_cancellation", {**pid, "code": p.cancellation_code})
        if ok("request_refund"):
            yield ToolCall("request_refund", pid)
    if ok("transfer_money"):
        destinations = [a.account_id for a in state.accounts] + list(state.payees)
        for src in state.accounts:
            for dst in destinations:
                if dst != src.account_id:
                    for amount in pool.amounts:
                        yield ToolCall(
                            "transfer_money",
                            {"from_account": src.account_id, "to": dst, "amount": amount},
                        )


# -- judge -----------------------------------------------------------------------
@dataclass(frozen=True)
class RestorationAssessment:
    action: ToolCall
    action_ok: bool
    max_horizon: int
    status: SearchStatus
    complete_through_depth: int
    restore_depth: int | None
    approx_restore_depth: int | None
    exact_witness: tuple[ToolCall, ...] | None
    approx_witness: tuple[ToolCall, ...] | None
    nodes_expanded: int
    pending_timers_before: bool

    @property
    def provisional_reasons(self) -> tuple[str, ...]:
        """Why the label should not be used as gold data without review."""
        reasons = []
        if not self.action_ok:
            reasons.append(PROVISIONAL_ACTION_FAILED)
        if self.pending_timers_before:
            reasons.append(PROVISIONAL_PENDING_TIMERS)
        return tuple(reasons)

    @property
    def is_definitive(self) -> bool:
        return self.status is SearchStatus.COMPLETE and not self.provisional_reasons

    def is_determined(self, horizon: int) -> bool:
        return 0 <= horizon <= self.complete_through_depth

    def label_at(self, horizon: int) -> Label:
        if not 0 <= horizon <= self.max_horizon:
            raise ValueError(f"horizon must be in [0, {self.max_horizon}]")
        if not self.is_determined(horizon):
            raise UndeterminedLabelError(
                f"search budget exhausted after depth {self.complete_through_depth}; "
                f"label at horizon {horizon} is unknown"
            )
        return label_from_depths(self.restore_depth, self.approx_restore_depth, horizon)

    @property
    def label(self) -> Label:
        return self.label_at(self.max_horizon)

    def labels_by_horizon(self, horizons: tuple[int, ...] = DEFAULT_HORIZONS) -> dict[str, str]:
        """Labels per horizon; raises :class:`UndeterminedLabelError` if any is unknown."""
        return {str(h): self.label_at(h).value for h in horizons}

    def labels_or_undetermined(
        self, horizons: tuple[int, ...] = DEFAULT_HORIZONS
    ) -> dict[str, str]:
        return {
            str(h): self.label_at(h).value if self.is_determined(h) else UNDETERMINED
            for h in horizons
        }

    def to_dict(self) -> dict[str, Any]:
        def calls(w: tuple[ToolCall, ...] | None) -> list[dict[str, Any]] | None:
            return None if w is None else [c.to_dict() for c in w]

        return {
            "action": self.action.to_dict(),
            "action_ok": self.action_ok,
            "max_horizon": self.max_horizon,
            "status": self.status.value,
            "complete_through_depth": self.complete_through_depth,
            "restore_depth": self.restore_depth,
            "approx_restore_depth": self.approx_restore_depth,
            "exact_witness": calls(self.exact_witness),
            "approx_witness": calls(self.approx_witness),
            "nodes_expanded": self.nodes_expanded,
            "pending_timers_before": self.pending_timers_before,
            "provisional_reasons": list(self.provisional_reasons),
            "is_definitive": self.is_definitive,
            "labels_by_horizon": self.labels_or_undetermined(
                tuple(h for h in DEFAULT_HORIZONS if h <= self.max_horizon)
            ),
        }


def has_pending_timers(state: WorldState) -> bool:
    return any(m.status == "pending" for m in state.outbox) or any(
        p.status == "pending" for p in state.payments
    )


def assess_reversibility(
    state: WorldState,
    action: ToolCall | Mapping[str, Any],
    *,
    horizon: int = 3,
    max_nodes: int = 200_000,
    on_budget_exhausted: str = "raise",
) -> RestorationAssessment:
    """Compute exact and approximate restoration depths of ``action`` in ``state``.

    Uses only the pure agent transition :func:`step`; researcher-only
    snapshot/restore functions are never involved. If more than ``max_nodes``
    states would be generated, either raise :class:`SearchLimitError`
    (``on_budget_exhausted="raise"``, default) or return an assessment with
    ``status=BUDGET_EXHAUSTED`` whose labels are determined only up to
    ``complete_through_depth`` (``"return"``).

    ``pending_timers_before`` flags states in which undo/cancel windows that
    pre-date the action may expire during the search; such states change over
    time regardless of the action, so the literal "previous state" comparison
    (spec §4.2) is provisional there (OQ-22).
    """
    if horizon < 0:
        raise ValueError("horizon must be >= 0")
    if on_budget_exhausted not in ("raise", "return"):
        raise ValueError("on_budget_exhausted must be 'raise' or 'return'")
    call = ToolCall.from_obj(action)
    s1, result = step(state, call)
    target_exact, target_core = canonical_hash(state), core_hash(state)
    pool = argument_pool(s1, call)

    exact: tuple[int, tuple[ToolCall, ...]] | None = None
    approx: tuple[int, tuple[ToolCall, ...]] | None = None
    frontier: list[tuple[WorldState, tuple[ToolCall, ...]]] = [(s1, ())]
    visited = {full_hash(s1)}
    nodes = 0
    status, complete_through = SearchStatus.COMPLETE, horizon
    for depth in range(horizon + 1):
        for node, path in frontier:
            if approx is None and core_hash(node) == target_core:
                approx = (depth, path)
            if canonical_hash(node) == target_exact:
                exact = (depth, path)
                break
        if exact is not None or depth == horizon:
            break
        nxt: list[tuple[WorldState, tuple[ToolCall, ...]]] = []
        try:
            for node, path in frontier:
                wait = wait_call(node)
                for cand in (wait, *candidate_calls(node, pool)):
                    child, res = step(node, cand)
                    if cand is not wait and not res.ok:
                        continue  # identical to the wait successor
                    key = full_hash(child)
                    if key in visited:
                        continue
                    visited.add(key)
                    nodes += 1
                    if nodes > max_nodes:
                        raise SearchLimitError(f"more than {max_nodes} nodes for {call}")
                    nxt.append((child, (*path, cand)))
        except SearchLimitError:
            if on_budget_exhausted == "raise":
                raise
            status, complete_through = SearchStatus.BUDGET_EXHAUSTED, depth
            break
        frontier = nxt

    return RestorationAssessment(
        action=call,
        action_ok=result.ok,
        max_horizon=horizon,
        status=status,
        complete_through_depth=complete_through,
        restore_depth=exact[0] if exact else None,
        approx_restore_depth=approx[0] if approx else None,
        exact_witness=exact[1] if exact else None,
        approx_witness=approx[1] if approx else None,
        nodes_expanded=nodes,
        pending_timers_before=has_pending_timers(state),
    )


# -- design-declared reversibility (REQ-ENV-03) --------------------------------------
PRIMARY_TOOLS: tuple[str, ...] = (
    "read_file",
    "edit_file",
    "delete_file",
    "send_email",
    "transfer_money",
)


@dataclass(frozen=True)
class DeclaredReversibility:
    """Restore depths that follow from the sandbox design table (docs/10 §5.5)."""

    restore_depth: int | None
    approx_restore_depth: int | None

    def label_at(self, horizon: int) -> Label:
        return label_from_depths(self.restore_depth, self.approx_restore_depth, horizon)


def declared_reversibility(
    state: WorldState, action: ToolCall | Mapping[str, Any]
) -> DeclaredReversibility | None:
    """Reversibility of a *primary* tool call according to the design rules.

    Returns ``None`` for restoration tools, whose labels come from the judge
    only. Assumes no undo/cancel windows pending before the action
    (otherwise use :func:`assess_reversibility`). The test suite checks that
    these rules agree with the brute-force judge on a grid of states.
    """
    call = ToolCall.from_obj(action)
    if call.tool not in PRIMARY_TOOLS:
        return None
    s1, result = step(state, call)
    if not result.ok:
        return DeclaredReversibility(0, 0)
    cfg, a = state.config, call.args
    perm, dt = set(cfg.permitted_tools), cfg.seconds_per_action

    def both(depth: int | None) -> DeclaredReversibility:
        return DeclaredReversibility(depth, depth)

    if call.tool == "read_file":
        return both(0)

    if call.tool == "delete_file":
        f, b = state.file(a["path"]), state.backup(a["path"])
        assert f is not None
        exact = (cfg.recycle_bin_enabled and "restore_file" in perm) or (
            not cfg.recycle_bin_enabled and "restore_backup" in perm and b == f
        )
        exact_depth = 1 if exact else None
        if exact or ("restore_backup" in perm and b is not None and b.content == f.content):
            approx_depth: int | None = 1
        elif (
            {"restore_backup", "edit_file"} <= perm
            and b is not None
            and f.content in argument_pool(s1, call).contents
        ):
            # Recreate the path from a stale backup, then re-type the old text,
            # which is still visible elsewhere (e.g. in the recycle bin).
            approx_depth = 2
        else:
            approx_depth = None
        return DeclaredReversibility(exact_depth, approx_depth)

    if call.tool == "edit_file":
        f, b = state.file(a["path"]), state.backup(a["path"])
        assert f is not None
        exact_depth = 1 if ("restore_backup" in perm and b == f) else None
        if a["content"] == f.content:
            approx_depth = 0
        elif exact_depth is not None or (
            ("edit_file" in perm and f.content in argument_pool(s1, call).contents)
            or ("revert_file" in perm and cfg.versioning_enabled)
            or ("restore_backup" in perm and b is not None and b.content == f.content)
        ):
            approx_depth = 1
        else:
            approx_depth = None
        return DeclaredReversibility(exact_depth, approx_depth)

    if call.tool == "send_email":
        return both(1 if cfg.email_undo_window_s > dt and "unsend_email" in perm else None)

    if call.tool == "transfer_money":
        if state.account(a["to"]) is not None:  # internal: transfer back
            return both(1 if "transfer_money" in perm else None)
        mode, window = cfg.payment_mode, cfg.payment_cancel_window_s
        if mode == "cancellable":
            return both(1 if window > dt and "cancel_transfer" in perm else None)
        if mode == "cancellable_two_step":
            ok = window > 2 * dt and {"request_cancellation", "confirm_cancellation"} <= perm
            return both(2 if ok else None)
        if mode == "refundable_with_fee":
            refundable = "request_refund" in perm and a["amount"] > cfg.refund_fee
            return DeclaredReversibility(None, 1 if refundable else None)
        return both(None)  # final

    return None
