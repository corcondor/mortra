"""Problem-independent polynomial certificates for local geometry lemmas."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import sympy as sp


@dataclass(frozen=True)
class PolynomialLemmaCertificate:
    theorem: str
    generators: tuple[str, ...]
    target: str
    multipliers: tuple[str, ...]
    residual: str
    replayed: bool
    certificate_sha256: str


def external_homothety_tangent_certificate() -> PolynomialLemmaCertificate:
    """Certify that the external homothety center lies on each outer tangent.

    The oriented tangent constraints are
    ``c - n.C1 - r1 = 0`` and ``c - n.C2 - r2 = 0``.  The two coordinate
    equations ``gx = gy = 0`` define the external homothety center K.  No
    concrete point names, coordinates, or benchmark values occur here.
    """

    c1x, c1y, c2x, c2y, kx, ky, nx, ny, c, r1, r2 = sp.symbols(
        "c1x c1y c2x c2y kx ky nx ny c r1 r2"
    )
    gx = (r1 - r2) * kx - r1 * c2x + r2 * c1x
    gy = (r1 - r2) * ky - r1 * c2y + r2 * c1y
    tangent_a = c - nx * c1x - ny * c1y - r1
    tangent_b = c - nx * c2x - ny * c2y - r2
    target = (r1 - r2) * (nx * kx + ny * ky - c)
    generators = (gx, gy, tangent_a, tangent_b)
    multipliers = (nx, ny, r2, -r1)
    residual = sp.expand(
        target
        - sum(
            (
                multiplier * generator
                for multiplier, generator in zip(multipliers, generators, strict=True)
            ),
            sp.Integer(0),
        )
    )
    material = "|".join(
        (
            "external_common_tangents_intersect_at_external_homothety_center",
            *(sp.sstr(item) for item in generators),
            sp.sstr(target),
            *(sp.sstr(item) for item in multipliers),
            sp.sstr(residual),
        )
    )
    return PolynomialLemmaCertificate(
        theorem="external_common_tangents_intersect_at_external_homothety_center",
        generators=tuple(sp.sstr(item) for item in generators),
        target=sp.sstr(target),
        multipliers=tuple(sp.sstr(item) for item in multipliers),
        residual=sp.sstr(residual),
        replayed=residual == 0,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )


def external_homothety_boundary_certificates() -> tuple[
    PolynomialLemmaCertificate,
    PolynomialLemmaCertificate,
]:
    """Certify center collinearity and the radius/distance ratio at K."""

    c1x, c1y, c2x, c2y, kx, ky, r1, r2 = sp.symbols("c1x c1y c2x c2y kx ky r1 r2")
    gx = r1 * (kx - c2x) - r2 * (kx - c1x)
    gy = r1 * (ky - c2y) - r2 * (ky - c1y)
    generators = (gx, gy)

    center_dx = c2x - c1x
    center_dy = c2y - c1y
    collinear_target = (r1 - r2) * ((kx - c1x) * center_dy - (ky - c1y) * center_dx)
    collinear_multipliers = (center_dy, -center_dx)

    first_x = r1 * (kx - c2x)
    first_y = r1 * (ky - c2y)
    second_x = r2 * (kx - c1x)
    second_y = r2 * (ky - c1y)
    ratio_target = (
        first_x * first_x
        + first_y * first_y
        - second_x * second_x
        - second_y * second_y
    )
    ratio_multipliers = (first_x + second_x, first_y + second_y)

    def build(
        theorem: str,
        target: sp.Expr,
        multipliers: tuple[sp.Expr, ...],
    ) -> PolynomialLemmaCertificate:
        residual = sp.expand(
            target
            - sum(
                (
                    multiplier * generator
                    for multiplier, generator in zip(
                        multipliers, generators, strict=True
                    )
                ),
                sp.Integer(0),
            )
        )
        material = "|".join(
            (
                theorem,
                *(sp.sstr(item) for item in generators),
                sp.sstr(target),
                *(sp.sstr(item) for item in multipliers),
                sp.sstr(residual),
            )
        )
        return PolynomialLemmaCertificate(
            theorem=theorem,
            generators=tuple(sp.sstr(item) for item in generators),
            target=sp.sstr(target),
            multipliers=tuple(sp.sstr(item) for item in multipliers),
            residual=sp.sstr(residual),
            replayed=residual == 0,
            certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        )

    return (
        build(
            "external_homothety_centers_are_collinear",
            collinear_target,
            collinear_multipliers,
        ),
        build(
            "external_homothety_preserves_radius_distance_ratio",
            ratio_target,
            ratio_multipliers,
        ),
    )
