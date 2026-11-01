"""Phase 5A measurement-symmetry check over every Phase 4G and 4H case (docs/25 §4).

Run from the repository root with the isolated runtime configured::

    python scripts/scienceworld/phase5a_symmetry.py

For each case it collects evidence twice, in fresh sessions: once with the frozen
asymmetric protocol and once with the symmetric counterfactual. Both runs are decided
under ``sw-admission-2``. Outputs go to ``results/phase5a/symmetry/`` (git-ignored).
Frozen Phase 4G/4H results are neither read for decisions nor overwritten. Affected
cases are listed for quarantine.
"""

from __future__ import annotations

import json
from pathlib import Path

from adnn.scienceworld import RuntimeConfig
from adnn.scienceworld.admission import decide
from adnn.scienceworld.label_cases import LABEL_CASES
from adnn.scienceworld.label_evidence import collect_case
from adnn.scienceworld.measurement_symmetry import (
    SYMMETRY_VERSION,
    compare_protocols,
    symmetric_protocol,
)
from adnn.scienceworld.phase4h_cases import PHASE4H_CASES

OUT = Path("results/phase5a/symmetry")
CERTS = Path("results/scienceworld_certificates")


def _write(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=1) + "\n")


def main() -> int:
    reports = {}
    for p in sorted(CERTS.glob("C-*.json")):
        r = json.loads(p.read_text("utf-8"))
        reports[r["certificate_id"]] = r
    config = RuntimeConfig.from_env()
    specs = [*LABEL_CASES, *(r.spec for r in PHASE4H_CASES)]
    rows = {}
    for spec in specs:
        ev_a = collect_case(spec, config=config)
        asym = {"evidence": ev_a, "decision": decide(ev_a, reports)}
        with symmetric_protocol() as runs:
            ev_s = collect_case(spec, config=config)
        sym = {"evidence": ev_s, "decision": decide(ev_s, reports)}
        pairs = [p for run in runs for p in run.pairs]
        row = compare_protocols(asym, sym, pairs) if ev_a["status"] == "complete" else {
            "status": [ev_a["status"], ev_s["status"]],
            "affected": ev_a["status"] != ev_s["status"],
            "outcome": [asym["decision"]["outcome"], sym["decision"]["outcome"]]}  # fmt: skip
        rows[spec.case_id] = row
        _write(OUT / f"{spec.case_id}.json", {"asymmetric": asym, "symmetric": sym,
                                              "cf_pairs": pairs, "comparison": row})  # fmt: skip
        print(json.dumps({spec.case_id: {k: row[k] for k in ("outcome", "affected")}}))
    affected = sorted(k for k, v in rows.items() if v["affected"])
    _write(OUT.parent / "symmetry_summary.json",
           {"version": SYMMETRY_VERSION, "n_cases": len(rows), "affected": affected,
            "quarantine": affected, "cases": rows})  # fmt: skip
    print(json.dumps({"n": len(rows), "affected": affected}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
