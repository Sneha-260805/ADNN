"""Shared ADNN RQ1 utilities for saved hidden-state arrays."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score
)

LABELS_3 = ["reversible", "partially_reversible", "irreversible"]
LABEL_TO_3 = {name: i for i, name in enumerate(LABELS_3)}

def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def load_split(path):
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    return np.asarray(obj["train_indices"], dtype=int), np.asarray(obj["test_indices"], dtype=int)

def labels_for(records, task):
    if task == "3class":
        return np.asarray([LABEL_TO_3[r["label"]] for r in records], dtype=int)
    if task == "binary":
        return np.asarray([int(r["label"] == "irreversible") for r in records], dtype=int)
    raise ValueError("task must be '3class' or 'binary'")

def make_probe(C, task, random_state=42):
    # Matches the notebook's StandardScaler + balanced L2 LogisticRegression pipeline.
    kwargs = dict(C=float(C), penalty="l2", class_weight="balanced",
                  solver="lbfgs", max_iter=1000, random_state=random_state)
    if task == "3class":
        kwargs["multi_class"] = "multinomial"
    return make_pipeline(StandardScaler(), LogisticRegression(**kwargs))

def score_model(model, X, y, task):
    pred = model.predict(X)
    result = {
        "n": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(y, pred, labels=[0,1,2] if task=="3class" else [0,1]).tolist(),
        "classification_report": classification_report(
            y, pred, labels=[0,1,2] if task=="3class" else [0,1],
            target_names=LABELS_3 if task=="3class" else ["non_irreversible","irreversible"],
            output_dict=True, zero_division=0
        )
    }
    if task == "binary":
        prob = model.predict_proba(X)[:, 1]
        result["auroc"] = float(roc_auc_score(y, prob)) if len(np.unique(y)) == 2 else None
    else:
        prob = model.predict_proba(X)
        result["macro_auroc_ovr"] = float(roc_auc_score(y, prob, multi_class="ovr", average="macro"))
    return pred, result
