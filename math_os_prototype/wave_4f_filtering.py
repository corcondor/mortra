"""4f Optical Spatial Filtering System Module (Task W2).

Simulates a canonical 4f coherent optical processor:
- Lens 1 (focal length f) takes input u_in(x, y) to its Fourier spectrum U_f(x_f, y_f).
- Physical Fourier plane coordinate relation: x_f = lambda * f * nu_x.
- Spatial frequency cutoff nu_c maps to aperture radius r_c = lambda * f * nu_c.
- Optical filter masks: All-pass, Low-pass (r <= r_c), High-pass (r > r_c).
- Lens 2 (focal length f) performs inverse Fourier transform to form the filtered, inverted output image.
"""
from __future__ import annotations

from typing import Any
import numpy as np


def simulate_4f_system(
    input_field: np.ndarray,
    pixel_pitch: float,  # [m]
    wavelength: float = 532e-9,  # 532 nm [m]
    focal_length: float = 0.1,  # 100 mm [m]
    cutoff_spatial_freq: float = 8000.0,  # 8 mm^-1 [m^-1]
) -> dict[str, Any]:
    """Simulate the 4f spatial filtering for (a) All-pass, (b) Low-pass, (c) High-pass.
    
    Parameters:
    -----------
    input_field: 2D complex or float array (N, N)
    pixel_pitch: sampling interval dx, dy in input plane [m]
    wavelength: optical wavelength lambda [m]
    focal_length: lens focal length f [m]
    cutoff_spatial_freq: spatial frequency cutoff nu_c [m^-1]
    """
    N, M = input_field.shape
    assert N == M, "Input field should be square"
    
    # 1. Fourier plane coordinates and spatial frequency grid
    # Frequency coordinates nu_x, nu_y in [-1/(2*dx), 1/(2*dx)]
    df = 1.0 / (N * pixel_pitch)
    nu_x = (np.arange(N) - N // 2) * df
    nu_y = (np.arange(N) - N // 2) * df
    NU_X, NU_Y = np.meshgrid(nu_x, nu_y)
    NU_R = np.sqrt(NU_X**2 + NU_Y**2)
    
    # Physical Fourier plane radius: r = lambda * f * nu
    r_c = wavelength * focal_length * cutoff_spatial_freq
    R_f = wavelength * focal_length * NU_R
    
    # 2. Optical Fourier Transform by Lens 1
    # FFT shifted so DC is at center
    F_in = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(input_field)))
    
    # 3. Filter Masks
    mask_all = np.ones((N, N), dtype=np.float64)
    mask_low = (R_f <= r_c).astype(np.float64)
    mask_high = (R_f > r_c).astype(np.float64)
    
    # 4. Lens 2 Propagation (Second Fourier Transform)
    # Note: A second forward 2D Fourier transform produces an inverted image u(-x, -y)
    def lens2_transform(F_filtered: np.ndarray) -> np.ndarray:
        # In optical 4f, the second lens takes another forward optical FT:
        # u_out(x, y) = FT{ F_filtered(x_f, y_f) } -> inverted image
        out = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(F_filtered))) / N
        return out

    out_all = lens2_transform(F_in * mask_all)
    out_low = lens2_transform(F_in * mask_low)
    out_high = lens2_transform(F_in * mask_high)
    
    # Intensities
    I_in = np.abs(input_field)**2
    I_all = np.abs(out_all)**2
    I_low = np.abs(out_low)**2
    I_high = np.abs(out_high)**2
    
    # Energy metrics
    energy_total = float(np.sum(np.abs(F_in)**2))
    energy_low = float(np.sum(np.abs(F_in * mask_low)**2))
    energy_high = float(np.sum(np.abs(F_in * mask_high)**2))
    
    return {
        "wavelength_nm": wavelength * 1e9,
        "focal_length_mm": focal_length * 1e3,
        "cutoff_freq_mm_inv": cutoff_spatial_freq * 1e-3,
        "theoretical_cutoff_radius_mm": r_c * 1e3,
        "energy_ratio_low": energy_low / max(energy_total, 1e-12),
        "energy_ratio_high": energy_high / max(energy_total, 1e-12),
        "input_intensity": I_in,
        "spectrum_magnitude": np.abs(F_in),
        "out_all_pass_intensity": I_all,
        "out_low_pass_intensity": I_low,
        "out_high_pass_intensity": I_high,
        "mask_low": mask_low,
        "mask_high": mask_high,
    }
