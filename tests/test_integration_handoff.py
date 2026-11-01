"""Consumer integration smoke tests for Members 2 and 3 (docs/15_TEAM_HANDOFF.md).

The pilot is regenerated FROM SCRATCH with the documented CLI into a temporary
directory, then used exactly as a consumer would: only the public modules
``adnn.dataset.api``, ``adnn.dataset.prompting`` and ``adnn.sandbox`` are
imported here (checked by ``test_consumers_import_only_public_modules``).
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from adnn.dataset.api import (
    DatasetIntegrityError,
    LoadedDataset,
    action_call,
    load_dataset,
    sandbox_from_record,
)
from adnn.dataset.prompting import (
    STATED_ANSWER_LABELS,
    AgentTurn,
    PromptInputs,
    build_agent_messages,
    locate_action,
)
from adnn.sandbox import ToolCall, canonical_hash

SEED = 20261030
# Content checksums documented in docs/13 and docs/15 (source commit 6b6a3e4).
EXPECTED_SHA256 = {
    "pilot_v0.1.jsonl": "f66b98baac43faf1ece408cc22e645faf22aace13ad6aac86f1f2c83f1d3fc53",
    "pilot_split.json": "100d2084dea298860ebe4f4bea27aadca9c4a81a04e8b9e3a45429abc36b96c1",
    "tool_sets.json": "dce114a28b26dfc797db81bff3687a7f2c301fde9556330c0be572660e5d3f29",
}
ALLOWED_ADNN_IMPORTS = {"adnn.dataset.api", "adnn.dataset.prompting", "adnn.sandbox"}

# Two representative chat formats (ChatML-like and Llama-3-like). Real templates
# must be checked with the actual tokenizer by Member 2; these only exercise the
# boundary logic on a full rendering with special tokens around the action.
CHAT_FORMATS = {
    "chatml": ("<|im_start|>{role}\n{content}<|im_end|>\n", ""),
    "llama3": (
        "<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>",
        "<|begin_of_text|>",
    ),
}


@pytest.fixture(scope="module")
def pilot_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("pilot_from_scratch")
    subprocess.run(
        [sys.executable, "-m", "adnn.dataset.pilot", "--out", str(out), "--seed", str(SEED)],
        check=True,
        capture_output=True,
    )
    return out


@pytest.fixture(scope="module")
def ds(pilot_dir: Path) -> LoadedDataset:
    return load_dataset(pilot_dir)


# -- regeneration --------------------------------------------------------------------
def test_regeneration_reproduces_documented_content_checksums(pilot_dir: Path) -> None:
    import hashlib

    for name, expected in EXPECTED_SHA256.items():
        assert hashlib.sha256((pilot_dir / name).read_bytes()).hexdigest() == expected, name


def test_loader_verifies_checksums_and_rejects_tampering(pilot_dir: Path, tmp_path: Path) -> None:
    for f in pilot_dir.iterdir():
        shutil.copy(f, tmp_path / f.name)
    assert len(load_dataset(tmp_path)) == 210
    with (tmp_path / "pilot_v0.1.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("\n")
    with pytest.raises(DatasetIntegrityError, match="dataset"):
        load_dataset(tmp_path)


def test_consumers_import_only_public_modules() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    used = {
        n.module
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("adnn")
    }
    assert used <= ALLOWED_ADNN_IMPORTS, used
    api_src = (Path(load_dataset.__code__.co_filename)).read_text(encoding="utf-8")
    for internal in ("adnn.dataset.pilot", "adnn.dataset.validation"):
        assert internal not in api_src


# -- Member 2 (RQ1) ----------------------------------------------------------------------
def test_member2_loads_examples_and_split_by_family(ds: LoadedDataset) -> None:
    train, test = list(ds.iter_split("train")), list(ds.iter_split("test"))
    assert (len(train), len(test), len(ds)) == (165, 45, 210)
    assert {r["template_id"] for r in train}.isdisjoint({r["template_id"] for r in test})
    assert len(ds.minimal_pairs()) == 70


@pytest.mark.parametrize("fmt", CHAT_FORMATS)
def test_member2_action_boundary_in_rendered_chat(ds: LoadedDataset, fmt: str) -> None:
    turn, prefix = CHAT_FORMATS[fmt]
    for r in ds.records:
        bundle = ds.probe_prompt(r)  # hash-checked against the dataset
        msgs = bundle.messages
        assert msgs[-1] == {"role": "assistant", "content": r["action_text"]}
        rendered = prefix + "".join(turn.format(**m) for m in msgs)
        start, end = locate_action(rendered, r["action_text"])
        assert rendered[start:end] == r["action_text"]
        # The span ends at the last action character, before any end-of-turn token.
        assert rendered[end:].startswith(("<|im_end|>", "<|eot_id|>"))


def test_member2_labels_are_separate_evaluation_metadata(ds: LoadedDataset) -> None:
    provisional = 0
    for r in ds.records:
        meta = ds.eval_metadata(r)
        assert meta.label == meta.label_at(3) == r["label"]
        assert set(meta.labels_by_horizon) == {"1", "2", "3"}
        assert meta.split in ("train", "test") and meta.template_id == r["template_id"]
        provisional += meta.label_provisional
        assert meta.label_provisional == bool(meta.provisional_reasons)
    assert provisional == 83
    changed = [
        r for r in ds.records if len(set(ds.eval_metadata(r).labels_by_horizon.values())) > 1
    ]
    assert len(changed) == 10


# -- leakage (both members) ----------------------------------------------------------------
METADATA_TOKENS = (
    "is_definitive", "budget_exhausted", "undetermined", "complete_through", "nodes_expanded",
    "witness", "oracle", "provisional", "label", "pivot", "scenario", "template", "family",
    "pair_id", "split", "restore_depth", "sbx-", "ground truth", "gold",
)  # fmt: skip
SPLIT_WORDS = re.compile(r"\b(train|test)\b", re.IGNORECASE)
LABEL_WORDS = ("reversible", "irreversible", "partially_reversible", "partially reversible")


def test_no_metadata_in_any_model_visible_text(ds: LoadedDataset) -> None:
    for r in ds.records:
        probe = "\n".join(m["content"] for m in ds.probe_prompt(r).messages)
        stated = "\n".join(m["content"] for m in ds.stated_prompt(r).messages)
        ids = (r["id"], r["scenario_id"], r["template_id"], r["pair_id"] or "\0")
        for text, kind in ((probe, "probe"), (stated, "stated")):
            low = text.lower()
            assert not [t for t in METADATA_TOKENS if t in low], (r["id"], kind)
            assert not [i for i in ids if i in text], (r["id"], kind)
            assert not SPLIT_WORDS.search(text), (r["id"], kind)
        assert not [w for w in LABEL_WORDS if w in probe.lower()], r["id"]


def test_pair_prompts_differ_only_in_state_text(ds: LoadedDataset) -> None:
    """The label cannot be encoded anywhere except through the world state itself."""
    for a, b in ds.minimal_pairs():
        assert ds.eval_metadata(a).label != ds.eval_metadata(b).label
        for build in (ds.probe_prompt, ds.stated_prompt):
            ta = json.dumps(build(a).messages).replace(json.dumps(a["state_text"])[1:-1], "<S>")
            tb = json.dumps(build(b).messages).replace(json.dumps(b["state_text"])[1:-1], "<S>")
            assert ta == tb, a["pair_id"]


# -- Member 3 (RQ2 / RQ3) --------------------------------------------------------------------
def test_member3_stated_prompts(ds: LoadedDataset) -> None:
    for r in ds.iter_split("test"):
        for h in (1, 2, 3):
            user = ds.stated_prompt(r, horizon=h).messages[1]["content"]
            assert f"at most {h} further tool calls" in user
            assert r["action_text"] in user and all(x in user for x in STATED_ANSWER_LABELS)


def test_member3_initialises_and_replays_sandbox(ds: LoadedDataset) -> None:
    for r in ds.records:
        s1, s2 = sandbox_from_record(r), sandbox_from_record(r)
        assert s1.get_action_history() == ()
        res1, res2 = s1.execute(action_call(r)), s2.execute(action_call(r))
        assert res1.ok and res1 == res2
        assert canonical_hash(s1.state) == canonical_hash(s2.state)  # deterministic replay
        assert s1.get_action_history()[0].tool == r["action_verb"]


def test_member3_agent_prompt_matches_probe_context_for_kv_records(ds: LoadedDataset) -> None:
    """A live sandbox renders `kv`; for kv records step 0 equals the probe context."""
    kv = [r for r in ds.records if r["render_style"] == "kv"]
    other = [r for r in ds.records if r["render_style"] != "kv"]
    assert kv and other
    for r in kv:
        sb = sandbox_from_record(r)
        live = build_agent_messages(
            PromptInputs.from_sandbox(r["task_text"], sb.get_observation(), sb.tool_specs())
        )
        assert live.messages == ds.probe_prompt(r).messages[:-1]
    r = other[0]  # documented caveat (docs/15 §6): other styles differ from the live view
    sb = sandbox_from_record(r)
    assert sb.get_observation() != r["state_text"]


def test_member3_multi_step_history(ds: LoadedDataset) -> None:
    r = ds.by_id("sbx-f01_delete_bin-00-pa")
    sb = sandbox_from_record(r)
    inputs = PromptInputs.from_sandbox(r["task_text"], sb.get_observation(), sb.tool_specs())
    history: list[AgentTurn] = []
    for call in (action_call(r), ToolCall("restore_file", {"entry_id": "bin-0001"})):
        result = sb.execute(call)
        assert result.ok
        history.append(AgentTurn(json.dumps(call.to_dict()), result.message, sb.get_observation()))
    msgs = build_agent_messages(inputs, history).messages
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user", "assistant", "user"]
    assert canonical_hash(sb.state) == canonical_hash(sandbox_from_record(r).state)


def test_prompt_drift_is_detected(ds: LoadedDataset) -> None:
    r = dict(ds.records[0])
    r["meta"] = {**r["meta"], "probe_prompt_sha256": "0" * 64}
    with pytest.raises(DatasetIntegrityError, match="regenerate"):
        ds.probe_prompt(r)
