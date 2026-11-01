"""Tool sandbox (owner: Member 1, Sneha).

A small, fully simulated, deterministic world (files with recycle bin, backups
and optional version history; email outbox with optional undo window; own
accounts and external payments with configurable reversibility) whose every
tool has a design-specified reversibility, verified by a brute-force
restoration search. Design: docs/10_SANDBOX_DESIGN.md.

Safety (REQ-SAFE-01): nothing in this package touches the real file system,
network, email or any account. All effects are changes to immutable values.

Not yet implemented here (later phases): ``ask_user`` (OQ-06), backup-creation
and listing tools, surface-form rendering variants, task success predicates.
"""

from adnn.sandbox.engine import ActionRecord, Sandbox, Snapshot
from adnn.sandbox.render import render_state
from adnn.sandbox.restoration import (
    DeclaredReversibility,
    Label,
    RestorationAssessment,
    SearchLimitError,
    assess_reversibility,
    core_projection,
    declared_reversibility,
)
from adnn.sandbox.state import (
    AGENT_TOOL_NAMES,
    Account,
    BinEntry,
    Counters,
    EmailMessage,
    FileRecord,
    InvalidStateError,
    Payment,
    SandboxConfig,
    WorldState,
    canonical_dict,
    canonical_hash,
    full_hash,
    validate_state,
    with_config,
)
from adnn.sandbox.tools import TOOL_SPECS, ErrorCode, ToolCall, ToolError, ToolResult, step

__all__ = [
    "AGENT_TOOL_NAMES",
    "TOOL_SPECS",
    "Account",
    "ActionRecord",
    "BinEntry",
    "Counters",
    "DeclaredReversibility",
    "EmailMessage",
    "ErrorCode",
    "FileRecord",
    "InvalidStateError",
    "Label",
    "Payment",
    "RestorationAssessment",
    "Sandbox",
    "SandboxConfig",
    "SearchLimitError",
    "Snapshot",
    "ToolCall",
    "ToolError",
    "ToolResult",
    "WorldState",
    "assess_reversibility",
    "canonical_dict",
    "canonical_hash",
    "core_projection",
    "declared_reversibility",
    "full_hash",
    "render_state",
    "step",
    "validate_state",
    "with_config",
]
