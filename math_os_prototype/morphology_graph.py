"""Typed morphology atlas for semantically continuous problem synthesis.

The atlas connects mathematical representations, not finished problem families.
A cross-domain candidate is valid only when every transition is an explicit
typed edge carrying a mathematical object or invariant. Passing a bare scalar
from an unrelated calculation is deliberately not an edge in this graph.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class MorphologyNode:
    name: str
    theory: str
    description: str


@dataclass(frozen=True)
class MorphologyEdge:
    name: str
    source: str
    target: str
    transport: tuple[str, ...]
    description: str
    requires: tuple[str, ...] = ()


def _node(name: str, theory: str, description: str) -> MorphologyNode:
    return MorphologyNode(name, theory, description)


def _edge(
    name: str,
    source: str,
    target: str,
    transport: tuple[str, ...],
    description: str,
    requires: tuple[str, ...] = (),
) -> MorphologyEdge:
    return MorphologyEdge(name, source, target, transport, description, requires)


NODES: tuple[MorphologyNode, ...] = (
    _node("EuclideanConfiguration", "geometry", "incidence and metric configuration"),
    _node("CoordinateConfiguration", "analytic_geometry", "coordinate realization"),
    _node("ComplexConfiguration", "complex_geometry", "complex coordinate realization"),
    _node("PolynomialFamily", "algebra", "parameterized polynomial equations"),
    _node("QuadraticCoefficientFamily", "algebra", "quadratics indexed by coefficients"),
    _node("CoefficientLattice", "discrete_algebra", "finite coefficient grid"),
    _node("DiscriminantFeasibleLattice", "algebraic_geometry", "grid filtered by root existence"),
    _node("RootConfiguration", "algebra", "roots with multiplicity and symmetry"),
    _node("SymmetricInvariant", "invariant_theory", "symmetric polynomial data"),
    _node("LocusFamily", "analytic_geometry", "locus reconstructed from invariant coordinates"),
    _node("GeometricObservable", "geometry_analysis", "locus and extremal geometric quantity"),
    _node("AntipodalOrbitStructure", "complex_geometry", "root set quotiented into opposite pairs"),
    _node("CardinalityObservable", "combinatorics", "cardinality of a constrained finite class"),
    _node("SemialgebraicRegion", "real_algebraic_geometry", "region cut out by inequalities"),
    _node("MeasureObservable", "analysis", "area or measure of a feasible set"),
    _node("ConditionalMomentObservable", "probability_analysis", "moment restricted to a feasible set"),
    _node("RecurrenceSystem", "discrete_dynamics", "finite-order recurrence"),
    _node("MatrixDynamics", "linear_algebra", "matrix representation of iteration"),
    _node("SpectralData", "spectral_theory", "eigenvalue and eigenspace data"),
    _node("CyclicGroupAction", "group_theory", "finite cyclic symmetry"),
    _node("ResidueClassStructure", "number_theory", "classes modulo an integer"),
    _node("CharacterSum", "harmonic_number_theory", "finite Fourier/character observable"),
    _node("GeneratingFunction", "algebraic_combinatorics", "coefficient encoding"),
    _node("CombinatorialClass", "combinatorics", "finite counted structures"),
    _node("ProbabilitySpace", "probability", "weighted combinatorial class"),
    _node("ExpectationObservable", "probability", "expectation of an observable"),
)


EDGES: tuple[MorphologyEdge, ...] = (
    _edge("CoordinateRealization", "EuclideanConfiguration", "CoordinateConfiguration", ("incidence", "metric"), "choose coordinates while preserving incidence and distance"),
    _edge("ComplexRealization", "EuclideanConfiguration", "ComplexConfiguration", ("incidence", "angle", "cyclic_order"), "encode the same configuration by complex numbers"),
    _edge("EquationEncoding", "CoordinateConfiguration", "PolynomialFamily", ("solution_set", "multiplicity"), "encode geometric constraints as polynomial equations"),
    _edge("ComplexRootEncoding", "ComplexConfiguration", "RootConfiguration", ("point_set", "multiplicity", "cyclic_order"), "view complex points as roots"),
    _edge("RootExtraction", "PolynomialFamily", "RootConfiguration", ("solution_set", "multiplicity"), "pass from coefficients to the root configuration"),
    _edge("InvariantQuotient", "RootConfiguration", "SymmetricInvariant", ("symmetry_orbit", "multiplicity"), "take symmetric invariants of roots"),
    _edge("InvariantLocus", "SymmetricInvariant", "LocusFamily", ("elementary_symmetric_values", "parameter"), "reconstruct a geometric locus from root invariants"),
    _edge("ExtremalObservation", "LocusFamily", "GeometricObservable", ("locus", "feasible_parameter", "objective"), "observe a locus together with an extremal quantity"),
    _edge("AntipodalFactorization", "SymmetricInvariant", "AntipodalOrbitStructure", ("root_set", "even_polynomial", "cyclic_order"), "factor a centrally symmetric unit-root set into opposite pairs", ("unit_roots", "four_distinct_roots", "vanishing_odd_coefficients")),
    _edge("CompatibilityClass", "AntipodalOrbitStructure", "CombinatorialClass", ("opposite_pairs", "compatibility_relation"), "form the class of compatible selections of opposite pairs"),
    _edge("CardinalityObservation", "CombinatorialClass", "CardinalityObservable", ("class_membership", "cardinality"), "count the same constrained class"),
    _edge("CoefficientInstantiation", "QuadraticCoefficientFamily", "CoefficientLattice", ("coefficients", "discriminant"), "instantiate coefficients on a finite grid"),
    _edge("DiscriminantFilter", "CoefficientLattice", "DiscriminantFeasibleLattice", ("coefficients", "real_root_existence"), "retain exactly the real-root coefficient pairs"),
    _edge("ScalingLimit", "DiscriminantFeasibleLattice", "SemialgebraicRegion", ("membership", "boundary", "density"), "rescale the grid while preserving the feasibility inequality"),
    _edge("RegionMeasure", "SemialgebraicRegion", "MeasureObservable", ("membership", "boundary"), "observe area or measure"),
    _edge("RestrictedMoment", "MeasureObservable", "ConditionalMomentObservable", ("measure", "normalization"), "normalize a weighted integral over the same region"),
    _edge("CompanionRepresentation", "RecurrenceSystem", "MatrixDynamics", ("orbit", "initial_state"), "represent recurrence iteration by a matrix"),
    _edge("SpectralDecomposition", "MatrixDynamics", "SpectralData", ("orbit_growth", "periodicity"), "diagonalize or use a canonical matrix form"),
    _edge("CyclicOrbit", "ComplexConfiguration", "CyclicGroupAction", ("cyclic_order", "orbit"), "expose cyclic symmetry of the same point set"),
    _edge("OrbitResidues", "CyclicGroupAction", "ResidueClassStructure", ("orbit", "period"), "index cyclic orbits by residue classes"),
    _edge("FiniteFourierTransform", "ResidueClassStructure", "CharacterSum", ("class_membership", "period"), "Fourier analyze residue restrictions"),
    _edge("CoefficientEncoding", "CharacterSum", "GeneratingFunction", ("coefficient_constraint", "period"), "encode the same restriction in generating-function coefficients"),
    _edge("CoefficientClass", "GeneratingFunction", "CombinatorialClass", ("coefficient", "size"), "interpret coefficients as counted objects"),
    _edge("UniformMeasure", "CombinatorialClass", "ProbabilitySpace", ("sample_space", "cardinality"), "equip the same finite class with uniform measure"),
    _edge("Expectation", "ProbabilitySpace", "ExpectationObservable", ("sample_space", "observable"), "take expectation without changing the outcomes"),
)


NODE_BY_NAME = {node.name: node for node in NODES}
EDGE_BY_PAIR = {(edge.source, edge.target): edge for edge in EDGES}


def shortest_path(
    source: str,
    target: str,
    *,
    established_conditions: Any = None,
) -> list[str] | None:
    """Return the shortest directed morphology path between two charts."""
    if source not in NODE_BY_NAME or target not in NODE_BY_NAME:
        return None
    queue = deque([(source, [source])])
    seen = {source}
    conditions = {str(item) for item in (established_conditions or [])}
    while queue:
        current, path = queue.popleft()
        if current == target:
            return path
        for edge in EDGES:
            if not set(edge.requires).issubset(conditions):
                continue
            if edge.source == current and edge.target not in seen:
                seen.add(edge.target)
                queue.append((edge.target, path + [edge.target]))
    return None


def certify_morphology_path(
    path: Any,
    *,
    morphism_chain: Any = None,
    established_conditions: Any = None,
) -> dict[str, Any]:
    """Certify that a candidate moves only through adjacent typed charts."""
    if not isinstance(path, (list, tuple)) or len(path) < 2:
        return {
            "present": bool(path),
            "valid": False,
            "reason": "path_missing_or_too_short",
            "edge_count": 0,
            "theory_transitions": 0,
        }
    names = [str(item) for item in path]
    unknown = [name for name in names if name not in NODE_BY_NAME]
    if unknown:
        return {
            "present": True,
            "valid": False,
            "reason": "unknown_morphology_node",
            "unknown": unknown,
            "edge_count": 0,
            "theory_transitions": 0,
        }

    edges: list[MorphologyEdge] = []
    conditions = {str(item) for item in (established_conditions or [])}
    for source, target in zip(names, names[1:]):
        edge = EDGE_BY_PAIR.get((source, target))
        if edge is None:
            return {
                "present": True,
                "valid": False,
                "reason": "non_adjacent_jump",
                "jump": [source, target],
                "edge_count": len(edges),
                "theory_transitions": 0,
            }
        if not edge.transport:
            return {
                "present": True,
                "valid": False,
                "reason": "empty_semantic_transport",
                "edge": edge.name,
                "edge_count": len(edges),
                "theory_transitions": 0,
            }
        missing_conditions = sorted(set(edge.requires) - conditions)
        if missing_conditions:
            return {
                "present": True,
                "valid": False,
                "reason": "edge_precondition_unproved",
                "edge": edge.name,
                "missing_conditions": missing_conditions,
                "edge_count": len(edges),
                "theory_transitions": 0,
            }
        edges.append(edge)

    edge_names = [edge.name for edge in edges]
    alignment_checked = morphism_chain is not None
    if alignment_checked:
        chain = [str(item) for item in morphism_chain]
        cursor = 0
        for morphism in chain:
            if cursor < len(edge_names) and morphism == edge_names[cursor]:
                cursor += 1
        if cursor != len(edge_names):
            return {
                "present": True,
                "valid": False,
                "reason": "morphism_chain_misaligned",
                "edge_count": len(edges),
                "expected_edge_morphisms": edge_names,
                "observed_morphism_chain": chain,
                "missing_from_ordered_chain": edge_names[cursor:],
                "theory_transitions": 0,
            }

    theories = [NODE_BY_NAME[name].theory for name in names]
    transitions = sum(a != b for a, b in zip(theories, theories[1:]))
    shortest = shortest_path(
        names[0],
        names[-1],
        established_conditions=conditions,
    )
    shortest_edges = len(shortest) - 1 if shortest else None
    return {
        "present": True,
        "valid": True,
        "reason": "adjacent_typed_path",
        "morphism_alignment_checked": alignment_checked,
        "morphism_chain_aligned": True,
        "nodes": names,
        "edges": [asdict(edge) for edge in edges],
        "edge_count": len(edges),
        "theories": theories,
        "theory_transitions": transitions,
        "shortest_edge_count": shortest_edges,
        "detour": len(edges) - shortest_edges if shortest_edges is not None else None,
        "transported_invariants": sorted({item for edge in edges for item in edge.transport}),
        "established_conditions": sorted(conditions),
        "required_conditions": sorted({item for edge in edges for item in edge.requires}),
    }


def enumerate_paths(
    source: str,
    *,
    min_edges: int = 2,
    max_edges: int = 6,
) -> Iterable[list[str]]:
    """Enumerate simple typed paths for morphology-guided exploration."""
    if source not in NODE_BY_NAME:
        return

    def walk(current: str, path: list[str]) -> Iterable[list[str]]:
        edge_count = len(path) - 1
        if edge_count >= min_edges:
            yield list(path)
        if edge_count >= max_edges:
            return
        for edge in EDGES:
            if edge.source != current or edge.target in path:
                continue
            path.append(edge.target)
            yield from walk(edge.target, path)
            path.pop()

    yield from walk(source, [source])
