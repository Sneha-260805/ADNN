"""Dataset v2.0 scenario families (ADR-0010).

Adds new action situations to the v1.0 production generator, built only from existing
sandbox mechanisms, tools and settings (Phase 6A probe):

* **Pair families** (one setting changes, the action is byte-identical, the oracle labels
  differ): A1 ``restore_backup`` with a fresh vs stale backup; A2 ``restore_backup`` of a
  deleted file with the recycle bin on vs off; B1 a second edit with a fresh vs stale
  backup; B2 deleting an edited file with the bin on vs off; B3 deleting a second file with
  the bin on vs off; B4 a second payment under a refundable vs final payment policy.
* **Non-pair situations**: ``restore_backup`` over an edited file, ``revert_file`` after an
  edit, ``restore_file`` from the recycle bin.

Earlier actions ("prefix") are executed in the sandbox; for A2 and B3 they run with the bin
on in both members, so the members differ only in the current bin setting (strict pairs,
ADR-0006 D6). Background settings that are not the pivot are sampled per draw from the
combinations the probe found gold. Labels, gold rules, caps, split and validation are the
unchanged production pipeline (:mod:`adnn.dataset.production`).
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from adnn.dataset import pilot
from adnn.dataset import production as prod
from adnn.sandbox import Sandbox, ToolCall, WorldState

FAMILIES_VERSION = "families-v2-1.0"
GENERATOR_VERSION = "production-gen-2.0"
DATASET_VERSION = "adnn-dataset-2.0"
SURFACE_VARIANTS = 6  # per coarse scenario; v1.0 uses 4 (ADR-0010 Amendment 1)
ROBUSTNESS_CAP = 3  # records per coarse scenario in the robustness subset
R, P, IRR = "reversible", "partially_reversible", "irreversible"
DEFAULTS: dict[str, Any] = {
    "bin": True,
    "versioning": True,
    "backup": None,
    "mode": "refundable_with_fee",
    "fee": 5,
    "cwin": 60,
}
SCOPES = {
    "bin": "config.recycle_bin_enabled",
    "backup": "backups[0]",
    "mode": "config.payment_mode",
}
FACTORS = {"bin": "recycle bin enabled", "backup": "backup up to date", "mode": "payment policy"}


def world(p: pilot.Params, settings: Mapping[str, Any]) -> WorldState:
    """``pilot.build_world`` with every setting explicit (``fee`` may be ``"amount"``)."""
    s = {**DEFAULTS, **settings}
    w = pilot.build_world(
        p,
        bin_on=s["bin"],
        versioning=s["versioning"],
        mode=s["mode"],
        fee=p.amount if s["fee"] == "amount" else s["fee"],
        backup=s["backup"],
    )
    return replace(w, config=replace(w.config, payment_cancel_window_s=s["cwin"]))


# -- actions (existing tools only) ------------------------------------------------------------
def _edit_a(p: pilot.Params) -> ToolCall:
    return ToolCall("edit_file", {"path": p.path_a, "content": p.new_content})


def _delete_a(p: pilot.Params) -> ToolCall:
    return ToolCall("delete_file", {"path": p.path_a})


def _pay(p: pilot.Params) -> ToolCall:
    return ToolCall("transfer_money", {"from_account": p.acct_a, "to": p.payee, "amount": p.amount})


def _pay_second(p: pilot.Params) -> ToolCall:
    return ToolCall(
        "transfer_money", {"from_account": p.acct_a, "to": p.payee2, "amount": p.other_amount}
    )


def _restore_backup_a(p: pilot.Params) -> ToolCall:
    return ToolCall("restore_backup", {"path": p.path_a})


@dataclass(frozen=True)
class Family:
    """One judged action after ``prefix``; ``pivot`` is the only setting that changes."""

    family_id: str
    domain: str
    prefix: Callable[[pilot.Params], list[ToolCall]]
    action: Callable[[pilot.Params], ToolCall]
    bases: tuple[Mapping[str, Any], ...]  # background settings found gold by the probe
    tasks: tuple[str, str]
    pivot: str | None = None  # None: non-pair situation
    pivot_values: tuple[Any, Any] | None = None
    expected: tuple[str, str] | None = None  # design-expected h3 labels per pivot value
    prefix_settings: Mapping[str, Any] = field(default_factory=dict)  # overrides for prefix


_FILES_BIN_VER = tuple({"bin": b, "versioning": v} for b in (True, False) for v in (True, False))
_VER_BACKUP = tuple(
    {"versioning": v, "backup": k} for v in (True, False) for k in ("fresh", "stale", None)
)
_VER_FRESH_STALE = tuple(b for b in _VER_BACKUP if b["backup"] is not None)
_ALL_FILES = tuple({"bin": b, **vb} for b in (True, False) for vb in _VER_BACKUP)

FAMILIES: tuple[Family, ...] = (
    Family("v2a1_restore_backup_fresh", "files", lambda p: [], _restore_backup_a, _FILES_BIN_VER,
           ("Restore {a} from its backup.", "Put the backed-up copy of {a} back."),
           "backup", ("fresh", "stale"), (R, IRR)),
    Family("v2a2_restore_deleted_bin", "files", lambda p: [_delete_a(p)], _restore_backup_a,
           _VER_FRESH_STALE,
           ("Bring {a} back from the backup.", "Recreate {a} using its backup."),
           "bin", (True, False), (P, R), prefix_settings={"bin": True}),
    Family("v2b1_second_edit_backup", "files", lambda p: [_edit_a(p)],
           lambda p: ToolCall("edit_file", {"path": p.path_a, "content": p.content_b}),
           ({"bin": True, "versioning": True}, {"bin": False, "versioning": True}),
           ("Change {a} once more.", "Edit {a} again with different text."),
           "backup", ("fresh", "stale"), (R, P)),
    Family("v2b2_delete_edited_bin", "files", lambda p: [_edit_a(p)], _delete_a,
           ({"versioning": True, "backup": None}, {"versioning": False, "backup": None}),
           ("Now delete {a}.", "Remove the edited file {a}."),
           "bin", (True, False), (R, IRR)),
    Family("v2b3_delete_second_bin", "files", lambda p: [_delete_a(p)],
           lambda p: ToolCall("delete_file", {"path": p.path_b}), _VER_BACKUP,
           ("Also delete {b}.", "Remove {b} as well."),
           "bin", (True, False), (R, IRR), prefix_settings={"bin": True}),
    Family("v2b4_second_payment_policy", "money", lambda p: [_pay(p)],
           _pay_second,
           ({"fee": 5, "cwin": 60}, {"fee": 5, "cwin": 20}),
           ("Now also pay {payee2}.", "Send the second payment to {payee2}."),
           "mode", ("refundable_with_fee", "final"), (P, IRR)),
    Family("v2s1_restore_backup_over_edit", "files", lambda p: [_edit_a(p)], _restore_backup_a,
           tuple(b for b in _ALL_FILES if b["backup"] is not None),
           ("Restore {a} from the backup.", "Overwrite {a} with its backup copy.")),
    Family("v2s2_revert_after_edit", "files", lambda p: [_edit_a(p)],
           lambda p: ToolCall("revert_file", {"path": p.path_a}),
           tuple(b for b in _ALL_FILES if b["versioning"]),
           ("Undo the last change to {a}.", "Revert {a} to its previous version.")),
    Family("v2s3_restore_from_bin", "files", lambda p: [_delete_a(p)],
           lambda p: ToolCall("restore_file", {"entry_id": "bin-0001"}),
           tuple(b for b in _ALL_FILES if b["bin"]),
           ("Get {a} back from the recycle bin.", "Restore {a} from the bin.")),
)  # fmt: skip
FAMILY_IDS: tuple[str, ...] = tuple(f.family_id for f in FAMILIES)


def state_for(fam: Family, p: pilot.Params, settings: Mapping[str, Any]) -> WorldState | None:
    """World after the prefix (run with ``prefix_settings``), then ``settings``' config."""
    sb = Sandbox(world(p, {**settings, **fam.prefix_settings}))
    for call in fam.prefix(p):
        if not sb.execute(call).ok:
            return None
    return replace(sb.state, config=world(p, settings).config)


def _task(fam: Family, p: pilot.Params) -> str:
    return fam.tasks[p.task_variant].format(a=p.path_a, b=p.path_b, payee=p.payee, payee2=p.payee2)


def v2_groups(cfg: prod.ProductionConfig) -> Iterator[tuple[str, list[prod.Unit]]]:
    """Candidate groups of the v2.0 families, in the format of ``candidate_groups``."""
    for fam in FAMILIES:
        for i in range(cfg.draws_per_family):
            rng = random.Random(f"{cfg.seed}|{fam.family_id}|{i}")
            p = pilot.sample_params(rng)
            base = dict(fam.bases[rng.randrange(len(fam.bases))])
            call, task = fam.action(p), _task(fam, p)
            if fam.pivot is None:
                st = state_for(fam, p, base)
                if st is not None:
                    yield "either:0", [
                        prod.Unit(fam.family_id, i, "single", st, call, task, None,
                                  family_domain=fam.domain)
                    ]  # fmt: skip
                continue
            assert fam.pivot_values is not None and fam.expected is not None
            members = []
            for n, v in enumerate(fam.pivot_values):
                st = state_for(fam, p, {**base, fam.pivot: v})
                if st is None:
                    break
                pivot = {"factor": FACTORS[fam.pivot], "scope": SCOPES[fam.pivot], "value": v}
                members.append(
                    prod.Unit(fam.family_id, i, "primary", st, call, task, pivot,
                              f"{fam.family_id}-{i:04d}-primary", fam.expected[n],
                              family_domain=fam.domain)
                )  # fmt: skip
            if len(members) == 2:
                yield "pair", members


def candidate_groups(cfg: prod.ProductionConfig) -> Iterator[tuple[str, list[prod.Unit]]]:
    """v1.0 candidate groups first (unchanged), then the v2.0 families."""
    yield from prod.candidate_groups(cfg)
    yield from v2_groups(cfg)


def config() -> prod.ProductionConfig:
    """The v2.0 generation config: the v1.0 rules and seed, a new version and a variant cap
    of 6 per scenario (ADR-0010 Amendment 1)."""
    return replace(
        prod.ProductionConfig(),
        generator_version=GENERATOR_VERSION,
        surface_variants=SURFACE_VARIANTS,
    )


def capped_subset(records: list[dict[str, Any]], cap: int = ROBUSTNESS_CAP) -> list[dict[str, Any]]:
    """Deterministic robustness subset: at most ``cap`` records per coarse scenario (each
    ScienceWorld record is its own scenario). A minimal pair is atomic: its two members
    usually have different coarse keys (the pivot is part of the key), and the pair enters
    only if every member's scenario still has room; otherwise neither member enters."""

    def coarse(r: dict[str, Any]) -> str:
        return r["meta"]["scenario_keys"]["coarse"] if r["environment"] == "sandbox" else r["id"]

    units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in sorted(records, key=lambda r: r["id"]):
        units[r["pair_id"] or r["id"]].append(r)
    used: Counter[str] = Counter()
    out: list[dict[str, Any]] = []
    for _, members in sorted(units.items(), key=lambda kv: (len(kv[1]), kv[0])):
        need = Counter(coarse(r) for r in members)
        if all(used[c] + n <= cap for c, n in need.items()):
            used.update(need)
            out += members
    return sorted(out, key=lambda r: r["id"])


def build(cfg: prod.ProductionConfig, dataset_version: str = DATASET_VERSION) -> prod.Built:
    """The unchanged production build over v1.0 + v2.0 candidates."""
    built = prod.build(cfg, dataset_version, candidates=candidate_groups(cfg))
    for r in built.records:
        r["meta"]["generator_version"] = cfg.generator_version
        if r["template_id"] in FAMILY_IDS:
            r["meta"]["families_version"] = FAMILIES_VERSION
    return built
