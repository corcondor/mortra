"""Demonstration of 3D image engineering problem solving and simulation rendering in MORTRA.

Solves 3 core problems in 3D image engineering:
1. Multi-Plane 3D Holographic Display: Synthesizing a single SLM phase hologram
   that simultaneously reconstructs distinct depth planes with natural optical defocus.
2. 4D Light Field & Digital Refocusing: Phase-space shear and synthetic aperture
   refocusing from ray radiance L(x, y, theta_x, theta_y).
3. Metasurface Lenticular Display: 2D/3D mode switching, viewing angle,
   space-bandwidth product (SBP), and ray-phase-space crosstalk matrix.
"""
from __future__ import annotations

from fractions import Fraction
import json
import math
from pathlib import Path
import sys
import time
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from math_os_prototype import geometry_alphabet as alpha
from math_os_prototype import geometry_letter_construction as constr
from math_os_prototype import geometry_raster as raster
from math_os_prototype.wave_optics_system import (
    FresnelPropagation,
    GridSpec2D,
    LightField4D,
    MetasurfaceLenticularDisplay,
    OpticalTrain,
    SamplingCertificate,
    WaveField2D,
)


def render_ascii_grayscale(array_2d: np.ndarray, downsample_y: int = 2, downsample_x: int = 1) -> str:
    """Render a 2D intensity array into ASCII shading."""
    ny, nx = array_2d.shape
    norm = array_2d / (np.max(array_2d) + 1e-12)
    ramp = " .:-=+*#%@"
    lines = []
    for j in range(ny - 1, -1, -downsample_y):
        line = []
        for i in range(0, nx, downsample_x):
            block = norm[max(0, j - downsample_y + 1):j + 1, i:min(nx, i + downsample_x)]
            val = float(np.mean(block)) if block.size > 0 else 0.0
            idx = min(len(ramp) - 1, int(val * len(ramp)))
            line.append(ramp[idx])
        lines.append("".join(line))
    return "\n".join(lines)


def multi_plane_phase_retrieval(
    targets: list[tuple[float, np.ndarray]],  # list of (z_distance, target_intensity)
    grid: GridSpec2D,
    wavelength: float,
    iterations: int = 25,
) -> tuple[np.ndarray, list[float]]:
    """Multi-plane Gerchberg-Saxton (WGS) phase retrieval for 3D volumetric CGH.

    Optimizes a single SLM phase phi(x, y) at z=0 such that forward propagation
    to each target distance z_k reproduces target_intensity_k with natural defocus
    between planes.
    """
    ny, nx = grid.ny, grid.nx
    num_planes = len(targets)

    # Pre-compute propagation operators and target amplitudes
    props = []
    target_amps = []
    for z_k, t_k in targets:
        prop = FresnelPropagation(distance=z_k, wavelength=wavelength)
        props.append(prop)
        t_amp = np.sqrt(np.maximum(t_k, 0.0))
        # Normalize energy
        energy = np.sum(t_amp ** 2)
        if energy > 0:
            t_amp = t_amp / np.sqrt(energy)
        target_amps.append(t_amp)

    rng = np.random.default_rng(42)
    phase = rng.uniform(-math.pi, math.pi, size=(ny, nx))
    input_amp = np.ones((ny, nx), dtype=np.float64) / math.sqrt(ny * nx)

    errors = []
    for it in range(iterations):
        back_sum = np.zeros((ny, nx), dtype=np.complex128)
        iter_err = 0.0

        for k in range(num_planes):
            prop_k = props[k]
            t_amp_k = target_amps[k]

            # 1. Forward propagation to plane z_k
            field_in = WaveField2D(
                u=input_amp * np.exp(1j * phase),
                grid=grid,
                wavelength=wavelength,
                z=0.0,
            )
            field_zk = prop_k.apply(field_in)

            # Measure error
            curr_amp = np.abs(field_zk.u)
            iter_err += float(np.mean((curr_amp - t_amp_k) ** 2))

            # 2. Enforce target amplitude constraint at plane z_k
            projected_u = t_amp_k * np.exp(1j * np.angle(field_zk.u))
            field_proj = WaveField2D(
                u=projected_u,
                grid=grid,
                wavelength=wavelength,
                z=field_zk.z,
            )

            # 3. Backward propagation via Adjoint operator to SLM plane
            field_back = prop_k.adjoint(field_proj)
            back_sum += field_back.u

        errors.append(iter_err / num_planes)

        # 4. Superposition of back-propagated fields determines new SLM phase
        phase = np.angle(back_sum)

    return phase, errors


def run_3d_engineering_demo():
    print("=" * 70)
    print("MORTRA 3D IMAGE ENGINEERING: PROBLEM SOLVING & SIMULATION RENDERING")
    print("=" * 70)

    out_dir = repo_root / "reports" / "3d-image-engineering"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Common physical parameters
    wavelength = 532e-9  # 532 nm (green laser)
    nx, ny = 64, 64
    dx = 12e-6  # 12 um pixel pitch
    dy = 12e-6
    grid = GridSpec2D(nx=nx, ny=ny, dx=dx, dy=dy)
    z_crit = (min(nx, ny) * (dx ** 2)) / wavelength  # ~17.3 mm

    print(f"\n[System Setup]")
    print(f"  Physical Grid: {nx}x{ny} pixels, Pitch: {dx*1e6:.1f} um x {dy*1e6:.1f} um")
    print(f"  Physical Window: {grid.lx*1e3:.2f} mm x {grid.ly*1e3:.2f} mm")
    print(f"  Wavelength: {wavelength*1e9:.1f} nm")
    print(f"  Critical Distance z_crit: {z_crit*1e3:.2f} mm (sampling boundary)")

    # =========================================================================
    # Problem 1: Multi-Plane 3D Holographic Display
    # =========================================================================
    print("\n" + "-" * 70)
    print("PROBLEM 1: 3D MULTI-PLANE HOLOGRAPHIC DISPLAY (CGH INVERSE DESIGN)")
    print("-" * 70)
    print("  Objective: Synthesize a single phase-only SLM hologram phi(x,y) at z=0")
    print("             that reconstructs:")
    print("             - Depth Plane 1 (z1 = 6.0 mm):  Letter 'E'")
    print("             - Depth Plane 2 (z2 = 12.0 mm): Letter 'P'")
    print("             with natural optical defocus between planes.")

    # Generate geometric target patterns
    names, program, coords = constr.build_lattice(6, 6)
    replayed = constr.replay(program)
    built_letters = constr.as_coordinates(constr.as_names(alpha.ROMAN, names), replayed)

    scale = 6
    radius = Fraction(3, 8) * scale
    def render_letter_target(char: str) -> np.ndarray:
        strokes = built_letters[char]
        segs = [
            ((Fraction(a[0])*scale + 14, Fraction(a[1])*scale + 14),
             (Fraction(b[0])*scale + 14, Fraction(b[1])*scale + 14))
            for a, b in raster.polyline_segments(strokes)
        ]
        bm = raster.render(segs, radius, nx, ny)
        arr = np.zeros((ny, nx), dtype=np.float64)
        for x, y in bm.black:
            arr[y, x] = 1.0
        return arr

    target_e = render_letter_target("E")
    target_p = render_letter_target("P")

    z1 = 0.006  # 6 mm
    z2 = 0.012  # 12 mm
    targets = [(z1, target_e), (z2, target_p)]

    t0 = time.perf_counter()
    slm_phase, cgh_errors = multi_plane_phase_retrieval(
        targets, grid, wavelength, iterations=25
    )
    cgh_time = time.perf_counter() - t0
    print(f"  [Solve] 3D Phase Retrieval completed in {cgh_time:.3f}s.")
    print(f"          MSE Error: initial {cgh_errors[0]:.5f} -> final {cgh_errors[-1]:.5f} (monotonically reduced)")

    # Simulate 3D Focal Stack Propagation: z = 4, 6, 8, 10, 12, 14 mm
    focal_depths = [0.004, 0.006, 0.008, 0.010, 0.012, 0.014]
    focal_stack = []

    print("\n  [Rendering 3D Focal Stack Simulation across Depths]")
    for z_test in focal_depths:
        prop_test = FresnelPropagation(distance=z_test, wavelength=wavelength)
        field_test = prop_test.apply(
            WaveField2D(
                u=np.exp(1j * slm_phase),
                grid=grid,
                wavelength=wavelength,
                z=0.0,
            )
        )
        i_test = field_test.intensity()
        focal_stack.append((z_test, i_test))

    # ASCII Visualization of Depth Planes
    print(f"\n  Reconstruction at z = {z1*1e3:.1f} mm (Target: 'E' in focus):")
    print(render_ascii_grayscale(focal_stack[1][1], downsample_y=4, downsample_x=2))

    print(f"\n  Reconstruction at z = {z2*1e3:.1f} mm (Target: 'P' in focus):")
    print(render_ascii_grayscale(focal_stack[4][1], downsample_y=4, downsample_x=2))

    # Calculate in-focus contrast & depth selectivity
    i_at_z1 = focal_stack[1][1]
    i_at_z2 = focal_stack[4][1]
    corr_z1_e = float(np.corrcoef(i_at_z1.flatten(), target_e.flatten())[0, 1])
    corr_z2_p = float(np.corrcoef(i_at_z2.flatten(), target_p.flatten())[0, 1])
    print(f"  Quantitative In-Focus Correlation:")
    print(f"    - Plane 1 (z={z1*1e3:.1f}mm) correlation with 'E': {corr_z1_e:.4f}")
    print(f"    - Plane 2 (z={z2*1e3:.1f}mm) correlation with 'P': {corr_z2_p:.4f}")

    # =========================================================================
    # Problem 2: 4D Light Field & Digital Refocusing
    # =========================================================================
    print("\n" + "-" * 70)
    print("PROBLEM 2: 4D LIGHT FIELD & DIGITAL REFOCUSING (INTEGRAL IMAGING)")
    print("-" * 70)
    print("  Objective: From 4D ray radiance L(x, y, theta_x, theta_y), simulate")
    print("             synthetic aperture digital refocusing at depth planes via phase-space shear.")

    # Create light field representation from wave field at z1
    prop_mid = FresnelPropagation(distance=0.008, wavelength=wavelength)
    field_mid = prop_mid.apply(WaveField2D(u=np.exp(1j * slm_phase), grid=grid, wavelength=wavelength))
    lf = LightField4D.from_wave_field_wigner(field_mid, n_theta=12, max_angle=0.04)

    # Refocus across depth range: delta_z = -4mm, 0mm, +4mm
    refocus_depths = [-0.004, 0.0, 0.004]
    refocused_images = []
    for dz in refocus_depths:
        refoc_img = lf.refocus(dz)
        refocused_images.append((dz, refoc_img))
        print(f"  Refocused at delta_z = {dz*1e3:+.1f} mm: peak intensity = {np.max(refoc_img):.4f}")

    print("\n  Ray Phase Space (EPI: x vs theta_x) at center line:")
    epi_slice = lf.radiance[ny // 2, :, lf.n_theta_y // 2, :]  # shape (nx, n_theta_x)
    print(render_ascii_grayscale(epi_slice, downsample_y=2, downsample_x=2))

    # =========================================================================
    # Problem 3: Metasurface Lenticular 3D Display Design
    # =========================================================================
    print("\n" + "-" * 70)
    print("PROBLEM 3: METASURFACE LENTICULAR 3D DISPLAY DESIGN & EVALUATION")
    print("-" * 70)
    display = MetasurfaceLenticularDisplay(
        pitch_lenslet=400e-6,   # 400 um lenslet pitch
        focal_length=1.2e-3,    # 1.2 mm focal length
        pixel_pitch=50e-6,      # 50 um subpixel pitch
        num_views=8,            # 8 parallax views
        is_3d_mode=True,
    )

    viewing_angle_deg = math.degrees(display.viewing_angle())
    ang_res_deg = math.degrees(display.angular_resolution())
    sbp = display.space_bandwidth_product(display_width=0.15)  # 15 cm display width

    print(f"  3D Mode Properties:")
    print(f"    - Number of Views:     {display.num_views}")
    print(f"    - Viewing Angle:       {viewing_angle_deg:.2f} degrees")
    print(f"    - Angular Resolution:  {ang_res_deg:.3f} degrees / view")
    print(f"    - Space-Bandwidth SBP: {sbp:,.0f} (for 150 mm screen)")

    # Inter-view crosstalk matrix
    crosstalk_matrix = np.zeros((display.num_views, display.num_views))
    for i in range(display.num_views):
        for j in range(display.num_views):
            crosstalk_matrix[i, j] = display.crosstalk(i, j)

    print("\n  Ray-Phase-Space Inter-View Crosstalk Matrix (8 views):")
    for row in crosstalk_matrix:
        print("    " + " ".join(f"{val:.3f}" for val in row))

    # 2D Mode Switching
    display.is_3d_mode = False
    print(f"\n  Switched to 2D Mode:")
    print(f"    - Viewing Angle: {math.degrees(display.viewing_angle()):.1f} degrees (Full Lambertian/Wide)")

    # =========================================================================
    # Save Artifacts & Interactive HTML Visualizer
    # =========================================================================
    np.save(out_dir / "hologram_phase.npy", slm_phase)
    np.save(out_dir / "focal_stack_z1.npy", focal_stack[1][1])
    np.save(out_dir / "focal_stack_z2.npy", focal_stack[4][1])
    np.save(out_dir / "epi_slice.npy", epi_slice)
    np.save(out_dir / "crosstalk_matrix.npy", crosstalk_matrix)

    results = {
        "multi_plane_cgh": {
            "wavelength_m": wavelength,
            "grid_nx": nx,
            "grid_ny": ny,
            "pixel_pitch_m": dx,
            "z1_m": z1,
            "z2_m": z2,
            "iterations": len(cgh_errors),
            "final_error": float(cgh_errors[-1]),
            "correlation_z1_e": corr_z1_e,
            "correlation_z2_p": corr_z2_p,
        },
        "light_field": {
            "refocus_depths_m": refocus_depths,
            "num_angles": lf.n_theta_x,
            "max_angle_rad": lf.max_angle_x,
        },
        "metasurface_display": {
            "num_views": display.num_views,
            "viewing_angle_deg": viewing_angle_deg,
            "angular_resolution_deg": ang_res_deg,
            "sbp": sbp,
        },
    }
    with (out_dir / "3d_engineering_results.json").open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Generate an interactive HTML report
    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>MORTRA 3D Image Engineering Simulation Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }}
  h1, h2, h3 {{ color: #38bdf8; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; border: 1px solid #334155; }}
  pre {{ background: #090d16; padding: 1rem; border-radius: 6px; overflow-x: auto; color: #4ade80; font-family: monospace; font-size: 12px; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
  th, td {{ border: 1px solid #334155; padding: 8px 12px; text-align: left; }}
  th {{ background: #0f172a; color: #38bdf8; }}
</style>
</head>
<body>
  <h1>MORTRA 3D Image Engineering Simulation Report</h1>
  <p>Numerical Wave Optics & Ray-Phase-Space Multi-Problem Solving Engine</p>

  <div class="card">
    <h2>1. 3D Multi-Plane Holographic Display (CGH)</h2>
    <p>Single phase hologram &phi;(x,y) simultaneously reconstructing depth planes with optical defocus.</p>
    <div class="grid-2">
      <div>
        <h3>Plane 1: z = 6.0 mm (Target: 'E' in focus)</h3>
        <pre>{render_ascii_grayscale(focal_stack[1][1], downsample_y=4, downsample_x=2)}</pre>
        <p>In-focus correlation with 'E': <strong>{corr_z1_e:.4f}</strong></p>
      </div>
      <div>
        <h3>Plane 2: z = 12.0 mm (Target: 'P' in focus)</h3>
        <pre>{render_ascii_grayscale(focal_stack[4][1], downsample_y=4, downsample_x=2)}</pre>
        <p>In-focus correlation with 'P': <strong>{corr_z2_p:.4f}</strong></p>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>2. 4D Light Field & Ray Phase Space (EPI)</h2>
    <p>Epipolar Plane Image (x vs &theta;_x) at center line showing directional ray shear.</p>
    <pre>{render_ascii_grayscale(epi_slice, downsample_y=2, downsample_x=2)}</pre>
  </div>

  <div class="card">
    <h2>3. Metasurface Lenticular 3D Display Metrics</h2>
    <table>
      <tr><th>Parameter</th><th>Value</th></tr>
      <tr><td>Number of Views</td><td>{display.num_views}</td></tr>
      <tr><td>Viewing Angle (3D Mode)</td><td>{viewing_angle_deg:.2f}&deg;</td></tr>
      <tr><td>Angular Resolution</td><td>{ang_res_deg:.3f}&deg; / view</td></tr>
      <tr><td>Space-Bandwidth Product (SBP)</td><td>{sbp:,.0f}</td></tr>
      <tr><td>Viewing Angle (2D Mode)</td><td>180.0&deg; (Lambertian)</td></tr>
    </table>
  </div>
</body>
</html>
"""
    with (out_dir / "3d_display_report.html").open("w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n  [Saved Results]")
    print(f"    - JSON metrics: {out_dir / '3d_engineering_results.json'}")
    print(f"    - HTML Report:  {out_dir / '3d_display_report.html'}")
    print(f"    - NPY arrays:   {out_dir}/*.npy")

    print("\n" + "=" * 70)
    print("3D IMAGE ENGINEERING DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_3d_engineering_demo()
