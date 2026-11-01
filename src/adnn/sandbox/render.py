"""Deterministic plain-text rendering of the world state shown to the agent.

This is the default renderer. The dataset phase may add surface-form variants
of pivot settings (docs/05_DATASET_SPECIFICATION.md §6); any variant must stay
a deterministic function of the state.
"""

from __future__ import annotations

from adnn.sandbox.state import WorldState


def _on_off(flag: bool) -> str:
    return "enabled" if flag else "disabled"


def render_state(state: WorldState) -> str:
    cfg = state.config
    lines = [f"Time: t={state.clock_s}s", "Settings:"]
    lines.append(f"  recycle_bin: {_on_off(cfg.recycle_bin_enabled)}")
    lines.append(f"  file_versioning: {_on_off(cfg.versioning_enabled)}")
    undo = f"{cfg.email_undo_window_s}s" if cfg.email_undo_window_s > 0 else "none (immediate)"
    lines.append(f"  email_undo_window: {undo}")
    lines.append(f"  payment_mode: {cfg.payment_mode}")
    if cfg.payment_mode in ("cancellable", "cancellable_two_step"):
        lines.append(f"  payment_cancel_window: {cfg.payment_cancel_window_s}s")
    if cfg.payment_mode == "refundable_with_fee":
        lines.append(f"  refund_fee: {cfg.refund_fee}")

    def section(title: str, items: list[str]) -> None:
        lines.append(f"{title}:")
        if items:
            lines.extend(f"  {i}" for i in items)
        else:
            lines.append("  (none)")

    section(
        "Files",
        [
            f"{f.path} (revision {f.revision}, {len(f.content)} chars"
            + (f", {len(f.history)} previous versions)" if f.history else ")")
            for f in state.files
        ],
    )
    section("Backups", [f"{b.path} (revision {b.revision})" for b in state.backups])
    section(
        "Recycle bin",
        [f"{e.entry_id}: {e.file.path} (deleted at t={e.deleted_at}s)" for e in state.recycle_bin],
    )
    section(
        "Outbox",
        [
            f"{m.message_id} to {m.to} subject {m.subject!r}: {m.status}"
            + (f" (undo until t={m.undo_deadline}s)" if m.status == "pending" else "")
            for m in state.outbox
        ],
    )
    section("Accounts", [f"{a.account_id}: {a.balance}" for a in state.accounts])
    section("Payees", list(state.payees))
    section(
        "Payments",
        [
            f"{p.payment_id}: {p.amount} from {p.from_account} to {p.payee}: {p.status}"
            + (f" (cancellable until t={p.cancel_deadline}s)" if p.status == "pending" else "")
            for p in state.payments
        ],
    )
    return "\n".join(lines)
