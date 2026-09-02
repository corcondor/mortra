"""Exact, reusable certificates for similarity containment of convex polytopes.

The local replay separates two logically different obligations:

* query-dependent algebra and half-space containment are checked exactly here;
* a published global optimum may be used as an explicit theorem dependency.

This prevents a feasible extremal configuration from being mistaken for a proof
that no better orientation exists.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

import sympy as sp

_CROFT_CUBE_IN_TETRAHEDRON_ID = "croft.1980.regular_cube_in_regular_tetrahedron"

_PUBLISHED_THEOREMS: dict[str, dict[str, Any]] = {
    _CROFT_CUBE_IN_TETRAHEDRON_ID: {
        "schema_version": 1,
        "theorem_id": _CROFT_CUBE_IN_TETRAHEDRON_ID,
        "claim": {
            "ambient_dimension": 3,
            "outer_polytope": "regular_tetrahedron",
            "outer_edge": "1",
            "inner_polytope": "cube",
            "quantification": "all translations and orthogonal orientations in Euclidean 3-space",
            "maximum_inner_edge": "1/(1 + 2*sqrt(3)/3 + sqrt(6)/2)",
            "attained": True,
        },
        "primary_source": {
            "author": "H. T. Croft",
            "title": "On Maximal Regular Polyhedra Inscribed in a Regular Polyhedron",
            "journal": "Proceedings of the London Mathematical Society",
            "volume": "s3-41",
            "year": 1980,
            "pages": "279-296",
            "doi": "10.1112/plms/s3-41.2.279",
            "url": "https://doi.org/10.1112/plms/s3-41.2.279",
        },
        "exact_value_source": {
            "author": "Moritz Firsching",
            "title": "Computing maximal copies of polytopes contained in a polytope",
            "arxiv": "1407.0683",
            "url": "https://arxiv.org/abs/1407.0683",
            "table_entry": "C in T",
        },
        "trust_basis": "published_global_theorem",
        "external_obligation": "global optimality over every relative orientation and translation",
    }
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def published_theorem_dependency(theorem_id: str) -> dict[str, Any]:
    """Return a hash-bound copy of a theorem dependency from the local registry."""

    if theorem_id not in _PUBLISHED_THEOREMS:
        raise KeyError(f"unknown published theorem: {theorem_id}")
    record = deepcopy(_PUBLISHED_THEOREMS[theorem_id])
    record["registry_record_sha256"] = sha256(
        _canonical_json(record).encode("utf-8")
    ).hexdigest()
    record["registry_integrity_valid"] = True
    return record


def validate_published_theorem_dependency(record: dict[str, Any]) -> bool:
    """Check that a dependency is an unchanged record from this registry."""

    theorem_id = record.get("theorem_id")
    if theorem_id not in _PUBLISHED_THEOREMS:
        return False
    expected = published_theorem_dependency(str(theorem_id))
    return record == expected


def _exact_rows(matrix: sp.Matrix) -> list[list[str]]:
    return [[sp.sstr(value) for value in row] for row in matrix.tolist()]


def _exact_vector(vector: sp.Matrix) -> list[str]:
    return [sp.sstr(value) for value in vector]


def _radical_normal_form(value: sp.Expr) -> sp.Expr:
    return sp.factor(sp.radsimp(value))


def _is_exact_zero(value: sp.Expr) -> bool:
    return _radical_normal_form(value) == 0


def _is_zero_matrix(matrix: sp.Matrix) -> bool:
    return all(_is_exact_zero(value) for value in matrix)


def regular_tetrahedron_cube_containment(edge: sp.Expr | str | int) -> dict[str, Any]:
    """Replay Croft's cube-in-tetrahedron optimum for a current edge length.

    The function does not store an answer for each edge.  It elaborates the edge
    supplied by the current query, applies similarity scaling, and independently
    checks the half-space model, orthogonal frame, eight cube vertices, four face
    contacts, and the exact equality construction.
    """

    edge_value = sp.sympify(edge)
    if edge_value.is_real is not True or edge_value.is_positive is not True:
        raise ValueError("regular tetrahedron edge must be a positive real exact value")

    theorem = published_theorem_dependency(_CROFT_CUBE_IN_TETRAHEDRON_ID)
    if not validate_published_theorem_dependency(theorem):
        raise ValueError("published theorem registry integrity check failed")

    sqrt2, sqrt3, sqrt6 = sp.sqrt(2), sp.sqrt(3), sp.sqrt(6)
    source_unit_side = sp.sympify(theorem["claim"]["maximum_inner_edge"])
    normalized_unit_side = sp.simplify(sqrt6 / (sqrt6 + 2 * sqrt2 + 3))
    source_expression_residual = _radical_normal_form(
        source_unit_side - normalized_unit_side
    )
    if source_expression_residual != 0:
        raise ValueError("published and internal exact forms disagree")

    normals = (
        sp.Matrix(
            [
                [1, 1, 1],
                [1, -1, -1],
                [-1, 1, -1],
                [-1, -1, 1],
            ]
        )
        / sqrt3
    )
    if normals.T * sp.ones(4, 1) != sp.zeros(3, 1):
        raise ValueError("regular tetrahedron face normals do not balance")

    orientation = sp.Matrix(
        [
            [-1 / sqrt3, -1 / sqrt6, -1 / sqrt2],
            [1 / sqrt3, 1 / sqrt6, -1 / sqrt2],
            [1 / sqrt3, -2 / sqrt6, 0],
        ]
    )
    orthogonality_residual = orientation.T * orientation - sp.eye(3)
    if not _is_zero_matrix(orthogonality_residual):
        raise ValueError("cube orientation is not orthonormal")

    inradius = edge_value * sqrt6 / 12
    side = edge_value * normalized_unit_side
    support_matrix = (normals * orientation).applyfunc(_radical_normal_form)
    row_support = sp.Matrix(
        [sum(abs(value) for value in support_matrix.row(index)) for index in range(4)]
    )
    support_sum = _radical_normal_form(sum(row_support))
    theorem_support_lower_bound = _radical_normal_form(
        8 * (sqrt6 / 12) / source_unit_side
    )
    if not _is_exact_zero(support_sum - theorem_support_lower_bound):
        raise ValueError(
            "equality orientation does not attain the published support bound"
        )

    right_hand_side = sp.ones(4, 1) * inradius - side * row_support / 2
    center = (sp.Rational(3, 4) * normals.T * right_hand_side).applyfunc(
        _radical_normal_form
    )
    face_contact_residual = (
        normals * center + side * row_support / 2 - sp.ones(4, 1) * inradius
    )
    if not _is_zero_matrix(face_contact_residual):
        raise ValueError("cube does not make the four claimed face contacts")

    cube_vertices: list[sp.Matrix] = []
    for signs in ((a, b, c) for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)):
        vertex = (center + side * orientation * sp.Matrix(signs) / 2).applyfunc(
            _radical_normal_form
        )
        cube_vertices.append(vertex)

    tetrahedron_vertices = [-3 * inradius * normals.row(i).T for i in range(4)]
    tetrahedron_edge_residuals = [
        _radical_normal_form(
            (tetrahedron_vertices[i] - tetrahedron_vertices[j]).dot(
                tetrahedron_vertices[i] - tetrahedron_vertices[j]
            )
            - edge_value**2
        )
        for i in range(4)
        for j in range(i + 1, 4)
    ]
    if any(residual != 0 for residual in tetrahedron_edge_residuals):
        raise ValueError(
            "half-space model does not have the requested tetrahedron edge"
        )

    section_ratio = sqrt3 / (2 + sqrt3)
    tetrahedron_height = edge_value * sqrt6 / 3
    section_side = _radical_normal_form(
        section_ratio
        * tetrahedron_height
        / (tetrahedron_height / edge_value + section_ratio)
    )
    if not _is_exact_zero(section_side - side):
        raise ValueError(
            "parallel-section equality construction disagrees with the theorem value"
        )

    return {
        "chart_id": "convex_polytope.similarity_containment.support_function.v2",
        "instance_id": "regular_tetrahedron.contains.regular_cube",
        "atomic_chart_ids": [
            "convex_polytope.halfspace_support.v1",
            "orthogonal_box.support_function.v1",
            "similarity.scale_covariance.v1",
            "regular_tetrahedron.parallel_section_square.v1",
        ],
        "query_parameters": {
            "outer_edge": sp.sstr(edge_value),
            "ambient_dimension": 3,
        },
        "normal_model": _exact_rows(normals),
        "inradius": sp.sstr(inradius),
        "orientation": _exact_rows(orientation),
        "support_matrix": _exact_rows(support_matrix),
        "row_support": _exact_vector(row_support),
        "support_sum": sp.sstr(support_sum),
        "global_support_lower_bound": sp.sstr(theorem_support_lower_bound),
        "center": _exact_vector(center),
        "cube_vertices": [_exact_vector(vertex) for vertex in cube_vertices],
        "tetrahedron_vertices": [
            _exact_vector(vertex) for vertex in tetrahedron_vertices
        ],
        "vertex_containment_certificate": (
            "For each face, max_v <n_i,v> equals <n_i,c> + "
            "side/2*sum_j|<n_i,u_j>| = inradius."
        ),
        "face_contact_residual": [
            sp.sstr(_radical_normal_form(value)) for value in face_contact_residual
        ],
        "contact_residual": [
            sp.sstr(_radical_normal_form(value)) for value in face_contact_residual
        ],
        "section_square_ratio": sp.sstr(section_ratio),
        "tetrahedron_height": sp.sstr(tetrahedron_height),
        "maximum_side": sp.sstr(side),
        "normalized_maximum_side": sp.sstr(normalized_unit_side),
        "published_exact_form": sp.sstr(source_unit_side),
        "published_form_equivalence_residual": sp.sstr(source_expression_residual),
        "trusted_theorem_dependencies": [theorem],
        "proof_basis": "published_global_theorem_with_exact_current_input_replay",
        "machine_replay_scope": [
            "current edge elaboration and positivity",
            "similarity scaling",
            "regular-tetrahedron half-space model",
            "orthogonality of the equality cube",
            "containment of all eight cube vertices",
            "four exact face contacts",
            "exact equivalence of the two radical expressions",
            "attainment by the parallel-section construction",
        ],
        "external_proof_scope": [
            "global upper bound over every cube orientation and translation"
        ],
        "proof_obligations": {
            "theorem_registry_integrity": True,
            "published_form_matches_internal_form": True,
            "halfspace_model_exact": True,
            "orientation_orthonormal": True,
            "all_eight_vertices_contained": True,
            "all_four_face_contacts_exact": True,
            "parallel_section_construction_attains_bound": True,
            "current_input_similarity_scaling_exact": True,
        },
    }


__all__ = [
    "published_theorem_dependency",
    "regular_tetrahedron_cube_containment",
    "validate_published_theorem_dependency",
]
