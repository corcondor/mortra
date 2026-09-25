"""Context-binned UCB1 with a deliberately narrow, numeric feedback API."""
from dataclasses import asdict, dataclass
import math

from experiments.game_frontier_v11.designer import FAMILIES


@dataclass(frozen=True, slots=True)
class Context:
    reachable_states: int
    rules: int
    variables: int
    actions: int
    board_area: int
    selection_D: float
    B80: int | None

    def __post_init__(self):
        for v in (self.reachable_states, self.rules, self.variables, self.actions, self.board_area):
            assert type(v) is int and v >= 0
        assert type(self.selection_D) in (int, float) and math.isfinite(self.selection_D)
        assert self.B80 is None or type(self.B80) is int

    def key(self):
        return f"{max(1, self.reachable_states).bit_length()-1}:{'unreached' if self.B80 is None else 'reached'}"


@dataclass(frozen=True, slots=True)
class Outcome:
    valid: bool
    eligible: bool
    D: float | None
    B80: int | None
    B90: int | None
    final_success: float | None
    full_info_success: float | None

    def __post_init__(self):
        assert type(self.valid) is bool and type(self.eligible) is bool
        for v in (self.D, self.final_success, self.full_info_success):
            assert v is None or (type(v) in (int, float) and math.isfinite(v))
        assert self.B80 is None or type(self.B80) is int
        assert self.B90 is None or type(self.B90) is int


def reward(parent_D, outcome):
    assert type(outcome) is Outcome
    if not outcome.eligible:
        return 0.0
    assert outcome.valid and outcome.full_info_success >= .8 and outcome.final_success >= .8
    assert outcome.D is not None
    return outcome.D - parent_D


class ContextualUCB:
    __slots__ = ("span", "tables")

    def __init__(self, span):
        assert span > 0
        self.span = float(span)
        self.tables = {}

    def table(self, context):
        assert type(context) is Context
        return self.tables.setdefault(context.key(), {a: {"count": 0, "reward_sum": 0.0} for a in FAMILIES})

    def decision(self, context, generation):
        table = self.table(context)
        total = sum(s["count"] for s in table.values())
        scores = {}
        for a, s in table.items():
            n = s["count"]
            scores[a] = None if not n else (s["reward_sum"] / n / self.span + 1) / 2 + math.sqrt(2 * math.log(max(1, total)) / n)
        if generation == 1:
            ties = list(FAMILIES)
        else:
            ties = [a for a in FAMILIES if table[a]["count"] == 0]
            if not ties:
                best = max(scores.values())
                ties = [a for a in FAMILIES if scores[a] == best]
        probabilities = {a: (1 / len(ties) if a in ties else 0.0) for a in FAMILIES}
        assert all(math.isfinite(p) and p >= 0 for p in probabilities.values())
        assert math.isclose(sum(probabilities.values()), 1.0)
        return {"context_key": context.key(), "context": asdict(context), "probabilities": probabilities,
                "ucb": scores, "counts": {a: table[a]["count"] for a in FAMILIES},
                "mean_rewards": {a: table[a]["reward_sum"] / table[a]["count"] if table[a]["count"] else None for a in FAMILIES}}

    def update(self, context, arm, outcome):
        assert type(context) is Context and type(outcome) is Outcome and arm in FAMILIES
        value = reward(context.selection_D, outcome)
        assert math.isfinite(value) and -self.span <= value <= self.span
        row = self.table(context)[arm]
        row["count"] += 1
        row["reward_sum"] += value
        return value

    def snapshot(self):
        return {k: {a: dict(s) for a, s in v.items()} for k, v in self.tables.items()}


def sample(probabilities, rng):
    ties = [a for a in FAMILIES if probabilities[a] > 0]
    # UCB selects maximizers uniformly; no softmax temperature or hidden floor.
    assert all(probabilities[a] == 1 / len(ties) for a in ties)
    return rng.choice(ties)
