"""Synthetic development fixtures, separate from frozen normal-run evidence."""
from copy import deepcopy

import pytest
import sympy as sp

from newclid.jgex.clause import JGEXClause
from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS
from newclid.jgex.definition import JGEXDefinition
from worker.backend.jgex_exact_constraint_bridge import _JGEXElaborator, _prepare_exact_system
from math_os_prototype.theory_geometry import GeometryDomain


def test_declared_relations_derive_parallelogram_without_name_formula():
    chart = _JGEXElaborator()
    chart._triangle(("a", "b", "c"))
    chart.elaborate_clause(JGEXClause.from_str("x = parallelogram x a b c")[0])
    assert all(sp.cancel(x - (a-b+c)) == 0 for x, a, b, c in zip(
        chart.coordinates["x"], chart.coordinates["a"], chart.coordinates["b"], chart.coordinates["c"]))
    cert = chart.structural_lemma_certificates[-1]
    assert cert.theorem == "declared_predicate_unique_affine_witness"
    assert cert.replayed and len(cert.replay_residuals) == 4
    assert not any(s.name.startswith("_free_") for s in chart.variables)


def test_definition_name_is_not_a_formula_lookup(monkeypatch):
    definitions = JGEXDefinition.to_dict(ALL_JGEX_CONSTRUCTIONS)
    definitions["fixture_affine"] = definitions["parallelogram"].model_copy(update={"name": "fixture_affine"})
    monkeypatch.setattr(JGEXDefinition, "to_dict", staticmethod(lambda _: definitions))
    chart = _JGEXElaborator()
    chart._triangle(("a", "b", "c"))
    chart.elaborate_clause(JGEXClause.from_str("x = fixture_affine x a b c")[0])
    assert chart.structural_lemma_certificates[-1].replayed


def test_all_effects_must_replay_not_only_affine_subset(monkeypatch):
    from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS
    definitions = deepcopy(JGEXDefinition.to_dict(ALL_JGEX_CONSTRUCTIONS))
    bad = definitions["parallelogram"].model_dump(mode="json")
    bad["clauses"][-1]["constructions"].append({"string": "cong x a a b"})
    definitions["parallelogram"] = JGEXDefinition.model_validate(bad)
    monkeypatch.setattr(JGEXDefinition, "to_dict", staticmethod(lambda _: definitions))
    chart = _JGEXElaborator()
    chart._triangle(("a", "b", "c"))
    with pytest.raises(ValueError, match="fails a declared"):
        chart.elaborate_clause(JGEXClause.from_str("x = parallelogram x a b c")[0])


@pytest.mark.parametrize("clause", [
    "x = between_bound x a b", "x = angle_mirror x a b c",
    "x = intersection_cc x a b c", "x = parallelogram x a a c",
])
def test_unproved_branch_or_degenerate_definition_is_not_admitted(clause):
    chart = _JGEXElaborator()
    chart._triangle(("a", "b", "c"))
    with pytest.raises(ValueError):
        chart.elaborate_clause(JGEXClause.from_str(clause)[0])


def test_normal_exact_prover_replays_derived_definition():
    from math_os_prototype.geometry_proof_dsl import search_exact_proof
    result = search_exact_proof("a b c = triangle a b c; x = parallelogram x a b c ? para a b c x")
    assert result["accepted"]
    assert any(c["theorem"] == "declared_predicate_unique_affine_witness"
               for c in result["obligation"]["structural_lemma_certificates"])


@pytest.mark.parametrize("construction", [
    "x = on_line x p0 p1, on_tline x p2 p0 p1",
    "x = parallelogram x p0 p1 p2",
])
def test_rational_witness_extends_original_scope(construction):
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? cong a b a b"}, {})
    source = str(domain.formulation)
    setup, goal = source.split("?")
    cert = domain.certify_extension(source, setup.strip()+"; "+construction+" ? "+goal)
    assert cert["accepted"], cert
    assert cert["all_residuals_zero"]
    assert set(cert["required_regularity"]) <= set(cert["original_regularity"])
    if "on_line" in construction:
        assert cert["witness_derivations"]


def test_witness_cannot_add_unproved_nonzero_condition():
    domain = GeometryDomain({"statement": "a b c = triangle a b c; p = free p ? cong a b a b"}, {})
    source = str(domain.formulation)
    setup, goal = source.split("?")
    augmented = setup.strip()+"; x = parallelogram x p0 p1 p3 ? "+goal
    cert = domain.certify_extension(source, augmented)
    assert not cert["accepted"] and "nonzero" in cert["refusal_reason"]


def test_failed_guard_cannot_disappear_during_elimination(monkeypatch):
    import worker.backend.jgex_exact_constraint_bridge as bridge
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? cong a b a b"}, {})
    source = str(domain.formulation)
    setup, goal = source.split("?")
    augmented = setup.strip()+"; x = on_line x p0 p1, on_tline x p0 p0 p1 ? "+goal
    def poisoned(statement, **kwargs):
        result = _prepare_exact_system(statement, **kwargs)
        if statement == augmented:
            chart = result[0]
            chart.denominators.append(chart.variables[-1])
        return result
    monkeypatch.setattr(bridge, "_prepare_exact_system", poisoned)
    cert = domain.certify_extension(source, augmented)
    assert not cert["accepted"]
    assert "existence guard" in cert["refusal_reason"]
