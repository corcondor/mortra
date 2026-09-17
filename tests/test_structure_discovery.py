"""Structures that change the order of a computation, and what may not be claimed about them.

The tests check three things about every structure: that it was found rather than
supplied, that it is exact for every input and not only for the ones it was found
on, and that the cheap route returns exactly what the expensive route returns.
"""
from fractions import Fraction
import random

import pytest

from math_os_prototype import structure_discovery as sd
from math_os_prototype import structure_families as fam
from math_os_prototype.algebraic_structures import OperationCounter, SparseMatrix


# ---------------------------------------------------------------------------
# Merging: histories that need not be told apart
# ---------------------------------------------------------------------------

def test_merging_finds_the_dimension_the_description_hides():
    """A description keeping the last ten symbols has 1024 states; the count needs two."""
    family = fam.window_family(10)
    assert family.dimension == 1024
    structure = fam.discover(family)
    assert structure["merged_dimension"] == 2
    assert structure["reachable_dimension"] <= family.dimension


def test_merging_preserves_every_word_and_not_only_the_sampled_ones():
    family = fam.window_family(4)
    summed = family.matrices[0]
    for matrix in family.matrices[1:]:
        summed = summed.add(matrix)
    representation = sd.minimal_representation([summed], family.start, family.functional)
    for length in range(7):
        original = sd.word_value([summed], family.start, family.functional, [0]*length)
        reduced = sd.word_value(representation["matrices"], representation["start"],
                                representation["functional"], [0]*length)
        assert original == reduced
    # the certificate is the invariance that makes this hold for every word
    reachable = sd.reachable_subspace([summed], family.start)
    for column in reachable.columns:
        image = summed.apply(dict(column))
        assert sd._span_solve(reachable, image) is not None
    rows = sd.invariant_row_space([summed], family.functional)
    for index in range(rows.ncols):
        image = sd.transpose(summed).apply(dict(rows.columns[index]))
        assert not image or sd._span_solve(rows, image) is not None


def test_merging_reports_when_there_is_nothing_to_merge():
    """A representation that is already minimal comes back unchanged, not compressed."""
    cycle = SparseMatrix.from_rows([[0, 0, 1], [1, 0, 0], [0, 1, 0]])
    watching_one_state = sd.minimal_representation([cycle], sd.unit(0), {0: Fraction(1)})
    assert watching_one_state["dimension"] == 3
    # the same operations with a functional that cannot tell the states apart do merge,
    # because then no word distinguishes them
    watching_the_sum = sd.minimal_representation([cycle], sd.unit(0),
                                                 {index: Fraction(1) for index in range(3)})
    assert watching_the_sum["dimension"] == 1


# ---------------------------------------------------------------------------
# Relations: an iteration of length L becomes a remainder
# ---------------------------------------------------------------------------

def test_the_relation_is_discovered_certified_and_holds_for_every_start():
    family = fam.window_family(6)
    structure = fam.discover(family)
    assert structure["degree"] == 2
    assert [str(c) for c in structure["relation"]["coefficients"]] == ["1", "1"]   # x^2 = x + 1
    assert structure["certified"] and structure["holds_for_every_start"]


def test_the_cheap_route_returns_what_the_iteration_returns_at_lengths_never_used():
    """The structure is found from the operations; no length is seen while finding it."""
    family = fam.window_family(4)
    structure = fam.discover(family)
    rng = random.Random(20260918)
    for length in [0, 1, 2, 3, 7, 33] + [rng.randrange(100, 5000) for _ in range(5)]:
        assert fam.count_by_structure(structure, length) == fam.count_by_iteration(family, length)


def test_the_cheap_route_agrees_with_an_independent_matrix_power():
    family = fam.window_family(5)
    structure = fam.discover(family)
    for length in (16, 64, 257):
        assert fam.count_by_structure(structure, length) == fam.reference_count(family, length)


def test_the_cheap_route_costs_less_as_the_length_grows():
    family = fam.window_family(6)
    structure = fam.discover(family)
    ratios = []
    for length in (256, 4096, 65536):
        iteration, compiled = OperationCounter(), OperationCounter()
        fam.count_by_iteration(family, length, counter=iteration)
        fam.count_by_structure(structure, length, counter=compiled)
        assert iteration["total"] > compiled["total"]
        ratios.append(iteration["total"]/compiled["total"])
    assert ratios[0] < ratios[1] < ratios[2]


def test_a_zero_start_is_reported_rather_than_divided_by():
    family = fam.window_family(3)
    empty = fam.Family("empty", family.matrices, {}, family.functional)
    structure = fam.discover(empty)
    assert structure["degree"] == 0
    assert fam.count_by_structure(structure, 1000) == 0


def test_a_relation_that_does_not_hold_is_refused():
    matrix = SparseMatrix.from_rows([[0, 1], [1, 1]])
    assert not sd.certify_relation(matrix, sd.unit(0), [Fraction(1), Fraction(0)])
    assert sd.certify_operator_relation(matrix, [Fraction(1), Fraction(1)])       # x^2 = x + 1


# ---------------------------------------------------------------------------
# Autonomy: the procedure, not a remembered answer
# ---------------------------------------------------------------------------

def test_discovery_works_on_families_generated_after_it_was_written():
    """Random operation systems: whatever dimension they have is found and reported."""
    rng = random.Random(4)
    for seed in range(4):
        size = 9
        matrices = []
        for _ in range(2):
            columns = [dict() for _ in range(size)]
            for source in range(size):
                for target in rng.sample(range(size), rng.randint(0, 2)):
                    columns[source][target] = Fraction(rng.randint(1, 2))
            matrices.append(SparseMatrix(size, columns))
        family = fam.Family(f"random {seed}", matrices, {rng.randrange(size): Fraction(1)},
                            {index: Fraction(1) for index in rng.sample(range(size), 3)})
        structure = fam.discover(family)
        assert structure["merged_dimension"] <= family.dimension
        for length in (5, 17, 64):
            assert fam.count_by_structure(structure, length) == fam.count_by_iteration(family, length)


def test_the_same_structure_answers_a_family_it_was_not_discovered_on():
    """Merging and the relation are statements about the operations, not about one question."""
    family = fam.window_family(4)
    structure = fam.discover(family)
    other = fam.window_family(4)
    other.start = {index: Fraction(1) for index in range(4)}
    assert structure["holds_for_every_start"]
    operator = structure["representation"]["matrices"][0]
    assert sd.certify_operator_relation(operator, structure["relation"]["coefficients"])


# ---------------------------------------------------------------------------
# Decomposition: fewer multiplications, and the exponent that follows
# ---------------------------------------------------------------------------

def test_a_flip_never_changes_the_tensor():
    tensor = sd.matrix_multiplication_tensor(2, 2, 2)
    terms = sd.reduce_decomposition(sd.trivial_decomposition(tensor))
    rng = random.Random(1)
    for _ in range(200):
        index, other = rng.randrange(len(terms)), rng.randrange(len(terms))
        if index == other:
            continue
        flipped = sd.flip(terms, index, other, rng.randrange(3), rng)
        if flipped is None:
            continue
        terms = sd.reduce_decomposition(flipped)
        assert not sd.decomposition_error(tensor, terms)


def test_the_search_finds_seven_multiplications_for_two_by_two():
    """Told only the target rank, the walk leaves the obvious eight."""
    tensor = sd.matrix_multiplication_tensor(2, 2, 2)
    assert len(sd.binary_terms(tensor)) == 8
    found = sd.search_decomposition(tensor, target_rank=7, steps=200000, seed=0)
    assert found["rank"] == 7 and found["exact_over_gf2"]


def test_the_discovery_is_lifted_to_an_exact_rational_decomposition():
    tensor = sd.matrix_multiplication_tensor(2, 2, 2)
    found = sd.search_decomposition(tensor, target_rank=7, steps=200000, seed=0)
    lifted = sd.lift_to_rationals(tensor, found["terms"])
    assert lifted is not None and lifted["rank"] == 7
    assert sd.decomposition_error(tensor, lifted["terms"]) == {}


def test_the_recursion_built_from_the_discovery_returns_the_same_product():
    tensor = sd.matrix_multiplication_tensor(2, 2, 2)
    found = sd.search_decomposition(tensor, target_rank=7, steps=200000, seed=0)
    terms = sd.lift_to_rationals(tensor, found["terms"])["terms"]
    rng = random.Random(11)
    for depth in (1, 2, 3):
        size = 2**depth
        A = [[Fraction(rng.randint(-3, 3)) for _ in range(size)] for _ in range(size)]
        B = [[Fraction(rng.randint(-3, 3)) for _ in range(size)] for _ in range(size)]
        discovered, obvious = OperationCounter(), OperationCounter()
        product = sd.recursive_multiply(terms, 2, A, B, size, counter=discovered)
        assert product == sd.naive_multiply(A, B, size, counter=obvious)
        assert discovered["execute:multiply"] == 7**depth
        assert obvious["baseline:multiply"] == 8**depth


def test_the_exponent_of_the_discovered_recursion_is_below_three():
    assert sd.exponent(7, 2) == pytest.approx(2.807354922, abs=1e-6)
    assert sd.exponent(8, 2) == pytest.approx(3.0)
    assert sd.exponent(7, 2) < 3


def test_the_extra_additions_are_counted_and_not_hidden():
    """The discovered recursion buys multiplications with additions; both are charged."""
    tensor = sd.matrix_multiplication_tensor(2, 2, 2)
    found = sd.search_decomposition(tensor, target_rank=7, steps=200000, seed=0)
    terms = sd.lift_to_rationals(tensor, found["terms"])["terms"]
    rng = random.Random(3)
    size = 4
    A = [[Fraction(rng.randint(-2, 2)) for _ in range(size)] for _ in range(size)]
    B = [[Fraction(rng.randint(-2, 2)) for _ in range(size)] for _ in range(size)]
    discovered, obvious = OperationCounter(), OperationCounter()
    sd.recursive_multiply(terms, 2, A, B, size, counter=discovered)
    sd.naive_multiply(A, B, size, counter=obvious)
    assert discovered["execute:multiply"] < obvious["baseline:multiply"]
    assert discovered["execute:add"] > obvious["baseline:add"]


# ---------------------------------------------------------------------------
# The system decides for itself which structure to use
# ---------------------------------------------------------------------------

def test_the_system_decides_to_compile_where_the_structure_pays():
    report = fam.autonomous_search(fam.window_family(8), target_length=4096)
    assert report["decision"].startswith("compile")
    assert report["priced_at"]["structure"] < report["priced_at"]["iterate"]
    assert report["priced_at"]["same_answer"] and report["agrees_on_short_lengths"]
    kinds = [attempt["structure"] for attempt in report["attempts"]]
    assert kinds == ["merging", "relation"]


def test_the_system_reports_a_description_that_does_not_merge():
    """Six states watched at one of them: nothing merges, and the run says so."""
    cycle = SparseMatrix.from_rows([[0, 0, 0, 0, 0, 1], [1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0],
                                    [0, 0, 1, 0, 0, 0], [0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 1, 0]])
    family = fam.Family("six-cycle", [cycle], {0: Fraction(1)}, {0: Fraction(1)})
    report = fam.autonomous_search(family, target_length=64)
    merging = report["attempts"][0]
    assert merging["from"] == merging["to"] == 6
    assert report["attempts"][1]["degree"] == 6


def test_the_system_decides_about_a_tensor_and_keeps_the_obvious_one_when_it_must():
    decided = fam.autonomous_bilinear_search(2, steps=200000, seed=0)
    assert decided["searched_rank"] == 7 and decided["lifted_to_rationals"]
    assert decided["decision"].startswith("compile")
    assert decided["exponent"] < decided["obvious_exponent"]
    stubborn = fam.autonomous_bilinear_search(2, target_rank=6, steps=20000, seed=0)
    assert stubborn["searched_rank"] >= 7
    assert stubborn["decision"].startswith(("compile", "use it over GF(2)"))


# ---------------------------------------------------------------------------
# The discovered structure as an operation of the shared contract registry
# ---------------------------------------------------------------------------

def test_a_discovered_structure_is_registered_as_an_operation_with_its_proof():
    from math_os_prototype import structure_contracts as sc
    from math_os_prototype import operation_contracts as oc
    family = fam.window_family(6)
    session, structure, contract = sc.discovered_session(family, verify_derivations=True)
    assert contract.provenance == oc.ACQUIRED and contract.parents == ("count_by_iterating",)
    assert contract.derivation["kind"] == "structure"
    assert contract.derivation["relation_certified"]
    assert contract.derivation["merged_dimension"] < contract.derivation["given_dimension"]
    result = session.apply(contract, {"F": family, "L": 64})
    guarantee = result.certificate_step["post"][0]
    assert guarantee["status"] == "certified" and guarantee["justification"]["verified_exactly"]
    assert result.value == fam.count_by_iteration(family, 64)


def test_the_registered_operation_costs_far_less_than_the_route_it_replaces():
    from math_os_prototype import structure_contracts as sc
    family = fam.window_family(6)
    session, _, contract = sc.discovered_session(family)
    iterating = sc.structure_registry().contracts["count_by_iterating"]
    plain = sc.Session(sc.structure_registry())
    before = session.counter["total"]
    cheap = session.apply(contract, {"F": family, "L": 8192})
    cheap_cost = session.counter["total"]-before
    before = plain.counter["total"]
    expensive = plain.apply(iterating, {"F": family, "L": 8192})
    assert cheap.value == expensive.value
    assert cheap_cost*100 < plain.counter["total"]-before


def test_the_registered_operation_refuses_a_family_it_was_not_discovered_on():
    from math_os_prototype import structure_contracts as sc
    family = fam.window_family(6)
    session, _, contract = sc.discovered_session(family)
    assert session.apply(contract, {"F": fam.typed_skeleton_family(), "L": 16}) is None
