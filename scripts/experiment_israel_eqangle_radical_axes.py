"""Derive the exact radical-axis certificate for the cevian-circle theorem.

This experiment deliberately avoids constructing any of the three named
second circle intersections.  Their carrier lines are the radical axes of the
parent circumcircle and the corresponding cevian circles, so every later point
is rational over QQ(u,v,r,s).
"""

from __future__ import annotations

import time

from sympy.polys.domains import QQ
from sympy.polys.fields import field


def main() -> None:
    started = time.perf_counter()
    rational_field, u, v, r, s = field("u,v,r,s", QQ)
    zero = rational_field.zero
    one = rational_field.one

    def add(left, right):
        return left[0] + right[0], left[1] + right[1]

    def subtract(left, right):
        return left[0] - right[0], left[1] - right[1]

    def scale(factor, value):
        return factor * value[0], factor * value[1]

    def dot(left, right):
        return left[0] * right[0] + left[1] * right[1]

    def cross(left, right):
        return left[0] * right[1] - left[1] * right[0]

    def line_intersection(a, b, c, d):
        ab = subtract(b, a)
        cd = subtract(d, c)
        parameter = cross(subtract(c, a), cd) / cross(ab, cd)
        return add(a, scale(parameter, ab))

    def implicit_line_intersection(first, second):
        determinant = first[0] * second[1] - first[1] * second[0]
        return (
            (first[1] * second[2] - first[2] * second[1]) / determinant,
            (first[2] * second[0] - first[0] * second[2]) / determinant,
        )

    def circle_coefficients(a, b, c):
        ab = subtract(b, a)
        ac = subtract(c, a)
        norm_a = dot(a, a)
        rhs_b = -(dot(b, b) - norm_a)
        rhs_c = -(dot(c, c) - norm_a)
        determinant = cross(ab, ac)
        horizontal = (rhs_b * ac[1] - rhs_c * ab[1]) / determinant
        vertical = (ab[0] * rhs_c - ac[0] * rhs_b) / determinant
        constant = -(norm_a + horizontal * a[0] + vertical * a[1])
        return horizontal, vertical, constant

    def circle_value(point, coefficients):
        return (
            dot(point, point)
            + coefficients[0] * point[0]
            + coefficients[1] * point[1]
            + coefficients[2]
        )

    def radical_axis(first, second):
        return tuple(
            left - right for left, right in zip(first, second, strict=True)
        )

    a = (zero, zero)
    b = (one, zero)
    c = (u, v)
    p = (r, s)

    p1 = line_intersection(a, p, b, c)
    p2 = line_intersection(b, p, a, c)
    p3 = line_intersection(c, p, a, b)

    parent_circle = circle_coefficients(a, b, c)
    cevian_a_circle = circle_coefficients(a, p2, p3)
    cevian_b_circle = circle_coefficients(b, p3, p1)
    cevian_c_circle = circle_coefficients(c, p1, p2)

    axis_a = radical_axis(cevian_a_circle, parent_circle)
    axis_b = radical_axis(cevian_b_circle, parent_circle)
    axis_c = radical_axis(cevian_c_circle, parent_circle)
    b1 = implicit_line_intersection(axis_a, axis_c)
    c1 = implicit_line_intersection(axis_a, axis_b)
    k = line_intersection(b, b1, c, c1)

    equal_angle = (
        cross(subtract(b, p), subtract(c, p))
        * dot(subtract(c, a), subtract(b, a))
        - dot(subtract(b, p), subtract(c, p))
        * cross(subtract(c, a), subtract(b, a))
    )
    cyclic_goal = circle_value(k, cevian_a_circle)

    quotient, remainder = cyclic_goal.numer.div(equal_angle.numer)
    print(f"elapsed_seconds={time.perf_counter() - started:.3f}")
    def total_degree(polynomial):
        return max((sum(monomial) for monomial in polynomial.monoms()), default=0)

    print(f"equal_angle_degree={total_degree(equal_angle.numer)}")
    print(f"cyclic_goal_degree={total_degree(cyclic_goal.numer)}")
    print(f"quotient_degree={total_degree(quotient)}")
    print(f"remainder_zero={not remainder}")
    print(f"quotient={quotient}")
    print(f"quotient_factorization={quotient.factor_list()}")


if __name__ == "__main__":
    main()
