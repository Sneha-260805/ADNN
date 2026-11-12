"""Run one direction of the ADNN Sandbox <-> ScienceWorld transfer test.

Inputs are aligned record JSONL + hidden-state .npy arrays. Supply source and
target environments explicitly. The chosen layer/C are fixed experiment
settings, not tuned on the target environment.
"""
import argparse, json
from pathlib import Path
import numpy as np
from scripts.rq1.common import read_jsonl, labels_for, make_probe, score_model

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--records", required=True, help="JSONL whose order matches the embeddings")
    p.add_argument("--hidden-states", required=True)
    p.add_argument("--source", required=True, help="e.g. sandbox or scienceworld")
    p.add_argument("--target", required=True, help="e.g. scienceworld or sandbox")
    p.add_argument("--layer", type=int, required=True)
    p.add_argument("--C", type=float, required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    records = read_jsonl(args.records)
    X = np.load(args.hidden_states, mmap_mode="r")
    if len(records) != X.shape[0]:
        raise ValueError("records.jsonl order/length must match hidden-state rows")
    if not 0 <= args.layer < X.shape[1]:
        raise ValueError("Requested layer is outside hidden-state tensor")
    env = np.asarray([str(r.get("environment", "")).lower() for r in records])
    source_mask = env == args.source.lower()
    target_mask = env == args.target.lower()
    # The transfer experiment uses reversible vs partially reversible records;
    # irreversible examples are excluded because ScienceWorld has no I class.
    valid = np.asarray([r.get("label") in ("reversible", "partially_reversible") for r in records])
    source_idx = np.where(source_mask & valid)[0]
    target_idx = np.where(target_mask & valid)[0]
    if not len(source_idx) or not len(target_idx):
        raise ValueError(f"Empty source/target after filtering: source={len(source_idx)}, target={len(target_idx)}")
    y = np.asarray([int(r["label"] == "partially_reversible") for r in records])
    probe = make_probe(args.C, "binary")
    probe.fit(np.asarray(X[source_idx, args.layer, :], dtype=np.float32), y[source_idx])
    pred, metrics = score_model(probe, np.asarray(X[target_idx, args.layer, :], dtype=np.float32), y[target_idx], "binary")
    result = {
        "source_environment": args.source, "target_environment": args.target,
        "layer": args.layer, "C": args.C, "source_records": len(source_idx),
        "target_records": len(target_idx), "metrics": metrics,
        "target_indices": target_idx.tolist(), "predictions": pred.astype(int).tolist(),
        "limitation": "ScienceWorld transfer tests generalisation to a new environment. It cannot separate state reasoning from action identity."
    }
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2)); print("Saved:", out)

if __name__ == "__main__":
    main()
