"""Benchmark script for wave optics representations and inverse design in MORTRA.

Measures:
1. Computational complexity and runtime: Convolution vs Transfer Function (O(N^4) vs O(N^2 log N))
2. Representation equivalence across sampling regimes (z < z_crit, z = z_crit, z > z_crit)
3. Round-trip inverse design reconstruction quality (PSNR, correlation, MSE)
4. Camera-in-the-loop (CITL) system identification parameter recovery
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import time

import numpy as np

repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from math_os_prototype.wave_optics_system import (
    CalibrationDigitalTwin,
    CameraInTheLoopCalibrator,
    FresnelPropagation,
    GreenFunction,
    GridSpec2D,
    IntensitySensor,
    MetasurfaceLenticularDisplay,
    OpticalTrain,
    RepresentationKind,
    SamplingCertificate,
    WaveField2D,
    phase_retrieval_gerchberg_saxton,
)


def run_benchmark() -> dict:
    results = {}
    wavelength = 532e-9  # 532 nm

    # -------------------------------------------------------------------------
    # 1. Complexity & Runtime Benchmark: Convolution vs Transfer Function
    # -------------------------------------------------------------------------
    runtime_table = []
    for n in [32, 64, 128]:
        dx = 10e-6
        grid = GridSpec2D(nx=n, ny=n, dx=dx, dy=dx)
        z_crit = (n * (dx ** 2)) / wavelength
        z = z_crit

        xx, yy = grid.spatial_coords()
        u = (xx ** 2 + yy ** 2 <= (n * dx / 4.0) ** 2).astype(np.complex128)
        field_in = WaveField2D(u=u, grid=grid, wavelength=wavelength, z=0.0)

        prop = FresnelPropagation(distance=z, wavelength=wavelength)

        # Warmup
        _ = prop.apply(field_in, representation=RepresentationKind.FOURIER_TRANSFER_FUNCTION)
        _ = prop.apply(field_in, representation=RepresentationKind.CONVOLUTION_KERNEL)

        # Timed Transfer Function (Angular Spectrum)
        n_repeats = 20
        t0 = time.perf_counter()
        for _ in range(n_repeats):
            f_tf = prop.apply(field_in, representation=RepresentationKind.FOURIER_TRANSFER_FUNCTION)
        time_tf = (time.perf_counter() - t0) / n_repeats

        # Timed Convolution Kernel
        t0 = time.perf_counter()
        for _ in range(n_repeats):
            f_conv = prop.apply(field_in, representation=RepresentationKind.CONVOLUTION_KERNEL)
        time_conv = (time.perf_counter() - t0) / n_repeats

        # Equivalence metrics
        i_tf = f_tf.intensity()
        i_cv = f_conv.intensity()
        norm_tf = i_tf - np.mean(i_tf)
        norm_cv = i_cv - np.mean(i_cv)
        corr = float(np.sum(norm_tf * norm_cv) / (np.linalg.norm(norm_tf) * np.linalg.norm(norm_cv) + 1e-12))
        mse = float(np.mean((i_tf - i_cv) ** 2))

        runtime_table.append({
            "grid_size": f"{n}x{n}",
            "z_crit_mm": round(z_crit * 1e3, 3),
            "time_tf_ms": round(time_tf * 1e3, 4),
            "time_conv_ms": round(time_conv * 1e3, 4),
            "speedup_tf_vs_conv": round(time_conv / (time_tf + 1e-12), 2),
            "intensity_correlation": round(corr, 4),
            "mse": round(mse, 6),
        })

    results["complexity_benchmark"] = runtime_table

    # -------------------------------------------------------------------------
    # 2. Critical Distance Sampling Transition
    # -------------------------------------------------------------------------
    sampling_table = []
    n = 64
    dx = 10e-6
    grid = GridSpec2D(nx=n, ny=n, dx=dx, dy=dx)
    z_crit = (n * (dx ** 2)) / wavelength  # ~12.03 mm

    for ratio in [0.25, 0.5, 1.0, 2.0, 4.0]:
        z_test = z_crit * ratio
        cert = SamplingCertificate.inspect(grid, wavelength, z_test)
        sampling_table.append({
            "z_over_z_crit": ratio,
            "z_mm": round(z_test * 1e3, 2),
            "admitted_tf": cert.admitted_tf,
            "admitted_conv": cert.admitted_conv,
            "fresnel_number": round(cert.fresnel_number, 2),
            "selected_rep": "FOURIER_TRANSFER_FUNCTION" if cert.admitted_tf else "CONVOLUTION_KERNEL",
        })

    results["sampling_transition"] = sampling_table

    # -------------------------------------------------------------------------
    # 3. Round-Trip Inverse Design (Target -> SLM -> Wave -> Sensor)
    # -------------------------------------------------------------------------
    nx, ny = 64, 64
    dx = 10e-6
    grid = GridSpec2D(nx=nx, ny=ny, dx=dx, dy=dx)
    z = 0.01  # 10 mm (within z_crit = 12.03 mm)

    # Target: geometric letters / pattern
    xx, yy = grid.spatial_coords()
    target = np.zeros((ny, nx), dtype=np.float64)
    # Box + central square target
    target[16:48, 16:48] = 0.3
    target[24:40, 24:40] = 1.0

    input_amp = np.ones((ny, nx), dtype=np.float64)
    train = OpticalTrain().add(FresnelPropagation(distance=z, wavelength=wavelength))

    phase_slm, errors = phase_retrieval_gerchberg_saxton(
        target_intensity=target,
        optical_train=train,
        input_amplitude=input_amp,
        grid=grid,
        wavelength=wavelength,
        iterations=30,
    )

    f_in = WaveField2D(u=input_amp * np.exp(1j * phase_slm), grid=grid, wavelength=wavelength, z=0.0)
    f_sensor = train.apply(f_in)
    i_sensor = f_sensor.intensity()

    # PSNR calculation
    max_val = np.max(target)
    final_mse = float(np.mean((i_sensor - target) ** 2))
    psnr = float(10.0 * np.log10((max_val ** 2) / (final_mse + 1e-12)))

    norm_target = target - np.mean(target)
    norm_sensor = i_sensor - np.mean(i_sensor)
    corr = float(np.sum(norm_target * norm_sensor) / (np.linalg.norm(norm_target) * np.linalg.norm(norm_sensor) + 1e-12))

    results["inverse_design"] = {
        "iterations": 30,
        "initial_mse": round(errors[0], 6),
        "final_mse": round(errors[-1], 6),
        "psnr_db": round(psnr, 2),
        "reconstruction_correlation": round(corr, 4),
    }

    # -------------------------------------------------------------------------
    # 4. Camera-in-the-Loop (CITL) System Identification
    # -------------------------------------------------------------------------
    nominal_train = OpticalTrain().add(FresnelPropagation(distance=0.02, wavelength=wavelength))
    twin = CalibrationDigitalTwin(
        nominal_train=nominal_train,
        grid=GridSpec2D(nx=32, ny=32, dx=10e-6, dy=10e-6),
        wavelength=wavelength,
    )
    true_params = {"lut_scale": 0.85, "defocus_dz": 0.001, "zero_order": 0.05}
    sensor = IntensitySensor(noise_std=1e-4, zero_order_leakage=true_params["zero_order"])
    calibrator = CameraInTheLoopCalibrator(digital_twin=twin, sensor=sensor)

    probes = calibrator.generate_probe_patterns()
    observed = [calibrator.simulate_with_params(p, **true_params) for p in probes]
    identified = calibrator.identify_parameters(observed, probes)

    results["citl_identification"] = {
        "ground_truth": true_params,
        "identified": identified,
        "parameter_recovery_error": {
            "lut_scale_error": round(abs(true_params["lut_scale"] - identified["lut_scale"]), 4),
            "defocus_error_mm": round(abs(true_params["defocus_dz"] - identified["defocus_dz"]) * 1e3, 4),
        }
    }

    # -------------------------------------------------------------------------
    # 5. Metasurface 2D/3D Display Metrics (R81, R82, R83)
    # -------------------------------------------------------------------------
    display = MetasurfaceLenticularDisplay(
        pitch_lenslet=0.8e-3,
        focal_length=2.5e-3,
        pixel_pitch=40e-6,
        num_views=12,
        is_3d_mode=True,
    )
    results["metasurface_display"] = {
        "viewing_angle_deg": round(math.degrees(display.viewing_angle()), 2),
        "angular_resolution_deg": round(math.degrees(display.angular_resolution()), 3),
        "space_bandwidth_product_150mm": display.space_bandwidth_product(0.15),
        "crosstalk_adjacent_view": round(display.crosstalk(0, 1), 4),
        "crosstalk_second_view": round(display.crosstalk(0, 2), 4),
        "2d_mode_viewing_angle_deg": round(math.degrees(math.pi), 1),
    }

    return results


if __name__ == "__main__":
    res = run_benchmark()
    print(json.dumps(res, indent=2))
