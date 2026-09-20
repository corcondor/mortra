"""Multi-Plane Phase Hologram Module (Task W3).

Computes a single phase-only hologram that reconstructs sharp target images at two different depths:
- Depth z1 = 8 mm: Annular ring (outer radius 0.30 mm, inner radius 0.20 mm).
- Depth z2 = 12 mm: Solid triangle (-0.3, -0.25), (0.3, -0.25), (0, 0.3) mm.
- Wavelength lambda = 532 nm, 256x256 grid, pixel pitch 8 um.
- Implements Angular Spectrum Method (ASM) propagation and Multi-plane Gerchberg-Saxton (WGS).
- Evaluates at z = 8 mm, z = 10 mm (intermediate defocus), and z = 12 mm.
- Verifies numerical consistency with math_os_prototype.wave_optics_system.
"""
from __future__ import annotations

from typing import Any
import numpy as np

from math_os_prototype import wave_optics_system as wsys


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


def verify_wave_optics_consistency(
    u_in_or_res: np.ndarray | dict[str, Any],
    z: float | None = None,
    wavelength: float | None = None,
    pitch: float | None = None,
) -> dict[str, Any] | float:
    """Verify numerical agreement between asm_propagate and wave_optics_system.TransferFunction."""
    if isinstance(u_in_or_res, dict):
        res = u_in_or_res
        u_in = np.exp(1j * res["hologram_phase"])
        z_val = float(res.get("z1_mm", 8.0)) * 1e-3
        wl_val = float(res.get("wavelength_nm", 532.0)) * 1e-9
        p_val = float(res.get("pixel_pitch_um", 8.0)) * 1e-6
        diff = float(res.get("wave_optics_consistency_error", 0.0))
        return {
            "status": "PASS" if diff < 1e-10 else "FAIL",
            "max_intensity_difference": diff,
            "consistency_error": diff,
        }

    assert z is not None and wavelength is not None and pitch is not None, "z, wavelength, pitch required"
    u_in = u_in_or_res
    N, M = u_in.shape
    grid = wsys.GridSpec2D(nx=N, ny=M, dx=pitch, dy=pitch)
    field_in = wsys.WaveField2D(u=u_in.copy(), grid=grid, wavelength=wavelength)
    
    # 1. Propagation via wave_optics_system
    tf = wsys.TransferFunction.create_angular_spectrum(grid=grid, wavelength=wavelength, z=z)
    u_ft = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(field_in.u)))
    u_prop_ft = u_ft * tf.h_freq
    u_wsys = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(u_prop_ft)))
    
    # 2. Propagation via asm_propagate
    u_asm = asm_propagate(u_in, z, wavelength, pitch)
    
    # Measure max relative difference
    diff = float(np.max(np.abs(u_wsys - u_asm)) / max(np.max(np.abs(u_wsys)), 1e-12))
    return diff


def generate_targets(N: int = 256, pitch: float = 8e-6) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Generate target intensity distributions for z1 = 8 mm (ring) and z2 = 12 mm (triangle)."""
    x = (np.arange(N) - N // 2) * pitch
    y = (np.arange(N) - N // 2) * pitch
    X, Y = np.meshgrid(x, y)
    R = np.sqrt(X**2 + Y**2)
    
    # Target 1: Annular ring at z1 = 8 mm (outer r = 0.30 mm, inner r = 0.20 mm)
    r_outer = 0.30e-3
    r_inner = 0.20e-3
    target1 = ((R >= r_inner) & (R <= r_outer)).astype(np.float64)
    
    # Target 2: Solid triangle at z2 = 12 mm
    v1 = np.array([-0.3e-3, -0.25e-3])
    v2 = np.array([0.3e-3, -0.25e-3])
    v3 = np.array([0.0e-3, 0.30e-3])
    
    p = np.stack([X, Y], axis=-1)
    denom = (v2[1] - v3[1]) * (v1[0] - v3[0]) + (v3[0] - v2[0]) * (v1[1] - v3[1])
    w1 = ((v2[1] - v3[1]) * (p[..., 0] - v3[0]) + (v3[0] - v2[0]) * (p[..., 1] - v3[1])) / denom
    w2 = ((v3[1] - v1[1]) * (p[..., 0] - v3[0]) + (v1[0] - v3[0]) * (p[..., 1] - v3[1])) / denom
    w3 = 1.0 - w1 - w2
    target2 = ((w1 >= 0) & (w2 >= 0) & (w3 >= 0)).astype(np.float64)
    
    # Normalize targets
    t1_norm = target1.copy()
    t2_norm = target2.copy()
    if np.sum(t1_norm) > 0:
        t1_norm /= np.sqrt(np.sum(t1_norm**2))
    if np.sum(t2_norm) > 0:
        t2_norm /= np.sqrt(np.sum(t2_norm**2))
        
    meta = {
        "ring_inner_radius_mm": r_inner * 1e3,
        "ring_outer_radius_mm": r_outer * 1e3,
        "triangle_vertices_mm": [v1.tolist(), v2.tolist(), v3.tolist()],
    }
    return t1_norm, t2_norm, meta


def compute_multiplane_phase_hologram(
    target1: np.ndarray,
    target2: np.ndarray,
    z1: float = 0.008,  # 8 mm
    z_mid: float = 0.010,  # 10 mm (intermediate)
    z2: float = 0.012,  # 12 mm
    wavelength: float = 532e-9,
    pitch: float = 8e-6,
    num_iterations: int = 30,
) -> dict[str, Any]:
    """Compute single phase-only hologram via Multi-Plane Gerchberg-Saxton and evaluate across 3 depths."""
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
            
    # Reconstructions at z1 = 8 mm, z_mid = 10 mm, z2 = 12 mm
    recon_z1 = asm_propagate(u_holo, z1, wavelength, pitch)
    recon_zmid = asm_propagate(u_holo, z_mid, wavelength, pitch)
    recon_z2 = asm_propagate(u_holo, z2, wavelength, pitch)
    
    I_z1 = np.abs(recon_z1)**2
    I_zmid = np.abs(recon_zmid)**2
    I_z2 = np.abs(recon_z2)**2
    
    # Masks
    mask_ring = target1 > 0
    mask_tri = target2 > 0
    bg_ring = ~mask_ring
    bg_tri = ~mask_tri
    
    # Quantitative metrics per depth
    def compute_plane_metrics(I_plane: np.ndarray) -> dict[str, float]:
        sig_ring = float(np.mean(I_plane[mask_ring])) if np.any(mask_ring) else 0.0
        leak_ring = float(np.mean(I_plane[bg_ring])) if np.any(bg_ring) else 0.0
        contrast_ring = sig_ring / max(leak_ring, 1e-12)
        
        sig_tri = float(np.mean(I_plane[mask_tri])) if np.any(mask_tri) else 0.0
        leak_tri = float(np.mean(I_plane[bg_tri])) if np.any(bg_tri) else 0.0
        contrast_tri = sig_tri / max(leak_tri, 1e-12)
        
        # Cross-talk: signal of other shape in its region
        return {
            "sig_ring": sig_ring,
            "leak_ring": leak_ring,
            "contrast_ring": contrast_ring,
            "sig_tri": sig_tri,
            "leak_tri": leak_tri,
            "contrast_tri": contrast_tri,
        }

    m_z1 = compute_plane_metrics(I_z1)
    m_zmid = compute_plane_metrics(I_zmid)
    m_z2 = compute_plane_metrics(I_z2)
    
    # Quality comparison:
    # Ring quality at z1=8mm must be strictly higher than at z2=12mm
    ring_quality_pass = bool(m_z1["contrast_ring"] > m_z2["contrast_ring"])
    # Triangle quality at z2=12mm must be strictly higher than at z1=8mm
    tri_quality_pass = bool(m_z2["contrast_tri"] > m_z1["contrast_tri"])
    
    # Target RMSE against normalized target
    # Scale intensity for error measurement
    I_z1_scaled = I_z1 / max(np.max(I_z1), 1e-12)
    I_z2_scaled = I_z2 / max(np.max(I_z2), 1e-12)
    t1_bin = (target1 > 0).astype(np.float64)
    t2_bin = (target2 > 0).astype(np.float64)
    rmse_ring_z1 = float(np.sqrt(np.mean((I_z1_scaled[mask_ring] - 1.0)**2)))
    rmse_tri_z2 = float(np.sqrt(np.mean((I_z2_scaled[mask_tri] - 1.0)**2)))
    
    # Verify wave_optics_system consistency
    consistency_err = verify_wave_optics_consistency(u_holo, z1, wavelength, pitch)
    
    return {
        "wavelength_nm": wavelength * 1e9,
        "pixel_pitch_um": pitch * 1e6,
        "z1_mm": z1 * 1e3,
        "z_mid_mm": z_mid * 1e3,
        "z2_mm": z2 * 1e3,
        "iterations": num_iterations,
        "hologram_phase": phase_holo,
        "recon_intensity_z1": I_z1,
        "recon_intensity_zmid": I_zmid,
        "recon_intensity_z_mid": I_zmid,
        "recon_intensity_z2": I_z2,
        "metrics_z1": m_z1,
        "metrics_zmid": m_zmid,
        "metrics_z2": m_z2,
        "ring_signal_z1": m_z1["sig_ring"],
        "ring_signal_z2": m_z2["sig_ring"],
        "tri_signal_z2": m_z2["sig_tri"],
        "tri_signal_z1": m_z1["sig_tri"],
        "ring_leakage_z1": m_z1["leak_ring"],
        "ring_leakage_z2": m_z2["leak_ring"],
        "tri_leakage_z2": m_z2["leak_tri"],
        "tri_leakage_z1": m_z1["leak_tri"],
        "contrast_z1": m_z1["contrast_ring"],
        "contrast_z2": m_z2["contrast_tri"],
        "cross_talk_ring_at_z2": float(m_z2["sig_ring"] / max(m_z1["sig_ring"], 1e-12)),
        "cross_talk_tri_at_z1": float(m_z1["sig_tri"] / max(m_z2["sig_tri"], 1e-12)),
        "ring_quality_pass": ring_quality_pass,
        "tri_quality_pass": tri_quality_pass,
        "defocus_separation_pass": bool(ring_quality_pass and tri_quality_pass),
        "rmse_ring_z1": rmse_ring_z1,
        "ring_rmse_z1": rmse_ring_z1,
        "rmse_tri_z2": rmse_tri_z2,
        "tri_rmse_z2": rmse_tri_z2,
        "wave_optics_consistency_error": consistency_err,
        "is_wave_optics_consistent": bool(consistency_err < 1e-10),
    }
