"""SWT pilot evidence, rubric sensitivity, replication, query-order audit, symmetry and the
frozen go/no-go evaluation (approved pilot, 2026-11-04).

Run from the repository root with the isolated runtime configured, AFTER ``freeze.py``::

    python scripts/scienceworld/swt_pilot/run.py main       # M1 + rubric-1 declarations
    python scripts/scienceworld/swt_pilot/run.py replica    # second fresh process (eligible)
    python scripts/scienceworld/swt_pilot/run.py audit      # query-order audit (eligible)
    python scripts/scienceworld/swt_pilot/run.py symmetry   # symmetric protocol (eligible)
    python scripts/scienceworld/swt_pilot/run.py compare    # pure: replication + sensitivity
    python scripts/scienceworld/swt_pilot/run.py gate       # pure: tier G + G1-G5 verdict

Resume (added after the first main run was stopped by host memory pressure; the frozen
pre-registration is unchanged): every collecting mode skips a case only if its stored
evidence is readable, matches the frozen case definition and declaration hash, and its
stored decision equals a fresh ``decide`` on the stored evidence; anything else is rerun.
Files are written atomically. Before every JVM launch free RAM is checked; below
``MIN_FREE_GB`` the run stops cleanly (exit 3) and keeps all completed evidence.
``--limit N`` collects at most N cases per invocation (for short foreground chunks).

Every mode first verifies the frozen manifest (records, rubric declarations, cases module,
sidecar) and refuses to run on any mismatch. Decisions use the unchanged ``sw-admission-2``
and the Phase 4G certificate reports. Outputs go to ``results/swt_pilot/`` (git-ignored).
Nothing here writes a dataset record or a gold label; unresolved cases stay unresolved.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cases import SWT_PILOT_CASES

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.admission import DECISION_RULE_VERSION, decide
from adnn.scienceworld.label_evidence import collect_case
from adnn.scienceworld.measurement_symmetry import compare_protocols, symmetric_protocol
from adnn.scienceworld.preregistration import verify_manifest
from adnn.scienceworld.query_audit import AuditScenario, audit_scenario
from adnn.scienceworld.semantics import declaration_from_dict

PREREG = Path("docs/preregistration/swt_pilot")
OUT = Path("results/swt_pilot")
CERTS = Path("results/scienceworld_certificates")
ELIGIBLE = ("eligible_reversible", "eligible_partially_reversible", "eligible_irreversible")
LABEL_OF = {"eligible_reversible": "R", "eligible_partially_reversible": "P"}
BY_ID = {r.case_id: r for r in SWT_PILOT_CASES}
MIN_FREE_GB = 1.5
LIMIT: int | None = None  # set by --limit


class MemoryLowError(SystemExit):
    pass


def _write(path: Path, doc: object) -> None:
    """Atomic write: a killed process never leaves a partial evidence file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=1) + "\n")
    os.replace(tmp, path)


class _MemStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def free_gb() -> float:
    ms = _MemStatus()
    ms.dwLength = ctypes.sizeof(_MemStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))  # type: ignore[attr-defined]
    return ms.ullAvailPhys / 2**30


def _guard(what: str) -> None:
    gb = free_gb()
    if gb < MIN_FREE_GB:
        print(json.dumps({"stopped": "memory_low", "free_gb": round(gb, 2), "before": what}))
        raise MemoryLowError(3)


def _budget(done: list[str]) -> bool:
    """True while this invocation may collect another case (``--limit``)."""
    return LIMIT is None or len(done) < LIMIT


def _rubric_decl(cid: str, rubric: dict[str, Any]) -> Any:
    r = declaration_from_dict(rubric["cases"][cid]["declaration"])
    return replace(r, paths=BY_ID[cid].spec.declaration.paths)  # property choice only


def _valid(path: Path, cid: str, case_id: str, decl_sha: str, reports: dict[str, dict]) -> bool:
    """Stored evidence is complete, readable and belongs to the frozen case definition, and
    its stored decision equals a fresh decision on the stored evidence."""
    try:
        doc = _read(path)
        ev, dec = doc["evidence"], doc["decision"]
        spec = BY_ID[cid].spec
        case = ev["case"]
        same = (
            case["case_id"] == case_id
            and case["family_id"] == spec.family.family_id
            and case["task"] == spec.family.task
            and ev["provenance"]["recipe"]["variation"] == spec.family.variation
            and case["history"] == list(spec.history)
            and case["target"] == spec.target
            and ev["declaration_sha256"] == decl_sha
            and ev["status"] is not None
        )
        fresh = decide(ev, reports)
        keys = ("outcome", "reasons", "witness", "quarantined")
        return same and all(fresh[k] == dec[k] for k in keys)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _read(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def _reports() -> dict[str, dict]:
    reports = {}
    for p in sorted(CERTS.glob("C-*.json")):
        r = _read(p)
        reports[r["certificate_id"]] = r
    if not reports:
        raise SystemExit("Phase 4G certificate reports missing")
    return reports


def _verify() -> dict[str, Any]:
    if DECISION_RULE_VERSION != "sw-admission-2":
        raise SystemExit(f"rule changed to {DECISION_RULE_VERSION}; pilot pinned to sw-admission-2")
    text = (PREREG / "manifest.json").read_bytes()
    side = (PREREG / "manifest.sha256").read_text("utf-8").split()[0]
    if hashlib.sha256(text).hexdigest() != side:
        raise SystemExit("manifest.json differs from manifest.sha256")
    bad = verify_manifest(SWT_PILOT_CASES, PREREG / "manifest.json")
    if bad:
        raise SystemExit(f"pre-registration differs from the frozen manifest: {bad}")
    man = json.loads(text)
    cases_sha = hashlib.sha256(
        Path(__file__).with_name("cases.py").read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    if cases_sha != man["cases_module_sha256"]:
        raise SystemExit("cases.py differs from the frozen module hash")
    rubric = _read(PREREG / "rubric_declarations.json")
    for cid, row in rubric["cases"].items():
        if (
            declaration_from_dict(row["declaration"]).sha256
            != man["rubric_declaration_sha256"][cid]
        ):
            raise SystemExit(f"rubric declaration for {cid} differs from the manifest")
    return rubric


def _run(spec: Any, reports: dict[str, dict]) -> dict[str, Any]:
    _guard(spec.case_id)
    evidence = collect_case(spec, config=RuntimeConfig.from_env())
    return {"evidence": evidence, "decision": decide(evidence, reports)}


def _row(doc: dict[str, Any]) -> dict[str, Any]:
    e, d = doc["evidence"], doc["decision"]
    w = d["witness"]
    return {
        "case_id": e["case"]["case_id"],
        "evidence_status": e["status"],
        "outcome": d["outcome"],
        "quarantined": d["quarantined"],
        "reasons": d["reasons"],
        "witness": w and {k: w[k] for k in ("source", "path", "canonical_level", "restored",
                                            "residual")},
        "elapsed_s": e.get("elapsed_s"),
    }  # fmt: skip


def _timed(mode: str, fn: Any) -> None:
    t0 = time.perf_counter()
    try:
        fn()
    finally:  # accumulated across resumed invocations, including interrupted ones
        path = OUT / "runtime.json"
        rt = _read(path) if path.exists() else {}
        rt[mode] = round(rt.get(mode, 0) + time.perf_counter() - t0, 1)
        _write(path, rt)


def mode_main(rubric: dict[str, Any]) -> None:
    reports = _reports()
    done: list[str] = []
    skipped, rerun = [], []

    def paths(cid: str) -> tuple[Path, Path]:
        return OUT / "main" / f"{cid}.json", OUT / "rubric" / f"{cid}.json"

    def status(cid: str) -> tuple[bool, bool]:
        r = _rubric_decl(cid, rubric)
        mp, rp = paths(cid)
        return (_valid(mp, cid, cid, BY_ID[cid].spec.declaration.sha256, reports),
                _valid(rp, cid, r.case_id, r.sha256, reports))  # fmt: skip

    for rec in SWT_PILOT_CASES:
        cid, spec = rec.case_id, rec.spec
        ok_m, ok_r = status(cid)
        if ok_m and ok_r:
            skipped.append(cid)
            continue
        mp, rp = paths(cid)
        if mp.exists() or rp.exists():
            rerun.append(cid)
        if not _budget(done):
            continue
        if not ok_m:
            doc = _run(spec, reports)
            _write(mp, doc)
            row = _row(doc)
            print(json.dumps({k: row[k] for k in ("case_id", "outcome", "reasons")}), flush=True)
        if not ok_r:
            r = _rubric_decl(cid, rubric)
            _write(rp, _run(replace(spec, case_id=r.case_id, declaration=r), reports))
        done.append(cid)
    print(json.dumps({"verified_and_skipped": len(skipped), "invalid_or_partial": rerun,
                      "collected_now": len(done)}))  # fmt: skip
    rows, sens = [], []
    for rec in SWT_PILOT_CASES:
        if not all(status(rec.case_id)):
            print(json.dumps({"main_complete": False, "next": rec.case_id}))
            return
        mp, rp = paths(rec.case_id)
        rows.append(_row(_read(mp)))
        sens.append(_row(_read(rp)))
    counts = Counter(r["outcome"] for r in rows)
    _write(OUT / "main_summary.json", {"rule": DECISION_RULE_VERSION, "counts": counts,
                                       "cases": rows, "rubric_sensitivity": sens})  # fmt: skip
    print(json.dumps(counts))


def _eligible_ids() -> list[str]:
    return [
        r["case_id"] for r in _read(OUT / "main_summary.json")["cases"] if r["outcome"] in ELIGIBLE
    ]


def mode_replica() -> None:
    reports = _reports()
    done: list[str] = []
    for cid in _eligible_ids():
        path = OUT / "replica" / f"{cid}.json"
        if _valid(path, cid, cid, BY_ID[cid].spec.declaration.sha256, reports):
            continue
        if not _budget(done):
            print(json.dumps({"replica_complete": False, "next": cid}))
            return
        doc = _run(BY_ID[cid].spec, reports)
        _write(path, doc)
        done.append(cid)
        print(json.dumps(_row(doc)), flush=True)
    print(json.dumps({"replica_complete": True}))


def mode_audit() -> None:
    out: dict[str, Any] = {}
    done: list[str] = []
    for cid in _eligible_ids():
        part = OUT / "audit" / f"{cid}.json"
        try:
            prev = _read(part)
            if prev["conditions"]:
                out[cid] = prev
                continue
        except (OSError, ValueError, KeyError):
            pass
        if not _budget(done):
            print(json.dumps({"audit_complete": False, "next": cid}))
            return
        _guard(f"audit {cid}")
        done.append(cid)
        rec = BY_ID[cid]
        witness = _read(OUT / "main" / f"{cid}.json")["decision"]["witness"] or {}
        fam = rec.spec.family
        actions = (*fam.base_actions, *rec.spec.history, rec.spec.target, *witness.get("path", []))
        audit = audit_scenario(
            AuditScenario(cid, fam.task, fam.variation, actions),
            repeats=1, shared=False, config=RuntimeConfig.from_env(),
        )  # fmt: skip
        comps = audit.summary()["comparisons"]
        out[cid] = {
            "actions": list(actions),
            "conditions": {c["condition"]: {k: c[k] for k in (
                "transitions_equal_all_k", "valid_actions_equal_all_k", "n_k_state_differs")}
                for c in comps},
        }  # fmt: skip
        _write(part, out[cid])
        print(json.dumps({cid: out[cid]["conditions"]}), flush=True)
    _write(OUT / "measurement_audit.json", out)
    print(json.dumps({"audit_complete": True}))


def mode_symmetry() -> None:
    """Symmetric-protocol collection; the asymmetric arm is the frozen-protocol main run."""
    reports = _reports()
    rows: dict[str, Any] = {}
    done: list[str] = []
    for cid in _eligible_ids():
        part = OUT / "symmetry" / f"{cid}.json"
        try:
            prev = _read(part)
            if prev["symmetric"]["evidence"]["case"]["case_id"] == cid:
                rows[cid] = prev["comparison"]
                continue
        except (OSError, ValueError, KeyError):
            pass
        if not _budget(done):
            print(json.dumps({"symmetry_complete": False, "next": cid}))
            return
        done.append(cid)
        asym = _read(OUT / "main" / f"{cid}.json")
        with symmetric_protocol() as runs:
            sym = _run(BY_ID[cid].spec, reports)
        pairs = [p for run in runs for p in run.pairs]
        rows[cid] = compare_protocols(asym, sym, pairs)
        _write(part, {"symmetric": sym, "cf_pairs": pairs,
                                                  "comparison": rows[cid]})  # fmt: skip
        print(json.dumps({cid: {k: rows[cid][k] for k in ("outcome", "affected")}}), flush=True)
    _write(OUT / "symmetry_summary.json",
           {"n_cases": len(rows), "affected": sorted(k for k, v in rows.items() if v["affected"]),
            "cases": rows})  # fmt: skip


def _attempt_sig(doc: dict[str, Any]) -> list[Any]:
    return [
        (a["source"], tuple(a["path"]), a.get("verified"), a.get("executed"),
         tuple(sorted((t, x["canonical_level"], tuple(x["concepts"]))
                      for t, x in (a.get("assessments") or {}).items())))
        for a in doc["evidence"].get("attempts", [])
    ]  # fmt: skip


def mode_compare() -> None:
    rows = {}
    for cid in _eligible_ids():
        a, b = _read(OUT / "main" / f"{cid}.json"), _read(OUT / "replica" / f"{cid}.json")
        ea, eb = a["evidence"], b["evidence"]
        checks = {
            "s0_fingerprint": ea["replay"]["s0_raw_fingerprint"]
            == eb["replay"]["s0_raw_fingerprint"],
            "target": {k: ea["target"].get(k) for k in ("status", "ticks", "no_op")}
            == {k: eb["target"].get(k) for k in ("status", "ticks", "no_op")},
            "attempts": _attempt_sig(a) == _attempt_sig(b),
            "certificate_checks": ea.get("certificate_checks") == eb.get("certificate_checks"),
            "outcome": a["decision"]["outcome"] == b["decision"]["outcome"],
            "reasons": a["decision"]["reasons"] == b["decision"]["reasons"],
            "witness": a["decision"]["witness"] == b["decision"]["witness"],
            "stochastic_exposure": ea["exclusion_signals"] == eb["exclusion_signals"],
        }  # fmt: skip
        rows[cid] = {"replicated": all(checks.values()), "checks": checks,
                     "outcome": [a["decision"]["outcome"], b["decision"]["outcome"]]}  # fmt: skip
    summary = _read(OUT / "main_summary.json")
    sens = {}
    for m, r in zip(summary["cases"], summary["rubric_sensitivity"], strict=True):
        sens[m["case_id"]] = {"m1": m["outcome"], "rubric": r["outcome"],
                              "changed": m["outcome"] != r["outcome"],
                              "m1_reasons": m["reasons"],
                              "rubric_reasons": r["reasons"]}  # fmt: skip
    _write(OUT / "comparison.json", {"replication": rows, "rubric_sensitivity": sens})
    print(json.dumps({"replication": {k: v["replicated"] for k, v in rows.items()},
                      "sensitivity_changed": [k for k, v in sens.items() if v["changed"]]},
                     indent=1))  # fmt: skip


MECHANISM = (
    ("use lighter on ", "combustion"), ("open ", "container"), ("close ", "container"),
    ("move ", "relocation"), ("pick up ", "relocation"), ("activate ", "device"),
    ("deactivate ", "device"), ("connect ", "electrical"), ("pour ", "liquid transfer"),
    ("eat ", "consumption"),
)  # fmt: skip


def scenario(cid: str) -> dict[str, str]:
    spec = BY_ID[cid].spec
    mech = next(m for p, m in MECHANISM if spec.target.startswith(p))
    room = spec.family.family_id.rsplit("-", 3)[0].replace("-", " ")
    obj = spec.declaration.required[0].role
    return {"task": spec.family.task, "variation": str(spec.family.variation), "room": room,
            "mechanism": mech, "object": obj, "group": f"{room} | {mech} | {obj}"}  # fmt: skip


def mode_gate() -> None:
    man = _read(PREREG / "manifest.json")
    summary = _read(OUT / "main_summary.json")
    comp = _read(OUT / "comparison.json")
    audit = _read(OUT / "measurement_audit.json")
    sym = _read(OUT / "symmetry_summary.json")["cases"]
    cases = {}
    for row in summary["cases"]:
        cid = row["case_id"]
        doc = _read(OUT / "main" / f"{cid}.json")
        dec, ev = doc["decision"], doc["evidence"]
        outcome = dec["outcome"]
        eligible = outcome in ELIGIBLE and not dec["quarantined"]
        cert = dec.get("certificate") or {}
        protected = {f for c in cert.get("claims", []) for _, f in c.get("protects", [])}
        residual = (dec["witness"] or {}).get("residual") or []
        conds = audit.get(cid, {}).get("conditions", {})
        checks = {
            "eligible": eligible,
            "evidence_complete": ev["status"] == "complete" and ev["replay"]["verified"],
            "r5_replicated": comp["replication"].get(cid, {}).get("replicated") is True,
            "query_order_audit": bool(conds)
            and all(c.get("transitions_equal_all_k") for c in conds.values()),
            "symmetry_unaffected": sym.get(cid, {}).get("affected") is False,
            "rubric_unchanged": comp["rubric_sensitivity"][cid]["changed"] is False,
            "partial_residual_certified": outcome != "eligible_partially_reversible"
            or (cert.get("admissible") is True
                and all(r.split(".", 1)[1] in protected for r in residual)),
            "witness_depth_le_3": eligible and len(dec["witness"]["path"]) <= 3,
        }  # fmt: skip
        tier_g = all(checks.values()) and outcome in LABEL_OF
        cases[cid] = {
            **scenario(cid),
            "expected": BY_ID[cid].expected_category,
            "outcome": outcome,
            "reasons": dec["reasons"],
            "witness": row["witness"],
            "rubric_outcome": comp["rubric_sensitivity"][cid]["rubric"],
            "checks": checks if eligible else {"eligible": False},
            "tier_g": tier_g,
            "label": LABEL_OF[outcome] if tier_g else None,
            "elapsed_s": row["elapsed_s"],
        }
    g = [c for c in cases.values() if c["tier_g"]]
    gp = [c for c in g if c["label"] == "P"]
    gr = [c for c in g if c["label"] == "R"]
    elig = [cid for cid, c in cases.items() if c["outcome"] in ELIGIBLE]
    sens = comp["rubric_sensitivity"]
    either = [cid for cid, s in sens.items() if s["m1"] in ELIGIBLE or s["rubric"] in ELIGIBLE]
    changed = [cid for cid in either if sens[cid]["changed"]]
    affected = [cid for cid in elig if not cases[cid]["checks"].get("query_order_audit")
                or not cases[cid]["checks"].get("symmetry_unaffected")]  # fmt: skip
    replicated = [cid for cid in elig if cases[cid]["checks"].get("r5_replicated")]
    crit = {
        "G1": {"n": len(gp), "groups": len({c["group"] for c in gp}),
               "pass": len(gp) >= 8 and len({c["group"] for c in gp}) >= 4},
        "G2": {"n": len(gr), "task_families": len({c["task"] for c in gr}),
               "groups": len({c["group"] for c in gr}),
               "pass": len(gr) >= 12 and len({c["task"] for c in gr}) >= 4},
        "G3": {"eligible": len(elig), "replicated": len(replicated),
               "pass": bool(elig) and len(replicated) == len(elig)},
        "G4": {"eligible": len(elig), "affected": affected,
               "fraction": len(affected) / len(elig) if elig else None,
               "pass": bool(elig) and len(affected) / len(elig) <= 0.02},
        "G5": {"eligible_either": len(either), "changed": changed,
               "fraction": len(changed) / len(either) if either else None,
               "pass": bool(either) and len(changed) / len(either) <= 0.10},
    }  # fmt: skip
    verdict = "GO" if all(c["pass"] for c in crit.values()) else "NO-GO"
    report = {
        "pilot_id": man["pilot_id"],
        "manifest_sha256": (PREREG / "manifest.sha256").read_text("utf-8").split()[0],
        "rule": DECISION_RULE_VERSION,
        "counts": {"outcome": Counter(c["outcome"] for c in cases.values()),
                   "tier_g": Counter(c["label"] for c in g),
                   "rubric_outcome": Counter(s["rubric"] for s in sens.values())},
        "criteria": crit,
        "verdict": verdict,
        "runtime_s": _read(OUT / "runtime.json") if (OUT / "runtime.json").exists() else {},
        "cases": cases,
    }  # fmt: skip
    _write(OUT / "report.json", report)
    print(json.dumps({k: report[k] for k in ("counts", "criteria", "verdict")}, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("main", "replica", "audit", "symmetry", "compare", "gate"))
    ap.add_argument("--limit", type=int, default=None, help="collect at most N cases now")
    args = ap.parse_args()
    global LIMIT
    LIMIT = args.limit
    rubric = _verify()
    fns = {"main": lambda: mode_main(rubric), "replica": mode_replica, "audit": mode_audit,
           "symmetry": mode_symmetry, "compare": mode_compare, "gate": mode_gate}  # fmt: skip
    _timed(args.mode, fns[args.mode])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
