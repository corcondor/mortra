"""Ranking and fixed-budget replay with explicit tie semantics."""
import numpy as np
from scipy.stats import spearmanr


def top_weights(values, k):
    values = np.asarray(values)
    cutoff = np.sort(values)[-k]
    above, tied = values > cutoff, values == cutoff
    return above.astype(float) + tied * ((k-above.sum())/tied.sum())


def top_indices(values, k, tie_priority):
    return np.lexsort((tie_priority, -np.asarray(values)))[:k]


def ranking(y, pred, eligible):
    y, pred = np.asarray(y), np.asarray(pred)
    i, j = np.triu_indices(len(y), 1)
    mask = y[i] != y[j]
    dy, dp = y[i[mask]]-y[j[mask]], pred[i[mask]]-pred[j[mask]]
    w = top_weights(pred, 8)
    return dict(spearman=float(spearmanr(y, pred).statistic) if np.ptp(y) and np.ptp(pred) else None,
        pairwise_accuracy=float(np.mean((dy*dp > 0) + .5*(dp == 0))) if len(dy) else None,
        comparable_pairs=len(dy), top1_regret=float(y.max()-np.dot(top_weights(pred, 1), y)),
        top5_recall=float(np.dot(top_weights(y, 5), top_weights(pred, 5))/5),
        positive_precision8=float(np.dot(w, y > 0)/8), eligible_precision8=float(np.dot(w, eligible)/8),
        mse=float(np.mean((y-pred)**2)))


def outcomes(indices, reward, eligible, delta):
    indices = np.atleast_2d(indices)
    r, e, d = reward[indices], eligible[indices], delta[indices]
    available = np.any(np.isfinite(d), axis=1)
    maxima = np.max(np.where(np.isfinite(d), d, -np.inf), axis=1)
    maxima[~available] = np.nan
    return dict(mean_reward=r.mean(axis=1), best_reward=r.max(axis=1),
        positive_rate=(r > 0).mean(axis=1), eligible_rate=e.mean(axis=1),
        max_delta_D=maxima, beats_parent=np.any(r > 0, axis=1).astype(float))


def summarize_draws(values):
    result = {}
    for name, v in values.items():
        v = np.asarray(v); v = v[np.isfinite(v)]
        result[name] = float(v.mean()) if len(v) else None
        result[name+'_p025'] = float(np.quantile(v, .025)) if len(v) else None
        result[name+'_p975'] = float(np.quantile(v, .975)) if len(v) else None
        result[name+'_mc_se'] = float(v.std(ddof=1)/np.sqrt(len(v))) if len(v) > 1 else None
        result[name+'_defined_draws'] = len(v)
    return result


def headroom(model, uniform, oracle, guard=1e-12):
    h = oracle-uniform
    return dict(headroom=h, improvement=model-uniform,
                recovery=(model-uniform)/h if h > guard else None)
