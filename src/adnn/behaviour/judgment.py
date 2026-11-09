"""Frozen stated-answer parsing and classification scoring."""
import string

LABELS = ("reversible", "partially_reversible", "irreversible")


def parse_judgment(raw):
    lines = raw.strip().splitlines()
    if not lines:
        return "UNPARSEABLE"
    label = lines[0].strip().strip(string.punctuation + " ").lower()
    return label if label in LABELS else "UNPARSEABLE"


def classification_metrics(rows):
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
    from sklearn.metrics import precision_recall_fscore_support

    truth = [r["label"] for r in rows]
    predicted = [r["prediction"] for r in rows]
    if not rows:
        raise ValueError("No predictions to score")
    p, r, f, n = precision_recall_fscore_support(
        truth, predicted, labels=list(LABELS), zero_division=0,
    )
    return {"n": len(rows), "accuracy": accuracy_score(truth, predicted),
            "balanced_accuracy": balanced_accuracy_score(truth, predicted),
            "macro_f1": float(f.mean()),
            "unparseable": predicted.count("UNPARSEABLE"),
            "confusion_labels": [*LABELS, "UNPARSEABLE"],
            "confusion_matrix": confusion_matrix(
                truth, predicted, labels=[*LABELS, "UNPARSEABLE"],
            ).tolist(),
            "per_class": {label: {"precision": float(p[i]), "recall": float(r[i]),
                                  "f1": float(f[i]), "support": int(n[i])}
                          for i, label in enumerate(LABELS)}}
