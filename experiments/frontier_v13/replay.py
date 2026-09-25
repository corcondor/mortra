"""Selection of saved candidates only; no new outcomes or UCB feedback."""
from pathlib import Path
import numpy as np

from .protocol import CONFIG, ARMS, rng_seed, read, csv_write
from .train import load, load_csv
from .metrics import top_indices, outcomes, summarize_draws, headroom


def run(source, folds, output):
    out = Path(output)
    _, y, eligible, delta, _, _, groups = load(source)
    predictions = []
    for path in sorted(Path(folds).glob('*/row_predictions.csv')):
        predictions.extend(load_csv(path))
    assert len(predictions) == 70000
    lookup = {(r['model'], r['feature_set'], int(r['row_id'])): float(r['prediction']) for r in predictions}
    assert len(lookup) == 70000
    top_rows, pool_rows, head_rows, recovery_rows = [], [], [], []
    availability = read(Path(source)/'data/parent_availability.json')
    for parent in availability:
        pid, seed = parent['parent_id'], parent['seed']
        ix = np.array([i for i, g in enumerate(groups) if g['parent_id'] == pid])
        assert len(ix) == 140
        reward, e, d = y[ix], eligible[ix], delta[ix]
        tie = np.random.default_rng(rng_seed('ties', pid)).random(140)
        rng = np.random.default_rng(rng_seed('uniform', pid))
        subsets = np.argsort(rng.random((CONFIG['uniform_draws'], 140)), axis=1)[:, :8]
        uniform = summarize_draws(outcomes(subsets, reward, e, d))
        top_rows.append(dict(seed=seed, parent_id=pid, policy='Uniform-8', draws=len(subsets), **uniform))
        oracle = top_indices(reward, 8, tie)
        oracle_values = summarize_draws(outcomes(oracle, reward, e, d))
        top_rows.append(dict(seed=seed, parent_id=pid, policy='Oracle-top8', draws=1, **oracle_values))
        probabilities = np.array([parent['ucb_probabilities'][groups[i]['primitive']]/10 for i in ix])
        assert np.isclose(probabilities.sum(), 1) and np.count_nonzero(probabilities) >= 8
        rng = np.random.default_rng(rng_seed('ucb', pid))
        ucb_subsets = np.array([rng.choice(140, size=8, replace=False, p=probabilities) for _ in range(CONFIG['uniform_draws'])])
        policy = 'Recorded-UCB-snapshot' if parent['recorded_proposal_available'] else 'Terminal-UCB-hypothetical'
        top_rows.append(dict(seed=seed, parent_id=pid, policy=policy, draws=len(ucb_subsets),
            **summarize_draws(outcomes(ucb_subsets, reward, e, d))))
        for measure in ('mean_reward', 'best_reward', 'positive_rate', 'eligible_rate', 'beats_parent'):
            head_rows.append(dict(seed=seed, parent_id=pid, measure=measure, uniform=uniform[measure],
                oracle=oracle_values[measure], headroom=oracle_values[measure]-uniform[measure],
                objective='oracle ranks reward; it is NOT an upper bound for eligibility or max_delta_D'))
        model_scores = {}
        for kind in CONFIG['models']:
            for fs in CONFIG['feature_sets']:
                name = kind + ':' + fs
                scores = np.array([lookup[kind, fs, i] for i in ix])
                model_scores[name] = scores
                chosen = top_indices(scores, 8, tie)
                values = summarize_draws(outcomes(chosen, reward, e, d))
                top_rows.append(dict(seed=seed, parent_id=pid, policy=name, draws=1, **values))
                for measure in ('mean_reward', 'best_reward'):
                    recovery_rows.append(dict(seed=seed, parent_id=pid, policy=name, measure=measure,
                        **headroom(values[measure], uniform[measure], oracle_values[measure], CONFIG['headroom_min_denominator'])))
        for size in CONFIG['pool_sizes']:
            rng = np.random.default_rng(rng_seed('pool', pid, size))
            pool = np.arange(140)[None, :] if size == 140 else np.argsort(rng.random((CONFIG['pool_draws'], 140)), axis=1)[:, :size]
            baseline = uniform if size == 140 else summarize_draws(outcomes(pool[:, :8], reward, e, d))
            pool_rows.append(dict(seed=seed, parent_id=pid, pool_size=size, policy='Uniform-8',
                draws=CONFIG['uniform_draws'] if size == 140 else len(pool), **baseline))
            for name, scores in {**model_scores, 'Oracle-top8': reward}.items():
                order = np.lexsort((tie[pool], -scores[pool]), axis=1)[:, :8]
                selected = np.take_along_axis(pool, order, axis=1)
                values = summarize_draws(outcomes(selected, reward, e, d))
                if size == 8:
                    assert np.allclose(outcomes(selected, reward, e, d)['mean_reward'], outcomes(pool, reward, e, d)['mean_reward'])
                pool_rows.append(dict(seed=seed, parent_id=pid, pool_size=size, policy=name, draws=len(pool), **values))
        print('REPLAY', seed, pid, flush=True)
    csv_write(out/'top8_results.csv', top_rows)
    csv_write(out/'proposal_pool_size.csv', pool_rows)
    csv_write(out/'oracle_headroom.csv', head_rows)
    csv_write(out/'headroom_recovery.csv', recovery_rows)
