
import json
import time
from pathlib import Path

import numpy as np

from joblib import Parallel, delayed

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)


# ============================================================
# CONFIG
# ============================================================

HIDDEN_PATH = Path(
    "/kaggle/working/e2_qwen7b_full/last_action_token.npy"
)

METADATA_PATH = Path(
    "/kaggle/working/e2_qwen7b_full/metadata.jsonl"
)

SPLIT_DIR = Path(
    "/kaggle/working/ADNN/results/"
    "E2_extensions/qwen2.5-7b-instruct/"
    "three_class_splits"
)

OUTPUT_DIR = Path(
    "/kaggle/working/ADNN/results/"
    "E2_extensions/qwen2.5-7b-instruct/"
    "three_class_probe_sklearn_parallel"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

SEEDS = [0, 1, 2]

C_GRID = [
    0.001,
    0.01,
    0.1,
    1.0,
    10.0,
]

N_LAYERS = 29
N_SPLITS = 5
MIN_VALID_FOLDS = 4

N_JOBS = 4

LABELS = {
    "reversible": 0,
    "partially_reversible": 1,
    "irreversible": 2,
}

CLASS_NAMES = [
    "reversible",
    "partially_reversible",
    "irreversible",
]


# ============================================================
# HELPERS
# ============================================================

def save_json(path, obj):

    tmp = Path(
        str(path) + ".tmp"
    )

    with open(
        tmp,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            obj,
            f,
            indent=2,
        )

    tmp.replace(path)


def load_metadata():

    metadata = []

    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            metadata.append(
                json.loads(line)
            )

    return metadata


def compute_macro_auroc(
    y_true,
    probabilities,
):

    try:

        return float(
            roc_auc_score(
                y_true,
                probabilities,
                multi_class="ovr",
                average="macro",
            )
        )

    except ValueError:

        return None


# ============================================================
# ONE CV FIT
# ============================================================

def evaluate_cv_fold(
    X_layer,
    train_idx,
    y_train_full,
    tr,
    va,
    C,
):

    X_tr = X_layer[
        train_idx[tr]
    ]

    X_va = X_layer[
        train_idx[va]
    ]

    y_tr = y_train_full[tr]
    y_va = y_train_full[va]

    scaler = StandardScaler()

    X_tr_scaled = scaler.fit_transform(
        X_tr
    )

    X_va_scaled = scaler.transform(
        X_va
    )

    model = LogisticRegression(
        penalty="l2",
        C=C,
        solver="lbfgs",
        max_iter=2000,
        random_state=0,
    )

    model.fit(
        X_tr_scaled,
        y_tr,
    )

    pred = model.predict(
        X_va_scaled
    )

    ba = balanced_accuracy_score(
        y_va,
        pred,
    )

    return float(ba)


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 70)
print("E2 THREE-CLASS R/P/I SKLEARN PARALLEL PROBE")
print("=" * 70)

print()
print("CPU jobs:", N_JOBS)

print()
print("Loading hidden states...")

hidden = np.load(
    HIDDEN_PATH,
    mmap_mode="r",
)

print(
    "Hidden states:",
    hidden.shape,
)

metadata = load_metadata()

print(
    "Metadata:",
    len(metadata),
)

if hidden.shape[0] != len(metadata):

    raise RuntimeError(
        "Hidden-state count does not match metadata count."
    )

if hidden.shape[1] != N_LAYERS:

    raise RuntimeError(
        f"Expected {N_LAYERS} layers, "
        f"got {hidden.shape[1]}"
    )

y = np.array(
    [
        LABELS[m["label"]]
        for m in metadata
    ],
    dtype=int,
)

print(
    "Label counts:",
    np.bincount(
        y,
        minlength=3,
    )
)


# ============================================================
# ALL SEEDS
# ============================================================

all_seed_results = []


for seed in SEEDS:

    print()
    print("=" * 70)
    print(f"SEED {seed}")
    print("=" * 70)

    split_path = (
        SPLIT_DIR
        / f"split_seed_{seed}.json"
    )

    with open(
        split_path,
        "r",
        encoding="utf-8",
    ) as f:

        split = json.load(f)

    train_idx = np.array(
        split["train_indices"],
        dtype=int,
    )

    test_idx = np.array(
        split["test_indices"],
        dtype=int,
    )

    y_train_full = y[
        train_idx
    ]

    y_test = y[
        test_idx
    ]

    groups = np.array(
        [
            metadata[i]["scenario_id"]
            for i in train_idx
        ]
    )

    print(
        "Train:",
        len(train_idx),
        "Test:",
        len(test_idx),
    )

    print(
        "Train labels:",
        np.bincount(
            y_train_full,
            minlength=3,
        )
    )

    print(
        "Test labels:",
        np.bincount(
            y_test,
            minlength=3,
        )
    )

    # --------------------------------------------------------
    # GROUP K-FOLD
    # --------------------------------------------------------

    gkf = GroupKFold(
        n_splits=N_SPLITS
    )

    valid_folds = []

    for fold_id, (tr, va) in enumerate(
        gkf.split(
            train_idx,
            y_train_full,
            groups,
        )
    ):

        y_tr = y_train_full[tr]
        y_va = y_train_full[va]

        if len(np.unique(y_tr)) < 3:
            continue

        if len(np.unique(y_va)) < 3:
            continue

        valid_folds.append(
            (
                fold_id,
                tr,
                va,
            )
        )

    print(
        "Valid inner folds:",
        [
            x[0]
            for x in valid_folds
        ],
    )

    # --------------------------------------------------------
    # CHECKPOINT
    # --------------------------------------------------------

    checkpoint_path = (
        OUTPUT_DIR
        / f"checkpoint_seed_{seed}.json"
    )

    if checkpoint_path.exists():

        with open(
            checkpoint_path,
            "r",
            encoding="utf-8",
        ) as f:

            checkpoint = json.load(f)

        completed_layers = {
            int(x)
            for x in checkpoint.get(
                "completed_layers",
                []
            )
        }

        layer_results = (
            checkpoint.get(
                "layer_results",
                {}
            )
        )

        print(
            "Resuming checkpoint."
        )

        print(
            "Completed layers:",
            sorted(
                completed_layers
            ),
        )

    else:

        completed_layers = set()
        layer_results = {}

    # --------------------------------------------------------
    # LAYERS
    # --------------------------------------------------------

    for layer in range(
        N_LAYERS
    ):

        if layer in completed_layers:

            print(
                f"Layer {layer}/28 "
                "already complete — skipping."
            )

            continue

        print()
        print(
            f"Seed {seed} | "
            f"Layer {layer}/28"
        )

        layer_start = time.time()

        X_layer = np.asarray(
            hidden[
                :,
                layer,
                :
            ],
            dtype=np.float32,
        )

        c_results = []

        # ----------------------------------------------------
        # EACH C
        # ----------------------------------------------------

        for C in C_GRID:

            # Run independent folds in parallel.
            fold_scores = Parallel(
                n_jobs=N_JOBS,
                backend="loky",
            )(
                delayed(
                    evaluate_cv_fold
                )(
                    X_layer,
                    train_idx,
                    y_train_full,
                    tr,
                    va,
                    C,
                )
                for (
                    fold_id,
                    tr,
                    va,
                ) in valid_folds
            )

            mean_ba = float(
                np.mean(
                    fold_scores
                )
            )

            c_results.append(
                {
                    "C": C,
                    "fold_balanced_accuracy":
                        fold_scores,
                    "mean_balanced_accuracy":
                        mean_ba,
                }
            )

        # ----------------------------------------------------
        # BEST C
        # ----------------------------------------------------

        best_c_result = max(
            c_results,
            key=lambda x: (
                x[
                    "mean_balanced_accuracy"
                ],
                -x["C"],
            ),
        )

        best_C = (
            best_c_result["C"]
        )

        best_inner_ba = (
            best_c_result[
                "mean_balanced_accuracy"
            ]
        )

        elapsed = (
            time.time()
            - layer_start
        )

        print(
            f"  Best C={best_C} "
            f"Inner BA={best_inner_ba:.6f} "
            f"Time={elapsed:.2f}s"
        )

        layer_results[
            str(layer)
        ] = {
            "layer": layer,
            "best_C": best_C,
            "best_inner_balanced_accuracy":
                best_inner_ba,
            "c_results": c_results,
            "time_seconds": elapsed,
        }

        completed_layers.add(
            layer
        )

        checkpoint = {
            "seed": seed,
            "completed_layers":
                sorted(
                    completed_layers
                ),
            "layer_results":
                layer_results,
        }

        save_json(
            checkpoint_path,
            checkpoint,
        )

        del X_layer

    # --------------------------------------------------------
    # SELECT LAYER
    # --------------------------------------------------------

    completed = [
        layer_results[
            str(layer)
        ]
        for layer in range(
            N_LAYERS
        )
    ]

    best_layer_result = min(
        completed,
        key=lambda x: (
            -x[
                "best_inner_balanced_accuracy"
            ],
            x["layer"],
            x["best_C"],
        ),
    )

    selected_layer = (
        best_layer_result["layer"]
    )

    selected_C = (
        best_layer_result["best_C"]
    )

    selected_inner_ba = (
        best_layer_result[
            "best_inner_balanced_accuracy"
        ]
    )

    print()
    print("SELECTED:")
    print(
        "  Layer:",
        selected_layer,
    )

    print(
        "  C:",
        selected_C,
    )

    print(
        "  Inner CV BA:",
        f"{selected_inner_ba:.6f}",
    )

    # --------------------------------------------------------
    # FINAL TRAINING
    # --------------------------------------------------------

    print()
    print("Final training...")

    X_selected = np.asarray(
        hidden[
            :,
            selected_layer,
            :
        ],
        dtype=np.float32,
    )

    X_train = X_selected[
        train_idx
    ]

    X_test = X_selected[
        test_idx
    ]

    scaler = StandardScaler()

    X_train_scaled = (
        scaler.fit_transform(
            X_train
        )
    )

    X_test_scaled = (
        scaler.transform(
            X_test
        )
    )

    final_model = LogisticRegression(
        penalty="l2",
        C=selected_C,
        solver="lbfgs",
        max_iter=2000,
        random_state=0,
    )

    final_model.fit(
        X_train_scaled,
        y_train_full,
    )

    test_pred = (
        final_model.predict(
            X_test_scaled
        )
    )

    test_prob = (
        final_model.predict_proba(
            X_test_scaled
        )
    )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    accuracy = accuracy_score(
        y_test,
        test_pred,
    )

    balanced_accuracy = (
        balanced_accuracy_score(
            y_test,
            test_pred,
        )
    )

    macro_f1 = f1_score(
        y_test,
        test_pred,
        average="macro",
    )

    macro_auroc = (
        compute_macro_auroc(
            y_test,
            test_prob,
        )
    )

    cm = confusion_matrix(
        y_test,
        test_pred,
        labels=[0, 1, 2],
    )

    print()
    print("TEST RESULTS")

    print(
        f"  Accuracy: "
        f"{accuracy:.6f}"
    )

    print(
        f"  Balanced Accuracy: "
        f"{balanced_accuracy:.6f}"
    )

    print(
        f"  Macro-F1: "
        f"{macro_f1:.6f}"
    )

    print(
        f"  Macro-AUROC: "
        f"{macro_auroc:.6f}"
    )

    print(
        "  Confusion Matrix:"
    )

    print(cm)

    # --------------------------------------------------------
    # PREDICTIONS
    # --------------------------------------------------------

    prediction_path = (
        OUTPUT_DIR
        / f"predictions_seed_{seed}.jsonl"
    )

    with open(
        prediction_path,
        "w",
        encoding="utf-8",
    ) as f:

        for position, idx in enumerate(
            test_idx
        ):

            record = {
                "index": int(idx),
                "id":
                    metadata[idx]["id"],
                "scenario_id":
                    metadata[idx][
                        "scenario_id"
                    ],
                "pair_id":
                    metadata[idx].get(
                        "pair_id"
                    ),
                "action_verb":
                    metadata[idx][
                        "action_verb"
                    ],
                "true_label":
                    CLASS_NAMES[
                        int(
                            y_test[
                                position
                            ]
                        )
                    ],
                "predicted_label":
                    CLASS_NAMES[
                        int(
                            test_pred[
                                position
                            ]
                        )
                    ],
                "probabilities": {
                    CLASS_NAMES[c]:
                        float(
                            test_prob[
                                position,
                                c,
                            ]
                        )
                    for c in range(3)
                },
            }

            f.write(
                json.dumps(record)
                + "\n"
            )

    # --------------------------------------------------------
    # SEED RESULT
    # --------------------------------------------------------

    seed_result = {
        "experiment":
            "E2_three_class_RPI",
        "model":
            "Qwen/Qwen2.5-7B-Instruct",
        "seed":
            seed,
        "dataset_records":
            621,
        "task": {
            "labels":
                CLASS_NAMES,
            "label_mapping":
                LABELS,
        },
        "representation":
            "last_action_token",
        "split": {
            "train_records":
                int(
                    len(train_idx)
                ),
            "test_records":
                int(
                    len(test_idx)
                ),
            "train_scenarios":
                len(
                    set(
                        metadata[i][
                            "scenario_id"
                        ]
                        for i in train_idx
                    )
                ),
            "test_scenarios":
                len(
                    set(
                        metadata[i][
                            "scenario_id"
                        ]
                        for i in test_idx
                    )
                ),
            "scenario_overlap":
                len(
                    set(
                        metadata[i][
                            "scenario_id"
                        ]
                        for i in train_idx
                    )
                    &
                    set(
                        metadata[i][
                            "scenario_id"
                        ]
                        for i in test_idx
                    )
                ),
        },
        "inner_cv": {
            "method":
                "GroupKFold",
            "requested_folds":
                N_SPLITS,
            "valid_folds":
                [
                    int(x[0])
                    for x in valid_folds
                ],
            "minimum_valid_folds":
                MIN_VALID_FOLDS,
            "selection_metric":
                "balanced_accuracy",
        },
        "selection": {
            "selected_layer":
                selected_layer,
            "selected_C":
                selected_C,
            "inner_cv_balanced_accuracy":
                selected_inner_ba,
        },
        "test_metrics": {
            "accuracy":
                float(accuracy),
            "balanced_accuracy":
                float(
                    balanced_accuracy
                ),
            "macro_f1":
                float(macro_f1),
            "macro_auroc":
                (
                    float(
                        macro_auroc
                    )
                    if macro_auroc
                    is not None
                    else None
                ),
            "confusion_matrix":
                cm.tolist(),
        },
        "layer_results":
            layer_results,
    }

    save_json(
        OUTPUT_DIR
        / f"seed_{seed}.json",
        seed_result,
    )

    all_seed_results.append(
        seed_result
    )

    print()
    print(
        f"Seed {seed} complete."
    )


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 70)
print("ALL SEEDS COMPLETE")
print("=" * 70)

selected_layers = [
    r["selection"][
        "selected_layer"
    ]
    for r in all_seed_results
]

selected_Cs = [
    r["selection"][
        "selected_C"
    ]
    for r in all_seed_results
]

test_acc = np.array([
    r["test_metrics"][
        "accuracy"
    ]
    for r in all_seed_results
])

test_ba = np.array([
    r["test_metrics"][
        "balanced_accuracy"
    ]
    for r in all_seed_results
])

test_f1 = np.array([
    r["test_metrics"][
        "macro_f1"
    ]
    for r in all_seed_results
])

test_auroc = np.array([
    r["test_metrics"][
        "macro_auroc"
    ]
    for r in all_seed_results
])

summary = {
    "experiment":
        "E2_three_class_RPI",
    "model":
        "Qwen/Qwen2.5-7B-Instruct",
    "seeds":
        SEEDS,
    "selected_layers":
        selected_layers,
    "selected_C":
        selected_Cs,
    "test_accuracy": {
        "mean":
            float(
                np.mean(test_acc)
            ),
        "sd":
            float(
                np.std(
                    test_acc,
                    ddof=1,
                )
            ),
        "per_seed":
            test_acc.tolist(),
    },
    "test_balanced_accuracy": {
        "mean":
            float(
                np.mean(test_ba)
            ),
        "sd":
            float(
                np.std(
                    test_ba,
                    ddof=1,
                )
            ),
        "per_seed":
            test_ba.tolist(),
    },
    "test_macro_f1": {
        "mean":
            float(
                np.mean(test_f1)
            ),
        "sd":
            float(
                np.std(
                    test_f1,
                    ddof=1,
                )
            ),
        "per_seed":
            test_f1.tolist(),
    },
    "test_macro_auroc": {
        "mean":
            float(
                np.mean(test_auroc)
            ),
        "sd":
            float(
                np.std(
                    test_auroc,
                    ddof=1,
                )
            ),
        "per_seed":
            test_auroc.tolist(),
    },
}

save_json(
    OUTPUT_DIR
    / "all_seeds.json",
    summary,
)

print()
print(
    "Selected layers:",
    selected_layers,
)

print(
    "Selected C:",
    selected_Cs,
)

print(
    "Test Balanced Accuracy:",
    summary[
        "test_balanced_accuracy"
    ],
)

print(
    "Test Macro-F1:",
    summary[
        "test_macro_f1"
    ],
)

print(
    "Test Macro-AUROC:",
    summary[
        "test_macro_auroc"
    ],
)

print()
print(
    "Results saved to:",
    OUTPUT_DIR,
)
