"""New offline experiment only. Existing research implementations stay frozen."""
import argparse
import hashlib
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.frontier_v13.protocol import ROOT, CONFIG, read, write


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('dataset', 'fold', 'replay', 'report', 'verify-smoke'))
    p.add_argument('--source', type=Path)
    p.add_argument('--folds', type=Path)
    p.add_argument('--replay', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seed', type=int)
    args = p.parse_args()
    if args.mode == 'dataset':
        from experiments.frontier_v13.dataset import build
        build(args.output)
    elif args.mode == 'fold':
        from experiments.frontier_v13.train import run_fold
        run_fold(args.source, args.output, args.seed)
    elif args.mode == 'replay':
        from experiments.frontier_v13.replay import run
        run(args.source, args.folds, args.output)
    elif args.mode == 'report':
        from experiments.frontier_v13.report import summarize
        summarize(args.source, args.folds, args.replay, args.output)
        files = [*sorted((ROOT/'experiments/frontier_v13').glob('*.py')), Path(__file__),
                 ROOT/'tests/test_frontier_v13.py', ROOT/'.github/workflows/frontier-v13-structural-edit-prediction.yml',
                 ROOT/'docs/research/FRONTIER-V13-PREREGISTRATION-20260925.md']
        write(args.output/'experiment_source_sha.json', dict(run=os.environ.get('GITHUB_RUN_ID'),
            hashes={str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}))
    else:
        # Stage 1 and Stage 2 execute the same 2101 fold: bit-identical predictions required.
        for name in ('row_predictions.csv', 'parent_rank_metrics.csv', 'secondary_predictions.csv', 'feature_importance.csv'):
            assert (args.source/name).read_bytes() == (args.folds/'2101'/name).read_bytes(), name
        write(args.output, dict(stage1_stage2_predictions_exactly_equal=True, config=CONFIG))


if __name__ == '__main__':
    main()
