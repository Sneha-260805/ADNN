"""Run the Phase 4G constructed cases through evidence collection and admission (docs/23).

Run from the repository root with the isolated runtime configured (see
``provisional_pilot.py``), after ``certificate_verification.py``::

    .venv/Scripts/python.exe scripts/scienceworld/label_validation.py [--case ID ...]

``--redecide`` re-applies the decision rule to the saved evidence (e.g. after the
certificate reports were regenerated) without re-running the simulator.

Writes ``results/scienceworld_label_validation/<case>.json`` (evidence + decision) and
``summary.json`` (git-ignored). Decisions are eligibility outcomes, not gold labels; the
35 Phase 4E provisional records are not touched.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.admission import decide
from adnn.scienceworld.label_cases import LABEL_CASES
from adnn.scienceworld.label_evidence import collect_case

OUT = Path("results/scienceworld_label_validation")
CERTS = Path("results/scienceworld_certificates")


def load_reports() -> dict[str, dict]:
    reports = {}
    for p in sorted(CERTS.glob("C-*.json")):
        r = json.loads(p.read_text("utf-8"))
        reports[r["certificate_id"]] = r
    return reports


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", action="append", default=[])
    ap.add_argument("--redecide", action="store_true", help="reuse saved evidence")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    reports = load_reports()
    if not reports:
        raise SystemExit("run certificate_verification.py first")
    summary = []
    for spec in LABEL_CASES:
        if args.case and spec.case_id not in args.case:
            continue
        path = OUT / f"{spec.case_id}.json"
        if args.redecide:
            evidence = json.loads(path.read_text("utf-8"))["evidence"]
        else:
            evidence = collect_case(spec, config=RuntimeConfig.from_env())
        decision = decide(evidence, reports)
        doc = {"evidence": evidence, "decision": decision}
        path.write_text(json.dumps(doc, indent=1) + "\n", "utf-8")
        row = {
            "case_id": spec.case_id,
            "expected": spec.expected,
            "outcome": decision["outcome"],
            "quarantined": decision["quarantined"],
            "reasons": decision["reasons"],
            "witness": decision["witness"],
            "evidence_status": evidence["status"],
            "elapsed_s": evidence.get("elapsed_s"),
        }
        summary.append(row)
        print(json.dumps({k: row[k] for k in ("case_id", "outcome", "quarantined", "reasons")}))
    if not args.case:
        counts = Counter(r["outcome"] for r in summary)
        (OUT / "summary.json").write_text(
            json.dumps({"counts": dict(counts), "cases": summary}, indent=1) + "\n", "utf-8"
        )
        print(json.dumps(dict(counts)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
