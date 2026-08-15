from newclid.problem import PredicateConstruction

from worker.backend.gclc_newclid_bridge import lower_gclc_to_newclid


def test_midpoint_parallel_certificate_replays_exactly() -> None:
    source = """
    point A 20 10
    point B 70 10
    point C 35 40
    midpoint B_1 B C
    midpoint A_1 A C
    prove { parallel A_1 B_1 A B }
    """
    obligation = lower_gclc_to_newclid(source)
    assert obligation.channel == "para"
    assert obligation.exact_replay
    assert obligation.remainder == "0"
    assert str(PredicateConstruction.from_str(obligation.newclid_predicate)).startswith("para ")


def test_orthocenter_perpendicular_certificate_replays_exactly() -> None:
    source = """
    point A 20 10
    point B 60 10
    point C 50 70
    line a B C
    line b A C
    perp hA A a
    perp hB B b
    intersec H hA hB
    prove { perpendicular A B C H }
    """
    obligation = lower_gclc_to_newclid(source)
    assert obligation.channel == "perp"
    assert obligation.exact_replay
    assert obligation.remainder == "0"
    assert obligation.nondegeneracy_conditions
    assert str(PredicateConstruction.from_str(obligation.newclid_predicate)).startswith("perp ")


def test_pappus_online_points_certificate_replays_exactly() -> None:
    source = """
    point A 40 10
    point B 90 10
    online C A B
    point A_1 25 40
    point B_1 45 45
    online C_1 A_1 B_1
    line AB_1 A B_1
    line AC_1 A C_1
    line BA_1 B A_1
    line BC_1 B C_1
    line CA_1 C A_1
    line CB_1 C B_1
    intersec P AB_1 BA_1
    intersec Q AC_1 CA_1
    intersec S BC_1 CB_1
    prove { collinear P Q S }
    """
    obligation = lower_gclc_to_newclid(source)
    assert obligation.channel == "coll"
    assert obligation.exact_replay
    assert obligation.remainder == "0"
    assert len(obligation.construction_equations) == 8
    assert obligation.verification_method == "rational_construction_elimination"
    assert obligation.rational_denominators
    assert str(PredicateConstruction.from_str(obligation.newclid_predicate)).startswith("coll ")


def test_pappus_altered_conclusion_is_rejected() -> None:
    source = """
    point A 40 10
    point B 90 10
    online C A B
    point A_1 25 40
    point B_1 45 45
    online C_1 A_1 B_1
    line AB_1 A B_1
    line AC_1 A C_1
    line BA_1 B A_1
    line BC_1 B C_1
    line CA_1 C A_1
    line CB_1 C B_1
    intersec P AB_1 BA_1
    intersec Q AC_1 CA_1
    intersec S BC_1 CB_1
    prove { collinear P Q B }
    """
    obligation = lower_gclc_to_newclid(source)
    assert not obligation.exact_replay
    assert obligation.verification_method == "unproved"
    assert obligation.remainder != "0"


def test_unknown_semantic_command_is_not_silently_ignored() -> None:
    source = """
    point A 0 0
    point B 1 0
    point O 0 1
    circle k O A
    prove { collinear A B O }
    """
    try:
        lower_gclc_to_newclid(source)
    except ValueError as error:
        assert "circle" in str(error)
    else:
        raise AssertionError("unsupported circle command was silently accepted")
