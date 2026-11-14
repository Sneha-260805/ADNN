"""Excel workbooks for the human agreement study (REQ-LBL-05). Requires ``openpyxl``
(``pip install -e ".[annotation]"``).

The workbooks show exactly the rows of the blank CSV sheets (same ids, text and A/B order),
laid out for reading: one row per example, the A and B rows of a pair adjacent and banded,
a frozen header, dropdowns for the label (R, P, I, U) and for ``uncertain`` (yes), and
progress counters. Content cells are locked (sheet protection without a password). Only
label, uncertain and notes can be edited.

:func:`read_workbook` maps a returned workbook back to CSV-style rows, so the unchanged
:func:`adnn.dataset.annotation.check_sheet` validates both formats identically.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from adnn.dataset.annotation import COLUMNS, read_sheet

SHEET = "ANNOTATION"
INTRO = "START HERE"
HEADER_ROW = 3
FIRST_ROW = HEADER_ROW + 1
# (internal column, header shown, width). Decision columns sit right after the action so
# that they are visible on a laptop without scrolling; the tool list is last.
LAYOUT = (
    ("annotation_id", "ID", 9),
    ("pair", "Pair", 6.5),
    ("example", "Example", 8.5),
    ("task", "Task", 24),
    ("state", "State before the action", 46),
    ("action", "Action", 30),
    ("label", "Label", 8),
    ("uncertain", "Uncertain", 10.5),
    ("notes", "Notes (optional)", 28),
    ("available_tools", "Available tools", 30),
)
INPUTS = ("label", "uncertain", "notes")


def title(annotator: int) -> str:
    return f"ADNN reversibility annotation · Annotator {annotator}"


def _lines(text: str, chars: int) -> int:
    return sum(max(1, -(-len(part) // chars)) for part in str(text).split("\n"))


def _row_height(row: Mapping[str, str]) -> float:
    n = max(_lines(row[key], max(int(width * 1.15) - 1, 4)) for key, _, width in LAYOUT)
    return min(409.0, 13.5 * n + 5)


def write_workbook(
    path: Path,
    rows: Sequence[Mapping[str, str]],
    annotator: int,
    intro: Sequence[tuple[str, ...]],
) -> None:
    """Write one annotator workbook. ``intro`` lines for START HERE are ``("h", heading)``,
    ``("p", paragraph)``, ``("note", paragraph)`` or ``("kv", term, explanation)``."""
    from openpyxl import Workbook
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    n = len(rows)
    last = FIRST_ROW + n - 1
    col = {key: get_column_letter(i) for i, (key, _, _) in enumerate(LAYOUT, 1)}
    lab, unc = col["label"], col["uncertain"]
    lab_rng = f"{lab}{FIRST_ROW}:{lab}{last}"
    unc_rng = f"{unc}{FIRST_ROW}:{unc}{last}"
    ink, muted, accent, green = "1F2937", "6B7280", "1F4E79", "2E7D32"
    thin = Side(style="thin", color="D9DEE5")
    rule = Side(style="medium", color="8EA3BC")
    top_wrap = Alignment(wrap_text=True, vertical="top")

    wb = Workbook()
    wb.properties.creator = "ADNN project"
    wb.properties.lastModifiedBy = "ADNN project"
    wb.properties.title = title(annotator)
    wb.properties.created = wb.properties.modified = datetime(2026, 11, 5)

    # START HERE --------------------------------------------------------------------------
    st = wb.active
    st.title = INTRO
    st.sheet_view.showGridLines = False
    st.sheet_properties.tabColor = accent
    for letter, width in (("A", 3), ("B", 18), ("C", 98)):
        st.column_dimensions[letter].width = width
    st.cell(2, 2, title(annotator)).font = Font(size=16, bold=True, color=accent)
    progress = st.cell(3, 2, f'="Your progress: "&{SHEET}!{lab}1')
    progress.font = Font(size=11, bold=True, color=green)
    r = 5
    for item in intro:
        kind = item[0]
        if kind == "h":
            r += 1
            st.cell(r, 2, item[1]).font = Font(size=12, bold=True, color=accent)
            st.row_dimensions[r].height = 20
        elif kind == "kv":
            a, b = st.cell(r, 2, item[1]), st.cell(r, 3, item[2])
            a.font, b.font = Font(bold=True, color=ink), Font(color=ink)
            a.alignment = b.alignment = top_wrap
            st.row_dimensions[r].height = 15 * _lines(item[2], 100) + 3
        else:
            st.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
            c = st.cell(r, 2, item[1])
            c.font = Font(color=muted if kind == "note" else ink, italic=kind == "note")
            c.alignment = top_wrap
            st.row_dimensions[r].height = 15 * _lines(item[1], 118) + 3
        r += 1

    # ANNOTATION --------------------------------------------------------------------------
    ws = wb.create_sheet(SHEET)
    ws.sheet_properties.tabColor = green
    for i, (_, _, width) in enumerate(LAYOUT, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.merge_cells(f"A1:{col['action']}1")
    ws["A1"] = title(annotator)
    ws["A1"].font = Font(size=13, bold=True, color=accent)
    ws["A1"].alignment = Alignment(vertical="center")
    ws[f"{lab}1"] = f'=COUNTA({lab_rng})&" / {n} done"'
    ws[f"{unc}1"] = f"=COUNTA({lab_rng})/{n}"
    ws[f"{unc}1"].number_format = "0%"
    ws[f"{col['notes']}1"] = (
        f'="Uncertain: "&COUNTIF({unc_rng},"yes")&"   U: "&COUNTIF({lab_rng},"U")'
    )
    for key in INPUTS:
        c = ws[f"{col[key]}1"]
        c.font = Font(bold=True, color=green if key != "notes" else muted)
        c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 24
    ws.merge_cells(f"A2:{col['available_tools']}2")
    ws["A2"] = (
        "Choose R, P, I or U in the Label column for every row (dropdown). Uncertain and "
        "Notes are optional. Judge A and B separately, each from its own state. "
        "Definitions: START HERE."
    )
    ws["A2"].font = Font(italic=True, color=muted)
    ws.row_dimensions[2].height = 18
    for i, (_, text, _) in enumerate(LAYOUT, 1):
        c = ws.cell(HEADER_ROW, i, text)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=accent)
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[HEADER_ROW].height = 22
    bands = (PatternFill("solid", fgColor="FFFFFF"), PatternFill("solid", fgColor="F3F6FA"))
    input_fill = PatternFill("solid", fgColor="FFFBEA")
    for k, row in enumerate(rows):
        rr = FIRST_ROW + k
        last_of_pair = row["example"] == "B"
        for i, (key, _, _) in enumerate(LAYOUT, 1):
            c = ws.cell(rr, i, row[key] if row[key] != "" else None)
            c.border = Border(left=thin, right=thin, top=thin,
                              bottom=rule if last_of_pair else thin)  # fmt: skip
            if key in INPUTS:
                c.fill = input_fill
                c.protection = Protection(locked=False)
                if key == "notes":
                    c.alignment = top_wrap
                    c.font = Font(color=ink, size=10)
                else:
                    c.alignment = Alignment(horizontal="center", vertical="top")
                    c.font = Font(color=ink, size=11, bold=True)
            else:
                c.fill = bands[(k // 2) % 2]
                c.alignment = top_wrap
                c.font = Font(color=ink, size=10, bold=key in ("annotation_id", "example"))
        ws.row_dimensions[rr].height = _row_height(row)
    labels = DataValidation(
        type="list", formula1='"R,P,I,U"', allow_blank=True, showErrorMessage=True,
        errorStyle="stop", errorTitle="Label", error="Choose R, P, I or U from the list.",
        showInputMessage=True, promptTitle="Label",
        prompt="R reversible, P partially reversible, I irreversible, U cannot decide",
    )  # fmt: skip
    labels.add(lab_rng)
    unsure = DataValidation(
        type="list", formula1='"yes"', allow_blank=True, showErrorMessage=True,
        errorStyle="stop", errorTitle="Uncertain", error="Leave empty or choose yes.",
    )  # fmt: skip
    unsure.add(unc_rng)
    ws.add_data_validation(labels)
    ws.add_data_validation(unsure)
    ws.conditional_formatting.add(
        lab_rng,
        FormulaRule(formula=[f"LEN(TRIM({lab}{FIRST_ROW}))>0"],
                    fill=PatternFill("solid", fgColor="E3F2E1")),
    )  # fmt: skip
    ws.freeze_panes = f"D{FIRST_ROW}"
    ws.protection.sheet = True
    ws.protection.formatColumns = False  # resizing columns and rows stays allowed
    ws.protection.formatRows = False
    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"
    ws.page_setup.orientation = "landscape"
    wb.active = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def read_workbook(
    path: Path, annotator: int | None = None
) -> tuple[list[str], list[dict[str, str]]]:
    """A returned workbook as ``(CSV header, CSV-style rows)``.

    Raises ``ValueError`` if the ANNOTATION sheet, its header row or (when ``annotator`` is
    given) its annotator title is not as issued. Completely empty rows are skipped. Every
    other row is returned unchanged (cell values as text, empty cells as "") so that
    :func:`adnn.dataset.annotation.check_sheet` can accept or reject it.
    """
    from openpyxl import load_workbook

    wb = load_workbook(path)
    if SHEET not in wb.sheetnames:
        raise ValueError(f"{path.name}: no sheet named {SHEET!r}")
    ws = wb[SHEET]
    if annotator is not None and ws["A1"].value != title(annotator):
        raise ValueError(
            f"{path.name}: not the Annotator {annotator} workbook (title {ws['A1'].value!r})"
        )
    shown = [ws.cell(HEADER_ROW, i).value for i in range(1, len(LAYOUT) + 1)]
    if shown != [t for _, t, _ in LAYOUT]:
        raise ValueError(f"{path.name}: header row changed: {shown}")
    keys = [k for k, _, _ in LAYOUT]
    rows = []
    for values in ws.iter_rows(min_row=FIRST_ROW, max_col=len(keys), values_only=True):
        if all(v is None or str(v).strip() == "" for v in values):
            continue
        rows.append({k: "" if v is None else str(v) for k, v in zip(keys, values, strict=True)})
    return list(COLUMNS), rows


def read_any(path: Path, annotator: int | None = None) -> tuple[list[str], list[dict[str, str]]]:
    """A returned sheet, ``.xlsx`` workbook or ``.csv`` (kept for compatibility)."""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return read_workbook(path, annotator)
    if suffix == ".csv":
        return read_sheet(path)
    raise ValueError(f"{path.name}: expected a .xlsx or .csv file")
