"""Paraxial optics domain integrating operator folding with MORTRA's typed planner and contract session.

This module exposes sorts, primitive contracts, and acquisition mechanics for:
  - Ray optics (Ray: x, theta)
  - Wave optics (GaussianBeam: complex q parameter)
  - Optical elements (P(d), L(f))
  - Optical trains (sequences of elements)
  - Compact operators (folded SL(2, R) representations)

It provides the standard MORTRA life cycle:
  1. Sequential solving without fold (Condition A: Untrained baseline)
  2. Acquisition of compact folded operators during training
  3. Replay and cross-domain reuse of the same compact operator in wave optics
     (Condition B: With acquired fold)
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Callable, Sequence

from math_os_prototype.operator_fold_engine import (
    LinearOperator2D,
    OperatorTrain,
)
from math_os_prototype.runtime_typed_planner import (
    PrimitiveResult,
    RuntimeFact,
    RuntimePlan,
    RuntimePrimitive,
    RuntimeSearchProgress,
    initial_fact,
)


@dataclass(frozen=True)
class Ray:
    """Paraxial geometric ray with position x (m) and slope theta (rad)."""
    x: float
    theta: float

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.theta)


@dataclass(frozen=True)
class GaussianBeam:
    """Gaussian beam complex q parameter."""
    q: complex
    wavelength: float = 532e-9  # meters

    @property
    def waist_radius(self) -> float:
        """Beam radius w from Im(1/q) = -lambda / (pi * w^2)."""
        import math
        inv_q = 1.0 / self.q
        # Im(inv_q) = -lambda / (pi * w^2)
        val = -inv_q.imag
        if val <= 0.0:
            return float("nan")
        return math.sqrt(self.wavelength / (math.pi * val))

    @property
    def wavefront_curvature(self) -> float:
        """Wavefront radius of curvature R from Re(1/q) = 1/R."""
        inv_q = 1.0 / self.q
        if abs(inv_q.real) < 1e-15:
            return float("inf")
        return 1.0 / inv_q.real


# ---------------------------------------------------------------------------
# Execution Tracing & Metrics
# ---------------------------------------------------------------------------

@dataclass
class ParaxialExecutionRecord:
    task_id: str
    condition: str  # "A" or "B"
    domain: str  # "geometric", "wave", "cross_domain"
    solved: bool
    final_value: Any
    verification_residual: float
    primitive_applications: int
    plan_expansions: int
    intermediate_expression_size: int
    acquired_representation: str | None = None
    fold_used: bool = False
    proof_trace: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Solver Core for Paraxial System
# ---------------------------------------------------------------------------

class ParaxialSolver:
    """Deterministic solver for paraxial optical propagation with optional fold library."""

    def __init__(self, acquired_library: dict[str, LinearOperator2D] | None = None):
        self.acquired_library: dict[str, LinearOperator2D] = dict(acquired_library) if acquired_library else {}
        self.applications_count: int = 0
        self.expansions_count: int = 0

    def reset_counters(self) -> None:
        self.applications_count = 0
        self.expansions_count = 0

    # -- Primitives --

    def step_ray(self, elem: LinearOperator2D, ray: Ray) -> Ray:
        """Single primitive step: apply one optical element to a ray."""
        self.applications_count += 1
        new_x, new_theta = elem.apply_vector(ray.x, ray.theta)
        return Ray(x=new_x, theta=new_theta)

    def step_beam(self, elem: LinearOperator2D, beam: GaussianBeam) -> GaussianBeam:
        """Single primitive step: apply one optical element to a Gaussian beam."""
        self.applications_count += 1
        new_q = elem.apply_mobius(beam.q)
        return GaussianBeam(q=new_q, wavelength=beam.wavelength)

    def compose_train(self, train: OperatorTrain) -> LinearOperator2D:
        """Fold primitive: contract an optical train into a single compact operator."""
        self.applications_count += 1
        compact = train.fold()
        return compact

    def apply_compact_ray(self, compact: LinearOperator2D, ray: Ray) -> Ray:
        """Apply a compact folded operator to a ray in one step."""
        self.applications_count += 1
        new_x, new_theta = compact.apply_vector(ray.x, ray.theta)
        return Ray(x=new_x, theta=new_theta)

    def apply_compact_beam(self, compact: LinearOperator2D, beam: GaussianBeam) -> GaussianBeam:
        """Apply a compact folded operator to a Gaussian beam in one step (cross-domain reuse)."""
        self.applications_count += 1
        new_q = compact.apply_mobius(beam.q)
        return GaussianBeam(q=new_q, wavelength=beam.wavelength)

    # -- High Level Task Execution --

    def solve_ray_propagation(
        self, train: OperatorTrain, initial_ray: Ray, use_library: bool = False
    ) -> tuple[Ray, ParaxialExecutionRecord]:
        """Solve geometric ray propagation through an optical train."""
        self.reset_counters()
        trace = []
        proof_trace = []

        if use_library and self.acquired_library:
            # Condition B: use acquired compact operator if available for this train
            train_key = train.name
            compact = self.acquired_library.get(train_key)
            if compact is None and "universal_fold" in self.acquired_library:
                # If universal fold operator is acquired, fold the train and register
                compact = self.compose_train(train)
                proof_trace.append(f"fold({train.name}) -> compact [{compact.a:.4g}, {compact.b:.4g}, {compact.c:.4g}, {compact.d:.4g}]")

            if compact is not None:
                self.expansions_count += 1
                final_ray = self.apply_compact_ray(compact, initial_ray)
                proof_trace.append(f"apply_compact_ray(compact, ray_0) -> ray_final")
                expr_size = train.expression_size_compact
                fold_used = True
                acq_repr = f"Matrix([[ {compact.a:g}, {compact.b:g} ], [ {compact.c:g}, {compact.d:g} ]]), det={compact.det():g}"
                # Cache folded compact operator for cross-domain reuse
                self.acquired_library[train_key] = compact
            else:
                # Fallback to sequential
                final_ray, expr_size, fold_used, acq_repr = self._solve_ray_sequential(train, initial_ray, proof_trace)
        else:
            # Condition A: pure sequential propagation without fold
            final_ray, expr_size, fold_used, acq_repr = self._solve_ray_sequential(train, initial_ray, proof_trace)

        # Verification against ground truth sequential computation
        exact_ray, _ = train.apply_sequential_vector(initial_ray.x, initial_ray.theta)
        residual = max(abs(final_ray.x - exact_ray[0]), abs(final_ray.theta - exact_ray[1]))

        record = ParaxialExecutionRecord(
            task_id=f"ray_{train.name}",
            condition="B" if use_library else "A",
            domain="geometric",
            solved=(residual < 1e-11),
            final_value={"x": final_ray.x, "theta": final_ray.theta},
            verification_residual=residual,
            primitive_applications=self.applications_count,
            plan_expansions=self.expansions_count,
            intermediate_expression_size=expr_size,
            acquired_representation=acq_repr,
            fold_used=fold_used,
            proof_trace=proof_trace,
        )
        return final_ray, record

    def _solve_ray_sequential(
        self, train: OperatorTrain, initial_ray: Ray, proof_trace: list[str]
    ) -> tuple[Ray, int, bool, str | None]:
        curr = initial_ray
        for i, elem in enumerate(train.elements):
            self.expansions_count += 1
            curr = self.step_ray(elem, curr)
            proof_trace.append(f"step_ray({elem.name}, ray_{i}) -> ray_{i+1}")
        return curr, train.expression_size_sequential, False, None

    def solve_beam_propagation(
        self, train: OperatorTrain, initial_beam: GaussianBeam, use_library: bool = False
    ) -> tuple[GaussianBeam, ParaxialExecutionRecord]:
        """Solve wave optics Gaussian beam propagation through an optical train."""
        self.reset_counters()
        proof_trace = []

        if use_library and self.acquired_library:
            train_key = train.name
            compact = self.acquired_library.get(train_key)
            if compact is None and "universal_fold" in self.acquired_library:
                compact = self.compose_train(train)
                proof_trace.append(f"fold({train.name}) -> compact")

            if compact is not None:
                self.expansions_count += 1
                # Cross-domain reuse: apply the exact same compact operator acquired in geometric optics
                final_beam = self.apply_compact_beam(compact, initial_beam)
                proof_trace.append(f"apply_compact_beam(compact, beam_0) -> beam_final [reused from geometric fold]")
                expr_size = train.expression_size_compact
                fold_used = True
                acq_repr = f"Matrix([[ {compact.a:g}, {compact.b:g} ], [ {compact.c:g}, {compact.d:g} ]]), det={compact.det():g}"
            else:
                final_beam, expr_size, fold_used, acq_repr = self._solve_beam_sequential(train, initial_beam, proof_trace)
        else:
            final_beam, expr_size, fold_used, acq_repr = self._solve_beam_sequential(train, initial_beam, proof_trace)

        # Verification against ground truth
        exact_q, _ = train.apply_sequential_mobius(initial_beam.q)
        residual = abs(final_beam.q - exact_q)

        record = ParaxialExecutionRecord(
            task_id=f"beam_{train.name}",
            condition="B" if use_library else "A",
            domain="wave",
            solved=(residual < 1e-11),
            final_value={"q_real": final_beam.q.real, "q_imag": final_beam.q.imag, "waist": final_beam.waist_radius},
            verification_residual=residual,
            primitive_applications=self.applications_count,
            plan_expansions=self.expansions_count,
            intermediate_expression_size=expr_size,
            acquired_representation=acq_repr,
            fold_used=fold_used,
            proof_trace=proof_trace,
        )
        return final_beam, record

    def _solve_beam_sequential(
        self, train: OperatorTrain, initial_beam: GaussianBeam, proof_trace: list[str]
    ) -> tuple[GaussianBeam, int, bool, str | None]:
        curr = initial_beam
        for i, elem in enumerate(train.elements):
            self.expansions_count += 1
            curr = self.step_beam(elem, curr)
            proof_trace.append(f"step_beam({elem.name}, beam_{i}) -> beam_{i+1}")
        return curr, train.expression_size_sequential, False, None
