"""Explicit finite-sample diagnostics; none of these functions controls a Player."""
import math
import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr
from scipy.stats import rankdata


def correlation(x, y, rank=False):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 2 or np.all(x == x[0]) or np.all(y == y[0]):
        return None
    if rank:
        x, y = rankdata(x), rankdata(y)
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        return None
    return float(np.corrcoef(x, y)[0, 1])


def top_membership(values, k):
    values = np.asarray(values, float)
    cutoff = sorted(values, reverse=True)[k-1]
    above, tied = values > cutoff, values == cutoff
    return above.astype(float) + tied * ((k-int(above.sum())) / int(tied.sum()))


def calibration(mu, probabilities, ucb):
    mu, p = np.asarray(mu, float), np.asarray(probabilities, float)
    assert len(mu) == len(p) and np.isclose(p.sum(), 1)
    # Untried arms have conceptual +infinity priority; only ranks use this.
    scores = rankdata([float('inf') if v is None else v for v in ucb])
    best = np.flatnonzero(p == p.max())
    ea, eu = float(p @ mu), float(mu.mean())
    return dict(rho_UCB=correlation(scores, mu, True), rho_P=correlation(p, mu, True),
                R1=float(mu.max()-mu[best].mean()),
                R1_min=float(mu.max()-mu[best].max()), R1_max=float(mu.max()-mu[best].min()),
                top3_expected_overlap=float(top_membership(mu, 3) @ top_membership(p, 3)),
                E_adaptive=ea, E_uniform=eu, Delta_E=ea-eu)


def threshold_audit(success, budgets):
    y = np.asarray(success, int)
    x = np.log2(budgets)
    assert len(y) == len(x) and np.all(np.isin(y, [0, 1])) and np.all(np.diff(x) > 0)
    hit = np.flatnonzero(y)
    k = int(hit[0]) if len(hit) else None
    absorbed = np.maximum.accumulate(y)
    area = lambda z: float(np.sum(np.diff(x) * (2-z[:-1]-z[1:])/2))
    d, first_area = area(y), area(absorbed)
    threshold = float(x[-1]-x[0] if k is None else x[k]-x[0])
    half_bin = float((x[k]-x[k-1])/2) if k is not None and k > 0 else 0.
    penalty = d-first_area
    assert np.isclose(d, threshold-half_bin+penalty, atol=1e-12)
    return dict(monotone=not bool(np.any(np.diff(y)<0)), reversals=int(np.sum(np.diff(y)<0)),
                first_success_budget=None if k is None else int(budgets[k]), censored=k is None,
                success_bits=''.join(map(str,y)), D_task=d, capped_log_threshold=threshold,
                trapezoid_half_bin=half_bin, nonmonotonicity_penalty=penalty,
                D_first_passage=first_area)


def max_normal_constant(m=8):
    def integrand(z):
        return z*m*math.exp(-z*z/2)/math.sqrt(2*math.pi)*ndtr(z)**(m-1)
    value, error = quad(integrand, -np.inf, np.inf, epsabs=1e-12, epsrel=1e-12)
    return dict(m=m, value=value, quadrature_error=error)


def response_stats(pairs):
    if not pairs:
        return dict(n=0, mean_X=None, mean_Y=None, variance_X=None, variance_Y=None,
                    covariance=None, Pearson=None, Spearman=None)
    x, y = np.array(pairs, float).T
    return dict(n=len(x), mean_X=float(x.mean()), mean_Y=float(y.mean()),
                variance_X=float(x.var(ddof=1)) if len(x)>1 else None,
                variance_Y=float(y.var(ddof=1)) if len(x)>1 else None,
                covariance=float(np.cov(x,y,ddof=1)[0,1]) if len(x)>1 else None,
                Pearson=correlation(x,y), Spearman=correlation(x,y,True))


def gaussian_response(pairs, constant):
    s = response_stats(pairs)
    if s['n']<2 or not s['variance_X']:
        return None
    return s['mean_Y'] + s['covariance']/math.sqrt(s['variance_X'])*constant


def resampled_response(pairs, seed, m=8, draws=10000):
    if not pairs:
        return None
    p = np.array(pairs, float)
    rng = np.random.default_rng(seed)
    sample = p[rng.integers(len(p), size=(draws,m))]
    maxima = sample[:,:,0].max(axis=1,keepdims=True)
    tied = sample[:,:,0] == maxima
    selected = (sample[:,:,1]*tied).sum(axis=1)/tied.sum(axis=1)
    return dict(expected_max_X_response=float(selected.mean()),
                expected_random_response=float(p[:,1].mean()),
                Monte_Carlo_SE=float(selected.std(ddof=1)/math.sqrt(draws)), draws=draws)


def path_attenuation(weights, q=.9):
    w = np.asarray(weights, float)
    assert np.all(w>0) and np.all(w<=1)
    n = len(w)
    log_w = float(np.log(w).sum())
    log_a = n*math.log(q)+log_w
    return dict(L=n, geometric_mean_weight=math.exp(log_w/n) if n else 1.,
                b_eff=math.exp(-log_w/n) if n else 1.,
                log_A_path=log_a, A_path=math.exp(log_a), below_cutoff=log_a<math.log(1e-7))
