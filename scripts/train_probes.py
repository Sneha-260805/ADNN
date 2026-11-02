
#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


SEEDS = [0, 1, 2]
C_GRID = [0.001, 0.01, 0.1, 1.0, 10.0]
MIN_VALID_FOLDS = 4


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)




def _evaluate_one_layer(args):
    """
    Evaluate one layer across all GroupKFold folds and C values.

    This function is intentionally self-contained so it can be
    executed safely by a separate worker process.
    """
    (
        X_layer,
        y,
        fold_splits,
        layer,
        C_grid,
    ) = args

    X_layer = np.asarray(X_layer, dtype=np.float32)

    scores_by_C = {
        float(C): []
        for C in C_grid
    }

    for train_idx, val_idx in fold_splits:

        y_train = y[train_idx]
        y_val = y[val_idx]

        if len(np.unique(y_train)) < 2:
            continue

        if len(np.unique(y_val)) < 2:
            continue

        # Fit scaler exactly once per layer/fold.
        scaler = StandardScaler()

        X_train_scaled = scaler.fit_transform(
            X_layer[train_idx]
        )

        X_val_scaled = scaler.transform(
            X_layer[val_idx]
        )

        # Reuse scaled data for every C.
        for C in C_grid:

            model = LogisticRegression(
                penalty="l2",
                solver="liblinear",
                C=C,
                max_iter=2000,
                random_state=0,
            )

            model.fit(
                X_train_scaled,
                y_train,
            )

            pred = model.predict(
                X_val_scaled
            )

            score = balanced_accuracy_score(
                y_val,
                pred,
            )

            scores_by_C[float(C)].append(
                float(score)
            )

    candidates = []

    for C in C_grid:

        scores = scores_by_C[float(C)]

        if len(scores) < MIN_VALID_FOLDS:
            continue

        candidates.append(
            {
                "layer": int(layer),
                "C": float(C),
                "inner_cv_balanced_accuracy": float(
                    np.mean(scores)
                ),
                "valid_folds": len(scores),
            }
        )

    return candidates


def select_layer_and_C(X, y, groups, layers, C_grid):
    """
    Inner GroupKFold selection with parallel layer evaluation.

    Methodology is unchanged:
    - GroupKFold(n_splits=5)
    - StandardScaler
    - L2 LogisticRegression
    - liblinear
    - same C grid
    - balanced accuracy
    - highest inner-CV BA
    - tie: lowest layer, then lowest C
    """

    unique_groups = np.unique(groups)

    if len(unique_groups) < 5:
        raise RuntimeError(
            f"Need at least 5 unique groups for GroupKFold; "
            f"found {len(unique_groups)}."
        )

    # Compute the GroupKFold splits once.
    gkf = GroupKFold(n_splits=5)

    fold_splits = list(
        gkf.split(
            X[:, 0, :],
            y,
            groups,
        )
    )

    # Prepare one job per layer.
    jobs = []

    for layer in layers:
        jobs.append(
            (
                X[:, layer, :],
                y,
                fold_splits,
                layer,
                C_grid,
            )
        )

    # ----------------------------------------------------------
    # Parallelize independent layer evaluations.
    #
    # n_jobs=3 is deliberate because the Kaggle environment
    # has 4 CPU cores. BLAS threads are limited to 1 in the
    # launcher to prevent oversubscription.
    # ----------------------------------------------------------
    from joblib import Parallel, delayed

    print(
        f"Evaluating {len(layers)} layers "
        f"with 3 parallel workers...",
        flush=True,
    )

    results = Parallel(
        n_jobs=3,
        backend="loky",
        verbose=10,
    )(
        delayed(_evaluate_one_layer)(job)
        for job in jobs
    )

    candidates = [
        candidate
        for layer_candidates in results
        for candidate in layer_candidates
    ]

    if not candidates:
        raise RuntimeError(
            "No valid layer/C candidate survived inner CV."
        )

    candidates.sort(
        key=lambda x: (
            -x["inner_cv_balanced_accuracy"],
            x["layer"],
            x["C"],
        )
    )

    best = candidates[0]

    print(
        f"Best layer={best['layer']} "
        f"C={best['C']} "
        f"inner_BA="
        f"{best['inner_cv_balanced_accuracy']:.6f}",
        flush=True,
    )

    return best, candidates

def evaluate(model, X, y):
    pred = model.predict(X)

    if hasattr(model, "predict_proba"):
        prob = model.predict_proba(X)[:, 1]
    else:
        prob = model.decision_function(X)

    labels = [0, 1]

    cm = confusion_matrix(
        y,
        pred,
        labels=labels,
    )

    try:
        auroc = roc_auc_score(y, prob)
    except ValueError:
        auroc = None

    return {
        "accuracy": float(
            accuracy_score(y, pred)
        ),
        "balanced_accuracy": float(
            balanced_accuracy_score(y, pred)
        ),
        "macro_f1": float(
            f1_score(
                y,
                pred,
                average="macro",
            )
        ),
        "auroc": None if auroc is None else float(auroc),
        "confusion_matrix": cm.tolist(),
    }, pred, prob


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--hidden",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--metadata",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--splits",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--representation",
        choices=[
            "last_action_token",
            "mean_action_tokens",
        ],
        default="last_action_token",
    )

    args = parser.parse_args()

    # -----------------------------------------------------
    # Load fresh hidden states
    # -----------------------------------------------------

    hidden_path = (
        args.hidden
        / (
            "last_action_token.npy"
            if args.representation == "last_action_token"
            else "mean_action_tokens.npy"
        )
    )

    X = np.load(
        hidden_path,
        mmap_mode="r",
    )

    if X.ndim != 3:
        raise RuntimeError(
            f"Expected 3-D hidden-state array, got {X.shape}"
        )

    n_records, n_layers, hidden_size = X.shape

    print(
        f"Loaded hidden states: "
        f"records={n_records}, "
        f"layers={n_layers}, "
        f"hidden_size={hidden_size}"
    )

    # -----------------------------------------------------
    # Load fresh metadata
    # -----------------------------------------------------

    with args.metadata.open(
        "r",
        encoding="utf-8",
    ) as f:
        metadata = [
            json.loads(line)
            for line in f
        ]

    if len(metadata) != n_records:
        raise RuntimeError(
            "Metadata length does not match "
            "hidden-state record count."
        )

    fresh_id_to_row = {
        record["id"]: i
        for i, record in enumerate(metadata)
    }

    if len(fresh_id_to_row) != n_records:
        raise RuntimeError(
            "Duplicate record IDs detected in metadata."
        )

    # -----------------------------------------------------
    # Binary labels
    # -----------------------------------------------------

    binary_records = []

    for row, record in enumerate(metadata):

        label = record["label"]

        if label == "partially_reversible":
            continue

        if label not in {
            "reversible",
            "irreversible",
        }:
            raise RuntimeError(
                f"Unexpected label: {label}"
            )

        binary_records.append(
            {
                "row": row,
                "id": record["id"],
                "label": label,
                "scenario_id": record["scenario_id"],
            }
        )

    label_to_int = {
        "irreversible": 0,
        "reversible": 1,
    }

    print(
        "Binary records:",
        len(binary_records),
    )

    print(
        "Binary label counts:",
        {
            label: sum(
                r["label"] == label
                for r in binary_records
            )
            for label in label_to_int
        },
    )

    # -----------------------------------------------------
    # Run all frozen seeds
    # -----------------------------------------------------

    all_results = []

    for seed in SEEDS:

        split_path = (
            args.splits
            / f"split_seed_{seed}.json"
        )

        split = load_json(split_path)

        # IMPORTANT:
        # split indices refer to canonical dataset ordering,
        # not fresh hidden-state ordering.
        #
        # Load canonical dataset to translate:
        # canonical index -> record ID -> fresh row.
        from adnn.dataset.api import load_dataset

        dataset = load_dataset(
            Path(
                "data/production/v1.0"
            )
        )

        canonical_records = list(
            dataset.records
        )

        if len(canonical_records) != len(metadata):
            raise RuntimeError(
                "Canonical dataset and fresh metadata "
                "have different record counts."
            )

        train_rows_all = [
            fresh_id_to_row[
                canonical_records[i]["id"]
            ]
            for i in split["train_indices"]
        ]

        test_rows_all = [
            fresh_id_to_row[
                canonical_records[i]["id"]
            ]
            for i in split["test_indices"]
        ]

        # -------------------------------------------------
        # Keep only binary records.
        # -------------------------------------------------

        binary_row_set = {
            r["row"]
            for r in binary_records
        }

        train_rows = [
            i
            for i in train_rows_all
            if i in binary_row_set
        ]

        test_rows = [
            i
            for i in test_rows_all
            if i in binary_row_set
        ]

        # -------------------------------------------------
        # Scenario groups
        # -------------------------------------------------

        scenario_by_row = {
            r["row"]: r["scenario_id"]
            for r in binary_records
        }

        label_by_row = {
            r["row"]: label_to_int[r["label"]]
            for r in binary_records
        }

        train_scenarios = {
            scenario_by_row[i]
            for i in train_rows
        }

        test_scenarios = {
            scenario_by_row[i]
            for i in test_rows
        }

        overlap = train_scenarios & test_scenarios

        if overlap:
            raise RuntimeError(
                f"Seed {seed}: scenario leakage after "
                f"ID-based split translation."
            )

        X_train = np.asarray(
            X[train_rows],
            dtype=np.float32,
        )

        X_test = np.asarray(
            X[test_rows],
            dtype=np.float32,
        )

        y_train = np.asarray(
            [
                label_by_row[i]
                for i in train_rows
            ],
            dtype=np.int64,
        )

        y_test = np.asarray(
            [
                label_by_row[i]
                for i in test_rows
            ],
            dtype=np.int64,
        )

        groups_train = np.asarray(
            [
                scenario_by_row[i]
                for i in train_rows
            ]
        )

        print("\n" + "=" * 70)
        print(f"SEED {seed}")
        print("=" * 70)
        print(
            "Train:",
            len(train_rows),
            "Test:",
            len(test_rows),
        )
        print(
            "Train scenarios:",
            len(train_scenarios),
        )
        print(
            "Test scenarios:",
            len(test_scenarios),
        )

        # -------------------------------------------------
        # Inner CV layer/C selection
        # -------------------------------------------------

        layers = list(range(n_layers))

        best, candidates = select_layer_and_C(
            X_train,
            y_train,
            groups_train,
            layers,
            C_GRID,
        )

        best_layer = best["layer"]
        best_C = best["C"]

        print(
            "Selected layer:",
            best_layer,
            "C:",
            best_C,
            "inner BA:",
            best["inner_cv_balanced_accuracy"],
        )

        # -------------------------------------------------
        # Fit final model on complete training split
        # -------------------------------------------------

        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                penalty="l2",
                solver="liblinear",
                C=best_C,
                max_iter=2000,
                random_state=0,
            ),
        )

        model.fit(
            X_train[:, best_layer, :],
            y_train,
        )

        metrics, pred, prob = evaluate(
            model,
            X_test[:, best_layer, :],
            y_test,
        )

        print(
            "Test accuracy:",
            metrics["accuracy"],
        )
        print(
            "Test balanced accuracy:",
            metrics["balanced_accuracy"],
        )
        print(
            "Test macro-F1:",
            metrics["macro_f1"],
        )
        print(
            "Test AUROC:",
            metrics["auroc"],
        )

        result = {
            "seed": seed,
            "representation": args.representation,
            "hidden_shape": [
                int(n_records),
                int(n_layers),
                int(hidden_size),
            ],
            "train_count": len(train_rows),
            "test_count": len(test_rows),
            "train_scenarios": len(train_scenarios),
            "test_scenarios": len(test_scenarios),
            "selected_layer": best_layer,
            "selected_C": best_C,
            "inner_cv": best,
            "test_metrics": metrics,
            "candidates": candidates,
        }

        all_results.append(result)

        # -------------------------------------------------
        # Save predictions
        # -------------------------------------------------

        prediction_path = (
            args.output
            / (
                f"predictions_"
                f"{args.representation}_"
                f"seed_{seed}.jsonl"
            )
        )

        prediction_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with prediction_path.open(
            "w",
            encoding="utf-8",
        ) as f:

            for row, true_y, pred_y, p in zip(
                test_rows,
                y_test,
                pred,
                prob,
            ):

                record = metadata[row]

                out = {
                    "id": record["id"],
                    "scenario_id": record["scenario_id"],
                    "true_label": int(true_y),
                    "predicted_label": int(pred_y),
                    "probability_reversible": float(p),
                    "seed": seed,
                    "representation": args.representation,
                    "layer": best_layer,
                }

                f.write(
                    json.dumps(out)
                    + "\n"
                )

    # -----------------------------------------------------
    # Save aggregate results
    # -----------------------------------------------------

    output_metrics = (
        args.output
        / f"metrics_{args.representation}.json"
    )

    save_json(
        all_results,
        output_metrics,
    )

    manifest = {
        "experiment": "E2",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "representation": args.representation,
        "hidden_shape": [
            int(n_records),
            int(n_layers),
            int(hidden_size),
        ],
        "seeds": SEEDS,
        "C_grid": C_GRID,
        "inner_cv": {
            "method": "GroupKFold",
            "folds": 5,
            "minimum_valid_folds": MIN_VALID_FOLDS,
            "selection_metric": "balanced_accuracy",
        },
        "split_mapping": (
            "canonical_dataset_index -> record_id "
            "-> fresh_hidden_state_row"
        ),
        "results_file": str(output_metrics),
    }

    save_json(
        manifest,
        args.output / "manifest.json",
    )

    print("\n" + "=" * 70)
    print("BINARY PROBE RUN COMPLETE")
    print("=" * 70)
    print("Output:", args.output)


if __name__ == "__main__":
    main()
