"""General linear operator composition, folding, and cross-domain homomorphism engine.

This module provides domain-agnostic operator algebra for 2D symplectic linear
transformations, specifically paraxial optical systems, and their homomorphic
actions across multiple domains:
  1. Vector action (geometric ray optics: (x, theta) -> (x', theta'))
  2. Projective / Möbius action on the Poincaré upper half-plane
     (wave optics: complex beam parameter q -> (A q + B) / (C q + D))
  3. Fold contraction: transforming an O(N) sequence of operators into an O(1)
     compact operator representation preserving det(M) = 1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import math
from typing import Any, Sequence


@dataclass(frozen=True)
class LinearOperator2D:
    """A 2x2 linear symplectic operator M = [[A, B], [C, D]].

    In paraxial optics:
      - Free space of length d:  P(d) = [[1, d], [0, 1]]
      - Thin lens of focal f:   L(f) = [[1, 0], [-1/f, 1]]
    Invariance:
      det(M) = A*D - B*C == 1 (preserves phase space volume / optical invariant).
    """
    a: float
    b: float
    c: float
    d: float
    name: str = "operator"
    element_type: str = "generic"
    parameter: float = 0.0

    def det(self) -> float:
        """Determinant of the operator."""
        return self.a * self.d - self.b * self.c

    def is_symplectic(self, tol: float = 1e-9) -> bool:
        """Verify det(M) == 1 within numerical tolerance."""
        return abs(self.det() - 1.0) < tol

    def compose(self, other: LinearOperator2D, name: str | None = None) -> LinearOperator2D:
        """Compose this operator with another: (self * other).

        If light passes through 'other' first, then 'self', the composite operator
        M_total = self * other.
        """
        new_a = self.a * other.a + self.b * other.c
        new_b = self.a * other.b + self.b * other.d
        new_c = self.c * other.a + self.d * other.c
        new_d = self.c * other.b + self.d * other.d
        comp_name = name or f"({self.name} o {other.name})"
        return LinearOperator2D(
            a=new_a,
            b=new_b,
            c=new_c,
            d=new_d,
            name=comp_name,
            element_type="composite",
            parameter=0.0,
        )

    def apply_vector(self, x: float, theta: float) -> tuple[float, float]:
        """Linear action on a 2D vector (ray position x, angle theta).

        [x', theta']^T = [[A, B], [C, D]] * [x, theta]^T
        """
        x_out = self.a * x + self.b * theta
        theta_out = self.c * x + self.d * theta
        return x_out, theta_out

    def apply_mobius(self, q: complex) -> complex:
        """Projective Möbius action on a complex number (Gaussian beam q parameter).

        q' = (A * q + B) / (C * q + D)
        For physical Gaussian beams in the upper half-plane (Im(q) > 0),
        det(M) > 0 guarantees Im(q') > 0.
        """
        denom = self.c * q + self.d
        if abs(denom) < 1e-15:
            raise ZeroDivisionError(f"Singular point in Möbius transformation: C*q + D = {denom}")
        return (self.a * q + self.b) / denom

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "element_type": self.element_type,
            "parameter": self.parameter,
            "matrix": [[self.a, self.b], [self.c, self.d]],
            "det": self.det(),
        }

    @staticmethod
    def identity() -> LinearOperator2D:
        return LinearOperator2D(1.0, 0.0, 0.0, 1.0, name="I", element_type="identity")

    @staticmethod
    def free_space(d: float, name: str | None = None) -> LinearOperator2D:
        """Free space propagation of distance d (meters)."""
        op_name = name or f"P({d:g}m)"
        return LinearOperator2D(1.0, float(d), 0.0, 1.0, name=op_name, element_type="free_space", parameter=float(d))

    @staticmethod
    def thin_lens(f: float, name: str | None = None) -> LinearOperator2D:
        """Thin lens refraction with focal length f (meters)."""
        if abs(f) < 1e-15:
            raise ValueError("Focal length cannot be zero")
        op_name = name or f"L({f:g}m)"
        return LinearOperator2D(1.0, 0.0, -1.0 / float(f), 1.0, name=op_name, element_type="thin_lens", parameter=float(f))


@dataclass
class OperatorTrain:
    """An ordered sequence of operators representing a composite system.

    Light propagates through elements[0], then elements[1], ..., up to elements[-1].
    """
    elements: list[LinearOperator2D] = field(default_factory=list)
    name: str = "OpticalTrain"

    def __len__(self) -> int:
        return len(self.elements)

    def append(self, element: LinearOperator2D) -> None:
        self.elements.append(element)

    @property
    def expression_size_sequential(self) -> int:
        """Representation size in sequential form (number of elements)."""
        return len(self.elements)

    @property
    def expression_size_compact(self) -> int:
        """Representation size after folding (always 1 compact operator)."""
        return 1

    def fold(self) -> LinearOperator2D:
        """Contract the entire sequence into a single compact operator via associative fold.

        M_net = M_n * M_{n-1} * ... * M_1
        """
        if not self.elements:
            return LinearOperator2D.identity()
        net = self.elements[0]
        for elem in self.elements[1:]:
            # Net effect when light passes through 'net' then 'elem':
            # M_new = elem * net
            net = elem.compose(net)
        return net

    def apply_sequential_vector(
        self, x: float, theta: float
    ) -> tuple[tuple[float, float], list[tuple[float, float]]]:
        """Apply each element sequentially to ray (x, theta), recording trace."""
        curr_x, curr_theta = x, theta
        trace = [(curr_x, curr_theta)]
        for elem in self.elements:
            curr_x, curr_theta = elem.apply_vector(curr_x, curr_theta)
            trace.append((curr_x, curr_theta))
        return (curr_x, curr_theta), trace

    def apply_sequential_mobius(
        self, q: complex
    ) -> tuple[complex, list[complex]]:
        """Apply each element sequentially to complex q, recording trace."""
        curr_q = q
        trace = [curr_q]
        for elem in self.elements:
            curr_q = elem.apply_mobius(curr_q)
            trace.append(curr_q)
        return curr_q, trace

    def verify_fold_equivalence(
        self,
        test_rays: Sequence[tuple[float, float]],
        test_beams: Sequence[complex],
        tol: float = 1e-12,
    ) -> dict[str, Any]:
        """Verify exact mathematical equivalence between sequential execution and folded execution."""
        folded = self.fold()
        ray_residuals = []
        for x, theta in test_rays:
            (seq_x, seq_theta), _ = self.apply_sequential_vector(x, theta)
            fold_x, fold_theta = folded.apply_vector(x, theta)
            err_x = abs(seq_x - fold_x)
            err_theta = abs(seq_theta - fold_theta)
            ray_residuals.append(max(err_x, err_theta))

        beam_residuals = []
        for q in test_beams:
            seq_q, _ = self.apply_sequential_mobius(q)
            fold_q = folded.apply_mobius(q)
            err_q = abs(seq_q - fold_q)
            beam_residuals.append(err_q)

        max_ray_res = max(ray_residuals) if ray_residuals else 0.0
        max_beam_res = max(beam_residuals) if beam_residuals else 0.0

        return {
            "num_elements": len(self.elements),
            "folded_matrix": [[folded.a, folded.b], [folded.c, folded.d]],
            "folded_det": folded.det(),
            "is_symplectic": folded.is_symplectic(tol),
            "max_ray_residual": max_ray_res,
            "max_beam_residual": max_beam_res,
            "verified": (max_ray_res < tol) and (max_beam_res < tol) and folded.is_symplectic(tol),
        }
