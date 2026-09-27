"""Use the frozen V2 runner, with only its learner constructor rebound."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .core import FamilyLearner
from .gate import verify_sources


def constructor(*args, **kwargs):
    labels = kwargs['label_equality'].__self__.records
    return FamilyLearner(*args, labels=labels, **kwargs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--camera', choices=['base', 'shifted'], required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    assert args.seed in range(97027000, 97027032)
    assert not args.output.exists()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = args.output.with_name(args.output.name+'_family_execution.json')
    with metadata.open('x', encoding='utf-8') as f:
        json.dump(dict(arm='B', frozen_files=verify_sources(), command=sys.argv,
            commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            files={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in Path(__file__).parent.glob('*') if p.is_file()},
            config=json.loads(Path(__file__).with_name('config.json').read_text()),
            integration='Frozen runner constructor binding only; original evaluator and all merge gates'), f, indent=2)
    from experiments.noisy_rgb_predictive_v2 import run as frozen
    original, argv = frozen.ProvisionalLearner, sys.argv
    frozen.ProvisionalLearner = constructor
    sys.argv = [argv[0], '--phase', 'development', '--seed', str(args.seed),
                '--camera', args.camera, '--arm', 'V2', '--output', str(args.output)]
    try:
        frozen.main()
    finally:
        frozen.ProvisionalLearner, sys.argv = original, argv


if __name__ == '__main__':
    main()
