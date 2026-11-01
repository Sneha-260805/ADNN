"""Dataset-composition validators for the final dataset design (docs/25 §5-§7).

These functions measure, and never repair. A dataset that fails a check is reported, and
no label or record is changed to pass.

* :func:`minimal_pairs`: a **genuine** minimal pair is a group with the same
  ``scenario_id``, byte-identical ``action_text``, and at least two distinct labels, where
  every member's label is *justified*. The default justification is
  ``label_provisional == False``. A caller can pass a stricter predicate, e.g. one that
  rejects search-relative ScienceWorld classifications. Groups that differ only in
  immediate effect, or that rest on a provisional label, are counted separately.
* :func:`template_signature` / :func:`duplicate_templates`: the same template with
  re-sampled surface values (names, paths, numbers) is not an independent example. The
  signature masks these surface values.
* :func:`split_leakage`: family-disjointness, exact and normalised overlap between
  train and test, and a lexical shortcut indicator (accuracy of the majority label per
  action verb, from train to test).
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from typing import Any

Record = Mapping[str, Any]

COMPOSITION_VERSION = "composition-checks-1"


def not_provisional(record: Record) -> bool:
    return not record.get("label_provisional", False)


def minimal_pairs(
    records: Iterable[Record], justified: Callable[[Record], bool] = not_provisional
) -> dict[str, Any]:
    recs = list(records)
    groups: dict[str, list[Record]] = defaultdict(list)
    for r in recs:
        if r.get("pair_id"):
            groups[str(r["pair_id"])].append(r)
    kinds: Counter[str] = Counter()
    genuine_members = 0
    for members in groups.values():
        same_scenario = len({m["scenario_id"] for m in members}) == 1
        same_action = len({m["action_text"].encode("utf-8") for m in members}) == 1
        labels = {m["label"] for m in members}
        if len(members) < 2 or not same_scenario or not same_action:
            kinds["malformed"] += 1
        elif len(labels) < 2:
            kinds["same_label"] += 1
        elif not all(justified(m) for m in members):
            kinds["label_difference_not_justified"] += 1
        else:
            kinds["genuine"] += 1
            genuine_members += len(members)
    n = len(recs)
    return {
        "n_records": n,
        "n_groups": len(groups),
        "group_kinds": dict(kinds),
        "genuine_member_fraction": round(genuine_members / n, 4) if n else None,
        "any_pair_member_fraction": round(sum(len(g) for g in groups.values()) / n, 4)
        if n
        else None,
    }


_MASKS = (
    (re.compile(r"/[\w./-]+"), "<PATH>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<EMAIL>"),
    (re.compile(r"\b\d+(?:\.\d+)?\b"), "<NUM>"),
    (re.compile(r'"[^"]*"'), '"<STR>"'),
)


def normalise(text: str) -> str:
    for rx, repl in _MASKS:
        text = rx.sub(repl, text)
    return re.sub(r"\s+", " ", text).strip().lower()


def template_signature(record: Record) -> str:
    """Hash of the surface-masked (state_text, action_text): equal = same template."""
    key = (
        normalise(str(record.get("state_text", "")))
        + "\x1f"
        + normalise(str(record.get("action_text", "")))
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def duplicate_templates(records: Iterable[Record]) -> dict[str, Any]:
    recs = list(records)
    sig_scen: dict[str, set[str]] = defaultdict(set)
    for r in recs:
        sig_scen[template_signature(r)].add(str(r["scenario_id"]))
    multi = {s: sorted(v) for s, v in sig_scen.items() if len(v) > 1}
    return {
        "n_records": len(recs),
        "n_signatures": len(sig_scen),
        "effective_fraction": round(len(sig_scen) / len(recs), 4) if recs else None,
        "signatures_shared_across_scenarios": len(multi),
        "examples": dict(list(multi.items())[:5]),
    }


def split_leakage(
    records: Iterable[Record], test_groups: Iterable[str], group_key: str = "template_id"
) -> dict[str, Any]:
    recs = list(records)
    test = set(test_groups)
    tr = [r for r in recs if r[group_key] not in test]
    te = [r for r in recs if r[group_key] in test]
    scen_overlap = {r["scenario_id"] for r in tr} & {r["scenario_id"] for r in te}
    exact = {(r["state_text"], r["action_text"]) for r in tr} & {
        (r["state_text"], r["action_text"]) for r in te
    }
    sig = {template_signature(r) for r in tr} & {template_signature(r) for r in te}
    by_verb: dict[str, Counter[str]] = defaultdict(Counter)
    for r in tr:
        by_verb[str(r.get("action_verb"))][r["label"]] += 1
    majority = {v: c.most_common(1)[0][0] for v, c in by_verb.items()}
    hits = [majority.get(str(r.get("action_verb"))) == r["label"] for r in te]
    test_major = Counter(r["label"] for r in te).most_common(1)
    return {
        "group_key": group_key,
        "n_train": len(tr),
        "n_test": len(te),
        "group_disjoint": not ({r[group_key] for r in tr} & {r[group_key] for r in te}),
        "scenario_overlap": len(scen_overlap),
        "exact_input_overlap": len(exact),
        "normalised_template_overlap": len(sig),
        "verb_majority_accuracy_on_test": round(sum(hits) / len(hits), 4) if hits else None,
        "test_majority_class_rate": round(test_major[0][1] / len(te), 4) if te else None,
    }


def class_balance(records: Iterable[Record], by: str = "environment") -> dict[str, Any]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for r in records:
        out[str(r.get(by))][r["label"]] += 1
        out["all"][r["label"]] += 1
    return {
        k: {lab: (n, round(n / sum(c.values()), 4)) for lab, n in sorted(c.items())}
        for k, c in out.items()
    }
