"""Demonstration of end-to-end geometric construction, sentence rendering,

character recognition, formal task specification, problem solving, representation
training, operation acquisition, and wave-optics round-trip in MORTRA.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from math_os_prototype import geometry_acquired_library as acqlib
from math_os_prototype import geometry_acquisition as acq
from math_os_prototype import geometry_alphabet as alpha
from math_os_prototype import geometry_instruction_parser as parser
from math_os_prototype import geometry_letter_construction as constr
from math_os_prototype import geometry_raster as raster
from math_os_prototype import geometry_reading as reading
from math_os_prototype import geometry_recognition_policy as rec_policy
from math_os_prototype import geometry_relational_search as search
from math_os_prototype import geometry_self_improvement as loop
from math_os_prototype.wave_optics_system import (
    FresnelPropagation,
    GridSpec2D,
    OpticalTrain,
    SamplingCertificate,
    WaveField2D,
    phase_retrieval_gerchberg_saxton,
)


def render_ascii_map(array_2d: np.ndarray, downsample_y: int = 4, downsample_x: int = 2) -> str:
    """Render a 2D numpy array (binary or float) into an ASCII text representation."""
    ny, nx = array_2d.shape
    lines = []
    # Cartesian y (bottom to top)
    for j in range(ny - 1, -1, -downsample_y):
        line = []
        for i in range(0, nx, downsample_x):
            block = array_2d[max(0, j - downsample_y + 1):j + 1, i:min(nx, i + downsample_x)]
            val = np.max(block) if block.size > 0 else 0.0
            if val > 0.5:
                line.append("#")
            elif val > 0.15:
                line.append("+")
            elif val > 0.05:
                line.append(".")
            else:
                line.append(" ")
        lines.append("".join(line))
    return "\n".join(lines)


def save_png_recovered_strokes(
    recovered_strokes: list[dict[str, Any]],
    total_width: int,
    total_height: int,
    output_path: Path,
) -> None:
    """Render recovered vector strokes and vertices to a PNG image."""
    fig, ax = plt.subplots(figsize=(max(6, total_width / 18.0), max(3, total_height / 18.0)), dpi=100)
    ax.set_facecolor("#16161e")
    fig.patch.set_facecolor("#0f0f14")
    ax.set_xlim(-4, total_width + 4)
    ax.set_ylim(-4, total_height + 4)
    ax.set_aspect("equal")
    ax.grid(True, linestyle=":", alpha=0.25, color="#555577")

    colors = ["#4fc3f7", "#ffb74d", "#81c784", "#ba68c8", "#4db6ac", "#e57373"]

    for idx, seg in enumerate(recovered_strokes):
        color = colors[idx % len(colors)]
        offset = seg.get("offset", [seg["x_range"][0], 0])
        ox, oy = offset[0], offset[1]

        # Draw edges
        for edge in seg.get("strokes", []):
            p1_idx, p2_idx = edge[0], edge[1]
            if p1_idx < len(seg["vertices"]) and p2_idx < len(seg["vertices"]):
                v1 = [float(seg["vertices"][p1_idx][0]) + ox, float(seg["vertices"][p1_idx][1]) + oy]
                v2 = [float(seg["vertices"][p2_idx][0]) + ox, float(seg["vertices"][p2_idx][1]) + oy]
                ax.plot([v1[0], v2[0]], [v1[1], v2[1]], "-", color=color, linewidth=2.5, alpha=0.9)

        # Draw vertices
        for v in seg.get("vertices", []):
            vx, vy = float(v[0]) + ox, float(v[1]) + oy
            ax.plot(vx, vy, "o", color="#ffffff", markersize=4, alpha=0.8)

        # Label bounding segment
        ax.axvline(seg["x_range"][0], color="#444466", linestyle="--", alpha=0.5)
        ax.axvline(seg["x_range"][1], color="#444466", linestyle="--", alpha=0.5)

    ax.set_title("Recovered Geometric Strokes & Vertices", color="#e0e0e0", fontsize=10, pad=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=100)
    plt.close(fig)


def evaluate_term(term: Any, points: Mapping[str, Any]) -> list[float] | None:
    """Evaluate numerical coordinates of a construction term given input points."""
    if not isinstance(term, dict):
        return None
    op = term.get("op")
    if op == "var":
        name = term.get("name")
        if name in points:
            return [float(c) for c in points[name]]
        return None
    args = [evaluate_term(a, points) for a in term.get("args", [])]
    if any(a is None for a in args):
        return None
    if op == "midpoint" and len(args) == 2:
        return [(args[0][0] + args[1][0]) / 2.0, (args[0][1] + args[1][1]) / 2.0]
    elif op == "foot" and len(args) == 3:
        c, a, b = args[0], args[1], args[2]
        ab_x = b[0] - a[0]
        ab_y = b[1] - a[1]
        denom = ab_x**2 + ab_y**2
        if abs(denom) < 1e-12:
            return a
        t = ((c[0] - a[0]) * ab_x + (c[1] - a[1]) * ab_y) / denom
        return [a[0] + t * ab_x, a[1] + t * ab_y]
    elif op == "mirror" and len(args) == 2:
        p, center = args[0], args[1]
        return [2.0 * center[0] - p[0], 2.0 * center[1] - p[1]]
    return None


def save_png_construction_result(
    task_spec: dict[str, Any],
    solution: dict[str, Any],
    output_path: Path,
) -> None:
    """Render the geometric construction DAG result to a PNG image."""
    fig, ax = plt.subplots(figsize=(6, 6), dpi=120)
    ax.set_facecolor("#16161e")
    fig.patch.set_facecolor("#0f0f14")
    ax.grid(True, linestyle="--", alpha=0.3, color="#555577")

    cmd = task_spec.get("command", "GEOMETRY")
    points = task_spec.get("external_inputs", {})
    sol = solution.get("solution") or {}
    term = sol.get("term")
    u_pt = evaluate_term(term, points) if term else None

    xs, ys = [], []
    for name, pt in points.items():
        x, y = float(pt[0]), float(pt[1])
        xs.append(x)
        ys.append(y)
        ax.plot(x, y, "o", color="#4fc3f7", markersize=8)
        ax.annotate(
            f"{name}({x:g},{y:g})",
            (x, y),
            textcoords="offset points",
            xytext=(8, 8),
            color="#e0e0e0",
            fontsize=10,
            fontweight="bold",
        )

    if "a" in points and "b" in points:
        ax.plot(
            [points["a"][0], points["b"][0]],
            [points["a"][1], points["b"][1]],
            "-",
            color="#81c784",
            linewidth=2,
            label="Base line ab",
        )

    if u_pt is not None:
        ux, uy = float(u_pt[0]), float(u_pt[1])
        xs.append(ux)
        ys.append(uy)
        ax.plot(ux, uy, "*", color="#ff5252", markersize=14, label=f"Constructed u({ux:g},{uy:g})")
        ax.annotate(
            f"u({ux:g},{uy:g})",
            (ux, uy),
            textcoords="offset points",
            xytext=(10, -12),
            color="#ff8a80",
            fontsize=11,
            fontweight="bold",
        )

        if cmd == "PERP" and "c" in points:
            ax.plot(
                [points["c"][0], ux],
                [points["c"][1], uy],
                "--",
                color="#ffab40",
                linewidth=1.5,
                label="Perpendicular foot",
            )
        elif cmd == "MIDP" and "a" in points and "b" in points:
            ax.plot([points["a"][0], ux], [points["a"][1], uy], ":", color="#ffab40", linewidth=1.5)
        elif cmd == "COLL" and "a" in points and "b" in points:
            ax.plot([points["a"][0], ux], [points["a"][1], uy], "-.", color="#ffab40", linewidth=1.5)
    else:
        status_note = solution.get("reason", "Solver not invoked")
        ax.text(
            0.5,
            0.5,
            f"Command Rejected:\n{status_note}",
            horizontalalignment="center",
            verticalalignment="center",
            transform=ax.transAxes,
            color="#ffa726",
            fontsize=10,
            bbox=dict(boxstyle="round", facecolor="#2c1a1a", edgecolor="#ffa726", alpha=0.8),
        )

    margin = 1.5
    if xs and ys:
        ax.set_xlim(min(xs) - margin, max(xs) + margin)
        ax.set_ylim(min(ys) - margin, max(ys) + margin)
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(loc="upper right", facecolor="#262638", edgecolor="#444466", labelcolor="#e0e0e0", fontsize=9)

    term_str = str(sol.get("term", "N/A"))
    if len(term_str) > 45:
        term_str = term_str[:42] + "..."
    ax.set_title(f"Task: {cmd} | Term: {term_str}", color="#ffffff", fontsize=11, pad=10)
    plt.tight_layout()
    plt.savefig(output_path, dpi=120)
    plt.close(fig)


def execute_task_through_wave_optics(
    task_config: dict[str, Any],
    built_alphabets: dict[str, dict[str, Any]],
    loaded_policy: rec_policy.RecognitionPolicy,
    rec_libs: dict[str, Any],
    library: acqlib.AcquiredLibrary,
    output_base_dir: Path,
) -> dict[str, Any]:
    """Execute wave optics round-trip, geometric reading, relational solving, and operation acquisition."""
    task_id = task_config["task_id"]
    word = task_config["word"]
    font_name = task_config.get("font", "ROMAN")
    scale = task_config.get("scale", 8)
    rf = task_config.get("radius_fraction", [3, 8])
    radius = Fraction(rf[0], rf[1]) * scale
    external_points = task_config.get("external_points", {})
    optical_cfg = task_config.get("optical", {})
    is_negative_control = bool(task_config.get("is_negative_control", False))

    print(f"\n" + "-" * 75)
    print(f"TASK: '{task_id}' | Word: '{word}' | Font: {font_name} | Scale: {scale} | Negative Control: {is_negative_control}")
    print("-" * 75)

    task_dir = output_base_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    built_letters = built_alphabets[font_name]
    rec_lib = rec_libs[font_name]

    letter_height = 6
    letter_spacing = 6

    # Step 1: Geometric scene composition
    composed_segments = []
    for idx, char in enumerate(word):
        strokes = built_letters[char]
        offset_x = idx * letter_spacing
        for chain in strokes:
            for k in range(len(chain) - 1):
                p1 = (Fraction(chain[k][0] + offset_x) * scale, Fraction(chain[k][1]) * scale)
                p2 = (Fraction(chain[k+1][0] + offset_x) * scale, Fraction(chain[k+1][1]) * scale)
                composed_segments.append((p1, p2))

    total_width = (len(word) * letter_spacing + 2) * scale
    total_height = (letter_height + 4) * scale

    t0 = time.perf_counter()
    scene_bitmap = raster.render(composed_segments, radius, total_width, total_height)
    render_time = time.perf_counter() - t0
    print(f"  [1] Rendered scene bitmap: {total_width}x{total_height} px, {scene_bitmap.count()} inked cells in {render_time:.3f}s.")

    # Target intensity array directly from scene_bitmap
    target_intensity = np.zeros((total_height, total_width), dtype=np.float64)
    for x, y in scene_bitmap.black:
        target_intensity[y, x] = 1.0

    # Step 2: Numerical wave optics simulation
    wavelength = optical_cfg.get("wavelength_m", 532e-9)
    dx = optical_cfg.get("dx_m", 10e-6)
    dy = optical_cfg.get("dy_m", 10e-6)
    z_factor = optical_cfg.get("z_factor", 0.5)
    gs_iterations = optical_cfg.get("iterations", 20)

    grid = GridSpec2D(nx=total_width, ny=total_height, dx=dx, dy=dy)
    z_cert = SamplingCertificate.inspect(grid, wavelength, z=0.005)
    z_crit = z_cert.z_crit
    z_prop = z_factor * z_crit

    cert = SamplingCertificate.inspect(grid, wavelength, z_prop)
    prop = FresnelPropagation(distance=z_prop, wavelength=wavelength)
    model_name = prop.select_representation(grid).name

    print(f"  [2] Numerical Wave Optics Simulation:")
    print(f"      Model: {model_name} (Scalar diffraction / angular spectrum)")
    print(f"      Grid: {grid.nx}x{grid.ny} px, Pitch: ({dx*1e6:.1f}um, {dy*1e6:.1f}um)")
    print(f"      Wavelength: {wavelength*1e9:.1f} nm, Critical Distance z_crit: {z_crit*1e3:.2f} mm")
    print(f"      Propagation Distance z:   {z_prop*1e3:.2f} mm (z <= z_crit: {cert.admitted_tf})")

    optical_train = OpticalTrain()
    optical_train.add(prop)
    input_amplitude = np.ones((total_height, total_width), dtype=np.float64)

    t0 = time.perf_counter()
    phase_slm, gs_errors = phase_retrieval_gerchberg_saxton(
        target_intensity=target_intensity,
        optical_train=optical_train,
        input_amplitude=input_amplitude,
        grid=grid,
        wavelength=wavelength,
        iterations=gs_iterations,
    )
    gs_time = time.perf_counter() - t0
    print(f"      Phase retrieval ({gs_iterations} iters) in {gs_time:.3f}s: error {gs_errors[0]:.4f} -> {gs_errors[-1]:.4f}")

    field_in = WaveField2D(
        u=input_amplitude * np.exp(1j * phase_slm),
        grid=grid,
        wavelength=wavelength,
        z=0.0,
    )
    field_sensor = optical_train.apply(field_in)
    i_sensor = field_sensor.intensity()

    # Step 3: Objective binarization condition (Otsu thresholding)
    norm_i = (i_sensor - np.min(i_sensor)) / (np.max(i_sensor) - np.min(i_sensor) + 1e-12)
    hist, bin_edges = np.histogram(norm_i, bins=64, range=(0.0, 1.0))
    prob = hist / float(np.sum(hist))
    omega = np.cumsum(prob)
    mu = np.cumsum(prob * np.arange(len(prob)))
    mu_t = mu[-1]

    sigma_b_squared = np.zeros(len(prob))
    for t in range(len(prob)):
        if 0 < omega[t] < 1.0:
            sigma_b_squared[t] = ((mu_t * omega[t] - mu[t]) ** 2) / (omega[t] * (1.0 - omega[t]))
    best_bin = np.argmax(sigma_b_squared)
    threshold_val = float(bin_edges[best_bin])

    binarization_condition = {
        "method": "otsu_between_class_variance",
        "bins": 64,
        "threshold_normalized": threshold_val,
        "rule": "norm_intensity >= threshold_normalized",
    }
    reconstructed_black = {
        (x, y)
        for y in range(total_height)
        for x in range(total_width)
        if norm_i[y, x] >= threshold_val
    }
    reconstructed_bitmap = raster.Bitmap(total_width, total_height, reconstructed_black)
    reconstructed_array = np.zeros((total_height, total_width), dtype=np.uint8)
    for x, y in reconstructed_black:
        reconstructed_array[y, x] = 1

    print(f"  [3] Objective Binarization: threshold={threshold_val:.5f}, reconstructed cells={reconstructed_bitmap.count()} (original: {scene_bitmap.count()})")

    # Step 4: Geometric reading and stroke recovery from wave-reconstructed bitmap
    reconstructed_comps = raster.components(reconstructed_bitmap)
    rec_letter_comps = []
    for comp in reconstructed_comps:
        if len(comp) > 20:
            xs = [i for i, j in comp]
            rec_letter_comps.append((min(xs), comp))
    rec_letter_comps.sort(key=lambda x: x[0])

    rec_chars = []
    recognition_details = []
    all_recovered_strokes = []

    for idx, (min_x, comp) in enumerate(rec_letter_comps):
        xs = [i for i, j in comp]
        ys = [j for i, j in comp]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        sub_black = {(i - min(xs), j - min(ys)) for i, j in comp}
        sub_bm = raster.Bitmap(w, h, sub_black)

        glyph = reading.recover(sub_bm, grid=loaded_policy.grid)
        all_recovered_strokes.append({
            "segment_index": idx,
            "x_range": [min(xs), max(xs)],
            "offset": [min(xs), min(ys)],
            "vertices": [[str(x), str(y)] for x, y in glyph.vertices],
            "strokes": [list(e) for e in glyph.edges],
            "holes": glyph.holes,
            "degrees": glyph.degrees(),
        })

        res = reading.read(
            sub_bm,
            rec_lib,
            grid=loaded_policy.grid,
            use_relations=loaded_policy.use_relations,
            use_structure=loaded_policy.use_structure,
            frame=loaded_policy.frame,
        )
        rec_chars.append(res["letter"])
        recognition_details.append({
            "segment_index": idx,
            "x_range": [min(xs), max(xs)],
            "recognized": res["letter"],
            "score": float(res["score"]),
            "margin": float(res["margin"]),
        })

    wave_word = "".join(rec_chars)
    print(f"  [4] Word recognized from wave optical reconstruction: '{wave_word}'")
    recognition_passed = (wave_word == word)

    # Step 5: Generating formal specification from wave_word
    print(f"  [5] Generating formal specification from wave-recognized word '{wave_word}'...")
    parsed_spec = parser.parse_geometric_instruction(wave_word, external_points)
    spec_valid = bool(parsed_spec.get("valid", False))
    print(f"      Parser output: valid={spec_valid}")
    if not spec_valid:
        print(f"      Rejection reason: {parsed_spec.get('reason')}")

    # Step 6: Task solving with relational synthesizer and operation acquisition
    solve_passed = False
    replay_passed = False
    solver_solution = None
    used_acquired_ops = []
    acquisition_report = {"acquired": False, "reason": "solver not invoked"}
    registration_report = {"registered": False}
    meas = {}

    library_state_before = library.state()

    if spec_valid:
        print(f"  [6] Solving task with loop.solve and AcquiredLibrary (programs: {len(library.programs)})...")
        task = parsed_spec["task"]
        t0 = time.perf_counter()
        res_solve = loop.solve(task, library=library, applications=20)
        meas = loop.measurements(res_solve)
        solve_passed = bool(meas.get("solved", False))
        sol = res_solve.get("solution") or {}
        replay_passed = bool(sol.get("replay", {}).get("passed", False))
        solver_solution = res_solve

        # Check whether any acquired operation was actually reused
        used_acquired_ops = acq.used_acquired_operation(sol, library)
        print(f"      Solved: {solve_passed}, Applications: {meas.get('primitive_applications')}, Replay passed: {replay_passed}")
        print(f"      Reused acquired operations: {len(used_acquired_ops)}")
        if used_acquired_ops:
            for uop in used_acquired_ops:
                print(f"        -> Reused op #{uop['index']}: families={uop['families']}, source={uop['source']}")

        # Acquire and register new operation into library
        if solve_passed and replay_passed:
            acq_result = acq.acquire(sol, task, definitions=getattr(library, "definitions", None))
            acquisition_report = acq_result
            if acq_result.get("acquired"):
                reg_result = acq.register(
                    library,
                    acq_result,
                    source={"task": task_id, "word": wave_word, "font": font_name},
                )
                registration_report = reg_result
                print(f"      Acquisition result: ACQUIRED. Registration: {reg_result}")
            else:
                print(f"      Acquisition result: NOT ACQUIRED ({acq_result.get('reason')})")
    else:
        print(f"  [6] Command is invalid/rejected. loop.solve is NOT invoked.")
        solver_solution = {
            "status": "rejected_command_solver_not_invoked",
            "reason": parsed_spec.get("reason"),
            "solver_invoked": False,
        }

    library_state_after = library.state()

    # Step 7: Verification booleans and status
    if is_negative_control:
        overall_passed = (not spec_valid) and (not solver_solution.get("solver_invoked", True))
    else:
        overall_passed = recognition_passed and spec_valid and solve_passed and replay_passed

    print(f"  [7] Step Verification:")
    print(f"      Recognition Passed: {recognition_passed}")
    print(f"      Specification Valid: {spec_valid}")
    print(f"      Solve Passed:        {solve_passed}")
    print(f"      Replay Passed:       {replay_passed}")
    print(f"      -> Overall Status:   {'PASSED' if overall_passed else 'FAILED'}")

    # Step 8: Save all numeric arrays, PNG images, and artifacts
    np.save(task_dir / "original_scene.npy", target_intensity)
    plt.imsave(task_dir / "original_scene.png", target_intensity, cmap="gray_r")
    with (task_dir / "original_scene.txt").open("w", encoding="utf-8") as f:
        f.write(render_ascii_map(target_intensity))

    np.save(task_dir / "phase_slm.npy", phase_slm)
    plt.imsave(task_dir / "phase_slm.png", phase_slm, cmap="twilight", vmin=-np.pi, vmax=np.pi)

    np.save(task_dir / "sensor_intensity.npy", i_sensor)
    plt.imsave(task_dir / "sensor_intensity.png", norm_i, cmap="inferno")
    with (task_dir / "sensor_intensity.txt").open("w", encoding="utf-8") as f:
        f.write(render_ascii_map(norm_i))

    np.save(task_dir / "reconstructed_bitmap.npy", reconstructed_array)
    plt.imsave(task_dir / "reconstructed_bitmap.png", reconstructed_array, cmap="gray_r")
    with (task_dir / "reconstructed_bitmap.txt").open("w", encoding="utf-8") as f:
        f.write(render_ascii_map(reconstructed_array))

    save_png_recovered_strokes(all_recovered_strokes, total_width, total_height, task_dir / "recovered_strokes.png")
    save_png_construction_result(parsed_spec, solver_solution, task_dir / "construction_result.png")

    with (task_dir / "recovered_strokes.json").open("w", encoding="utf-8") as f:
        json.dump(all_recovered_strokes, f, indent=2)

    with (task_dir / "wave_recognized_word.json").open("w", encoding="utf-8") as f:
        json.dump({
            "composed_word": word,
            "wave_recognized_word": wave_word,
            "recognition_passed": recognition_passed,
            "details": recognition_details,
        }, f, indent=2)

    with (task_dir / "formal_specification.json").open("w", encoding="utf-8") as f:
        json.dump(parsed_spec, f, indent=2)

    with (task_dir / "solver_solution.json").open("w", encoding="utf-8") as f:
        json.dump(solver_solution, f, indent=2)

    task_summary = {
        "task_id": task_id,
        "word": word,
        "font": font_name,
        "scale": scale,
        "is_negative_control": is_negative_control,
        "simulation_parameters": {
            "model_name": model_name,
            "wavelength_m": wavelength,
            "dx_m": dx,
            "dy_m": dy,
            "grid_nx": grid.nx,
            "grid_ny": grid.ny,
            "z_crit_m": z_crit,
            "z_prop_m": z_prop,
            "admitted_tf": cert.admitted_tf,
        },
        "phase_retrieval": {
            "iterations": len(gs_errors),
            "initial_error": float(gs_errors[0]),
            "final_error": float(gs_errors[-1]),
            "seconds": gs_time,
        },
        "binarization_condition": binarization_condition,
        "step_verifications": {
            "recognition_passed": recognition_passed,
            "spec_valid": spec_valid,
            "solve_passed": solve_passed,
            "replay_passed": replay_passed,
            "overall_passed": overall_passed,
        },
        "wave_recognized_word": wave_word,
        "solver_costs": meas,
        "structural_reuse": {
            "used_acquired_operations": used_acquired_ops,
            "acquisition": {
                "acquired": bool(acquisition_report.get("acquired", False)),
                "reason": acquisition_report.get("reason"),
            },
            "registration": registration_report,
            "library_state_before": library_state_before,
            "library_state_after": library_state_after,
        },
    }

    with (task_dir / "task_summary.json").open("w", encoding="utf-8") as f:
        json.dump(task_summary, f, indent=2)

    return task_summary


def run_pipeline(tasks_config_path: Path, execution_mode: str = "initial", checkpoint_path: str = ""):
    print("=" * 75)
    print("MORTRA CONFIG-DRIVEN GEOMETRIC TEXT GENERATION, READING, AND SOLVING")
    print(f"Mode: {execution_mode} | Tasks Config: {tasks_config_path}")
    print("=" * 75)

    # -------------------------------------------------------------------------
    # 1. Geometric Construction of Alphabets from 3 Seeds (o, ex, ey)
    # -------------------------------------------------------------------------
    print("\n[1] Constructing lattice and alphabets from 3 seeds (o, ex, ey)...")
    names, program, coords = constr.build_lattice(6, 6)
    replayed_coords = constr.replay(program)

    built_roman = constr.as_coordinates(constr.as_names(alpha.ROMAN, names), replayed_coords)
    built_narrow = constr.as_coordinates(constr.as_names(alpha.NARROW, names), replayed_coords)
    built_alphabets = {
        "ROMAN": built_roman,
        "NARROW": built_narrow,
    }
    print(f"  Constructed lattice points: {len(coords)} via {len(program)} steps.")
    print(f"  ROMAN (26 glyphs) and NARROW (26 glyphs) constructed as replayable DAGs.")

    # -------------------------------------------------------------------------
    # 2. Recognition Policy Selection & Persistence
    # -------------------------------------------------------------------------
    print("\n[2] Recognition Policy Selection and State Persistence...")
    policy_dir = repo_root / "reports" / "recognition-policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    policy_path = policy_dir / "recognition_policy.json"

    initial_policy = rec_policy.load_recognition_policy(policy_path)
    print(f"  Initial policy from disk: {initial_policy.policy_id}")

    best_policy, train_report = rec_policy.train_recognition_policy(
        reference_alphabet=built_roman,
        validation_letters=built_narrow,
        current_policy=initial_policy,
    )
    rec_policy.save_recognition_policy(best_policy, policy_path)
    loaded_policy = rec_policy.load_recognition_policy(policy_path)

    print(f"  Selected recognition model: {loaded_policy.policy_id} ({loaded_policy.description})")
    print(f"  Policy updated from previous state: {train_report['policy_updated']}")
    print(f"  [Note] Recognition policy selection is a lexicographical/Pareto choice among 4 candidate models.")
    print(f"         It is not acquisition of a novel predicate ontology or a proof of minimal sufficiency.")

    with (policy_dir / "training_report.json").open("w", encoding="utf-8") as f:
        json.dump(train_report, f, indent=2)

    rec_libs = {
        "ROMAN": reading.library_from(
            built_roman,
            grid=loaded_policy.grid,
            use_relations=loaded_policy.use_relations,
            use_structure=loaded_policy.use_structure,
            frame=loaded_policy.frame,
        ),
        "NARROW": reading.library_from(
            built_narrow,
            grid=loaded_policy.grid,
            use_relations=loaded_policy.use_relations,
            use_structure=loaded_policy.use_structure,
            frame=loaded_policy.frame,
        ),
    }

    # -------------------------------------------------------------------------
    # 3. Acquired Library Initialization / Restoration
    # -------------------------------------------------------------------------
    print("\n[3] Acquired Library State Setup...")
    library_dir = repo_root / "reports" / "acquired-library"
    library_dir.mkdir(parents=True, exist_ok=True)
    library_path = library_dir / "library_state.json"

    if library_path.exists():
        try:
            with library_path.open("r", encoding="utf-8") as f:
                lib_data = json.load(f)
            library = acqlib.AcquiredLibrary.from_dict(lib_data)
            print(f"  Restored AcquiredLibrary from disk: {len(library.programs)} programs, {len(library.acquired)} acquired.")
        except Exception as e:
            print(f"  Warning: Could not parse {library_path} ({e}), initializing clean AcquiredLibrary.")
            library = acqlib.AcquiredLibrary()
    else:
        library = acqlib.AcquiredLibrary()
        print("  Initialized clean AcquiredLibrary (0 acquired programs).")

    # -------------------------------------------------------------------------
    # 4. Multi-Task Execution from Configuration
    # -------------------------------------------------------------------------
    print(f"\n[4] Loading tasks configuration from: {tasks_config_path}...")
    with tasks_config_path.open("r", encoding="utf-8") as f:
        config_data = json.load(f)

    tasks = config_data.get("tasks", [])
    print(f"  Found {len(tasks)} tasks to execute.")

    demo_dir = repo_root / "reports" / "geometric-reading-demo"
    demo_dir.mkdir(parents=True, exist_ok=True)

    all_summaries = []
    for task_cfg in tasks:
        task_summary = execute_task_through_wave_optics(
            task_config=task_cfg,
            built_alphabets=built_alphabets,
            loaded_policy=loaded_policy,
            rec_libs=rec_libs,
            library=library,
            output_base_dir=demo_dir,
        )
        all_summaries.append(task_summary)

    # Save updated library state to disk
    with library_path.open("w", encoding="utf-8") as f:
        json.dump(library.to_dict(), f, indent=2)
    print(f"\n  Saved updated AcquiredLibrary state to: {library_path}")

    # -------------------------------------------------------------------------
    # 5. Final Comprehensive Status Report & Matrix
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PIPELINE EXECUTION SUMMARY & VERIFICATION MATRIX")
    print("=" * 80)
    print(f"{'Task ID':<28} | {'Word':<6} | {'Font':<7} | {'Recognized':<10} | {'Valid':<5} | {'Solved':<6} | {'Reused':<6} | {'Result':<6}")
    print("-" * 85)

    all_passed = True
    for s in all_summaries:
        tid = s["task_id"]
        w = s["word"]
        font = s["font"]
        rec = s["wave_recognized_word"]
        v = s["step_verifications"]
        spec_v = str(v["spec_valid"])
        solved_v = str(v["solve_passed"])
        reused_count = len(s["structural_reuse"]["used_acquired_operations"])
        reused_v = str(reused_count)
        res_v = "PASS" if v["overall_passed"] else "FAIL"
        if not v["overall_passed"]:
            all_passed = False
        print(f"{tid:<28} | {w:<6} | {font:<7} | {rec:<10} | {spec_v:<5} | {solved_v:<6} | {reused_v:<6} | {res_v:<6}")

    print("-" * 85)
    print(f"Final Pipeline Verdict: {'ALL STAGES PASSED' if all_passed else 'PIPELINE HAD FAILURES'}")
    print("=" * 80)

    # Save master summary JSON
    with (demo_dir / "master_summary.json").open("w", encoding="utf-8") as f:
        json.dump({
            "all_passed": all_passed,
            "execution_mode": execution_mode,
            "tasks_count": len(tasks),
            "summaries": all_summaries,
            "policy": loaded_policy.to_dict(),
            "library_final_state": library.state(),
        }, f, indent=2)

    if not all_passed:
        sys.exit(1)


def main():
    parser_cli = argparse.ArgumentParser(description="MORTRA Geometric Reading & Multi-Task Solving Pipeline.")
    parser_cli.add_argument(
        "--tasks-config",
        type=str,
        default="configs/geometric_reading_tasks.json",
        help="Path to tasks configuration JSON file.",
    )
    parser_cli.add_argument(
        "--mode",
        choices=["initial", "continuous"],
        default="initial",
        help="Execution mode.",
    )
    parser_cli.add_argument(
        "--checkpoint",
        type=str,
        default="",
        help="Checkpoint path (used in continuous mode).",
    )

    args = parser_cli.parse_args()
    tasks_path = repo_root / args.tasks_config
    if not tasks_path.exists():
        print(f"[ERROR] Tasks config file not found: {tasks_path}", file=sys.stderr)
        sys.exit(1)

    run_pipeline(
        tasks_config_path=tasks_path,
        execution_mode=args.mode,
        checkpoint_path=args.checkpoint,
    )


if __name__ == "__main__":
    main()
