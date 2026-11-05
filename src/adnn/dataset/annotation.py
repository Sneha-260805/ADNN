"""Human agreement study on 100 minimal pairs (REQ-LBL-05; docs/05 §10).

* :func:`sample_pairs`: draws 100 strict minimal pairs from frozen v2.0 uniformly at random,
  without replacement, with a fixed seed. It also fixes a random A/B order per pair, because
  ordering members by record id would put the irreversible member first in 231 of 439 pairs.
* :func:`sheet_rows`: the blank annotation sheet. It holds only model-visible text (task,
  state, action) and the names of the available tools, under opaque ids. It never contains
  labels, record ids, pivots, rationales or depths.
* :func:`read_sheet` and :func:`check_sheet`: strict validation of a returned sheet.
* :func:`cohen_kappa`, :func:`confusion`, :func:`bootstrap_ci`: agreement statistics.

No human label is ever created here. Every human label comes from a returned CSV.
"""

from __future__ import annotations

import csv
import hashlib
import io
import random
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

SEED = 20261105
N_PAIRS = 100
LETTERS = ("R", "P", "I")
UNSURE = "U"  # "cannot decide"; allowed, counted, excluded from kappa
VALID = (*LETTERS, UNSURE)
GOLD_LETTER = {"reversible": "R", "partially_reversible": "P", "irreversible": "I"}
COLUMNS = (
    "annotation_id",
    "pair",
    "example",
    "task",
    "state",
    "action",
    "available_tools",
    "label",
    "uncertain",
    "notes",
)
CONTENT_COLUMNS = ("task", "state", "action", "available_tools")
ANSWER_COLUMNS = ("label", "uncertain", "notes")
UNCERTAIN_VALUES = ("", "yes")


class InsufficientPairsError(ValueError):
    """Fewer eligible minimal pairs than requested."""


def sample_pairs(
    pairs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    n: int = N_PAIRS,
    seed: int = SEED,
) -> list[dict[str, Any]]:
    """``n`` pairs drawn uniformly without replacement; each gets an opaque id and A/B order.

    Procedure (reproducible): sort the eligible pairs by ``pair_id``; ``rng.sample`` ``n`` of
    them with ``rng = random.Random(seed)`` (the sample order is the presentation order);
    then one ``rng.random() < 0.5`` per sampled pair, in that order, decides whether the
    id-sorted members are swapped.
    """
    by_id = {}
    for a, b in pairs:
        if a["pair_id"] != b["pair_id"] or a["id"] == b["id"]:
            raise ValueError(f"malformed pair {a['id']} / {b['id']}")
        by_id[a["pair_id"]] = tuple(sorted((a, b), key=lambda r: r["id"]))
    if len(by_id) < n:
        raise InsufficientPairsError(f"{len(by_id)} eligible minimal pairs < {n}")
    rng = random.Random(seed)
    chosen = rng.sample(sorted(by_id), n)
    out = []
    for i, pid in enumerate(chosen, 1):
        first, second = by_id[pid]
        swap = rng.random() < 0.5
        a, b = (second, first) if swap else (first, second)
        out.append({"pair": f"H{i:03d}", "pair_id": pid, "A": a["id"], "B": b["id"]})
    return out


def _tools(record: Mapping[str, Any], tool_sets: Mapping[str, Any]) -> str:
    return ", ".join(t["name"] for t in tool_sets[record["tool_set_id"]])


def sheet_rows(
    sample: Sequence[Mapping[str, Any]],
    record_of: Callable[[str], Mapping[str, Any]],
    tool_sets: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Blank sheet rows (two per pair). Only model-visible text; answer columns empty."""
    rows = []
    for s in sample:
        for ex in ("A", "B"):
            r = record_of(s[ex])
            rows.append(
                {
                    "annotation_id": f"{s['pair']}-{ex}",
                    "pair": s["pair"],
                    "example": ex,
                    "task": r["task_text"],
                    "state": r["state_text"],
                    "action": r["action_text"],
                    "available_tools": _tools(r, tool_sets),
                    "label": "",
                    "uncertain": "",
                    "notes": "",
                }
            )
    return rows


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def content_hash(row: Mapping[str, str]) -> str:
    """Hash of a row's shown content, robust to spreadsheet line-ending changes."""
    payload = "\x1f".join(_norm(row[c]) for c in ("annotation_id", *CONTENT_COLUMNS))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_sheet(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    """UTF-8 with BOM so that Excel opens it correctly; Google Sheets ignores the BOM."""
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue().encode("utf-8-sig"))


def read_sheet(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(r) for r in reader]


def check_sheet(
    header: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    expected_hashes: Mapping[str, str],
    name: str,
    accept_uncertain_no: bool = False,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Validate one returned sheet. Returns ``({annotation_id: answer}, errors)``.

    Errors: wrong header, unknown, missing or duplicate ids, changed task/state/action text
    or pair/example columns,
    missing or invalid labels, invalid ``uncertain`` values. Labels and ``uncertain`` are
    compared case-insensitively after trimming; nothing else is normalised or guessed.
    ``accept_uncertain_no`` (off by default, explicit opt-in) additionally reads an
    ``uncertain`` value of exactly ``no`` as "not uncertain". It never touches labels.
    """
    allowed_unc = (*UNCERTAIN_VALUES, "no") if accept_uncertain_no else UNCERTAIN_VALUES
    errors: list[str] = []
    missing_cols = [c for c in COLUMNS if c not in header]
    if missing_cols:
        return {}, [f"{name}: missing columns {missing_cols}"]
    ids = [r["annotation_id"].strip() for r in rows]
    dup = sorted(k for k, v in Counter(ids).items() if v > 1)
    if dup:
        errors.append(f"{name}: duplicate annotation ids {dup}")
    unknown = sorted(set(ids) - set(expected_hashes))
    if unknown:
        errors.append(f"{name}: unknown annotation ids {unknown}")
    absent = sorted(set(expected_hashes) - set(ids))
    if absent:
        errors.append(f"{name}: {len(absent)} annotation ids missing, e.g. {absent[:5]}")
    answers: dict[str, dict[str, Any]] = {}
    no_label, bad_label, bad_unc, changed, moved = [], [], [], [], []
    for r in rows:
        aid = r["annotation_id"].strip()
        if aid not in expected_hashes:
            continue
        if content_hash({**r, "annotation_id": aid}) != expected_hashes[aid]:
            changed.append(aid)
        if [r["pair"].strip(), r["example"].strip()] != aid.split("-"):
            moved.append(aid)
        label = (r["label"] or "").strip().upper()
        unc = (r["uncertain"] or "").strip().lower()
        if not label:
            no_label.append(aid)
        elif label not in VALID:
            bad_label.append(f"{aid}={r['label']!r}")
        if unc not in allowed_unc:
            bad_unc.append(f"{aid}={r['uncertain']!r}")
        answers[aid] = {"label": label, "uncertain": unc == "yes", "notes": r["notes"] or ""}
    for what, items in (
        ("missing labels", no_label),
        ("invalid labels (use R, P, I or U)", bad_label),
        ("invalid 'uncertain' values (leave empty or write yes)", bad_unc),
        ("task/state/action text changed", changed),
        ("pair or example column changed", moved),
    ):
        if items:
            errors.append(f"{name}: {len(items)} {what}: {sorted(items)[:10]}")
    return answers, errors


def cohen_kappa(x: Sequence[str], y: Sequence[str], categories: Sequence[str] = LETTERS) -> float:
    """Unweighted Cohen's kappa. ``nan`` if expected agreement is 1 (degenerate marginals)."""
    if len(x) != len(y) or not x:
        raise ValueError("kappa needs two equal-length, non-empty label lists")
    n = len(x)
    po = sum(a == b for a, b in zip(x, y, strict=True)) / n
    cx, cy = Counter(x), Counter(y)
    pe = sum(cx[c] * cy[c] for c in categories) / (n * n)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def split_pattern(x: str, y: str) -> str:
    """Unordered label split of a disagreement, e.g. ``R/P`` for (P, R); ``with U`` if U."""
    if UNSURE in (x, y):
        return "with U"
    return "/".join(sorted({x, y}, key=LETTERS.index))


def raw_agreement(x: Sequence[str], y: Sequence[str]) -> float:
    return sum(a == b for a, b in zip(x, y, strict=True)) / len(x)


def confusion(
    rows_from: Sequence[str], cols_from: Sequence[str], categories: Sequence[str] = LETTERS
) -> dict[str, dict[str, int]]:
    """``m[row_label][col_label]`` counts."""
    m = {a: dict.fromkeys(categories, 0) for a in categories}
    for a, b in zip(rows_from, cols_from, strict=True):
        m[a][b] += 1
    return m


def bootstrap_ci(
    items: Sequence[tuple[str, Sequence[tuple[str, str]]]],
    stat: Callable[[Sequence[str], Sequence[str]], float],
    n_boot: int = 1000,
    seed: int = SEED,
) -> tuple[float, float]:
    """95% percentile CI, resampling *pairs* (clusters) with replacement.

    ``items`` = ``[(pair, [(label_x, label_y), ...]), ...]``. Replicates where the statistic
    is undefined (nan) are dropped.
    """
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        draw = [items[rng.randrange(len(items))] for _ in items]
        xy = [p for _, ps in draw for p in ps]
        if not xy:
            continue
        v = stat([a for a, _ in xy], [b for _, b in xy])
        if v == v:  # not nan
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    vals.sort()
    return vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))]
