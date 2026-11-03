# ============================================================
# RQ1 Qwen — 10-record hidden-state reproducibility test
# ============================================================

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime

import numpy as np
import torch

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

BASE_DIR = Path("/kaggle/working/ADNN_RQ1_Qwen_v2")
HIDDEN_DIR = BASE_DIR / "hidden_states"
VALIDATION_DIR = BASE_DIR / "validation"

VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

LAST_PATH = HIDDEN_DIR / "last_action_token.npy"
MEAN_PATH = HIDDEN_DIR / "mean_action_tokens.npy"

# ------------------------------------------------------------
# Load saved representations
# ------------------------------------------------------------

saved_last = np.load(LAST_PATH, mmap_mode="r")
saved_mean = np.load(MEAN_PATH, mmap_mode="r")

# ------------------------------------------------------------
# Deterministic selection of 10 records
# Spread across the full extraction rather than taking only
# adjacent examples.
# ------------------------------------------------------------

n_total = len(extraction_index)

selected_rows = np.linspace(
    0,
    n_total - 1,
    num=10,
    dtype=int
).tolist()

selected_entries = [
    extraction_index[i]
    for i in selected_rows
]

# Record lookup
record_by_id = {
    r["id"]: r
    for r in records
}

# ------------------------------------------------------------
# Reproduce the exact prompt construction used by extraction
# ------------------------------------------------------------

def build_formatted_prompt(record):
    prompt = build_prompt(record)

    formatted_prompt = tokenizer.apply_chat_template(
        [
            {
                "role": "user",
                "content": prompt
            }
        ],
        tokenize=False,
        add_generation_prompt=True,
    )

    return prompt, formatted_prompt


def sha256_text(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


# ------------------------------------------------------------
# Run reproducibility check
# ------------------------------------------------------------

results = []

max_last_diff = 0.0
max_mean_diff = 0.0

all_last_match = True
all_mean_match = True
all_prompt_hashes_match = True

# Use the same model device setup already present in notebook.
model_device = next(model.parameters()).device

model.eval()

for entry in selected_entries:

    row_index = int(entry["row_index"])
    record_id = entry["record_id"]

    record = record_by_id[record_id]

    # --------------------------------------------------------
    # Rebuild prompt
    # --------------------------------------------------------

    prompt, formatted_prompt = build_formatted_prompt(record)

    current_prompt_hash = sha256_text(formatted_prompt)

    saved_prompt_hash = entry["prompt_hash"]

    prompt_match = (
        current_prompt_hash == saved_prompt_hash
    )

    all_prompt_hashes_match &= prompt_match

    # --------------------------------------------------------
    # Tokenize exactly as original extraction
    # --------------------------------------------------------

    inputs = tokenizer(
        formatted_prompt,
        return_tensors="pt",
        add_special_tokens=False,
    )

    inputs = {
        k: v.to(model_device)
        for k, v in inputs.items()
    }

    # --------------------------------------------------------
    # Forward pass
    # --------------------------------------------------------

    with torch.no_grad():
        outputs = model(
            **inputs,
            output_hidden_states=True,
            use_cache=False,
        )

    hidden_states = outputs.hidden_states

    # --------------------------------------------------------
    # Verify tokenization matches saved extraction metadata
    # --------------------------------------------------------

    sequence_length = int(inputs["input_ids"].shape[1])

    saved_sequence_length = int(
        entry["sequence_length"]
    )

    sequence_match = (
        sequence_length == saved_sequence_length
    )

    # --------------------------------------------------------
    # Action span from saved extraction metadata
    # --------------------------------------------------------

    action_start = int(entry["action_start"])
    action_end = int(entry["action_end"])

    action_token_count = int(
        entry["action_token_count"]
    )

    actual_action_token_count = (
        action_end - action_start
    )

    action_count_match = (
        actual_action_token_count == action_token_count
    )

    # --------------------------------------------------------
    # Extract representations using same convention
    # --------------------------------------------------------

    # Last action token = action_end - 1
    last_token_position = action_end - 1

    layer_last_vectors = []
    layer_mean_vectors = []

    for layer_hidden in hidden_states:

        # Shape:
        # [batch, sequence, hidden]
        h = layer_hidden[0]

        last_vec = h[last_token_position]
        mean_vec = h[action_start:action_end].mean(
            dim=0
        )

        layer_last_vectors.append(
            last_vec.detach().float().cpu().numpy()
        )

        layer_mean_vectors.append(
            mean_vec.detach().float().cpu().numpy()
        )

    reproduced_last = np.stack(
        layer_last_vectors,
        axis=0
    )

    reproduced_mean = np.stack(
        layer_mean_vectors,
        axis=0
    )

    # --------------------------------------------------------
    # Compare with saved vectors
    # --------------------------------------------------------

    saved_last_row = np.asarray(
        saved_last[row_index],
        dtype=np.float32
    )

    saved_mean_row = np.asarray(
        saved_mean[row_index],
        dtype=np.float32
    )

    last_abs_diff = float(
        np.max(
            np.abs(
                reproduced_last - saved_last_row
            )
        )
    )

    mean_abs_diff = float(
        np.max(
            np.abs(
                reproduced_mean - saved_mean_row
            )
        )
    )

    # Float16 storage means tiny numerical differences are
    # expected after recomputation.
    tolerance = 1e-3

    last_match = last_abs_diff <= tolerance
    mean_match = mean_abs_diff <= tolerance

    all_last_match &= last_match
    all_mean_match &= mean_match

    max_last_diff = max(
        max_last_diff,
        last_abs_diff
    )

    max_mean_diff = max(
        max_mean_diff,
        mean_abs_diff
    )

    results.append({
        "row_index": row_index,
        "record_id": record_id,
        "scenario_id": entry["scenario_id"],
        "split": entry["split"],
        "action_verb": entry["action_verb"],

        "saved_prompt_hash": saved_prompt_hash,
        "reproduced_prompt_hash": current_prompt_hash,
        "prompt_hash_match": prompt_match,

        "saved_sequence_length": saved_sequence_length,
        "reproduced_sequence_length": sequence_length,
        "sequence_length_match": sequence_match,

        "action_start": action_start,
        "action_end": action_end,
        "action_token_count": action_token_count,
        "actual_action_token_count": actual_action_token_count,
        "action_count_match": action_count_match,

        "last_action_token_max_abs_diff": last_abs_diff,
        "mean_action_tokens_max_abs_diff": mean_abs_diff,

        "last_action_token_match": last_match,
        "mean_action_tokens_match": mean_match,

        "tolerance": tolerance,
    })

# ------------------------------------------------------------
# Overall result
# ------------------------------------------------------------

overall_pass = (
    all_prompt_hashes_match
    and all(
        r["sequence_length_match"]
        for r in results
    )
    and all(
        r["action_count_match"]
        for r in results
    )
    and all_last_match
    and all_mean_match
)

report = {
    "experiment": "ADNN_RQ1_Qwen_v2_reproducibility_test",

    "model": "Qwen/Qwen2.5-7B-Instruct",

    "dataset_version": "adnn-dataset-2.0",

    "representation": [
        "last_action_token",
        "mean_action_tokens"
    ],

    "num_records_tested": len(results),

    "selected_rows": selected_rows,

    "tolerance": 1e-3,

    "overall_pass": overall_pass,

    "all_prompt_hashes_match": all_prompt_hashes_match,

    "all_last_action_token_vectors_match": all_last_match,

    "all_mean_action_token_vectors_match": all_mean_match,

    "maximum_last_action_token_abs_difference": max_last_diff,

    "maximum_mean_action_tokens_abs_difference": max_mean_diff,

    "records": results,

    "timestamp_utc": datetime.utcnow().isoformat() + "Z",

    "note": (
        "Re-extraction uses the same prompt construction, "
        "chat-template rendering, tokenization, action span, "
        "and hidden-state representation convention used by "
        "the saved Qwen extraction."
    ),
}

# ------------------------------------------------------------
# Save JSON report
# ------------------------------------------------------------

json_path = (
    VALIDATION_DIR /
    "qwen_v2_reproducibility_test.json"
)

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(
        report,
        f,
        indent=2
    )

# ------------------------------------------------------------
# Save this test code itself
# ------------------------------------------------------------

script_path = (
    VALIDATION_DIR /
    "qwen_v2_reproducibility_test.py"
)

# Get the current cell source from IPython history.
try:
    cell_source = In[-1]
except Exception:
    cell_source = "# Reproducibility test source was executed from notebook cell."

with open(script_path, "w", encoding="utf-8") as f:
    f.write(cell_source)

# ------------------------------------------------------------
# Print concise result
# ------------------------------------------------------------

print("=" * 70)
print("QWEN RQ1 — 10-RECORD REPRODUCIBILITY TEST")
print("=" * 70)

print(f"Records tested: {len(results)}")
print(f"Prompt hashes match: {all_prompt_hashes_match}")
print(f"Last-action vectors match: {all_last_match}")
print(f"Mean-action vectors match: {all_mean_match}")

print(
    f"Maximum last-token absolute difference: "
    f"{max_last_diff:.8f}"
)

print(
    f"Maximum mean-token absolute difference: "
    f"{max_mean_diff:.8f}"
)

print(f"\nOVERALL PASS: {overall_pass}")

print("\nSaved:")
print(json_path)
print(script_path)