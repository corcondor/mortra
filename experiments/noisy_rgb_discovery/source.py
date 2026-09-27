"""Load selected reference definitions, without executing old experiments."""
import ast
import hashlib
import itertools
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent / 'reference'
EXPECTED = {
    'physics3d.py': 'bf36fceb6b787a2f0c6e7d1f43c629912ddc224c85512ca9c7680a357713f4e5',
    'run_experiment.py': '1e39f962a41c49999a9f9cef3aa0ab633c0a1e2b0eb4665b0730b682fe8eacf5',
    'noisy_active.py': '5e93bf079c47be00258e174f94586e245166df857238ab41c49317f6f85ebd33',
    'stat_psm.py': 'db14c31a2a42d4f9b8623cd832cedccbf85d48a04e19729c1f10719ae4de5514',
}


def definition(filename, name, namespace):
    path = ROOT / filename
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED[filename], filename
    tree = ast.parse(data.decode('utf-8'), filename=str(path))
    selected = [x for x in tree.body if isinstance(x, (ast.ClassDef, ast.FunctionDef)) and x.name == name]
    assert len(selected) == 1
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


def environment_class():
    ns = dict(np=np, math=math, hashlib=hashlib, json=json, Image=Image, ImageDraw=ImageDraw)
    definition('physics3d.py', 'PhysicsArena3D', ns)
    definition('run_experiment.py', 'DelayedJumpArena', ns)
    ns['R'] = SimpleNamespace(DelayedJumpArena=ns['DelayedJumpArena'])
    return definition('noisy_active.py', 'NoisyDelayedJumpArena', ns)


def table_class(actions):
    ns = dict(ACTIONS=tuple(actions), itertools=itertools, RGBDistributionOracle=object)
    return definition('stat_psm.py', 'StatisticalObservationTable', ns)
