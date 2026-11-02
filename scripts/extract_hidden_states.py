#!/usr/bin/env python3

"""
E2 hidden-state extraction for ADNN.

Extracts Qwen 2.5 7B hidden representations for the action tokens
of every production-v1.0 record.

Representations:
    1. last_action_token
    2. mean_action_tokens

All model layers are retained, including layer 0.

The output arrays are stored outside Git and accompanied by metadata
and a manifest.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dataset",
        default="data/production/v1.0",
        help="Path to production dataset."
    )

    parser.add_argument(
        "--output",
        default="/kaggle/working/e2_qwen7b_full",
        help="Output directory."
    )

    parser.add_argument(
        "--model",
        default="Qwen/Qwen2.5-7B-Instruct",
        help="Hugging Face model ID."
    )

    parser.add_argument(
        "--dtype",
        choices=["float16", "float32"],
        default="float16"
    )

    return parser.parse_args()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    args = parse_args()

    dataset_path = Path(args.dataset)
    output_dir = Path(args.output)

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Import project dataset utilities
    # --------------------------------------------------------

    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"

    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from adnn.dataset.api import load_dataset
    from adnn.dataset.prompting import locate_action

    # --------------------------------------------------------
    # Load dataset
    # --------------------------------------------------------

    ds = load_dataset(
        str(dataset_path)
    )

    train_records = list(ds.iter_split("train"))
    test_records = list(ds.iter_split("test"))
    records = train_records + test_records

    if not records:
        raise RuntimeError("Dataset contains no records")

    record_ids = [r["id"] for r in records]

    if len(record_ids) != len(set(record_ids)):
        raise RuntimeError("Duplicate record IDs detected")

    print(
        f"Loaded {len(records)} records "
        f"(train={len(train_records)}, test={len(test_records)})"
    )

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        trust_remote_code=True
    )

    if args.dtype == "float16":
        torch_dtype = torch.float16
        storage_dtype = np.float16
    else:
        torch_dtype = torch.float32
        storage_dtype = np.float32

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch_dtype,
        device_map="auto",
        trust_remote_code=True
    )

    model.eval()

    num_layers = model.config.num_hidden_layers + 1
    hidden_size = model.config.hidden_size

    # --------------------------------------------------------
    # Allocate output arrays
    # --------------------------------------------------------

    last_action = np.empty(
        (
            len(records),
            num_layers,
            hidden_size
        ),
        dtype=storage_dtype
    )

    mean_action = np.empty(
        (
            len(records),
            num_layers,
            hidden_size
        ),
        dtype=storage_dtype
    )

    metadata = []

    # --------------------------------------------------------
    # Extract representations
    # --------------------------------------------------------

    for index, record in enumerate(records):

        bundle = ds.probe_prompt(record)

        messages = bundle.messages

        rendered = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )

        encoded = tokenizer(
            rendered,
            return_offsets_mapping=True,
            add_special_tokens=False
        )

        input_ids = torch.tensor(
            [encoded["input_ids"]],
            dtype=torch.long,
            device=model.device
        )

        offsets = encoded["offset_mapping"]

        action_start, action_end = locate_action(
            rendered,
            record["action_text"]
        )

        action_token_positions = []

        for token_index, (
            token_start,
            token_end
        ) in enumerate(offsets):

            if (
                token_start < action_end
                and token_end > action_start
            ):
                action_token_positions.append(
                    token_index
                )

        if not action_token_positions:
            raise RuntimeError(
                f"No action tokens found for "
                f"record {record['id']}"
            )

        # Verify decoded action tokens.
        decoded_action = tokenizer.decode(
            [
                encoded["input_ids"][i]
                for i in action_token_positions
            ],
            skip_special_tokens=True
        ).strip()

        expected_action = (
            record["action_text"].strip()
        )

        if decoded_action != expected_action:
            raise RuntimeError(
                "Action-token alignment mismatch for "
                f"{record['id']}: "
                f"decoded={decoded_action!r}, "
                f"expected={expected_action!r}"
            )

        with torch.no_grad():

            outputs = model(
                input_ids=input_ids,
                output_hidden_states=True
            )

        hidden_states = outputs.hidden_states

        # ----------------------------------------------------
        # Last action token
        # ----------------------------------------------------

        last_position = (
            action_token_positions[-1]
        )

        last_vectors = []

        mean_vectors = []

        for layer_hidden in hidden_states:

            last_vector = (
                layer_hidden[
                    0,
                    last_position,
                    :
                ]
                .detach()
                .cpu()
                .float()
                .numpy()
            )

            mean_vector = (
                layer_hidden[
                    0,
                    action_token_positions,
                    :
                ]
                .mean(dim=0)
                .detach()
                .cpu()
                .float()
                .numpy()
            )

            last_vectors.append(
                last_vector
            )

            mean_vectors.append(
                mean_vector
            )

        last_action[index] = np.asarray(
            last_vectors,
            dtype=storage_dtype
        )

        mean_action[index] = np.asarray(
            mean_vectors,
            dtype=storage_dtype
        )

        metadata.append({
            "id": record["id"],
            "scenario_id": record["scenario_id"],
            "pair_id": record.get("pair_id"),
            "environment": record.get(
                "environment"
            ),
            "label": record["label"],
            "action_verb": record.get(
                "action_verb"
            ),
            "action_text": record["action_text"],
            "action_token_positions": (
                action_token_positions
            ),
            "model": args.model,
            "num_layers": num_layers,
            "hidden_size": hidden_size
        })

        if (
            (index + 1) % 25 == 0
            or index == len(records) - 1
        ):
            print(
                f"Processed {index + 1}/"
                f"{len(records)}"
            )

    # --------------------------------------------------------
    # Save arrays
    # --------------------------------------------------------

    last_path = (
        output_dir /
        "last_action_token.npy"
    )

    mean_path = (
        output_dir /
        "mean_action_tokens.npy"
    )

    metadata_path = (
        output_dir /
        "metadata.jsonl"
    )

    np.save(
        last_path,
        last_action
    )

    np.save(
        mean_path,
        mean_action
    )

    with open(
        metadata_path,
        "w",
        encoding="utf-8"
    ) as f:

        for item in metadata:
            f.write(
                json.dumps(
                    item,
                    ensure_ascii=False
                ) + "\n"
            )

    # --------------------------------------------------------
    # Manifest
    # --------------------------------------------------------

    manifest = {
        "experiment": "E2",
        "model": args.model,
        "dataset": str(dataset_path),
        "records": len(records),
        "num_layers": num_layers,
        "hidden_size": hidden_size,
        "representations": [
            "last_action_token",
            "mean_action_tokens"
        ],
        "storage_dtype": args.dtype,
        "files": {
            "last_action_token.npy": {
                "sha256": sha256_file(
                    last_path
                ),
                "shape": list(
                    last_action.shape
                )
            },
            "mean_action_tokens.npy": {
                "sha256": sha256_file(
                    mean_path
                ),
                "shape": list(
                    mean_action.shape
                )
            },
            "metadata.jsonl": {
                "sha256": sha256_file(
                    metadata_path
                ),
                "records": len(metadata)
            }
        }
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
    print("E2 HIDDEN-STATE EXTRACTION COMPLETE")
    print("=" * 70)
    print("Records:", len(records))
    print("Layers:", num_layers)
    print("Hidden size:", hidden_size)
    print("Last:", last_action.shape)
    print("Mean:", mean_action.shape)
    print("Output:", output_dir)


if __name__ == "__main__":
    main()
