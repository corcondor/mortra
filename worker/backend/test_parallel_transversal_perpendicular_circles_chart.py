from pathlib import Path
import re

import pytest

from worker.backend.parallel_transversal_perpendicular_circles_chart import (
    certify_jgex_parallel_transversal_perpendicular_circles_application,
    certify_parallel_transversal_perpendicular_circles_chart,
    render_parallel_transversal_perpendicular_circles_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2022G5.jgex.txt").read_text(
    encoding="utf-8"
)


def _rename_points(source: str) -> str:
    names = (
        "a b c x1 y1 z1 x2 y2 z2 u1 v1 w1 u2 v2 w2 o1 o2 t".split()
    )
    replacements = {name: f"point_{index}" for index, name in enumerate(names)}
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, names)) + r")\b")
    return pattern.sub(lambda match: replacements[match.group(0)], source)


def test_exact_parallel_family_certificate_replays() -> None:
    certificate = certify_parallel_transversal_perpendicular_circles_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 33
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.circle_parameter_degrees == {
        "Gamma_b_in_tau": 1,
        "Gamma_c_in_tau": 1,
        "Gamma_d_in_tau": 1,
    }
    assert len(certificate.certificate_sha256) == 64


def test_frozen_formulation_matches_without_problem_id() -> None:
    application = certify_jgex_parallel_transversal_perpendicular_circles_application(
        SOURCE
    )

    assert application.replayed is True
    assert application.roles["O1"] == "o1"
    assert application.roles["O2"] == "o2"
    assert application.roles["T"] == "t"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_point_renaming_and_alternate_radius_witness_preserve_match() -> None:
    source = SOURCE.replace(
        "on_circle t o1 u1, on_circle t o2 u2",
        "on_circle t o1 w1, on_circle t o2 v2",
    )
    application = certify_jgex_parallel_transversal_perpendicular_circles_application(
        _rename_points(source)
    )

    assert application.replayed is True
    assert application.roles["T"] == "point_17"
    assert {application.roles["O1"], application.roles["O2"]} == {
        "point_15",
        "point_16",
    }


@pytest.mark.parametrize(
    "mutated",
    (
        SOURCE.replace("on_pline y2 x2 x1 y1", "on_pline y2 x2 x1 z1"),
        SOURCE.replace("on_tline w2 y2 a c", "on_tline w2 y2 a b"),
        SOURCE.replace("circumcenter o2 u2 v2 w2", "circumcenter o2 u1 v2 w2"),
        SOURCE.replace("on_circle t o2 u2", "on_circle t o1 u2"),
        SOURCE.replace("? coll o1 o2 t", "? coll o1 u1 t"),
    ),
)
def test_nearby_non_theorems_are_rejected(mutated: str) -> None:
    application = certify_jgex_parallel_transversal_perpendicular_circles_application(
        mutated
    )

    assert application.replayed is False


def test_renderer_returns_svg() -> None:
    rendered = render_parallel_transversal_perpendicular_circles_chart_svg()

    assert rendered.startswith("<?xml")
    assert "<svg" in rendered[:512]
    assert "Parallel transversals" in rendered
