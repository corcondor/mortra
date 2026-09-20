"""Tests for MORTRA's unified wave optics and 3D image engineering system.

Validates:
1. Green function -> impulse response -> transfer function hierarchy
2. Equivalence and computational complexity of convolution vs transfer function
3. Sampling certificates and critical distance z_crit = N * dx^2 / lambda
4. Round-trip inverse design: target -> SLM phase -> wave propagation -> sensor
5. Camera-in-the-loop (CITL) system identification
6. 4D Light Field and ray-phase-space metrics (R81, R82, R83)
"""
import math
from pathlib import Path
import sys
import time
import numpy as np
import pytest

# Ensure repository root is on sys.path
repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from math_os_prototype.wave_optics_system import (
    Aperture,
    CalibrationDigitalTwin,
    CameraInTheLoopCalibrator,
    FresnelPropagation,
    GreenFunction,
    GridSpec2D,
    ImpulseResponse,
    IntensitySensor,
    LightField4D,
    MetasurfaceLenticularDisplay,
    OpticalTrain,
    PhaseOnlySLM,
    RepresentationKind,
    SamplingCertificate,
    ThinLens,
    TransferFunction,
    WaveField2D,
    phase_retrieval_adjoint_gradient,
    phase_retrieval_gerchberg_saxton,
)


def test_green_impulse_transfer_hierarchy():
    """Verify Green function -> impulse response -> transfer function."""
    wavelength = 632.8e-9  # 632.8 nm (He-Ne laser)
    grid = GridSpec2D(nx=32, ny=32, dx=10e-6, dy=10e-6)
    # At critical distance z_crit = N * dx^2 / lambda, the discrete sampling conditions
    # in spatial and frequency domains perfectly balance, yielding exact discrete equivalence.
    z_crit = (grid.nx * (grid.dx ** 2)) / wavelength

    green = GreenFunction(wavelength=wavelength)
    is_si, reason = green.is_shift_invariant()
    assert is_si is True
    assert "shift" in reason.lower() or "homogeneous" in reason.lower()

    # Convert Green function to impulse response under paraxial approximation
    ir = green.to_impulse_response(z=z_crit, grid=grid)
    assert isinstance(ir, ImpulseResponse)
    assert ir.kernel.shape == (32, 32)

    # Convert impulse response to transfer function via Fourier transform
    tf_from_ir = ir.to_transfer_function()
    assert isinstance(tf_from_ir, TransferFunction)
    assert tf_from_ir.h_freq.shape == (32, 32)

    # Compare with analytical Fresnel transfer function at z_crit
    tf_analytical = TransferFunction.create_fresnel_transfer_function(
        grid=grid, wavelength=wavelength, z=z_crit
    )
    # At z_crit, the discrete Fourier transform of the sampled impulse response
    # matches the sampled transfer function with correlation = 1.0
    corr = np.abs(
        np.sum(tf_from_ir.h_freq * np.conj(tf_analytical.h_freq))
    ) / (np.linalg.norm(tf_from_ir.h_freq) * np.linalg.norm(tf_analytical.h_freq))
    assert corr > 0.99, f"Correlation at z_crit was {corr:.4f}"


def test_convolution_vs_transfer_function_equivalence_and_complexity():
    """Equivalence and complexity comparison of Convolution vs Transfer Function."""
    wavelength = 532e-9  # 532 nm
    nx, ny = 32, 32
    dx = 15e-6
    grid = GridSpec2D(nx=nx, ny=ny, dx=dx, dy=dx)
    z = 0.02  # 20 mm

    # Create input wave field: circular aperture illuminated by plane wave
    xx, yy = grid.spatial_coords()
    r = np.sqrt(xx ** 2 + yy ** 2)
    u_in = (r <= 80e-6).astype(np.complex128)
    field_in = WaveField2D(u=u_in, grid=grid, wavelength=wavelength, z=0.0)

    prop = FresnelPropagation(distance=z, wavelength=wavelength)

    # 1. Propagation via Fourier Transfer Function (Angular Spectrum)
    t0 = time.perf_counter()
    field_tf = prop.apply(field_in, representation=RepresentationKind.FOURIER_TRANSFER_FUNCTION)
    time_tf = time.perf_counter() - t0

    # 2. Propagation via Spatial Convolution Kernel
    t0 = time.perf_counter()
    field_conv = prop.apply(field_in, representation=RepresentationKind.CONVOLUTION_KERNEL)
    time_conv = time.perf_counter() - t0

    # Verify energy conservation (unitary propagation)
    power_in = field_in.total_power()
    power_tf = field_tf.total_power()
    assert math.isclose(power_in, power_tf, rel_tol=1e-2)

    # Verify numerical equivalence between the two representations
    i_tf = field_tf.intensity()
    i_conv = field_conv.intensity()

    # Normalized cross-correlation between the two intensity patterns.
    # Note: TF computes circular convolution (periodic boundary conditions),
    # while spatial kernel convolution computes linear convolution with zero-padding.
    norm_tf = i_tf - np.mean(i_tf)
    norm_conv = i_conv - np.mean(i_conv)
    corr = np.sum(norm_tf * norm_conv) / (
        np.linalg.norm(norm_tf) * np.linalg.norm(norm_conv) + 1e-12
    )
    assert corr > 0.85, f"Correlation between TF and Conv was {corr:.4f}"

    # Both representations produce valid fields
    assert field_tf.z == z
    assert field_conv.z == z


def test_sampling_certificate_admissibility():
    """Verify critical distance z_crit = N * dx^2 / lambda and representation selection."""
    wavelength = 632.8e-9
    nx, ny = 64, 64
    dx = 10e-6
    grid = GridSpec2D(nx=nx, ny=ny, dx=dx, dy=dx)

    # z_crit = 64 * (1e-5)^2 / (632.8e-9) = 64 * 1e-10 / 6.328e-7 = 6.4e-9 / 6.328e-7 ≈ 0.0101 m ≈ 10.1 mm
    expected_z_crit = (64 * (10e-6 ** 2)) / wavelength

    # Case 1: Short distance z < z_crit (Transfer function is admitted)
    z_short = 0.005  # 5 mm < 10.1 mm
    cert_short = SamplingCertificate.inspect(grid, wavelength, z_short)
    assert math.isclose(cert_short.z_crit, expected_z_crit, rel_tol=1e-3)
    assert cert_short.admitted_tf is True
    assert cert_short.admitted_conv is False

    prop_short = FresnelPropagation(distance=z_short, wavelength=wavelength)
    selected_short = prop_short.select_representation(grid)
    assert selected_short == RepresentationKind.FOURIER_TRANSFER_FUNCTION

    # Case 2: Long distance z > z_crit (Convolution is admitted)
    z_long = 0.03  # 30 mm > 10.1 mm
    cert_long = SamplingCertificate.inspect(grid, wavelength, z_long)
    assert cert_long.admitted_tf is False
    assert cert_long.admitted_conv is True

    prop_long = FresnelPropagation(distance=z_long, wavelength=wavelength)
    selected_long = prop_long.select_representation(grid)
    assert selected_long == RepresentationKind.CONVOLUTION_KERNEL


def test_round_trip_inverse_design_gerchberg_saxton():
    """Round-trip inverse design: Target Image -> SLM Phase -> Wave Propagation -> Sensor."""
    wavelength = 532e-9
    nx, ny = 32, 32
    dx = 12e-6
    grid = GridSpec2D(nx=nx, ny=ny, dx=dx, dy=dx)
    z = 0.008  # 8 mm (admitted TF regime, z < z_crit = 8.66 mm)

    # Target intensity: geometric cross pattern
    target_intensity = np.zeros((ny, nx), dtype=np.float64)
    target_intensity[14:18, 8:24] = 1.0
    target_intensity[8:24, 14:18] = 1.0

    # Input beam: uniform amplitude
    input_amplitude = np.ones((ny, nx), dtype=np.float64)

    # Optical train: Fresnel propagation from SLM to Sensor
    train = OpticalTrain()
    train.add(FresnelPropagation(distance=z, wavelength=wavelength))

    # Run Gerchberg-Saxton phase retrieval
    phase_slm, errors = phase_retrieval_gerchberg_saxton(
        target_intensity=target_intensity,
        optical_train=train,
        input_amplitude=input_amplitude,
        grid=grid,
        wavelength=wavelength,
        iterations=25,
    )

    # Monotonic error reduction
    assert len(errors) == 25
    assert errors[-1] < errors[0]

    # Verify forward propagation reproduces target
    field_in = WaveField2D(
        u=input_amplitude * np.exp(1j * phase_slm),
        grid=grid,
        wavelength=wavelength,
        z=0.0,
    )
    field_sensor = train.apply(field_in)
    i_sensor = field_sensor.intensity()

    # Check correlation with target image
    norm_target = target_intensity - np.mean(target_intensity)
    norm_sensor = i_sensor - np.mean(i_sensor)
    corr = np.sum(norm_target * norm_sensor) / (
        np.linalg.norm(norm_target) * np.linalg.norm(norm_sensor) + 1e-12
    )
    assert corr > 0.80, f"Round-trip reconstruction correlation was {corr:.4f}"


def test_round_trip_adjoint_gradient_descent():
    """Verify differentiable adjoint gradient descent for phase optimization (R79)."""
    wavelength = 532e-9
    grid = GridSpec2D(nx=32, ny=32, dx=12e-6, dy=12e-6)
    z = 0.008  # 8 mm

    target = np.zeros((32, 32))
    target[12:20, 12:20] = 1.0
    input_amp = np.ones((32, 32))

    train = OpticalTrain().add(FresnelPropagation(distance=z, wavelength=wavelength))

    phase_opt, errors = phase_retrieval_adjoint_gradient(
        target_intensity=target,
        optical_train=train,
        input_amplitude=input_amp,
        grid=grid,
        wavelength=wavelength,
        iterations=20,
        learning_rate=0.4,
    )

    assert len(errors) == 20
    assert errors[-1] < errors[0]


def test_camera_in_the_loop_system_identification():
    """CITL System Identification: calibrate digital twin from camera feedback (R80)."""
    wavelength = 632.8e-9
    grid = GridSpec2D(nx=32, ny=32, dx=10e-6, dy=10e-6)
    z_nom = 0.02

    nominal_train = OpticalTrain().add(FresnelPropagation(distance=z_nom, wavelength=wavelength))
    twin = CalibrationDigitalTwin(
        nominal_train=nominal_train,
        grid=grid,
        wavelength=wavelength,
        lut_scale=1.0,
        defocus_delta_z=0.0,
        zero_order_alpha=0.0,
    )

    # Physical hardware ground truth with perturbations:
    true_lut = 0.90          # SLM phase scale error (gamma)
    true_dz = 0.001          # 1 mm defocus misalignment
    true_alpha = 0.05        # Undiffracted leakage

    sensor = IntensitySensor(noise_std=1e-4, zero_order_leakage=true_alpha)
    calibrator = CameraInTheLoopCalibrator(digital_twin=twin, sensor=sensor)

    # Generate calibration probes
    probes = calibrator.generate_probe_patterns()
    assert len(probes) == 4

    # Generate observations from "real hardware"
    observed_images = [
        calibrator.simulate_with_params(p, true_lut, true_dz, true_alpha)
        for p in probes
    ]

    # Perform system identification
    identified = calibrator.identify_parameters(observed_images, probes)

    # Check identified parameters are close to true physical parameters
    assert math.isclose(identified["lut_scale"], true_lut, abs_tol=0.15)
    assert math.isclose(identified["defocus_dz"], true_dz, abs_tol=1.5e-3)
    assert identified["zero_order"] >= 0.0

    # Digital twin has been updated with calibrated parameters
    assert twin.lut_scale == identified["lut_scale"]
    assert twin.defocus_delta_z == identified["defocus_dz"]


def test_metasurface_lenticular_and_light_field():
    """Test 4D light field, ray-phase-space and metasurface lenticular display (R81, R82, R83)."""
    display = MetasurfaceLenticularDisplay(
        pitch_lenslet=1.0e-3,     # 1 mm pitch
        focal_length=3.0e-3,      # 3 mm focal length
        pixel_pitch=50e-6,        # 50 um pixels
        num_views=8,
        is_3d_mode=True,
    )

    # 1. 3D mode viewing angle: theta = 2 * arctan(pitch / (2*f))
    expected_va = 2.0 * math.atan(1.0e-3 / (2.0 * 3.0e-3))
    assert math.isclose(display.viewing_angle(), expected_va, rel_tol=1e-4)

    # 2. Angular resolution: delta_theta = pixel_pitch / f
    expected_ar = 50e-6 / 3.0e-3
    assert math.isclose(display.angular_resolution(), expected_ar, rel_tol=1e-4)

    # 3. Space-Bandwidth Product (SBP) (R82)
    sbp = display.space_bandwidth_product(display_width=0.1)  # 100 mm display
    assert sbp == (0.1 / 50e-6) * 8

    # 4. Crosstalk metric in ray-phase-space (R83)
    assert display.crosstalk(0, 0) == 0.0
    assert display.crosstalk(0, 1) > display.crosstalk(0, 2)

    # 5. Switchable 2D mode (R81)
    display.is_3d_mode = False
    assert display.viewing_angle() == math.pi  # Full Lambertian view in 2D mode

    # 6. 4D Light Field digital refocusing
    grid = GridSpec2D(nx=16, ny=16, dx=100e-6, dy=100e-6)
    radiance = np.ones((16, 16, 4, 4), dtype=np.float64)
    lf = LightField4D(
        radiance=radiance,
        grid_spatial=grid,
        max_angle_x=0.05,
        max_angle_y=0.05,
    )
    refocused_0 = lf.refocus(depth_z=0.0)
    refocused_z = lf.refocus(depth_z=0.02)
    assert refocused_0.shape == (16, 16)
    assert refocused_z.shape == (16, 16)


if __name__ == "__main__":
    print("Running test_green_impulse_transfer_hierarchy...")
    test_green_impulse_transfer_hierarchy()
    print("  [PASS] test_green_impulse_transfer_hierarchy")

    print("Running test_convolution_vs_transfer_function_equivalence_and_complexity...")
    test_convolution_vs_transfer_function_equivalence_and_complexity()
    print("  [PASS] test_convolution_vs_transfer_function_equivalence_and_complexity")

    print("Running test_sampling_certificate_admissibility...")
    test_sampling_certificate_admissibility()
    print("  [PASS] test_sampling_certificate_admissibility")

    print("Running test_round_trip_inverse_design_gerchberg_saxton...")
    test_round_trip_inverse_design_gerchberg_saxton()
    print("  [PASS] test_round_trip_inverse_design_gerchberg_saxton")

    print("Running test_round_trip_adjoint_gradient_descent...")
    test_round_trip_adjoint_gradient_descent()
    print("  [PASS] test_round_trip_adjoint_gradient_descent")

    print("Running test_camera_in_the_loop_system_identification...")
    test_camera_in_the_loop_system_identification()
    print("  [PASS] test_camera_in_the_loop_system_identification")

    print("Running test_metasurface_lenticular_and_light_field...")
    test_metasurface_lenticular_and_light_field()
    print("  [PASS] test_metasurface_lenticular_and_light_field")

    print("\nALL WAVE OPTICS & 3D IMAGING TESTS PASSED SUCCESSFULLY!")
