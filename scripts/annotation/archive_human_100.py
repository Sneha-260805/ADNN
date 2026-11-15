"""Archive the git-ignored inputs and outputs of the REQ-LBL-05 human agreement study.

    .venv/Scripts/python.exe scripts/annotation/archive_human_100.py \
        --a1 ADNN_Annotator_1.xlsx --a2 ADNN_Annotator_2_filled.xlsx

Writes ``ADNN_REQ-LBL-05_Human_Agreement_Archive.zip`` (refuses to overwrite). Inside the ZIP,
files sit at their repository paths, so extracting the ZIP into a checkout of the recorded
commit and running the command in ``ARCHIVE_MANIFEST.json`` reproduces the analysis.

Privacy: a returned workbook's document properties (``docProps/core.xml``: ``creator`` and
``lastModifiedBy``) can carry a personal name. Those two fields are set to ``ADNN project``
in the archived copy. No cell is touched, so validation and every statistic are unaffected.
The original and archived SHA-256 are both recorded. The original files are only read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ZIP = Path("ADNN_REQ-LBL-05_Human_Agreement_Archive.zip")
STUDY = Path("data/annotation/human_100_pairs")
COMPLETED = STUDY / "completed"
FIXED_TIME = (2026, 11, 5, 0, 0, 0)
INPUTS = [
    *(STUDY / f for f in ("ANNOTATION_INSTRUCTIONS.md", "README.md", "annotator_1.csv",
                          "annotator_2.csv", "sampling_manifest.json")),
    *(STUDY / "excel" / f for f in ("ADNN_Annotator_1.xlsx", "ADNN_Annotator_2.xlsx",
                                    "README.md", "excel_manifest.json")),
    *(Path("data/production/v2.0") / f for f in (
        "manifest.json", "records.jsonl", "tool_sets.json", "split.json",
        "robustness_subset_le3.json", "sensitivity_oq21.jsonl", "generation_report.json")),
]  # fmt: skip
RESULTS = Path("results/human_annotation")
RESULT_FILES = (
    "summary.json",
    "human_disagreements.csv",
    "human_disagreements_detailed.csv",
    "disagreement_groups.json",
    "human_vs_automatic.csv",
)
NEUTRAL = "ADNN project"
_PROPS = re.compile(rb"(<(?:dc:creator|cp:lastModifiedBy)\b[^>]*>)([^<]*)(</)")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def redact_workbook(data: bytes) -> tuple[bytes, list[str]]:
    """Copy of an .xlsx with neutral ``creator``/``lastModifiedBy``; every other entry is
    copied byte for byte. Returns the new bytes and the names of the fields changed."""
    import io

    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    changed: list[str] = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            body = src.read(info.filename)
            if info.filename == "docProps/core.xml":

                def sub(m: re.Match[bytes]) -> bytes:
                    if m.group(2) != NEUTRAL.encode():
                        changed.append(m.group(1).decode().split()[0].strip("<>"))
                    return m.group(1) + NEUTRAL.encode() + m.group(3)

                body = _PROPS.sub(sub, body)
            dst.writestr(info, body)
    return (out.getvalue(), changed) if changed else (data, [])


def _commit() -> dict[str, object]:
    def git(*a: str) -> str:
        return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout

    return {"commit": git("rev-parse", "HEAD").strip(),
            "dirty_tracked_files": [ln[3:] for ln in git("status", "--porcelain").splitlines()
                                    if not ln.startswith("??")]}  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a1", type=Path, required=True)
    ap.add_argument("--a2", type=Path, required=True)
    args = ap.parse_args()
    if ZIP.exists():
        raise SystemExit(f"{ZIP} exists; refusing to overwrite")
    entries: dict[str, bytes] = {}
    files: list[dict[str, object]] = []
    for p in INPUTS:
        entries[p.as_posix()] = p.read_bytes()
        files.append({"path": p.as_posix(), "role": "input (unchanged)"})
    for k, p in ((1, args.a1), (2, args.a2)):
        raw = p.read_bytes()
        data, changed = redact_workbook(raw)
        arc = (COMPLETED / p.name).as_posix()
        entries[arc] = data
        files.append({
            "path": arc, "role": f"returned workbook, annotator {k}",
            "original_name": p.name, "original_sha256": sha(raw),
            "metadata_redacted": changed,
            "note": "document properties set to 'ADNN project'; cells unchanged" if changed
            else "byte-identical to the returned file",
        })  # fmt: skip
    for f in RESULT_FILES:
        p = RESULTS / f
        entries[p.as_posix()] = p.read_bytes()
        files.append({"path": p.as_posix(), "role": "official result (computed from the "
                      "original workbooks)"})  # fmt: skip
    for f in files:
        f["sha256"] = sha(entries[str(f["path"])])
        f["bytes"] = len(entries[str(f["path"])])
    a1, a2 = (COMPLETED / args.a1.name).as_posix(), (COMPLETED / args.a2.name).as_posix()
    manifest = {
        "archive": ZIP.name,
        "study": "REQ-LBL-05 human agreement, 100 minimal pairs of adnn-dataset-2.0",
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code": _commit(),
        "reproduce": [
            "git checkout <code.commit>; unzip this archive into the checkout root",
            f".venv/Scripts/python.exe scripts/annotation/human_100.py agreement --a1 {a1} "
            f"--a2 {a2} --accept-uncertain-no",
            "expected: the four CSV/JSON result files other than summary.json are "
            "byte-identical; summary.json differs only in computed_utc and in the input "
            "path/sha256 of any metadata-redacted workbook",
        ],
        "validation": "strict validation fails for annotator 2 (all 200 'uncertain' cells are "
        "'no'); --accept-uncertain-no (approved by Member 1, 2026-11-05) reads only that value "
        "as not uncertain. summary.json keeps strict_ok=false",
        "adjudication": "none; all disagreements unresolved",
        "privacy": "no annotator names; workbook document properties neutralised where needed",
        "files": files,
    }
    readme = (
        "# ADNN REQ-LBL-05 human agreement archive\n\n"
        "Inputs and results of the independent two-annotator agreement study (docs/43 in the "
        "repository). Files are at their repository paths. `ARCHIVE_MANIFEST.json` lists every "
        "file with SHA-256, the code commit and the reproduction command. No adjudication was "
        "performed and no dataset label was changed.\n"
    )
    entries["ARCHIVE_MANIFEST.json"] = (json.dumps(manifest, indent=1) + "\n").encode()
    entries["ARCHIVE_README.md"] = readme.encode()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in ["ARCHIVE_README.md", "ARCHIVE_MANIFEST.json", *sorted(set(entries) - {
                "ARCHIVE_README.md", "ARCHIVE_MANIFEST.json"})]:  # fmt: skip
            z.writestr(zipfile.ZipInfo(name, FIXED_TIME), entries[name], zipfile.ZIP_DEFLATED)
    print(json.dumps({"zip": str(ZIP.resolve()), "files": len(entries),
                      "bytes": ZIP.stat().st_size, "sha256": sha(ZIP.read_bytes()),
                      "commit": manifest["code"]}))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
