"""Replay the existential branch of the reflected-chord circle theorem.

The parent cyclic configuration is normalized so the shared chord CD is the
x-axis with C=(-1,0), D=(1,0).  Instead of solving the unordered intersection
of (PQR) and (A'XY), construct its two labels by known-root circle steps:

* N is the non-R intersection of (PQR) and (DRY);
* M is the non-Q intersection of (PQR) and (XQC).

Both points are then proved to lie on (A'XY).  The non-N intersection K of DN
and (PQR) is rational as well, and C,M,K are collinear.  Every construction is
therefore replayed over QQ(w,alpha,beta,epsilon), without square roots.
"""

from __future__ import annotations

import time

from sympy.polys.domains import QQ
from sympy.polys.fields import field


def main() -> None:
    started = time.perf_counter()
    base, w, alpha, beta, epsilon = field("w,alpha,beta,epsilon", QQ)
    zero, one = base.zero, base.one

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

    def second_circle_intersection(known, carrier, coefficients):
        direction = subtract(carrier, known)
        quadratic = dot(direction, direction)
        linear = (
            2 * dot(known, direction)
            + coefficients[0] * direction[0]
            + coefficients[1] * direction[1]
        )
        return add(known, scale(-linear / quadratic, direction))

    def second_circle_circle_intersection(known, first, second):
        radical_linear = first[0] - second[0]
        radical_vertical = first[1] - second[1]
        carrier = add(known, (radical_vertical, -radical_linear))
        return second_circle_intersection(known, carrier, first)

    def parent_point(parameter):
        denominator = one + parameter * parameter
        return (
            (one + 2 * w * parameter - parameter * parameter) / denominator,
            2 * parameter * (one + w * parameter) / denominator,
        )

    c = (-one, zero)
    d = (one, zero)
    a = parent_point(alpha)
    b = parent_point(beta)
    e = parent_point(epsilon)
    reflected_a = (a[0], -a[1])
    parent_circle = (zero, -2 * w, -one)
    x = line_intersection(a, b, c, d)
    y = line_intersection(a, e, c, d)
    p = line_intersection(e, x, b, y)
    q = second_circle_intersection(e, x, parent_circle)
    r = second_circle_intersection(b, y, parent_circle)
    omega = circle_coefficients(p, q, r)
    sigma = circle_coefficients(reflected_a, x, y)
    print(f"base_construction_seconds={time.perf_counter() - started:.3f}")

    dry_circle = circle_coefficients(d, r, y)
    xqc_circle = circle_coefficients(x, q, c)
    n = second_circle_circle_intersection(r, omega, dry_circle)
    print(f"N_known_root_seconds={time.perf_counter() - started:.3f}")
    m = second_circle_circle_intersection(q, omega, xqc_circle)
    print(f"M_known_root_seconds={time.perf_counter() - started:.3f}")
    k = second_circle_intersection(n, d, omega)
    print(f"K_known_root_seconds={time.perf_counter() - started:.3f}")

    residuals = {
        "N_on_omega": circle_value(n, omega),
        "N_on_DRY": circle_value(n, dry_circle),
        "N_on_sigma": circle_value(n, sigma),
        "M_on_omega": circle_value(m, omega),
        "M_on_XQC": circle_value(m, xqc_circle),
        "M_on_sigma": circle_value(m, sigma),
        "K_on_DN": cross(subtract(k, d), subtract(n, d)),
        "K_on_omega": circle_value(k, omega),
        "C_M_K_collinear": cross(subtract(m, c), subtract(k, c)),
    }
    print(f"residual_construction_seconds={time.perf_counter() - started:.3f}")
    for name, value in residuals.items():
        print(f"{name}={value == zero}")
        if value != zero:
            print(f"{name}_residual={value}")
    print(f"full_replay_seconds={time.perf_counter() - started:.3f}")


if __name__ == "__main__":
    main()
