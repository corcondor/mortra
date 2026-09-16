"""Source-semantics regression fixtures; no test witnesses enter normal search."""
import pytest

from worker.backend.jgex_exact_constraint_bridge import _prepare_exact_system
from math_os_prototype.geometry_proof_dsl import search_exact_proof, request_options
from math_os_prototype.theory_geometry import GeometryDomain


SOURCE = ("a b = segment a b; c = on_circle c a b, on_tline c a a b; "
          "p = on_tline p a a b, on_circle p a b ? midp a c p")


@pytest.mark.parametrize("representation", ["explicit", "relational"])
def test_two_locus_distinctness_is_not_limited_to_on_line(representation):
    chart = _prepare_exact_system(SOURCE, representation=representation,
                                  preserve_intersection_distinctness=True)[0]
    assert {"diff p a", "diff p b", "diff p c"} <= set(chart.normalization_assumptions)
    certs = [c for c in chart.structural_lemma_certificates
             if c.theorem == "source_two_locus_distinctness"]
    assert certs and all(c.replayed and c.replay_residuals == ("0",) for c in certs)
    assert any(c.output == "p" and c.inputs == ("c",) for c in certs)


def test_single_locus_does_not_receive_two_locus_premises():
    chart = _prepare_exact_system("a b = segment a b; p = on_line p a b ? coll a b p",
                                  preserve_intersection_distinctness=True)[0]
    assert not any(a.startswith("diff p ") for a in chart.normalization_assumptions)


def test_same_definition_different_names_has_same_scope_shape():
    from newclid.jgex.formulation import JGEXFormulation
    renamed = JGEXFormulation.from_text(SOURCE).renamed({"a": "u", "b": "v", "c": "w", "p": "z"})
    chart = _prepare_exact_system(str(renamed), preserve_intersection_distinctness=True)[0]
    assert {"diff z u", "diff z v", "diff z w"} <= set(chart.normalization_assumptions)


def test_normal_proof_planner_can_select_source_scope():
    result = search_exact_proof(SOURCE, budget=256)
    assert result["accepted"]
    assert result["options"]["preserve_intersection_distinctness"]
    assert "source_scope" in [s["operation"] for s in result["proof_program"]]
    assert result["obligation"]["exact_replay"]


def test_source_scope_cannot_reinterpret_single_locus_as_opposite_point():
    source = "a b = segment a b; p = on_circle p a b ? midp a b p"
    result = search_exact_proof(source, budget=256)
    assert not result["accepted"]


def test_auxiliary_freshness_must_not_strengthen_the_original_scope():
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? cong a b a b"}, {})
    source = str(domain.formulation)
    setup, goal = source.split("?")
    augmented = setup.strip()+"; x = on_line x p0 p1, on_tline x p2 p0 p1 ? "+goal
    assert domain.certify_extension(source, augmented)["accepted"]
    scoped = domain.certify_extension(source, augmented, preserve_intersection_distinctness=True)
    assert not scoped["accepted"]
    assert "scope" in scoped["refusal_reason"]
    assert scoped["preserve_intersection_distinctness"]


def test_request_scope_is_explicit():
    request = {"chart": "explicit", "goal_slice": False, "local_elimination": False,
               "affine": False, "structural": False}
    assert not request_options(request)["preserve_intersection_distinctness"]
    assert request_options(dict(request, source_scope=True))["preserve_intersection_distinctness"]
