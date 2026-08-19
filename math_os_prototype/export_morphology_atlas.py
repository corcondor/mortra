"""Export the morphology atlas used by autonomous generation gates."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from math_os_prototype.morphology_graph import EDGES, NODES, shortest_path
    from math_os_prototype.morphology_geometry_synthesis import (
        PARABOLA_PATH,
        POLYGON_PATH,
    )
except ImportError:  # pragma: no cover
    from morphology_graph import EDGES, NODES, shortest_path
    from morphology_geometry_synthesis import PARABOLA_PATH, POLYGON_PATH


HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "docs" / "generated" / "latest-morphology-atlas.md"


def _route(source: str, target: str, *, conditions: list[str] | None = None) -> str:
    path = shortest_path(source, target, established_conditions=conditions) or []
    return " -> ".join(path)


def render() -> str:
    lines = [
        "# MathOS モルフォロジー・アトラス",
        "",
        f"- 型付き表現ノード: **{len(NODES)}**",
        f"- 許可された隣接射: **{len(EDGES)}**",
        "- 裸の数値代入による接続: **0**",
        "",
        "## 採用条件",
        "",
        "異分野候補は隣接する型付き射だけをたどり、各射で数学対象または不変量を明示的に輸送する。",
        "経路の各辺は実際の解法射列と同じ順序で現れ、複数条件が合流する証明DAGを持たなければならない。",
        "条件付き射は必要な前提の証明も要求する。分野名や数値型が一致するだけでは接続と認めない。",
        "",
        "## 検証済み経路",
        "",
        "二次式の係数から条件付きモーメントまで:",
        "",
        f"`{_route('QuadraticCoefficientFamily', 'ConditionalMomentObservable')}`",
        "",
        "複素幾何から確率の期待値まで:",
        "",
        f"`{_route('ComplexConfiguration', 'ExpectationObservable')}`",
        "",
        "根の対称式から軌跡と極値まで:",
        "",
        f"`{' -> '.join(PARABOLA_PATH)}`",
        "",
        "単位根の対蹠点分解から数え上げまで（条件付き）:",
        "",
        f"`{' -> '.join(POLYGON_PATH)}`",
        "",
        "遠い分野への直結辺は置かない。条件付きの近道は、その条件を証明した問題だけが利用できる。",
        "",
        "## 隣接射一覧",
        "",
        "| 始域 | 射 | 終域 | 輸送される意味 | 必要条件 |",
        "|---|---|---|---|---|",
    ]
    for edge in EDGES:
        conditions = ", ".join(edge.requires) if edge.requires else "-"
        lines.append(
            f"| `{edge.source}` | `{edge.name}` | `{edge.target}` | "
            f"{', '.join(edge.transport)} | {conditions} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render())
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
