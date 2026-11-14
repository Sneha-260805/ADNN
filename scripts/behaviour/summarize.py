"""Regenerate summary JSON and a figure from an experiment's saved outcomes."""
import argparse
import json
from pathlib import Path

from adnn.behaviour.analysis import behaviour_metrics
from adnn.behaviour.judgment import classification_metrics


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run_directory")
    args = p.parse_args()
    root = Path(args.run_directory)
    rows = [json.loads(line) for line in (root / "outcomes.jsonl").read_text().splitlines()]
    metrics = classification_metrics(rows) if "example_id" in rows[0] else behaviour_metrics(rows)
    (root / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if "outcomes" in metrics:
        names = ["K", "A", "blindness_gap"]
        vals = [metrics["outcomes"][name] for name in names]
        means = [v["estimate"] for v in vals]
        plt.bar(names, means)
        # Percentile intervals need not contain the estimate; draw endpoints directly.
        for j, value in enumerate(vals):
            plt.plot([j, j], value["ci95"], color="black")
        plt.ylabel("Fraction of task pairs")
        plt.title(f"Matched judgments and behaviour ({metrics['n_pairs']} pairs)")
    else:
        plt.imshow(metrics["confusion_matrix"], cmap="Blues")
        plt.xticks(range(4), ["R", "P", "I", "Invalid"])
        plt.yticks(range(4), ["R", "P", "I", "Invalid"])
        plt.xlabel("Predicted")
        plt.ylabel("Ground truth")
    plt.tight_layout()
    plt.savefig(root / "summary.png", dpi=200)
    plt.close()


if __name__ == "__main__":
    main()
