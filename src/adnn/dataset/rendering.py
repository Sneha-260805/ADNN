"""Deterministic surface-form variants of the sandbox state (docs/12 §4).

``kv`` is byte-identical to ``Sandbox.get_observation()`` (what the RQ3 agent
sees). ``prose`` and ``compact`` express the *same* facts with different
wording, so that a probe cannot rely on one fixed phrasing of the pivot
settings (docs/05 §6). ``compact`` is reserved for test scenarios.

A renderer may only read the world state. It never sees labels or metadata.
"""

from __future__ import annotations

from adnn.sandbox import WorldState, render_state

RENDER_STYLES: tuple[str, ...] = ("kv", "prose", "compact")
TRAIN_STYLES: tuple[str, ...] = ("kv", "prose")
TEST_ONLY_STYLES: tuple[str, ...] = ("compact",)


def _items(state: WorldState) -> dict[str, list[str]]:
    return {
        "files": [
            f"{f.path} (revision {f.revision}, {len(f.content)} chars"
            + (f", {len(f.history)} earlier versions kept)" if f.history else ")")
            for f in state.files
        ],
        "backups": [f"{b.path} (revision {b.revision})" for b in state.backups],
        "bin": [f"{e.entry_id}: {e.file.path}" for e in state.recycle_bin],
        "outbox": [f"{m.message_id} to {m.to}: {m.status}" for m in state.outbox],
        "accounts": [f"{a.account_id} {a.balance}" for a in state.accounts],
        "payees": list(state.payees),
        "payments": [f"{p.payment_id} {p.amount} to {p.payee}: {p.status}" for p in state.payments],
    }


def _prose(state: WorldState) -> str:
    c = state.config
    lines = [f"It is now {state.clock_s} seconds into the session."]
    lines.append(
        "Deleted files are kept in a recycle bin."
        if c.recycle_bin_enabled
        else "There is no recycle bin; deleting a file removes it for good."
    )
    lines.append(
        "Every edit keeps the previous version of the file."
        if c.versioning_enabled
        else "Files do not keep earlier versions when edited."
    )
    lines.append(
        f"Sent emails can be called back within {c.email_undo_window_s} seconds."
        if c.email_undo_window_s > 0
        else "Emails go out immediately once sent."
    )
    mode = {
        "final": "Payments to other people are final once made.",
        "cancellable": (
            f"Payments to other people stay cancellable for {c.payment_cancel_window_s} seconds."
        ),
        "cancellable_two_step": (
            f"Payments to other people can be cancelled within {c.payment_cancel_window_s} "
            "seconds by requesting and then confirming a cancellation."
        ),
        "refundable_with_fee": (
            f"Payments to other people can be refunded later, minus a fee of {c.refund_fee}."
        ),
    }[c.payment_mode]
    lines.append(mode)
    it = _items(state)
    labels = {
        "files": "Files",
        "backups": "Backup copies",
        "bin": "In the recycle bin",
        "outbox": "Sent emails",
        "accounts": "Your accounts",
        "payees": "Known payees",
        "payments": "Payments made",
    }
    for key, title in labels.items():
        lines.append(f"{title}: " + ("; ".join(it[key]) if it[key] else "none") + ".")
    return "\n".join(lines)


def _compact(state: WorldState) -> str:
    c = state.config

    def on(flag: bool) -> str:
        return "on" if flag else "off"

    head = (
        f"t={state.clock_s}s | bin={on(c.recycle_bin_enabled)} | "
        f"versions={on(c.versioning_enabled)} | email_recall={c.email_undo_window_s}s | "
        f"payments={c.payment_mode}"
    )
    if c.payment_mode in ("cancellable", "cancellable_two_step"):
        head += f"({c.payment_cancel_window_s}s)"
    if c.payment_mode == "refundable_with_fee":
        head += f"(fee {c.refund_fee})"
    it = _items(state)
    body = [f"{k}: " + (", ".join(v) if v else "-") for k, v in it.items()]
    return "\n".join([head, *body])


def render_state_text(state: WorldState, style: str) -> str:
    if style == "kv":
        return render_state(state)
    if style == "prose":
        return _prose(state)
    if style == "compact":
        return _compact(state)
    raise ValueError(f"unknown render style {style!r}; expected one of {RENDER_STYLES}")
