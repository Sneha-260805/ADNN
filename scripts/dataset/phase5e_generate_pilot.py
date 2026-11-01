"""Generate the Phase 5E sharing-link diagnostic pilot from the FROZEN manifest (docs/30).

    python scripts/dataset/phase5e_generate_pilot.py --out results/phase5e/pilot/run1

Orchestration only: every definition (families, gates, oracle, builder 1.1.0) comes from the
code at the manifest's ``base_commit``. Refuses to run unless the frozen manifest matches its
sha256 sidecar, HEAD descends from ``base_commit``, ``src/adnn`` is unchanged since then, the
generation config equals the frozen one and the prior datasets match their checksums.

Writes ``records.jsonl``, ``tool_sets.json``, ``manifest.json`` (loadable by
``adnn.dataset.api.load_dataset``) and ``generation_report.json``. Exit status 1 if any stop
condition of the frozen manifest is hit; the output is kept either way.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from adnn.dataset import share_link_family as fam
from adnn.dataset.api import load_dataset
from adnn.dataset.schema import HORIZONS, sha256_file, write_json, write_jsonl
from adnn.dataset.validation import validate_directory
from adnn.feasibility import share_link_diagnostics as sl
from adnn.feasibility.scenario_diversity import recovery_signature_id

FROZEN = Path("docs/preregistration/phase5e_pilot_manifest.json")
SIDECAR = Path("docs/preregistration/phase5e_pilot_manifest.sha256")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def verify_freeze() -> dict[str, Any]:
    """Return the frozen manifest; raise SystemExit if any freeze check fails."""
    sha = hashlib.sha256(FROZEN.read_bytes()).hexdigest()
    if sha != SIDECAR.read_text("utf-8").split()[0]:
        raise SystemExit(f"frozen manifest sha256 {sha} does not match its sidecar")
    m = json.loads(FROZEN.read_text("utf-8"))
    base = m["base_commit"]
    if not m["status"].startswith("FROZEN") or not m["frozen_at_utc"] or not base:
        raise SystemExit("manifest is not frozen")
    if _git("merge-base", "--is-ancestor", base, "HEAD").returncode != 0:
        raise SystemExit(f"HEAD does not descend from base_commit {base}")
    if _git("diff", "--quiet", base, "--", "src/adnn").returncode != 0:
        raise SystemExit("src/adnn differs from base_commit; definitions must not change")
    cfg = fam.GenerationConfig()
    if (
        cfg.to_dict() != m["generation"]["config"]
        or cfg.sha256() != m["generation"]["config_sha256"]
    ):
        raise SystemExit("generation config differs from the frozen manifest")
    if sl.verify_spec() != m["mechanism"]["spec_sha256"]:
        raise SystemExit("Candidate A spec hash differs from the frozen manifest")
    for prior in m["prior_datasets_for_SD1"]:
        if sha256_file(Path(prior["path"])) != prior["sha256"]:
            raise SystemExit(f"prior dataset {prior['name']} checksum mismatch")
    m["_sha256"] = sha
    return m


def _pair_contract(records: list[dict[str, Any]]) -> list[str]:
    """Actual h3 minimal-pair contract: two members, identical action bytes, different labels."""
    pairs: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        pairs.setdefault(r["pair_id"], []).append(r)
    bad = []
    for pid, members in sorted(pairs.items()):
        if len(members) != 2:
            bad.append(f"{pid}: {len(members)} members")
            continue
        a, b = members
        if a["action_text"].encode() != b["action_text"].encode():
            bad.append(f"{pid}: action text differs")
        if a["labels_by_horizon"]["3"] == b["labels_by_horizon"]["3"]:
            bad.append(f"{pid}: equal h3 labels")
    return bad


def _residual_type(diffs: list[str]) -> str:
    """Classify a residual from ``share_link_diagnostics.residual`` (links keyed by id)."""
    added = [d for d in diffs if ": added " in d]
    if not diffs:
        return "none"
    if any("'active': True" in d for d in added):  # a new active link replaces the old one
        return "identity_loss"
    if added:  # a new record remains, inactive
        return "residual_history"
    if all(d.endswith((".access: view -> edit", ".access: edit -> view")) for d in diffs):
        return "stale_access_on_revoked_record"
    return "other: " + "; ".join(diffs)


def generate(out: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = fam.GenerationConfig()
    plans = fam.plan_share_scenarios(cfg)
    counts = fam.planned_counts(plans)
    records, tool_sets, drops = fam.build_records(plans)
    t_build = time.perf_counter() - t0
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "records.jsonl", records)
    write_json(out / "tool_sets.json", tool_sets)
    dataset_manifest = {
        "dataset_version": fam.DATASET_VERSION,
        "purpose": "Phase 5E DIAGNOSTIC pilot (sharing links); diagnostic coverage of one "
        "mechanism, not a training or evaluation dataset; never pooled with historical data",
        "prompt_builder_version": cfg.prompt_builder_version,
        "generator_version": fam.GENERATOR_VERSION,
        "frozen_manifest": {
            "path": str(FROZEN).replace("\\", "/"),
            "sha256": manifest["_sha256"],
            "base_commit": manifest["base_commit"],
        },
        "generation_config": cfg.to_dict(),
        "generation_config_sha256": cfg.sha256(),
        "split": None,
        "files": {
            "dataset": {"file": "records.jsonl", "sha256": sha256_file(out / "records.jsonl")},
            "tool_sets": {"file": "tool_sets.json", "sha256": sha256_file(out / "tool_sets.json")},
        },
        "counts": {"records": len(records), "drops": dict(drops)},
    }
    write_json(out / "manifest.json", dataset_manifest)

    t1 = time.perf_counter()
    rep = validate_directory(out, thresholds=fam.LINK_PILOT_THRESHOLDS)
    ds = load_dataset(out)
    hash_ok = sum(
        ds.probe_prompt(r).prompt_sha256 == r["meta"]["probe_prompt_sha256"]
        and ds.stated_prompt(r).prompt_sha256 == r["meta"]["stated_prompt_sha256"]
        for r in ds.records
    )
    t_validate = time.perf_counter() - t1

    priors = {
        p["name"]: [json.loads(x) for x in Path(p["path"]).read_text("utf-8").splitlines() if x]
        for p in manifest["prior_datasets_for_SD1"]
    }
    diag = [
        {"state_struct": c.state.to_dict(), "action_call": c.action}
        for c in sl.cases()
        if c.predicted != "not_definitive"
    ]
    diversity = fam.pilot_diversity(records, priors, diag)
    prior_signatures = {recovery_signature_id(x) for recs in priors.values() for x in recs}
    pilot_signatures = sorted({recovery_signature_id(r) for r in records})
    residual_types = Counter()
    per_record = []
    for r in records:
        audit = r["meta"]["horizon_audit"]["by_horizon"]
        types = {h: _residual_type(audit[h].get("residual", [])) for h in audit}
        residual_types.update(f"h{h}:{t}" for h, t in types.items())
        per_record.append(
            {
                "id": r["id"],
                "pair_id": r["pair_id"],
                "labels_by_horizon": r["labels_by_horizon"],
                "restore_depth": r["restore_depth"],
                "approx_restore_depth": r["approx_restore_depth"],
                "exact_witness": r["meta"]["oracle"]["exact_witness"],
                "approx_witness": r["meta"]["oracle"]["approx_witness"],
                "evidence_ok_by_horizon": {h: audit[h]["evidence_ok"] for h in audit},
                "residual_type_by_horizon": types,
                "matches_expectation": r["meta"]["matches_expectation"],
                "declaration_agrees": r["meta"]["declaration_agrees"],
            }
        )
    planned = manifest["generation"]["planned_counts"]
    stops = {
        "planned_counts_differ_from_frozen": counts != planned,
        "gate_drops": dict(drops),
        "record_count": len(records) != planned["records_if_all_pass_gates"],
        "pair_contract_violations": _pair_contract(records),
        "unsupported_labels": [
            x["id"] for x in per_record if not all(x["evidence_ok_by_horizon"].values())
        ],
        "validator_errors": rep.errors,
        "loader_prompt_hash_failures": len(ds.records) - hash_ok,
    }
    gates = diversity["gates_descriptive"]
    gate_fail = {
        "SD1": gates["SD1_novel_coarse_fraction_vs_named_priors"] < 0.50,
        "SD2": gates["SD2_max_records_per_coarse_scenario"] > 3,
        "SD3": gates["SD3_conflicting_coarse_groups_pooled_with_priors"] != 0,
    }
    stopped = any(bool(v) for v in stops.values())
    report = {
        "status": "STOPPED" if stopped else "OK",
        "stop_conditions": stops,
        "prospective_gates_failed": gate_fail,
        "frozen_manifest_sha256": manifest["_sha256"],
        "base_commit": manifest["base_commit"],
        "head": _git("rev-parse", "HEAD").stdout.strip(),
        "generation_config_sha256": cfg.sha256(),
        "output_sha256": {k: v["sha256"] for k, v in dataset_manifest["files"].items()},
        "counts": counts,
        "labels_by_horizon": {
            str(h): dict(Counter(r["labels_by_horizon"][str(h)] for r in records)) for h in HORIZONS
        },
        "label_patterns": dict(
            Counter(json.dumps(r["labels_by_horizon"], sort_keys=True) for r in records)
        ),
        "labels_by_family_h": {
            f: {
                str(h): dict(
                    Counter(
                        r["labels_by_horizon"][str(h)] for r in records if r["template_id"] == f
                    )
                )
                for h in HORIZONS
            }
            for f in fam.FAMILY_IDS
        },
        "expectation_mismatches": [x["id"] for x in per_record if not x["matches_expectation"]],
        "declaration_disagreements": [x["id"] for x in per_record if not x["declaration_agrees"]],
        "residual_types": dict(sorted(residual_types.items())),
        "validator": {
            "errors": rep.errors,
            "warnings": rep.warnings,
            "checks_run": dict(rep.checks_run),
        },
        "loader": {
            "records": len(ds),
            "minimal_pairs": len(ds.minimal_pairs()),
            "prompt_hashes_rebuilt": hash_ok,
        },
        "diversity": diversity,
        "novelty_interpretation": {
            "mechanical_novelty": "SD1 = coarse novelty vs the named priors; 1.0 by "
            "construction because the link field and tools are new (not evidence)",
            "causal_novelty": {
                "mechanisms": 1,
                "mechanism": "Candidate A sharing links (share-links-spec-1.0)",
                "recovery_signatures": pilot_signatures,
                "recovery_signatures_new_vs_priors": [
                    s for s in pilot_signatures if s not in prior_signatures
                ],
                "note": "new signatures are new only because the tools are new; the pilot "
                "covers one mechanism with three residual kinds",
            },
        },
        "records": per_record,
        "runtime_s": {
            "build_and_label": round(t_build, 1),
            "validate_and_load": round(t_validate, 1),
            "total": round(time.perf_counter() - t0, 1),
        },
    }
    write_json(out / "generation_report.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    manifest = verify_freeze()
    report = generate(args.out, manifest)
    keys = (
        "status",
        "stop_conditions",
        "prospective_gates_failed",
        "output_sha256",
        "labels_by_horizon",
        "residual_types",
        "runtime_s",
    )
    print(json.dumps({k: report[k] for k in keys}, indent=1))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
