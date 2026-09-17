"""Task-only generator for homology tasks (docs/research/ALGEBRAIC-STRUCTURES-20260917.md).

A task is an integer point cloud and a squared radius. Its complex is the
Vietoris-Rips 2-skeleton (vertices, edges of squared length <= r2, triangles of
pairwise edges); the question is b_0 and b_1 over QQ with representative cycles.
The generator reads no solver. The evaluator's reference answer uses python-flint
ranks, an implementation independent of the solver's column reduction.
"""
from __future__ import annotations

from itertools import combinations
import math
import random

SHAPES = ("circle", "two_circles", "figure_eight", "annulus", "blob")


def _sample(shape, n, rng):
    points = []
    for _ in range(n):
        noise = lambda: rng.uniform(-2.5, 2.5)
        angle = rng.uniform(0, 2*math.pi)
        if shape == "circle":
            x, y = 30*math.cos(angle), 30*math.sin(angle)
        elif shape == "two_circles":
            centre = rng.choice((-40, 40))
            x, y = centre+22*math.cos(angle), 22*math.sin(angle)
        elif shape == "figure_eight":
            centre = rng.choice((-22, 22))
            x, y = centre+22*math.cos(angle), 22*math.sin(angle)
        elif shape == "annulus":
            radius = rng.uniform(18, 32)
            x, y = radius*math.cos(angle), radius*math.sin(angle)
        else:
            x, y = rng.gauss(0, 18), rng.gauss(0, 18)
        points.append((round(x+noise()), round(y+noise())))
    return sorted(set(points))


def rips_simplices(points, r2):
    n = len(points)
    def close(i, j):
        return (points[i][0]-points[j][0])**2+(points[i][1]-points[j][1])**2 <= r2
    edges = [(i, j) for i, j in combinations(range(n), 2) if close(i, j)]
    neighbours = {i: set() for i in range(n)}
    for i, j in edges:
        neighbours[i].add(j)
        neighbours[j].add(i)
    triangles = {(i, j, k) for i, j in edges for k in neighbours[i] & neighbours[j] if k > j}
    return {(i,) for i in range(n)} | set(edges) | triangles


def generate(seed, count, *, min_points=40, max_points=160):
    rng = random.Random(seed)
    tasks = []
    while len(tasks) < count:
        shape = rng.choice(SHAPES)
        n = rng.randint(min_points, max_points)
        points = _sample(shape, n, rng)
        distances = sorted((a[0]-b[0])**2+(a[1]-b[1])**2 for a, b in combinations(points, 2))
        quantile = rng.uniform(0.015, 0.06)
        r2 = distances[max(0, int(quantile*len(distances))-1)]
        tasks.append({"shape": shape, "points": [list(p) for p in points], "r2": r2, "question": "betti_0_1"})
    return {"seed": seed, "tasks": tasks,
            "rule": "shape uniform over SHAPES; 40-160 samples with uniform noise in [-2.5, 2.5], rounded; "
                    "r2 = the q-quantile of pairwise squared distances, q uniform in [0.015, 0.06]; Rips 2-skeleton"}


def generate_model_tasks(seed, count, *, max_cells=6000):
    """Minimal-model tasks: shape uniform, 40-110 samples, r2 at a quantile uniform in [0.03, 0.12]; complexes above max_cells are rejected."""
    rng = random.Random(seed)
    tasks, rejected = [], 0
    while len(tasks) < count:
        shape = rng.choice(SHAPES)
        points = _sample(shape, rng.randint(40, 110), rng)
        distances = sorted((a[0]-b[0])**2+(a[1]-b[1])**2 for a, b in combinations(points, 2))
        r2 = distances[max(0, int(rng.uniform(0.03, 0.12)*len(distances))-1)]
        if len(rips_simplices(points, r2)) > max_cells:
            rejected += 1
            continue
        tasks.append({"shape": shape, "points": [list(p) for p in points], "r2": r2, "question": "minimal_model"})
    return {"seed": seed, "tasks": tasks, "rejected_over_size": rejected,
            "rule": "shape uniform over SHAPES; 40-110 samples; r2 = q-quantile of pairwise squared distances, "
                    f"q uniform in [0.03, 0.12]; Rips 2-skeleton with at most {max_cells} cells"}


def reference_betti(simplices):
    """b_0, b_1 over QQ from python-flint ranks of dense boundary matrices (independent of the solver)."""
    from flint import fmpq_mat
    by = {q: sorted(s for s in simplices if len(s) == q+1) for q in range(3)}
    index = {q: {s: i for i, s in enumerate(by[q])} for q in range(3)}
    ranks = {}
    for q in (1, 2):
        rows, cols = len(by[q-1]), len(by[q])
        if rows == 0 or cols == 0:
            ranks[q] = 0
            continue
        matrix = fmpq_mat(rows, cols)
        for j, s in enumerate(by[q]):
            for i in range(len(s)):
                matrix[index[q-1][s[:i]+s[i+1:]], j] = -1 if i % 2 else 1
        ranks[q] = matrix.rank()
    return [len(by[0])-ranks[1], len(by[1])-ranks[1]-ranks[2]]
