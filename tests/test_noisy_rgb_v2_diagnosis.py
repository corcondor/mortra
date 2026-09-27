import itertools

from experiments.noisy_rgb_predictive_v2.diagnose_v1 import minimum_cover


def test_exact_cover_matches_exhaustive():
    for masks in itertools.product(range(1,8),repeat=4):
        universe = 0
        for m in masks:
            universe |= m
        result = minimum_cover([((j,),m) for j,m in enumerate(masks)],universe)
        best = min(len(c) for n in range(5) for c in itertools.combinations(range(4),n)
                   if __import__('functools').reduce(int.__or__,(masks[j] for j in c),0)==universe)
        assert len(result)==best
        assert __import__('functools').reduce(int.__or__,(masks[e[0]] for e in result),0)==universe


def test_empty_cover():
    assert minimum_cover([],0)==[]
