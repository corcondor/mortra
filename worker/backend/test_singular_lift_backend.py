from pathlib import Path

import pytest
import sympy as sp

from worker.backend.singular_lift_backend import (
    _marker_map,
    _render_program,
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


def test_marker_parser_ignores_native_diagnostics() -> None:
    markers = _marker_map(
        "// warning\nMORTRA_STATUS=COMPUTED\nMORTRA_REMAINDER=x1^2-x2\n"
    )
    assert markers == {
        "MORTRA_STATUS": "COMPUTED",
        "MORTRA_REMAINDER": "x1^2-x2",
    }


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
