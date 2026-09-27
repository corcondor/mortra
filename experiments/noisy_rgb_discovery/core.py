"""RGB-only adapter around the supplied statistical observation table."""
from dataclasses import dataclass
import itertools
import math

import numpy as np

from .source import table_class


@dataclass(frozen=True)
class Emission:
    mean: np.ndarray
    var: np.ndarray
    n: int

    @property
    def goal(self):
        # Constant compatibility field required by the unchanged reference table.
        return False


class Statistics:
    def __init__(self, port, noise_floor=.01):
        self.port, self.noise_floor = port, noise_floor
        self.cache = {}
        self.query_count = self.query_actions = self.exposures = 0

    def summary(self, history, rep=0):
        key = (tuple(history), int(rep))
        if key not in self.cache:
            rgb = self.port.sample(*key)
            assert isinstance(rgb, np.ndarray) and rgb.dtype == np.uint8
            x = rgb.reshape(len(rgb), -1).astype(np.float32) / 255.
            self.cache[key] = Emission(x.mean(0), x.var(0, ddof=1), len(x))
            self.query_count += 1
            self.query_actions += len(history)
            self.exposures += len(x)
        return self.cache[key]

    def z(self, a, b):
        den = a.var/a.n + b.var/b.n + self.noise_floor**2
        return float(np.sqrt(np.mean((a.mean-b.mean)**2/den)))


def calibrate(statistics, actions, words=100, margin=1.18):
    # Same-history comparison only, matching the reference calibration recipe.
    histories = [()]
    for length in range(1, 6):
        for word in itertools.product(actions, repeat=length):
            histories.append(word)
            if len(histories) >= words:
                break
        if len(histories) >= words:
            break
    scores = [statistics.z(statistics.summary(h, 0), statistics.summary(h, 1)) for h in histories]
    threshold = max(scores) * margin
    return threshold, dict(histories=histories, scores=scores, margin=margin, threshold=threshold,
                           noise_floor=statistics.noise_floor)


class EventList(list):
    def __init__(self, values, callback):
        super().__init__(values)
        self.callback = callback

    def append(self, value):
        self.callback(value)
        super().append(value)


def learner(statistics, actions, threshold, emit, memoize=True):
    base = table_class(actions)

    class TracedTable(base):
        def __init__(self):
            super().__init__(statistics, threshold)
            self.pairs = {}
            self.last_difference = None
            self.events = []
            self.S = EventList(self.S, self.access_added)
            self.E = EventList(self.E, self.suffix_added)

        def access_added(self, word):
            emit(dict(event='access_added', history=word, access_count=len(self.S)+1,
                      suffix_count=len(self.E), queries=self.o.query_count))

        def out_same(self, w1, w2):
            w1, w2 = tuple(w1), tuple(w2)
            pair = tuple(sorted((w1, w2)))
            if memoize and pair in self.pairs:
                same = self.pairs[pair]
            else:
                same = super().out_same(w1, w2)
                if memoize:
                    self.pairs[pair] = same
            if not same:
                self.last_difference = (w1, w2)
            return same

        def suffix_added(self, suffix):
            w1, w2 = self.last_difference
            suffix = tuple(suffix)
            assert suffix and w1[-len(suffix):] == w2[-len(suffix):] == suffix
            h1, h2 = w1[:-len(suffix)], w2[:-len(suffix)]
            before = []
            for e in self.E:
                x, y = self.o.cache[(h1+e, 0)], self.o.cache[(h2+e, 0)]
                before.append(self.o.z(x, y))
            distance = self.o.z(self.o.cache[(w1, 0)], self.o.cache[(w2, 0)])
            assert all(z <= self.T for z in before) and distance > self.T
            event = dict(event='suffix_added', suffix=suffix, action=suffix[0], previous_suffix=suffix[1:],
                         history1=h1, history2=h2, prior_E=list(self.E), prior_scores=before,
                         witness_score=distance, threshold=self.T, queries=self.o.query_count)
            assert suffix[1:] in self.E
            self.events.append(event)
            emit(event)

        def machine(self):
            m = super().machine()
            assert not any(m['goal'].values())
            emit(dict(event='model_constructed', states=len(m['reps']), suffixes=list(self.E),
                      queries=self.o.query_count))
            return m

    return TracedTable()


def predict_from_rgb(statistics, history, suffixes, prototypes, threshold):
    scores = np.zeros(len(prototypes), dtype=float)
    for j, e in enumerate(suffixes):
        x = statistics.summary(tuple(history)+tuple(e))
        means = np.stack([p[j].mean for p in prototypes])
        variances = np.stack([p[j].var/p[j].n for p in prototypes])
        d = np.sqrt(np.mean((means-x.mean)**2 / (variances+x.var/x.n+statistics.noise_floor**2), axis=1))
        scores = np.maximum(scores, d)
    eligible = np.flatnonzero(scores <= threshold).tolist()
    return dict(candidates=eligible, predicted=eligible[0] if len(eligible) == 1 else None,
                nearest=int(np.argmin(scores)), best_distance=float(np.min(scores)))


def model_record(model, suffixes):
    return dict(reps=model['reps'], groups=model['groups'], start=model['start'],
                transitions=[[q, a, t] for (q, a), t in sorted(model['trans'].items())],
                suffixes=list(suffixes), success_field_is_constant_false=True)
