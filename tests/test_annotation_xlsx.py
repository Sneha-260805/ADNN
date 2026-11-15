"""REQ-LBL-05 annotator workbooks: faithful to the blank sheets, blinded, validated on return."""

from __future__ import annotations

import importlib.util
import json
import shutil
import zipfile
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from adnn.dataset.annotation import COLUMNS, check_sheet, read_sheet  # noqa: E402
from adnn.dataset.annotation_xlsx import (  # noqa: E402
    FIRST_ROW,
    SHEET,
    read_any,
    read_workbook,
)

PREPARED = Path("data/annotation/human_100_pairs")
XLSX = PREPARED / "excel"
NAMES = {1: "ADNN_Annotator_1.xlsx", 2: "ADNN_Annotator_2.xlsx"}
ZIP = Path("ADNN_Human_Annotation_100_Pairs_Excel.zip")
LAST = FIRST_ROW + 199

pytestmark = pytest.mark.skipif(
    not (XLSX / "excel_manifest.json").exists(), reason="workbooks not built"
)


def _manifest() -> dict:
    return json.loads((PREPARED / "sampling_manifest.json").read_text(encoding="utf-8"))


def _expected() -> dict[str, str]:
    return _manifest()["row_content_sha256"]


def _all_text(path: Path) -> str:
    """Every XML part of the workbook (cells, shared strings, properties)."""
    with zipfile.ZipFile(path) as z:
        return "\n".join(z.read(n).decode("utf-8", "replace") for n in z.namelist())


def _fill(src: Path, dst: Path, labels: list[str], edit=None) -> Path:
    shutil.copy(src, dst)
    wb = openpyxl.load_workbook(dst)
    ws = wb[SHEET]
    for i, lab in enumerate(labels):
        ws.cell(FIRST_ROW + i, 7, lab or None)
    if edit:
        edit(ws)
    wb.save(dst)
    return dst


# -- faithful to the blank CSV sheets ------------------------------------------------------
@pytest.mark.parametrize("k", [1, 2])
def test_workbook_rows_equal_blank_csv(k: int) -> None:
    _, csv_rows = read_sheet(PREPARED / "annotator_1.csv")
    header, rows = read_workbook(XLSX / NAMES[k], annotator=k)
    assert header == list(COLUMNS) and len(rows) == 200
    assert len({r["pair"] for r in rows}) == 100
    norm = [{c: r[c].replace("\r\n", "\n") for c in COLUMNS} for r in rows]
    assert norm == [{c: r[c].replace("\r\n", "\n") for c in COLUMNS} for r in csv_rows]
    assert [r["annotation_id"] for r in rows] == list(_expected())  # same A/B order
    assert all(r["label"] == r["uncertain"] == r["notes"] == "" for r in rows)
    _, errors = check_sheet(header, rows, _expected(), f"a{k}")
    assert any("missing labels" in e for e in errors) and len(errors) == 1  # only blanks


def test_built_from_unchanged_blank_sheets() -> None:
    built = json.loads((XLSX / "excel_manifest.json").read_text(encoding="utf-8"))
    assert built["built_from"] == _manifest()["blank_sheet_sha256"]
    for n, h in built["workbook_sha256"].items():
        import hashlib

        assert hashlib.sha256((XLSX / n).read_bytes()).hexdigest() == h


# -- blinding ------------------------------------------------------------------------------
@pytest.mark.parametrize("k", [1, 2])
def test_workbook_hides_gold_and_record_ids(k: int) -> None:
    text = _all_text(XLSX / NAMES[k])
    for p in _manifest()["pairs"]:
        for key in ("pair_id", "A", "B"):
            assert p[key] not in text
    for word in ("partially_reversible", "label_rationale", "labels_by_horizon", "oracle"):
        assert word not in text  # gold label values and hidden metadata
    with zipfile.ZipFile(XLSX / NAMES[k]) as z:
        props = z.read("docProps/core.xml").decode() + z.read("docProps/app.xml").decode()
    assert "reversible" not in props and "pair" not in props.lower()
    ws = openpyxl.load_workbook(XLSX / NAMES[k])[SHEET]
    cells = [str(ws.cell(r, c).value) for r in range(FIRST_ROW, LAST + 1) for c in range(1, 11)]
    assert not any("reversible" in v for v in cells)  # label words only in the definitions
    assert all(ws.cell(r, c).value is None for r in range(FIRST_ROW, LAST + 1) for c in (7, 8, 9))


# -- usability features --------------------------------------------------------------------
@pytest.mark.parametrize("k", [1, 2])
def test_dropdowns_progress_and_layout(k: int) -> None:
    wb = openpyxl.load_workbook(XLSX / NAMES[k])
    assert wb.sheetnames == ["START HERE", SHEET]
    ws = wb[SHEET]
    dv = {str(d.sqref): d for d in ws.data_validations.dataValidation}
    assert dv[f"G{FIRST_ROW}:G{LAST}"].formula1 == '"R,P,I,U"'
    assert dv[f"H{FIRST_ROW}:H{LAST}"].formula1 == '"yes"'
    assert all(d.showErrorMessage and d.errorStyle == "stop" for d in dv.values())
    assert ws["G1"].value == f'=COUNTA(G{FIRST_ROW}:G{LAST})&" / 200 done"'
    assert ws["H1"].value == f"=COUNTA(G{FIRST_ROW}:G{LAST})/200"
    assert "Your progress" in wb["START HERE"]["B3"].value
    assert ws.freeze_panes == f"D{FIRST_ROW}"
    assert ws.protection.sheet
    assert not ws.cell(FIRST_ROW, 7).protection.locked
    assert ws.cell(FIRST_ROW, 5).protection.locked
    assert ws.cell(FIRST_ROW, 5).alignment.wrap_text


def test_zip_has_only_workbooks_and_readme() -> None:
    with zipfile.ZipFile(ZIP) as z:
        names = sorted(n.split("/", 1)[1] for n in z.namelist())
    assert names == sorted([*NAMES.values(), "README.md"])


# -- returned workbooks --------------------------------------------------------------------
def test_filled_workbook_passes(tmp_path: Path) -> None:
    p = _fill(XLSX / NAMES[1], tmp_path / NAMES[1], [" r", "P", "I", "U"] * 50,
              lambda ws: setattr(ws.cell(FIRST_ROW, 8), "value", "yes"))  # fmt: skip
    answers, errors = check_sheet(*read_any(p, annotator=1), _expected(), "a1")
    assert errors == [] and len(answers) == 200
    assert answers["H001-A"] == {"label": "R", "uncertain": True, "notes": ""}


def _errors(path: Path, k: int = 1) -> list[str]:
    try:
        header, rows = read_any(path, annotator=k)
    except ValueError as exc:
        return [str(exc)]
    return check_sheet(header, rows, _expected(), "a")[1]


def test_rejects_changes(tmp_path: Path) -> None:
    src, full = XLSX / NAMES[1], ["R"] * 200

    def edited(ws) -> None:
        ws.cell(FIRST_ROW, 5).value = "something else"

    def dup(ws) -> None:
        for c in range(1, 11):
            ws.cell(FIRST_ROW + 1, c).value = ws.cell(FIRST_ROW, c).value

    def deleted(ws) -> None:
        ws.delete_rows(FIRST_ROW + 5)

    def header(ws) -> None:
        ws.cell(FIRST_ROW - 1, 5).value = "State"

    cases = {
        "text changed": _fill(src, tmp_path / "e.xlsx", full, edited),
        "invalid labels": _fill(src, tmp_path / "i.xlsx", ["X", *full[1:]]),
        "missing labels": _fill(src, tmp_path / "m.xlsx", ["", *full[1:]]),
        "duplicate": _fill(src, tmp_path / "d.xlsx", full, dup),
        "missing": _fill(src, tmp_path / "r.xlsx", full, deleted),
        "header row changed": _fill(src, tmp_path / "h.xlsx", full, header),
    }
    for needle, path in cases.items():
        errs = _errors(path)
        assert any(needle in e for e in errs), (needle, errs)
    # the Annotator 1 workbook returned as Annotator 2 is refused
    ok = _fill(src, tmp_path / "ok.xlsx", full)
    assert _errors(ok, 1) == []
    assert "not the Annotator 2 workbook" in _errors(ok, 2)[0]
    with pytest.raises(ValueError, match=r"\.xlsx or \.csv"):
        read_any(tmp_path / "x.ods")


# -- agreement from workbooks equals agreement from CSV ------------------------------------
def _script():
    spec = importlib.util.spec_from_file_location("human_100", "scripts/annotation/human_100.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_agreement_xlsx_equals_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import csv

    mod = _script()
    l1, l2 = ["R", "P", "I", "U"] * 50, ["R", "P", "P", "I"] * 50  # synthetic test labels
    x1 = _fill(XLSX / NAMES[1], tmp_path / NAMES[1], l1)
    x2 = _fill(XLSX / NAMES[2], tmp_path / NAMES[2], l2)
    header, rows = read_sheet(PREPARED / "annotator_1.csv")

    def save(name: str, labels: list[str]) -> Path:
        for r, lab in zip(rows, labels, strict=True):
            r["label"] = lab
        p = tmp_path / name
        with open(p, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=header)
            w.writeheader()
            w.writerows(rows)
        return p

    c1, c2 = save("a1.csv", l1), save("a2.csv", l2)
    outs = {}
    for kind, (a, b) in {"xlsx": (x1, x2), "csv": (c1, c2)}.items():
        monkeypatch.setattr(mod, "OUT", tmp_path / kind)
        assert mod.mode_agreement(a, b) == 0
        s = json.loads((tmp_path / kind / "summary.json").read_text(encoding="utf-8"))
        s.pop("inputs", None)
        s.pop("created_utc", None)
        outs[kind] = (
            s,
            (tmp_path / kind / "human_disagreements.csv").read_bytes(),
            (tmp_path / kind / "human_vs_automatic.csv").read_bytes(),
        )
    assert outs["xlsx"][1:] == outs["csv"][1:]
    sx, sc = outs["xlsx"][0], outs["csv"][0]
    assert sx["primary"] == sc["primary"] and sx["label_counts"] == sc["label_counts"]

    monkeypatch.setattr(mod, "OUT", tmp_path / "bad")
    assert mod.mode_agreement(x2, x1) == 1  # swapped workbooks are refused
    assert (tmp_path / "bad" / "validation_errors.json").exists()
    assert not (tmp_path / "bad" / "summary.json").exists()


# -- archive: workbook metadata redaction ----------------------------------------------------
def test_archive_redacts_names_but_not_cells(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "archive_human_100", "scripts/annotation/archive_human_100.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    p = _fill(XLSX / NAMES[1], tmp_path / NAMES[1], ["R", "P", "I", "U"] * 50)
    wb = openpyxl.load_workbook(p)
    wb.properties.lastModifiedBy = "Private Person"
    wb.properties.creator = "Private Person"
    wb.save(p)
    raw = p.read_bytes()
    data, changed = mod.redact_workbook(raw)
    assert sorted(changed) == ["cp:lastModifiedBy", "dc:creator"]
    out = tmp_path / "redacted.xlsx"
    out.write_bytes(data)
    assert "Private Person" not in _all_text(out) and "Private Person" in _all_text(p)
    assert read_any(out, annotator=1) == read_any(p, annotator=1)  # every cell unchanged
    assert mod.redact_workbook(data) == (data, [])  # already neutral: returned unchanged
