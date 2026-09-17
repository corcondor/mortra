"""The shared operation contract, the acquisition loop, and what may not be claimed.

Every test states what is checked rather than that something "works": a composed
operation is refused unless its guarantee is derived and its preconditions are
carried, and an operation acquired on one problem is executed again on another.
"""
from fractions import Fraction

import pytest

from math_os_prototype import algebraic_operation_domain as dom
from math_os_prototype import algebraic_structures as alg
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_relational_edit as edit
from math_os_prototype import operation_acquisition as acq
from math_os_prototype import operation_contracts as oc
from math_os_prototype import operation_integration as oi

TRIANGLE_WITH_LOOP = alg.closure([(0, 1, 2), (0, 3), (1, 3)])
TWO_TRIANGLES = alg.closure([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2, 4), (2, 4, 5)])
TWO_CIRCLES = alg.closure([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)])
SPHERE = {"variables": ["x", "y", "z"], "polynomials": ["x**2 + y**2 + z**2 - 1"]}
SPHERE_AND_PLANE = {"variables": ["x", "y", "z"], "polynomials": ["x**2 + y**2 + z**2 - 1", "z"]}
ON_SPHERE = (Fraction(1), Fraction(0), Fraction(0))


def complex_of(facets):
    return alg.simplicial_chain_complex(facets)


def first_task(session, complex_):
    """The first integration task: ker(A) / im(B) under A B = 0, with A B = 0 as the hypothesis."""
    A, B = complex_.d(1), complex_.d(2)
    session.context.assume("zero_composition",
                           [session.registry.object_id("Map", A), session.registry.object_id("Map", B)],
                           source="task hypothesis A B = 0")
    inputs = {"A": ("Map", A), "B": ("Map", B)}
    solution = oi.solve_specification(session, "homology_of", inputs, max_states=800)
    return solution, inputs


def with_first_generation(*, verify_derivations=False):
    session = oi.new_session(verify_derivations=verify_derivations)
    solution, inputs = first_task(session, complex_of(TRIANGLE_WITH_LOOP))
    contract = oi.acquire_from(session, solution, inputs, name="homology_pair", specification="homology_of")
    return session, contract, solution


# ---------------------------------------------------------------------------
# The first integration task
# ---------------------------------------------------------------------------

def test_the_quotient_is_composed_from_the_given_contracts_not_supplied():
    """No given contract produces ker(A)/im(B); the planner composes kernel, image and quotient."""
    session = oi.new_session(verify_derivations=True)
    complex_ = complex_of(TRIANGLE_WITH_LOOP)
    assert not any(contract.post and contract.post[0].predicate == "homology_of"
                   for contract in session.registry.by_provenance(oc.GIVEN))
    solution, _ = first_task(session, complex_)
    assert solution["solved"]
    assert [step["contract"] for step in solution["plan"].proof_program] == [
        "kernel_basis", "image_basis", "quotient_basis"]
    quotient = solution["plan"].goals["Quotient"].value
    assert quotient["dimension"] == alg.homology(complex_, 1)["betti"]


def test_a_composite_is_refused_unless_its_guarantee_follows_from_its_steps():
    session, _, _ = with_first_generation()
    body = {"params": ["A", "B"], "steps": [{"out": "t1", "prim": "kernel_basis", "args": ["A"]}],
            "result": "t1"}
    with pytest.raises(acq.AcquisitionRefused):
        acq.acquire(session, name="not_a_quotient", body=body,
                    parameters=[("A", "Map"), ("B", "Map")], specification="homology_of",
                    spec_binding={"A": "A", "B": "B"},
                    bindings={"A": "Map.absent", "B": "Map.absent"}, result_id="Quotient.absent",
                    result_sort="Quotient")


def test_the_acquired_operation_carries_the_precondition_it_did_not_prove():
    """A B = 0 was a hypothesis about two matrices, so it becomes a precondition of the operation."""
    session, contract, _ = with_first_generation()
    assert contract.provenance == oc.ACQUIRED and contract.generation == 1
    assert [condition.as_json() for condition in contract.pre] == [["zero_composition", ["A", "B"]]]
    assert [condition.as_json() for condition in contract.post] == [["homology_of", ["A", "B", "v"]]]
    other = complex_of(TWO_TRIANGLES)
    assert session.apply(contract, {"A": other.d(1), "B": other.d(1)}) is None


def test_the_acquired_operation_is_a_program_that_expands_to_given_contracts():
    session, contract, _ = with_first_generation()
    assert contract.body["steps"] and all("prim" in step for step in contract.body["steps"])
    expansion = acq.expand(session.registry, contract.body)
    assert all(session.registry.contracts[step["prim"]].provenance == oc.GIVEN
               for step in expansion["steps"])
    complex_ = complex_of(TWO_TRIANGLES)
    arguments = {"A": complex_.d(1), "B": complex_.d(2)}
    from_body = acq.execute_body(session, contract.body, arguments)
    from_expansion = acq.execute_body(session, expansion, arguments)
    assert (session.registry.object_id("Quotient", from_body)
            == session.registry.object_id("Quotient", from_expansion))


# ---------------------------------------------------------------------------
# Later goals, and the second generation
# ---------------------------------------------------------------------------

def test_the_acquired_operation_is_used_for_the_homology_of_a_complex():
    session, _, _ = with_first_generation(verify_derivations=True)
    complex_ = complex_of(TWO_TRIANGLES)
    inputs = {"C": ("Complex", complex_), "q": ("Degree", 1)}
    solution = oi.solve_specification(session, "homology_at", inputs, max_states=4000)
    assert solution["solved"] and "homology_pair" in [s["contract"] for s in solution["plan"].proof_program]
    second = oi.acquire_from(session, solution, inputs, name="homology_at_degree",
                             specification="homology_at", parents=["homology_pair"])
    assert second.generation == 2 and second.parents == ("homology_pair",)
    assert any(step["prim"] == "homology_pair" for step in second.body["steps"])
    assert [c.as_json() for c in second.pre] == [["complex_differentials_vanish", ["C"]]]
    assert solution["plan"].goals["Quotient"].value["dimension"] == alg.homology(complex_, 1)["betti"]


def test_the_same_acquired_operation_serves_a_tangent_space_problem():
    """ker(J of the subsystem) / im(basis of ker J): the tangent directions the extra equations remove."""
    session, _, _ = with_first_generation(verify_derivations=True)
    inputs = {"S": ("System", SPHERE), "T": ("System", SPHERE_AND_PLANE), "p": ("Point", ON_SPHERE)}
    solution = oi.solve_specification(session, "tangent_quotient", inputs, max_states=9000)
    assert solution["solved"] and "homology_pair" in [s["contract"] for s in solution["plan"].proof_program]
    third = oi.acquire_from(session, solution, inputs, name="tangent_gap",
                            specification="tangent_quotient", parents=["homology_pair"])
    assert third.generation == 2 and third.parents == ("homology_pair",)
    assert {c.predicate for c in third.pre} == {"vanishes_at", "subsystem"}
    functions = dom.system_callables(SPHERE), dom.system_callables(SPHERE_AND_PLANE)
    outer = alg.tangent_space(functions[0], ON_SPHERE)["dimension"]
    inner = alg.tangent_space(functions[1], ON_SPHERE)["dimension"]
    assert solution["plan"].goals["Quotient"].value["dimension"] == outer-inner


def test_an_acquired_operation_runs_on_inputs_it_was_not_acquired_on():
    session, contract, _ = with_first_generation()
    for facets, degree in [(TWO_TRIANGLES, 1), (TWO_CIRCLES, 1), (TRIANGLE_WITH_LOOP, 1)]:
        complex_ = complex_of(facets)
        value = acq.execute_body(session, contract.body, {"A": complex_.d(1), "B": complex_.d(2)})
        assert value["dimension"] == alg.homology(complex_, degree)["betti"]


def test_reaching_a_later_goal_costs_less_with_the_acquired_operation():
    """A measurement of this run, not a claim about searches in general."""
    complex_ = complex_of(TWO_TRIANGLES)
    inputs = {"C": ("Complex", complex_), "q": ("Degree", 1)}
    prepared, _, _ = with_first_generation()
    before = prepared.counter["total"]
    with_acquired = oi.solve_specification(prepared, "homology_at", inputs, max_states=4000)
    reused = {"states": sum(a["states"] for a in with_acquired["attempts"]),
              "operations": prepared.counter["total"]-before}
    bare = oi.new_session()
    start = bare.counter["total"]
    given_only = oi.solve_specification(bare, "homology_at", inputs, max_states=4000)
    alone = {"states": sum(a["states"] for a in given_only["attempts"]),
             "operations": bare.counter["total"]-start}
    assert with_acquired["solved"] and given_only["solved"]
    assert reused["states"] < alone["states"] and reused["operations"] < alone["operations"]


# ---------------------------------------------------------------------------
# Editing an acquired operation and re-certifying it
# ---------------------------------------------------------------------------

def test_an_acquired_operation_can_be_generalised_instantiated_and_recertified():
    session, _, _ = with_first_generation()
    complex_ = complex_of(TWO_TRIANGLES)
    inputs = {"C": ("Complex", complex_), "q": ("Degree", 1)}
    solution = oi.solve_specification(session, "homology_at", inputs, max_states=4000)
    second = oi.acquire_from(session, solution, inputs, name="homology_at_degree",
                             specification="homology_at", parents=["homology_pair"])
    step = next(s for s in second.body["steps"] if s["prim"] == "differential")
    higher = oi.abstract_step(session, second, step["out"])
    parameter = higher["params"][-1]
    assert parameter["sort"] == "Op" and parameter["interface"] == [["differential_of", ["i0", "i1", "o"]]]
    with pytest.raises(edit.EditRefused):
        oi.instantiate(session, higher, {"op0": "compose_maps"})
    definition = oi.instantiate(session, higher, {"op0": "differential"})
    assert definition["certification"].startswith("pending")
    reacquired = oi.reacquire(session, definition, inputs, name="homology_at_degree_again",
                              specification="homology_at", parents=["homology_at_degree"])
    assert reacquired.generation == 3 and reacquired.provenance == oc.ACQUIRED
    assert acq.expand(session.registry, reacquired.body) == acq.expand(session.registry, second.body)


def test_editing_a_body_into_one_that_does_not_meet_the_specification_is_refused():
    session, contract, _ = with_first_generation()
    without_the_quotient = {"params": ["A", "B"], "steps": contract.body["steps"][:2], "result": "t2"}
    complex_ = complex_of(TWO_TRIANGLES)
    inputs = {"A": ("Map", complex_.d(1)), "B": ("Map", complex_.d(2))}
    with pytest.raises((acq.AcquisitionRefused, KeyError, TypeError)):
        oi.reacquire(session, {"body": without_the_quotient}, inputs, name="truncated",
                     specification="homology_of")


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def test_a_candidate_guarantee_never_discharges_another_operations_precondition():
    """Observed on the instances run so far is not the same as proved, and is not treated as such."""
    session, _, _ = with_first_generation()
    complex_ = complex_of(TWO_TRIANGLES)
    body = {"params": ["A"], "steps": [{"out": "t1", "prim": "kernel_basis", "args": ["A"]}], "result": "t1"}
    candidate = acq.acquire_candidate(session, name="guessed_image", body=body,
                                      parameters=[("A", "Map")],
                                      post=[oc.Condition.of("image_of", "A", "v")], result_sort="Basis")
    assert candidate.provenance == oc.CANDIDATE
    # on this nilpotent matrix the kernel happens to be the image, so the guessed
    # guarantee holds here and nowhere it was not tried
    nilpotent = alg.SparseMatrix.from_rows([[0, 1], [0, 0]])
    result = session.apply(candidate, {"A": nilpotent})
    assert result is not None and all(entry["status"] == "instance" for entry in result.certificate_step["post"])
    assert session.context.lookup("image_of", [session.registry.object_id("Map", nilpotent),
                                               result.certificate_step["objects"]["v"]]) is None
    assert candidate not in session.registry.certified_contracts()
    assert session.apply(candidate, {"A": complex_.d(1)}) is None


def test_the_registry_keeps_the_three_kinds_apart():
    session, _, _ = with_first_generation()
    given = {c.name for c in session.registry.by_provenance(oc.GIVEN)}
    acquired = {c.name for c in session.registry.by_provenance(oc.ACQUIRED)}
    assert "homology_pair" in acquired and "kernel_basis" in given and not given & acquired
    assert all(c.generation == 0 for c in session.registry.by_provenance(oc.GIVEN))
    assert all(c.body is not None and c.derivation for c in session.registry.by_provenance(oc.ACQUIRED))


# ---------------------------------------------------------------------------
# The supplied rules are audited, and the layer does not disturb what was frozen
# ---------------------------------------------------------------------------

def test_every_derived_guarantee_also_passes_its_exact_check():
    """The supplied inference rules are audited against recomputation on these runs."""
    session, _, _ = with_first_generation(verify_derivations=True)
    inputs = {"C": ("Complex", complex_of(TWO_TRIANGLES)), "q": ("Degree", 1)}
    solution = oi.solve_specification(session, "homology_at", inputs, max_states=4000)
    assert solution["solved"]
    derived = [entry for execution in session.executions for entry in execution["post"]
               if entry["justification"].get("kind") == "derivation"]
    assert derived and all(entry["justification"]["verified_exactly"] for entry in derived)


def test_a_guarantee_that_fails_its_check_is_a_defect_not_a_dead_end():
    session = oi.new_session(verify_derivations=True)
    lying = oc.Contract(name="lying_kernel", params=(("A", "Map"),), result="Basis",
                        post=(oc.Condition.of("kernel_of", "A", "v"),),
                        run=lambda binding, counter: alg.SparseMatrix.identity(binding["A"].ncols))
    session.registry.add(lying)
    with pytest.raises(oc.ContractViolation):
        session.apply(lying, {"A": complex_of(TWO_TRIANGLES).d(1)})


def test_the_geometry_edit_calculus_keeps_its_own_domain():
    """The calculus was generalised by a parameter; the geometry default is unchanged."""
    assert edit.GEOMETRY.name == "relational-geometry" and edit.GEOMETRY.id_prefix == "rel."
    family = next(iter(rdsl.primitive_contracts()))
    assert edit.GEOMETRY.arity(family) == len(rdsl.primitive_contracts()[family]["params"])
    assert edit.GEOMETRY.param_sort("A") == "Point"
    contracts = dom.base_registry().contracts
    algebraic = acq.edit_domain(dom.base_registry())
    assert algebraic.has_primitive("kernel_basis") and not algebraic.has_primitive(family)
    assert algebraic.arity("quotient_basis") == len(contracts["quotient_basis"].params)


def test_object_identity_is_content_addressed_within_a_sort():
    registry = dom.base_registry()
    left = alg.SparseMatrix.from_rows([[1, 0], [0, 1]])
    right = alg.SparseMatrix.from_rows([[1, 0], [0, 1]])
    assert registry.object_id("Map", left) == registry.object_id("Map", right)
    assert registry.object_id("Map", left) != registry.object_id("Basis", left)
    assert registry.object_id("Map", left) != registry.object_id("Map", alg.SparseMatrix.identity(3))
