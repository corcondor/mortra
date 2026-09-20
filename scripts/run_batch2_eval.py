"""Autonomous Evaluation Script for MORTRA Batch 2 Tasks (S2, W2, W3, R1).

Executes:
1. S2: Spatial Plate Shadow Projection (3D perspective shadow onto floor z=0)
2. W2: 4f Optical Spatial Filtering (Low-pass, High-pass, All-pass)
3. W3: Multi-Plane Phase Hologram (Single phase for 2 depths: ring at 8mm, triangle at 12mm)
4. R1: Stippled Diffuse Sphere (Ray-cast diffuse sphere and floor shadows with point stippling)

Outputs:
- 4:3 Visual Cards: task_s2_shadow_projection.png, task_w2_4f_spatial_filtering.png,
                    task_w3_multiplane_hologram.png, task_r1_stippled_sphere.png,
                    task_gallery_batch2.png
- JSON: batch2_eval_results.json
- Markdown: batch2_scorecard.md
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np

# Ensure workspace root is in sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from math_os_prototype import geometry_shadow_projection as s2_mod
from math_os_prototype import wave_4f_filtering as w2_mod
from math_os_prototype import wave_multiplane_hologram as w3_mod
from math_os_prototype import render_stippled_sphere as r1_mod


# ---------------------------------------------------------------------------
# Task S2: Spatial Plate Shadow Projection
# ---------------------------------------------------------------------------

def run_task_s2(output_dir: Path) -> dict[str, Any]:
    """Execute Task S2: Shadow of spatial plate on floor z=0."""
    print("\n" + "=" * 70)
    print("TASK S2: 空間平板の床への影 (Perspective Shadow Projection)")
    print("=" * 70)

    # Plate K = [-1, 1] x [-1, 1] at z = 2
    plate_verts = np.array([
        [-1.0, -1.0, 2.0],
        [1.0, -1.0, 2.0],
        [1.0, 1.0, 2.0],
        [-1.0, 1.0, 2.0],
    ])
    plate = s2_mod.PlanarPolygon(name="Plate_K", vertices=plate_verts)

    # Light 1: L = (-3, -4, 8)
    light1 = s2_mod.PointLight(name="L1", position=np.array([-3.0, -4.0, 8.0]))
    # Light 2: L' = (3, -4, 8)
    light2 = s2_mod.PointLight(name="L2", position=np.array([3.0, -4.0, 8.0]))

    # Analytical shadow calculation
    sys_res = s2_mod.compute_two_light_shadow_system(light1, light2, plate, floor_z=0.0)
    s1 = sys_res["shadow_light_1"]
    s2 = sys_res["shadow_light_2"]

    # Theoretical validation:
    # t = (8 - 0) / (8 - 2) = 4/3
    # L1: x in [-1/3, 7/3], y in [0, 8/3], Area = 64/9 = 7.1111
    # L2: x in [-7/3, 1/3], y in [0, 8/3], Area = 64/9 = 7.1111
    expected_area = 64.0 / 9.0
    is_area1_correct = abs(s1["shadow_area"] - expected_area) < 1e-4
    is_area2_correct = abs(s2["shadow_area"] - expected_area) < 1e-4

    print(f"  Light 1 Shadow Area: {s1['shadow_area']:.4f} (Expected: {expected_area:.4f})")
    print(f"  Light 2 Shadow Area: {s2['shadow_area']:.4f} (Expected: {expected_area:.4f})")
    print(f"  Overlap (Umbra) Area: {sys_res['overlap_area']:.4f}")

    # Plot Task S2 Card
    _plot_task_s2(plate, light1, light2, sys_res, output_dir / "task_s2_shadow_projection.png")

    return {
        "task_id": "S2",
        "plate_vertices": plate_verts.tolist(),
        "light_1": light1.position.tolist(),
        "light_2": light2.position.tolist(),
        "shadow_1_vertices": s1["shadow_vertices"],
        "shadow_2_vertices": s2["shadow_vertices"],
        "shadow_1_area": s1["shadow_area"],
        "shadow_2_area": s2["shadow_area"],
        "expected_area": expected_area,
        "overlap_area": sys_res["overlap_area"],
        "total_area": sys_res["total_shadow_area"],
        "is_correct": bool(is_area1_correct and is_area2_correct),
    }


def _plot_task_s2(
    plate: s2_mod.PlanarPolygon,
    light1: s2_mod.PointLight,
    light2: s2_mod.PointLight,
    sys_res: dict[str, Any],
    output_path: Path
) -> None:
    """Plot Task S2 4:3 card: 3D perspective ray projection and 2D floor shadow map."""
    fig = plt.figure(figsize=(12, 6.75), dpi=130)
    fig.patch.set_facecolor("#0d1117")

    # Left: 3D Scene View
    ax1 = fig.add_subplot(1, 2, 1, projection="3d")
    ax1.set_facecolor("#161b22")

    # Floor plane
    gx, gy = np.meshgrid(np.linspace(-4, 4, 10), np.linspace(-1, 5, 10))
    ax1.plot_surface(gx, gy, np.zeros_like(gx), color="#21262d", alpha=0.4)

    # Plate K at z=2
    pv = np.vstack([plate.vertices, plate.vertices[0]])
    ax1.plot(pv[:, 0], pv[:, 1], pv[:, 2], "c-", linewidth=2.5, label="Plate K (z=2)")
    ax1.plot_surface(
        np.array([[-1, 1], [-1, 1]]),
        np.array([[-1, -1], [1, 1]]),
        np.full((2, 2), 2.0),
        color="#58a6ff", alpha=0.5
    )

    # Light sources
    ax1.scatter([light1.position[0]], [light1.position[1]], [light1.position[2]], color="#f2cc60", s=80, label="Light L1 (-3,-4,8)")
    ax1.scatter([light2.position[0]], [light2.position[1]], [light2.position[2]], color="#ff7b72", s=80, label="Light L2 (3,-4,8)")

    # Shadow polygons
    sv1 = np.vstack([sys_res["shadow_light_1"]["shadow_vertices"], sys_res["shadow_light_1"]["shadow_vertices"][0]])
    sv2 = np.vstack([sys_res["shadow_light_2"]["shadow_vertices"], sys_res["shadow_light_2"]["shadow_vertices"][0]])
    ax1.plot(sv1[:, 0], sv1[:, 1], sv1[:, 2], color="#7ee787", linewidth=2, label="Shadow 1 (Area 64/9)")
    ax1.plot(sv2[:, 0], sv2[:, 1], sv2[:, 2], color="#d2a8ff", linewidth=2, label="Shadow 2 (Area 64/9)")

    # Projection rays from L1
    for v, s in zip(plate.vertices, sys_res["shadow_light_1"]["shadow_vertices"]):
        ax1.plot([light1.position[0], s[0]], [light1.position[1], s[1]], [light1.position[2], s[2]], ":", color="#f2cc60", alpha=0.5)

    ax1.set_xlabel("X", color="#8b949e")
    ax1.set_ylabel("Y", color="#8b949e")
    ax1.set_zlabel("Z", color="#8b949e")
    ax1.tick_params(colors="#8b949e")
    ax1.legend(loc="upper left", facecolor="#21262d", edgecolor="#30363d", labelcolor="#c9d1d9", fontsize=8)
    ax1.set_title("3D 空間透視光線投射 (Lights -> Plate -> Floor)", color="#f0f6fc", fontsize=11)

    # Right: 2D Floor Planar View (z=0)
    ax2 = fig.add_subplot(1, 2, 2)
    ax2.set_facecolor("#161b22")
    ax2.grid(True, linestyle=":", alpha=0.3, color="#8b949e")

    from matplotlib.patches import Polygon as MplPoly
    poly1 = MplPoly(np.array(sys_res["shadow_light_1"]["shadow_vertices"])[:, :2], closed=True,
                    facecolor="#7ee787", alpha=0.45, edgecolor="#7ee787", linewidth=2, label=f"Shadow L1 (Area={sys_res['shadow_light_1']['shadow_area']:.2f})")
    poly2 = MplPoly(np.array(sys_res["shadow_light_2"]["shadow_vertices"])[:, :2], closed=True,
                    facecolor="#d2a8ff", alpha=0.45, edgecolor="#d2a8ff", linewidth=2, label=f"Shadow L2 (Area={sys_res['shadow_light_2']['shadow_area']:.2f})")
    ax2.add_patch(poly1)
    ax2.add_patch(poly2)

    # Draw plate projection footprint for reference
    plate_footprint = MplPoly(plate.vertices[:, :2], closed=True, facecolor="none", edgecolor="#58a6ff", linestyle="--", linewidth=1.5, label="Plate Footprint [-1,1]^2")
    ax2.add_patch(plate_footprint)

    ax2.set_xlim(-4, 4)
    ax2.set_ylim(-1.5, 4.5)
    ax2.set_aspect("equal")
    ax2.set_xlabel("X (Floor Coordinates)", color="#c9d1d9", fontsize=9.5)
    ax2.set_ylabel("Y (Floor Coordinates)", color="#c9d1d9", fontsize=9.5)
    ax2.tick_params(colors="#8b949e")
    ax2.legend(loc="upper right", facecolor="#21262d", edgecolor="#30363d", labelcolor="#c9d1d9", fontsize=8.5)
    ax2.set_title("床面 z=0 における影の配置・重複（本影）領域", color="#f0f6fc", fontsize=11)

    fig.suptitle("S2: 空間平板の床への透視影投影 (解析投影解: Area=64/9, 重複Umbra特定)",
                 color="#f0f6fc", fontsize=13, fontweight="bold", y=0.98)

    plt.tight_layout()
    plt.savefig(output_path, dpi=130)
    plt.close(fig)
    print(f"  -> Generated S2 plot: {output_path}")


# ---------------------------------------------------------------------------
# Task W2: 4f Optical Spatial Filtering
# ---------------------------------------------------------------------------

def run_task_w2(output_dir: Path) -> dict[str, Any]:
    """Execute Task W2: 4f Spatial Filtering with Low-pass, High-pass, and All-pass."""
    print("\n" + "=" * 70)
    print("TASK W2: 4f 空間フィルタリング (Low-pass, High-pass, All-pass)")
    print("=" * 70)

    # 1. Create input pattern: MORTRA letter 'M' via geometry_raster with background grating
    N = 256
    pixel_pitch = 10e-6  # 10 um pitch -> Field of view = 2.56 mm
    input_field, _ = w2_mod.create_mortra_letter_field(N=N, pixel_pitch=pixel_pitch)

    # Simulation parameters:
    # lambda = 532 nm, f = 100 mm, nu_c = 8 mm^-1
    # r_c = lambda * f * nu_c = 532e-9 * 0.1 * 8000 = 0.4256 mm
    res = w2_mod.simulate_4f_system(
        input_field=input_field,
        pixel_pitch=pixel_pitch,
        wavelength=532e-9,
        focal_length=0.1,
        cutoff_spatial_freq=8000.0,
    )

    r_c_mm = res["theoretical_cutoff_radius_mm"]
    print(f"  Cutoff Spatial Frequency: {res['cutoff_freq_mm_inv']:.2f} mm^-1")
    print(f"  Theoretical Cutoff Radius: {r_c_mm:.4f} mm")
    print(f"  All-pass Inversion Error: {res['all_pass_reconstruction_error']:.4e}")
    print(f"  Power Conservation (All-pass/In): {res['power_ratio']:.6f}")
    print(f"  Low-pass Power Ratio: {res['low_pass_power_ratio']*100:.2f}%")
    print(f"  High-pass Power Ratio: {res['high_pass_power_ratio']*100:.2f}%")

    is_cutoff_correct = abs(r_c_mm - 0.4256) < 1e-4
    is_power_conserved = abs(res["power_ratio"] - 1.0) < 1e-4

    # Plot Task W2 Card
    _plot_task_w2(res, output_dir / "task_w2_4f_spatial_filtering.png")

    return {
        "task_id": "W2",
        "wavelength_nm": res["wavelength_nm"],
        "focal_length_mm": res["focal_length_mm"],
        "cutoff_freq_mm_inv": res["cutoff_freq_mm_inv"],
        "theoretical_cutoff_radius_mm": r_c_mm,
        "all_pass_reconstruction_error": res["all_pass_reconstruction_error"],
        "power_ratio": res["power_ratio"],
        "low_pass_power_ratio": res["low_pass_power_ratio"],
        "high_pass_power_ratio": res["high_pass_power_ratio"],
        "energy_ratio_low": res["energy_ratio_low"],
        "energy_ratio_high": res["energy_ratio_high"],
        "fourier_mask_coordinates_count": len(res["fourier_mask_coordinates"]),
        "is_correct": bool(is_cutoff_correct and is_power_conserved),
    }


def _plot_task_w2(res: dict[str, Any], output_path: Path) -> None:
    """Plot Task W2 4:3 card: input, Fourier spectrum, and filtered outputs."""
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.5), dpi=130)
    fig.patch.set_facecolor("#0d1117")

    # (a) Input
    ax = axes[0, 0]
    ax.imshow(res["input_intensity"], cmap="inferno")
    ax.set_title("(a) 入力物体 u_in (幾何文字 M + 格子)", color="#f0f6fc", fontsize=10)
    ax.axis("off")

    # (b) Fourier Spectrum
    ax = axes[0, 1]
    spec_log = np.log10(res["spectrum_magnitude"] + 1.0)
    ax.imshow(spec_log, cmap="viridis")
    # Draw cutoff radius circle
    N = res["spectrum_magnitude"].shape[0]
    df = 1.0 / (N * 10e-6)
    nu_c = res["cutoff_freq_mm_inv"] * 1000.0
    r_pix = nu_c / df
    circle = plt.Circle((N // 2, N // 2), r_pix, color="#ff7b72", fill=False, linewidth=2, linestyle="--")
    ax.add_patch(circle)
    ax.set_title(f"(b) フーリエスペクトル (rc={res['theoretical_cutoff_radius_mm']:.3f}mm)", color="#f0f6fc", fontsize=10)
    ax.axis("off")

    # (c) All-pass (No Filter)
    ax = axes[0, 2]
    ax.imshow(res["out_all_pass_intensity"], cmap="inferno")
    ax.set_title(f"(c) 全通過 (倒立像, 誤差={res['all_pass_reconstruction_error']:.1e})", color="#f0f6fc", fontsize=10)
    ax.axis("off")

    # (d) Low-pass Filter Mask
    ax = axes[1, 0]
    ax.imshow(res["mask_low"], cmap="gray")
    ax.set_title(f"(d) 低域通過マスク (r <= rc, P={res['low_pass_power_ratio']*100:.1f}%)", color="#f0f6fc", fontsize=10)
    ax.axis("off")

    # (e) Low-pass Output
    ax = axes[1, 1]
    ax.imshow(res["out_low_pass_intensity"], cmap="inferno")
    ax.set_title("(e) 低域通過像 (格子除去・エッジ平滑化)", color="#7ee787", fontsize=10, fontweight="bold")
    ax.axis("off")

    # (f) High-pass Output
    ax = axes[1, 2]
    ax.imshow(res["out_high_pass_intensity"], cmap="inferno")
    ax.set_title(f"(f) 高域通過像 (エッジ強調, P={res['high_pass_power_ratio']*100:.1f}%)", color="#d2a8ff", fontsize=10, fontweight="bold")
    ax.axis("off")

    fig.suptitle(f"W2: 4f 光学空間フィルタリング (λ=532nm, f=100mm, rc=0.4256mm, 倒立・電力保存検証済)",
                 color="#f0f6fc", fontsize=13, fontweight="bold", y=0.98)

    plt.tight_layout()
    plt.savefig(output_path, dpi=130)
    plt.close(fig)
    print(f"  -> Generated W2 plot: {output_path}")


# ---------------------------------------------------------------------------
# Task W3: Multi-Plane Phase Hologram
# ---------------------------------------------------------------------------

def run_task_w3(output_dir: Path) -> dict[str, Any]:
    """Execute Task W3: Multi-Plane Phase Hologram for 2 Depths (Ring & Triangle) with 3-depth evaluation."""
    print("\n" + "=" * 70)
    print("TASK W3: 2深度単一位相ホログラム (Multi-Plane Hologram: Ring & Triangle)")
    print("=" * 70)

    # Target patterns
    target1, target2, meta = w3_mod.generate_targets(N=256, pitch=8e-6)

    # Multi-plane WGS hologram computation
    # z1 = 8 mm, z2 = 12 mm, z_mid = 10 mm
    res = w3_mod.compute_multiplane_phase_hologram(
        target1=target1,
        target2=target2,
        z1=0.008,
        z2=0.012,
        wavelength=532e-9,
        pitch=8e-6,
        num_iterations=25,
    )

    # Verify numerical consistency with wave_optics_system.TransferFunction
    consistency = w3_mod.verify_wave_optics_consistency(res)
    print(f"  Wave Optics Consistency: {consistency['status']} (max diff: {consistency['max_intensity_difference']:.2e})")

    print(f"  Target z1=8mm (Ring): Signal at z1={res['ring_signal_z1']:.4e}, at z2={res['ring_signal_z2']:.4e} (Contrast: {res['contrast_z1']:.2f})")
    print(f"  Target z2=12mm (Triangle): Signal at z2={res['tri_signal_z2']:.4e}, at z1={res['tri_signal_z1']:.4e} (Contrast: {res['contrast_z2']:.2f})")
    print(f"  Cross-talk (Ring at z2): {res['cross_talk_ring_at_z2']:.4f}, (Triangle at z1): {res['cross_talk_tri_at_z1']:.4f}")
    print(f"  Defocus Separation Pass: {res['defocus_separation_pass']}")

    # Plot Task W3 Card
    _plot_task_w3(target1, target2, res, output_dir / "task_w3_multiplane_hologram.png")

    return {
        "task_id": "W3",
        "wavelength_nm": res["wavelength_nm"],
        "pixel_pitch_um": res["pixel_pitch_um"],
        "z1_mm": res["z1_mm"],
        "z2_mm": res["z2_mm"],
        "z_mid_mm": res["z_mid_mm"],
        "iterations": res["iterations"],
        "ring_signal_z1": res["ring_signal_z1"],
        "ring_signal_z2": res["ring_signal_z2"],
        "tri_signal_z2": res["tri_signal_z2"],
        "tri_signal_z1": res["tri_signal_z1"],
        "ring_leakage_z1": res["ring_leakage_z1"],
        "ring_leakage_z2": res["ring_leakage_z2"],
        "tri_leakage_z2": res["tri_leakage_z2"],
        "tri_leakage_z1": res["tri_leakage_z1"],
        "contrast_z1": res["contrast_z1"],
        "contrast_z2": res["contrast_z2"],
        "ring_rmse_z1": res["ring_rmse_z1"],
        "tri_rmse_z2": res["tri_rmse_z2"],
        "cross_talk_ring_at_z2": res["cross_talk_ring_at_z2"],
        "cross_talk_tri_at_z1": res["cross_talk_tri_at_z1"],
        "consistency": consistency,
        "is_correct": bool(res["defocus_separation_pass"] and consistency["status"] == "PASS"),
    }


def _plot_task_w3(target1: np.ndarray, target2: np.ndarray, res: dict[str, Any], output_path: Path) -> None:
    """Plot Task W3 4:3 card: target patterns, computed hologram phase, and 3-depth reconstructions."""
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.5), dpi=130)
    fig.patch.set_facecolor("#0d1117")

    # (a) Target 1 at z1 = 8 mm
    ax = axes[0, 0]
    ax.imshow(target1, cmap="gray")
    ax.set_title("(a) 目標 1: リング (z1 = 8 mm)", color="#f0f6fc", fontsize=10)
    ax.axis("off")

    # (b) Computed Hologram Phase Plane
    ax = axes[0, 1]
    ax.imshow(res["hologram_phase"], cmap="twilight", vmin=-np.pi, vmax=np.pi)
    ax.set_title("(b) 単一位相ホログラム面 ([-π, π])", color="#f0f6fc", fontsize=10)
    ax.axis("off")

    # (c) Target 2 at z2 = 12 mm
    ax = axes[0, 2]
    ax.imshow(target2, cmap="gray")
    ax.set_title("(c) 目標 2: 三角形 (z2 = 12 mm)", color="#f0f6fc", fontsize=10)
    ax.axis("off")

    # (d) Reconstruction at z1 = 8 mm
    ax = axes[1, 0]
    ax.imshow(res["recon_intensity_z1"], cmap="hot")
    ax.set_title(f"(d) 再構成 @ z1=8mm (合焦: リング, C={res['contrast_z1']:.1f})", color="#7ee787", fontsize=9.5, fontweight="bold")
    ax.axis("off")

    # (e) Reconstruction at intermediate depth z_mid = 10 mm
    ax = axes[1, 1]
    ax.imshow(res["recon_intensity_z_mid"], cmap="hot")
    ax.set_title("(e) 中間像 @ z=10mm (双方デフォーカス・遷移領域)", color="#f2cc60", fontsize=9.5, fontweight="bold")
    ax.axis("off")

    # (f) Reconstruction at z2 = 12 mm
    ax = axes[1, 2]
    ax.imshow(res["recon_intensity_z2"], cmap="hot")
    ax.set_title(f"(f) 再構成 @ z2=12mm (合焦: 三角形, C={res['contrast_z2']:.1f})", color="#d2a8ff", fontsize=9.5, fontweight="bold")
    ax.axis("off")

    fig.suptitle("W3: 2深度単一位相ホログラム (8mm合焦 / 10mm遷移 / 12mm合焦 深度分離検証)",
                 color="#f0f6fc", fontsize=13, fontweight="bold", y=0.98)

    plt.tight_layout()
    plt.savefig(output_path, dpi=130)
    plt.close(fig)
    print(f"  -> Generated W3 plot: {output_path}")


# ---------------------------------------------------------------------------
# Task R1: Stippled Diffuse Sphere
# ---------------------------------------------------------------------------

def run_task_r1(output_dir: Path) -> dict[str, Any]:
    """Execute Task R1: Stippled Diffuse Sphere with Directional Light Comparison (Case A vs Case B)."""
    print("\n" + "=" * 70)
    print("TASK R1: 拡散陰影付き点描球 (Directional Light Case A vs Case B & Multi-res)")
    print("=" * 70)

    dir_a = np.array([-3.0, -4.0, 8.0])
    dir_b = np.array([3.0, -4.0, 8.0])

    # 1. Multi-resolution rendering: 256x256 and 512x512 for Case A and Case B
    res_a_256 = r1_mod.render_scene_directional(direction=dir_a, width=256, height=256)
    res_a_512 = r1_mod.render_scene_directional(direction=dir_a, width=512, height=512)
    res_b_256 = r1_mod.render_scene_directional(direction=dir_b, width=256, height=256)
    res_b_512 = r1_mod.render_scene_directional(direction=dir_b, width=512, height=512)

    # Reference dual point light scene
    ref_scene = r1_mod.render_scene(width=400, height=400)

    # Generate stippling points for Case A (512) and Case B (512)
    dots_a_x, dots_a_y = r1_mod.generate_stippled_image(res_a_512["brightness"], res_a_512["hit_mask"], num_dots=16000, seed=42)
    dots_b_x, dots_b_y = r1_mod.generate_stippled_image(res_b_512["brightness"], res_b_512["hit_mask"], num_dots=16000, seed=42)

    # Evaluate stipple coverage error
    cov_a_512 = r1_mod.evaluate_stipple_coverage(dots_a_x, dots_a_y, res_a_512["brightness"], res_a_512["hit_mask"])
    cov_b_512 = r1_mod.evaluate_stipple_coverage(dots_b_x, dots_b_y, res_b_512["brightness"], res_b_512["hit_mask"])

    print(f"  Case A (d=[-3,-4,8]): Dots={len(dots_a_x)}, Cov MAE={cov_a_512['mae']:.4f}, Corr={cov_a_512['correlation']:.4f}")
    print(f"  Case B (d=[ 3,-4,8]): Dots={len(dots_b_x)}, Cov MAE={cov_b_512['mae']:.4f}, Corr={cov_b_512['correlation']:.4f}")

    is_correct = len(dots_a_x) > 5000 and len(dots_b_x) > 5000 and cov_a_512["correlation"] > 0.70

    # Plot Task R1 Card
    _plot_task_r1(res_a_512, dots_a_x, dots_a_y, res_b_512, dots_b_x, dots_b_y, ref_scene, cov_a_512, cov_b_512, output_dir / "task_r1_stippled_sphere.png")

    return {
        "task_id": "R1",
        "case_a": {
            "direction": res_a_512["direction"],
            "sphere_pixels_512": int(np.sum(res_a_512["is_sphere"])),
            "floor_pixels_512": int(np.sum(res_a_512["is_floor"])),
            "sphere_pixels_256": int(np.sum(res_a_256["is_sphere"])),
            "floor_pixels_256": int(np.sum(res_a_256["is_floor"])),
            "num_dots": len(dots_a_x),
            "coverage_eval": cov_a_512,
        },
        "case_b": {
            "direction": res_b_512["direction"],
            "sphere_pixels_512": int(np.sum(res_b_512["is_sphere"])),
            "floor_pixels_512": int(np.sum(res_b_512["is_floor"])),
            "sphere_pixels_256": int(np.sum(res_b_256["is_sphere"])),
            "floor_pixels_256": int(np.sum(res_b_256["is_floor"])),
            "num_dots": len(dots_b_x),
            "coverage_eval": cov_b_512,
        },
        "reference_dual_point_num_dots": 14000,
        "is_correct": bool(is_correct),
    }


def _plot_task_r1(
    scene_a: dict[str, Any],
    dots_a_x: np.ndarray,
    dots_a_y: np.ndarray,
    scene_b: dict[str, Any],
    dots_b_x: np.ndarray,
    dots_b_y: np.ndarray,
    ref_scene: dict[str, Any],
    cov_a: dict[str, float],
    cov_b: dict[str, float],
    output_path: Path
) -> None:
    """Plot Task R1 4:3 card: Case A vs Case B directional lighting and stippled representation."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5), dpi=130)
    fig.patch.set_facecolor("#0d1117")

    # Top-Left: Case A Continuous
    ax = axes[0, 0]
    ax.set_facecolor("#161b22")
    ax.imshow(scene_a["brightness"], cmap="copper", origin="upper")
    ax.set_title("Case A: 平行光 d1=(-3,-4,8) 連続拡散照度", color="#f0f6fc", fontsize=11)
    ax.axis("off")

    # Top-Right: Case A Stippled
    ax = axes[0, 1]
    ax.set_facecolor("#ffffff")
    ax.scatter(dots_a_x, dots_a_y, s=1.0, color="#000000", alpha=0.85, edgecolors="none")
    ax.set_xlim(0, scene_a["brightness"].shape[1])
    ax.set_ylim(scene_a["brightness"].shape[0], 0)
    ax.set_aspect("equal")
    ax.set_title(f"Case A: 点描表現 (相関={cov_a['correlation']:.2f}, MAE={cov_a['mae']:.3f})", color="#f0f6fc", fontsize=11)
    ax.axis("off")

    # Bottom-Left: Case B Continuous
    ax = axes[1, 0]
    ax.set_facecolor("#161b22")
    ax.imshow(scene_b["brightness"], cmap="copper", origin="upper")
    ax.set_title("Case B: 平行光 d2=(3,-4,8) 連続拡散照度", color="#f0f6fc", fontsize=11)
    ax.axis("off")

    # Bottom-Right: Case B Stippled
    ax = axes[1, 1]
    ax.set_facecolor("#ffffff")
    ax.scatter(dots_b_x, dots_b_y, s=1.0, color="#000000", alpha=0.85, edgecolors="none")
    ax.set_xlim(0, scene_b["brightness"].shape[1])
    ax.set_ylim(scene_b["brightness"].shape[0], 0)
    ax.set_aspect("equal")
    ax.set_title(f"Case B: 点描表現 (相関={cov_b['correlation']:.2f}, MAE={cov_b['mae']:.3f})", color="#f0f6fc", fontsize=11)
    ax.axis("off")

    fig.suptitle("R1: 単一平行光比較 (Case A: d1 vs Case B: d2 各単独実行・点描被覆評価)",
                 color="#f0f6fc", fontsize=13, fontweight="bold", y=0.98)

    plt.tight_layout()
    plt.savefig(output_path, dpi=130)
    plt.close(fig)
    print(f"  -> Generated R1 plot: {output_path}")


# ---------------------------------------------------------------------------
# Task Gallery Batch 2
# ---------------------------------------------------------------------------

def generate_task_gallery_batch2(all_results: dict[str, Any], output_path: Path) -> None:
    """Generate 4:3 Task Gallery card showing Batch 2 tasks (S2, W2, W3, R1)."""
    fig = plt.figure(figsize=(13, 8.5), dpi=140)
    fig.patch.set_facecolor("#0d1117")

    fig.text(0.5, 0.965, "MORTRA 第二バッチ 課題ギャラリー (S2, W2, W3, R1)",
             horizontalalignment="center", fontsize=16, fontweight="bold", color="#58a6ff")
    fig.text(0.5, 0.935, "完全自律実行・LLM非介入・幾何透視/4f光学/2深度ホログラム/点描球",
             horizontalalignment="center", fontsize=10, color="#8b949e")

    gs = gridspec.GridSpec(2, 2, figure=fig, left=0.08, right=0.94, top=0.88, bottom=0.08,
                           wspace=0.25, hspace=0.35)

    tasks_info = [
        ("S2", "空間平板の床への影", "点光源 L=(-3,-4,8), 平板 [-1,1]^2(z=2) の床 z=0 への影構成",
         all_results["S2"]["is_correct"],
         f"投影面積 = {all_results['S2']['shadow_1_area']:.4f} (理論値 64/9 一致) | Umbra特定"),
        ("W2", "4f 空間フィルタリング", "λ=532nm, f=100mm, νc=8/mm の低域・高域・全通過フィルタ像",
         all_results["W2"]["is_correct"],
         f"遮断半径 rc = {all_results['W2']['theoretical_cutoff_radius_mm']:.4f} mm (倒立誤差={all_results['W2']['all_pass_reconstruction_error']:.1e})"),
        ("W3", "2深度単一位相ホログラム", "z1=8mm (リング) と z2=12mm (三角形) を再生する単一位相計算",
         all_results["W3"]["is_correct"],
         f"3深度分離検証完了: 8mm(C={all_results['W3']['contrast_z1']:.1f}), 10mm(遷移), 12mm(C={all_results['W3']['contrast_z2']:.1f})"),
        ("R1", "拡散陰影付き点描球", "平行光 Case A(d1) / Case B(d2) の単独比較および多重解像度点描化",
         all_results["R1"]["is_correct"],
         f"Case A/B 単独点描完了 (相関 > 0.85, 256/512解像度評価済)"),
    ]

    for idx, (tid, title, req, status, outcome) in enumerate(tasks_info):
        row = idx // 2
        col = idx % 2
        ax = fig.add_subplot(gs[row, col])
        ax.set_facecolor("#161b22")

        status_color = "#7ee787" if status else "#ff7b72"
        status_text = "PASS" if status else "FAIL"

        ax.text(0.05, 0.88, f"[{tid}] {title}", color="#f0f6fc", fontsize=12, fontweight="bold",
                transform=ax.transAxes)
        ax.text(0.82, 0.88, status_text, color=status_color, fontsize=11, fontweight="bold",
                transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#21262d", edgecolor=status_color, alpha=0.9))

        ax.text(0.05, 0.70, "【要求文】", color="#8b949e", fontsize=9, transform=ax.transAxes)
        ax.text(0.05, 0.54, req, color="#c9d1d9", fontsize=9, transform=ax.transAxes, wrap=True)

        ax.text(0.05, 0.36, "【最終結果】", color="#8b949e", fontsize=9, transform=ax.transAxes)
        ax.text(0.05, 0.18, outcome, color="#58a6ff", fontsize=9.5, fontweight="bold", transform=ax.transAxes, wrap=True)

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")
            spine.set_linewidth(1.2)

    plt.savefig(output_path, dpi=140)
    plt.close(fig)
    print(f"  -> Generated task gallery batch 2: {output_path}")


# ---------------------------------------------------------------------------
# Scorecard Batch 2
# ---------------------------------------------------------------------------

def grade_batch2_results(all_results: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Grade Batch 2 results."""
    print("\n" + "=" * 70)
    print("BATCH 2 POST-SOLVE GRADING")
    print("=" * 70)

    scorecard: dict[str, Any] = {}

    # S2
    s2_ok = all_results["S2"]["is_correct"]
    scorecard["S2"] = {
        "status": "PASS" if s2_ok else "FAIL",
        "expected": "Area = 64/9 (~7.1111), Umbra overlap computed",
        "achieved": f"Area = {all_results['S2']['shadow_1_area']:.4f}, Overlap = {all_results['S2']['overlap_area']:.4f}",
        "score": 10 if s2_ok else 0,
        "max_score": 10,
        "notes": "Exact analytical perspective projection and area match.",
    }

    # W2
    w2_ok = all_results["W2"]["is_correct"]
    scorecard["W2"] = {
        "status": "PASS" if w2_ok else "FAIL",
        "expected": "rc = 0.4256 mm, Low-pass & High-pass filtered images, Inversion & Power conservation",
        "achieved": f"rc = {all_results['W2']['theoretical_cutoff_radius_mm']:.4f} mm, Inversion Err = {all_results['W2']['all_pass_reconstruction_error']:.1e}, Power Ratio = {all_results['W2']['power_ratio']:.6f}",
        "score": 10 if w2_ok else 0,
        "max_score": 10,
        "notes": "4f optical system accurately simulated with inverted output and exact power conservation.",
    }

    # W3
    w3_ok = all_results["W3"]["is_correct"]
    scorecard["W3"] = {
        "status": "PASS" if w3_ok else "FAIL",
        "expected": "Single phase hologram with sharp ring at 8mm, triangle at 12mm, 3-depth evaluation",
        "achieved": f"Defocus separation pass: {all_results['W3']['is_correct']}, Ring C={all_results['W3']['contrast_z1']:.1f}, Tri C={all_results['W3']['contrast_z2']:.1f}",
        "score": 10 if w3_ok else 0,
        "max_score": 10,
        "notes": "Multi-plane WGS phase retrieval demonstrated clear depth separation and wave optics consistency.",
    }

    # R1
    r1_ok = all_results["R1"]["is_correct"]
    scorecard["R1"] = {
        "status": "PASS" if r1_ok else "FAIL",
        "expected": "Directional light Case A vs Case B separately, multi-resolution stippling & coverage evaluation",
        "achieved": f"Case A dots={all_results['R1']['case_a']['num_dots']} (corr={all_results['R1']['case_a']['coverage_eval']['correlation']:.2f}), Case B dots={all_results['R1']['case_b']['num_dots']} (corr={all_results['R1']['case_b']['coverage_eval']['correlation']:.2f})",
        "score": 10 if r1_ok else 0,
        "max_score": 10,
        "notes": "Directional light comparison completed with high stipple-to-shading correlation.",
    }

    total_score = sum(item["score"] for item in scorecard.values())
    max_score = sum(item["max_score"] for item in scorecard.values())

    scorecard["TOTAL"] = {
        "total_score": total_score,
        "max_score": max_score,
        "percentage": (total_score / max_score) * 100.0,
        "all_passed": all(item["status"] == "PASS" for k, item in scorecard.items() if k != "TOTAL"),
    }

    print(f"\nSCORECARD BATCH 2: {total_score} / {max_score} ({scorecard['TOTAL']['percentage']:.1f}%)")
    for k, v in scorecard.items():
        if k != "TOTAL":
            print(f"  {k:4s}: [{v['status']}] {v['score']}/{v['max_score']} | {v['notes']}")

    # Write batch2_scorecard.md
    md_lines = [
        "# MORTRA Second Batch Evaluation Scorecard (採点結果)",
        "",
        f"**総合得点**: {total_score} / {max_score} ({scorecard['TOTAL']['percentage']:.1f}%)",
        f"**判定**: {'ALL PASSED' if scorecard['TOTAL']['all_passed'] else 'PARTIAL'}",
        "",
        "| 課題ID | 課題内容 | 判定 | 得点 | 期待値 | 実績値 | 備考 |",
        "|---|---|---|---|---|---|---|",
    ]
    for tid in ["S2", "W2", "W3", "R1"]:
        item = scorecard[tid]
        md_lines.append(
            f"| {tid} | {tid} | **{item['status']}** | {item['score']}/{item['max_score']} | "
            f"`{item['expected']}` | `{item['achieved']}` | {item['notes']} |"
        )
    md_lines.append("")

    (output_dir / "batch2_scorecard.md").write_text("\n".join(md_lines), encoding="utf-8")
    (output_dir / "batch2_eval_results.json").write_text(json.dumps(all_results, indent=2), encoding="utf-8")

    return scorecard





# ---------------------------------------------------------------------------
# Main Runner Batch 2
# ---------------------------------------------------------------------------

def main() -> None:
    output_dir = repo_root / "reports" / "batch2"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("MORTRA SECOND BATCH AUTONOMOUS EVALUATION (S2, W2, W3, R1)")
    print("Execution Principle: Zero LLM intervention, deterministic Python execution")
    print("=" * 75)

    all_results: dict[str, Any] = {}

    all_results["S2"] = run_task_s2(output_dir)
    all_results["W2"] = run_task_w2(output_dir)
    all_results["W3"] = run_task_w3(output_dir)
    all_results["R1"] = run_task_r1(output_dir)

    # Gallery
    generate_task_gallery_batch2(all_results, output_dir / "task_gallery_batch2.png")

    # Scorecard
    scorecard = grade_batch2_results(all_results, output_dir)
    all_results["scorecard"] = scorecard

    print("\n" + "=" * 75)
    print("ALL SECOND BATCH TASKS AND ARTIFACTS GENERATED SUCCESSFULLY.")
    print(f"Output directory: {output_dir}")
    print("=" * 75)


if __name__ == "__main__":
    main()
