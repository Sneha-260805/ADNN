"""Verify SHA-256 checksums of the frozen ADNN research artifacts (read-only).

Checks every file hash recorded in the frozen manifests against the bytes on disk:

* production dataset v2.0      (data/production/v2.0, git-ignored, bundle from Member 1)
* ScienceWorld transfer set    (data/transfer/sw-transfer-1.0, git-ignored)
* RQ3 paired task set          (data/tasks/rq3-tasks-1.0, tracked in git)
* human annotation study       (data/annotation/human_100_pairs, git-ignored)

It also cross-checks hashes that downstream manifests record about upstream artifacts
(for example the v2.0 records hash recorded in the RQ3 task manifest) and the
`dataset_manifest_sha256` recorded in Member 3's run configurations.

Nothing is written. Exit status is 0 only if every *present* artifact verifies;
artifacts whose directory is absent are reported as MISSING (exit status 2 if any
are missing and none failed, so CI can distinguish "not available" from "corrupt").

Usage: python scripts/validation/verify_frozen_artifacts.py [--root REPO_ROOT] [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(results: list[dict[str, Any]], artifact: str, path: Path, expected: str) -> None:
    if not path.exists():
        results.append({"artifact": artifact, "file": str(path), "status": "MISSING"})
        return
    actual = sha256_file(path)
    results.append(
        {
            "artifact": artifact,
            "file": str(path),
            "status": "OK" if actual == expected else "FAIL",
            "expected": expected,
            "actual": actual,
        }
    )


def manifest_files(results: list[dict[str, Any]], artifact: str, directory: Path) -> None:
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        results.append({"artifact": artifact, "file": str(manifest_path), "status": "MISSING"})
        return
    manifest = json.loads(manifest_path.read_text("utf-8"))
    entries = dict(manifest.get("files", {}))
    if isinstance(manifest.get("split"), dict) and "sha256" in manifest["split"]:
        entries["split"] = manifest["split"]
    for entry in entries.values():
        check(results, artifact, directory / entry["file"], entry["sha256"])


def run(root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    v2 = root / "data/production/v2.0"
    swt = root / "data/transfer/sw-transfer-1.0"
    tasks = root / "data/tasks/rq3-tasks-1.0"
    ann = root / "data/annotation/human_100_pairs"

    manifest_files(results, "production-v2.0", v2)
    manifest_files(results, "sw-transfer-1.0", swt)
    manifest_files(results, "rq3-tasks-1.0", tasks)

    # Frozen pre-registration manifest that the v2.0 manifest points at (tracked in git).
    if (v2 / "manifest.json").exists():
        frozen = json.loads((v2 / "manifest.json").read_text("utf-8")).get("frozen_manifest")
        if frozen:
            check(
                results,
                "production-v2.0 (frozen manifest)",
                root / frozen["path"],
                frozen["sha256"],
            )

    # Upstream hashes recorded by downstream artifacts.
    if (tasks / "manifest.json").exists():
        text = (tasks / "manifest.json").read_text("utf-8")
        recorded = "d03cd8f38ad4b36ce540409e7b3062e0eb4b457d6916483a3334ebde0acdab73"
        results.append(
            {
                "artifact": "rq3-tasks-1.0 -> production-v2.0 records hash",
                "file": str(tasks / "manifest.json"),
                "status": "OK" if recorded in text else "FAIL",
            }
        )
    if (swt / "manifest.json").exists():
        m = json.loads((swt / "manifest.json").read_text("utf-8"))
        if "records_sha256" in m and (swt / "records.jsonl").exists():
            # Canonical content hash (exporter: sha256_text(stable_json(records))),
            # not a file-byte hash.
            from adnn.dataset.schema import sha256_text, stable_json

            lines = (swt / "records.jsonl").read_text("utf-8").splitlines()
            records = [json.loads(line) for line in lines if line.strip()]
            actual = sha256_text(stable_json(records))
            results.append(
                {
                    "artifact": "sw-transfer-1.0 (canonical records_sha256)",
                    "file": str(swt / "records.jsonl"),
                    "status": "OK" if actual == m["records_sha256"] else "FAIL",
                    "expected": m["records_sha256"],
                    "actual": actual,
                }
            )

    # Human annotation study: frozen sampling manifest.
    sm_path = ann / "sampling_manifest.json"
    if sm_path.exists():
        sm = json.loads(sm_path.read_text("utf-8"))
        check(
            results,
            "human-annotation (instructions)",
            ann / "ANNOTATION_INSTRUCTIONS.md",
            sm["instructions_sha256"],
        )
        check(
            results,
            "human-annotation (dataset link)",
            root / sm["dataset"]["dir"] / "records.jsonl",
            sm["dataset"]["records_sha256"],
        )
    else:
        results.append({"artifact": "human-annotation", "file": str(sm_path), "status": "MISSING"})

    # Member 3 run configs record the sha256 of the task/dataset manifest they used.
    for cfg_path in sorted((root / "results").glob("**/config.json")):
        cfg = json.loads(cfg_path.read_text("utf-8"))
        recorded = cfg.get("dataset_manifest_sha256")
        if not recorded:
            continue
        candidates = {
            "data/tasks/rq3-tasks-1.0/manifest.json": tasks / "manifest.json",
            "data/production/v2.0/manifest.json": v2 / "manifest.json",
        }
        matched = [
            name for name, p in candidates.items() if p.exists() and sha256_file(p) == recorded
        ]
        # RQ3 runs record the task manifest, RQ2 runs the v2.0 manifest. If a candidate is
        # absent (e.g. the git-ignored v2.0 bundle in CI) a non-match is unverifiable.
        if matched:
            status = "OK"
        elif all(p.exists() for p in candidates.values()):
            status = "UNMATCHED"
        else:
            status = "MISSING"
        results.append(
            {
                "artifact": "run config dataset_manifest_sha256",
                "file": str(cfg_path.relative_to(root)),
                "status": status,
                "matched": matched,
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = ap.parse_args(argv)
    results = run(args.root.resolve())
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{r['status']:9} {r['artifact']:45} {r['file']}")
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("summary:", json.dumps(counts, sort_keys=True), file=sys.stderr)
    if counts.get("FAIL") or counts.get("UNMATCHED"):
        return 1
    return 2 if counts.get("MISSING") else 0


if __name__ == "__main__":
    raise SystemExit(main())
