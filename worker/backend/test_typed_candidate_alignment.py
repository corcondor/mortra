from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.typed_candidate_alignment import (
    align_candidate_atoms,
    instantiate_relation_templates,
)


def test_direct_alignment_binds_hole_and_respects_line_symmetry() -> None:
    alignment = align_candidate_atoms(
        (Atom("perp", ("d", "a", "c", "b")),),
        (Atom("perp", ("?x", "a", "b", "c")),),
        {"perp": {"perp": 0}},
    )

    assert alignment.direct_match_count == 1
    assert alignment.direct_hole_binding_count == 1
    assert alignment.rank[0] == 0


def test_direct_unification_ranks_before_relation_only_overlap() -> None:
    demand = (Atom("perp", ("?x", "a", "b", "c")),)
    distances = {"perp": {"perp": 0, "coll": 1}}
    direct = align_candidate_atoms(
        (Atom("perp", ("d", "a", "b", "c")),), demand, distances
    )
    indirect = align_candidate_atoms(
        (Atom("coll", ("d", "a", "b")),), demand, distances
    )

    assert direct.rank < indirect.rank


def test_alignment_is_invariant_under_entity_renaming() -> None:
    distances = {"coll": {"coll": 0}}
    first = align_candidate_atoms(
        (Atom("coll", ("x", "a", "b")),),
        (Atom("coll", ("?p", "a", "b")),),
        distances,
    )
    renamed = align_candidate_atoms(
        (Atom("coll", ("u", "r", "s")),),
        (Atom("coll", ("?q", "r", "s")),),
        distances,
    )

    assert first == renamed


def test_relation_templates_are_instantiated_without_text_heuristics() -> None:
    atoms = instantiate_relation_templates(
        ("x", "a", "b"),
        (Atom("midp", ("x", "a", "b")),),
        ("m", "p", "q"),
    )

    assert atoms == (Atom("midp", ("m", "p", "q")),)
