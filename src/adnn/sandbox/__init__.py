"""Tool sandbox (owner: Member 1, Sneha). NOT YET IMPLEMENTED.

Planned: a small, fully simulated Python world (file system with optional
recycle bin and backups, email outbox with optional undo window, wallet with
optional cancellable transfers) whose full state can be snapshotted and
restored, and whose every tool has a design-specified reversibility.
Includes an ``ask_user`` tool with scripted, deterministic replies.

Safety (REQ-SAFE-01): nothing in this package may touch the real file system,
network, email or any account. See docs/03_SYSTEM_ARCHITECTURE.md.
"""
