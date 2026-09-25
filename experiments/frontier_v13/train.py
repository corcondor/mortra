"""LOSO training from isolated numeric features, never from genome evaluations."""
import csv
from pathlib import Path
import time

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .protocol import CONFIG, SEEDS, read, write, csv_write, rng_seed
from .features import columns
from .metrics import ranking


def load_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def model(kind):
    estimator = Ridge(**CONFIG['models']['ridge']) if kind == 'ridge' else HistGradientBoostingRegressor(**CONFIG['models']['tree'])
    return make_pipeline(StandardScaler(), estimator)


def split(groups, seed):
    test = np.array([int(g['seed']) == seed for g in groups])
    assert np.any(test) and np.any(~test)
    assert not ({g['parent_hash'] for g, t in zip(groups, test) if t} &
                {g['parent_hash'] for g, t in zip(groups, test) if not t})
    return ~test, test


def numeric(x):
    return np.nan if x in ('', 'None') else float(x)


def load(source):
    source = Path(source)
    features = load_csv(source/'data/features.csv')
    labels = load_csv(source/'data/labels.csv')
    groups = load_csv(source/'data/fold_assignments.csv')
    assert [r['row_id'] for r in features] == [r['row_id'] for r in labels] == [r['row_id'] for r in groups]
    names = [n for n in features[0] if n != 'row_id']
    assert names == read(source/'feature_schema.json')['columns']
    X = np.array([[float(r[n]) for n in names] for r in features])
    y = np.array([float(r['reward']) for r in labels])
    eligible = np.array([r['eligible'] == 'True' for r in labels])
    delta = np.array([numeric(r['delta_D']) for r in labels])
    return X, y, eligible, delta, names, labels, groups


def run_fold(source, output, held_out):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    assert held_out in SEEDS and read(Path(source)/'config.json') == CONFIG
    X, y, eligible, delta, names, labels, groups = load(source)
    train, test = split(groups, held_out)
    indices = np.flatnonzero(test)
    prediction_rows, parent_rows, importance_rows, secondary_rows, compute_rows = [], [], [], [], []
    target_values = dict(reward=y, eligibility=eligible.astype(float), delta_D=delta, positive=(y > 0).astype(float))
    feature_map = {}
    for kind in CONFIG['models']:
        for feature_set in CONFIG['feature_sets']:
            selected = columns(names, feature_set)
            cols = [names.index(n) for n in selected]
            feature_map[feature_set] = selected
            xx = X[:, cols]
            predictions = {}
            for target, yy in target_values.items():
                mask = train & np.isfinite(yy)
                assert not np.any(mask & test)
                start = time.process_time()
                fitted = model(kind).fit(xx[mask], yy[mask])
                # This directly verifies the fitted normalizer's provenance.
                assert np.allclose(fitted[0].mean_, np.mean(xx[mask], axis=0), rtol=0, atol=1e-12)
                pred = fitted.predict(xx)
                assert np.all(np.isfinite(pred))
                predictions[target] = pred
                compute_rows.append(dict(seed=held_out, model=kind, feature_set=feature_set,
                    target=target, train_rows=int(mask.sum()), test_rows=int(test.sum()),
                    features=len(cols), CPU_seconds=time.process_time()-start))
                if target != 'reward':
                    for i in indices:
                        secondary_rows.append(dict(row_id=i, seed=held_out, parent_id=groups[i]['parent_id'],
                            model=kind, feature_set=feature_set, target=target,
                            truth=float(yy[i]) if np.isfinite(yy[i]) else None, prediction=float(pred[i])))
                    continue
                for part, part_mask in (('train', train), ('test', test)):
                    for parent in sorted({g['parent_id'] for g, take in zip(groups, part_mask) if take}):
                        ix = np.array([i for i, g in enumerate(groups) if g['parent_id'] == parent])
                        parent_rows.append(dict(held_out_seed=held_out, seed=int(groups[ix[0]]['seed']),
                            parent_id=parent, split=part, model=kind, feature_set=feature_set,
                            **ranking(y[ix], pred[ix], eligible[ix])))
                base_error = float(np.mean((pred[test]-y[test])**2))
                for group_name, prefix in (('primitive', 'op_'), ('parent', 'parent_'), ('edit', 'edit_'), ('ucb', 'ucb_'), ('history', 'history_')):
                    pos = [j for j, n in enumerate(selected) if n.startswith(prefix)]
                    if not pos:
                        continue
                    shuffled = xx[test].copy()
                    permutation = np.random.default_rng(rng_seed('importance', held_out, group_name)).permutation(len(shuffled))
                    shuffled[:, pos] = shuffled[permutation][:, pos]
                    error = float(np.mean((fitted.predict(shuffled)-y[test])**2))
                    importance_rows.append(dict(seed=held_out, model=kind, feature_set=feature_set,
                        method='held_out_group_permutation', feature=group_name, value=error-base_error))
                if kind == 'ridge':
                    importance_rows.extend(dict(seed=held_out, model=kind, feature_set=feature_set,
                        method='standardized_coefficient', feature=n, value=float(v))
                        for n, v in zip(selected, fitted[-1].coef_))
            for i in indices:
                prediction_rows.append(dict(row_id=i, seed=held_out, parent_id=groups[i]['parent_id'],
                    model=kind, feature_set=feature_set, truth=float(y[i]), prediction=float(predictions['reward'][i]),
                    eligible=bool(eligible[i]), delta_D=float(delta[i]) if np.isfinite(delta[i]) else None,
                    reward_category=labels[i]['reward_category']))
            print(f'FOLD {held_out} {kind} {feature_set} complete', flush=True)
    csv_write(out/'row_predictions.csv', prediction_rows)
    csv_write(out/'parent_rank_metrics.csv', parent_rows)
    csv_write(out/'secondary_predictions.csv', secondary_rows)
    csv_write(out/'feature_importance.csv', importance_rows)
    csv_write(out/'compute.csv', compute_rows)
    write(out/'completed.json', dict(seed=held_out, status='COMPLETED', train_rows=int(train.sum()),
          test_rows=int(test.sum()), prediction_rows=len(prediction_rows), train_test_disjoint=True,
          train_only_standardization_verified=True, features=feature_map))
