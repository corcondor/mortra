"""Handwritten reference cases test the verifier, not autonomous discovery."""
from copy import deepcopy
import pytest
import sympy as sp

from math_os_prototype.holonomic_algebraic_discovery import (
    X, Y, certify_algebraic_value, certify_relation, decode_polynomial, encode_polynomial,
    guess_relations, replay_algebraic_value, replay_relation,
)
from math_os_prototype.holonomic_certified_evaluation import certify_evaluation


H = {"op": "hyper", "a": ["1/2"], "b": []}


def test_guess_and_prove_algebraic_relation_without_target_polynomial():
    guess = guess_relations(H, degree_x=2, degree_y=3)
    assert guess["candidates"]
    assert not guess["infinite_identity_proved"]
    cert = certify_relation(H, guess["candidates"][0]["polynomial"])
    assert cert["status"] == "exact_formal_algebraic_relation"
    assert replay_relation(cert)
    assert decode_polynomial(cert["polynomial"]).as_expr() == X*Y**2-Y**2+1


def test_finite_fit_trap_is_refuted_beyond_training_data():
    p = {"op": "poly", "coefficients": [1]+[0]*63+[1]}
    guess = guess_relations(p, degree_x=1, degree_y=1)
    terms = encode_polynomial(Y-1)
    assert terms in [c["polynomial"] for c in guess["candidates"]]
    cert = certify_relation(p, terms)
    assert cert["status"] == "refuted"
    assert cert["first_coefficient_mismatch"] == 64


def test_non_algebraic_reference_has_no_small_fitting_equation():
    p = {"op": "hyper", "a": [1, 1], "b": [2]}
    assert not guess_relations(p, degree_x=2, degree_y=2)["candidates"]


def test_exact_special_value_selects_positive_algebraic_root():
    relation = certify_relation(H, encode_polynomial((1-X)*Y**2-1))
    evaluation = certify_evaluation(H, "1/4", "1/2")
    cert = certify_algebraic_value(relation, evaluation)
    assert cert["status"] == "exact_real_algebraic_value"
    assert cert["minimal_polynomial_descending"] == ["3", "0", "-4"]
    assert sp.Rational(cert["isolating_interval"][0]) > 0
    assert replay_algebraic_value(cert, relation, evaluation)


def test_vacuous_specialization_is_not_an_exact_value():
    relation = certify_relation(H, encode_polynomial((4*X-1)*((1-X)*Y**2-1)))
    evaluation = certify_evaluation(H, "1/4", "1/2")
    assert certify_algebraic_value(relation, evaluation)["status"] == "degenerate_specialization"


def test_distinct_close_roots_require_more_precision():
    program = {"op": "poly", "coefficients": [1]}
    relation = certify_relation(program, encode_polynomial((Y-1)*(10**30*(Y-1)-1)))
    coarse = certify_evaluation(program, "1/4", "1/2", digits=20)
    assert certify_algebraic_value(relation, coarse)["status"] == "root_not_isolated"
    fine = certify_evaluation(program, "1/4", "1/2", digits=40)
    cert = certify_algebraic_value(relation, fine)
    assert cert["rational_value"] == "1"


@pytest.mark.parametrize("field,value", [("sha256", "bad"), ("common_operator", ["1"]),
    ("initial_residual_coefficients", ["1"]), ("polynomial", [[0, 1, "1"], [0, 0, "-1"]])])
def test_modified_relation_is_rejected(field, value):
    cert = deepcopy(certify_relation(H, encode_polynomial((1-X)*Y**2-1)))
    cert[field] = value
    assert not replay_relation(cert)


def test_mismatched_program_and_modified_interval_are_rejected():
    relation = certify_relation(H, encode_polynomial((1-X)*Y**2-1))
    other = certify_evaluation({"op": "poly", "coefficients": [1]}, "1/4", "1/2")
    with pytest.raises(ValueError):
        certify_algebraic_value(relation, other)
    evaluation = certify_evaluation(H, "1/4", "1/2")
    evaluation["lower"] = "-2"
    with pytest.raises(ValueError):
        certify_algebraic_value(relation, evaluation)


@pytest.mark.parametrize("terms", [[], [[0, 0, "1"]], [[0, 1, "0"]], [[-1, 1, "1"]],
    [[0, 1, "1"], [0, 1, "2"]], [[0, 9, "1"]]])
def test_bad_polynomial_is_rejected(terms):
    with pytest.raises(ValueError):
        certify_relation(H, terms)
