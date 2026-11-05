"""Human agreement study, 100 minimal pairs from frozen v2.0 (REQ-LBL-05).

    .venv/Scripts/python.exe scripts/annotation/human_100.py prepare     # blank sheets + manifest
    .venv/Scripts/python.exe scripts/annotation/human_100.py zip         # CSV annotator ZIP
    .venv/Scripts/python.exe scripts/annotation/human_100.py excel       # annotator workbooks
    .venv/Scripts/python.exe scripts/annotation/human_100.py zip-excel   # workbook ZIP
    .venv/Scripts/python.exe scripts/annotation/human_100.py agreement   # after both return
        [--a1 X.xlsx --a2 Y.xlsx] [--accept-uncertain-no]

``prepare`` and ``excel`` refuse to overwrite. ``excel`` builds the workbooks from the
frozen blank CSV sheets (same rows, ids and A/B order). ``agreement`` reads the returned
sheets from ``data/annotation/human_100_pairs/completed/``: ``ADNN_Annotator_{1,2}.xlsx``, or
``annotator_{1,2}.csv`` if no workbook is there (override with ``--a1`` and ``--a2``; ``.xlsx``
or ``.csv``). If either sheet fails validation it writes the errors and computes no statistic.
``--accept-uncertain-no`` is an explicit opt-in that reads an ``uncertain`` cell of exactly
``no`` as "not uncertain" (labels are never touched); the strict validation result is still
run and recorded in ``summary.json``. Before any statistic, the frozen sampling manifest is
re-checked against frozen v2.0 (sample reproducible from the seed, A/B members form strict
minimal pairs, shown text unchanged). Results go to ``results/human_annotation/``.
Disagreements are listed and grouped, never resolved.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adnn.dataset.annotation import (
    COLUMNS,
    GOLD_LETTER,
    LETTERS,
    N_PAIRS,
    SEED,
    UNSURE,
    bootstrap_ci,
    check_sheet,
    cohen_kappa,
    confusion,
    content_hash,
    raw_agreement,
    sample_pairs,
    sheet_rows,
    split_pattern,
    write_sheet,
)
from adnn.dataset.annotation_xlsx import read_any, write_workbook
from adnn.dataset.api import LoadedDataset, load_dataset
from adnn.dataset.schema import sha256_file

ROOT = Path(__file__).resolve().parents[2]
V2 = Path("data/production/v2.0")
V2_RECORDS_SHA256 = "d03cd8f38ad4b36ce540409e7b3062e0eb4b457d6916483a3334ebde0acdab73"
DIR = Path("data/annotation/human_100_pairs")
OUT = Path("results/human_annotation")
ZIP = Path("ADNN_Human_Annotation_100_Pairs.zip")
ZIP_FILES = ("annotator_1.csv", "annotator_2.csv", "ANNOTATION_INSTRUCTIONS.md", "README.md")
N_BOOT = 1000
XLSX_DIR = DIR / "excel"
XLSX_NAMES = {1: "ADNN_Annotator_1.xlsx", 2: "ADNN_Annotator_2.xlsx"}
XLSX_ZIP = Path("ADNN_Human_Annotation_100_Pairs_Excel.zip")
CODE = (
    "src/adnn/dataset/annotation.py",
    "src/adnn/dataset/annotation_xlsx.py",
    "scripts/annotation/human_100.py",
    "scripts/annotation/workbook_intro.py",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _code_sha() -> str:
    h = hashlib.sha256()
    for rel in CODE:
        h.update(rel.encode() + b"\0" + (ROOT / rel).read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def _v2() -> LoadedDataset:
    if sha256_file(V2 / "records.jsonl") != V2_RECORDS_SHA256:
        raise SystemExit("frozen v2.0 records.jsonl does not match its frozen hash")
    return load_dataset(V2)  # verifies the manifest checksums too


def mode_prepare() -> None:
    targets = [DIR / f for f in ("annotator_1.csv", "annotator_2.csv", "sampling_manifest.json")]
    if any(p.exists() for p in targets):
        raise SystemExit(f"{DIR} already prepared; refusing to overwrite")
    ds = _v2()
    pairs = ds.minimal_pairs()
    sample = sample_pairs(pairs, N_PAIRS, SEED)  # raises if fewer than 100 eligible pairs
    rows = sheet_rows(sample, ds.by_id, ds.tool_sets)
    for name in ("annotator_1.csv", "annotator_2.csv"):
        write_sheet(DIR / name, rows)
    eligible = sorted(a["pair_id"] for a, _ in pairs)
    manifest = {
        "study": "REQ-LBL-05 human agreement, 100 minimal pairs",
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": {
            "version": ds.manifest["dataset_version"],
            "dir": str(V2.as_posix()),
            "records_sha256": V2_RECORDS_SHA256,
        },
        "eligible": {
            "definition": "strict minimal pairs of frozen v2.0 (LoadedDataset.minimal_pairs: "
            "same action text, one pivot condition differs, gold labels differ)",
            "n_pairs": len(eligible),
            "pair_ids_sha256": hashlib.sha256("\n".join(eligible).encode()).hexdigest(),
        },
        "sampling": {
            "seed": SEED,
            "n_pairs": N_PAIRS,
            "n_examples": 2 * N_PAIRS,
            "method": "uniform without replacement: random.Random(seed).sample(sorted(pair_ids), "
            "100); the sample order is the presentation order; then one rng.random() < 0.5 per "
            "sampled pair (same rng, in order) swaps the id-sorted members into A/B. No quota, "
            "no manual selection",
        },
        "pairs": sample,
        "row_content_sha256": {r["annotation_id"]: content_hash(r) for r in rows},
        "sheet_columns": list(COLUMNS),
        "valid_labels": [*LETTERS, UNSURE],
        "blank_sheet_sha256": {n: _sha(DIR / n) for n in ("annotator_1.csv", "annotator_2.csv")},
        "instructions_sha256": _sha(DIR / "ANNOTATION_INSTRUCTIONS.md"),
        "code_sha256": _code_sha(),
        "note": "no labels are stored here; gold labels are read from frozen v2.0 only when "
        "agreement is computed. Not for annotators.",
    }
    (DIR / "sampling_manifest.json").write_text(
        json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"prepared": str(DIR), "pairs": len(sample), "examples": len(rows),
                      "eligible_pairs": len(eligible)}))  # fmt: skip


def mode_zip() -> None:
    missing = [f for f in ZIP_FILES if not (DIR / f).exists()]
    if missing:
        raise SystemExit(f"missing {missing}")
    manifest = json.loads((DIR / "sampling_manifest.json").read_text(encoding="utf-8"))
    for n, h in manifest["blank_sheet_sha256"].items():
        if _sha(DIR / n) != h:
            raise SystemExit(f"{n} is no longer the blank sheet recorded in the manifest")
    folder = "ADNN_Human_Annotation_100_Pairs"
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in ZIP_FILES:
            z.write(DIR / f, f"{folder}/{f}")
    print(json.dumps({"zip": str(ZIP.resolve()), "bytes": ZIP.stat().st_size,
                      "sha256": _sha(ZIP)}))  # fmt: skip


def _blank_rows() -> list[dict[str, str]]:
    """The frozen blank sheet rows, checked against the sampling manifest."""
    manifest = json.loads((DIR / "sampling_manifest.json").read_text(encoding="utf-8"))
    for n, h in manifest["blank_sheet_sha256"].items():
        if _sha(DIR / n) != h:
            raise SystemExit(f"{n} is no longer the blank sheet recorded in the manifest")
    _, rows = read_any(DIR / "annotator_1.csv")
    if [r["annotation_id"] for r in rows] != list(manifest["row_content_sha256"]):
        raise SystemExit("blank sheet row order differs from the manifest")
    if any(content_hash(r) != manifest["row_content_sha256"][r["annotation_id"]] for r in rows):
        raise SystemExit("blank sheet content differs from the manifest")
    return rows


def mode_excel() -> None:
    from openpyxl import __version__ as openpyxl_version

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from workbook_intro import INTRO

    paths = [XLSX_DIR / name for name in XLSX_NAMES.values()]
    if any(p.exists() for p in paths):
        raise SystemExit(f"{XLSX_DIR} already has workbooks; refusing to overwrite")
    rows = _blank_rows()
    for k, name in XLSX_NAMES.items():
        write_workbook(XLSX_DIR / name, rows, k, INTRO)
    (XLSX_DIR / "excel_manifest.json").write_text(
        json.dumps(
            {
                "built_from": {n: _sha(DIR / n) for n in ("annotator_1.csv", "annotator_2.csv")},
                "sampling_manifest_sha256": _sha(DIR / "sampling_manifest.json"),
                "rows": len(rows),
                "workbook_sha256": {n: _sha(XLSX_DIR / n) for n in XLSX_NAMES.values()},
                "openpyxl": openpyxl_version,
                "code_sha256": _code_sha(),
                "note": "same rows, ids, text and A/B order as the blank CSV sheets; no labels",
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"workbooks": [str(p) for p in paths], "rows": len(rows)}))


def mode_zip_excel() -> None:
    files = [*XLSX_NAMES.values(), "README.md"]
    missing = [f for f in files if not (XLSX_DIR / f).exists()]
    if missing:
        raise SystemExit(f"missing {missing}")
    built = json.loads((XLSX_DIR / "excel_manifest.json").read_text(encoding="utf-8"))
    for n, h in built["workbook_sha256"].items():
        if _sha(XLSX_DIR / n) != h:
            raise SystemExit(f"{n} differs from the blank workbook that was built")
    folder = "ADNN_Human_Annotation_100_Pairs_Excel"
    with zipfile.ZipFile(XLSX_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files:
            z.write(XLSX_DIR / f, f"{folder}/{f}")
    print(json.dumps({"zip": str(XLSX_ZIP.resolve()), "bytes": XLSX_ZIP.stat().st_size,
                      "sha256": _sha(XLSX_ZIP)}))  # fmt: skip


def _pairs_of(
    ids: list[str], x: dict[str, str], y: dict[str, str]
) -> list[tuple[str, list[tuple[str, str]]]]:
    by_pair: dict[str, list[tuple[str, str]]] = {}
    for aid in ids:
        by_pair.setdefault(aid.split("-")[0], []).append((x[aid], y[aid]))
    return list(by_pair.items())


def _num(v: float) -> float | None:
    return None if math.isnan(v) else round(v, 4)


def _compare(
    name_x: str, x: dict[str, str], name_y: str, y: dict[str, str], ids: list[str]
) -> dict[str, Any]:
    use = [i for i in ids if x[i] in LETTERS and y[i] in LETTERS]
    if not use:
        return {"n_examples": 0, "note": "no example labelled R/P/I by both"}
    xs, ys = [x[i] for i in use], [y[i] for i in use]
    lo, hi = bootstrap_ci(_pairs_of(use, x, y), cohen_kappa, N_BOOT, SEED)
    rlo, rhi = bootstrap_ci(_pairs_of(use, x, y), raw_agreement, N_BOOT, SEED)
    return {
        "rows": name_x,
        "cols": name_y,
        "n_examples": len(use),
        "n_pairs": len({i.split("-")[0] for i in use}),
        "cohen_kappa": _num(cohen_kappa(xs, ys)),
        "kappa_95ci_pair_bootstrap": [_num(lo), _num(hi)],
        "raw_agreement": round(raw_agreement(xs, ys), 4),
        "raw_agreement_95ci_pair_bootstrap": [_num(rlo), _num(rhi)],
        "confusion": confusion(xs, ys),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _manifest_errors(ds: LoadedDataset, manifest: dict[str, Any]) -> list[str]:
    """The frozen sampling manifest, re-derived from frozen v2.0 (nothing is rewritten)."""
    errs = []
    pairs = ds.minimal_pairs()
    eligible = sorted(a["pair_id"] for a, _ in pairs)
    eligible_sha = hashlib.sha256("\n".join(eligible).encode()).hexdigest()
    if eligible_sha != manifest["eligible"]["pair_ids_sha256"]:
        errs.append("manifest: eligible minimal-pair set differs from frozen v2.0")
    if (
        sample_pairs(pairs, manifest["sampling"]["n_pairs"], manifest["sampling"]["seed"])
        != (manifest["pairs"])
    ):
        errs.append("manifest: pairs/A-B order are not reproducible from the recorded seed")
    if len({p["pair"] for p in manifest["pairs"]}) != N_PAIRS:
        errs.append("manifest: pair codes are not 100 distinct codes")
    for p in manifest["pairs"]:
        ra, rb = ds.by_id(p["A"]), ds.by_id(p["B"])
        if not (ra["pair_id"] == rb["pair_id"] == p["pair_id"] and ra["label"] != rb["label"]
                and ra["action_text"] == rb["action_text"]):  # fmt: skip
            errs.append(f"manifest: {p['pair']} is not a strict minimal pair of v2.0")
    rows = sheet_rows(manifest["pairs"], ds.by_id, ds.tool_sets)
    if [r["annotation_id"] for r in rows] != list(manifest["row_content_sha256"]):
        errs.append("manifest: annotation id order differs from the pairs")
    want = manifest["row_content_sha256"]
    bad = [r["annotation_id"] for r in rows if content_hash(r) != want.get(r["annotation_id"])]
    if bad:
        errs.append(f"manifest: shown text differs from v2.0 for {bad[:10]}")
    for n, h in manifest["blank_sheet_sha256"].items():
        if _sha(DIR / n) != h:
            errs.append(f"manifest: {n} is no longer the recorded blank sheet")
    return errs


def mode_agreement(a1: Path, a2: Path, accept_uncertain_no: bool = False) -> int:
    manifest = json.loads((DIR / "sampling_manifest.json").read_text(encoding="utf-8"))
    expected = manifest["row_content_sha256"]
    OUT.mkdir(parents=True, exist_ok=True)
    answers, errors, strict_errors, unc_no = {}, [], [], {}
    for k, key, path in ((1, "annotator_1", a1), (2, "annotator_2", a2)):
        if not path.exists():
            errors.append(f"{key}: file not found: {path}")
            continue
        try:
            header, rows = read_any(path, annotator=k)
        except ValueError as exc:
            errors.append(f"{key}: {exc}")
            continue
        strict_errors += check_sheet(header, rows, expected, key)[1]
        answers[key], errs = check_sheet(header, rows, expected, key, accept_uncertain_no)
        errors += errs
        unc_no[key] = sum((r["uncertain"] or "").strip().lower() == "no" for r in rows)
    if not errors and a1.resolve() == a2.resolve():
        errors.append("annotator_1 and annotator_2 are the same file")
    if not errors:
        ds = _v2()
        errors += _manifest_errors(ds, manifest)
    if errors:
        (OUT / "validation_errors.json").write_text(
            json.dumps({"ok": False, "errors": errors}, indent=1) + "\n", encoding="utf-8"
        )
        print("VALIDATION FAILED; no agreement statistic computed:\n- " + "\n- ".join(errors))
        return 1
    stale = OUT / "validation_errors.json"
    if stale.exists():
        stale.unlink()
    rid = {f"{p['pair']}-{ex}": p[ex] for p in manifest["pairs"] for ex in ("A", "B")}
    ids = sorted(rid)
    gold = {i: GOLD_LETTER[ds.by_id(rid[i])["label"]] for i in ids}
    h1 = {i: answers["annotator_1"][i]["label"] for i in ids}
    h2 = {i: answers["annotator_2"][i]["label"] for i in ids}
    sure = [i for i in ids if not (answers["annotator_1"][i]["uncertain"]
                                   or answers["annotator_2"][i]["uncertain"])]  # fmt: skip
    warnings = []
    if h1 == h2 and all(answers["annotator_1"][i]["notes"] == answers["annotator_2"][i]["notes"]
                        for i in ids):  # fmt: skip
        warnings.append("the two sheets have identical labels and notes; check independence")
    summary = {
        "study": manifest["study"],
        "computed_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {"annotator_1": {"path": str(a1), "sha256": _sha(a1)},
                   "annotator_2": {"path": str(a2), "sha256": _sha(a2)},
                   "sampling_manifest_sha256": _sha(DIR / "sampling_manifest.json"),
                   "gold": {"dataset": manifest["dataset"]["version"],
                            "records_sha256": V2_RECORDS_SHA256, "label": "label (h=3)"}},
        "validation": {
            "strict_ok": not strict_errors, "strict_errors": strict_errors,
            "accept_uncertain_no": accept_uncertain_no,
            "uncertain_cells_equal_no": unc_no,
            "manifest_consistency": "ok: sample re-derived from seed, 100 strict minimal "
            "pairs, shown text and blank sheets unchanged",
            "note": "accept_uncertain_no only reads 'no' in the uncertain column as not "
            "uncertain; no label was changed" if accept_uncertain_no else "strict"},
        "seed": SEED, "bootstrap": {"resamples": N_BOOT, "unit": "pair", "ci": "95% percentile"},
        "n_pairs": len(manifest["pairs"]), "n_examples": len(ids),
        "label_counts": {"annotator_1": dict(Counter(h1.values())),
                         "annotator_2": dict(Counter(h2.values())),
                         "automatic": dict(Counter(gold.values()))},
        "uncertain_flagged": {k: sum(answers[k][i]["uncertain"] for i in ids) for k in answers},
        "primary": {
            "note": "examples labelled U (cannot decide) are excluded pairwise and counted",
            "human_vs_human": _compare("annotator_1", h1, "annotator_2", h2, ids),
            "annotator_1_vs_automatic": _compare("annotator_1", h1, "automatic", gold, ids),
            "annotator_2_vs_automatic": _compare("annotator_2", h2, "automatic", gold, ids),
        },
        "secondary_excluding_uncertain": {
            "note": "also excludes examples either annotator flagged uncertain",
            "human_vs_human": _compare("annotator_1", h1, "annotator_2", h2, sure),
            "annotator_1_vs_automatic": _compare("annotator_1", h1, "automatic", gold, sure),
            "annotator_2_vs_automatic": _compare("annotator_2", h2, "automatic", gold, sure),
        },
        "disagreements": {"human_vs_human": sum(h1[i] != h2[i] for i in ids),
                          "status": "unresolved (listed in human_disagreements.csv; "
                          "detail in human_disagreements_detailed.csv, groups in "
                          "disagreement_groups.json)"},
        "warnings": warnings,
        "code_sha256": _code_sha(),
    }  # fmt: skip
    a, b = answers["annotator_1"], answers["annotator_2"]
    _write_csv(
        OUT / "human_disagreements.csv",
        [{"annotation_id": i, "annotator_1": h1[i], "annotator_1_uncertain": a[i]["uncertain"],
          "annotator_2": h2[i], "annotator_2_uncertain": b[i]["uncertain"],
          "annotator_1_notes": a[i]["notes"], "annotator_2_notes": b[i]["notes"],
          "status": "unresolved"} for i in ids if h1[i] != h2[i]],
        ["annotation_id", "annotator_1", "annotator_1_uncertain", "annotator_2",
         "annotator_2_uncertain", "annotator_1_notes", "annotator_2_notes", "status"],
    )  # fmt: skip
    _write_csv(
        OUT / "human_vs_automatic.csv",
        [{"annotation_id": i, "record_id": rid[i], "automatic": gold[i], "annotator_1": h1[i],
          "annotator_2": h2[i]} for i in ids if h1[i] != gold[i] or h2[i] != gold[i]],
        ["annotation_id", "record_id", "automatic", "annotator_1", "annotator_2"],
    )  # fmt: skip
    _write_disagreement_detail(ds, rid, ids, a, b, gold)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    p = summary["primary"]
    for k in ("human_vs_human", "annotator_1_vs_automatic", "annotator_2_vs_automatic"):
        r = p[k]
        print(f"{k}: kappa={r.get('cohen_kappa')} CI={r.get('kappa_95ci_pair_bootstrap')} "
              f"raw={r.get('raw_agreement')} n={r['n_examples']}")  # fmt: skip
    print(f"written: {OUT}/summary.json, human_disagreements.csv, human_vs_automatic.csv, "
          "human_disagreements_detailed.csv, disagreement_groups.json")  # fmt: skip
    if strict_errors:
        print("STRICT VALIDATION (recorded in summary.json):\n- " + "\n- ".join(strict_errors))
    for w in warnings:
        print("WARNING:", w)
    return 0


DETAIL_FIELDS = [
    "annotation_id", "pair", "example", "pattern", "annotator_1", "annotator_1_uncertain",
    "annotator_2", "annotator_2_uncertain", "automatic", "matches_automatic", "action",
    "state", "task", "available_tools", "annotator_1_notes", "annotator_2_notes",
    "diag_action_verb", "diag_pivot_factor", "diag_pivot_value", "diag_family",
    "diag_restore_depth", "diag_approx_restore_depth", "diag_render_style", "status",
]  # fmt: skip
PATTERNS = ("R/P", "P/I", "R/I")


def _write_disagreement_detail(
    ds: LoadedDataset,
    rid: dict[str, str],
    ids: list[str],
    a: dict[str, dict[str, Any]],
    b: dict[str, dict[str, Any]],
    gold: dict[str, str],
) -> None:
    """Every human-human disagreement with the shown text, both labels and the automatic
    label, under the anonymous annotation id (no record id); grouped by label split.
    ``diag_*`` columns are post-hoc diagnostics from the frozen record, never shown."""
    rows = []
    for i in ids:
        x, y = a[i]["label"], b[i]["label"]
        if x == y:
            continue
        r = ds.by_id(rid[i])
        g = gold[i]
        rows.append({
            "annotation_id": i, "pair": i.split("-")[0], "example": i.split("-")[1],
            "pattern": split_pattern(x, y), "annotator_1": x,
            "annotator_1_uncertain": a[i]["uncertain"], "annotator_2": y,
            "annotator_2_uncertain": b[i]["uncertain"], "automatic": g,
            "matches_automatic": "annotator_1" if x == g else "annotator_2" if y == g
            else "neither",
            "action": r["action_text"], "state": r["state_text"], "task": r["task_text"],
            "available_tools": ", ".join(t["name"] for t in ds.tool_sets[r["tool_set_id"]]),
            "annotator_1_notes": a[i]["notes"], "annotator_2_notes": b[i]["notes"],
            "diag_action_verb": r["action_verb"], "diag_pivot_factor": r["pivot"]["factor"],
            "diag_pivot_value": r["pivot"]["value"], "diag_family": r["template_id"],
            "diag_restore_depth": r["restore_depth"],
            "diag_approx_restore_depth": r["approx_restore_depth"],
            "diag_render_style": r["render_style"], "status": "unresolved",
        })  # fmt: skip
    order = {p: k for k, p in enumerate(PATTERNS)}
    rows.sort(key=lambda d: (order.get(d["pattern"], len(PATTERNS)), d["annotation_id"]))
    _write_csv(OUT / "human_disagreements_detailed.csv", rows, DETAIL_FIELDS)

    def counts(sub: list[dict[str, Any]], key: str) -> dict[str, int]:
        if key == "pivot":
            return dict(
                Counter(
                    f"{d['diag_pivot_factor']}={d['diag_pivot_value']}" for d in sub
                ).most_common()
            )
        return dict(Counter(str(d[key]) for d in sub).most_common())

    groups: dict[str, Any] = {}
    for pat in PATTERNS:
        sub = [d for d in rows if d["pattern"] == pat]
        groups[pat] = {
            "n": len(sub),
            "annotator_1_to_annotator_2": dict(
                Counter(f"{d['annotator_1']}->{d['annotator_2']}" for d in sub).most_common()
            ),
            "automatic_label": counts(sub, "automatic"),
            "matches_automatic": counts(sub, "matches_automatic"),
            "action_verb": counts(sub, "diag_action_verb"),
            "pivot": counts(sub, "pivot"),
            "family": counts(sub, "diag_family"),
            "annotation_ids": [d["annotation_id"] for d in sub],
        }
    pairs_hit = sorted({d["pair"] for d in rows})
    both = [p for p in pairs_hit if sum(d["pair"] == p for d in rows) == 2]
    doc = {
        "n_disagreements": len(rows),
        "groups": groups,
        "involving_U": [d["annotation_id"] for d in rows if d["pattern"] not in groups],
        "pairs_with_any_disagreement": len(pairs_hit),
        "pairs_with_both_members_disagreeing": len(both),
        "of_those_pairs_annotator_gave_both_members_same_label": {
            k: sum(ans[f"{p}-A"]["label"] == ans[f"{p}-B"]["label"] for p in both)
            for k, ans in (("annotator_1", a), ("annotator_2", b))
        },
        "status": "unresolved; no adjudication performed",
    }
    (OUT / "disagreement_groups.json").write_text(
        json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("prepare", "zip", "excel", "zip-excel", "agreement"))
    ap.add_argument("--a1", type=Path, default=None, help=".xlsx or .csv")
    ap.add_argument("--a2", type=Path, default=None, help=".xlsx or .csv")
    ap.add_argument("--accept-uncertain-no", action="store_true",
                    help="read an 'uncertain' cell of exactly 'no' as not uncertain")  # fmt: skip
    args = ap.parse_args()
    for k in (1, 2):
        if getattr(args, f"a{k}") is None:
            xlsx = DIR / "completed" / XLSX_NAMES[k]
            csv_ = DIR / "completed" / f"annotator_{k}.csv"
            setattr(args, f"a{k}", xlsx if xlsx.exists() else csv_)
    if args.mode == "prepare":
        mode_prepare()
        return 0
    if args.mode == "zip":
        mode_zip()
        return 0
    if args.mode == "excel":
        mode_excel()
        return 0
    if args.mode == "zip-excel":
        mode_zip_excel()
        return 0
    return mode_agreement(args.a1, args.a2, args.accept_uncertain_no)


if __name__ == "__main__":
    sys.exit(main())
