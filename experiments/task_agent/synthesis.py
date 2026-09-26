"""The task automaton from labelled traces, not from a specification.

Every experiment so far handed the agent its task as SEQ / ALL / BRANCH over
named predicates and compiled the automaton from that. Here the agent is given
only traces through the world, each labelled at every step with whether the task
has been accomplished yet -- what a reward signal gives -- and must infer the
automaton itself, then plan with what it inferred.

The learner is RPNI (Oncina and Garcia, 1992): build the prefix-tree acceptor of
the labelled traces and merge its nodes greedily, in length-lexicographic order,
whenever the merge (with the folding that keeps it deterministic) never puts an
accepted prefix and a rejected one in the same block. RPNI identifies a regular
language in the limit and returns the target exactly once the sample contains a
characteristic set -- and returns something smaller and more general when it
does not. Which of those happens here is the experiment.

The alphabet is the world's own states, as indices into the true state list;
nothing tells the learner which of them matter. Labels come from the true
automaton, which is absorbing on acceptance, so a trace stops at its first
acceptance and all its proper prefixes are rejected.

Conventions, stated because they are choices:

* a symbol never seen from an inferred state leaves the memory where it is.
  That is right for landmark states and wrong for a predicate such as
  "variable j equals v", which many unseen states satisfy;
* planning is on the TRUE world graph, so what is measured is the inferred
  automaton and nothing else; the learned world model was the subject of every
  earlier experiment;
* an inferred automaton is judged on this world: equivalence means no sequence
  of actions from the evaluation starts makes one automaton accept and the other
  not, which is the only equivalence an agent here could ever observe.
"""
from __future__ import annotations

import random
from collections import deque

import numpy as np


# ---------------------------------------------------------------------------
# The true product, once per task
# ---------------------------------------------------------------------------

class TrueTask:
    """World x true automaton: distances to acceptance, labels, shortest runs."""

    def __init__(self, states, edges, automaton, num_actions):
        self.states, self.edges, self.automaton = states, edges, automaton
        self.A = num_actions
        n, M = len(states), automaton.num_memory
        self.M = M
        step = np.zeros((n, M, num_actions), dtype=np.int64)       # next memory
        for s in range(n):
            for m in range(M):
                for a in range(num_actions):
                    step[s, m, a] = automaton.update(m, states[edges[s][a]])
        self.step = step
        dist = np.full((n, M), -1, dtype=np.int64)
        reverse = [[] for _ in range(n*M)]
        for s in range(n):
            for m in range(M):
                if automaton.done(m):
                    continue
                for a in range(num_actions):
                    t = edges[s][a]
                    reverse[t*M+int(step[s, m, a])].append(s*M+m)
        queue = deque()
        for s in range(n):
            for m in range(M):
                if automaton.done(m):
                    dist[s, m] = 0
                    queue.append(s*M+m)
        while queue:
            z = queue.popleft()
            d = dist[z//M, z % M]
            for y in reverse[z]:
                if dist[y//M, y % M] < 0:
                    dist[y//M, y % M] = d+1
                    queue.append(y)
        self.dist = dist
        self.init = np.array([automaton.initial_memory(states[s]) for s in range(n)])

    def optimal_steps(self, s):
        d = int(self.dist[s, self.init[s]])
        return None if d < 0 else d

    def solvable(self):
        return [s for s in range(len(self.states)) if self.optimal_steps(s) is not None]

    def demonstration(self, s, rng):
        """A shortest accomplishing run from s, ties broken at random."""
        m = int(self.init[s])
        trace = [s]
        while not self.automaton.done(m):
            d = self.dist[s, m]
            options = [a for a in range(self.A)
                       if self.dist[self.edges[s][a], self.step[s, m, a]] == d-1]
            a = rng.choice(options)
            s, m = self.edges[s][a], int(self.step[s, m, a])
            trace.append(s)
        return trace, True

    def label(self, path):
        """Run the true automaton along a path of states; cut at the first acceptance."""
        m = int(self.init[path[0]])
        if self.automaton.done(m):
            return [path[0]], True
        for k in range(1, len(path)):
            prev, s = path[k-1], path[k]
            a = next(a for a in range(self.A) if self.edges[prev][a] == s)
            m = int(self.step[prev, m, a])
            if self.automaton.done(m):
                return list(path[:k+1]), True
        return list(path), False

    def random_walk(self, s, length, rng):
        path = [s]
        for _ in range(length):
            path.append(self.edges[path[-1]][rng.randrange(self.A)])
        return self.label(path)

    def direct_route(self, s, target):
        """The shortest world path from s to a demonstration's final state, labelled."""
        parent = {s: None}
        queue = deque([s])
        while queue and target not in parent:
            u = queue.popleft()
            for a in range(self.A):
                v = self.edges[u][a]
                if v not in parent:
                    parent[v] = u
                    queue.append(v)
        if target not in parent:
            return None
        path = [target]
        while parent[path[-1]] is not None:
            path.append(parent[path[-1]])
        return self.label(path[::-1])


# ---------------------------------------------------------------------------
# RPNI
# ---------------------------------------------------------------------------

def labelled_prefixes(traces):
    """Every prefix of every trace, labelled; a trace stops at its first acceptance."""
    labels = {}
    for trace, accepted in traces:
        for k in range(1, len(trace)+1):
            prefix = tuple(trace[:k])
            value = bool(accepted and k == len(trace))
            if labels.get(prefix, value) != value:
                raise ValueError("inconsistent sample")
            labels[prefix] = value
    return labels


class _Partition:
    """Blocks of prefix-tree nodes under trial merges, with an undo log."""

    def __init__(self, children, label):
        self.parent = list(range(len(label)))
        self.children = children
        self.label = label
        self.log = []

    def find(self, x):
        while self.parent[x] != x:
            x = self.parent[x]
        return x

    def merge(self, a, b):
        """Merge the blocks of a and b and fold; False (state unchanged) on a label clash."""
        mark = len(self.log)
        stack = [(a, b)]
        while stack:
            x, y = stack.pop()
            x, y = self.find(x), self.find(y)
            if x == y:
                continue
            lx, ly = self.label[x], self.label[y]
            if lx is not None and ly is not None and lx != ly:
                self.undo(mark)
                return False
            if x > y:
                x, y = y, x
            self.log.append(("parent", y))
            self.parent[y] = x
            if self.label[x] is None and self.label[y] is not None:
                self.log.append(("label", x))
                self.label[x] = self.label[y]
            for symbol, child in self.children[y].items():
                if symbol in self.children[x]:
                    stack.append((self.children[x][symbol], child))
                else:
                    self.log.append(("child", x, symbol))
                    self.children[x][symbol] = child
        return True

    def undo(self, mark):
        while len(self.log) > mark:
            entry = self.log.pop()
            if entry[0] == "parent":
                self.parent[entry[1]] = entry[1]
            elif entry[0] == "label":
                self.label[entry[1]] = None
            else:
                del self.children[entry[1]][entry[2]]

    def commit(self):
        self.log.clear()


def rpni(labels):
    """A DFA consistent with a prefix-closed labelled sample (RPNI, red-blue)."""
    prefixes = sorted(labels, key=lambda p: (len(p), p))
    node = {(): 0}
    children = [{}]
    # before the first state is read nothing has been accomplished: the empty prefix is
    # rejected. Leaving it unlabelled would let RPNI merge an accepting node into the root
    # and make the start accepting, which absorbing acceptance cannot then undo.
    label = [False]
    for p in prefixes:                      # prefix-closed, so a parent precedes its child
        node[p] = len(children)
        children.append({})
        label.append(labels[p])
        children[node[p[:-1]]][p[-1]] = node[p]
    h = _Partition(children, label)
    red = [0]
    while True:
        reds = {h.find(r) for r in red}
        blue = sorted({h.find(c) for r in reds for c in h.children[r].values()} - reds)
        if not blue:
            break
        b = blue[0]
        for r in sorted(reds):
            if h.merge(r, b):
                h.commit()
                break
        else:
            red.append(b)
    return LearnedAutomaton.from_partition(h)


class LearnedAutomaton:
    """The inferred DFA over world-state indices; unseen symbols leave the memory as is."""

    def __init__(self, delta, accepting, initial=0, num_memory=1):
        self.delta = delta
        self.accepting = frozenset(accepting)
        self.initial = initial
        self.num_memory = num_memory

    @classmethod
    def from_partition(cls, h):
        names = {}
        delta, accepting = {}, set()
        root = h.find(0)
        names[root] = 0
        queue = deque([root])
        while queue:
            x = queue.popleft()
            if h.label[x] is True:
                accepting.add(names[x])
            for symbol, child in h.children[x].items():
                y = h.find(child)
                if y not in names:
                    names[y] = len(names)
                    queue.append(y)
                delta[(names[x], symbol)] = names[y]
        return cls(delta, accepting, 0, len(names))

    def update(self, memory, symbol):
        if memory in self.accepting:
            return memory
        return self.delta.get((memory, symbol), memory)

    def initial_memory(self, symbol):
        return self.update(self.initial, symbol)

    def done(self, memory):
        return memory in self.accepting


class GoalSet:
    """The no-automaton baseline: accomplished means reaching a state some demonstration ended in."""

    def __init__(self, traces):
        self.goals = frozenset(t[-1] for t, accepted in traces if accepted)
        self.num_memory = 2

    def update(self, memory, symbol):
        return 1 if memory == 1 or symbol in self.goals else 0

    def initial_memory(self, symbol):
        return self.update(0, symbol)

    def done(self, memory):
        return memory == 1


# ---------------------------------------------------------------------------
# Planning with, and judging, an inferred automaton
# ---------------------------------------------------------------------------

def plan(task, hypothesis, s):
    """Shortest path in world x hypothesis to hypothesised acceptance, as world states."""
    z0 = (s, hypothesis.initial_memory(s))
    if hypothesis.done(z0[1]):
        return [s]
    parent = {z0: None}
    queue = deque([z0])
    while queue:
        z = queue.popleft()
        u, m = z
        for a in range(task.A):
            v = task.edges[u][a]
            z2 = (v, hypothesis.update(m, v))
            if z2 in parent:
                continue
            parent[z2] = z
            if hypothesis.done(z2[1]):
                path = [z2]
                while parent[path[-1]] is not None:
                    path.append(parent[path[-1]])
                return [u for u, _ in reversed(path)]
            queue.append(z2)
    return None


def execute(task, hypothesis, s):
    """Plan with the hypothesis, execute in the deterministic world, judge by the truth.

    Returns (accomplished, steps, trace): the task counts as accomplished the
    moment the true automaton accepts along the executed path.
    """
    path = plan(task, hypothesis, s)
    if path is None:
        return False, None, None
    trace, accepted = task.label(path)
    return accepted, (len(trace)-1 if accepted else None), (trace, accepted)


def disagreement(task, hypothesis, starts):
    """Is there a reachable point, from any of these starts, where the two automata disagree?"""
    seen = set()
    queue = deque()
    for s in starts:
        z = (s, int(task.init[s]), hypothesis.initial_memory(s))
        if z not in seen:
            seen.add(z)
            queue.append(z)
    while queue:
        s, mt, mh = queue.popleft()
        if task.automaton.done(mt) != hypothesis.done(mh):
            return True
        if task.automaton.done(mt):
            continue
        for a in range(task.A):
            t = task.edges[s][a]
            z = (t, int(task.step[s, mt, a]), hypothesis.update(mh, t))
            if z not in seen:
                seen.add(z)
                queue.append(z)
    return False


# ---------------------------------------------------------------------------
# The three ways of getting a sample, and the counterexample loop
# ---------------------------------------------------------------------------

WALK = 32


def material(task, starts, key):
    """For each demonstration start: a demonstration, a random walk and a direct route.

    Each is drawn with its own seeded generator, so the sample for N starts is
    the first N entries of the sample for 16, and every condition at a given N
    sees the same demonstrations.
    """
    rows = []
    for i, s in enumerate(starts):
        demo = task.demonstration(s, random.Random(f"demo:{key}:{i}"))
        walk = task.random_walk(s, WALK, random.Random(f"walk:{key}:{i}"))
        route = task.direct_route(s, demo[0][-1])
        rows.append((demo, walk, route))
    return rows


def sample(rows, n, negatives):
    """The first n demonstrations, with negatives of the named kind."""
    traces = [demo for demo, _, _ in rows[:n]]
    if negatives in ("random", "near_miss"):
        traces += [walk for _, walk, _ in rows[:n]]
    if negatives == "near_miss":
        traces += [route for _, _, route in rows[:n] if route is not None]
    return traces


def counterexample_loop(task, traces, start, *, rounds=16, rng=None):
    """Infer, plan, execute, and add what was observed, until the task is accomplished.

    This is the agent learning from its own reward signal: a failed execution
    is a trace the hypothesis accepted and the truth did not, so the next
    hypothesis must reject it and the same plan is never repeated. When the
    hypothesis has no plan at all, the agent takes a random walk instead.
    """
    traces = list(traces)
    rng = rng or random.Random(0)
    for r in range(rounds+1):
        hypothesis = rpni(labelled_prefixes(traces))
        accomplished, steps, observed = execute(task, hypothesis, start)
        if accomplished:
            return hypothesis, r, traces
        if r == rounds:
            break
        traces.append(observed if observed is not None
                      else task.random_walk(start, WALK, rng))
    return hypothesis, None, traces
