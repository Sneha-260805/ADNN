#!/usr/bin/env python3

"""
E2 linear probes for ADNN.

Task:
    Binary reversible vs irreversible classification.

Excluded:
    partially_reversible

Representations:
    - last_action_token
    - mean_action_tokens

Model:
    Qwen/Qwen2.5-7B-Instruct

Probe:
    StandardScaler + L2 Logistic Regression

Selection:
    - 5-fold GroupKFold by scenario_id
    - C selected using training data only
    - layer selected using training-only inner-CV
    - at least 4 valid folds required

Evaluation:
    Held-out scenario-disjoint test set.

No test data is used for C or layer selection.
"""

import argparse
import hashlib
import json
import os
from collections import Counter
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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

SEEDS = [0, 1, 2]

LAYERS = list(range(29))

C_GRID = [
    0.001,
    0.01,
    0.1,
    1.0,
    10.0,
]

N_SPLITS = 5

LABEL_TO_INT = {
    "reversible": 0,
    "irreversible": 1,
}

POSITIONS = [
    "last_action_token",
    "mean_action_tokens",
]


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def sha256_file(path):

    digest = hashlib.sha256()

    with open(path, "rb") as f:

        while True:

            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def load_metadata(path):

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return [
            json.loads(line)
            for line in f
        ]


def evaluate_binary(
    y_true,
    y_pred,
    y_probability
):

    metrics = {
        "accuracy": float(
            accuracy_score(
                y_true,
                y_pred
            )
        ),

        "balanced_accuracy": float(
            balanced_accuracy_score(
                y_true,
                y_pred
            )
        ),

        "macro_f1": float(
            f1_score(
                y_true,
                y_pred,
                average="macro"
            )
        ),
    }

    if len(np.unique(y_true)) == 2:

        metrics["auroc"] = float(
            roc_auc_score(
                y_true,
                y_probability
            )
        )

    else:

        metrics["auroc"] = None

    metrics["confusion_matrix"] = (
        confusion_matrix(
            y_true,
            y_pred,
            labels=[0, 1]
        ).tolist()
    )

    return metrics


def build_model(C):

    return Pipeline([
        (
            "scaler",
            StandardScaler()
        ),
        (
            "classifier",
            LogisticRegression(
                C=C,
                penalty="l2",
                solver="liblinear",
                max_iter=2000,
                random_state=0
            )
        ),
    ])


def inner_cv_score(
    X,
    y,
    groups,
    C
):

    group_kfold = GroupKFold(
        n_splits=N_SPLITS
    )

    fold_scores = []

    for train_idx, val_idx in group_kfold.split(
        X,
        y,
        groups=groups
    ):

        y_train_fold = y[
            train_idx
        ]

        y_val_fold = y[
            val_idx
        ]

        # A one-class validation fold cannot
        # provide a meaningful BA estimate.
        if len(
            np.unique(y_val_fold)
        ) < 2:
            continue

        if len(
            np.unique(y_train_fold)
        ) < 2:
            continue

        model = build_model(C)

        model.fit(
            X[train_idx],
            y_train_fold
        )

        y_val_pred = model.predict(
            X[val_idx]
        )

        score = balanced_accuracy_score(
            y_val_fold,
            y_val_pred
        )

        fold_scores.append(
            float(score)
        )

    # Frozen analysis-plan rule.
    if len(fold_scores) < 4:

        return None, fold_scores

    return (
        float(np.mean(fold_scores)),
        fold_scores
    )


def select_layer_and_C(
    X_all,
    y,
    groups
):

    layer_results = []

    for layer in LAYERS:

        X_layer = X_all[
            :,
            layer,
            :
        ]

        best_C = None
        best_score = -np.inf
        best_folds = None

        for C in C_GRID:

            cv_score, fold_scores = (
                inner_cv_score(
                    X_layer,
                    y,
                    groups,
                    C
                )
            )

            if cv_score is None:
                continue

            if cv_score > best_score:

                best_score = cv_score
                best_C = C
                best_folds = fold_scores

        if best_C is None:

            layer_results.append({
                "layer": layer,
                "best_C": None,
                "inner_cv_balanced_accuracy": None,
                "valid_folds": 0,
            })

        else:

            layer_results.append({
                "layer": layer,
                "best_C": float(best_C),
                "inner_cv_balanced_accuracy": (
                    float(best_score)
                ),
                "valid_folds": len(
                    best_folds
                ),
                "fold_scores": best_folds,
            })

    valid_layers = [
        item
        for item in layer_results
        if item[
            "inner_cv_balanced_accuracy"
        ] is not None
    ]

    if not valid_layers:

        raise RuntimeError(
            "No valid layer passed the "
            "inner-CV requirement."
        )

    # Highest inner-CV BA.
    # Lowest layer breaks exact ties.
    selected = sorted(
        valid_layers,
        key=lambda item: (
            -item[
                "inner_cv_balanced_accuracy"
            ],
            item["layer"],
        )
    )[0]

    return selected, layer_results


def parse_args():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--hidden-states",
        default="/kaggle/working/e2_qwen7b_full",
    )

    parser.add_argument(
        "--splits",
        default=(
            "results/E2_probes/splits"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "results/E2_probes/"
            "qwen2.5-7b-instruct/"
            "probe_run"
        ),
    )

    return parser.parse_args()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    args = parse_args()

    hidden_dir = Path(
        args.hidden_states
    )

    split_dir = Path(
        args.splits
    )

    output_dir = Path(
        args.output
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Load hidden states
    # --------------------------------------------------------

    last_hidden = np.load(
        hidden_dir /
        "last_action_token.npy",
        mmap_mode="r"
    )

    mean_hidden = np.load(
        hidden_dir /
        "mean_action_tokens.npy",
        mmap_mode="r"
    )

    metadata = load_metadata(
        hidden_dir /
        "metadata.jsonl"
    )

    if len(metadata) != 621:

        raise RuntimeError(
            f"Expected 621 metadata rows, "
            f"got {len(metadata)}"
        )

    if last_hidden.shape != (
        621,
        29,
        3584
    ):

        raise RuntimeError(
            "Unexpected last-action hidden-state "
            f"shape: {last_hidden.shape}"
        )

    if mean_hidden.shape != (
        621,
        29,
        3584
    ):

        raise RuntimeError(
            "Unexpected mean-action hidden-state "
            f"shape: {mean_hidden.shape}"
        )

    metadata_id_to_row = {
        item["id"]: i
        for i, item in enumerate(metadata)
    }

    if len(metadata_id_to_row) != 621:

        raise RuntimeError(
            "Duplicate record IDs in metadata."
        )

    positions = {
        "last_action_token": last_hidden,
        "mean_action_tokens": mean_hidden,
    }

    all_results = []

    # --------------------------------------------------------
    # Seeds
    # --------------------------------------------------------

    for seed in SEEDS:

        split_path = (
            split_dir /
            f"split_seed_{seed}.json"
        )

        with open(
            split_path,
            "r",
            encoding="utf-8"
        ) as f:

            split = json.load(f)

        train_scenarios = set(
            split["train_scenarios"]
        )

        test_scenarios = set(
            split["test_scenarios"]
        )

        if train_scenarios & test_scenarios:

            raise RuntimeError(
                f"Scenario leakage in seed {seed}"
            )

        train_rows = []
        test_rows = []

        for record_id, row in (
            metadata_id_to_row.items()
        ):

            label = metadata[row]["label"]

            if label not in LABEL_TO_INT:
                continue

            scenario_id = (
                metadata[row]["scenario_id"]
            )

            if scenario_id in train_scenarios:

                train_rows.append(row)

            elif scenario_id in test_scenarios:

                test_rows.append(row)

            else:

                raise RuntimeError(
                    f"Unassigned scenario: "
                    f"{scenario_id}"
                )

        if len(train_rows) != 311:

            raise RuntimeError(
                f"Seed {seed}: expected 311 "
                f"binary train rows, got "
                f"{len(train_rows)}"
            )

        if len(test_rows) != 78:

            raise RuntimeError(
                f"Seed {seed}: expected 78 "
                f"binary test rows, got "
                f"{len(test_rows)}"
            )

        y_train = np.array([
            LABEL_TO_INT[
                metadata[row]["label"]
            ]
            for row in train_rows
        ])

        y_test = np.array([
            LABEL_TO_INT[
                metadata[row]["label"]
            ]
            for row in test_rows
        ])

        groups_train = np.array([
            metadata[row]["scenario_id"]
            for row in train_rows
        ])

        groups_test = np.array([
            metadata[row]["scenario_id"]
            for row in test_rows
        ])

        if set(
            groups_train
        ) & set(
            groups_test
        ):

            raise RuntimeError(
                f"Scenario leakage in seed {seed}"
            )

        print()
        print("=" * 70)
        print(f"E2 SEED {seed}")
        print("=" * 70)

        print(
            "Train:",
            len(train_rows),
            Counter(y_train)
        )

        print(
            "Test:",
            len(test_rows),
            Counter(y_test)
        )

        # ----------------------------------------------------
        # Representation positions
        # ----------------------------------------------------

        for position_name in POSITIONS:

            print()
            print("-" * 70)
            print(
                f"POSITION: {position_name}"
            )
            print("-" * 70)

            hidden = positions[
                position_name
            ]

            X_train_all = np.asarray(
                hidden[train_rows],
                dtype=np.float32
            )

            X_test_all = np.asarray(
                hidden[test_rows],
                dtype=np.float32
            )

            # ------------------------------------------------
            # Select layer and C using training only
            # ------------------------------------------------

            selected, layer_results = (
                select_layer_and_C(
                    X_train_all,
                    y_train,
                    groups_train
                )
            )

            selected_layer = selected[
                "layer"
            ]

            selected_C = selected[
                "best_C"
            ]

            print(
                "Selected layer:",
                selected_layer
            )

            print(
                "Selected C:",
                selected_C
            )

            print(
                "Inner-CV BA:",
                selected[
                    "inner_cv_balanced_accuracy"
                ]
            )

            print(
                "Valid folds:",
                selected[
                    "valid_folds"
                ]
            )

            # ------------------------------------------------
            # Fit final model on ALL training data
            # ------------------------------------------------

            X_train = X_train_all[
                :,
                selected_layer,
                :
            ]

            X_test = X_test_all[
                :,
                selected_layer,
                :
            ]

            final_model = build_model(
                selected_C
            )

            final_model.fit(
                X_train,
                y_train
            )

            # ------------------------------------------------
            # Held-out test evaluation
            # ------------------------------------------------

            y_pred = final_model.predict(
                X_test
            )

            y_probability = (
                final_model.predict_proba(
                    X_test
                )[:, 1]
            )

            test_metrics = evaluate_binary(
                y_test,
                y_pred,
                y_probability
            )

            print()
            print("TEST RESULTS")

            print(
                "Accuracy:",
                test_metrics[
                    "accuracy"
                ]
            )

            print(
                "Balanced accuracy:",
                test_metrics[
                    "balanced_accuracy"
                ]
            )

            print(
                "Macro-F1:",
                test_metrics[
                    "macro_f1"
                ]
            )

            print(
                "AUROC:",
                test_metrics[
                    "auroc"
                ]
            )

            print(
                "Confusion matrix:"
            )

            print(
                np.array(
                    test_metrics[
                        "confusion_matrix"
                    ]
                )
            )

            # ------------------------------------------------
            # Result object
            # ------------------------------------------------

            result = {
                "experiment": "E2",
                "model": (
                    "Qwen/Qwen2.5-7B-Instruct"
                ),
                "seed": seed,
                "position": position_name,
                "task": "binary",
                "labels": [
                    "reversible",
                    "irreversible",
                ],
                "excluded_label": (
                    "partially_reversible"
                ),
                "selected_layer": (
                    selected_layer
                ),
                "selected_C": (
                    selected_C
                ),
                "inner_cv": {
                    "balanced_accuracy": (
                        selected[
                            "inner_cv_balanced_accuracy"
                        ]
                    ),
                    "valid_folds": (
                        selected[
                            "valid_folds"
                        ]
                    ),
                    "fold_scores": (
                        selected[
                            "fold_scores"
                        ]
                    ),
                },
                "test": test_metrics,
                "n_train": len(train_rows),
                "n_test": len(test_rows),
                "train_scenarios": len(
                    set(groups_train)
                ),
                "test_scenarios": len(
                    set(groups_test)
                ),
            }

            all_results.append(
                result
            )

            # ------------------------------------------------
            # Predictions
            # ------------------------------------------------

            predictions_path = (
                output_dir /
                f"predictions_seed_{seed}_"
                f"{position_name}.jsonl"
            )

            with open(
                predictions_path,
                "w",
                encoding="utf-8"
            ) as f:

                for i, row in enumerate(
                    test_rows
                ):

                    pred_label = (
                        "irreversible"
                        if y_pred[i] == 1
                        else "reversible"
                    )

                    prediction = {
                        "id": metadata[row]["id"],
                        "scenario_id": (
                            metadata[row][
                                "scenario_id"
                            ]
                        ),
                        "true_label": (
                            metadata[row][
                                "label"
                            ]
                        ),
                        "true_binary": int(
                            y_test[i]
                        ),
                        "pred_binary": int(
                            y_pred[i]
                        ),
                        "pred_label": pred_label,
                        "prob_irreversible": (
                            float(
                                y_probability[i]
                            )
                        ),
                    }

                    f.write(
                        json.dumps(
                            prediction
                        ) + "\n"
                    )

            # ------------------------------------------------
            # Layer selection details
            # ------------------------------------------------

            selection_path = (
                output_dir /
                f"layer_selection_seed_{seed}_"
                f"{position_name}.json"
            )

            with open(
                selection_path,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    {
                        "seed": seed,
                        "position": position_name,
                        "selected_layer": (
                            selected_layer
                        ),
                        "selected_C": (
                            selected_C
                        ),
                        "layers": (
                            layer_results
                        ),
                    },
                    f,
                    indent=2
                )

    # --------------------------------------------------------
    # Combined metrics
    # --------------------------------------------------------

    metrics_path = (
        output_dir /
        "metrics.json"
    )

    with open(
        metrics_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            all_results,
            f,
            indent=2
        )

    # --------------------------------------------------------
    # Run manifest
    # --------------------------------------------------------

    manifest = {
        "experiment": "E2",
        "model": (
            "Qwen/Qwen2.5-7B-Instruct"
        ),
        "task": "binary",
        "excluded_label": (
            "partially_reversible"
        ),
        "seeds": SEEDS,
        "layers": LAYERS,
        "C_grid": C_GRID,
        "inner_cv_folds": N_SPLITS,
        "group_key": "scenario_id",
        "selection_metric": (
            "balanced_accuracy"
        ),
        "minimum_valid_folds": 4,
        "representations": POSITIONS,
        "hidden_state_manifest_sha256": (
            sha256_file(
                hidden_dir /
                "manifest.json"
            )
            if (
                hidden_dir /
                "manifest.json"
            ).exists()
            else None
        ),
        "results": len(all_results),
    }

    manifest_path = (
        output_dir /
        "manifest.json"
    )

    with open(
        manifest_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2
        )

    print()
    print("=" * 70)
    print("E2 PROBE TRAINING COMPLETE")
    print("=" * 70)
    print(
        "Results saved to:",
        output_dir
    )
    print(
        "Total result rows:",
        len(all_results)
    )


if __name__ == "__main__":
    main()
