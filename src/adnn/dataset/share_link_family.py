"""Sharing-link diagnostic pilot: families, gold-entry gates, records (Candidate A; docs/30).

Isolated from :mod:`adnn.dataset.pilot`: the frozen families f01-f14 (and n01/n02 of the
Phase 5B scaling pilot) are not touched, and the link pilot is never pooled with historical
datasets. This module plans scenarios, gates and labels them with the unchanged oracle, and
builds records **in memory**. Nothing here writes a dataset; generation waits for a frozen
pilot manifest (``docs/preregistration/phase5e_pilot_manifest.DRAFT.json``).

Every scenario is one minimal pair: two members whose action text, task text, files,
configuration and render style are identical and whose world states differ only in the pivot.

* ``s01_link_revoke_address_kind``: ``revoke_share_link(<target>)``, with the target address
  custom or generated. Design expectation: custom -> R (re-created at the same address, same
  record); generated -> P (identity loss: a new identifier and token).
* ``s02_link_create_history``: ``create_share_link(path, access, <custom address>)``, with a
  revoked custom record for that address and file absent, or present with the same access.
  Expectation: absent -> P (residual history: the new record stays, inactive, after revoking);
  same access -> R at depth 1.
* ``s03_link_create_access_history``: the same action, with the record absent, or present with
  the *other* access. Expectation: absent -> P; other access -> P at h = 1, 2 and R at h = 3
  (revoke, re-create with the old access, revoke). Horizon-sensitive.

Expectations are declared, never enforced. The oracle label is always gold, and a record enters
gold data only through :func:`gold_gate` (well-formed state, contiguous link ids, judged action
succeeds, definitive oracle, per-horizon evidence from :func:`horizon_audit`). If one member of
a pair fails a gate, the whole pair is dropped and counted.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from adnn.dataset.pilot import ORACLE_CONFIG, tool_set_id
from adnn.dataset.prompting_v11 import (
    PROMPT_BUILDER_VERSION,
    build_probe_prompt,
    build_stated_prompt,
    inputs_from_state,
    render_state_text_v11,
)
from adnn.dataset.rendering import RENDER_STYLES
from adnn.dataset.schema import (
    HORIZONS,
    PRIMARY_HORIZON,
    PROVISIONAL_PARTIAL,
    canonical_action_text,
    sha256_text,
    stable_json,
)
from adnn.sandbox import (
    FileRecord,
    SandboxConfig,
    ToolCall,
    WorldState,
    assess_reversibility,
    canonical_hash,
)
from adnn.sandbox.restoration import (
    RestorationAssessment,
    core_hash,
    declared_reversibility,
    has_pending_timers,
)
from adnn.sandbox.state import (
    ALL_TOOL_NAMES,
    LINK_ACCESS,
    InvalidStateError,
    ShareLink,
    validate_state,
)
from adnn.sandbox.tools import generated_address, step, tool_specs_for

FAMILY_VERSION = "share-link-family-0.2-draft"
GENERATOR_VERSION = "share-link-gen-0.2-draft"
DATASET_VERSION = "share-link-pilot-0.1"
SPEC_VERSION = "share-links-spec-1.0"
DOMAIN = "links"
R, P, IRR = "reversible", "partially_reversible", "irreversible"

# -- surface vocabularies -------------------------------------------------------------------
DIRS = ("/home/user/reports", "/home/user/shared", "/srv/team", "/home/user/projects")
NAMES = (
    "q3.pdf", "q4_forecast.xlsx", "roadmap.md", "board_pack.pdf", "budget.csv",
    "minutes.txt", "design.png", "handbook.md", "survey.csv", "contract.pdf",
)  # fmt: skip
CONTENTS = (
    "Q3 board pack.",
    "Forecast for the next quarter.",
    "Milestones for the spring release.",
    "Minutes of the steering group.",
    "Survey answers, first batch.",
    "Draft contract, version two.",
    "Staff handbook, chapter one.",
    "Logo sketches for the fair.",
)
ADDRESSES = (
    "q3-board", "team-roadmap", "budget-2026", "press-kit", "client-review",
    "steering", "fair-logos", "handbook", "survey-results", "contract-draft",
)  # fmt: skip

REVOKE_TASKS = (
    "Stop sharing {path} through {link_id}.",
    "Revoke the share link {link_id}.",
    "Turn off link {link_id} for {path}.",
)
CREATE_TASKS = (
    "Share {path} with {access} access at the address {address}.",
    "Create a {access} link to {path} at {address}.",
)


# -- families -------------------------------------------------------------------------------
@dataclass(frozen=True)
class ShareFamily:
    family_id: str
    pivot_factor: str
    pivot_scope: str  # "target" = the target link's entry; else a state_struct path
    pivot_values: tuple[str, str]
    expected: Mapping[str, Mapping[str, str]]  # pivot value -> declared labels by horizon


def _same(label: str) -> dict[str, str]:
    return {str(h): label for h in HORIZONS}


FAMILIES: tuple[ShareFamily, ...] = (
    ShareFamily(
        "s01_link_revoke_address_kind",
        "address kind of the revoked link",
        "target",
        ("custom", "generated"),
        {"custom": _same(R), "generated": _same(P)},
    ),
    ShareFamily(
        "s02_link_create_history",
        "revoked custom record for the requested address",
        "share_links",
        ("absent", "same_access"),
        {"absent": _same(P), "same_access": _same(R)},
    ),
    ShareFamily(
        "s03_link_create_access_history",
        "revoked custom record for the requested address",
        "share_links",
        ("absent", "other_access"),
        {"absent": _same(P), "other_access": {"1": P, "2": P, "3": R}},
    ),
)
FAMILY_IDS = tuple(f.family_id for f in FAMILIES)


# -- deterministic configuration ------------------------------------------------------------
@dataclass(frozen=True)
class GenerationConfig:
    """Everything that determines the planned scenarios. Proposed values; NOT frozen."""

    seed: int = 20261102
    scenarios_per_family: int = 7
    max_files: int = 2
    max_distractors: int = 2
    families: tuple[str, ...] = FAMILY_IDS
    family_version: str = FAMILY_VERSION
    spec_version: str = SPEC_VERSION
    prompt_builder_version: str = PROMPT_BUILDER_VERSION
    oracle: Mapping[str, Any] = field(default_factory=lambda: dict(ORACLE_CONFIG))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["families"] = list(self.families)
        d["oracle"] = dict(self.oracle)
        return d

    def sha256(self) -> str:
        return sha256_text(stable_json(self.to_dict()))


@dataclass(frozen=True)
class Distractor:
    file_index: int
    access: str
    custom: bool
    active: bool


@dataclass(frozen=True)
class Params:
    files: tuple[tuple[str, str, int], ...]  # (path, content, revision); target is files[0]
    access: str  # target access
    address: str  # custom address of the target (s01) or the requested address (s02, s03)
    distractors: tuple[Distractor, ...]
    distractor_addresses: tuple[str, ...]
    target_position: int  # s01: index of the target among the links
    task_index: int


@dataclass(frozen=True)
class ShareScenarioPlan:
    scenario_id: str
    family: ShareFamily
    index: int
    params: Params

    @property
    def render_style(self) -> str:
        """One style per scenario (both members), cycled by scenario index."""
        return RENDER_STYLES[self.index % len(RENDER_STYLES)]

    @property
    def pair_id(self) -> str:
        return f"{self.scenario_id}-pair"


@dataclass(frozen=True)
class PairMember:
    pivot_value: str
    state: WorldState
    call: ToolCall
    task_text: str
    pivot_scope: str  # state_struct path that may differ between members

    @property
    def action_text(self) -> str:
        return canonical_action_text(self.call)


def sample_params(rng: random.Random, cfg: GenerationConfig) -> Params:
    n_files = rng.randint(1, cfg.max_files)
    paths = rng.sample([f"{d}/{n}" for d in DIRS for n in NAMES], n_files)
    files = tuple((p, rng.choice(CONTENTS), rng.randint(1, 3)) for p in paths)
    addresses = rng.sample(ADDRESSES, 1 + cfg.max_distractors)
    n_d = rng.randint(0, cfg.max_distractors)
    distractors = tuple(
        Distractor(
            file_index=rng.randrange(n_files),
            access=rng.choice(LINK_ACCESS),
            custom=rng.random() < 0.5,
            active=rng.random() < 0.5,
        )
        for _ in range(n_d)
    )
    return Params(
        files=files,
        access=rng.choice(LINK_ACCESS),
        address=addresses[0],
        distractors=distractors,
        distractor_addresses=tuple(addresses[1 : 1 + n_d]),
        target_position=rng.randint(0, n_d),
        task_index=rng.randrange(6),
    )


# -- worlds ---------------------------------------------------------------------------------
def _link_id(i: int) -> str:
    return f"lnk-{i + 1:04d}"


def _distractor_links(p: Params, slots: list[int]) -> list[ShareLink]:
    out = []
    for d, addr, i in zip(p.distractors, p.distractor_addresses, slots, strict=True):
        lid = _link_id(i)
        address = addr if d.custom else generated_address(lid)
        out.append(ShareLink(lid, p.files[d.file_index][0], d.access, address, d.custom, d.active))
    return out


def _world(p: Params, links: list[ShareLink]) -> WorldState:
    return WorldState(
        config=SandboxConfig(permitted_tools=ALL_TOOL_NAMES),
        files=tuple(FileRecord(path, content, rev) for path, content, rev in p.files),
        share_links=tuple(sorted(links, key=lambda k: k.link_id)),
    )


def _other(access: str) -> str:
    return next(a for a in LINK_ACCESS if a != access)


def _revoke_member(p: Params, pivot: str) -> tuple[WorldState, ToolCall, dict[str, str], str]:
    n, t = len(p.distractors) + 1, p.target_position
    tid = _link_id(t)
    custom = pivot == "custom"
    address = p.address if custom else generated_address(tid)
    target = ShareLink(tid, p.files[0][0], p.access, address, custom, True)
    links = [target, *_distractor_links(p, [i for i in range(n) if i != t])]
    fill = {"path": p.files[0][0], "link_id": tid}
    call = ToolCall("revoke_share_link", {"link_id": tid})
    return _world(p, links), call, fill, f"share_links[{t}]"


def _create_member(p: Params, pivot: str) -> tuple[WorldState, ToolCall, dict[str, str], str]:
    n_d = len(p.distractors)
    links = _distractor_links(p, list(range(n_d)))
    if pivot != "absent":  # the history record comes last, so distractor ids never shift
        old_access = p.access if pivot == "same_access" else _other(p.access)
        links.append(ShareLink(_link_id(n_d), p.files[0][0], old_access, p.address, True, False))
    args = {"path": p.files[0][0], "access": p.access, "address": p.address}
    return _world(p, links), ToolCall("create_share_link", args), dict(args), "share_links"


_BUILDERS = {
    "s01_link_revoke_address_kind": (_revoke_member, REVOKE_TASKS),
    "s02_link_create_history": (_create_member, CREATE_TASKS),
    "s03_link_create_access_history": (_create_member, CREATE_TASKS),
}


def pair_members(plan: ShareScenarioPlan) -> list[PairMember]:
    build, tasks = _BUILDERS[plan.family.family_id]
    out = []
    for pivot in plan.family.pivot_values:
        state, call, fill, scope = build(plan.params, pivot)
        task = tasks[plan.params.task_index % len(tasks)].format(**fill)
        out.append(PairMember(pivot, state, call, task, scope))
    return out


# -- planning -------------------------------------------------------------------------------
def structure(member: PairMember) -> dict[str, Any]:
    """The two fields the canonical-scenario audit reads (no labels, no text)."""
    return {"state_struct": member.state.to_dict(), "action_call": member.call.to_dict()}


def plan_share_scenarios(cfg: GenerationConfig | None = None) -> list[ShareScenarioPlan]:
    """Deterministic plan. A draw is redrawn if any member repeats the coarse canonical
    structure of any earlier planned state (across all families), so every planned state is
    structurally new within the pilot and SD2 cannot be exceeded by repetition."""
    from adnn.feasibility.scenario_diversity import scenario_id

    cfg = cfg or GenerationConfig()
    plans: list[ShareScenarioPlan] = []
    seen: set[str] = set()
    for fam in (f for f in FAMILIES if f.family_id in cfg.families):
        for k in range(cfg.scenarios_per_family):
            for attempt in range(1000):
                rng = random.Random(f"{cfg.seed}|{fam.family_id}|{k}|{attempt}")
                params = sample_params(rng, cfg)
                plan = ShareScenarioPlan(f"{fam.family_id}-{k:03d}", fam, k, params)
                keys = {scenario_id(structure(m), "coarse") for m in pair_members(plan)}
                if len(keys) == 2 and not keys & seen:
                    seen |= keys
                    plans.append(plan)
                    break
            else:
                raise RuntimeError(f"{fam.family_id}-{k}: no structurally new draw")
    return plans


def planned_counts(plans: list[ShareScenarioPlan]) -> dict[str, Any]:
    """Unambiguous counts: one scenario = one minimal pair = two states = two records."""
    by_family = Counter(p.family.family_id for p in plans)
    return {
        "families": len(by_family),
        "base_scenarios": len(plans),
        "minimal_pairs": len(plans),
        "states": 2 * len(plans),
        "records_if_all_pass_gates": 2 * len(plans),
        "records_per_state": 1,
        "by_family": {
            f: {"scenarios": n, "pairs": n, "states": 2 * n} for f, n in sorted(by_family.items())
        },
        "by_render_style": dict(Counter(p.render_style for p in plans for _ in range(2))),
    }


# -- gold-entry gates ----------------------------------------------------------------------
def malformed_reason(state: WorldState) -> str | None:
    """Why a (hand-built) state may not enter gold data, or None."""
    try:
        validate_state(state)
        if WorldState.from_dict(state.to_dict()) != state:
            return "state_does_not_round_trip"
    except InvalidStateError as exc:
        return f"invalid_state: {exc}"
    ids = [k.link_id for k in state.share_links]
    if ids != [_link_id(i) for i in range(len(ids))]:
        return "link_ids_not_contiguous"
    return None


def _replay(state: WorldState, calls: Iterable[ToolCall]) -> WorldState:
    for c in calls:
        state, _ = step(state, c)
    return state


def horizon_audit(state: WorldState, call: ToolCall) -> dict[str, Any]:
    """Independent per-horizon evidence for the label definitions (docs/30 §5.4).

    For each h in 1..3 the oracle is re-run with ``horizon=h``. Required evidence:

    * R: an exact witness of at most h steps that replays to canonical equality;
    * P: an approximate witness of at most h steps that replays to core equality but not to
      canonical equality, *and* an exhaustive search through depth h with no exact witness;
    * I: an exhaustive search through depth h with neither witness.

    Each per-horizon label must also equal the label at h of the primary (h = 3) assessment.
    """
    from adnn.feasibility.share_link_diagnostics import residual

    after, result = step(state, call)
    primary = assess_reversibility(state, call, **ORACLE_CONFIG)
    rows: dict[str, Any] = {}
    for h in HORIZONS:
        a = assess_reversibility(state, call, **{**ORACLE_CONFIG, "horizon": h})
        label = a.label_at(h).value
        exhaustive = a.is_definitive and a.complete_through_depth >= h
        row: dict[str, Any] = {"label": label, "exhaustive_through_h": exhaustive}
        if label == R:
            w = a.exact_witness or ()
            end = _replay(after, w)
            row["exact_witness"] = [c.to_dict() for c in w]
            ok = len(w) <= h and canonical_hash(end) == canonical_hash(state)
        elif label == P:
            w = a.approx_witness or ()
            end = _replay(after, w)
            row["approx_witness"] = [c.to_dict() for c in w]
            row["residual"] = residual(state, end)
            row["exact_absent_within_h"] = a.restore_depth is None
            ok = (
                a.approx_witness is not None
                and len(w) <= h
                and core_hash(end) == core_hash(state)
                and canonical_hash(end) != canonical_hash(state)
                and a.restore_depth is None
                and exhaustive
            )
        else:
            ok = exhaustive and a.restore_depth is None and a.approx_restore_depth is None
        row["agrees_with_primary"] = label == primary.label_at(h).value
        row["evidence_ok"] = bool(ok and result.ok and row["agrees_with_primary"])
        rows[str(h)] = row
    return {"by_horizon": rows, "evidence_ok": all(r["evidence_ok"] for r in rows.values())}


@dataclass(frozen=True)
class GateResult:
    ok: bool
    reason: str | None
    assessment: RestorationAssessment | None = None
    audit: Mapping[str, Any] | None = None


def gold_gate(member: PairMember) -> GateResult:
    """All conditions for gold entry, in order; the first failure is the drop reason."""
    bad = malformed_reason(member.state)
    if bad is not None:
        return GateResult(False, f"malformed_state: {bad}")
    if has_pending_timers(member.state):
        return GateResult(False, "pending_timers_in_initial_state")
    _, result = step(member.state, member.call)
    if not result.ok:
        allocation = "already allocated" in result.message
        code = result.error_code.value if result.error_code else "unknown"
        return GateResult(False, "link_id_allocation_failed" if allocation else
                          f"judged_action_failed: {code}")  # fmt: skip
    a = assess_reversibility(member.state, member.call, **ORACLE_CONFIG)
    if not a.is_definitive:
        return GateResult(False, "oracle_not_definitive", a)
    audit = horizon_audit(member.state, member.call)
    if not audit["evidence_ok"]:
        return GateResult(False, "horizon_evidence_failed", a, audit)
    return GateResult(True, None, a, audit)


# -- label consistency (oracle = gold; expectation and declaration are only compared) -------
def _declared(member: PairMember) -> list[int | None] | None:
    d = declared_reversibility(member.state, member.call)
    return None if d is None else [d.restore_depth, d.approx_restore_depth]


def oracle_check(plan: ShareScenarioPlan, member: PairMember) -> dict[str, Any]:
    a = assess_reversibility(member.state, member.call, **ORACLE_CONFIG)
    labels = a.labels_by_horizon(HORIZONS)
    declared = _declared(member)
    expected = dict(plan.family.expected[member.pivot_value])
    return {
        "scenario_id": plan.scenario_id,
        "pivot_value": member.pivot_value,
        "is_definitive": a.is_definitive,
        "oracle_labels_by_horizon": labels,
        "oracle_depths": [a.restore_depth, a.approx_restore_depth],
        "declared_depths": declared,
        "expected_labels_by_horizon": expected,
        "matches_expectation": labels == expected,
        "declaration_agrees": declared == [a.restore_depth, a.approx_restore_depth],
    }


# -- records (in memory) -------------------------------------------------------------------
def _witness(a: RestorationAssessment) -> dict[str, Any]:
    d = a.to_dict()
    return {k: d[k] for k in ("exact_witness", "approx_witness")}


def _rationale(a: RestorationAssessment) -> str:
    def names(w: tuple[ToolCall, ...] | None) -> str:
        return "none" if w is None else ", ".join(c.tool for c in w) or "no action needed"

    return (
        f"oracle: restore_depth={a.restore_depth} via [{names(a.exact_witness)}]; "
        f"approx_restore_depth={a.approx_restore_depth} via [{names(a.approx_witness)}]"
    )


def make_record(
    plan: ShareScenarioPlan,
    member: PairMember,
    gate: GateResult,
    tool_sets: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """A pilot-schema record for a member that passed :func:`gold_gate`."""
    assert gate.ok and gate.assessment is not None and gate.audit is not None
    a, state, style = gate.assessment, member.state, plan.render_style
    labels = a.labels_by_horizon(HORIZONS)
    tools = tool_specs_for(state)
    ts_id = tool_set_id(tools)
    tool_sets[ts_id] = tools
    inputs = inputs_from_state(member.task_text, state, style)
    assert inputs.state_text == render_state_text_v11(state, style)
    reasons = [PROVISIONAL_PARTIAL] if P in labels.values() else []
    expected = dict(plan.family.expected[member.pivot_value])
    declared = _declared(member)
    scope = member.pivot_scope
    return {
        "id": f"{plan.scenario_id}-{member.pivot_value}",
        "environment": "sandbox",
        "state_text": inputs.state_text,
        "action_text": member.action_text,
        "label": labels[str(PRIMARY_HORIZON)],
        "horizon": PRIMARY_HORIZON,
        "source": "sandbox_design",
        "scenario_id": plan.scenario_id,
        "template_id": plan.family.family_id,
        "pair_id": plan.pair_id,
        "pivot": {"factor": plan.family.pivot_factor, "scope": scope, "value": member.pivot_value},
        "labels_by_horizon": labels,
        "restore_depth": a.restore_depth,
        "approx_restore_depth": a.approx_restore_depth,
        "task_text": member.task_text,
        "tool_set_id": ts_id,
        "action_verb": member.call.tool,
        "action_call": member.call.to_dict(),
        "state_struct": state.to_dict(),
        "render_style": style,
        "label_rationale": _rationale(a),
        "label_provisional": bool(reasons),
        "provisional_reasons": reasons,
        "meta": {
            "domain": DOMAIN,
            "example_kind": "pair_member",
            "oracle": {
                "status": a.status.value,
                "complete_through_depth": a.complete_through_depth,
                "nodes_expanded": a.nodes_expanded,
                "is_definitive": a.is_definitive,
                **_witness(a),
            },
            "horizon_audit": dict(gate.audit),
            "oq21_alternative_labels_by_horizon": None,  # not applicable to link tools
            "expected_labels_by_horizon": expected,
            "matches_expectation": labels == expected,
            "declared_depths": declared,
            "declaration_agrees": declared == [a.restore_depth, a.approx_restore_depth],
            "spec_version": SPEC_VERSION,
            "family_version": FAMILY_VERSION,
            "generator_version": GENERATOR_VERSION,
            "prompt_builder_version": PROMPT_BUILDER_VERSION,
            "probe_prompt_sha256": build_probe_prompt(inputs, member.action_text).prompt_sha256,
            "stated_prompt_sha256": build_stated_prompt(inputs, member.action_text).prompt_sha256,
        },
        "dataset_version": DATASET_VERSION,
    }


def build_records(
    plans: list[ShareScenarioPlan],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], Counter[str]]:
    """Gate, label and build records in memory. A pair enters only if both members pass."""
    records: list[dict[str, Any]] = []
    tool_sets: dict[str, list[dict[str, Any]]] = {}
    drops: Counter[str] = Counter()
    for plan in plans:
        members = pair_members(plan)
        gates = [gold_gate(m) for m in members]
        failed = [g.reason for g in gates if not g.ok]
        if failed:
            drops.update(str(r) for r in failed)
            drops["pairs_dropped"] += 1
            continue
        records.extend(make_record(plan, m, g, tool_sets) for m, g in zip(members, gates,
                                                                          strict=True))  # fmt: skip
    return records, tool_sets, drops


LINK_PILOT_THRESHOLDS = {"min_examples": 1, "min_pair_fraction": 1.0, "min_class_fraction": 0.25}


# -- prospective within-pilot diversity and concentration ---------------------------------
def _concentration(values: Iterable[Any]) -> dict[str, Any]:
    counts = Counter(stable_json(v) if not isinstance(v, str) else v for v in values)
    n = sum(counts.values())
    if not n:
        return {"n": 0, "distinct": 0, "max_share": None, "effective_number": None}
    shares = [c / n for c in counts.values()]
    return {
        "n": n,
        "distinct": len(counts),
        "counts": dict(sorted(counts.items())),
        "max_share": round(max(shares), 4),
        "effective_number": round(1 / sum(s * s for s in shares), 3),  # inverse Simpson
    }


def _background(row: Mapping[str, Any]) -> dict[str, Any]:
    s = row["state_struct"]
    links = s.get("share_links", [])
    return {
        "n_files": len(s.get("files", [])),
        "n_links": len(links),
        "n_custom_links": sum(k["custom"] for k in links),
        "n_active_links": sum(k["active"] for k in links),
    }


def pilot_diversity(
    rows: list[Mapping[str, Any]],
    priors: Mapping[str, list[Mapping[str, Any]]],
    diagnostics: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Within-pilot diversity, concentration and SD1-SD3 values (descriptive; docs/30 §6).

    ``rows`` need ``template_id``, ``labels_by_horizon``, ``state_struct``, ``action_call`` and
    ``meta.oracle`` witnesses (records, or in-memory planned rows). ``priors`` maps the names of
    the prior datasets to their records. SD1 against them is reported with an explicit flag: it
    is mechanically inflated, because no prior record has a ``share_links`` field or a link tool.
    """
    from adnn.feasibility.scenario_diversity import (
        PROSPECTIVE_THRESHOLDS,
        recovery_signature_id,
        scenario_id,
    )

    def behaviour(r: Mapping[str, Any]) -> str:
        return stable_json([r["labels_by_horizon"], recovery_signature_id(r)])

    out: dict[str, Any] = {"n_records": len(rows), "levels": {}}
    for level in ("strict", "coarse"):
        ids = [scenario_id(r, level) for r in rows]
        per = Counter(ids)
        fam_ids = {f: {scenario_id(r, level) for r in rows if r["template_id"] == f}
                   for f in sorted({r["template_id"] for r in rows})}  # fmt: skip
        prior_ids = {name: {scenario_id(x, level) for x in recs} for name, recs in priors.items()}
        pooled = set().union(*prior_ids.values()) if prior_ids else set()
        diag_ids = {scenario_id(x, level) for x in diagnostics}
        n = len(rows) or 1
        out["levels"][level] = {
            "distinct_scenarios": len(per),
            "max_records_per_scenario": max(per.values(), default=0),
            "distinct_by_family": {f: len(v) for f, v in fam_ids.items()},
            "novel_fraction_vs_prior": {
                **{
                    name: round(sum(i not in s for i in ids) / n, 4)
                    for name, s in prior_ids.items()
                },
                "pooled": round(sum(i not in pooled for i in ids) / n, 4),
            },
            "novel_fraction_vs_diagnostics": round(sum(i not in diag_ids for i in ids) / n, 4)
            if diagnostics
            else None,
        }
    groups: dict[str, set[str]] = {}
    for r in [*rows, *(x for recs in priors.values() for x in recs)]:
        groups.setdefault(scenario_id(r, "coarse"), set()).add(behaviour(r))
    conflicts = sorted(k for k, v in groups.items() if len(v) > 1)
    coarse = out["levels"]["coarse"]
    out["gates_descriptive"] = {
        "SD1_novel_coarse_fraction_vs_named_priors": coarse["novel_fraction_vs_prior"]["pooled"],
        "SD1_mechanically_inflated": True,
        "SD1_note": "every link record is canonically new against the named priors by "
        "construction (new state field and new tools); not evidence of diversity",
        "SD2_max_records_per_coarse_scenario": coarse["max_records_per_scenario"],
        "SD3_conflicting_coarse_groups_pooled_with_priors": len(conflicts),
        "thresholds_prospective": PROSPECTIVE_THRESHOLDS,
        "SD4": "deferred",
    }
    bg = [_background(r) for r in rows]
    out["concentration"] = {
        "family": _concentration(r["template_id"] for r in rows),
        "recovery_signature": _concentration(recovery_signature_id(r) for r in rows),
        "labels_by_horizon": _concentration(r["labels_by_horizon"] for r in rows),
        "label_h3": _concentration(r["labels_by_horizon"]["3"] for r in rows),
        "render_style": _concentration(r.get("render_style") for r in rows),
        **({f"background_{k}": _concentration(b[k] for b in bg) for k in bg[0]} if bg else {}),
    }
    out["recovery_signatures_by_family"] = {
        f: sorted({recovery_signature_id(r) for r in rows if r["template_id"] == f})
        for f in sorted({r["template_id"] for r in rows})
    }
    out["recovery_signatures_by_label_h3"] = {
        lab: sorted({recovery_signature_id(r) for r in rows if r["labels_by_horizon"]["3"] == lab})
        for lab in sorted({r["labels_by_horizon"]["3"] for r in rows})
    }
    return out
