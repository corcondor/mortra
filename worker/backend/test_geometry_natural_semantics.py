from worker.backend.geometry_natural_semantics import (
    extract_geometry_natural_semantics,
)


def test_extracts_named_circle_pair_and_existential_midpoint_branch() -> None:
    semantics = extract_geometry_natural_semantics(
        "Let ABC be a triangle with circumcircle Omega. The circumcircles of "
        "triangles KID and MAN intersect at points L1 and L2. Prove that Omega "
        "passes through the midpoint of either IL1 or IL2."
    )

    assert semantics.has_circle_intersection_pair(
        ("L1", "L2"),
        (("K", "I", "D"), ("M", "A", "N")),
    )
    assert semantics.has_existential_midpoint_on_circumcircle(
        "I",
        ("L1", "L2"),
        ("A", "B", "C"),
    )


def test_extracts_second_intersection_from_shared_circle_point() -> None:
    semantics = extract_geometry_natural_semantics(
        "Let L be the second intersection of the circumcircles of triangles "
        "AKH and HEF."
    )

    assert semantics.has_second_circle_intersection(
        "L",
        "H",
        (("A", "K", "H"), ("H", "E", "F")),
    )


def test_unqualified_intersection_does_not_invent_a_branch_constraint() -> None:
    semantics = extract_geometry_natural_semantics(
        "The circumcircles of triangles AKH and HEF meet at L."
    )

    assert semantics.second_circle_intersections == ()
    assert semantics.existential_midpoints_on_circumcircles == ()


def test_extracts_named_miquel_point_without_inferring_it_from_incidence() -> None:
    semantics = extract_geometry_natural_semantics(
        "Let DEF be the cevian triangle of P and let Q be the Miquel point Q "
        "of DEF."
    )
    unnamed = extract_geometry_natural_semantics(
        "The circumcircles AEF and BDF meet at F and Q."
    )

    assert semantics.has_miquel_point("Q", ("D", "E", "F"))
    assert "miquel_point(Q,D,E,F)" in semantics.typed_atoms
    assert unnamed.miquel_points == ()


def test_extracts_existential_circle_pair_labelling_with_reflected_point() -> None:
    semantics = extract_geometry_natural_semantics(
        "The circles $(PQR)$ and $(A'XY)$ meet in two points. Prove that these "
        "intersection points can be named $M$ and $N$ so that the conclusion holds."
    )

    assert semantics.has_existential_circle_pair_labelling(
        ("M", "N"),
        (("P", "Q", "R"), ("A1", "X", "Y")),
    )
    assert (
        "exists_circle_pair_labelling(M,N,circumcircle(P,Q,R),"
        "circumcircle(A1,X,Y))"
    ) in semantics.typed_atoms
