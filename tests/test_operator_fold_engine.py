"""Unit tests for operator folding, symplectic preservation, and cross-domain homomorphism."""
import math
import pytest

from math_os_prototype.operator_fold_engine import (
    LinearOperator2D,
    OperatorTrain,
)
from math_os_prototype.paraxial_optics_domain import (
    GaussianBeam,
    ParaxialSolver,
    Ray,
)


def test_elementary_operators():
    # 1. Free space P(d)
    d = 0.25  # 250 mm
    p = LinearOperator2D.free_space(d)
    assert p.det() == 1.0
    assert p.is_symplectic()

    # Ray action: x' = x + d*theta, theta' = theta
    x_out, theta_out = p.apply_vector(0.01, 0.05)
    assert abs(x_out - (0.01 + d * 0.05)) < 1e-15
    assert theta_out == 0.05

    # Möbius action on q: q' = q + d
    q_in = 0.1 + 0.5j
    q_out = p.apply_mobius(q_in)
    assert abs(q_out - (q_in + d)) < 1e-15

    # 2. Thin lens L(f)
    f = 0.1  # 100 mm
    lens = LinearOperator2D.thin_lens(f)
    assert lens.det() == 1.0
    assert lens.is_symplectic()

    # Ray action: x' = x, theta' = theta - x/f
    x_out, theta_out = lens.apply_vector(0.01, 0.05)
    assert x_out == 0.01
    assert abs(theta_out - (0.05 - 0.01 / f)) < 1e-15

    # Möbius action on q: 1/q' = 1/q - 1/f
    inv_q_in = 1.0 / q_in
    inv_q_out = 1.0 / lens.apply_mobius(q_in)
    assert abs(inv_q_out - (inv_q_in - 1.0 / f)) < 1e-14


def test_homomorphism_property():
    """Verify group homomorphism Phi(M2 * M1)(q) == Phi(M2)(Phi(M1)(q))."""
    p1 = LinearOperator2D.free_space(0.15)
    lens = LinearOperator2D.thin_lens(0.08)
    p2 = LinearOperator2D.free_space(0.20)

    # Composite operator: M = P2 * Lens * P1
    m_composite = p2.compose(lens).compose(p1)
    assert m_composite.is_symplectic()

    q_test = 0.05 + 0.3j
    # Sequential Möbius
    q_seq = p2.apply_mobius(lens.apply_mobius(p1.apply_mobius(q_test)))
    # Composite Möbius
    q_comp = m_composite.apply_mobius(q_test)

    assert abs(q_seq - q_comp) < 1e-13


def test_keplerian_telescope_train():
    """Test 4f Keplerian telescope: P(f1) -> L(f1) -> P(f1+f2) -> L(f2) -> P(f2)."""
    f1 = 0.100  # 100 mm
    f2 = 0.050  # 50 mm
    train = OperatorTrain(name="KeplerianTelescope")
    train.append(LinearOperator2D.free_space(f1))
    train.append(LinearOperator2D.thin_lens(f1))
    train.append(LinearOperator2D.free_space(f1 + f2))
    train.append(LinearOperator2D.thin_lens(f2))
    train.append(LinearOperator2D.free_space(f2))

    assert len(train) == 5
    folded = train.fold()
    assert folded.is_symplectic()

    # For an afocal telescope with focal lengths f1, f2:
    # Transverse magnification m = -f2/f1 = -0.5
    # Angular magnification = 1/m = -2.0
    # A = m = -0.5, D = 1/m = -2.0, B = 0, C = 0
    assert abs(folded.a - (-f2 / f1)) < 1e-12
    assert abs(folded.b) < 1e-12
    assert abs(folded.c) < 1e-12
    assert abs(folded.d - (-f1 / f2)) < 1e-12

    # Verify equivalence on a set of test rays and beams
    rays = [(0.01, 0.0), (0.0, 0.02), (-0.005, 0.01)]
    beams = [0.0 + 0.2j, 0.05 + 0.4j]
    eval_res = train.verify_fold_equivalence(rays, beams)
    assert eval_res["verified"]
    assert eval_res["max_ray_residual"] < 1e-14
    assert eval_res["max_beam_residual"] < 1e-14


def test_paraxial_solver_cross_domain_reuse():
    """Verify solver A/B behavior: Condition A (sequential) vs Condition B (fold reuse)."""
    train = OperatorTrain(name="RelaySystem")
    for _ in range(3):
        train.append(LinearOperator2D.free_space(0.1))
        train.append(LinearOperator2D.thin_lens(0.05))
    train.append(LinearOperator2D.free_space(0.1))

    # Condition A: Untrained (no library)
    solver_a = ParaxialSolver()
    ray_in = Ray(x=0.005, theta=0.01)
    ray_out_a, rec_ray_a = solver_a.solve_ray_propagation(train, ray_in, use_library=False)
    assert rec_ray_a.condition == "A"
    assert not rec_ray_a.fold_used
    assert rec_ray_a.primitive_applications == len(train)
    assert rec_ray_a.intermediate_expression_size == len(train)

    # Condition B: Trained with fold
    # Simulate acquisition: fold the train and register in library
    compact_op = train.fold()
    solver_b = ParaxialSolver(acquired_library={train.name: compact_op})

    ray_out_b, rec_ray_b = solver_b.solve_ray_propagation(train, ray_in, use_library=True)
    assert rec_ray_b.condition == "B"
    assert rec_ray_b.fold_used
    assert rec_ray_b.primitive_applications == 1  # 1 compact application!
    assert rec_ray_b.intermediate_expression_size == 1  # compact size!
    assert abs(ray_out_a.x - ray_out_b.x) < 1e-13
    assert abs(ray_out_a.theta - ray_out_b.theta) < 1e-13

    # Cross-domain reuse: Wave optics Gaussian beam with the EXACT SAME acquired library
    beam_in = GaussianBeam(q=0.0 + 0.15j)
    beam_out_a, rec_beam_a = solver_a.solve_beam_propagation(train, beam_in, use_library=False)
    beam_out_b, rec_beam_b = solver_b.solve_beam_propagation(train, beam_in, use_library=True)

    assert rec_beam_b.condition == "B"
    assert rec_beam_b.fold_used
    assert rec_beam_b.primitive_applications == 1
    assert rec_beam_b.intermediate_expression_size == 1
    assert abs(beam_out_a.q - beam_out_b.q) < 1e-13
