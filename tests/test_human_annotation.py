"""REQ-LBL-05 human agreement study: sampling, blinding, sheet validation, statistics."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
from pathlib import Path

import pytest

from adnn.dataset.annotation import (
    COLUMNS,
    SEED,
    InsufficientPairsError,
    bootstrap_ci,
    check_sheet,
    cohen_kappa,
    confusion,
    content_hash,
    raw_agreement,
    read_sheet,
    sample_pairs,
    sheet_rows,
    split_pattern,
    write_sheet,
)

PREPARED = Path("data/annotation/human_100_pairs")
V2 = Path("data/production/v2.0")
SECRET = "GOLD-SECRET-TOKEN"


def _record(pid: str, member: str, label: str) -> dict:
    return {
        "id": f"{pid}-{member}-{label}", "pair_id": pid, "label": label,
        "task_text": f"task {pid}", "state_text": f"state {pid} {member}",
        "action_text": f'{{"tool": "delete_file", "args": {{"path": "/{pid}"}}}}',
        "tool_set_id": "ts", "label_rationale": SECRET, "restore_depth": 1,
        "labels_by_horizon": {"3": label}, "pivot": {"value": SECRET},
        "meta": {"oracle": SECRET},
    }  # fmt: skip


def _pairs(n: int) -> list[tuple[dict, dict]]:
    return [(_record(f"p{i:04d}", "a", "irreversible"), _record(f"p{i:04d}", "b", "reversible"))
            for i in range(n)]  # fmt: skip


TOOLS = {"ts": [{"name": "delete_file"}, {"name": "restore_file"}]}


# -- sampling ------------------------------------------------------------------------------
def test_sampling_is_reproducible_and_seed_dependent() -> None:
    pairs = _pairs(439)
    a, b = sample_pairs(pairs), sample_pairs(list(reversed(pairs)))  # input order irrelevant
    assert a == b
    assert sample_pairs(pairs, seed=SEED + 1) != a


def test_sample_is_unique_without_replacement() -> None:
    s = sample_pairs(_pairs(439))
    assert len(s) == 100 and len({x["pair_id"] for x in s}) == 100
    assert [x["pair"] for x in s] == [f"H{i:03d}" for i in range(1, 101)]
    for x in s:  # A and B are the two members of the same pair
        assert (
            x["A"] != x["B"] and x["A"].startswith(x["pair_id"]) and x["B"].startswith(x["pair_id"])
        )


def test_ab_order_is_randomised() -> None:
    s = sample_pairs(_pairs(439))
    first_irr = sum("-a-" in x["A"] for x in s)  # id order would always put member a first
    assert 30 < first_irr < 70


def test_fewer_than_100_pairs_stops() -> None:
    with pytest.raises(InsufficientPairsError):
        sample_pairs(_pairs(99))


# -- blinding ------------------------------------------------------------------------------
def test_sheet_excludes_gold_and_record_ids() -> None:
    s = sample_pairs(_pairs(150))
    by_id = {r["id"]: r for p in _pairs(150) for r in p}
    rows = sheet_rows(s, by_id.__getitem__, TOOLS)
    assert len(rows) == 200
    text = json.dumps(rows)
    assert SECRET not in text
    assert not any(w in text for w in ("irreversible", "reversible"))  # label values
    assert not any(rid in text for rid in by_id)  # record ids encode the pivot
    for r in rows:
        assert tuple(r) == COLUMNS and r["label"] == r["uncertain"] == r["notes"] == ""


@pytest.mark.skipif(not (PREPARED / "sampling_manifest.json").exists(), reason="not prepared")
def test_prepared_sheets_match_frozen_v2_and_hide_labels() -> None:
    from adnn.dataset.api import load_dataset

    ds = load_dataset(V2)
    manifest = json.loads((PREPARED / "sampling_manifest.json").read_text(encoding="utf-8"))
    assert manifest["pairs"] == sample_pairs(ds.minimal_pairs())  # reproducible from v2.0
    assert manifest["eligible"]["n_pairs"] == 439 and manifest["sampling"]["seed"] == 20261105
    for name in ("annotator_1.csv", "annotator_2.csv"):
        header, rows = read_sheet(PREPARED / name)
        raw = (PREPARED / name).read_text(encoding="utf-8-sig")
        assert header == list(COLUMNS) and len(rows) == 200
        assert all(not (r["label"] or r["uncertain"] or r["notes"]) for r in rows)
        assert not any(p[k] in raw for p in manifest["pairs"] for k in ("pair_id", "A", "B"))
        for word in ("irreversible", "partially_reversible", "label_rationale"):
            assert word not in raw
    text = (PREPARED / "sampling_manifest.json").read_text(encoding="utf-8")
    assert "partially_reversible" not in text and "irreversible" not in text


# -- sheet validation ----------------------------------------------------------------------
def _sheet(tmp_path: Path, labels: list[str], **edit: str) -> tuple[Path, dict[str, str]]:
    s = sample_pairs(_pairs(150))
    by_id = {r["id"]: r for p in _pairs(150) for r in p}
    rows = sheet_rows(s, by_id.__getitem__, TOOLS)
    expected = {r["annotation_id"]: content_hash(r) for r in rows}
    for r, lab in zip(rows, labels, strict=False):
        r["label"] = lab
    for k, v in edit.items():
        rows[0][k] = v
    path = tmp_path / "sheet.csv"
    write_sheet(path, rows)
    return path, expected


def test_check_sheet_accepts_complete_sheet(tmp_path: Path) -> None:
    path, expected = _sheet(tmp_path, ["r", " P ", "I", "U"] * 50, uncertain="Yes")
    answers, errors = check_sheet(*read_sheet(path), expected, "a1")
    assert errors == [] and len(answers) == 200
    assert answers["H001-A"] == {"label": "R", "uncertain": True, "notes": ""}


def test_check_sheet_reports_missing_invalid_and_changed(tmp_path: Path) -> None:
    path, expected = _sheet(tmp_path, ["R"] * 198 + ["", "X"], state="edited")
    _, errors = check_sheet(*read_sheet(path), expected, "a1")
    joined = " | ".join(errors)
    assert "1 missing labels" in joined and "1 invalid labels" in joined
    assert "text changed" in joined


def test_check_sheet_reports_duplicate_and_unknown_ids(tmp_path: Path) -> None:
    path, expected = _sheet(tmp_path, ["R"] * 200)
    header, rows = read_sheet(path)
    rows[1]["annotation_id"] = rows[0]["annotation_id"]
    rows[2]["annotation_id"] = "H999-A"
    _, errors = check_sheet(header, rows, expected, "a1")
    joined = " | ".join(errors)
    assert "duplicate" in joined and "unknown" in joined and "missing" in joined


def test_uncertain_no_is_rejected_unless_opted_in(tmp_path: Path) -> None:
    path, expected = _sheet(tmp_path, ["R", "P"] * 100)
    header, rows = read_sheet(path)
    for r in rows:
        r["uncertain"] = "no"
    rows[0]["uncertain"] = "maybe"
    strict = " | ".join(check_sheet(header, rows, expected, "a2")[1])
    assert "200 invalid 'uncertain' values" in strict
    answers, errors = check_sheet(header, rows, expected, "a2", accept_uncertain_no=True)
    assert len(errors) == 1 and "1 invalid 'uncertain' values" in errors[0]  # 'maybe' stays bad
    assert answers["H001-B"] == {"label": "P", "uncertain": False, "notes": ""}
    assert [a["label"] for a in answers.values()] == ["R", "P"] * 100  # labels untouched


def test_split_pattern() -> None:
    assert split_pattern("P", "R") == split_pattern("R", "P") == "R/P"
    assert split_pattern("I", "P") == "P/I" and split_pattern("I", "R") == "R/I"
    assert split_pattern("U", "R") == "with U"


def test_line_ending_changes_are_not_edits(tmp_path: Path) -> None:
    path, expected = _sheet(tmp_path, ["R"] * 200)
    header, rows = read_sheet(path)
    rows[0]["state"] = rows[0]["state"].replace("\n", "\r\n") + "\r\n"
    assert check_sheet(header, rows, expected, "a1")[1] == []


# -- statistics ----------------------------------------------------------------------------
def test_cohen_kappa_hand_computed() -> None:
    x, y = ["R", "R", "P", "I"], ["R", "P", "P", "I"]
    # po = 3/4; pe = (2*1 + 1*2 + 1*1) / 16 = 5/16; kappa = (12/16 - 5/16) / (11/16) = 7/11
    assert cohen_kappa(x, y) == pytest.approx(7 / 11)
    assert raw_agreement(x, y) == 0.75
    assert cohen_kappa(["R", "P", "I"], ["R", "P", "I"]) == 1.0
    assert math.isnan(cohen_kappa(["R", "R"], ["R", "R"]))  # degenerate marginals
    assert confusion(x, y)["R"] == {"R": 1, "P": 1, "I": 0}


def test_kappa_matches_sklearn_definition() -> None:
    x = list("RRPPIIRPIRPI")
    y = list("RPPIIIRRIRPP")
    po = sum(a == b for a, b in zip(x, y, strict=True)) / 12
    pe = sum(x.count(c) * y.count(c) for c in "RPI") / 144
    assert cohen_kappa(x, y) == pytest.approx((po - pe) / (1 - pe))


def test_bootstrap_ci_is_deterministic_and_brackets_estimate() -> None:
    items = [(f"H{i:03d}", [("R", "R"), ("I", "I" if i % 5 else "P")]) for i in range(100)]
    lo, hi = bootstrap_ci(items, cohen_kappa)
    assert (lo, hi) == bootstrap_ci(items, cohen_kappa)
    xs = [a for _, ps in items for a, _ in ps]
    ys = [b for _, ps in items for _, b in ps]
    assert -1 <= lo <= cohen_kappa(xs, ys) <= hi <= 1


# -- end to end (synthetic test sheets in a temporary directory) ----------------------------
def _script():
    spec = importlib.util.spec_from_file_location("human_100", "scripts/annotation/human_100.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not (PREPARED / "sampling_manifest.json").exists(), reason="not prepared")
def test_agreement_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _script()
    monkeypatch.setattr(mod, "OUT", tmp_path / "out")
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

    a1 = save("a1.csv", ["R", "P", "I", "U"] * 50)  # synthetic test labels only
    a2 = save("a2.csv", ["R", "P", "P", "I"] * 50)
    assert mod.mode_agreement(a1, a2) == 0
    s = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    hh = s["primary"]["human_vs_human"]
    assert hh["n_examples"] == 150 and s["label_counts"]["annotator_1"]["U"] == 50
    assert hh["cohen_kappa"] == pytest.approx(
        cohen_kappa(["R", "P", "I"] * 50, ["R", "P", "P"] * 50), abs=1e-4
    )
    with open(tmp_path / "out" / "human_disagreements.csv", encoding="utf-8") as fh:
        dis = list(csv.DictReader(fh))
    assert len(dis) == 100 and {d["status"] for d in dis} == {"unresolved"}
    assert s["disagreements"]["human_vs_human"] == 100
    assert s["validation"]["strict_ok"] and s["validation"]["manifest_consistency"].startswith("ok")
    lo, hi = hh["raw_agreement_95ci_pair_bootstrap"]
    assert lo <= hh["raw_agreement"] <= hi
    with open(tmp_path / "out" / "human_disagreements_detailed.csv", encoding="utf-8") as fh:
        det = list(csv.DictReader(fh))
    assert sorted(d["annotation_id"] for d in det) == sorted(d["annotation_id"] for d in dis)
    assert all("record_id" not in d and d["action"] and d["state"] for d in det)
    assert {d["automatic"] for d in det} <= {"R", "P", "I"}
    groups = json.loads((tmp_path / "out" / "disagreement_groups.json").read_text("utf-8"))
    # a1 = R P I U, a2 = R P P I: example 3 is I/P (50x), example 4 involves U (50x)
    assert groups["groups"]["P/I"]["n"] == 50 and len(groups["involving_U"]) == 50
    assert groups["groups"]["R/P"]["n"] == groups["groups"]["R/I"]["n"] == 0

    bad = save("bad.csv", ["R"] * 199 + [""])  # one missing label: no statistics
    (tmp_path / "out" / "summary.json").unlink()
    assert mod.mode_agreement(a1, bad) == 1
    assert not (tmp_path / "out" / "summary.json").exists()
    assert (tmp_path / "out" / "validation_errors.json").exists()
