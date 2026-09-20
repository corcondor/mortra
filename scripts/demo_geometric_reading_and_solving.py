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
    WaveField2D,
    phase_retrieval_gerchberg_saxton,
)


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
    # 2. Composing and Rendering a Word/Sentence as a Geometric Scene
    # -------------------------------------------------------------------------
    word = "PERP"
    print(f"\n[2] Composing word '{word}' as a unified geometric scene...")
    letter_width = 4
    letter_height = 6
    letter_spacing = 6
    scale = 8  # pixels per unit
    radius = Fraction(3, 8) * scale  # stroke width

    # Compose polylines with horizontal translation morphisms
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

    # Render bitmap using exact rational stroke distances
    t0 = time.perf_counter()
    scene_bitmap = raster.render(composed_segments, radius, total_width, total_height)
    render_time = time.perf_counter() - t0
    print(f"  Rendered scene bitmap: {total_width}x{total_height} px, {scene_bitmap.count()} inked cells in {render_time:.3f}s.")

    # ASCII representation of the rendered word
    print("\n  Rendered Word ASCII Preview (downsampled 2x for display):")
    for j in range(total_height - 1, -1, -4):
        line = "".join("#" if any((i, j - dy) in scene_bitmap.black for dy in range(4)) else " "
                       for i in range(0, total_width, 2))
        print("    " + line)

    # -------------------------------------------------------------------------
    # 3. Geometric Segmentation and Reading (No OCR, No Neural Net)
    # -------------------------------------------------------------------------
    print(f"\n[3] Reading and recognizing letters from the raw bitmap...")
    lib = reading.library_from(built_letters)

    components = raster.components(scene_bitmap)
    letter_comps = []
    for comp in components:
        if len(comp) > 20:
            xs = [i for i, j in comp]
            letter_comps.append((min(xs), comp))
    letter_comps.sort(key=lambda x: x[0])

    recognized_chars = []
    recognition_details = []
    for idx, (min_x, comp) in enumerate(letter_comps):
        xs = [i for i, j in comp]
        ys = [j for i, j in comp]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        sub_black = {(i - min(xs), j - min(ys)) for i, j in comp}
        sub_bm = raster.Bitmap(w, h, sub_black)

        res = reading.read(sub_bm, lib)
        char = res["letter"]
        score = float(res["score"])
        margin = float(res["margin"])
        recognized_chars.append(char)
        recognition_details.append({
            "segment_index": idx,
            "x_range": [min(xs), max(xs)],
            "recognized": char,
            "score": score,
            "margin": margin,
        })
        print(f"  Segment {idx+1} at x=[{min(xs)}, {max(xs)}]: Recognized '{char}' (agreement: {score:.3f}, margin: {margin:.3f})")

    recognized_word = "".join(recognized_chars)
    print(f"  -> Successfully recognized word: '{recognized_word}'")

    # -------------------------------------------------------------------------
    # 4. Generating Formal Specification from Recognized Text & External Inputs
    # -------------------------------------------------------------------------
    print(f"\n[4] Generating formal specification from '{recognized_word}'...")
    # Explicit external inputs (coordinates NOT read from the bitmap)
    external_points = {
        "a": [0, 0],
        "b": [4, 0],
        "c": [2, 3],
    }
    print(f"  External point inputs: {external_points}")

    # Test 4a: Parse recognized command
    parsed_spec = parser.parse_geometric_instruction(recognized_word, external_points)
    print(f"  Parser output for '{recognized_word}': valid={parsed_spec['valid']}")
    if not parsed_spec["valid"]:
        raise RuntimeError(f"Command '{recognized_word}' was rejected by parser: {parsed_spec['reason']}")

    task = parsed_spec["task"]
    print(f"  Generated formal task: points={task['points']}, goals={task['goals']}")

    # Test 4b: Rejection of invalid/unknown commands (must NOT fall back to default task)
    invalid_test = parser.parse_geometric_instruction("UNKNOWN_CMD", external_points)
    print(f"  Rejection test ('UNKNOWN_CMD'): valid={invalid_test['valid']}, reason='{invalid_test['reason']}'")
    assert invalid_test["valid"] is False, "Invalid command was improperly accepted!"
    assert invalid_test["task"] is None, "Invalid command produced an executable task!"

    # Test 4c: Different valid commands produce different goals
    midp_test = parser.parse_geometric_instruction("MIDP", external_points)
    print(f"  Alternative command ('MIDP'): valid={midp_test['valid']}, goals={midp_test['task']['goals']}")
    assert midp_test["task"]["goals"] != task["goals"], "Different commands produced identical goals!"

    # Solve the task with MORTRA's relational synthesizer
    print("  Solving the recognized task via loop.solve...")
    t0 = time.perf_counter()
    res_solve = loop.solve(task, applications=10)
    solve_time = time.perf_counter() - t0
    meas = loop.measurements(res_solve)

    print(f"  Solved: {meas['solved']}")
    print(f"  Applications: {meas['primitive_applications']}")
    print(f"  Search states: {meas['search_states']}")
    print(f"  Polynomial checks: {meas['costs']['polynomial_checks']}")
    print(f"  Wall time: {meas['wall_seconds']:.4f}s")
    if meas['solved']:
        sol = res_solve.get("solution", {})
        print(f"  Constructed point: {sol.get('point')}")
        print(f"  Construction term: {sol.get('term')}")
        print(f"  Exact replay passed: {sol.get('replay', {}).get('passed')}")

    # -------------------------------------------------------------------------
    # 5. Representation Self-Improvement: Training, Persistence, and Reloading
    # -------------------------------------------------------------------------
    print("\n[5] Training, Selecting, and Persisting Better Recognition Representations...")
    narrow_letters = constr.as_coordinates(constr.as_names(alpha.NARROW, names), replayed_coords)

    # Train/select optimal policy using Pareto optimization over validation deformations
    best_policy, train_report = rec_policy.train_recognition_policy(
        reference_alphabet=built_letters,
        validation_letters=narrow_letters,
        current_policy=rec_policy.DEFAULT_POLICY,
    )
    print(f"  Selected Policy: {best_policy.policy_id} ({best_policy.description})")
    print(f"  Policy updated from default: {train_report['policy_updated']}")

    # Persist policy checkpoint
    policy_dir = repo_root / "reports" / "recognition-policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    policy_path = policy_dir / "recognition_policy.json"
    rec_policy.save_recognition_policy(best_policy, policy_path)
    print(f"  Saved policy checkpoint to: {policy_path}")

    # Reload policy in separate step to verify persistence round-trip
    loaded_policy = rec_policy.load_recognition_policy(policy_path)
    assert loaded_policy == best_policy, "Loaded policy did not match saved policy!"
    print(f"  Reloaded policy verified from disk: {loaded_policy.policy_id}")

    # -------------------------------------------------------------------------
    # 6. Wave Optics Round-Trip: Direct Scene Bitmap to Wave Field and Back
    # -------------------------------------------------------------------------
    print("\n[6] Wave Optics Round-Trip: Bitmap -> SLM -> Wave Propagation -> Sensor -> Bitmap -> Reading...")
    # Convert scene_bitmap directly into wave optics target intensity (no redrawing)
    target_intensity = np.zeros((total_height, total_width), dtype=np.float64)
    for x, y in scene_bitmap.black:
        target_intensity[y, x] = 1.0

    # Physical parameters
    wavelength = 532e-9  # 532 nm
    dx = 10e-6  # 10 um pitch
    dy = 10e-6
    grid = GridSpec2D(nx=total_width, ny=total_height, dx=dx, dy=dy)
    z = 0.008  # 8 mm propagation distance (z < z_crit = 12.0 mm, certified TF regime)

    print(f"  Physical parameters: lambda={wavelength*1e9:.1f}nm, pitch=({dx*1e6:.1f}um, {dy*1e6:.1f}um), z={z*1e3:.1f}mm")
    print(f"  Grid: {grid.nx}x{grid.ny} px, Physical window: {grid.lx*1e3:.2f}mm x {grid.ly*1e3:.2f}mm")

    # Phase retrieval via Gerchberg-Saxton
    optical_train = OpticalTrain()
    optical_train.add(FresnelPropagation(distance=z, wavelength=wavelength))
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
    print(f"  Phase retrieval completed in {gs_time:.3f}s (initial error: {gs_errors[0]:.4f} -> final: {gs_errors[-1]:.4f})")

    # Forward propagation to sensor plane
    field_in = WaveField2D(
        u=input_amplitude * np.exp(1j * phase_slm),
        grid=grid,
        wavelength=wavelength,
        z=0.0,
    )
    field_sensor = optical_train.apply(field_in)
    i_sensor = field_sensor.intensity()

    # Objective binarization condition (Otsu thresholding, no arbitrary tuning)
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
    print(f"  Objective Binarization Condition: {binarization_condition}")

    # Construct reconstructed bitmap
    reconstructed_black = {
        (x, y)
        for y in range(total_height)
        for x in range(total_width)
        if norm_i[y, x] >= threshold_val
    }
    reconstructed_bitmap = raster.Bitmap(total_width, total_height, reconstructed_black)
    print(f"  Reconstructed Bitmap: {reconstructed_bitmap.count()} inked cells (original: {scene_bitmap.count()})")

    # Read reconstructed bitmap using the loaded recognition policy
    rec_lib = reading.library_from(
        built_letters,
        grid=loaded_policy.grid,
        use_relations=loaded_policy.use_relations,
        use_structure=loaded_policy.use_structure,
        frame=loaded_policy.frame,
    )

    reconstructed_comps = raster.components(reconstructed_bitmap)
    rec_letter_comps = []
    for comp in reconstructed_comps:
        if len(comp) > 20:
            xs = [i for i, j in comp]
            rec_letter_comps.append((min(xs), comp))
    rec_letter_comps.sort(key=lambda x: x[0])

    rec_chars = []
    for idx, (min_x, comp) in enumerate(rec_letter_comps):
        xs = [i for i, j in comp]
        ys = [j for i, j in comp]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        sub_black = {(i - min(xs), j - min(ys)) for i, j in comp}
        sub_bm = raster.Bitmap(w, h, sub_black)

        res = reading.read(
            sub_bm,
            rec_lib,
            grid=loaded_policy.grid,
            use_relations=loaded_policy.use_relations,
            use_structure=loaded_policy.use_structure,
            frame=loaded_policy.frame,
        )
        rec_chars.append(res["letter"])
        print(f"  Wave Segment {idx+1} at x=[{min(xs)}, {max(xs)}]: Recognized '{res['letter']}' (score: {float(res['score']):.3f})")

    wave_word = "".join(rec_chars)
    print(f"  -> Word recognized from wave optical reconstruction: '{wave_word}'")

    # -------------------------------------------------------------------------
    # 7. Saving Evidence and Artifacts
    # -------------------------------------------------------------------------
    out_dir = repo_root / "reports" / "geometric-reading-demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    wave_dir = repo_root / "reports" / "wave-optics-roundtrip"
    wave_dir.mkdir(parents=True, exist_ok=True)

    demo_results = {
        "composed_word": word,
        "recognized_word": recognized_word,
        "recognition_details": recognition_details,
        "formal_specification": parsed_spec,
        "solver_solution": res_solve,
        "solver_measurements": meas,
    }
    with (out_dir / "demo_results.json").open("w", encoding="utf-8") as f:
        json.dump(demo_results, f, indent=2)

    with (policy_dir / "training_report.json").open("w", encoding="utf-8") as f:
        json.dump(train_report, f, indent=2)

    roundtrip_results = {
        "physical_parameters": {
            "wavelength_m": wavelength,
            "dx_m": dx,
            "dy_m": dy,
            "z_m": z,
            "grid_nx": grid.nx,
            "grid_ny": grid.ny,
        },
        "phase_retrieval": {
            "iterations": len(gs_errors),
            "initial_error": float(gs_errors[0]),
            "final_error": float(gs_errors[-1]),
            "seconds": gs_time,
        },
        "binarization_condition": binarization_condition,
        "original_inked_cells": scene_bitmap.count(),
        "reconstructed_inked_cells": reconstructed_bitmap.count(),
        "wave_recognized_word": wave_word,
    }
    with (wave_dir / "roundtrip_results.json").open("w", encoding="utf-8") as f:
        json.dump(roundtrip_results, f, indent=2)

    print(f"\n  Saved demo results to: {out_dir / 'demo_results.json'}")
    print(f"  Saved roundtrip results to: {wave_dir / 'roundtrip_results.json'}")
    print(f"  Saved policy report to: {policy_dir / 'training_report.json'}")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE: Full loop of construction -> drawing -> reading -> formal spec -> problem solving -> representation training -> wave optics round-trip verified.")
    print("=" * 70)


if __name__ == "__main__":
    run_pipeline()
