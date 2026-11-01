"""Phase 5H bounded feasibility check of the corrected production generator (docs/34).

    python scripts/dataset/phase5h_feasibility.py

Runs the complete production build in memory (admission, grouping, split, rendering,
selection) and writes only ``results/phase5h/feasibility.json`` (git-ignored). No dataset
file is written. Exit status 1 if any production gate fails.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from adnn.dataset import production as prod
from adnn.dataset.schema import sha256_text, stable_json, write_json

OUT = Path("results/phase5h/feasibility.json")


def main() -> int:
    t0 = time.perf_counter()
    cfg = prod.ProductionConfig()
    built = prod.build(cfg, prod.DATASET_VERSION)
    summary = prod.summarise(built.records, built.split)
    gates = prod.gates(summary, cfg)
    report = {k: v for k, v in built.report.items() if not k.startswith("_")}
    result = {
        "config": cfg.to_dict(),
        "config_sha256": cfg.sha256(),
        "build": report,
        "summary": summary,
        "gates": gates,
        "records_sha256": sha256_text(stable_json(built.records)),
        "runtime_s": round(time.perf_counter() - t0, 1),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUT, result)
    print(
        json.dumps(
            {k: result[k] for k in ("build", "gates", "records_sha256", "runtime_s")}, indent=1
        )
    )
    s = {k: v for k, v in summary.items() if k != "concentration"}
    print(
        json.dumps(s | {"max_family_share": summary["concentration"]["max_family_share"]}, indent=1)
    )
    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
