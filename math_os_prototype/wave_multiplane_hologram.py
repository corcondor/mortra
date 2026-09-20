"""Multi-Plane Phase Hologram Module (Task W3).

Computes a single phase-only hologram that reconstructs sharp target images at two different depths:
- Depth z1 = 8 mm: Annular ring (outer radius 0.30 mm, inner radius 0.20 mm).
- Depth z2 = 12 mm: Solid triangle (-0.3, -0.25), (0.3, -0.25), (0, 0.3) mm.
- Wavelength lambda = 532 nm, 256x256 grid, pixel pitch 8 um.
- Implements Angular Spectrum Method (ASM) propagation and Multi-plane Gerchberg-Saxton (WGS).
"""
from __future__ import annotations

from typing import Any
import numpy as np


def asm_propagate(u_in: np.ndarray, z: float, wavelength: float, pitch: float) -> np.ndarray:
    """Propagate complex optical field by distance z using Angular Spectrum Method (ASM)."""
    N, M = u_in.shape
    df = 1.0 / (N * pitch)
    fx = (np.arange(N) - N // 2) * df
    fy = (np.arange(N) - N // 2) * df
    FX, FY = np.meshgrid(fx, fy)
    
    # Evanescent cutoff: 1 - (lambda*fx)^2 - (lambda*fy)^2 >= 0
    radicand = 1.0 - (wavelength * FX)**2 - (wavelength * FY)**2
    mask = radicand >= 0
    
    kz = np.zeros_like(radicand)
    kz[mask] = (2.0 * np.pi / wavelength) * np.sqrt(radicand[mask])
    
    # Kernel H = exp(i * kz * z)
    H = np.fft.ifftshift(np.exp(1j * kz * z) * mask)
    
    # FFT -> Multiply by H -> IFFT
    U_fft = np.fft.fft2(u_in)
    u_out = np.fft.ifft2(U_fft * H)
    return u_out


def generate_targets(N: int = 256, pitch: float = 8e-6) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Generate target intensity distributions for z1 = 8 mm (ring) and z2 = 12 mm (triangle)."""
    # Coordinates in meters
    x = (np.arange(N) - N // 2) * pitch
    y = (np.arange(N) - N // 2) * pitch
    X, Y = np.meshgrid(x, y)
    R = np.sqrt(X**2 + Y**2)
    
    # Target 1: Annular ring at z1 = 8 mm (outer r = 0.30 mm, inner r = 0.20 mm)
    r_outer = 0.30e-3
    r_inner = 0.20e-3
    target1 = ((R >= r_inner) & (R <= r_outer)).astype(np.float64)
    
    # Target 2: Solid triangle at z2 = 12 mm with vertices:
    # V1 = (-0.3, -0.25) mm, V2 = (0.3, -0.25) mm, V3 = (0.0, 0.30) mm
    v1 = np.array([-0.3e-3, -0.25e-3])
    v2 = np.array([0.3e-3, -0.25e-3])
    v3 = np.array([0.0e-3, 0.30e-3])
    
    # Point-in-triangle test using barycentric coordinates
    p = np.stack([X, Y], axis=-1)  # (N, N, 2)
    denom = (v2[1] - v3[1]) * (v1[0] - v3[0]) + (v3[0] - v2[0]) * (v1[1] - v3[1])
    w1 = ((v2[1] - v3[1]) * (p[..., 0] - v3[0]) + (v3[0] - v2[0]) * (p[..., 1] - v3[1])) / denom
    w2 = ((v3[1] - v1[1]) * (p[..., 0] - v3[0]) + (v1[0] - v3[0]) * (p[..., 1] - v3[1])) / denom
    w3 = 1.0 - w1 - w2
    target2 = ((w1 >= 0) & (w2 >= 0) & (w3 >= 0)).astype(np.float64)
    
    # Normalize targets
    if np.sum(target1) > 0:
        target1 /= np.sqrt(np.sum(target1**2))
    if np.sum(target2) > 0:
        target2 /= np.sqrt(np.sum(target2**2))
        
    meta = {
        "ring_inner_radius_mm": r_inner * 1e3,
        "ring_outer_radius_mm": r_outer * 1e3,
        "triangle_vertices_mm": [v1.tolist(), v2.tolist(), v3.tolist()],
    }
    return target1, target2, meta


def compute_multiplane_phase_hologram(
    target1: np.ndarray,
    target2: np.ndarray,
    z1: float = 0.008,  # 8 mm
    z2: float = 0.012,  # 12 mm
    wavelength: float = 532e-9,
    pitch: float = 8e-6,
    num_iterations: int = 30,
) -> dict[str, Any]:
    """Compute single phase-only hologram via Multi-Plane Gerchberg-Saxton."""
    N, M = target1.shape
    
    # Initial random phase at hologram plane
    np.random.seed(42)
    phase_holo = np.random.uniform(-np.pi, np.pi, (N, N))
    u_holo = np.exp(1j * phase_holo)
    
    w1 = 1.0
    w2 = 1.0
    
    for it in range(num_iterations):
        # 1. Forward propagate to z1 and z2
        u_z1 = asm_propagate(u_holo, z1, wavelength, pitch)
        u_z2 = asm_propagate(u_holo, z2, wavelength, pitch)
        
        # 2. Impose target amplitudes with current phase
        u_z1_mod = w1 * target1 * np.exp(1j * np.angle(u_z1))
        u_z2_mod = w2 * target2 * np.exp(1j * np.angle(u_z2))
        
        # 3. Back-propagate to hologram plane
        b_z1 = asm_propagate(u_z1_mod, -z1, wavelength, pitch)
        b_z2 = asm_propagate(u_z2_mod, -z2, wavelength, pitch)
        
        # 4. Superposition and phase extraction
        u_total = b_z1 + b_z2
        phase_holo = np.angle(u_total)
        u_holo = np.exp(1j * phase_holo)
        
        # Weight adjustment for uniformity
        e1 = np.sum(np.abs(u_z1)**2 * (target1 > 0))
        e2 = np.sum(np.abs(u_z2)**2 * (target2 > 0))
        if e1 > 0 and e2 > 0:
            avg_e = 0.5 * (e1 + e2)
            w1 *= (avg_e / max(e1, 1e-12))**0.3
            w2 *= (avg_e / max(e2, 1e-12))**0.3
            
    # Final reconstructions
    recon_z1 = asm_propagate(u_holo, z1, wavelength, pitch)
    recon_z2 = asm_propagate(u_holo, z2, wavelength, pitch)
    
    I_z1 = np.abs(recon_z1)**2
    I_z2 = np.abs(recon_z2)**2
    
    # Efficiency & Contrast metrics
    # Ring contrast at z1 vs z2
    ring_signal_at_z1 = float(np.mean(I_z1[target1 > 0])) if np.any(target1 > 0) else 0.0
    ring_signal_at_z2 = float(np.mean(I_z2[target1 > 0])) if np.any(target1 > 0) else 0.0
    
    # Triangle contrast at z2 vs z1
    tri_signal_at_z2 = float(np.mean(I_z2[target2 > 0])) if np.any(target2 > 0) else 0.0
    tri_signal_at_z1 = float(np.mean(I_z1[target2 > 0])) if np.any(target2 > 0) else 0.0
    
    return {
        "wavelength_nm": wavelength * 1e9,
        "pixel_pitch_um": pitch * 1e6,
        "z1_mm": z1 * 1e3,
        "z2_mm": z2 * 1e3,
        "iterations": num_iterations,
        "hologram_phase": phase_holo,
        "recon_intensity_z1": I_z1,
        "recon_intensity_z2": I_z2,
        "ring_signal_z1": ring_signal_at_z1,
        "ring_signal_z2": ring_signal_at_z2,
        "tri_signal_z2": tri_signal_at_z2,
        "tri_signal_z1": tri_signal_at_z1,
        "defocus_separation_pass": bool(ring_signal_at_z1 > ring_signal_at_z2 and tri_signal_at_z2 > tri_signal_at_z1),
    }
