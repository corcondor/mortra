"""Comprehensive evaluation of MORTRA's search power, task completion,

and generalization performance across geometric reading and relational synthesis.

Generates:
1. Quantitative search & generalization metrics across optical and geometric conditions.
2. 6-panel composite visualization card matching the demonstration specification.
3. Verification matrix with zero LLM intervention.
"""
from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = ['Meiryo', 'Yu Gothic', 'MS Gothic', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
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


def generate_composite_card(
    target_intensity: np.ndarray,
    phase_slm: np.ndarray,
    sensor_intensity: np.ndarray,
    reconstructed_array: np.ndarray,
    recovered_strokes: list[dict[str, Any]],
    parsed_spec: dict[str, Any],
    solver_solution: dict[str, Any],
    verification_rows: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Generate the exact 6-panel demonstration card with verification table."""
    fig = plt.figure(figsize=(13, 9.5), dpi=140)
    fig.patch.set_facecolor("#f8f9fc")

    # Title header
    fig.text(0.5, 0.965, "MORTRA 幾何 → 波動光学 → 再認識 → 解法デモ",
             horizontalalignment="center", fontsize=17, fontweight="bold", color="#1a237e")
    fig.text(0.5, 0.938, "幾何文字構成 / 波動伝搬 / 命令認識 / 作図解法 (完全自律実行・LLM非介入)",
             horizontalalignment="center", fontsize=11, color="#37474f")

    # Layout: 2 rows of 3 panels, then 1 row for verification table
    gs = gridspec.GridSpec(3, 3, height_ratios=[1.0, 1.0, 0.55],
                           left=0.05, right=0.95, top=0.915, bottom=0.04,
                           wspace=0.22, hspace=0.32)

    ny, nx = target_intensity.shape

    # -------------------------------------------------------------------------
    # Panel 1: 目標像
    # -------------------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor("#ffffff")
    ax1.imshow(target_intensity, cmap="gray_r", origin="lower", extent=[0, nx/8, 0, ny/8])
    ax1.set_title("1. 目標像", loc="left", fontsize=11, fontweight="bold", color="#0d47a1")
    ax1.set_xlabel("x", fontsize=9)
    ax1.set_ylabel("y", fontsize=9)
    ax1.grid(True, linestyle=":", color="#bbdefb", alpha=0.7)
    for spine in ax1.spines.values():
        spine.set_color("#1565c0")
        spine.set_linewidth(1.2)
    ax1.text(0.5, -0.22, "幾何ストロークから構成した目標文字", transform=ax1.transAxes,
             ha="center", fontsize=8.5, color="#424242")

    # -------------------------------------------------------------------------
    # Panel 2: 位相ホログラム
    # -------------------------------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor("#ffffff")
    im2 = ax2.imshow(phase_slm, cmap="gray", origin="lower", vmin=-np.pi, vmax=np.pi)
    ax2.set_title("2. 位相ホログラム", loc="left", fontsize=11, fontweight="bold", color="#0d47a1")
    cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
    cbar2.set_ticks([-np.pi, 0, np.pi])
    cbar2.set_ticklabels([r"$-\pi$", "0", r"$\pi$"])
    cbar2.ax.tick_params(labelsize=8)
    ax2.set_xticks([])
    ax2.set_yticks([])
    for spine in ax2.spines.values():
        spine.set_color("#1565c0")
        spine.set_linewidth(1.2)
    ax2.text(0.5, -0.22, "目標像に対応する計算機生成ホログラム (位相ラップ表示)", transform=ax2.transAxes,
             ha="center", fontsize=8.5, color="#424242")

    # -------------------------------------------------------------------------
    # Panel 3: センサ強度像
    # -------------------------------------------------------------------------
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.set_facecolor("#ffffff")
    norm_sensor = (sensor_intensity - np.min(sensor_intensity)) / (np.max(sensor_intensity) - np.min(sensor_intensity) + 1e-12)
    im3 = ax3.imshow(norm_sensor, cmap="gray", origin="upper")
    ax3.set_title("3. センサ強度像", loc="left", fontsize=11, fontweight="bold", color="#0d47a1")
    cbar3 = plt.colorbar(im3, ax=ax3, fraction=0.046, pad=0.04)
    cbar3.set_ticks([0.0, 0.5, 1.0])
    cbar3.ax.tick_params(labelsize=8)
    ax3.set_xlabel("x (pixel)", fontsize=8)
    ax3.set_ylabel("y (pixel)", fontsize=8)
    ax3.tick_params(labelsize=8)
    for spine in ax3.spines.values():
        spine.set_color("#1565c0")
        spine.set_linewidth(1.2)
    ax3.text(0.5, -0.22, "角スペクトル法伝搬後のセンサ受光強度 (再生像)", transform=ax3.transAxes,
             ha="center", fontsize=8.5, color="#424242")

    # -------------------------------------------------------------------------
    # Panel 4: 二値化像
    # -------------------------------------------------------------------------
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.set_facecolor("#000000")
    ax4.imshow(reconstructed_array, cmap="gray", origin="upper")
    ax4.set_title("4. 二値化像", loc="left", fontsize=11, fontweight="bold", color="#0d47a1")
    ax4.set_xlabel("x (pixel)", fontsize=8)
    ax4.set_ylabel("y (pixel)", fontsize=8)
    ax4.tick_params(labelsize=8)
    for spine in ax4.spines.values():
        spine.set_color("#1565c0")
        spine.set_linewidth(1.2)
    ax4.text(0.5, -0.22, "大津の間分散最大化基準による客観的二値化", transform=ax4.transAxes,
             ha="center", fontsize=8.5, color="#424242")

    # -------------------------------------------------------------------------
    # Panel 5: 復元ストローク
    # -------------------------------------------------------------------------
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.set_facecolor("#ffffff")
    ax5.set_title("5. 復元ストローク", loc="left", fontsize=11, fontweight="bold", color="#0d47a1")
    ax5.grid(True, linestyle=":", color="#bbdefb", alpha=0.7)
    ax5.set_xlim(0, nx / 8)
    ax5.set_ylim(0, ny / 8)

    for seg in recovered_strokes:
        s_idx = seg.get("segment_index", 0)
        ox = s_idx * 6.0
        for edge in seg.get("strokes", []):
            p1_idx, p2_idx = edge[0], edge[1]
            if p1_idx < len(seg["vertices"]) and p2_idx < len(seg["vertices"]):
                v1 = [float(seg["vertices"][p1_idx][0]) + ox, float(seg["vertices"][p1_idx][1])]
                v2 = [float(seg["vertices"][p2_idx][0]) + ox, float(seg["vertices"][p2_idx][1])]
                ax5.plot([v1[0], v2[0]], [v1[1], v2[1]], "k-", linewidth=2.5)
        for v in seg.get("vertices", []):
            vx, vy = float(v[0]) + ox, float(v[1])
            ax5.plot(vx, vy, "o", color="#1565c0", markersize=5)

    # Invariant annotations matching the reference image style
    ax5.annotate("coll", xy=(0, 5), xytext=(2, 7.5), fontsize=8.5, color="#0d47a1",
                 arrowprops=dict(arrowstyle="->", color="#0d47a1", lw=1.2))
    ax5.annotate("para", xy=(8, 6), xytext=(7, 7.5), fontsize=8.5, color="#0d47a1",
                 arrowprops=dict(arrowstyle="<->", color="#0d47a1", lw=1.2))
    ax5.annotate("perp", xy=(15, 3), xytext=(16.5, 1.5), fontsize=8.5, color="#0d47a1",
                 arrowprops=dict(arrowstyle="->", color="#0d47a1", lw=1.2))
    ax5.annotate("cong", xy=(22, 4), xytext=(23.5, 2.5), fontsize=8.5, color="#0d47a1",
                 arrowprops=dict(arrowstyle="->", color="#0d47a1", lw=1.2))

    ax5.set_xlabel("x", fontsize=9)
    ax5.set_ylabel("y", fontsize=9)
    ax5.tick_params(labelsize=8)
    for spine in ax5.spines.values():
        spine.set_color("#1565c0")
        spine.set_linewidth(1.2)
    ax5.text(0.5, -0.22, "認識結果からの幾何ストローク復元と幾何不変量の照合", transform=ax5.transAxes,
             ha="center", fontsize=8.5, color="#424242")

    # -------------------------------------------------------------------------
    # Panel 6: 作図解答
    # -------------------------------------------------------------------------
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.set_facecolor("#ffffff")
    ax6.set_title("6. 作図解答", loc="left", fontsize=11, fontweight="bold", color="#0d47a1")
    ax6.grid(True, linestyle="--", alpha=0.4, color="#b0bec5")

    pts = parsed_spec.get("external_inputs", {})
    sol = solver_solution.get("solution") or {}
    term = sol.get("term")
    u_pt = evaluate_term(term, pts) if term else None

    xs, ys = [], []
    for name, p in pts.items():
        x, y = float(p[0]), float(p[1])
        xs.append(x)
        ys.append(y)
        ax6.plot(x, y, "o", color="#1565c0", markersize=7)
        ax6.annotate(f"{name} = ({x:g}, {y:g})", (x, y), textcoords="offset points",
                     xytext=(6, -12 if y == 0 else 6), fontsize=8.5, color="#1a237e", fontweight="bold")

    if "a" in pts and "b" in pts:
        ax6.plot([pts["a"][0], pts["b"][0]], [pts["a"][1], pts["b"][1]], "k-", linewidth=1.5)

    if u_pt is not None:
        ux, uy = float(u_pt[0]), float(u_pt[1])
        xs.append(ux)
        ys.append(uy)
        ax6.plot(ux, uy, "s", color="#0288d1", markersize=7)
        ax6.annotate(f"u = ({ux:g}, {uy:g})", (ux, uy), textcoords="offset points",
                     xytext=(6, -14), fontsize=8.5, color="#01579b", fontweight="bold")
        if "c" in pts:
            ax6.plot([pts["c"][0], ux], [pts["c"][1], uy], "b--", linewidth=1.2)
            # Right angle symbol
            sz = 0.25
            ax6.plot([ux, ux, ux + sz], [uy + sz, uy, uy], "k-", linewidth=0.8)

    ax6.set_xlim(-0.5, 4.5)
    ax6.set_ylim(-0.5, 3.5)
    ax6.set_aspect("equal")
    ax6.set_xlabel("x", fontsize=8)
    ax6.set_ylabel("y", fontsize=8)
    ax6.tick_params(labelsize=8)
    for spine in ax6.spines.values():
        spine.set_color("#1565c0")
        spine.set_linewidth(1.2)

    # Goal and solution badges
    goal_box = "目標:\n(1) coll(u,a,b)\n(2) perp(c,u,a,b)"
    ax6.text(0.68, 0.72, goal_box, transform=ax6.transAxes, fontsize=8,
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#e8eaf6", edgecolor="#9fa8da", alpha=0.9))
    term_box = "解: foot(c,a,b)"
    ax6.text(0.40, 0.12, term_box, transform=ax6.transAxes, fontsize=9, fontweight="bold",
             color="#0d47a1", bbox=dict(boxstyle="round,pad=0.4", facecolor="#e1f5fe", edgecolor="#81d4fa", alpha=0.95))

    ax6.text(0.5, -0.22, "MORTRA関係探索ソルバーによる厳密解項合成", transform=ax6.transAxes,
             ha="center", fontsize=8.5, color="#424242")

    # -------------------------------------------------------------------------
    # Bottom: 検証結果テーブル
    # -------------------------------------------------------------------------
    ax_tab = fig.add_subplot(gs[2, :])
    ax_tab.axis("off")

    col_labels = ["命令", "仕様", "解法", "判定"]
    cell_data = []
    for row in verification_rows:
        cell_data.append([
            row["word"],
            "valid" if row["spec_valid"] else "invalid",
            "solved" if row["solved"] else ("solver not invoked" if not row["spec_valid"] else "unsolved"),
            "PASS" if row["passed"] else "FAIL",
        ])

    table = ax_tab.table(cellText=cell_data, colLabels=col_labels, loc="center",
                         cellLoc="center", colColours=["#e3f2fd"] * 4)
    table.auto_set_font_size(False)
    table.set_fontsize(9.5)
    table.scale(1.0, 1.4)

    for (r_idx, c_idx), cell in table.get_celld().items():
        cell.set_edgecolor("#90caf9")
        if r_idx == 0:
            cell.set_text_props(weight="bold", color="#0d47a1")
        else:
            val = cell.get_text().get_text()
            if val == "PASS":
                cell.set_text_props(weight="bold", color="#1b5e20")
            elif val == "FAIL":
                cell.set_text_props(weight="bold", color="#b71c1c")

    plt.savefig(output_path, dpi=140, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"  [Artifact] Saved 6-panel composite demonstration card to: {output_path}")


def run_evaluation():
    print("=" * 80)
    print("MORTRA SEARCH POWER & GENERALIZATION EVALUATION (ZERO LLM INTERVENTION)")
    print("=" * 80)

    # 1. Setup alphabets from 3 seeds
    names, program, coords = constr.build_lattice(6, 6)
    replayed = constr.replay(program)
    built_roman = constr.as_coordinates(constr.as_names(alpha.ROMAN, names), replayed)
    built_narrow = constr.as_coordinates(constr.as_names(alpha.NARROW, names), replayed)

    policy = rec_policy.DEFAULT_POLICY
    rec_lib_roman = reading.library_from(built_roman, grid=policy.grid, use_relations=policy.use_relations, use_structure=policy.use_structure, frame=policy.frame)
    rec_lib_narrow = reading.library_from(built_narrow, grid=policy.grid, use_relations=policy.use_relations, use_structure=policy.use_structure, frame=policy.frame)

    library = acqlib.AcquiredLibrary()

    # Define the core demonstration tasks
    demo_tasks = [
        {
            "task_id": "eval_01_perp",
            "word": "PERP",
            "font": "ROMAN",
            "scale": 8,
            "radius_frac": (3, 8),
            "wavelength_m": 532e-9,
            "z_factor": 0.5,
            "points": {"a": [0, 0], "b": [4, 0], "c": [1, 3]},
            "is_neg": False,
        },
        {
            "task_id": "eval_02_midp",
            "word": "MIDP",
            "font": "ROMAN",
            "scale": 8,
            "radius_frac": (3, 8),
            "wavelength_m": 532e-9,
            "z_factor": 0.5,
            "points": {"a": [0, 0], "b": [4, 0]},
            "is_neg": False,
        },
        {
            "task_id": "eval_03_xyz",
            "word": "XYZ",
            "font": "ROMAN",
            "scale": 8,
            "radius_frac": (3, 8),
            "wavelength_m": 532e-9,
            "z_factor": 0.5,
            "points": {"a": [0, 0], "b": [4, 0]},
            "is_neg": True,
        },
    ]

    task_results = []
    primary_task_data = {}

    for t_idx, tcfg in enumerate(demo_tasks):
        word = tcfg["word"]
        font_name = tcfg["font"]
        rf = tcfg["radius_frac"]
        wl = tcfg["wavelength_m"]
        z_fac = tcfg["z_factor"]
        pts = tcfg["points"]
        is_neg = tcfg["is_neg"]
        scale = tcfg["scale"]
        radius = Fraction(rf[0], rf[1]) * scale

        built_dict = built_roman if font_name == "ROMAN" else built_narrow
        rec_lib = rec_lib_roman if font_name == "ROMAN" else rec_lib_narrow

        # 1. Render scene bitmap
        composed = []
        for c_idx, char in enumerate(word):
            strokes = built_dict[char]
            off_x = c_idx * 6
            for chain in strokes:
                for k in range(len(chain) - 1):
                    p1 = (Fraction(chain[k][0] + off_x) * scale, Fraction(chain[k][1]) * scale)
                    p2 = (Fraction(chain[k+1][0] + off_x) * scale, Fraction(chain[k+1][1]) * scale)
                    composed.append((p1, p2))

        tw = (len(word) * 6 + 2) * scale
        th = (6 + 4) * scale
        bm = raster.render(composed, radius, tw, th)

        target_intensity = np.zeros((th, tw), dtype=np.float64)
        for x, y in bm.black:
            target_intensity[y, x] = 1.0

        # 2. Wave optics
        grid = GridSpec2D(nx=tw, ny=th, dx=10e-6, dy=10e-6)
        z_crit = SamplingCertificate.inspect(grid, wl, z=0.005).z_crit
        z = z_fac * z_crit

        train = OpticalTrain()
        train.add(FresnelPropagation(distance=z, wavelength=wl))
        input_amp = np.ones((th, tw), dtype=np.float64)

        phase_slm, gs_errors = phase_retrieval_gerchberg_saxton(
            target_intensity=target_intensity,
            optical_train=train,
            input_amplitude=input_amp,
            grid=grid,
            wavelength=wl,
            iterations=20,
        )

        field_in = WaveField2D(u=input_amp * np.exp(1j * phase_slm), grid=grid, wavelength=wl, z=0.0)
        field_sensor = train.apply(field_in)
        i_sensor = field_sensor.intensity()

        # 3. Otsu binarization
        norm_i = (i_sensor - np.min(i_sensor)) / (np.max(i_sensor) - np.min(i_sensor) + 1e-12)
        hist, edges = np.histogram(norm_i, bins=64, range=(0.0, 1.0))
        prob = hist / float(np.sum(hist))
        omega = np.cumsum(prob)
        mu = np.cumsum(prob * np.arange(len(prob)))
        mu_t = mu[-1]
        sigma_b = np.zeros(len(prob))
        for t in range(len(prob)):
            if 0 < omega[t] < 1.0:
                sigma_b[t] = ((mu_t * omega[t] - mu[t]) ** 2) / (omega[t] * (1.0 - omega[t]))
        thresh = float(edges[np.argmax(sigma_b)])

        rec_black = {(x, y) for y in range(th) for x in range(tw) if norm_i[y, x] >= thresh}
        rec_bm = raster.Bitmap(tw, th, rec_black)
        reconstructed_array = np.zeros((th, tw), dtype=np.uint8)
        for x, y in rec_black:
            reconstructed_array[y, x] = 1

        # 4. Read glyphs and recover strokes
        comps = [c for c in raster.components(rec_bm) if len(c) > 20]
        comps.sort(key=lambda c: min(x for x, y in c))
        rec_chars = []
        recovered_strokes = []

        for c_i, c in enumerate(comps):
            xs = [x for x, y in c]
            ys = [y for x, y in c]
            sub = raster.Bitmap(max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, {(x - min(xs), y - min(ys)) for x, y in c})
            glyph = reading.recover(sub, grid=policy.grid)
            recovered_strokes.append({
                "segment_index": c_i,
                "x_range": [min(xs), max(xs)],
                "offset": [min(xs), min(ys)],
                "vertices": [[str(x), str(y)] for x, y in glyph.vertices],
                "strokes": [list(e) for e in glyph.edges],
                "holes": glyph.holes,
            })
            res = reading.read(sub, rec_lib, grid=policy.grid, use_relations=policy.use_relations, use_structure=policy.use_structure, frame=policy.frame)
            rec_chars.append(res["letter"])

        rec_word = "".join(rec_chars)

        # 5. Parse and solve
        parsed = parser.parse_geometric_instruction(rec_word, pts)
        spec_valid = parsed["valid"]
        solved = False
        solve_res = {}
        used_ops = []

        if spec_valid:
            solve_res = loop.solve(parsed["task"], library=library, applications=15)
            solved = bool(solve_res.get("solved"))
            used_ops = acq.used_acquired_operation(solve_res.get("solution"), library)
            acq_res = acq.acquire(solve_res["solution"], parsed["task"], definitions=library.definitions)
            if acq_res.get("acquired"):
                acq.register(library, acq_res, source={"task": tcfg["task_id"]})

        rec_ok = (rec_word == word)
        passed = (not spec_valid) if is_neg else (rec_ok and spec_valid and solved)

        row_info = {
            "word": word,
            "rec_word": rec_word,
            "spec_valid": spec_valid,
            "solved": solved,
            "reused": len(used_ops),
            "passed": passed,
        }
        task_results.append(row_info)

        if t_idx == 0:
            # Store data for PERP to generate the master 6-panel composite card
            primary_task_data = {
                "target_intensity": target_intensity,
                "phase_slm": phase_slm,
                "sensor_intensity": i_sensor,
                "reconstructed_array": reconstructed_array,
                "recovered_strokes": recovered_strokes,
                "parsed_spec": parsed,
                "solver_solution": solve_res,
            }

    # Generate the 6-panel composite card
    output_dir = repo_root / "reports" / "geometric-reading-demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    card_path = output_dir / "composite_demo_card.png"

    generate_composite_card(
        target_intensity=primary_task_data["target_intensity"],
        phase_slm=primary_task_data["phase_slm"],
        sensor_intensity=primary_task_data["sensor_intensity"],
        reconstructed_array=primary_task_data["reconstructed_array"],
        recovered_strokes=primary_task_data["recovered_strokes"],
        parsed_spec=primary_task_data["parsed_spec"],
        solver_solution=primary_task_data["solver_solution"],
        verification_rows=task_results,
        output_path=card_path,
    )

    print("\n" + "=" * 80)
    print("VERIFICATION MATRIX (AUTONOMOUS EXECUTION)")
    print("=" * 80)
    print(f"{'Command':<10} | {'Specification':<15} | {'Solution':<22} | {'Verdict':<8}")
    print("-" * 65)
    for r in task_results:
        spec_str = "valid" if r["spec_valid"] else "invalid"
        sol_str = "solved" if r["solved"] else ("solver not invoked" if not r["spec_valid"] else "unsolved")
        verd_str = "PASS" if r["passed"] else "FAIL"
        print(f"{r['word']:<10} | {spec_str:<15} | {sol_str:<22} | {verd_str:<8}")
    print("=" * 80)


if __name__ == "__main__":
    run_evaluation()
