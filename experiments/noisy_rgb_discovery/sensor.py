"""Environment-side RGB transport; no state labels or success return values."""
from dataclasses import dataclass
import gzip
import hashlib
import json

import numpy as np

from .source import environment_class


def make_game(seed):
    class GoalForbidden(environment_class()):
        def raw_goal(self, *args):
            raise AssertionError('Success flags are forbidden in this experiment')

        def token_for(self, *args):
            raise AssertionError('State tokens are forbidden in this experiment')

    return GoalForbidden(seed, 'state_opaque')


@dataclass(frozen=True)
class RGBPort:
    actions: tuple
    sample: object


class Sensor:
    def __init__(self, game, camera_bias, namespace, directory, batch=8, size=12):
        self.game = game
        self.camera_bias = tuple(camera_bias)
        self.namespace = namespace
        self.batch, self.size = batch, size
        self.queries = self.actions = self.exposures = self.duplicates = 0
        self.hashes = set()
        directory.mkdir()
        self.frames = gzip.open(directory / 'raw.rgb.gz', 'wb', compresslevel=1)
        self.trace = gzip.open(directory / 'queries.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1)
        self.first_sample = None
        self.port = RGBPort(tuple(range(game.num_actions)), self.sample)

    def sample(self, history, replicate):
        assert all(a in self.port.actions for a in history)
        raw = self.game.start_raw
        for action in history:
            raw = self.game.raw_step(raw, int(action))
            self.actions += 1
        key = json.dumps([self.namespace, list(history), int(replicate)], separators=(',', ':')).encode()
        views = self.game.noisy_batch(raw, 0, key, self.batch, self.size, camera_bias=self.camera_bias)
        data = np.stack(views, axis=1)
        assert data.shape == (self.batch, 4, self.size, self.size, 3) and data.dtype == np.uint8
        if self.first_sample is None:
            self.first_sample = data.copy()
        self.frames.write(data.tobytes())
        hashes = []
        for exposure in data:
            h = hashlib.sha256(exposure.tobytes()).hexdigest()
            self.duplicates += h in self.hashes
            self.hashes.add(h)
            hashes.append(h)
        row = dict(query=self.queries, history=list(history), replicate=int(replicate),
                   shape=list(data.shape), raw_hashes=hashes)
        self.trace.write(json.dumps(row) + '\n')
        self.queries += 1
        self.exposures += self.batch
        return data

    def metrics(self):
        return dict(queries=self.queries, environment_actions=self.actions, exposures=self.exposures,
                    views_per_exposure=4, exact_duplicate_exposures=self.duplicates)

    def close(self):
        self.trace.close()
        self.frames.close()
