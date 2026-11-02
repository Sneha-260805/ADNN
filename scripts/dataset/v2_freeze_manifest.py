"""Write the AMENDED v2.0 production manifest (v2 amendment 1) BEFORE v2.0 is regenerated.

    python scripts/dataset/v2_freeze_manifest.py

Writes ``docs/preregistration/production_manifest_v2_amend1.json`` and its ``.sha256``
sidecar, then run ``v2_generate.py``. The original v2 freeze
(``production_manifest_v2.json``, 2026-11-02) is kept unchanged as a historical artifact and
is protected below; this script wrote it before the amendment.
The code is pinned by ``base_commit`` (HEAD) **and**
``code_sha256``, a hash of every ``src/adnn`` source file (LF-normalised), so the freeze
holds whether or not the v2 code is committed yet; the generator refuses to run if either
differs. v1.0 (its frozen manifests and its dataset files) is protected and never touched.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

from adnn.dataset import families_v2 as v2
from adnn.dataset import production as prod
from adnn.dataset.validation import PARTIAL_POLICY_TEAM
from adnn.scienceworld import export as sx

OUT = Path("docs/preregistration/production_manifest_v2_amend1.json")
SIDECAR = Path("docs/preregistration/production_manifest_v2_amend1.sha256")
AMENDS = {
    "path": "docs/preregistration/production_manifest_v2.json",
    "sha256": "ed7b24a1b04add4b1662be8703c35d7540f7e62b168f2b46766636a324fca585",
    "frozen_at_utc": "2026-11-02T17:43:49Z",
    "base_commit": "4ae4cd4ce34c4767bce3aa860f6582885db6f7ca",
    "code_sha256": "cf122fff1b46fedd1a3a542ba5282eb78b2ee6f5c9309a7ee53349904dc555a5",
}
AMENDMENTS = [
    "A1: families_v2.capped_subset treated the two members of a minimal pair as separate "
    "units because they always have different coarse scenario keys (the pivot is part of the "
    "key); the first v2.0 run's robustness_subset_le3.json therefore held 17 split pairs "
    "(719 records). The pair is now atomic: it enters only if both members' coarse scenarios "
    "have room under the cap of 3. Only src/adnn/dataset/families_v2.py changed (new "
    "code_sha256); labels, records, configuration, gates and split rules are unchanged, and "
    "the regenerated records must be byte-identical to the first run",
]
FIRST_RUN = {
    "records_jsonl_sha256": "d03cd8f38ad4b36ce540409e7b3062e0eb4b457d6916483a3334ebde0acdab73",
    "split_json_sha256": "110d1b6ae9b704987f95df328a10b6473c6a71993488674fcf6e4f3865c94d3e",
}
CODE_ROOT = Path("src/adnn")
PROTECTED = {
    # inputs protected by the v1.0 freeze
    "data/pilot/pilot_v0.1.jsonl": "f66b98baac43faf1ece408cc22e645faf22aace13ad6aac86f1f2c83f1d3fc53",  # noqa: E501
    "data/scaling_pilot/records.jsonl": "bfd1175fb7e12c0f0993adb3f7079d29388dcf250d35f1ac37693af0236baa5b",  # noqa: E501
    "docs/preregistration/phase5b_manifest.json": "887e42ba79b34f1c7eacadb4c777fce9869b31b0ef32aadfe7a86363edffb72f",  # noqa: E501
    "docs/preregistration/phase5d_share_link_spec.md": "5da475c50cf6f472014e3d2e4a5d53d9120f765915751126f4a3c9d09858e137",  # noqa: E501
    "docs/preregistration/phase5e_pilot_manifest.json": "e3fe50101c05bb96337e1644a6920fb98ba20a1a6f9e0ed46e996bb91a8f9fdd",  # noqa: E501
    "docs/preregistration/production_manifest.json": "39ccc1e3a067fe9cc4f53df947c74b109cb51b994131c8c726af888e00f8c720",  # noqa: E501
    "docs/preregistration/production_manifest.sha256": "c9fc98f8a44dafd2c8d324c0643c5430021838e495b18550d8938a4065dbfbec",  # noqa: E501
    # v1.0 itself: its frozen manifest and its dataset files stay byte-identical
    "docs/preregistration/production_manifest_amend1.json": "729bcd7ca17d74406f25345874623b4c422cea9c5731ed95f194d77f0bf1620d",  # noqa: E501
    "docs/preregistration/production_manifest_amend1.sha256": "a2f02373dc7371a6ac72d72660ec3f9d0cad79b7fef1d47f1c2785da37a94054",  # noqa: E501
    "data/production/v1.0/records.jsonl": "b5a7d58f342fbc2ef7c0658a0dd2a9ffc99c95f8153c8aa1d79bcb70620e20dd",  # noqa: E501
    "data/production/v1.0/split.json": "cd60ceb391e701a9e5603792baf4ad617f5594240fe6787d941de77460d90db2",  # noqa: E501
    "data/production/v1.0/tool_sets.json": "a45f798be15a7019dca356334f83fe1be5fa99741d7d8b813cda31e9e09eba33",  # noqa: E501
    "data/production/v1.0/sensitivity_oq21.jsonl": "8d6b8b86e672e3d5628a9bc0748f4ffa0d68c4cd6a271183343ee5d2bf372ce2",  # noqa: E501
    "data/production/v1.0/manifest.json": "f869791d1c104eca920caa18f620af9837725032890afdba9e25d8e127971667",  # noqa: E501
    "data/production/v1.0/generation_report.json": "6fe1be710d7b4c94f45f18094193f89951b940a1ee935cd37e9adf8d1edaaaba",  # noqa: E501
    # the original v2 freeze, kept as a historical record
    "docs/preregistration/production_manifest_v2.json": "ed7b24a1b04add4b1662be8703c35d7540f7e62b168f2b46766636a324fca585",  # noqa: E501
    "docs/preregistration/production_manifest_v2.sha256": "a4b263d858ae0e36000efc5410403121726ed57d0387e110a8c68f2f193fc3d3",  # noqa: E501
}


def code_sha256(root: Path = CODE_ROOT) -> str:
    """sha256 over (relative path, LF-normalised bytes) of every ``*.py`` under ``root``."""
    h = hashlib.sha256()
    for f in sorted(root.rglob("*.py")):
        h.update(f.relative_to(root).as_posix().encode() + b"\0")
        h.update(f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main() -> int:
    for path, sha in PROTECTED.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != sha:
            raise SystemExit(f"{path}: protected artifact changed")
    cfg = v2.config()
    head = _git("rev-parse", "HEAD").strip()
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "manifest": "adnn-production",
        "version": "2.0-amend1",
        "status": "FROZEN: prospective amendment, written before v2.0 was regenerated; "
        "supersedes the original v2 freeze for generation only",
        "amends": AMENDS,
        "amendments": AMENDMENTS,
        "expected_identical_to_first_run": FIRST_RUN,
        "frozen_at_utc": now,
        "base_commit": head,
        "code_sha256": code_sha256(),
        "code_committed_at_freeze": not _git("status", "--porcelain", "--", "src/adnn").strip(),
        "decision_record": "docs/decisions/0010-dataset-v2-families.md (incl. Amendment 1)",
        "builds_on": "docs/preregistration/production_manifest_amend1.json (v1.0, unchanged)",
        "dataset_version": v2.DATASET_VERSION,
        "families_version": v2.FAMILIES_VERSION,
        "families": list(v2.FAMILY_IDS),
        "changes_from_v1": [
            "ADR-0010: nine families built from existing sandbox tools and settings",
            "ADR-0010 Amendment 1: surface_variants 4 -> 6 per coarse scenario",
            "generator_version production-gen-2.0",
        ],
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
        "label_rules": "unchanged from v1.0: see production_manifest_amend1.json label_rules; "
        "the label is always the oracle's (declared design depths are informational only)",
        "grouping_version": prod.GROUPING_VERSION,
        "gates": {
            "min_pair_fraction": cfg.min_pair_fraction,
            "family_share_cap": cfg.family_share_cap,
            "d5_signature_cap": cfg.d5_signature_cap,
            "sd3_conflicting_coarse_groups": 0,
            "test_fraction_range": [0.18, 0.22],
            "compact_test_only": True,
            "validator_errors": 0,
        },
        "robustness_subset": {
            "file": "robustness_subset_le3.json",
            "rule": f"families_v2.capped_subset: <= {v2.ROBUSTNESS_CAP} records per coarse "
            "scenario; a minimal pair enters only if both members' coarse scenarios have room "
            "(atomic, never split); deterministic (units by size, then pair id / record id)",
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
        "outputs": "data/production/v2.0/ (git-ignored); checksums in manifest.json and "
        "generation_report.json",
    }
    text = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    with open(SIDECAR, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{sha}  {OUT.name}\nfrozen_at_utc {now}\nbase_commit {head}\n")
    print(sha, head, manifest["code_sha256"], now)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
