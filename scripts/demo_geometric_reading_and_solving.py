"""Demonstration of end-to-end geometric construction, sentence rendering,

character recognition, formal task specification, problem solving, representation
training, and wave-optics round-trip in MORTRA.
"""
from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import sys
import time
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

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


def process_word_through_wave_optics(
    word: str,
    built_letters: dict[str, Any],
    external_points: dict[str, list[int]],
    loaded_policy: rec_policy.RecognitionPolicy,
    rec_lib: dict[str, Any],
    output_base_dir: Path,
    is_negative_control: bool = False,
) -> dict[str, Any]:
    """Execute the full round-trip for a single word and save all numeric/text artifacts."""
    print(f"\n" + "-" * 70)
    print(f"PROCESSING WORD: '{word}' (Negative Control: {is_negative_control})")
    print("-" * 70)

    word_dir = output_base_dir / word
    word_dir.mkdir(parents=True, exist_ok=True)

    letter_height = 6
    letter_spacing = 6
    scale = 8  # pixels per unit
    radius = Fraction(3, 8) * scale  # stroke width

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

    # Target intensity array directly from scene_bitmap (NO REDRAWING)
    target_intensity = np.zeros((total_height, total_width), dtype=np.float64)
    for x, y in scene_bitmap.black:
        target_intensity[y, x] = 1.0

    # Step 2: Numerical wave optics simulation
    wavelength = 532e-9  # 532 nm (green laser)
    dx = 10e-6  # 10 um pitch
    dy = 10e-6
    grid = GridSpec2D(nx=total_width, ny=total_height, dx=dx, dy=dy)

    # Dynamic inspection of critical distance and representation selection from actual grid and wavelength
    z_cert = SamplingCertificate.inspect(grid, wavelength, z=0.005)
    z_crit = z_cert.z_crit
    z_prop = 0.5 * z_crit  # Strictly within certified TF regime

    cert = SamplingCertificate.inspect(grid, wavelength, z_prop)
    prop = FresnelPropagation(distance=z_prop, wavelength=wavelength)
    model_name = prop.select_representation(grid).name

    print(f"  [2] Numerical Wave Optics Simulation:")
    print(f"      Model: {model_name} (Scalar diffraction / angular spectrum)")
    print(f"      Grid: {grid.nx}x{grid.ny} px, Pitch: ({dx*1e6:.1f}um, {dy*1e6:.1f}um)")
    print(f"      Critical Distance z_crit: {z_crit*1e3:.2f} mm")
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
        iterations=20,
    )
    gs_time = time.perf_counter() - t0
    print(f"      Phase retrieval (20 iters) in {gs_time:.3f}s: error {gs_errors[0]:.4f} -> {gs_errors[-1]:.4f}")

    # Forward propagation to sensor
    field_in = WaveField2D(
        u=input_amplitude * np.exp(1j * phase_slm),
        grid=grid,
        wavelength=wavelength,
        z=0.0,
    )
    field_sensor = optical_train.apply(field_in)
    i_sensor = field_sensor.intensity()

    # Step 3: Objective binarization condition (Otsu thresholding, no arbitrary tuning)
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

        # Recover strokes and corners geometrically
        glyph = reading.recover(sub_bm, grid=loaded_policy.grid)
        all_recovered_strokes.append({
            "segment_index": idx,
            "x_range": [min(xs), max(xs)],
            "vertices": [[str(x), str(y)] for x, y in glyph.vertices],
            "strokes": [list(e) for e in glyph.edges],
            "holes": glyph.holes,
            "degrees": glyph.degrees(),
        })

        # Read character using loaded policy
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
        print(f"      Segment {idx+1} at x=[{min(xs)}, {max(xs)}]: Recognized '{res['letter']}' (score: {float(res['score']):.3f}, margin: {float(res['margin']):.3f})")

    wave_word = "".join(rec_chars)
    print(f"  [4] Word recognized from wave optical reconstruction: '{wave_word}'")
    recognition_passed = (wave_word == word)

    # Step 5: Generating formal specification from wave_word (NOT original word)
    print(f"  [5] Generating formal specification from wave-recognized word '{wave_word}'...")
    parsed_spec = parser.parse_geometric_instruction(wave_word, external_points)
    spec_valid = bool(parsed_spec.get("valid", False))
    print(f"      Parser output: valid={spec_valid}")
    if not spec_valid:
        print(f"      Rejection reason: {parsed_spec.get('reason')}")

    # Step 6: Task solving with MORTRA relational synthesizer
    solve_passed = False
    replay_passed = False
    solver_solution = None
    meas = {}

    if spec_valid:
        print(f"  [6] Solving task with loop.solve (relational synthesis)...")
        task = parsed_spec["task"]
        t0 = time.perf_counter()
        res_solve = loop.solve(task, applications=10)
        meas = loop.measurements(res_solve)
        solve_passed = bool(meas.get("solved", False))
        sol = res_solve.get("solution") or {}
        replay_passed = bool(sol.get("replay", {}).get("passed", False))
        solver_solution = res_solve
        print(f"      Solved: {solve_passed}, Applications: {meas.get('primitive_applications')}, Replay passed: {replay_passed}")
        if solve_passed:
            print(f"      Constructed Point: {sol.get('point')}, Term: {sol.get('term')}")
    else:
        print(f"  [6] Command is invalid/rejected. loop.solve is NOT invoked.")
        solver_solution = {
            "status": "rejected_command_solver_not_invoked",
            "reason": parsed_spec.get("reason"),
            "solver_invoked": False,
        }

    # Step 7: Verification booleans and status
    if is_negative_control:
        # Negative control passes if and only if it is rejected and solver is not invoked
        overall_passed = (not spec_valid) and (not solver_solution.get("solver_invoked", True))
    else:
        overall_passed = recognition_passed and spec_valid and solve_passed and replay_passed

    print(f"  [7] Step Verification:")
    print(f"      Recognition Passed: {recognition_passed}")
    print(f"      Specification Valid: {spec_valid}")
    print(f"      Solve Passed:        {solve_passed}")
    print(f"      Replay Passed:       {replay_passed}")
    print(f"      -> Overall Status:   {'PASSED' if overall_passed else 'FAILED'}")

    # Step 8: Save all numeric arrays and artifacts
    np.save(word_dir / "original_scene.npy", target_intensity)
    with (word_dir / "original_scene.txt").open("w", encoding="utf-8") as f:
        f.write(render_ascii_map(target_intensity))

    np.save(word_dir / "phase_slm.npy", phase_slm)
    np.save(word_dir / "sensor_intensity.npy", i_sensor)
    with (word_dir / "sensor_intensity.txt").open("w", encoding="utf-8") as f:
        f.write(render_ascii_map(norm_i))

    np.save(word_dir / "reconstructed_bitmap.npy", reconstructed_array)
    with (word_dir / "reconstructed_bitmap.txt").open("w", encoding="utf-8") as f:
        f.write(render_ascii_map(reconstructed_array))

    with (word_dir / "recovered_strokes.json").open("w", encoding="utf-8") as f:
        json.dump(all_recovered_strokes, f, indent=2)

    with (word_dir / "wave_recognized_word.json").open("w", encoding="utf-8") as f:
        json.dump({
            "composed_word": word,
            "wave_recognized_word": wave_word,
            "recognition_passed": recognition_passed,
            "details": recognition_details,
        }, f, indent=2)

    with (word_dir / "formal_specification.json").open("w", encoding="utf-8") as f:
        json.dump(parsed_spec, f, indent=2)

    with (word_dir / "solver_solution.json").open("w", encoding="utf-8") as f:
        json.dump(solver_solution, f, indent=2)

    summary = {
        "word": word,
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
        "solver_solution_summary": {
            "solved": solve_passed,
            "term": (sol.get("term") if solve_passed else None),
            "point": (sol.get("point") if solve_passed else None),
        },
    }
    with (word_dir / "pipeline_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def run_pipeline():
    print("=" * 70)
    print("MORTRA GEOMETRIC TEXT GENERATION, READING, AND TASK SOLVING")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # 1. Geometric Construction of Alphabet from 3 Seeds
    # -------------------------------------------------------------------------
    print("\n[1] Constructing lattice and alphabet from 3 seeds (o, ex, ey)...")
    names, program, coords = constr.build_lattice(6, 6)
    named_alphabet = constr.as_names(alpha.ROMAN, names)
    replayed_coords = constr.replay(program)
    built_letters = constr.as_coordinates(named_alphabet, replayed_coords)
    print(f"  Seeds: o=(0,0), ex=(1,0), ey=(0,1)")
    print(f"  Constructed: {len(coords)} lattice points via {len(program)} steps of mirror/midpoint.")
    print(f"  All 26 letters constructed as replayable geometric DAGs.")

    # -------------------------------------------------------------------------
    # 2. Recognition Policy Selection & Persistence
    # -------------------------------------------------------------------------
    print("\n[2] Recognition Policy Selection and State Persistence...")
    policy_dir = repo_root / "reports" / "recognition-policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    policy_path = policy_dir / "recognition_policy.json"

    # Connect to existing persistence: load previous policy if present
    initial_policy = rec_policy.load_recognition_policy(policy_path)
    print(f"  Initial policy from disk: {initial_policy.policy_id}")

    narrow_letters = constr.as_coordinates(constr.as_names(alpha.NARROW, names), replayed_coords)

    # Lexicographical / Pareto selection from four predefined candidate models
    best_policy, train_report = rec_policy.train_recognition_policy(
        reference_alphabet=built_letters,
        validation_letters=narrow_letters,
        current_policy=initial_policy,
    )
    rec_policy.save_recognition_policy(best_policy, policy_path)
    loaded_policy = rec_policy.load_recognition_policy(policy_path)
    assert loaded_policy == best_policy

    print(f"  Selection result: {best_policy.policy_id} ({best_policy.description})")
    print(f"  Policy updated from previous state: {train_report['policy_updated']}")
    print(f"  [Note] Recognition policy selection is a lexicographical/Pareto choice among 4 candidate bundles.")
    print(f"         It is not acquisition of a novel predicate ontology or a proof of minimal sufficiency.")

    with (policy_dir / "training_report.json").open("w", encoding="utf-8") as f:
        json.dump(train_report, f, indent=2)

    # Build reference recognition library using loaded policy
    rec_lib = reading.library_from(
        built_letters,
        grid=loaded_policy.grid,
        use_relations=loaded_policy.use_relations,
        use_structure=loaded_policy.use_structure,
        frame=loaded_policy.frame,
    )

    # -------------------------------------------------------------------------
    # 3. Multi-Command Wave Optics Pipeline Execution
    # -------------------------------------------------------------------------
    # External points: a=(0,0), b=(4,0), c=(1,3)
    external_points = {
        "a": [0, 0],
        "b": [4, 0],
        "c": [1, 3],
    }
    print(f"\n[3] External Point Inputs for Tasks: {external_points}")
    print(f"    - Under 'PERP': foot of c(1,3) on line ab is u=(1, 0)")
    print(f"    - Under 'MIDP': midpoint of a(0,0) and b(4,0) is u=(2, 0)")
    print(f"    - Under 'XYZ':  unsupported command, must be rejected before solver")

    demo_dir = repo_root / "reports" / "geometric-reading-demo"
    demo_dir.mkdir(parents=True, exist_ok=True)

    test_words = [
        ("PERP", False),
        ("MIDP", False),
        ("XYZ", True),
    ]

    all_summaries = []
    for word, is_neg in test_words:
        summary = process_word_through_wave_optics(
            word=word,
            built_letters=built_letters,
            external_points=external_points,
            loaded_policy=loaded_policy,
            rec_lib=rec_lib,
            output_base_dir=demo_dir,
            is_negative_control=is_neg,
        )
        all_summaries.append(summary)

    # -------------------------------------------------------------------------
    # 4. Final Comprehensive Status Report (Decided from Actual Results)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PIPELINE EXECUTION SUMMARY & VERIFICATION MATRIX")
    print("=" * 70)
    print(f"{'Word':<8} | {'Type':<12} | {'Recognized':<10} | {'SpecValid':<10} | {'Solved':<8} | {'Replay':<8} | {'Result':<8}")
    print("-" * 75)

    all_passed = True
    for s in all_summaries:
        w = s["word"]
        wtype = "Neg Control" if s["is_negative_control"] else "Valid Target"
        rec = s["wave_recognized_word"]
        v = s["step_verifications"]
        spec_v = str(v["spec_valid"])
        solved_v = str(v["solve_passed"])
        replay_v = str(v["replay_passed"])
        res_v = "PASS" if v["overall_passed"] else "FAIL"
        if not v["overall_passed"]:
            all_passed = False
        print(f"{w:<8} | {wtype:<12} | {rec:<10} | {spec_v:<10} | {solved_v:<8} | {replay_v:<8} | {res_v:<8}")

    print("-" * 75)
    print(f"Final Pipeline Verdict: {'ALL STAGES PASSED' if all_passed else 'PIPELINE HAD FAILURES'}")
    print("=" * 70)

    # Save master summary JSON
    with (demo_dir / "master_summary.json").open("w", encoding="utf-8") as f:
        json.dump({
            "all_passed": all_passed,
            "summaries": all_summaries,
            "policy": loaded_policy.to_dict(),
        }, f, indent=2)

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()
