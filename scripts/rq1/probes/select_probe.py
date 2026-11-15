"""GroupKFold-by-scenario layer/C selection using training indices only."""
import argparse, json
from pathlib import Path
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from scripts.rq1.common import read_jsonl, load_split, labels_for

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--hidden-states", required=True)
    ap.add_argument("--task", choices=["3class", "binary"], required=True)
    ap.add_argument("--layers", default="all", help="all or comma-separated indices, e.g. 14,16,18,20")
    ap.add_argument("--Cs", default="0.001,0.01,0.1,1,10")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    records = read_jsonl(args.records)
    Xall = np.load(args.hidden_states, mmap_mode="r")
    if len(records) != Xall.shape[0]:
        raise ValueError("Record/embedding row counts do not match")
    train_idx, _ = load_split(args.split)
    yall = labels_for(records, args.task)
    y = yall[train_idx]
    groups = np.asarray([records[i]["scenario_id"] for i in train_idx])
    layers = list(range(Xall.shape[1])) if args.layers == "all" else [int(x) for x in args.layers.split(",")]
    Cs = [float(x) for x in args.Cs.split(",")]
    if len(np.unique(groups)) < args.folds:
        raise ValueError("Not enough distinct training scenarios for requested GroupKFold")
    cv = GroupKFold(n_splits=args.folds)
    folds = list(cv.split(np.zeros(len(train_idx)), y, groups))
    results = []
    for layer in layers:
        if layer < 0 or layer >= Xall.shape[1]:
            raise ValueError(f"Invalid layer index: {layer}")
        X = np.asarray(Xall[train_idx, layer, :], dtype=np.float32)
        for C in Cs:
            fold_scores = []
            for tr, va in folds:
                scaler = StandardScaler()
                Xtr = scaler.fit_transform(X[tr])
                Xva = scaler.transform(X[va])
                clf = LogisticRegression(
                    C=C, penalty="l2", class_weight="balanced",
                    solver="lbfgs", max_iter=1000, random_state=42,
                    **({"multi_class": "multinomial"} if args.task == "3class" else {})
                )
                clf.fit(Xtr, y[tr])
                fold_scores.append(float(balanced_accuracy_score(y[va], clf.predict(Xva))))
            results.append({
                "layer": layer, "C": C,
                "cv_balanced_accuracy_mean": float(np.mean(fold_scores)),
                "cv_balanced_accuracy_std": float(np.std(fold_scores)),
                "fold_scores": fold_scores
            })
            print(f"layer={layer:02d} C={C:g} mean_BA={np.mean(fold_scores):.4f}")
    results.sort(key=lambda r: r["cv_balanced_accuracy_mean"], reverse=True)
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"task": args.task, "selection": "GroupKFold on training scenarios only", "results": results, "best": results[0]}, indent=2), encoding="utf-8")
    print("Best:", results[0]); print("Saved:", out)

if __name__ == "__main__":
    main()
