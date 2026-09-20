"""Fraunhofer diffraction of double-slit apertures under varying phase and coherence.

Simulates:
(a) In-phase illumination (Delta phi = 0) -> Central maximum (bright).
(b) Out-of-phase illumination (Delta phi = pi) -> Central minimum (dark).
(c) Mutually incoherent illumination -> Cross-interference terms vanish on time average,
    yielding twice the single-slit diffraction envelope.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class DiffractionConditionResult:
    condition_id: str
    description: str
    angles_rad: np.ndarray
    intensity_1d: np.ndarray
    intensity_2d: np.ndarray  # 1D repeated vertically for 2D visualization
    center_intensity: float
    fringe_period_rad: float | None
    total_power: float


@dataclass(frozen=True)
class DoubleSlitDiffractionResult:
    slit_width_m: float
    slit_separation_m: float
    wavelength_m: float
    angle_min_rad: float
    angle_max_rad: float
    in_phase: DiffractionConditionResult
    out_of_phase_pi: DiffractionConditionResult
    mutually_incoherent: DiffractionConditionResult
    theoretical_fringe_period: float


def compute_double_slit_diffraction(
    slit_width_m: float = 40e-6,
    slit_separation_m: float = 200e-6,
    wavelength_m: float = 532e-9,
    angle_range_rad: tuple[float, float] = (-0.012, 0.012),
    num_angle_points: int = 1000,
    vertical_repeat_height: int = 120,
) -> DoubleSlitDiffractionResult:
    """Compute Fraunhofer diffraction under in-phase, out-of-phase, and incoherent illumination.

    Standard Fraunhofer double slit formula:
    beta = (pi * a / lambda) * sin(theta)
    alpha = (pi * d / lambda) * sin(theta)

    Single slit diffraction envelope:
    sinc(beta) = sin(beta) / beta

    (a) In-phase:
    I_a(theta) = 4 * I_0 * sinc^2(beta) * cos^2(alpha)

    (b) Relative phase pi:
    I_b(theta) = 4 * I_0 * sinc^2(beta) * sin^2(alpha)

    (c) Mutually incoherent:
    I_c(theta) = 2 * I_0 * sinc^2(beta)

    All conditions use the exact same incident intensity / transmitted power standard I_0 = 1.0.
    """
    a = slit_width_m
    d = slit_separation_m
    w = wavelength_m
    th_min, th_max = angle_range_rad

    angles = np.linspace(th_min, th_max, num_angle_points, dtype=np.float64)

    # beta and alpha
    # For small angles sin(theta) ~ theta
    sin_theta = np.sin(angles)
    beta = (math.pi * a / w) * sin_theta
    alpha = (math.pi * d / w) * sin_theta

    # sinc(beta) using np.sinc (note: np.sinc(x) is sin(pi*x)/(pi*x))
    # so np.sinc(beta / pi) = sin(beta) / beta
    sinc_beta = np.sinc(beta / math.pi)
    sinc_sq = sinc_beta ** 2

    # (a) In-phase (Delta phi = 0)
    cos_sq = np.cos(alpha) ** 2
    i_a = 4.0 * sinc_sq * cos_sq

    # (b) Out-of-phase (Delta phi = pi)
    sin_sq = np.sin(alpha) ** 2
    i_b = 4.0 * sinc_sq * sin_sq

    # (c) Mutually incoherent
    i_c = 2.0 * sinc_sq

    # Compute total transmitted power (integral over angles)
    d_th = angles[1] - angles[0]
    p_a = float(np.sum(i_a) * d_th)
    p_b = float(np.sum(i_b) * d_th)
    p_c = float(np.sum(i_c) * d_th)

    # Theoretical fringe period
    fringe_period = w / d  # lambda / d in radians

    # 2D repeated vertically
    i_a_2d = np.tile(i_a, (vertical_repeat_height, 1))
    i_b_2d = np.tile(i_b, (vertical_repeat_height, 1))
    i_c_2d = np.tile(i_c, (vertical_repeat_height, 1))

    # Center intensity at theta = 0
    center_idx = np.argmin(np.abs(angles))
    c_a = float(i_a[center_idx])
    c_b = float(i_b[center_idx])
    c_c = float(i_c[center_idx])

    res_a = DiffractionConditionResult(
        condition_id="in_phase",
        description="In-phase illumination (Delta phi = 0)",
        angles_rad=angles,
        intensity_1d=i_a,
        intensity_2d=i_a_2d,
        center_intensity=c_a,
        fringe_period_rad=fringe_period,
        total_power=p_a,
    )

    res_b = DiffractionConditionResult(
        condition_id="out_of_phase_pi",
        description="Relative phase pi (Delta phi = pi)",
        angles_rad=angles,
        intensity_1d=i_b,
        intensity_2d=i_b_2d,
        center_intensity=c_b,
        fringe_period_rad=fringe_period,
        total_power=p_b,
    )

    res_c = DiffractionConditionResult(
        condition_id="mutually_incoherent",
        description="Mutually incoherent illumination",
        angles_rad=angles,
        intensity_1d=i_c,
        intensity_2d=i_c_2d,
        center_intensity=c_c,
        fringe_period_rad=None,  # No interference fringes
        total_power=p_c,
    )

    return DoubleSlitDiffractionResult(
        slit_width_m=a,
        slit_separation_m=d,
        wavelength_m=w,
        angle_min_rad=th_min,
        angle_max_rad=th_max,
        in_phase=res_a,
        out_of_phase_pi=res_b,
        mutually_incoherent=res_c,
        theoretical_fringe_period=fringe_period,
    )
