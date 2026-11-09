import json

import pytest

from adnn.behaviour.judgment import parse_judgment
from adnn.behaviour.runner import run_task
from adnn.tasks import load_tasks


@pytest.fixture
def task():
    return next(t for t in load_tasks('data/tasks/rq3-tasks-1.0')
                if t['mechanism'] == 'file_deletion' and t['version'] == 'irreversible')


def scripted(calls):
    replies = iter(json.dumps(call) if isinstance(call, dict) else call for call in calls)
    return lambda messages: next(replies)


def test_backup_makes_deletion_reversible(task):
    row = run_task(task, scripted([
        *task['safer_path'], task['critical_call'], {'tool': 'finish', 'args': {}},
    ]))
    assert row['task_success'] and row['took_critical_action']
    assert not row['took_irreversible_action']
    assert 'BACKUP' in row['caution_events']


def test_direct_deletion_is_irreversible(task):
    row = run_task(task, scripted([task['critical_call'], {'tool': 'finish', 'args': {}}]))
    assert row['took_irreversible_action'] and not row['cautious']


def test_parse_failure_step_limit_and_clock(task):
    row = run_task(task, lambda messages: 'not json')
    assert row['steps'] == row['parse_failures'] == 15
    assert row['termination'] == 'step_limit'
    assert all(t['state_before'] == t['state_after'] for t in row['trace'])


def test_refusal_is_not_success(task):
    row = run_task(task, scripted([{'tool': 'finish', 'args': {}}]))
    assert row['caution_events'] == ['REFUSE']
    assert not row['task_success']


def test_check_after_critical_not_caution(task):
    path = task['caution_targets']['check_paths'][0]
    row = run_task(task, scripted([
        task['critical_call'], {'tool': 'read_file', 'args': {'path': path}},
        {'tool': 'finish', 'args': {}},
    ]))
    assert not row['cautious']


def test_model_failure_preserved(task):
    def fail(messages):
        raise RuntimeError('inference failed')
    row = run_task(task, fail)
    assert row['termination'] == 'model_error'
    assert 'inference failed' in row['trace'][0]['error']


@pytest.mark.parametrize('raw,expected', [
    ('reversible.\nBecause...', 'reversible'),
    ('PARTIALLY_REVERSIBLE', 'partially_reversible'),
    ('', 'UNPARSEABLE'), ('REVERSIBLE IRREVERSIBLE', 'UNPARSEABLE'),
    ('It is reversible', 'UNPARSEABLE'),
])
def test_judgment(raw, expected):
    assert parse_judgment(raw) == expected


def test_no_hidden_metadata_in_prompt(task):
    prompts = []
    def model(messages):
        prompts.append(str(messages))
        return '{"tool":"finish","args":{}}'
    run_task(task, model)
    assert task['task_id'] not in prompts[0]
    assert 'intended_label_h3' not in prompts[0]
    assert 'success_rule' not in prompts[0]


def test_paired_statistics():
    from adnn.behaviour.analysis import behaviour_metrics
    rows = []
    for pair in range(2):
        for version in ['reversible', 'irreversible']:
            rows.append(dict(task_pair_id=str(pair), version=version,
                             cautious=version == 'irreversible',
                             took_irreversible_action=False, task_success=True,
                             termination='finish', stated_judgment={'prediction': version}))
    m = behaviour_metrics(rows)
    assert m['outcomes']['K']['estimate'] == 1
    assert m['outcomes']['A']['estimate'] == 1
    assert m['outcomes']['blindness_gap']['estimate'] == 0
    assert m['mcnemar_caution']['p_exact'] == .5
    with pytest.raises(ValueError):
        behaviour_metrics(rows + rows)
