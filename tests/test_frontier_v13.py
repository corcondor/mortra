import ast
import copy
import inspect
from pathlib import Path

import numpy as np
import pytest

from experiments.frontier_v13 import features
from experiments.frontier_v13.dataset import label_of, parent_inputs
from experiments.frontier_v13.metrics import headroom, outcomes, ranking, top_indices, top_weights
from experiments.frontier_v13.protocol import ARMS, CONFIG, digest
from experiments.frontier_v13.train import model, split


def genome():
    return dict(version='finite-program-v1.1', domains=[12, 12, 2], actions=4,
        initial=[1, 1, 0], walls=[[0, 0]], rendering={'position_variables': [0, 1]},
        rules=[dict(action=0, guard=[], assign=[dict(var=0, op='add', value=1)]),
               dict(action=1, guard=[dict(var=0, op='eq', value=2)], assign=[dict(var=2, op='set', value=1)])])


def decision():
    return dict(context={'reachable_states': 128, 'B80': None}, counts={a: 0 for a in ARMS},
                mean_rewards={a: None for a in ARMS}, probabilities={a: 1/14 for a in ARMS})


def test_static_extractor_no_execution_or_file_access(monkeypatch):
    g = genome(); child = copy.deepcopy(g); child['domains'][2] = 3
    pm = {n: None for n in features.PARENT_METRICS}
    def forbidden(*a, **kw):
        raise AssertionError('forbidden evaluator/filesystem call')
    monkeypatch.setattr('builtins.open', forbidden)
    monkeypatch.setattr(Path, 'open', forbidden)
    before = digest(g)
    x = features.extract(g, child, 'domain', pm, decision(), [])
    assert x == features.extract(g, child, 'domain', pm, decision(), [])
    assert digest(g) == before
    assert x['edit_domain_sizes_changed'] == 1 and x['edit_domain_change_magnitude'] == 1
    assert not any(k in name for name in x for k in ('seed', 'hash', 'replicate', 'generation', 'filename'))


def test_static_module_dependency_allowlist():
    tree = ast.parse(inspect.getsource(features))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)
    assert set(imports) <= {'collections', 'difflib', 'math', 'statistics', 'protocol'}
    assert not any(s in inspect.getsource(features) for s in ('Engine(', 'oracle(', 'StructuralLearner', 'solve_fixed_field', 'evaluation['))


def test_no_candidate_evaluation_api():
    assert list(inspect.signature(features.extract).parameters) == [
        'parent_genome', 'candidate_genome', 'primitive', 'parent_metrics', 'decision', 'past_events']
    with pytest.raises(AssertionError):
        features.extract(genome(), genome(), 'initial', {'candidate_reward': 1}, decision(), [])


def test_feature_sets_do_not_expose_identifiers():
    x = features.extract(genome(), genome(), 'initial', {k: None for k in features.PARENT_METRICS}, decision(), [])
    for fs in CONFIG['feature_sets']:
        names = features.columns(x, fs)
        assert names and 'row_id' not in names
    assert set(features.columns(x, 'M0')) == {'op_'+a for a in ARMS}
    assert not any(n.startswith('parent_') for n in features.columns(x, 'M1'))
    assert all(not n.startswith('history_') for n in features.columns(x, 'M3'))


def test_static_dependency_depth_cycles():
    rules = [dict(action=0, guard=[dict(var=i, op='eq', value=0)],
                  assign=[dict(var=i+1, op='set', value=0)]) for i in range(3)]
    rw, edges, blocks, cycles, depth = features.dependency(rules)
    assert edges == {(0, 1), (1, 2)} and cycles == 0 and depth == 3
    rules.append(dict(action=0, guard=[dict(var=3, op='eq', value=0)], assign=[dict(var=0, op='set', value=0)]))
    assert features.dependency(rules)[2:] == (1, 1, 1)


def test_rendering_is_not_feature():
    a, b = genome(), genome(); b['rendering'] = {'secret': 'unavailable'}
    assert features.program(a) == features.program(b)
    assert all(v == 0 for v in features.edit(a, b).values())


def test_absent_genome_availability_not_outcome():
    x = features.extract(genome(), None, 'domain', {k: None for k in features.PARENT_METRICS}, decision(), [])
    assert x['edit_genome_available'] == 0 and x['edit_ast_nodes_changed'] == 0


def test_first_occurrence_history_no_future():
    h = digest(genome())
    rec = dict(game_hash=h, D=1., B50=None, B80=None, B90=None, final_success=.5,
               oracle={'reachable_states': 128}, full_info={'success_rate': 1}, learning=[])
    ev = dict(frontier=[rec]*11, mutation_history=[dict(generation=g, candidate=i,
        parent_hash=h, decision=decision(), mutation='domain', reward=999,
        outcome={'valid': True, 'eligible': True}) for g in range(1, 11) for i in range(8)])
    parent = dict(game_hash=h, generations=list(range(11)), D_parent=1.)
    metrics, dec, past, generation, actual = parent_inputs(parent, ev)
    assert past == [] and generation == 0 and actual


def test_label_validates_archive_exact_reward_and_hash():
    g = genome()
    ev = dict(game_hash=digest(g), valid=True, full_info={'success_rate': 1}, final_success=.9, D=2.)
    r = dict(mutation_attempts=1, parent_unchanged=True, candidate_hash=digest(g),
        eligible=True, valid=True, D_candidate=2., D_parent=3., reward=-1., delta_D=-1., reward_category='eligible_easier_negative')
    assert label_of(r, ev, g)['reward'] == -1
    with pytest.raises(AssertionError):
        label_of({**r, 'reward': 0}, ev, g)


def test_loso_all_parent_rows_stay_together():
    groups = [dict(seed=str(s), parent_hash=str(s)+'p') for s in (2101, 2202) for _ in range(140)]
    train, test = split(groups, 2101)
    assert train.sum() == test.sum() == 140 and not np.any(train & test)
    with pytest.raises(AssertionError):
        split([dict(seed='2101', parent_hash='same'), dict(seed='2202', parent_hash='same')], 2101)


def test_normalizer_train_only():
    x = np.array([[0.], [2.], [1e12]])
    estimator = model('ridge').fit(x[:2], [0., 1.])
    estimator.predict(x[2:])
    assert estimator[0].mean_[0] == 1 and estimator[0].scale_[0] == 1


def test_ranking_fixture_and_ties():
    y = np.arange(10, dtype=float)
    perfect = ranking(y, y, y > 4)
    assert perfect['spearman'] == pytest.approx(1)
    assert perfect['pairwise_accuracy'] == 1 and perfect['top1_regret'] == 0
    assert perfect['top5_recall'] == 1
    tied = ranking(y, np.zeros(10), y > 4)
    assert tied['spearman'] is None and tied['pairwise_accuracy'] == .5
    assert tied['top1_regret'] == pytest.approx(4.5)
    assert tied['top5_recall'] == pytest.approx(.5)
    assert np.isclose(top_weights(np.zeros(140), 8).sum(), 8)


def test_top8_and_headroom_fixture():
    y = np.arange(-10, 10, dtype=float)
    ix = top_indices(y, 8, np.arange(20))
    values = outcomes(ix, y, y >= 0, y)
    assert len(ix) == len(set(ix)) == 8
    assert values['mean_reward'][0] == 5.5 and values['best_reward'][0] == 9
    assert values['beats_parent'][0] == 1
    assert headroom(3., 1., 5.)['recovery'] == .5
    assert headroom(1., 1., 1.)['recovery'] is None


def test_trainer_has_no_holdout_artifact_or_world_access():
    from experiments.frontier_v13 import train
    source = inspect.getsource(train)
    assert 'game_frontier' not in source and 'api(' not in source and 'archive(' not in source
    for forbidden in ('genome.json', 'holdout_tasks', 'Engine(', 'oracle(', 'fixed_field'):
        assert forbidden not in source


def test_model_configuration_frozen():
    tree = model('tree')[-1]
    assert tree.max_depth == 4 and tree.max_iter == 200 and not tree.early_stopping
    assert model('ridge')[-1].alpha == 1.
