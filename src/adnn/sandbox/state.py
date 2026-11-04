"""Typed, immutable, JSON-serialisable world state of the tool sandbox.

All records are frozen dataclasses holding only tuples, strings, integers,
booleans and ``None``. Transitions therefore return *new* states, snapshots
are safe by construction, and two states compare equal iff they describe the
same world. Collections are normalised (sorted by key) on construction so that
equality and hashing never depend on insertion order.

Money is represented as integer currency units; there are no floats anywhere
in the state. See docs/10_SANDBOX_DESIGN.md §2 for the full schema.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any

AGENT_TOOL_NAMES: tuple[str, ...] = (
    # Primary tools (spec §4.1)
    "read_file",
    "edit_file",
    "delete_file",
    "send_email",
    "transfer_money",
    # Restoration / compensation tools
    "restore_file",
    "restore_backup",
    "revert_file",
    "unsend_email",
    "cancel_transfer",
    "request_cancellation",
    "confirm_cancellation",
    "request_refund",
)

# Extension tools (Phase 5D, share-links-spec-1.0). Registered, but never part of the
# default ``permitted_tools``: legacy scenarios cannot reach them.
EXTENSION_TOOL_NAMES: tuple[str, ...] = ("revoke_share_link", "create_share_link")
ALL_TOOL_NAMES: tuple[str, ...] = AGENT_TOOL_NAMES + EXTENSION_TOOL_NAMES
# RQ3 task tools (rq3-task-tools-1.0, docs/42). A separate group: never in the default
# ``permitted_tools`` or in ``ALL_TOOL_NAMES``, never enumerated by the restoration oracle.
TASK_TOOL_NAMES: tuple[str, ...] = ("ask_user", "backup_file", "finish")
LINK_ACCESS: tuple[str, ...] = ("view", "edit")

PAYMENT_MODES: tuple[str, ...] = (
    "final",
    "cancellable",
    "cancellable_two_step",
    "refundable_with_fee",
)
EMAIL_STATUSES: tuple[str, ...] = ("pending", "delivered")
PAYMENT_STATUSES: tuple[str, ...] = ("pending", "settled", "refunded")


class InvalidStateError(ValueError):
    """Raised when a world state violates a sandbox invariant."""


@dataclass(frozen=True)
class SandboxConfig:
    """Environment configuration. No agent tool can change it."""

    recycle_bin_enabled: bool = True
    versioning_enabled: bool = False
    email_undo_window_s: int = 0
    payment_mode: str = "final"
    payment_cancel_window_s: int = 0
    refund_fee: int = 0
    seconds_per_action: int = 10
    permitted_tools: tuple[str, ...] = AGENT_TOOL_NAMES

    def __post_init__(self) -> None:
        object.__setattr__(self, "permitted_tools", tuple(sorted(set(self.permitted_tools))))


@dataclass(frozen=True)
class FileRecord:
    """A file. ``history`` holds previous contents (oldest first) when versioning is on."""

    path: str
    content: str
    revision: int = 1
    history: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "history", tuple(self.history))


@dataclass(frozen=True)
class BinEntry:
    """A file moved to the recycle bin, restorable with ``restore_file``."""

    entry_id: str
    file: FileRecord
    deleted_at: int


@dataclass(frozen=True)
class EmailMessage:
    """An outgoing email. ``pending`` messages can be unsent before ``undo_deadline``."""

    message_id: str
    to: str
    subject: str
    body: str
    sent_at: int
    status: str
    undo_deadline: int | None = None


@dataclass(frozen=True)
class Account:
    """An account owned by the agent's user."""

    account_id: str
    balance: int


@dataclass(frozen=True)
class Payment:
    """A payment from an own account to an external payee."""

    payment_id: str
    from_account: str
    payee: str
    amount: int
    created_at: int
    status: str
    cancel_deadline: int | None = None
    cancellation_code: str | None = None
    fee_charged: int = 0


@dataclass(frozen=True)
class ShareLink:
    """A sharing link to a file (share-links-spec-1.0). Records are never deleted.

    ``address`` is user-chosen when ``custom`` is true, otherwise a generated token.
    """

    link_id: str
    path: str
    access: str
    address: str
    custom: bool
    active: bool


@dataclass(frozen=True)
class Counters:
    """Identifier allocation and step counting. Excluded from the canonical state."""

    next_message: int = 1
    next_payment: int = 1
    next_bin_entry: int = 1
    action_count: int = 0


@dataclass(frozen=True)
class WorldState:
    """The complete sandbox world. Immutable; use ``dataclasses.replace`` to derive."""

    config: SandboxConfig = field(default_factory=SandboxConfig)
    files: tuple[FileRecord, ...] = ()
    backups: tuple[FileRecord, ...] = ()
    recycle_bin: tuple[BinEntry, ...] = ()
    outbox: tuple[EmailMessage, ...] = ()
    accounts: tuple[Account, ...] = ()
    payees: tuple[str, ...] = ()
    payments: tuple[Payment, ...] = ()
    clock_s: int = 0
    counters: Counters = field(default_factory=Counters)
    share_links: tuple[ShareLink, ...] = ()

    def __post_init__(self) -> None:
        normalised = {
            "files": tuple(sorted(self.files, key=lambda f: f.path)),
            "backups": tuple(sorted(self.backups, key=lambda f: f.path)),
            "recycle_bin": tuple(sorted(self.recycle_bin, key=lambda e: e.entry_id)),
            "outbox": tuple(sorted(self.outbox, key=lambda m: m.message_id)),
            "accounts": tuple(sorted(self.accounts, key=lambda a: a.account_id)),
            "payees": tuple(sorted(self.payees)),
            "payments": tuple(sorted(self.payments, key=lambda p: p.payment_id)),
            "share_links": tuple(sorted(self.share_links, key=lambda k: k.link_id)),
        }
        for name, value in normalised.items():
            object.__setattr__(self, name, value)

    # -- lookups -----------------------------------------------------------
    def file(self, path: str) -> FileRecord | None:
        return next((f for f in self.files if f.path == path), None)

    def backup(self, path: str) -> FileRecord | None:
        return next((f for f in self.backups if f.path == path), None)

    def bin_entry(self, entry_id: str) -> BinEntry | None:
        return next((e for e in self.recycle_bin if e.entry_id == entry_id), None)

    def message(self, message_id: str) -> EmailMessage | None:
        return next((m for m in self.outbox if m.message_id == message_id), None)

    def account(self, account_id: str) -> Account | None:
        return next((a for a in self.accounts if a.account_id == account_id), None)

    def link(self, link_id: str) -> ShareLink | None:
        return next((k for k in self.share_links if k.link_id == link_id), None)

    def payment(self, payment_id: str) -> Payment | None:
        return next((p for p in self.payments if p.payment_id == payment_id), None)

    # -- serialisation -----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        d = _jsonify(asdict(self))
        if not self.share_links:  # legacy states serialise byte-identically
            d.pop("share_links")
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldState:
        """Strict parser: unknown keys are rejected, never silently dropped.

        This keeps research metadata (labels, scenario ids, splits) from being
        passed in by mistake and from ever being mistaken for world state.
        """
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise InvalidStateError(f"unknown state keys: {sorted(unknown)}")
        try:
            cfg = dict(data.get("config", {}))
            if "permitted_tools" in cfg:
                cfg["permitted_tools"] = tuple(cfg["permitted_tools"])
            return cls(
                config=SandboxConfig(**cfg),
                files=tuple(_file(f) for f in data.get("files", ())),
                backups=tuple(_file(f) for f in data.get("backups", ())),
                recycle_bin=tuple(
                    BinEntry(e["entry_id"], _file(e["file"]), e["deleted_at"])
                    for e in data.get("recycle_bin", ())
                ),
                outbox=tuple(EmailMessage(**m) for m in data.get("outbox", ())),
                accounts=tuple(Account(**a) for a in data.get("accounts", ())),
                payees=tuple(data.get("payees", ())),
                payments=tuple(Payment(**p) for p in data.get("payments", ())),
                clock_s=data.get("clock_s", 0),
                counters=Counters(**data.get("counters", {})),
                share_links=tuple(ShareLink(**k) for k in data.get("share_links", ())),
            )
        except (TypeError, KeyError) as exc:
            raise InvalidStateError(f"malformed state dict: {exc}") from exc

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, text: str) -> WorldState:
        return cls.from_dict(json.loads(text))


def _file(d: dict[str, Any]) -> FileRecord:
    return FileRecord(d["path"], d["content"], d.get("revision", 1), tuple(d.get("history", ())))


def _jsonify(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_jsonify(v) for v in obj]
    return obj


# -- canonical state ---------------------------------------------------------
NON_CANONICAL_FIELDS: tuple[str, ...] = ("clock_s", "counters")


def canonical_dict(state: WorldState) -> dict[str, Any]:
    """The state used to judge *exact* restoration.

    Excludes the logical clock and the identifier/step counters: the clock
    always advances and ids are bookkeeping, so including them would make
    every action irreversible. The audit log is not part of ``WorldState`` at
    all. Everything else (including recycle-bin contents, revisions, version
    history and payment records) is included.
    """
    d = state.to_dict()
    for name in NON_CANONICAL_FIELDS:
        d.pop(name)
    return d


def _hash(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_hash(state: WorldState) -> str:
    return _hash(canonical_dict(state))


def full_hash(state: WorldState) -> str:
    """Hash of the complete state, including clock and counters (for replay checks)."""
    return _hash(state.to_dict())


# -- invariants --------------------------------------------------------------
def validate_state(state: WorldState) -> None:
    """Raise :class:`InvalidStateError` if any invariant (docs/10 §6) is violated."""
    cfg = state.config
    errors: list[str] = []

    def unique(keys: list[str], what: str) -> None:
        if len(keys) != len(set(keys)):
            errors.append(f"duplicate {what}")

    unique([f.path for f in state.files], "file paths")
    unique([f.path for f in state.backups], "backup paths")
    unique([e.entry_id for e in state.recycle_bin], "recycle-bin entry ids")
    unique([m.message_id for m in state.outbox], "message ids")
    unique([a.account_id for a in state.accounts], "account ids")
    unique(list(state.payees), "payees")
    unique([p.payment_id for p in state.payments], "payment ids")

    unique([k.link_id for k in state.share_links], "link ids")
    unique([k.address for k in state.share_links if k.active], "active link addresses")
    for k in state.share_links:
        if k.access not in LINK_ACCESS:
            errors.append(f"link access must be one of {LINK_ACCESS}: {k.link_id}")
        if not k.path.startswith("/"):
            errors.append(f"link path must be absolute: {k.link_id}")

    unknown = set(cfg.permitted_tools) - set(ALL_TOOL_NAMES) - set(TASK_TOOL_NAMES)
    if unknown:
        errors.append(f"unknown permitted tools: {sorted(unknown)}")
    if cfg.payment_mode not in PAYMENT_MODES:
        errors.append(f"payment_mode must be one of {PAYMENT_MODES}")
    if cfg.seconds_per_action <= 0:
        errors.append("seconds_per_action must be > 0")
    for name in ("email_undo_window_s", "payment_cancel_window_s", "refund_fee"):
        if getattr(cfg, name) < 0:
            errors.append(f"{name} must be >= 0")
    if state.clock_s < 0:
        errors.append("clock_s must be >= 0")

    for f in (*state.files, *state.backups, *(e.file for e in state.recycle_bin)):
        if not f.path.startswith("/"):
            errors.append(f"path must be absolute: {f.path!r}")
        if f.revision < 1:
            errors.append(f"revision must be >= 1: {f.path!r}")
        if f.history and not cfg.versioning_enabled:
            errors.append(f"history present but versioning disabled: {f.path!r}")
    if state.recycle_bin and not cfg.recycle_bin_enabled:
        errors.append("recycle bin has entries but is disabled")

    for m in state.outbox:
        if m.status not in EMAIL_STATUSES:
            errors.append(f"bad email status {m.status!r}")
        if m.status == "pending" and m.undo_deadline is None:
            errors.append(f"pending message without deadline: {m.message_id}")

    account_ids = {a.account_id for a in state.accounts}
    if account_ids & set(state.payees):
        errors.append("payees must not overlap own accounts")
    for a in state.accounts:
        if a.balance < 0:
            errors.append(f"negative balance: {a.account_id}")
    for p in state.payments:
        if p.status not in PAYMENT_STATUSES:
            errors.append(f"bad payment status {p.status!r}")
        if p.amount <= 0:
            errors.append(f"payment amount must be > 0: {p.payment_id}")
        if p.from_account not in account_ids:
            errors.append(f"payment from unknown account: {p.payment_id}")
        if p.status == "pending" and p.cancel_deadline is None:
            errors.append(f"pending payment without deadline: {p.payment_id}")

    if errors:
        raise InvalidStateError("; ".join(errors))


def with_config(state: WorldState, **changes: Any) -> WorldState:
    """Convenience for researchers: a copy of ``state`` with config fields changed."""
    return replace(state, config=replace(state.config, **changes))
