"""Problem families whose size grows, and the three ways of answering them.

A family fixes an operation system and asks the same question for every length L:
how many operation sequences of length L does it accept? Three routes answer it,
and they are what the measurements compare.

    enumerate   every sequence, one at a time: exponential in L, and the thing
                MORTRA's own search does when it re-derives the same partial
                result along thousands of plans;
    iterate     the bracket identity: sum over all sequences at once by applying
                the sum of the operations L times. Linear in L;
    compile     the discovered structure: merge the states that need not be told
                apart, find the polynomial relation, and evaluate x^L mod p.
                Logarithmic in L, after a discovery that happens once.

The point of a family is that a structure is discovered from the operations, not
from any one L. The same certified structure answers every L, including the ones
no discovery run ever saw.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import product

from math_os_prototype import algebraic_operation_domain as dom
from math_os_prototype import structure_discovery as sd
from math_os_prototype.algebraic_structures import OperationCounter, SparseMatrix


# ---------------------------------------------------------------------------
# A family: an operation system, a start, and what counts as accepted
# ---------------------------------------------------------------------------

class Family:
    """States, operations as matrices over those states, a start vector and a functional."""

    def __init__(self, name, matrices, start, functional, *, states=None, note=""):
        self.name = name
        self.matrices = matrices
        self.start = start
        self.functional = functional
        self.states = states or [str(i) for i in range(matrices[0].nrows)]
        self.note = note

    @property
    def dimension(self):
        return self.matrices[0].nrows

    @property
    def letters(self):
        return len(self.matrices)


def window_family(window, forbidden=("11",), *, name=None):
    """Binary strings with no forbidden factor, described by remembering the last `window` symbols.

    The description is deliberately more detailed than the question needs: it keeps
    the last `window` symbols, so it has 2^window states, while what the answer
    depends on is far smaller. Discovering how much smaller is the task.
    """
    states = ["".join(bits) for bits in product("01", repeat=window)]
    index = {state: i for i, state in enumerate(states)}
    matrices = []
    for symbol in "01":
        columns = [dict() for _ in states]
        for state in states:
            nxt = (state+symbol)[1:]
            if any(pattern in state+symbol for pattern in forbidden):
                continue
            columns[index[state]][index[nxt]] = Fraction(1)
        matrices.append(SparseMatrix(len(states), columns))
    start = {index["0"*window]: Fraction(1)}
    functional = {i: Fraction(1) for i in range(len(states))}
    return Family(name or f"binary strings avoiding {'/'.join(forbidden)}, last {window} symbols kept",
                  matrices, start, functional, states=states,
                  note="the description keeps more history than the count depends on")


def typed_skeleton_family(*, name="typed operation skeletons"):
    """MORTRA's own vocabulary: how many operation skeletons of length L end in a basis?

    States are the sorts of the shared operation contract; letters are the given
    contracts that take one argument. This is the shape of the search space the
    planner walks, with the values left out.
    """
    registry = dom.base_registry()
    unary = [contract for contract in registry.by_provenance("given") if len(contract.params) == 1]
    sorts = sorted({sort for contract in unary for sort in (contract.params[0][1], contract.result)})
    index = {sort: i for i, sort in enumerate(sorts)}
    matrices = []
    for contract in unary:
        columns = [dict() for _ in sorts]
        columns[index[contract.params[0][1]]][index[contract.result]] = Fraction(1)
        matrices.append(SparseMatrix(len(sorts), columns))
    start = {index["Map"]: Fraction(1)}
    functional = {index["Basis"]: Fraction(1)}
    return Family(name, matrices, start, functional, states=sorts,
                  note="letters are the unary given contracts: "+", ".join(c.name for c in unary))


# ---------------------------------------------------------------------------
# The three routes
# ---------------------------------------------------------------------------

def count_by_enumeration(family, length, *, counter=None, budget=None):
    """One sequence at a time: the cost that grows like (number of operations)^L."""
    total = Fraction(0)
    for word in product(range(family.letters), repeat=length):
        vector = dict(family.start)
        for letter in word:
            vector = family.matrices[letter].apply(vector, counter)
            if counter is not None:
                counter.charge("enumerate")
        total += sd.pair(family.functional, vector, counter, "enumerate")
        if budget is not None and counter is not None and counter["total"] > budget:
            raise sd.NoStructure("enumeration exceeded the budget")
    return total


def count_by_iteration(family, length, *, counter=None):
    """All sequences at once, by applying the sum of the operations L times."""
    total = family.matrices[0]
    for matrix in family.matrices[1:]:
        total = total.add(matrix)
    vector = dict(family.start)
    for _ in range(length):
        vector = total.apply(vector, counter)
        if counter is not None:
            counter.charge("iterate")
    return sd.pair(family.functional, vector, counter, "iterate")


def discover(family, *, counter=None, budget=None):
    """Merge what need not be told apart, then find the relation that collapses the iteration."""
    counter = counter if counter is not None else OperationCounter()
    summed = family.matrices[0]
    for matrix in family.matrices[1:]:
        summed = summed.add(matrix)
    if not family.start:
        counter.charge("discover")
        return {"family": family.name, "given_dimension": family.dimension,
                "merged_dimension": 0, "reachable_dimension": 0, "hidden_dimension": 0,
                "degree": 0, "coefficients": [], "initial_values": [],
                "representation": {"matrices": [], "start": {}, "functional": {}},
                "relation": {"degree": 0, "coefficients": [], "vectors": []},
                "certified": True, "holds_for_every_start": True,
                "certificate": {"rule": "the start is the zero vector, so every word has value zero"}}
    representation = sd.minimal_representation([summed], family.start, family.functional,
                                               budget=budget, counter=counter)
    operator = representation["matrices"][0]
    relation = sd.krylov_relation(operator, representation["start"], counter=counter)
    values = [sd.pair(representation["functional"], vector, counter, "discover")
              for vector in relation["vectors"]]
    certified = sd.certify_relation(operator, representation["start"], relation["coefficients"],
                                    counter=counter)
    for_every_start = sd.certify_operator_relation(operator, relation["coefficients"], counter=counter)
    if not certified:
        raise sd.NoStructure("the relation did not certify")
    return {"family": family.name, "given_dimension": family.dimension,
            "merged_dimension": representation["dimension"],
            "reachable_dimension": representation["reachable_dimension"],
            "hidden_dimension": representation["hidden_dimension"],
            "degree": relation["degree"],
            "coefficients": [str(c) for c in relation["coefficients"]],
            "initial_values": values, "representation": representation, "relation": relation,
            "certified": certified, "holds_for_every_start": for_every_start,
            "certificate": representation["certificate"]}


def count_by_structure(structure, length, *, counter=None):
    """x^L mod p, then one combination of the first values.

    A relation of degree zero says the start is already zero: every length answers
    zero, and there is nothing to raise to a power.
    """
    if structure["degree"] == 0:
        if counter is not None:
            counter.charge("execute")
        return Fraction(0)
    remainder = sd.polynomial_remainder_power(structure["relation"]["coefficients"], length,
                                              counter=counter)
    return sd.value_from_relation(structure["initial_values"], remainder, counter=counter)


# ---------------------------------------------------------------------------
# An independent answer, for auditing
# ---------------------------------------------------------------------------

def autonomous_search(family, *, target_length=1 << 16, budget=None, counter=None, sample=(3, 5, 8)):
    """Try the structures, certify what is found, and decide which route to use.

    Nothing about the family is assumed. Merging is attempted; the relation is
    attempted on what merging leaves; each is kept only if it certifies. The
    decision to compile is made by comparing the cost the two routes would have at
    the target length, measured rather than predicted, and the decision is reported
    together with the evidence for it.
    """
    counter = counter if counter is not None else OperationCounter()
    report = {"family": family.name, "given_dimension": family.dimension, "attempts": []}
    before = counter["total"]
    try:
        structure = discover(family, counter=counter, budget=budget)
    except sd.NoStructure as refusal:
        report["attempts"].append({"structure": "merging and relation", "found": False,
                                   "reason": str(refusal)})
        report["decision"] = "iterate: no structure certified"
        report["discovery_operations"] = counter["total"]-before
        return report
    report["discovery_operations"] = counter["total"]-before
    report["attempts"].append({
        "structure": "merging", "found": True,
        "from": family.dimension, "to": structure["merged_dimension"],
        "certificate": structure["certificate"]["rule"]})
    report["attempts"].append({
        "structure": "relation", "found": structure["degree"] > 0,
        "degree": structure["degree"], "coefficients": structure["coefficients"],
        "certified": structure["certified"], "for_every_start": structure["holds_for_every_start"]})

    # the two routes are priced at a length neither of them was discovered on
    iteration, compiled = OperationCounter(), OperationCounter()
    by_iteration = count_by_iteration(family, target_length, counter=iteration)
    by_structure = count_by_structure(structure, target_length, counter=compiled)
    agreed = by_iteration == by_structure
    report["priced_at"] = {"length": target_length, "iterate": iteration["total"],
                           "structure": compiled["total"], "same_answer": agreed}
    checked = []
    for length in sample:
        checked.append(count_by_structure(structure, length) == count_by_iteration(family, length))
    report["agrees_on_short_lengths"] = all(checked)
    if agreed and all(checked) and compiled["total"] < iteration["total"]:
        report["decision"] = "compile: the certified structure answers the family more cheaply"
        report["structure"] = structure
    else:
        report["decision"] = "iterate: the structure did not pay at this length"
    return report


def autonomous_bilinear_search(n=2, *, target_rank=None, steps=200000, seed=0, counter=None):
    """Try to find a bilinear decomposition below the obvious rank, and decide whether to use it."""
    counter = counter if counter is not None else OperationCounter()
    tensor = sd.matrix_multiplication_tensor(n, n, n)
    obvious = len(sd.binary_terms(tensor))
    target = target_rank if target_rank is not None else obvious-1
    found = sd.search_decomposition(tensor, target_rank=target, steps=steps, seed=seed, counter=counter)
    report = {"tensor": f"{n}x{n} matrix multiplication", "obvious_rank": obvious,
              "searched_rank": found["rank"], "exact_over_gf2": found["exact_over_gf2"],
              "history": found["history"], "discovery_operations": counter["total"]}
    if found["rank"] >= obvious:
        report["decision"] = "keep the obvious algorithm: nothing smaller was found"
        return report
    lifted = sd.lift_to_rationals(tensor, found["terms"], counter=counter)
    report["lifted_to_rationals"] = lifted is not None
    if lifted is None:
        report["decision"] = ("use it over GF(2) only: the rank is lower there and no lift to the "
                              "rationals was found")
        report["exponent_over_gf2"] = sd.exponent(found["rank"], n)
        return report
    report["residual_over_the_rationals"] = sd.decomposition_error(tensor, lifted["terms"])
    report["exponent"] = sd.exponent(lifted["rank"], n)
    report["obvious_exponent"] = sd.exponent(obvious, n)
    report["terms"] = lifted["terms"]
    report["decision"] = ("compile the recursion from the discovered decomposition: it is exact over "
                          "the rationals and uses fewer multiplications")
    return report


def reference_count(family, length):
    """The same question answered by repeated squaring of the full transition matrix.

    This is not the route under test: it keeps every state of the given
    description and multiplies matrices, so it audits the answer without sharing
    the discovered structure.
    """
    summed = family.matrices[0]
    for matrix in family.matrices[1:]:
        summed = summed.add(matrix)
    size = summed.nrows
    power = [[Fraction(1) if i == j else Fraction(0) for j in range(size)] for i in range(size)]
    base = [[Fraction(0)]*size for _ in range(size)]
    for j, column in enumerate(summed.columns):
        for i, value in column.items():
            base[i][j] = value

    def multiply(left, right):
        result = [[Fraction(0)]*size for _ in range(size)]
        for i in range(size):
            for k in range(size):
                if not left[i][k]:
                    continue
                for j in range(size):
                    if right[k][j]:
                        result[i][j] += left[i][k]*right[k][j]
        return result

    exponent = length
    while exponent:
        if exponent & 1:
            power = multiply(power, base)
        exponent >>= 1
        if exponent:
            base = multiply(base, base)
    total = Fraction(0)
    for i, weight in family.functional.items():
        for j, value in family.start.items():
            total += weight*power[i][j]*value
    return total
