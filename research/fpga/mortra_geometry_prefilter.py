"""Synthesizable MORTRA geometry candidate prefilter.

The circuit is deliberately outside the truth plane.  It rejects only the
same obvious numerical degeneracies as ``numerical_precondition_holds`` and
passes every surviving construction to the symbolic verifier.
"""

from __future__ import annotations

from dataclasses import dataclass

from amaranth import Elaboratable, Module, Mux, Signal, signed


OP_PASS = 0
OP_DISTINCT_PAIR = 1
OP_NONCOLLINEAR_TRIPLE = 2
OP_NONPARALLEL_LINES = 3


@dataclass(frozen=True)
class PrefilterVector:
    opcode: int
    points: tuple[tuple[int, int], ...]


def reference_accept(vector: PrefilterVector, *, tolerance: int = 1) -> bool:
    points = (*vector.points, *((0, 0),) * (4 - len(vector.points)))

    def squared_distance(left: int, right: int) -> int:
        dx = points[right][0] - points[left][0]
        dy = points[right][1] - points[left][1]
        return dx * dx + dy * dy

    def oriented_area(a: int, b: int, c: int) -> int:
        abx = points[b][0] - points[a][0]
        aby = points[b][1] - points[a][1]
        acx = points[c][0] - points[a][0]
        acy = points[c][1] - points[a][1]
        return abx * acy - aby * acx

    if vector.opcode == OP_DISTINCT_PAIR:
        return squared_distance(0, 1) > tolerance * tolerance
    if vector.opcode == OP_NONCOLLINEAR_TRIPLE:
        return abs(oriented_area(0, 1, 2)) > tolerance
    if vector.opcode == OP_NONPARALLEL_LINES:
        abx = points[1][0] - points[0][0]
        aby = points[1][1] - points[0][1]
        cdx = points[3][0] - points[2][0]
        cdy = points[3][1] - points[2][1]
        return abs(abx * cdy - aby * cdx) > tolerance
    return True


class GeometryPrefilter(Elaboratable):
    """One-stage fixed-point pipeline accepting one candidate per clock."""

    def __init__(self, *, coordinate_width: int = 18, tolerance: int = 1) -> None:
        if coordinate_width < 4:
            raise ValueError("coordinate_width must be at least four bits")
        self.coordinate_width = coordinate_width
        self.tolerance = tolerance
        self.valid_in = Signal()
        self.opcode = Signal(2)
        self.x = tuple(Signal(signed(coordinate_width), name=f"x{index}") for index in range(4))
        self.y = tuple(Signal(signed(coordinate_width), name=f"y{index}") for index in range(4))
        self.valid_out = Signal()
        self.accept = Signal()

    def elaborate(self, platform) -> Module:
        del platform
        m = Module()
        delta_width = self.coordinate_width + 1
        product_width = 2 * delta_width
        sum_width = product_width + 1

        dx01 = Signal(signed(delta_width))
        dy01 = Signal(signed(delta_width))
        dx02 = Signal(signed(delta_width))
        dy02 = Signal(signed(delta_width))
        dx23 = Signal(signed(delta_width))
        dy23 = Signal(signed(delta_width))
        dist2 = Signal(sum_width)
        area012 = Signal(signed(sum_width))
        cross_lines = Signal(signed(sum_width))
        decision = Signal(reset=1)

        m.d.comb += [
            dx01.eq(self.x[1] - self.x[0]),
            dy01.eq(self.y[1] - self.y[0]),
            dx02.eq(self.x[2] - self.x[0]),
            dy02.eq(self.y[2] - self.y[0]),
            dx23.eq(self.x[3] - self.x[2]),
            dy23.eq(self.y[3] - self.y[2]),
            dist2.eq(dx01 * dx01 + dy01 * dy01),
            area012.eq(dx01 * dy02 - dy01 * dx02),
            cross_lines.eq(dx01 * dy23 - dy01 * dx23),
            decision.eq(1),
        ]
        with m.Switch(self.opcode):
            with m.Case(OP_DISTINCT_PAIR):
                m.d.comb += decision.eq(dist2 > self.tolerance * self.tolerance)
            with m.Case(OP_NONCOLLINEAR_TRIPLE):
                m.d.comb += decision.eq(
                    (area012 > self.tolerance) | (area012 < -self.tolerance)
                )
            with m.Case(OP_NONPARALLEL_LINES):
                m.d.comb += decision.eq(
                    (cross_lines > self.tolerance)
                    | (cross_lines < -self.tolerance)
                )

        m.d.sync += [
            self.valid_out.eq(self.valid_in),
            self.accept.eq(Mux(self.valid_in, decision, 0)),
        ]
        return m


def ports(design: GeometryPrefilter) -> list[Signal]:
    return [
        design.valid_in,
        design.opcode,
        *design.x,
        *design.y,
        design.valid_out,
        design.accept,
    ]
