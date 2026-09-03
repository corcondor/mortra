from math_os_prototype.solution_artifact import (
    _plane_diagram_tex,
    _safe_statement,
    _state_diagram_tex,
    _state_layout,
    _variation_diagram_tex,
)


def test_plane_diagram_renders_explicit_math_labels_without_escaping() -> None:
    diagram = {
        "kind": "plane",
        "viewport": {"xMin": 0, "xMax": 3, "yMin": -1, "yMax": 1},
        "axes": True,
        "shapes": [
            {
                "kind": "label",
                "point": {"x": 2, "y": 0},
                "tex": r"1+\sqrt{3}",
            }
        ],
    }

    tex = _plane_diagram_tex(diagram)

    assert r"\(1+\sqrt{3}\)" in tex
    assert r"\textbackslash{}sqrt" not in tex


def test_safe_statement_removes_internal_trailing_whitespace() -> None:
    assert _safe_statement("$x>1$において, \n\\[x<2\\]\n") == "$x>1$において,\n\\[x<2\\]"


def test_variation_diagram_distinguishes_math_cells_from_text_cells() -> None:
    tex = _variation_diagram_tex(
        {
            "kind": "variation",
            "variableLabel": "傾き",
            "columns": ({"tex": r"1<a<e"},),
            "rows": (
                {
                    "label": "共通部分",
                    "cells": ({"tex": r"1-\log a<b<a(1-\log a)"},),
                },
            ),
        }
    )

    assert r"\(1<a<e\)" in tex
    assert r"\(1-\log a<b<a(1-\log a)\)" in tex
    assert r"\textbackslash{}log" not in tex


def test_state_diagram_renders_formulae_in_non_overlapping_boxes() -> None:
    diagram = {
        "kind": "state",
        "states": [
            {"id": "odd", "label": r"J_{2n-1}=a_{2n}"},
            {"id": "even", "label": r"J_{2n}"},
            {
                "id": "squeeze",
                "label": r"\frac{2n}{2n+1}<\frac{J_{2n}}{J_{2n-1}}<1",
            },
            {"id": "limit", "label": r"\sqrt n\,a_{2n}\to\sqrt\pi/2", "terminal": True},
        ],
        "transitions": [
            {"from": "odd", "to": "squeeze", "label": "単調性"},
            {"from": "even", "to": "squeeze", "label": "縮約公式"},
            {
                "from": "squeeze",
                "to": "limit",
                "label": r"J_{2n-1}J_{2n}=\pi/(4n)",
            },
        ],
    }

    tex = _state_diagram_tex(diagram)

    assert "draw,circle" not in tex
    assert "state box/.style" in tex
    assert r"\(\displaystyle J_{2n-1}=a_{2n}\)" in tex
    assert r"\resizebox{25mm}{!}{\(\displaystyle \frac{2n}" in tex
    assert r"\textbackslash{}frac" not in tex
    assert "node[midway,edge label,above=6.5mm]" in tex
    assert "at (0,0.500)" in tex
    assert "at (0,-0.500)" in tex
    assert "at (1,0.000)" in tex
    assert "at (2,0.000)" in tex


def test_state_layout_wraps_long_forward_chains_serpentine() -> None:
    states = [{"id": f"s{index}", "label": f"S_{index}"} for index in range(6)]
    transitions = [
        {"from": f"s{index}", "to": f"s{index + 1}"}
        for index in range(5)
    ]

    positions, ranks = _state_layout(states, transitions)

    assert ranks == {index: index for index in range(6)}
    assert positions[0][0] == 0
    assert positions[3][0] == 3
    assert positions[4][0] == 3
    assert positions[5][0] == 2
    assert positions[4][1] < positions[0][1]
