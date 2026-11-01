"""Write the prospective production manifest (ADR-0009) BEFORE any record is generated.

    python scripts/dataset/phase5h_freeze_manifest.py

Requires a clean ``src/adnn`` at HEAD (the manifest's ``base_commit``). Writes
``docs/preregistration/production_manifest.json`` and its ``.sha256`` sidecar; commit both
in a freeze commit, then run ``phase5h_generate.py``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

from adnn.dataset import production as prod
from adnn.dataset.validation import PARTIAL_POLICY_TEAM
from adnn.scienceworld import export as sx

OUT = Path("docs/preregistration/production_manifest.json")
SIDECAR = Path("docs/preregistration/production_manifest.sha256")
PROTECTED = {
    "data/pilot/pilot_v0.1.jsonl": "f66b98baac43faf1ece408cc22e645faf22aace13ad6aac86f1f2c83f1d3fc53",  # noqa: E501
    "data/scaling_pilot/records.jsonl": "bfd1175fb7e12c0f0993adb3f7079d29388dcf250d35f1ac37693af0236baa5b",  # noqa: E501
    "docs/preregistration/phase5b_manifest.json": "887e42ba79b34f1c7eacadb4c777fce9869b31b0ef32aadfe7a86363edffb72f",  # noqa: E501
    "docs/preregistration/phase5d_share_link_spec.md": "5da475c50cf6f472014e3d2e4a5d53d9120f765915751126f4a3c9d09858e137",  # noqa: E501
    "docs/preregistration/phase5e_pilot_manifest.json": "e3fe50101c05bb96337e1644a6920fb98ba20a1a6f9e0ed46e996bb91a8f9fdd",  # noqa: E501
}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main() -> int:
    if _git("status", "--porcelain", "--", "src/adnn").strip():
        raise SystemExit("src/adnn has uncommitted changes: commit the code first")
    for path, sha in PROTECTED.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != sha:
            raise SystemExit(f"{path}: protected artifact changed")
    cfg = prod.ProductionConfig()
    head = _git("rev-parse", "HEAD").strip()
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "manifest": "adnn-production",
        "version": "1.0",
        "status": "FROZEN: prospective, written before any production record was generated",
        "frozen_at_utc": now,
        "base_commit": head,
        "decision_record": "docs/decisions/0009-production-dataset.md",
        "dataset_version": prod.DATASET_VERSION,
        "professor_requirements": {
            "size": "target >= 2,000 labelled (state, action) pairs from both testbeds; "
            "if missed, REQ-DATA-01 is reported unmet (ADR-0006 D8), never padded",
            "balance": "roughly balanced, else report class counts and use balanced accuracy",
            "split": "20% test, split by scenario (scenario_grouped), never by row",
            "minimal_pairs": ">= 30% of records in strict minimal pairs (ADR-0006 D6)",
        },
        "generation": {"config": cfg.to_dict(), "config_sha256": cfg.sha256()},
        "prompt_builder_version": cfg.prompt_builder_version,
        "partial_definition_policy": PARTIAL_POLICY_TEAM,
        "label_rules": {
            "sandbox_gold": "oracle definitive at h=3 (complete search, judged action ok, no "
            "pending timers); OQ-21 alternative not label-changing; link records also pass "
            "share_link_family.gold_gate with a definitive OQ-21 alternative",
            "partial": "scaling_pilot.PARTIAL_RULE (ADR-0006 D11)",
            "tier_P": "OQ-21-sensitive: sensitivity_oq21.jsonl only, never gold, not split",
            "scienceworld_gold": sx.SW_PARTIAL_RULE + "; plus R5 replication, query-order "
            "audit, symmetry and rubric stability; labels from frozen sw-admission-2 decisions",
            "minimal_pair": "same family world at two pivot values, byte-identical action, "
            "both gold, different h3 labels (family actions always; alternative actions "
            "only when the oracle labels differ)",
        },
        "grouping_version": prod.GROUPING_VERSION,
        "gates": {
            "min_pair_fraction": cfg.min_pair_fraction,
            "family_share_cap": cfg.family_share_cap,
            "sd3_conflicting_coarse_groups": 0,
            "test_fraction_range": [0.18, 0.22],
            "compact_test_only": True,
            "validator_errors": 0,
        },
        "scienceworld": {
            "decision_rule": sx.DECISION_RULE,
            "exporter_version": sx.EXPORTER_VERSION,
            "cases": {c: sx.sha256_path(sx.EVIDENCE_DIR / f"{c}.json") for c in sx.COMPLETE_CASES},
            "excluded": sx.EXCLUDED_CASES,
            "split_rule": "by ScienceWorld task family (ADR-0006 D9): the family whose record "
            "count is closest to 20% of ScienceWorld records goes to test (ties: sorted id)",
        },
        "protected_artifacts_sha256": PROTECTED,
        "outputs": "data/production/v1.0/ (git-ignored); checksums in manifest.json and "
        "generation_report.json",
    }
    text = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    with open(SIDECAR, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{sha}  {OUT.name}\nfrozen_at_utc {now}\nbase_commit {head}\n")
    print(sha, head, now)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
