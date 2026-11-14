"""Evaluate frozen official-split probes on the predefined 707-record subset.

The model is fitted on the original official training partition only. The
robustness subset's held-out IDs are evaluated without fitting on them.
"""
import argparse, json
from pathlib import Path
import numpy as np
from scripts.rq1.common import read_jsonl, load_split, labels_for, make_probe, score_model

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--records", required=True)
    p.add_argument("--split", required=True)
    p.add_argument("--hidden-states", required=True)
    p.add_argument("--subset", required=True, help="JSON containing an 'ids' list")
    p.add_argument("--model", required=True)
    p.add_argument("--task", choices=["3class","binary"], required=True)
    p.add_argument("--layer", type=int, required=True)
    p.add_argument("--C", type=float, required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    records = read_jsonl(args.records)
    X = np.load(args.hidden_states, mmap_mode="r")
    subset = json.loads(Path(args.subset).read_text(encoding="utf-8"))
    subset_ids = set(map(str, subset["ids"]))
    train_idx, official_test_idx = load_split(args.split)
    id_to_idx = {str(r["id"]): i for i, r in enumerate(records)}
    missing = sorted(subset_ids - set(id_to_idx))
    if missing:
        raise ValueError(f"{len(missing)} subset IDs are absent from records; first: {missing[:5]}")
    subset_idx = np.asarray([id_to_idx[x] for x in subset["ids"]], dtype=int)
    # Only subset members belonging to the official test partition are evaluated.
    official_test_set = set(official_test_idx.tolist())
    eval_idx = np.asarray([i for i in subset_idx if i in official_test_set], dtype=int)
    if not len(eval_idx):
        raise ValueError("No robustness-subset records overlap the official test partition.")

    y = labels_for(records, args.task)
    probe = make_probe(args.C, args.task)
    probe.fit(np.asarray(X[train_idx, args.layer, :], dtype=np.float32), y[train_idx])
    pred, metrics = score_model(probe, np.asarray(X[eval_idx, args.layer, :], dtype=np.float32), y[eval_idx], args.task)
    result = {
        "model": args.model, "task": args.task, "layer": args.layer, "C": args.C,
        "protocol": "fit on original official training partition; evaluate subset records in official test partition",
        "subset_ids": len(subset_ids), "evaluated_records": len(eval_idx),
        "metrics": metrics, "test_indices": eval_idx.tolist(),
        "predictions": pred.astype(int).tolist()
    }
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2)); print("Saved:", out)

if __name__ == "__main__":
    main()
