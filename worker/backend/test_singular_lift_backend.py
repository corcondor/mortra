from pathlib import Path

import pytest
import sympy as sp

from worker.backend.singular_lift_backend import (
    _marker_map,
    _render_bounded_linear_program,
    _render_probe_program,
    _render_program,
    _render_raw_source_replay_program,
    _replay_source_lift,
    _singular_command,
    _singular_expression,
    probe_ideal_membership_with_singular,
    prove_ideal_membership_with_singular,
    singular_runtime_available,
)


def test_program_renames_source_symbols_and_requests_a_lift() -> None:
    source_x, source_y = sp.symbols("_source_x _source_y")
    program, reverse = _render_program(
        (source_x**2 - source_y, source_x - source_y),
        (source_x, source_y),
        source_y**2 - source_y,
        monomial_order="dp",
    )
    assert "_source_x" not in program
    assert "liftstd(I,T)" in program
    assert "matrix H=T*U" in program
    assert reverse == {"x1": source_x, "x2": source_y}


def test_program_places_chart_parameters_in_a_fraction_field() -> None:
    x, parameter = sp.symbols("x parameter")
    program, reverse = _render_program(
        (parameter * x - 1,),
        (x,),
        x - 1 / parameter,
        monomial_order="dp",
        coefficient_parameters=(parameter,),
    )

    assert "ring mortra=(0,p1),(x1),dp;" in program
    assert reverse == {"x1": x, "p1": parameter}


def test_fraction_field_coefficients_stay_factored_in_singular_program() -> None:
    x, a, b = sp.symbols("x a b")
    expanded = sp.expand((a + b) ** 2 * x + (a - b) ** 2)

    program, _ = _render_program(
        (expanded,),
        (x,),
        expanded,
        monomial_order="dp",
        coefficient_parameters=(a, b),
    )

    assert "((p1 + p2)^2)*x1" in program
    assert "((p1 - p2)^2)" in program
    assert "p1^2 + 2*p1*p2 + p2^2" not in program


def test_large_singular_expression_streams_compact_dag_without_poly_rebuild() -> None:
    x, parameter = sp.symbols("x parameter")
    coefficient = sp.Add(
        *(parameter**index for index in range(1, 2_100)),
        evaluate=False,
    )
    expression = sp.Mul(coefficient, x + 1, evaluate=False)

    rendered = _singular_expression(
        expression,
        {x: "x1", parameter: "p1"},
        variables=(x,),
        coefficient_parameters=(parameter,),
    )

    assert int(sp.count_ops(expression)) > 2_048
    assert "parameter" not in rendered
    assert "x" not in rendered.replace("x1", "")
    assert "p1^2099" in rendered


def test_high_dimensional_expression_uses_structural_renderer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variables = sp.symbols("x0:13")
    parameter = sp.Symbol("parameter")
    expression = sp.Add(
        *(
            parameter**((index % 5) + 1)
            * variables[index % len(variables)]
            * variables[(index + 1) % len(variables)]
            for index in range(600)
        ),
        evaluate=False,
    )

    def fail_poly_rebuild(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("high-dimensional input must not be rebuilt as Poly")

    monkeypatch.setattr(sp, "Poly", fail_poly_rebuild)
    rendered = _singular_expression(
        expression,
        {
            **{symbol: f"x{index}" for index, symbol in enumerate(variables, 1)},
            parameter: "p1",
        },
        variables=variables,
        coefficient_parameters=(parameter,),
    )

    assert int(sp.count_ops(expression)) > 512
    assert "parameter" not in rendered
    assert "p1" in rendered


def test_probe_program_uses_slimgb_without_requesting_a_lift() -> None:
    x = sp.Symbol("x")
    program, _ = _render_probe_program(
        (x**2 - 1,),
        (x,),
        x**2 - 1,
        monomial_order="dp",
        engine="slimgb",
    )

    assert "ideal G=slimgb(I);" in program
    assert "liftstd" not in program


def test_slimgb_lift_program_recovers_a_source_transformation() -> None:
    x = sp.Symbol("x")
    program, _ = _render_program(
        (x**2 - 1,),
        (x,),
        x**2 - 1,
        monomial_order="lp",
        basis_engine="slimgb_lift",
    )

    assert "ideal G=slimgb(I);" in program
    assert "matrix T=lift(I,G);" in program
    assert "matrix H=T*U;" in program
    assert "MORTRA_SOURCE_RESIDUAL" in program


def test_raw_source_replay_program_checks_original_generators() -> None:
    x, parameter = sp.symbols("x parameter")
    program = _render_raw_source_replay_program(
        (parameter * x - 1,),
        (x,),
        parameter * x - 1,
        ("1",),
        monomial_order="dp",
        coefficient_parameters=(parameter,),
    )

    assert "ring mortra=(0,p1),(x1),dp;" in program
    assert "source_residual=source_residual-(1)*I[1];" in program
    assert "MORTRA_SOURCE_RESIDUAL=0" in program


def test_direct_lift_program_requests_only_the_target_source_representation() -> None:
    x = sp.Symbol("x")
    program, _ = _render_program(
        (x**2 - 1,),
        (x,),
        x**2 - 1,
        monomial_order="lp",
        basis_engine="direct_lift",
    )

    assert "ideal G=slimgb(I);" in program
    assert "matrix H=lift(I,J);" in program
    assert "matrix T=lift(I,G);" not in program
    assert "matrix H=T*U;" not in program


def test_module_slimgb_program_carries_source_coefficients() -> None:
    x, y = sp.symbols("x y")
    program, _ = _render_program(
        (x**2 - y, x - y),
        (x, y),
        y**2 - y,
        monomial_order="lp",
        basis_engine="module_slimgb",
    )

    assert "ring mortra=0,(x1,x2),(c,lp);" in program
    assert "module M=[I[1],1,0],[I[2],0,1];" in program
    assert "module GM=slimgb(M);" in program
    assert 'attrib(G,"isSB",1);' in program
    assert "T[mortra_i,mortra_column]=GM[mortra_j][mortra_i+1];" in program
    assert "matrix H=T*U;" in program


def test_marker_parser_ignores_native_diagnostics() -> None:
    markers = _marker_map(
        "// warning\nMORTRA_STATUS=COMPUTED\nMORTRA_REMAINDER=x1^2-x2\n"
    )
    assert markers == {
        "MORTRA_STATUS": "COMPUTED",
        "MORTRA_REMAINDER": "x1^2-x2",
    }


def test_marker_parser_reassembles_multiline_certificate_values() -> None:
    markers = _marker_map(
        "MORTRA_STATUS=COMPUTED\n"
        "MORTRA_MULTIPLIER_1_BEGIN\n"
        "p1*x1^2+\n"
        "p2*x2\n"
        "MORTRA_MULTIPLIER_1_END\n"
        "MORTRA_DONE=1\n"
    )

    assert markers["MORTRA_MULTIPLIER_1"] == "p1*x1^2+p2*x2"


def test_bounded_program_records_lift_matrix_shape_and_nonzero_count() -> None:
    x = sp.symbols("x")
    program, _, _ = _render_bounded_linear_program(
        (x,),
        (x,),
        x,
        coefficient_parameters=(),
        certificate_degree=1,
    )

    assert "MORTRA_LIFT_ROWS=" in program
    assert "MORTRA_LIFT_COLUMNS=" in program
    assert "MORTRA_LIFT_NONZERO_ENTRIES=" in program
    assert "MORTRA_BOUNDED_COLUMN_COUNT=" in program
    assert 'attrib(M,"rank",1);' in program
    assert 'attrib(N,"rank",1);' in program


def test_runtime_command_enforces_timeout_inside_wsl() -> None:
    command = _singular_command(
        singular_root=Path("/opt/singular"),
        wsl_distribution="Ubuntu",
        timeout_seconds=12.5,
    )

    assert command == (
        "wsl.exe",
        "-d",
        "Ubuntu",
        "--",
        "env",
        "LD_LIBRARY_PATH=/opt/singular/usr/lib/x86_64-linux-gnu",
        "timeout",
        "--signal=TERM",
        "--kill-after=5s",
        "12.5s",
        "/opt/singular/usr/bin/Singular",
        "-q",
    )


def test_source_lift_replays_coefficientwise_over_fraction_field() -> None:
    x, y, parameter = sp.symbols("x y parameter")
    polynomials = (parameter * x + y, x - y)
    multipliers = (1 / parameter, -y / parameter)
    goal = x + y / parameter - x * y / parameter + y**2 / parameter

    residual = _replay_source_lift(
        goal,
        multipliers,
        polynomials,
        (x, y),
        (parameter,),
    )

    assert residual == 0


@pytest.mark.skipif(
    not singular_runtime_available(),
    reason="local isolated Singular runtime is unavailable",
)
def test_live_singular_lift_replays_against_original_generators() -> None:
    x, y = sp.symbols("x y")
    result = prove_ideal_membership_with_singular(
        (x**2 - y, x - y),
        (x, y),
        y**2 - y,
        timeout_seconds=30,
        singular_root=Path("/home/shibahara/.local/mortra-singular/root"),
    )
    assert result.status == "proved"
    assert result.proved and result.replayed
    assert result.replay_residual == "0"


@pytest.mark.skipif(
    not singular_runtime_available(),
    reason="local isolated Singular runtime is unavailable",
)
def test_live_fraction_field_lift_replays_rational_multiplier() -> None:
    x, parameter = sp.symbols("x parameter")
    result = prove_ideal_membership_with_singular(
        (parameter * x - 1,),
        (x,),
        x - 1 / parameter,
        coefficient_parameters=(parameter,),
        timeout_seconds=30,
        singular_root=Path("/home/shibahara/.local/mortra-singular/root"),
    )

    assert result.status == "proved"
    assert result.proved and result.replayed
    assert result.replay_residual == "0"


@pytest.mark.skipif(
    not singular_runtime_available(),
    reason="local isolated Singular runtime is unavailable",
)
def test_live_slimgb_membership_probe() -> None:
    x, y = sp.symbols("x y")
    result = probe_ideal_membership_with_singular(
        (x**2 - y, x - y),
        (x, y),
        y**2 - y,
        timeout_seconds=30,
        singular_root=Path("/home/shibahara/.local/mortra-singular/root"),
    )

    assert result.status == "computed"
    assert result.member


@pytest.mark.skipif(
    not singular_runtime_available(),
    reason="local isolated Singular runtime is unavailable",
)
def test_live_slimgb_lift_replays_against_source_generators() -> None:
    x, y = sp.symbols("x y")
    result = prove_ideal_membership_with_singular(
        (x**2 - y, x - y),
        (x, y),
        y**2 - y,
        timeout_seconds=30,
        basis_engine="slimgb_lift",
        singular_root=Path("/home/shibahara/.local/mortra-singular/root"),
    )

    assert result.status == "proved"
    assert result.proved and result.replayed
    assert result.basis_engine == "slimgb_lift"


@pytest.mark.skipif(
    not singular_runtime_available(),
    reason="local isolated Singular runtime is unavailable",
)
def test_live_direct_lift_replays_against_source_generators() -> None:
    x, y = sp.symbols("x y")
    result = prove_ideal_membership_with_singular(
        (x**2 - y, x - y),
        (x, y),
        y**2 - y,
        timeout_seconds=30,
        basis_engine="direct_lift",
        singular_root=Path("/home/shibahara/.local/mortra-singular/root"),
    )

    assert result.status == "proved"
    assert result.proved and result.replayed
    assert result.basis_engine == "direct_lift"


@pytest.mark.skipif(
    not singular_runtime_available(),
    reason="local isolated Singular runtime is unavailable",
)
def test_live_module_slimgb_replays_against_source_generators() -> None:
    x, y = sp.symbols("x y")
    result = prove_ideal_membership_with_singular(
        (x**2 - y, x - y),
        (x, y),
        y**2 - y,
        timeout_seconds=30,
        basis_engine="module_slimgb",
        singular_root=Path("/home/shibahara/.local/mortra-singular/root"),
    )

    assert result.status == "proved"
    assert result.proved and result.replayed
    assert result.basis_engine == "module_slimgb"
    assert len(result.basis_polynomials) == 2


@pytest.mark.skipif(
    not singular_runtime_available(),
    reason="local isolated Singular runtime is unavailable",
)
def test_live_bounded_linear_replays_against_source_generators() -> None:
    x, y = sp.symbols("x y")
    result = prove_ideal_membership_with_singular(
        (x**2 - y, x - y),
        (x, y),
        y**2 - y,
        timeout_seconds=120,
        basis_engine="bounded_linear",
        max_certificate_degree=2,
        singular_root=Path("/home/shibahara/.local/mortra-singular/root"),
    )

    assert result.status == "proved"
    assert result.proved and result.replayed
    assert result.basis_engine == "bounded_linear"
    assert result.certificate_degree == 2
