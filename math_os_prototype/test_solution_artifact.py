from math_os_prototype.solution_artifact import _state_diagram_tex, _state_layout


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
