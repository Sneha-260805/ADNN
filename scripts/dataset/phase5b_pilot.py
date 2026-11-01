"""Phase 5B controlled scaling pilot (docs/26). Run from the repository root.

    python scripts/dataset/phase5b_pilot.py freeze      # once, BEFORE any generation
    python scripts/dataset/phase5b_pilot.py generate [--out data/scaling_pilot]
    python scripts/dataset/phase5b_pilot.py audit       # quality, leakage, stop conditions,
                                                        # reproducibility, performance

``freeze`` writes ``docs/preregistration/phase5b_manifest.json`` (committable) and refuses
to overwrite it. ``generate`` refuses to run on a manifest whose hash does not verify.
Records go to ``data/scaling_pilot/`` and audits to ``results/phase5b/``; both are
git-ignored. The existing 210-example pilot is only read (for duplicate rejection).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from adnn.dataset.schema import stable_json, write_json, write_jsonl
from adnn.feasibility import stop_conditions as sc
from adnn.feasibility.composition import (
    class_balance,
    duplicate_templates,
    minimal_pairs,
    split_leakage,
    template_signature,
)
from adnn.feasibility.pilot_audit import audit as evidence_audit
from adnn.feasibility.scaling_pilot import (
    build_manifest,
    existing_inputs,
    generate,
    structure_signature,
    sw_sampler_assessment,
    verify_manifest,
)

MANIFEST = Path("docs/preregistration/phase5b_manifest.json")
EXISTING = Path("data/pilot/pilot_v0.1.jsonl")
OUT = Path("data/scaling_pilot")
RESULTS = Path("results/phase5b")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()  # fmt: skip


def cmd_freeze() -> None:
    if MANIFEST.exists():
        raise SystemExit("phase5b manifest already frozen; refusing to overwrite")
    code = {
        str(p): _sha(p)
        for p in (
            Path("src/adnn/feasibility/scaling_pilot.py"),
            Path("src/adnn/feasibility/stop_conditions.py"),
            Path("src/adnn/dataset/pilot.py"),
            Path("src/adnn/sandbox/restoration.py"),
            Path("src/adnn/sandbox/tools.py"),
        )
    }
    doc = build_manifest(_git_head(), sw_sampler_assessment(), code)
    doc["frozen_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # frozen_at is outside the hashed content by construction (added after hashing)
    write_json(MANIFEST, doc)
    print(json.dumps({"sha256": doc["sha256"], "families": len(doc["sandbox"]["families"]),
                      "scienceworld": doc["scienceworld"]["decision"]}))  # fmt: skip


def _load_manifest() -> dict[str, Any]:
    doc = json.loads(MANIFEST.read_text("utf-8"))
    doc.pop("frozen_at_utc", None)
    if not verify_manifest(doc):
        raise SystemExit("manifest hash does not verify; refusing to run")
    return doc


def cmd_generate(out: Path) -> None:
    man = _load_manifest()
    t0 = time.perf_counter()
    split = {"manifest_sha256": man["sha256"], **man["sandbox"]["split"]}
    write_json(out / "split.json", split)  # frozen split written before any text
    split_sha = _sha(out / "split.json")
    existing = existing_inputs(EXISTING)
    res = generate(man, existing)
    elapsed = round(time.perf_counter() - t0, 1)
    write_jsonl(out / "records.jsonl", res["records"])
    write_json(out / "tool_sets.json", res["tool_sets"])
    report = {
        "manifest_sha256": man["sha256"],
        "split_sha256": split_sha,
        "records_sha256": _sha(out / "records.jsonl"),
        "n_records": len(res["records"]),
        "dropped": res["dropped"],
        "excluded_families": res["excluded_families"],
        "existing_pilot_checked": existing is not None,
        "elapsed_s": elapsed,
        "evidence_checksums": {
            r["id"]: hashlib.sha256(stable_json(r).encode("utf-8")).hexdigest()
            for r in res["records"]
        },
    }
    write_json(out / "generation_report.json", report)
    print(json.dumps({k: report[k] for k in ("n_records", "dropped", "excluded_families",
                                              "elapsed_s", "records_sha256")}))  # fmt: skip


def _replicate(out: Path) -> dict[str, Any]:
    t0 = time.perf_counter()
    subprocess.run([sys.executable, __file__, "generate", "--out", str(out)], check=True,
                   capture_output=True)  # fmt: skip
    return {"dir": str(out), "records_sha256": _sha(out / "records.jsonl"),
            "elapsed_s": round(time.perf_counter() - t0, 1)}  # fmt: skip


def cmd_audit() -> None:
    man = _load_manifest()
    gen = json.loads((OUT / "generation_report.json").read_text("utf-8"))
    recs = [json.loads(x) for x in (OUT / "records.jsonl").read_text("utf-8").splitlines() if x]
    test = man["sandbox"]["split"]["test_families"]
    t0 = time.perf_counter()
    ev = evidence_audit(recs, oq24=True)
    t_audit = round(time.perf_counter() - t0, 1)
    rows = {r["id"]: r for r in ev["rows"]}
    rederive_fail = sum(not r["agrees"] or r["support"] == "unsupported" for r in ev["rows"])
    gold = [
        r
        for r in recs
        if r["tier"] == "G"
        and rows[r["id"]]["agrees"]
        and rows[r["id"]]["support"] != "unsupported"
    ]
    gold_ids = {r["id"] for r in gold}
    strict = minimal_pairs(recs, justified=lambda r: r["id"] in gold_ids)
    spec_pairs = minimal_pairs(recs, justified=lambda r: True)
    dup = duplicate_templates(recs)
    struct = Counter(structure_signature(r) for r in recs)
    existing = (
        [json.loads(x) for x in EXISTING.read_text("utf-8").splitlines() if x]
        if EXISTING.exists()
        else []
    )
    old_tpl = {template_signature(r) for r in existing}
    old_struct = {structure_signature(r) for r in existing}
    leak = split_leakage(recs, test)
    by_family = {
        f: dict(Counter(r["label"] for r in recs if r["template_id"] == f))
        for f in sorted({r["template_id"] for r in recs})
    }
    rep_a = _replicate(RESULTS / "replica_a")
    rep_b = _replicate(RESULTS / "replica_b")
    replication_failures = sum(x["records_sha256"] != gen["records_sha256"] for x in (rep_a, rep_b))
    checks = [
        sc.s1_sw_yield(None, None),
        sc.s2_replication(replication_failures),
        sc.s3_rubric_sensitivity(None, None),
        sc.s4_family_concentration(recs),
        sc.s5_effective_fraction(dup["effective_fraction"]),
        sc.s6_strict_pairs(strict["genuine_member_fraction"]),
        sc.s7_rederivation(rederive_fail),
    ]
    storage = {p.name: p.stat().st_size for p in sorted(OUT.glob("*")) if p.is_file()}
    doc = {
        "manifest_sha256": man["sha256"],
        "records_sha256": gen["records_sha256"],
        "n_records": len(recs),
        "planned": man["sandbox"]["planned_examples"],
        "dropped": gen["dropped"],
        "excluded_families": gen["excluded_families"],
        "by_label": dict(Counter(r["label"] for r in recs)),
        "by_tier": dict(Counter(r["tier"] for r in recs)),
        "by_tier_and_label": dict(Counter(f"{r['tier']}|{r['label']}" for r in recs)),
        "by_family": by_family,
        "by_split": {
            s: dict(
                Counter(r["label"] for r in recs if (r["template_id"] in test) == (s == "test"))
            )
            for s in ("train", "test")
        },
        "labels_by_horizon": {
            h: dict(Counter(r["labels_by_horizon"][h] for r in recs)) for h in ("1", "2", "3")
        },
        "class_balance": class_balance(recs, by="template_id")["all"],
        "evidence": ev["summary"],
        "strict_minimal_pairs": strict,
        "spec_minimal_pairs": spec_pairs,
        "duplicates": dup,
        "structure": {
            "n_structure_signatures": len(struct),
            "structure_fraction": round(len(struct) / len(recs), 4),
            "n_unique_inputs": len({(r["state_text"], r["action_text"]) for r in recs}),
            "n_unique_state_action": len(
                {stable_json([r["state_struct"], r["action_call"]]) for r in recs}
            ),
            "template_signatures_shared_with_210_pilot": len(
                {template_signature(r) for r in recs} & old_tpl
            ),
            "records_whose_structure_occurs_in_210_pilot": sum(
                structure_signature(r) in old_struct for r in recs
            ),
        },
        "leakage": leak,
        "replication": {
            "main": gen["records_sha256"],
            "a": rep_a,
            "b": rep_b,
            "failures": replication_failures,
        },
        "stop_conditions": sc.summary(checks),
        "performance": {
            "generation_s": gen["elapsed_s"],
            "audit_s": t_audit,
            "storage_bytes": storage,
        },
        "scienceworld": man["scienceworld"],
    }
    write_json(RESULTS / "audit.json", doc)
    print(
        json.dumps(
            {k: doc[k] for k in ("n_records", "by_tier_and_label", "stop_conditions")}, indent=1
        )[:4000]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("freeze", "generate", "audit"))
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    if args.mode == "freeze":
        cmd_freeze()
    elif args.mode == "generate":
        cmd_generate(args.out)
    else:
        cmd_audit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
