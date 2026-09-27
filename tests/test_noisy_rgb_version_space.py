import hashlib
import json

import numpy as np
import pytest

from experiments.noisy_rgb_discovery.core import Statistics
from experiments.noisy_rgb_discovery.sensor import RGBPort
from experiments.noisy_rgb_version_space.core import CandidateLearner, Evidence, SAME, DIFFERENT, UNRESOLVED, stability
from experiments.noisy_rgb_version_space.runtime import Budget, ResourceLimit


def toy_evidence(emit):
    statistics = {}
    for n in (8, 16, 32):
        def sample(history, rep, n=n):
            visible = hidden = 0
            for a in history:
                if a == 0:
                    hidden = 1-hidden
                elif a == 1:
                    visible = hidden
            seed = int.from_bytes(hashlib.sha256(json.dumps([history, rep, n]).encode()).digest()[:8], 'little')
            rng = np.random.default_rng(seed)
            return np.clip(40+170*visible+rng.integers(-1, 2, (n, 4, 2, 2, 3)), 0, 255).astype(np.uint8)
        statistics[n] = Statistics(RGBPort((0, 1), sample))
    return Evidence(statistics, 2., 'unit', emit)


def test_stability_requires_full_schedule_and_margin():
    assert stability([0.1]*2, 2, 8) == UNRESOLVED
    assert stability([5.]*4, 2, 16) == UNRESOLVED
    assert stability([.1, .2]*3, 2, 32) == SAME
    assert stability([5., 5.1]*3, 2, 32) == DIFFERENT
    assert stability([1., 1.9]*3, 2, 32) == UNRESOLVED
    assert stability([1., 3.]*3, 2, 32) == UNRESOLVED
    assert stability([2.]*6, 2, 32) == UNRESOLVED


def test_no_transitive_closure():
    assert stability([1.5]*6, 2, 32) == SAME
    assert stability([1.5]*6, 2, 32) == SAME
    assert stability([3.]*6, 2, 32) == DIFFERENT


def test_measured_stages_and_reuse():
    rows = []
    ev = toy_evidence(rows.append)
    first = ev.compare((), (0,), stage=8)
    assert first['result'] == UNRESOLVED
    assert ev.statistics[8].query_count == 4
    assert ev.statistics[16].query_count == 0
    final = ev.compare((), (0,))
    assert final['result'] == SAME and len(final['scores']) == 6
    for n in (8, 16, 32):
        assert ev.statistics[n].query_count == 4
    assert ev.compare((0,), ()) is final


def test_hidden_future_discovered_without_given_suffix():
    rows = []
    table = CandidateLearner(toy_evidence(rows.append), (0, 1), rows.append)
    model, status = table.learn()
    assert status.startswith('COMPLETED')
    assert len(model['reps']) == 4
    assert table.E[0] == () and len(table.E) > 1
    assert all(len(e) <= 2 for e in table.E)
    assert all(event['previous_results'].count(DIFFERENT) == 0 for event in table.events)
    assert not any(model['goal'].values())
    assert all(row['reason'] == 'all_representatives_confirmed_different_32'
               for row in rows if row['event'] == 'state_added')


class UnresolvedEvidence:
    version = 0
    def compare(self, *args, **kwargs):
        return dict(result=UNRESOLVED, id=None, stage=32)
    def cached_result(self, *args):
        return UNRESOLVED


def test_ambiguity_never_adds_state_and_queue_does_not_spin():
    rows = []
    table = CandidateLearner(UnresolvedEvidence(), (0, 1), rows.append)
    table.S = [(), (1,)]
    assert table.resolve((0,)) is None
    assert table.S == [(), (1,)]
    assert table.queue[(0,)]['candidates'] == [0, 1]
    assert len(table.queue[(0,)]['tested_probes']) == 6
    count = len(rows)
    assert table.resolve((0,)) is None
    assert len(rows) == count
    table.structure_version += 1
    table.resolve((0,))
    assert table.queue[(0,)]['retry_count'] == 1


def test_probe_order_and_lexicographic_ties():
    rows = []
    table = CandidateLearner(UnresolvedEvidence(), (0, 1), rows.append)
    table.S = [(), (1,)]
    table.resolve((0,))
    assert [row['selected'] for row in rows if row['event'] == 'active_probe'] == [
        (0,), (1,), (0, 0), (0, 1), (1, 0), (1, 1)]


def test_limits_not_policy_failure():
    budget = Budget(max_actions=1, max_exposures=8, max_wall_seconds=100)
    budget.reserve((0,), 8)
    with pytest.raises(ResourceLimit):
        budget.reserve((0,), 8)
    assert budget.actions == 1 and budget.exposures == 8


def test_core_has_no_world_or_goal_access():
    from experiments.noisy_rgb_version_space import core
    assert not hasattr(core, 'truth')
    assert not hasattr(core, 'make_game')
    assert not hasattr(core, 'environment_class')


def test_new_state_has_32_stage_evidence_against_every_representative():
    rows = []
    table = CandidateLearner(toy_evidence(rows.append), (0, 1), rows.append)
    table.learn()
    certificates = {r['id']: r for r in rows if r['event'] == 'comparison'}
    for row in rows:
        if row['event'] != 'state_added':
            continue
        assert len(row['evidence']) == row['state']
        assert {e['q'] for e in row['evidence']} == set(range(row['state']))
        for e in row['evidence']:
            c = certificates[e['certificate']]
            assert c['stage'] == 32 and c['result'] == DIFFERENT and len(c['scores']) == 6


def test_frozen_readout_does_not_modify_prototypes_or_certificates():
    from experiments.noisy_rgb_version_space.evaluate import prototypes_for, frozen_candidates
    rows = []
    evidence = toy_evidence(rows.append)
    table = CandidateLearner(evidence, (0, 1), rows.append)
    model, _ = table.learn()
    proto = prototypes_for(model, table.E, evidence.statistics, 'V')
    before = (evidence.version, tuple(s.query_count for s in evidence.statistics.values()), list(table.E))
    other = toy_evidence(lambda r: None)
    candidates = frozen_candidates((0, 1), table.E, proto, other.statistics, evidence.threshold, 'V')
    assert len(candidates) == 1
    assert before == (evidence.version, tuple(s.query_count for s in evidence.statistics.values()), list(table.E))


def test_probe_selection_uses_only_cached_evidence():
    rows = []
    evidence = toy_evidence(rows.append)
    table = CandidateLearner(evidence, (0, 1), rows.append)
    table.S = [(), (0,)]
    assert table.probe_score([0, 1], (1,)) == 2.
    assert not rows
    evidence.compare((), (0,), (1,))
    count = len(rows)
    assert table.probe_score([0, 1], (1,)) == 1.
    assert len(rows) == count
