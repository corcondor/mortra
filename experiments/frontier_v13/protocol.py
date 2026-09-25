"""Preregistered constants and plain data IO. No research-runtime imports."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEEDS = [2101, 2202, 2303, 2404, 2505, 2606, 2707, 2808]
ARMS = ('variable_add', 'variable_delete', 'domain', 'action_add', 'action_delete',
        'rule_add', 'rule_delete', 'guard', 'assignment', 'priority', 'dependency',
        'topology', 'board', 'initial')
AUDIT_RUN = '36120576842'
AUDIT_HEAD = '3ccea4503a29a7e0f759694c26f1c5deae7c0155'
OLD_RUN = '36107649938'
OLD_HEAD = 'c060d5c9549eaae913bd7b9555ad2289ff96ff8c'
CONFIG = {
    'protocol': 'frontier-v1.3-offline-structural-edit-prediction',
    'seeds': SEEDS, 'primary_split': 'leave-one-seed-out', 'rows': 7000, 'parents': 50,
    'feature_sets': ['M0', 'M1', 'M2', 'M3', 'M4'],
    'models': {
        'ridge': {'alpha': 1.0, 'solver': 'svd'},
        'tree': {'max_depth': 4, 'learning_rate': .05, 'max_iter': 200,
                 'l2_regularization': 1.0, 'random_state': 130025,
                 'early_stopping': False, 'max_leaf_nodes': 31,
                 'min_samples_leaf': 20, 'max_bins': 255, 'loss': 'squared_error'},
    },
    'preprocessing': 'train-only zero imputation with explicit availability flags, StandardScaler train-only',
    'secondary': 'same regressors/settings for eligibility indicator, delta_D when observed, positive reward indicator',
    'classification_readout': 'secondary indicator prediction >= 0.5; not a change to reward',
    'uniform_draws': 10000, 'pool_draws': 1000, 'rng_root': 130025,
    'pool_sizes': [8, 16, 32, 64, 140], 'evaluation_budget': 8,
    'primary_reward': 'archived exact v1.2: eligible ? D_candidate-D_parent : 0',
    'history_cut': 'earliest frontier occurrence of each parent, before slot 0; G10-only uses terminal past history',
    'M1': 'actual coarse context log2 reachable bin/B80 reached, primitive, current-context arm count/mean/bonus',
    'M4_history': 'strictly past proposals: arm/global count, mean, variance, positive/eligible/invalid rates',
    'UCB_replay': 'freeze first recorded pre-slot probability distribution, sample eight distinct candidates; no counterfactual updates',
    'UCB_G10': 'terminal hypothetical distribution reported separately, never labeled recorded',
    'ties': 'rank metrics integrate boundary ties; replay uses one preregistered random priority per candidate shared across models, never hash fitness',
    'uniform_intervals': '2.5/97.5 percentiles over random subsets, not confidence intervals over environments; MC standard error also saved',
    'pool_pairing': 'same random subsets and tie priorities across all models for each parent/pool size',
    'headroom_min_denominator': 1e-12,
    'headroom_rule': 'ratio only for positive denominator > numerical reporting guard, otherwise absolute differences',
    'importance': 'ridge standardized coefficients plus held-out grouped permutation MSE increase; no refitting/tuning',
    'statistical_unit': 'parent macro within seed, then eight seed macro; no row-independent inference',
    'stage1': 'held-out 2101 all settings; correctness only, no outcome-based changes',
    'holdout_artifacts': 'never downloaded/read by this experiment',
    'forbidden': 'candidate evaluation/rollout, new mutation, online evolution, result-dependent features/models',
    'stop': 'after eight-fold results; no online integration',
}


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()


def rng_seed(*parts):
    return int(digest([CONFIG['rng_root'], *parts])[:15], 16)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False), encoding='utf-8')


def csv_write(path, rows):
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row)) or ['status']
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: canonical(v) if isinstance(v, (dict, list, tuple)) else v
                     for k, v in row.items()} for row in rows)
