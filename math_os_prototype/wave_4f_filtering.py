"""4f Optical Spatial Filtering System Module (Task W2).

Connects MORTRA geometric letter construction and rasterization to a canonical 4f coherent optical processor:
- Input field: MORTRA geometric letter ('M') rasterized via geometry_raster, combined with spatial grating.
- Lens 1 (focal length f): Optical Fourier transform from input u_in(x, y) to spectrum U_f(x_f, y_f).
- Fourier plane coordinates: x_f = lambda * f * nu_x, cutoff radius r_c = lambda * f * nu_c.
- Optical filter masks: All-pass (H = 1), Low-pass (r <= r_c), High-pass (r > r_c).
- Lens 2 (focal length f): Optical Fourier transform to output plane u_out(x, y).
- Physical consistency:
  - All-pass output satisfies exact spatial inversion: u_out(x, y) = -u_in(-x, -y).
  - Total optical power is conserved: ∫|u_out|^2 dS = ∫|u_in|^2 dS.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any
import numpy as np

from math_os_prototype import geometry_alphabet as alpha
from math_os_prototype import geometry_raster as raster


def create_mortra_letter_field(
    character: str = "M",
    N: int = 256,
    pixel_pitch: float = 10e-6,  # 10 um pitch -> 2.56 mm FOV
    grating_period: float = 40e-6,  # 40 um period -> nu = 25 mm^-1
    stroke_radius: float = 1.5,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Generate input optical field from MORTRA geometric letter rasterization and periodic grating."""
    strokes = alpha.ROMAN.get(character, alpha.ROMAN["M"])
    segments = raster.polyline_segments(strokes)
    
    # In geometry_alphabet, letters are defined in a bounding box (e.g. 0..4 or 0..6)
    # Find bounding box of letter
    all_pts = [pt for seg in segments for pt in seg]
    min_x = min(p[0] for p in all_pts)
    max_x = max(p[0] for p in all_pts)
    min_y = min(p[1] for p in all_pts)
    max_y = max(p[1] for p in all_pts)
    
    letter_w = float(max_x - min_x)
    letter_h = float(max_y - min_y)
    
    # Scale letter to occupy ~60% of the N x N grid
    target_size = 0.60 * N
    scale = target_size / max(letter_w, letter_h, 1.0)
    
    offset_x = (N - letter_w * scale) / 2.0 - min_x * scale
    offset_y = (N - letter_h * scale) / 2.0 - min_y * scale
    
    scaled_segments = [
        (
            (Fraction(str(round(a[0] * scale + offset_x, 4))), Fraction(str(round(a[1] * scale + offset_y, 4)))),
            (Fraction(str(round(b[0] * scale + offset_x, 4))), Fraction(str(round(b[1] * scale + offset_y, 4)))),
        )
        for a, b in segments
    ]
    
    # Rasterize using MORTRA's exact integer morphology and rational distance testing
    bitmap = raster.render(scaled_segments, radius=Fraction(str(stroke_radius)), width=N, height=N)
    
    # Convert bitmap to 2D float array
    char_mask = np.zeros((N, N), dtype=np.float64)
    for (i, j) in bitmap.black:
        if 0 <= i < N and 0 <= j < N:
            char_mask[j, i] = 1.0  # j is row (y), i is col (x)
            
    # Add high-frequency spatial grating: period = 40 um (nu = 25 mm^-1)
    x = (np.arange(N) - N // 2) * pixel_pitch
    X, Y = np.meshgrid(x, x)
    grating = 0.4 * (1.0 + np.sin(2.0 * np.pi * X / grating_period))
    
    input_field = np.clip(char_mask + grating, 0.0, 1.0)
    
    meta = {
        "character": character,
        "grid_size": N,
        "pixel_pitch_um": pixel_pitch * 1e6,
        "grating_period_um": grating_period * 1e6,
        "grating_spatial_freq_mm_inv": 1.0 / (grating_period * 1e3),
        "black_pixels_count": bitmap.count(),
        "total_input_power": float(np.sum(input_field**2) * pixel_pitch**2),
    }
    return input_field, meta


def simulate_4f_system(
    input_field: np.ndarray,
    pixel_pitch: float,  # [m]
    wavelength: float = 532e-9,  # 532 nm [m]
    focal_length: float = 0.1,  # 100 mm [m]
    cutoff_spatial_freq: float = 8000.0,  # 8 mm^-1 [m^-1]
) -> dict[str, Any]:
    """Simulate the 4f spatial filtering with exact physical normalization and power conservation."""
    N, M = input_field.shape
    assert N == M, "Input field should be square"
    
    # 1. Spatial and Fourier plane coordinates
    dx = pixel_pitch
    df = 1.0 / (N * dx)
    nu_x = (np.arange(N) - N // 2) * df
    nu_y = (np.arange(N) - N // 2) * df
    NU_X, NU_Y = np.meshgrid(nu_x, nu_y)
    NU_R = np.sqrt(NU_X**2 + NU_Y**2)
    
    # Physical Fourier plane radius: r = lambda * f * nu
    r_c = wavelength * focal_length * cutoff_spatial_freq
    R_f = wavelength * focal_length * NU_R
    r_c_pixels = r_c / (wavelength * focal_length * df)
    
    # 2. Optical Fourier Transform by Lens 1
    # Physical factor: 1 / (i * lambda * f) * dx^2
    # In discrete numpy: F_discrete = fftshift(fft2(ifftshift(input_field)))
    F_in = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(input_field)))
    
    # 3. Filter Masks
    mask_all = np.ones((N, N), dtype=np.float64)
    mask_low = (R_f <= r_c).astype(np.float64)
    mask_high = (R_f > r_c).astype(np.float64)
    
    # 4. Lens 2 Propagation (Second Optical Fourier Transform)
    # Two successive optical FTs produce an inverted field:
    # u_out = - fftshift(fft2(ifftshift(F_filtered))) / N^2
    def lens2_transform(F_filtered: np.ndarray) -> np.ndarray:
        # Note: double forward 2D FT gives spatial inversion u(-x, -y) with scale factor -1/N^2
        out = - np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(F_filtered))) / (N * N)
        return out

    u_all = lens2_transform(F_in * mask_all)
    u_low = lens2_transform(F_in * mask_low)
    u_high = lens2_transform(F_in * mask_high)
    
    # Intensities
    I_in = np.abs(input_field)**2
    I_all = np.abs(u_all)**2
    I_low = np.abs(u_low)**2
    I_high = np.abs(u_high)**2
    
    # Inverted input intensity for spatial inversion comparison: I_in(-x, -y)
    # Note: for even N centered at N//2, centered coordinate negation maps to roll(flip, 1)
    I_in_inverted = np.roll(np.roll(np.flip(I_in, axis=(0, 1)), 1, axis=0), 1, axis=1)
    
    # Total optical power (energy conservation check)
    P_in = float(np.sum(I_in) * dx * dx)
    P_all = float(np.sum(I_all) * dx * dx)
    P_low = float(np.sum(I_low) * dx * dx)
    P_high = float(np.sum(I_high) * dx * dx)
    
    # All-pass reconstruction error: MSE between I_all(x, y) and I_in(-x, -y)
    all_pass_reconstruction_error = float(np.mean((I_all - I_in_inverted)**2))
    power_ratio = P_all / max(P_in, 1e-15)
    low_pass_power_ratio = P_low / max(P_in, 1e-15)
    high_pass_power_ratio = P_high / max(P_in, 1e-15)
    
    return {
        "wavelength_nm": wavelength * 1e9,
        "focal_length_mm": focal_length * 1e3,
        "cutoff_freq_mm_inv": cutoff_spatial_freq * 1e-3,
        "theoretical_cutoff_radius_mm": r_c * 1e3,
        "cutoff_radius_pixels": float(r_c_pixels),
        "fourier_mask_coordinates": {
            "r_c_mm": r_c * 1e3,
            "r_c_pixels": float(r_c_pixels),
            "df_mm_inv": df * 1e-3,
        },
        "power_in": P_in,
        "power_all_pass": P_all,
        "power_low_pass": P_low,
        "power_high_pass": P_high,
        "power_ratio": power_ratio,
        "low_pass_power_ratio": low_pass_power_ratio,
        "high_pass_power_ratio": high_pass_power_ratio,
        "energy_ratio_low": low_pass_power_ratio,
        "energy_ratio_high": high_pass_power_ratio,
        "all_pass_reconstruction_error": all_pass_reconstruction_error,
        "is_power_conserved": bool(abs(power_ratio - 1.0) < 1e-6),
        "is_inverted_reconstructed": bool(all_pass_reconstruction_error < 1e-6),
        "input_intensity": I_in,
        "input_intensity_inverted": I_in_inverted,
        "spectrum_magnitude": np.abs(F_in),
        "out_all_pass_intensity": I_all,
        "out_low_pass_intensity": I_low,
        "out_high_pass_intensity": I_high,
        "mask_low": mask_low,
        "mask_high": mask_high,
    }
