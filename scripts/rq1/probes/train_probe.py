"""Train/evaluate an RQ1 probe from an already-extracted .npy hidden-state tensor.

Example:
python scripts/probes/train_probe.py --records data/records.jsonl \
 --split results/supplementary_splits/scenario_split_seed_2026.json \
 --hidden-states results/rq1_qwen/hidden_states/last_action_token.npy \
 --model Qwen --task 3class --layer 20 --C 0.1 \
 --output results/rq1_qwen/probes/reproduced_3class.json

Use the official frozen split and selected layer/C from the experiment handoff
for the primary reproduction. This script does not extract model activations.
"""
import argparse, json
from pathlib import Path
import numpy as np
from scripts.rq1.common import (
    read_jsonl, load_split, labels_for, make_probe, score_model
)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--records", required=True)
    p.add_argument("--split", required=True)
    p.add_argument("--hidden-states", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--task", choices=["3class","binary"], required=True)
    p.add_argument("--layer", type=int, required=True)
    p.add_argument("--C", type=float, required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    records = read_jsonl(args.records)
    X_all = np.load(args.hidden_states, mmap_mode="r")
    if len(records) != X_all.shape[0]:
        raise ValueError(f"Record/embedding mismatch: {len(records)} vs {X_all.shape[0]}")
    if not 0 <= args.layer < X_all.shape[1]:
        raise ValueError(f"Layer {args.layer} outside [0,{X_all.shape[1]-1}]")
    train_idx, test_idx = load_split(args.split)
    y = labels_for(records, args.task)
    X_train = np.asarray(X_all[train_idx, args.layer, :], dtype=np.float32)
    X_test = np.asarray(X_all[test_idx, args.layer, :], dtype=np.float32)
    model = make_probe(args.C, args.task)
    model.fit(X_train, y[train_idx])
    predictions, metrics = score_model(model, X_test, y[test_idx], args.task)

    output = {
        "model": args.model, "task": args.task, "layer": args.layer, "C": args.C,
        "train_records": int(len(train_idx)), "test_records": int(len(test_idx)),
        "metrics": metrics,
        "test_predictions": predictions.astype(int).tolist(),
        "test_indices": test_idx.tolist()
    }
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print("Saved:", out)

if __name__ == "__main__":
    main()
