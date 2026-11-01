
#!/usr/bin/env python3

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from adnn.dataset.loader import load_dataset


DATASET_PATH = Path("data/production/v1.0")
OUTPUT_DIR = Path(
    "results/E2_extensions/qwen2.5-7b-instruct/three_class_splits"
)

SEEDS = [0, 1, 2]
TEST_FRACTION_TARGET = 0.20


def get_label(record):
    return record["label"]


def get_scenario(record):
    return record["scenario_id"]


def score_candidate(test_records, target_size):
    labels = Counter(get_label(r) for r in test_records)

    total = len(test_records)
    proportions = {
        label: labels[label] / total
        for label in ["reversible", "partially_reversible", "irreversible"]
    }

    target_props = {
        "reversible": 279 / 621,
        "partially_reversible": 232 / 621,
        "irreversible": 110 / 621,
    }

    class_error = sum(
        abs(proportions[label] - target_props[label])
        for label in target_props
    )

    size_error = abs(total - target_size) / target_size

    return class_error + size_error


def make_split(records, seed):
    rng = random.Random(seed)

    target_size = round(len(records) * TEST_FRACTION_TARGET)

    scenarios = defaultdict(list)

    for record in records:
        scenarios[get_scenario(record)].append(record)

    scenario_items = list(scenarios.items())
    best = None

    for _ in range(20000):
        shuffled = scenario_items.copy()
        rng.shuffle(shuffled)

        test_records = []
        test_scenarios = []

        for scenario_id, scenario_records in shuffled:
            if len(test_records) >= target_size:
                break

            test_records = test_records + scenario_records
            test_scenarios.append(scenario_id)

        if not test_records:
            continue

        labels = set(get_label(r) for r in test_records)

        if labels != {
            "reversible",
            "partially_reversible",
            "irreversible",
        }:
            continue

        score = score_candidate(test_records, target_size)

        if best is None or score < best[0]:
            best = (
                score,
                test_records,
                test_scenarios,
            )

    if best is None:
        raise RuntimeError(
            f"Could not generate a valid three-class split for seed {seed}"
        )

    _, test_records, test_scenarios = best

    test_ids = {r["id"] for r in test_records}

    train_records = [
        r for r in records
        if r["id"] not in test_ids
    ]

    train_scenarios = sorted(
        set(get_scenario(r) for r in train_records)
    )

    test_scenarios = sorted(set(test_scenarios))

    overlap = set(train_scenarios) & set(test_scenarios)

    if overlap:
        raise RuntimeError(
            f"Scenario leakage detected for seed {seed}: {sorted(overlap)}"
        )

    return train_records, test_records, train_scenarios, test_scenarios


def main():
    print("Loading production dataset...")
    ds = load_dataset(DATASET_PATH)

    records = list(ds.iter_all())

    print(f"Total records: {len(records)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for seed in SEEDS:
        print()
        print("=" * 60)
        print(f"Creating three-class split for seed {seed}")
        print("=" * 60)

        train, test, train_scenarios, test_scenarios = make_split(
            records,
            seed,
        )

        train_labels = Counter(get_label(r) for r in train)
        test_labels = Counter(get_label(r) for r in test)

        overlap = set(train_scenarios) & set(test_scenarios)

        artifact = {
            "experiment": "E2_three_class_extension",
            "seed": seed,
            "group_key": "scenario_id",
            "test_fraction_target": TEST_FRACTION_TARGET,
            "selection_method": "randomized_scenario_disjoint_search",
            "train_scenarios": train_scenarios,
            "test_scenarios": test_scenarios,
            "train_indices": [
                records.index(r) for r in train
            ],
            "test_indices": [
                records.index(r) for r in test
            ],
            "test_label_counts": dict(test_labels),
            "train_label_counts": dict(train_labels),
            "scenario_overlap": sorted(overlap),
        }

        output_path = OUTPUT_DIR / f"split_seed_{seed}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                artifact,
                f,
                indent=2,
            )

        print(f"Train records : {len(train)}")
        print(f"Test records  : {len(test)}")
        print(f"Train scenarios: {len(train_scenarios)}")
        print(f"Test scenarios : {len(test_scenarios)}")
        print(f"Train labels   : {dict(train_labels)}")
        print(f"Test labels    : {dict(test_labels)}")
        print(f"Scenario overlap: {len(overlap)}")
        print(f"Saved: {output_path}")

    print()
    print("All three-class splits generated successfully.")


if __name__ == "__main__":
    main()
