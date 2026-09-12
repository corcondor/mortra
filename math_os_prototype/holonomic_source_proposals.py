"""Select new source functions inside the existing exact series language.

No parameter grid or target identity is supplied. Positive reduced rationals
are bounded by numerator + denominator; all supported hypergeometric arities
up to the operator-order budget are interleaved. This grows the objects under
study, not the mathematical language or the set of proof axioms.
"""
from math import comb, gcd

from math_os_prototype.holonomic_route_discovery import validate
from math_os_prototype.research_indexed_agenda import ResearchIndexedAgenda


def rational_alphabet(height):
    if type(height) is not int or not 2 <= height <= 8:
        raise ValueError("source rational height must be an integer from 2 through 8")
    return [str(p) if q == 1 else f"{p}/{q}"
            for total in range(2, height + 1) for p in range(1, total)
            if gcd(p, q := total - p) == 1]


def multiset_at(values, length, rank):
    """Unrank combinations with replacement without materializing the grid."""
    if not values or type(length) is not int or length < 0:
        raise ValueError("invalid multiset dimensions")
    count = comb(len(values) + length - 1, length)
    if type(rank) is not int or not 0 <= rank < count:
        raise ValueError("multiset rank out of bounds")
    result, start = [], 0
    for remaining in range(length - 1, -1, -1):
        for i in range(start, len(values)):
            size = comb(len(values) - i + remaining - 1, remaining)
            if rank < size:
                result.append(values[i])
                start = i
                break
            rank -= size
    return result


def diagonal_pair(rank, rows, columns):
    """Unrank a finite rectangle in diagonals, advancing both argument lists."""
    if (type(rows) is not int or type(columns) is not int or min(rows, columns) < 1
            or type(rank) is not int or not 0 <= rank < rows * columns):
        raise ValueError("rectangle rank out of bounds")

    def triangle(n):
        return (n + 1) * (n + 2) // 2 if n >= 0 else 0

    def through(d):
        return triangle(d) - triangle(d - rows) - triangle(d - columns) + triangle(d - rows - columns)

    lo, hi = 0, rows + columns - 2
    while lo < hi:
        middle = (lo + hi) // 2
        if through(middle) > rank:
            hi = middle
        else:
            lo = middle + 1
    row = max(0, lo - columns + 1) + rank - through(lo - 1)
    return row, lo - row


class SeriesSourceProposals:
    def __init__(self, *, every=1, height=5, max_order=4):
        if type(every) is not int or every < 1:
            raise ValueError("source proposal interval must be positive")
        if type(max_order) is not int or not 1 <= max_order <= 5:
            raise ValueError("source operator order must be from 1 through 5")
        self.values = rational_alphabet(height)
        self.every, self.height, self.max_order, self.round = every, height, max_order, 0
        self.agenda, self.shapes = ResearchIndexedAgenda(), []
        for b in range(max_order):
            for a in range(1, b + 2):
                left = comb(len(self.values) + a - 1, a)
                right = comb(len(self.values) + b - 1, b)
                self.agenda.admit(f"hyper:{a}:{b}", left * right)
                self.shapes.append((a, b, left, right))

    def offer(self):
        round_index = self.round
        self.round += 1
        before = self.agenda.digest()
        item = self.agenda.pop() if round_index % self.every == 0 else None
        receipt = {"round": round_index, "before_sha256": before,
                   "after_sha256": self.agenda.digest(), "item": item,
                   "scheduled": round_index % self.every == 0}
        if item is None:
            return None, receipt
        a, b, left, right = self.shapes[item["stream_id"]]
        i, j = diagonal_pair(item["offset"], left, right)
        program = {"op": "hyper", "a": multiset_at(self.values, a, i),
                   "b": multiset_at(self.values, b, j)}
        validate(program)
        return {"program": program, "parents": [], "proposal_origin": "enumerated_source",
                "source_construction": {"shape": [a, b], "parameter_ranks": [i, j],
                                        "item": item}}, receipt

    def snapshot(self):
        return {"schema": "mortra.series-source-proposals.v1", "every": self.every,
                "height": self.height, "max_order": self.max_order, "round": self.round,
                "parameters": list(self.values), "agenda": self.agenda.snapshot(),
                "new_mathematical_language_claimed": False}
