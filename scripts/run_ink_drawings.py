"""Draw with one black dot: a pale face, a dark face, a gradient, and a geometric shadow.

Every image uses the same convention — a point becomes a black disk of one fixed
radius on white paper — so the only thing that can carry tone is how many points
are placed where. The lattice the points come from is built by the fragment's own
`midpoint` and `mirror`; which lattice sites take ink is a plain deterministic
rule; and for the shadow, whether a site is inside comes from a composition of
the predicates the fragment already has, with `intersection_ll` doing the work.

    python scripts/run_ink_drawings.py --output reports/ink
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_ink as ink
from math_os_prototype import geometry_relational_dsl as rdsl


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def constant(level):
    return lambda xy: level


def horizontal_ramp(paper, low, high):
    x0, _, x1, _ = paper
    span = Fraction(x1)-Fraction(x0)

    def level(xy):
        t = (Fraction(xy[0])-Fraction(x0))/span
        return float(low)+(float(high)-float(low))*float(t)
    return level


def shadow_level(light, occluder, inside, outside, stats):
    a, b = occluder

    def level(xy):
        hit, _ = ink.occluded(xy, light, a, b, stats=stats)
        return inside if hit else outside
    return level


def measure(points, radius, paper, windows, *, samples):
    rows = []
    for name, window in windows:
        record = {"window_name": name}
        record.update(ink.coverage(points, radius, window, samples=samples))
        record.update(ink.analytic_coverage(points, radius, window))
        rows.append(record)
    return rows


def grid_of_windows(paper, columns, rows_count):
    x0, y0, x1, y1 = (Fraction(v) for v in paper)
    windows = []
    for a in range(columns):
        for b in range(rows_count):
            windows.append((f"cell {a},{b}",
                            (x0+(x1-x0)*a/columns, y0+(y1-y0)*b/rows_count,
                             x0+(x1-x0)*(a+1)/columns, y0+(y1-y0)*(b+1)/rows_count)))
    return windows


def band_windows(paper, bands):
    x0, y0, x1, y1 = (Fraction(v) for v in paper)
    return [(f"band {i}", (x0+(x1-x0)*i/bands, y0, x0+(x1-x0)*(i+1)/bands, y1))
            for i in range(bands)]


def draw(name, description, points, radius, paper, output, *, pixels_per_unit, statistics,
         extra=None):
    began = time.perf_counter()
    svg = ink.write_svg(output/f"{name}.svg", points, radius, paper,
                        pixels_per_unit=pixels_per_unit)
    png = ink.write_png(output/f"{name}.png", points, radius, paper,
                        pixels_per_unit=pixels_per_unit)
    check = ink.check_svg_is_one_radius_black_circles(output/f"{name}.svg")
    separated, offender = ink.pairwise_separation_ok(points, radius)
    record = {"image": name, "description": description, "dots": len(points),
              "radius_paper_units": float(radius), "paper": [float(v) for v in paper],
              "pixels_per_unit": pixels_per_unit, "svg": svg, "png": png,
              "svg_check": check, "disks_pairwise_disjoint": separated,
              "drawing_seconds": time.perf_counter()-began,
              "geometry_statistics": dict(statistics)}
    if offender is not None:
        record["overlapping_pair"] = [[float(v) for v in offender[0]],
                                      [float(v) for v in offender[1]]]
    if extra:
        record.update(extra)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--depth", type=int, default=5, help="lattice spacing is 1/2**depth")
    parser.add_argument("--pixels-per-unit", type=int, default=300)
    parser.add_argument("--samples", type=int, default=300)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    spacing = Fraction(1, 2**arguments.depth)
    radius = spacing/2
    ceiling = ink.maximum_coverage(radius, spacing)
    report = {"environment": {
        "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip(),
        "python": sys.version.split()[0], "platform": platform.platform()},
        "convention": {
            "a point becomes": "a black disk of radius r, opaque, on white paper",
            "radius_paper_units": float(radius), "lattice_spacing": float(spacing),
            "one radius for every image": True,
            "largest reachable black coverage": ceiling,
            "why": "disks on a lattice of spacing h with r = h/2 are tangent at closest and never "
                   "overlap, so coverage is (inked sites) x pi r^2 / area and cannot pass pi/4",
            "what carries tone": "the number and placement of points, nothing else",
            "clipping": "a lattice site is inked or not; whole disks are drawn, and a disk whose "
                        "centre is near the paper edge is drawn and clipped by the page, the same "
                        "rule in the image and in the measurement"},
        "determinism": {"randomness": "none: the selection is an ordered-dither threshold on the "
                                      "lattice indices, so the same inputs give the same points",
                        "seed": None},
        "images": [], "measurements": {}}
    say(f"lattice spacing {spacing}, radius {radius}, coverage ceiling {ceiling:.4f}")

    # -- the lattice, built by the fragment's primitives ---------------------
    paper = (Fraction(0), Fraction(0), Fraction(4), Fraction(3))
    began = time.perf_counter()
    statistics = Counter()
    lattice, statistics = ink.paper_lattice(4, 3, arguments.depth, statistics)
    say(f"lattice: {len(lattice)} points from {statistics['primitive_applications']} primitive "
        f"applications in {time.perf_counter()-began:.0f}s")
    report["lattice"] = {"sheet_cells": [4, 3], "depth": arguments.depth,
                         "points": len(lattice),
                         "built_by": "midpoint for the unit cell, midpoint and mirror to translate "
                                     "it over the sheet, through execute_primitive",
                         "primitive_applications": statistics["primitive_applications"],
                         "seconds": time.perf_counter()-began}

    targets = {"pale": 0.10, "dark": 0.60, "ramp_low": 0.04, "ramp_high": 0.70,
               "shadow_inside": 0.55, "shadow_outside": 0.06}
    fills = {key: ink.fill_for_coverage(value, radius, spacing) for key, value in targets.items()}
    report["targets"] = {"black_coverage": targets, "inked_site_fraction": fills}

    # -- A, B: one region, two densities ------------------------------------
    for name, key, description in (("a-pale", "pale", "the sheet filled sparsely"),
                                   ("b-dark", "dark", "the same sheet filled densely")):
        say(f"{name}: target coverage {targets[key]}")
        points = ink.select(lattice, constant(fills[key]))
        record = draw(name, description, points, radius, paper, output,
                      pixels_per_unit=arguments.pixels_per_unit, statistics={},
                      extra={"target_black_coverage": targets[key],
                             "inked_site_fraction": fills[key],
                             "selection_rule": "ordered dither, constant level"})
        cells = measure(points, radius, paper, grid_of_windows(paper, 4, 3),
                        samples=arguments.samples)
        record["local_windows"] = cells
        values = [c["black_coverage"] for c in cells]
        record["local_coverage"] = {"mean": sum(values)/len(values), "min": min(values),
                                    "max": max(values),
                                    "spread": max(values)-min(values),
                                    "note": "these windows are whole cells of the sheet, and the "
                                            "dither pattern repeats with a period that divides "
                                            "them, so they can agree exactly; the windows below do "
                                            "not line up with that period"}
        offset = measure(points, radius, paper,
                         [(f"offset {i}", (Fraction(i)*Fraction(7, 10)+Fraction(1, 7), Fraction(1, 5),
                                           Fraction(i)*Fraction(7, 10)+Fraction(1, 7)+Fraction(1, 2),
                                           Fraction(7, 10))) for i in range(5)],
                         samples=arguments.samples)
        record["offset_windows"] = offset
        off_values = [c["black_coverage"] for c in offset]
        record["local_coverage_off_the_dither_period"] = {
            "mean": sum(off_values)/len(off_values), "min": min(off_values), "max": max(off_values),
            "spread": max(off_values)-min(off_values)}
        record["error_against_target"] = record["local_coverage"]["mean"]-targets[key]
        report["images"].append(record)
        say(f"   {len(points)} dots, measured mean coverage "
            f"{record['local_coverage']['mean']:.4f} (target {targets[key]})")

    # -- C: a ramp ----------------------------------------------------------
    say("c-ramp: coverage rising left to right")
    ramp = horizontal_ramp(paper, ink.fill_for_coverage(targets["ramp_low"], radius, spacing),
                           ink.fill_for_coverage(targets["ramp_high"], radius, spacing))
    points = ink.select(lattice, ramp)
    record = draw("c-ramp", "point density rising from left to right", points, radius, paper,
                  output, pixels_per_unit=arguments.pixels_per_unit, statistics={},
                  extra={"target_black_coverage": [targets["ramp_low"], targets["ramp_high"]],
                         "selection_rule": "ordered dither, level linear in x"})
    bands = measure(points, radius, paper, band_windows(paper, 8), samples=arguments.samples)
    for index, band in enumerate(bands):
        centre = (index+Fraction(1, 2))/8
        band["target_black_coverage"] = targets["ramp_low"]+(
            targets["ramp_high"]-targets["ramp_low"])*float(centre)
        band["error"] = band["black_coverage"]-band["target_black_coverage"]
    record["bands"] = bands
    record["monotone_in_x"] = all(bands[i]["black_coverage"] <= bands[i+1]["black_coverage"]+1e-9
                                  for i in range(len(bands)-1))
    record["largest_band_error"] = max(abs(b["error"]) for b in bands)
    report["images"].append(record)
    say(f"   {len(points)} dots, bands "
        f"{[round(b['black_coverage'], 3) for b in bands]}, monotone {record['monotone_in_x']}")

    # -- D: the shadow ------------------------------------------------------
    shadow_paper = (Fraction(6, 5), Fraction(0), Fraction(26, 5), Fraction(3))
    say("d-shadow: a point light, a segment occluder, and the sheet as the window")
    began = time.perf_counter()
    shadow_lattice, lattice_statistics = ink.paper_lattice(4, 3, arguments.depth, Counter())
    shift = Fraction(6, 5)
    shadow_lattice = {index: (xy[0]+shift, xy[1]) for index, xy in shadow_lattice.items()}
    light = (Fraction(0), Fraction(3, 2))
    occluder = ((Fraction(1), Fraction(6, 5)), (Fraction(1), Fraction(9, 5)))
    shadow_statistics = Counter()
    level = shadow_level(light, occluder,
                         ink.fill_for_coverage(targets["shadow_inside"], radius, spacing),
                         ink.fill_for_coverage(targets["shadow_outside"], radius, spacing),
                         shadow_statistics)
    points = ink.select(shadow_lattice, level)
    say(f"   membership decided for {len(shadow_lattice)} sites in "
        f"{time.perf_counter()-began:.0f}s: {dict(shadow_statistics)}")
    inside = [(index, xy) for index, xy in points
              if ink.occluded(xy, light, occluder[0], occluder[1])[0]]
    record = draw("d-shadow", "the shadow a segment casts from a point light, inked densely "
                              "inside and sparsely outside", points, radius, shadow_paper, output,
                  pixels_per_unit=arguments.pixels_per_unit, statistics=shadow_statistics,
                  extra={"light": [float(v) for v in light],
                         "occluder": [[float(v) for v in occluder[0]],
                                      [float(v) for v in occluder[1]]],
                         "window": [float(v) for v in shadow_paper],
                         "target_black_coverage": {"inside": targets["shadow_inside"],
                                                   "outside": targets["shadow_outside"]},
                         "dots_inside_the_shadow": len(inside),
                         "dots_outside": len(points)-len(inside),
                         "selection_rule": "ordered dither whose level is set by the occlusion "
                                           "relation at the site",
                         "relation": "exists P: P on segment(A,B) and P strictly between L and X, "
                                     "reduced to the single candidate intersection_ll(L,X,A,B)"})
    # the windows have to sit wholly on one side of the boundary, or they measure a mixture
    windows = [("inside the shadow", (Fraction(3), Fraction(13, 10), Fraction(7, 2), Fraction(17, 10))),
               ("above the shadow", (Fraction(3), Fraction(28, 10), Fraction(7, 2), Fraction(295, 100))),
               ("below the shadow", (Fraction(3), Fraction(5, 100), Fraction(7, 2), Fraction(20, 100)))]
    record["local_windows"] = measure(points, radius, shadow_paper, windows,
                                      samples=arguments.samples)
    outline = ink.shadow_polygon(light, occluder, shadow_paper)
    record["shadow_outline"] = {"vertices": [[float(v) for v in p] for p in outline],
                                "area_of_the_shadow_in_the_window": float(ink.polygon_area(outline)),
                                "built_by": "intersection_ll of each boundary ray with each side of "
                                            "the window, plus the window corners that are in shadow",
                                "not_the_same_as": "the area the ink covers, which is the black "
                                                   "coverage times the area"}
    report["images"].append(record)
    say(f"   {len(points)} dots, {len(inside)} of them inside the shadow; "
        f"{[round(w['black_coverage'], 3) for w in record['local_windows']]}")

    say("d2-shadow: the same procedure with the light, the occluder and the window moved")
    second_light = (Fraction(1, 2), Fraction(3))
    second_occluder = ((Fraction(3, 2), Fraction(2)), (Fraction(23, 10), Fraction(2)))
    second_statistics = Counter()
    second_level = shadow_level(second_light, second_occluder,
                                ink.fill_for_coverage(targets["shadow_inside"], radius, spacing),
                                ink.fill_for_coverage(targets["shadow_outside"], radius, spacing),
                                second_statistics)
    second_points = ink.select(lattice, second_level)
    second_inside = [(index, xy) for index, xy in second_points
                     if ink.occluded(xy, second_light, second_occluder[0], second_occluder[1])[0]]
    second_outline = ink.shadow_polygon(second_light, second_occluder, paper)
    record = draw("d2-shadow", "the same procedure with the light above and the occluder horizontal",
                  second_points, radius, paper, output,
                  pixels_per_unit=arguments.pixels_per_unit, statistics=second_statistics,
                  extra={"light": [float(v) for v in second_light],
                         "occluder": [[float(v) for v in second_occluder[0]],
                                      [float(v) for v in second_occluder[1]]],
                         "window": [float(v) for v in paper],
                         "dots_inside_the_shadow": len(second_inside),
                         "dots_outside": len(second_points)-len(second_inside),
                         "shadow_outline": {
                             "vertices": [[float(v) for v in p] for p in second_outline],
                             "area_of_the_shadow_in_the_window": float(
                                 ink.polygon_area(second_outline))},
                         "selection_rule": "the same ordered dither driven by the same occlusion "
                                           "relation, with the light and occluder moved"})
    report["images"].append(record)
    say(f"   {len(second_points)} dots, {len(second_inside)} inside; outline "
        f"{[[float(v) for v in p] for p in second_outline]}")

    report["reused"] = ["geometry_relational_dsl.execute_primitive for every constructed point",
                        "the fragment's midpoint, mirror and intersection_ll primitives",
                        "the polynomial meaning of coll, cong and midp, composed by hand into the "
                        "region relations",
                        "Pillow, already a dependency of the repository"]
    report["newly_connected"] = ["a lattice iteration over the sheet",
                                 "an ordered-dither selection rule",
                                 "an SVG writer and a PNG writer that draw only what they are given",
                                 "a coverage measurement by sample cells"]
    report["not_claimed"] = [
        "no new geometric predicate and no new primitive: the region relations are compositions of "
        "coll, cong, midp and diff with auxiliary points",
        "the reduction of the existential to one intersection point assumes the light is off the "
        "line of the occluder and that a ray parallel to it meets nothing",
        "a rational witness failing to exist does not mean a real one does not; the disk relation "
        "is decided by its reduced inequality, not by searching for rational U and V",
        "the coverage figures are sample-cell approximations at the stated resolution, not areas "
        "computed exactly",
        "the grey along a disk's edge in a PNG is the rasteriser's averaging, not a drawn tone",
        "nothing here is an artistic technique the system discovered; it is the connection from "
        "geometry to ink"]
    report["total_seconds"] = time.perf_counter()-started
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n",
                                      encoding="utf-8")
    print(json.dumps({"images": [{k: image.get(k) for k in
                                  ("image", "dots", "target_black_coverage", "local_coverage",
                                   "largest_band_error", "monotone_in_x", "dots_inside_the_shadow",
                                   "disks_pairwise_disjoint")}
                                 for image in report["images"]],
                      "ceiling": ceiling}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
