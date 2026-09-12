"""Known elementary germs are fixtures, not mathematical discovery inputs."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from math_os_prototype.holonomic_route_discovery import coefficients, validate, certify_equal, replay_certificate
from math_os_prototype.holonomic_fast_coefficients import coefficients as fast_coefficients
from math_os_prototype.holonomic_action_control import order_bound
from math_os_prototype.holonomic_ode_source import source_corpus, replay_corpus, source_coefficients
from scripts.run_holonomic_route_discovery import main
from scripts.audit_holonomic_search_feedback import audit_search
from math_os_prototype.holonomic_shared_module import certify_equal_shared, replay_shared_certificate

EXP = {"op": "ode", "operator": [[-1], [1]], "initial": [1]}
SQUARE = {"op": "ode", "operator": [[-2], [0, 1]], "initial": [0, 0, 3]}


@pytest.mark.parametrize("program", [EXP, SQUARE,
    {"op": "diff", "child": EXP}, {"op": "mul", "left": EXP, "right": EXP},
    {"op": "add", "left": EXP, "right": SQUARE},
    {"op": "pullback", "child": EXP, "numerator": [0, 1, 1], "denominator": [1, -1]}])
def test_exact_coefficient_backends(program):
    assert coefficients(program, 32) == fast_coefficients(program, 32)
    assert len(coefficients(program, 0)) == 0


@pytest.mark.parametrize("program", [
    {"op": "ode", "operator": [[-2], [0, 1]], "initial": [0, 0]},
    {"op": "ode", "operator": [[-2], [0, 1]], "initial": [1, 0, 3]},
    {"op": "ode", "operator": [[-1], [0]], "initial": [1]},
    {"op": "ode", "operator": [[-1], [1]], "initial": [1, 2]},
])
def test_missing_or_inconsistent_initial_data_rejected(program):
    with pytest.raises((ValueError, ArithmeticError)):
        validate(program)


def test_ode_proof_and_order_bound():
    result = certify_equal({"op": "diff", "child": EXP}, EXP)
    assert result["status"] == "exact_formal_series_equality"
    assert replay_certificate(result)
    assert order_bound({"op": "mul", "left": EXP, "right": SQUARE}) == 1
    assert coefficients(SQUARE, 6) == (0, 0, 3, 0, 0, 0)


@pytest.mark.parametrize("left,right", [
    ({"op": "diff", "child": EXP}, EXP),
    (SQUARE, {"op": "poly", "coefficients": [0, 0, 3]}),
    ({"op": "diff", "child": {"op": "pullback", "child": EXP,
      "numerator": [0, 0, 1], "denominator": [1]}},
     {"op": "mul", "left": {"op": "poly", "coefficients": [0, 2]},
      "right": {"op": "pullback", "child": EXP, "numerator": [0, 0, 1], "denominator": [1]}}),
    ({"op": "ode", "operator": [[1], [0], [1]], "initial": [0, 1]},
     {"op": "scale", "factor": -1, "child": {"op": "diff", "child":
       {"op": "ode", "operator": [[1], [0], [1]], "initial": [1, 0]}}}),
])
def test_shared_ode_proof_and_replay(left, right):
    certificate = certify_equal_shared(left, right)
    assert certificate["status"] == "exact_shared_module_equality"
    assert replay_shared_certificate(certificate)


def test_shared_ode_keeps_initial_values():
    other = deepcopy(EXP)
    other["initial"] = [2]
    assert certify_equal_shared(EXP, other)["status"] == "refuted"


def test_high_degree_operator_is_not_replaced_by_an_easy_source():
    program = {"op": "ode", "operator": [[-1], [1]+[0]*550+[1]], "initial": [1]}
    validate(program)
    assert coefficients(program, 16) == coefficients(EXP, 16)
    values = source_coefficients(json.dumps(program), 553)
    assert values != source_coefficients(json.dumps(EXP), 553)
    assert list(source_coefficients(json.dumps(program), 553, fast=True)) == list(values)


def test_source_digest_and_non_geometric_scope():
    source = source_corpus([EXP], {"fixture": True})
    assert replay_corpus(source) == source
    changed = deepcopy(source)
    changed["programs"][0]["initial"] = [2]
    with pytest.raises(ValueError, match="changed"):
        replay_corpus(changed)


def test_common_search_uses_only_ode_sources_and_replays(tmp_path):
    source = tmp_path/"source.json"
    source.write_text(json.dumps(source_corpus([EXP], {"fixture": True})), encoding="utf-8")
    out = tmp_path/"search"
    argv = ["run", "--output", str(out), "--ode-sources", str(source), "--programs", "24",
            "--max-proposals", "24", "--max-certificates", "0", "--max-depth", "8",
            "--action-selection", "learn", "--compound-operands", "--with-add"]
    with patch("sys.argv", argv):
        main()
    data = json.loads((out/"discovery.json").read_text(encoding="utf-8"))
    assert data["policy"]["parameters"] == []
    assert data["programs"][0]["program"] == EXP
    assert len(data["programs"]) > 1
    assert audit_search(data)["generation_choices_replayed"] == 24
    changed = deepcopy(data)
    changed["ode_sources"]["programs"][0]["initial"] = [2]
    with pytest.raises(ValueError):
        audit_search(changed)
