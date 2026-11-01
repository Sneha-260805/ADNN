"""Write the DRAFT (unfrozen) sharing-link pilot manifest (docs/30). Run from the repo root.

    python scripts/dataset/phase5e_draft_manifest.py

Plans the pilot, gates and labels every planned state **in memory** (no record or dataset file
is written), and writes only ``docs/preregistration/phase5e_pilot_manifest.DRAFT.json`` with
the planned counts, gate outcomes, per-horizon audit summary and prospective diversity values.
Refuses to run unless the Candidate A spec hash and the prior-dataset checksums verify.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from adnn.dataset import share_link_family as fam
from adnn.dataset.pilot import _git
from adnn.dataset.prompting_v11 import PROMPT_BUILDER_VERSION
from adnn.dataset.schema import sha256_file
from adnn.feasibility import share_link_diagnostics as sl

OUT = Path("docs/preregistration/phase5e_pilot_manifest.DRAFT.json")
PRIOR = {
    "pilot_v0.1": (
        Path("data/pilot/pilot_v0.1.jsonl"),
        "f66b98baac43faf1ece408cc22e645faf22aace13ad6aac86f1f2c83f1d3fc53",
    ),
    "phase5b_scaling_pilot": (
        Path("data/scaling_pilot/records.jsonl"),
        "bfd1175fb7e12c0f0993adb3f7079d29388dcf250d35f1ac37693af0236baa5b",
    ),
}


def _load(path: Path, sha: str) -> list[dict[str, Any]]:
    if sha256_file(path) != sha:
        raise SystemExit(f"{path}: checksum mismatch")
    return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x]


def main() -> int:
    spec_sha = sl.verify_spec()
    cfg = fam.GenerationConfig()
    plans = fam.plan_share_scenarios(cfg)
    counts = fam.planned_counts(plans)
    records, _, drops = fam.build_records(plans)  # in memory only
    priors = {name: _load(p, sha) for name, (p, sha) in PRIOR.items()}
    diag = [
        {"state_struct": c.state.to_dict(), "action_call": c.action}
        for c in sl.cases()
        if c.predicted != "not_definitive"
    ]
    diversity = fam.pilot_diversity(records, priors, diag)
    audit_rows = [r["meta"]["horizon_audit"]["by_horizon"] for r in records]
    doc = {
        "version": "phase5e-share-link-pilot-manifest-0.2-DRAFT",
        "status": "DRAFT - NOT FROZEN. No records may be generated from this file. Freezing "
        "needs review (docs/30 section 9); a frozen copy will get frozen_at_utc, base_commit "
        "and a sha256 file.",
        "frozen_at_utc": None,
        "base_commit": None,
        "drafted_on": _git(),
        "decisions": {
            "seed": "retain 20261102",
            "size": "about 40 diagnostic states; actual: 21 pairs = 42 states = 42 records",
            "split": "none: no formal train/test split for this diagnostic pilot",
            "horizon_sensitive_family": "s03 included only if every member's per-horizon "
            "evidence holds (horizon_audit); each horizon reported separately",
            "pooling": "kept separate from all historical datasets",
            "loading": "version-aware loader and validator for prompt builders 1.0.0 and 1.1.0",
        },
        "mechanism": {
            "spec": str(sl.SPEC_PATH).replace("\\", "/"),
            "spec_version": sl.SPEC_VERSION,
            "spec_sha256": spec_sha,
            "simulator_assumptions": [
                "custom re-activation: re-creating a revoked custom link (same file and "
                "address) re-activates the same record",
                "generated identifier and token are non-core: functional restoration ignores them",
                "token reservation: a generated token can never be claimed as a custom address",
            ],
        },
        "generation": {
            "module": "src/adnn/dataset/share_link_family.py",
            "config": cfg.to_dict(),
            "config_sha256": cfg.sha256(),
            "families": [
                {
                    "family_id": f.family_id,
                    "domain": fam.DOMAIN,
                    "pivot_factor": f.pivot_factor,
                    "pivot_values": list(f.pivot_values),
                    "expected_labels_by_horizon_declared_not_enforced": {
                        k: dict(v) for k, v in f.expected.items()
                    },
                }
                for f in fam.FAMILIES
            ],
            "counting_rule": "one base scenario = one minimal pair = two states (one per pivot "
            "value) = two records (one render style per scenario, shared by both members)",
            "planned_counts": counts,
            "planner_rule": "deterministic per (seed, family, scenario, attempt); a draw is "
            "redrawn if either member repeats the coarse canonical structure of any earlier "
            "planned state in the pilot",
            "render_styles": "kv, prose, compact cycled by scenario index; no style is "
            "test-only because there is no split",
            "prompt_builder_version": PROMPT_BUILDER_VERSION,
            "class_balance": "not forced; no I examples by design (the policy-blocked "
            "irreversible case is excluded, docs/29)",
        },
        "label_rules": {
            "gold": "oracle labels_by_horizon (assess_reversibility, horizon 3, max_nodes "
            "200000, on_budget_exhausted=return)",
            "gold_entry_gates": [
                "well-formed state: validate_state, exact round trip, link ids contiguous from "
                "lnk-0001",
                "no pending timers",
                "judged action succeeds (an id-allocation refusal is named "
                "link_id_allocation_failed)",
                "definitive oracle",
                "per-horizon evidence at h = 1, 2, 3 (R: exact witness <= h replays to "
                "canonical equality; P: approximate witness <= h replays to core but not "
                "canonical equality, and an exhaustive search through h finds no exact "
                "witness; I: exhaustive, no witness), agreeing with the primary assessment",
            ],
            "pair_rule": "if either member fails a gate the whole pair is dropped and counted",
            "expectations_and_declared_reversibility": "compared and reported only; never "
            "change a gold label or drop a record",
            "partial": "label_provisional with partial_reversibility_definition_pending_"
            "professor, as in earlier pilots",
            "oq21_alternative": "not applicable to link tools; Candidate A diagnostics showed "
            "0 label changes",
            "validator": "adnn.dataset.validation with split=None and LINK_PILOT_THRESHOLDS; "
            "re-checks ids, replays every stored witness",
        },
        "planned_in_memory_not_records": {
            "note": "computed by this script without writing records; generation still "
            "requires a frozen manifest",
            "gate_drops": dict(drops),
            "records_passing": len(records),
            "labels_by_horizon": dict(
                Counter(json.dumps(r["labels_by_horizon"], sort_keys=True) for r in records)
            ),
            "per_horizon_labels": {
                h: dict(Counter(a[h]["label"] for a in audit_rows)) for h in ("1", "2", "3")
            },
            "per_horizon_evidence_ok": all(a[h]["evidence_ok"] for a in audit_rows for h in a),
            "expectation_mismatches": [
                r["id"] for r in records if not r["meta"]["matches_expectation"]
            ],
            "declaration_disagreements": [
                r["id"] for r in records if not r["meta"]["declaration_agrees"]
            ],
            "diversity": diversity,
        },
        "prior_datasets_for_SD1": [
            {
                "name": name,
                "path": str(p).replace("\\", "/"),
                "sha256": sha,
                "n_records": len(priors[name]),
            }
            for name, (p, sha) in PRIOR.items()
        ],
        "sensitivity_prior_not_a_gate": {
            "name": "candidate_a_diagnostics_D1_D9",
            "source": "adnn.feasibility.share_link_diagnostics.cases() (definitive cases)",
            "reason": "same mechanism; novelty against it is the informative within-mechanism "
            "figure",
        },
        "stop_conditions": {
            "diversity_version": "scenario-diversity-0.2",
            "primary_level": "coarse",
            "sensitivity_level": "strict",
            "SD1": {
                "metric": "fraction of gold records whose coarse canonical scenario is absent "
                "from every named prior dataset",
                "threshold": ">= 0.50",
                "caveat": "mechanically inflated: no prior record has share_links or a link "
                "tool; met by construction and not evidence of diversity",
            },
            "SD2": {
                "metric": "maximum gold records per coarse canonical scenario",
                "threshold": "<= 3",
            },
            "SD3": {
                "metric": "coarse canonical groups, pooled with the named priors, whose "
                "members' labels_by_horizon or recovery signature differ",
                "threshold": "== 0",
            },
            "SD4": "deferred until an explicit, auditable mechanism taxonomy and "
            "irreversibility-cause representation exist; recovery signatures are not causal "
            "mechanisms",
            "on_failure": "report and stop; no reseeding or planner tuning after seeing results",
        },
        "leakage_checks": {
            "scenario_level": [
                "every planned state has a distinct strict and coarse canonical scenario",
                "overlap with prior-dataset and diagnostic scenarios reported (strict and coarse)",
            ],
            "family_level": [
                "no split, so there is no train/test family leakage to check; families are "
                "reported separately and never pooled with historical datasets",
            ],
            "prompt": "validator leakage tokens plus tests: no label word, depth, witness, "
            "scenario/family/pair id or recovery certificate in 1.1.0 prompts",
        },
        "reporting": "strict and coarse canonical counts separately: within the pilot, per "
        "family, against each named prior, against the diagnostics; recovery signatures and "
        "concentration (max share, inverse-Simpson effective number) per family, label, render "
        "style and background factor; each horizon separately",
        "novelty_inflation_risk": {
            "risk": "share_links is a new state field and the link tools are new actions, so "
            "SD1 against the named priors is mechanically about 1.0",
            "mitigations": [
                "SD2 and within-pilot distinct coarse counts are the binding diversity measures",
                "novelty against the Candidate A diagnostics is the within-mechanism figure",
                "recovery-signature counts and concentration are reported next to structural "
                "counts, so background variation is not read as mechanism variation",
                "sandbox configuration is not varied",
            ],
        },
        "exclusions": [
            "policy-blocked irreversible link case (docs/29)",
            "generated-address create (always P, no state-dependent pair)",
            "states with link-id gaps or other malformed hand-built states (gate)",
            "pooling with historical datasets",
        ],
        "open_decisions_for_review": [
            "freeze this manifest (records may be generated only after that)",
            "whether 42 states with 5 recovery signatures and no I class suffice for the "
            "pilot's diagnostic purpose",
        ],
    }
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(
        json.dumps(
            {
                "counts": counts,
                "drops": dict(drops),
                "records": len(records),
                "gates": diversity["gates_descriptive"],
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
