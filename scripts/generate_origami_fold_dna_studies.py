from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_os_prototype.origami_fold_dna import (  # noqa: E402
    FoldProgram,
    FoldState,
    build_radial_panel_tree,
    execute_fold_program,
    make_fold_programs,
    state_to_spatial_figure,
    validate_fold_state,
)
from math_os_prototype.spatial_visual_basis import new_morphism_count, semantic_hash  # noqa: E402
from scripts.generate_spatial_rotation_studies import (  # noqa: E402
    Camera,
    StudySpec,
    render_spatial_figure,
)


OUTPUT_DIR = ROOT / "brand" / "studies" / "origami-fold-dna-20260904"


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flat_projection(state: FoldState, size: int):
    xs = [point[0] for point in state.points.values()]
    ys = [point[1] for point in state.points.values()]
    padding = 0.08 * size
    scale = min(
        (size - 2 * padding) / max(max(xs) - min(xs), 1e-9),
        (size - 2 * padding) / max(max(ys) - min(ys), 1e-9),
    )
    center_x = (min(xs) + max(xs)) / 2.0
    center_y = (min(ys) + max(ys)) / 2.0

    def project(point_id: str) -> tuple[float, float]:
        x, y, _ = state.points[point_id]
        return size / 2.0 + scale * (x - center_x), size / 2.0 - scale * (y - center_y)

    return project


def render_crease_pattern(state: FoldState, program: FoldProgram, size: int) -> Image.Image:
    canvas = Image.new("RGB", (size, size), "#F7F3EC")
    draw = ImageDraw.Draw(canvas, "RGBA")
    project = _flat_projection(state, size)
    pigments = ("#9CCDE4", "#F4A8B8", "#F4D06F", "#8FD0BD", "#9C8FD1", "#F19A67")

    for panel in state.panels.values():
        polygon = [project(item) for item in panel.vertex_ids]
        color = pigments[panel.pigment_index % len(pigments)]
        rgb = tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))
        draw.polygon(polygon, fill=(*rgb, 42), outline=(41, 59, 72, 92), width=max(1, size // 720))

    gene_by_hinge = {gene.hinge_id: gene for gene in program.genes}
    for hinge in state.hinges.values():
        gene = gene_by_hinge[hinge.hinge_id]
        color = (42, 103, 168, 220) if gene.direction == "V" else (198, 61, 92, 220)
        draw.line(
            (project(hinge.parent_edge[0]), project(hinge.parent_edge[1])),
            fill=color,
            width=max(2, size // 360),
        )

    legend_y = size - 44
    draw.line((28, legend_y, 74, legend_y), fill=(198, 61, 92, 220), width=4)
    draw.text((82, legend_y - 13), "M", font=_font(max(14, size // 55), bold=True), fill="#8F2944")
    draw.line((132, legend_y, 178, legend_y), fill=(42, 103, 168, 220), width=4)
    draw.text((186, legend_y - 13), "V", font=_font(max(14, size // 55), bold=True), fill="#245D99")
    return canvas


def _render_spec(program: FoldProgram, frame: int = 0) -> StudySpec:
    palettes = {"21": "spectrum-glass", "22": "sapphire-amber", "23": "prism-coral"}
    cameras = {
        "21": Camera(38, 31, -5, 10.8, 2.0),
        "22": Camera(122, 27, 4, 10.8, 2.0),
        "23": Camera(68, 35, -3, 10.8, 2.0),
    }
    return StudySpec(
        program.program_id,
        program.title,
        "origami_fold_dna",
        palettes[program.program_id],
        cameras[program.program_id],
        False,
        False,
        False,
        "watercolor",
        True,
    )


def _make_step_strip(
    states: tuple[FoldState, ...],
    program: FoldProgram,
    output: Path,
) -> None:
    indices = (0, 4, 8, 12, 16, 20, len(states) - 1)
    tile = 380
    strip = Image.new("RGB", (tile * len(indices), tile + 66), "#E8E4DD")
    draw = ImageDraw.Draw(strip)
    for column, state_index in enumerate(indices):
        figure = state_to_spatial_figure(states[state_index], f"origami-step-{state_index}", program)
        image = render_spatial_figure(figure, _render_spec(program, state_index), size=tile, seed_offset=state_index)
        strip.paste(image, (column * tile, 0))
        label = "flat" if state_index == 0 else f"fold {state_index:02d}"
        draw.text((column * tile + 18, tile + 16), label, font=_font(20, bold=True), fill="#253D4C")
    strip.save(output, optimize=True)


def _make_animation(
    states: tuple[FoldState, ...],
    program: FoldProgram,
    output: Path,
) -> None:
    frames: list[Image.Image] = []
    for state_index, state in enumerate(states):
        figure = state_to_spatial_figure(state, f"origami-frame-{state_index}", program)
        frames.append(
            render_spatial_figure(
                figure,
                _render_spec(program, state_index),
                size=480,
                seed_offset=state_index,
            )
        )
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=180,
        loop=0,
        disposal=2,
    )


def _make_review(records: list[dict[str, object]], flat_path: Path, output: Path) -> None:
    width, margin, gap = 2000, 48, 30
    columns = 4
    tile = (width - 2 * margin - gap * (columns - 1)) // columns
    header, caption = 174, 112
    sheet = Image.new("RGB", (width, header + tile + caption + margin), "#E9E5DE")
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 34), "MORTRA / FOLD DNA", font=_font(44, bold=True), fill="#173247")
    draw.text(
        (margin, 98),
        "one crease graph / three fold sequences / every gene compiled to existing Rotate3",
        font=_font(24),
        fill="#5B7380",
    )
    items = [("20", "Mountain / valley program", flat_path, "24 fold genes")]
    items.extend((str(item["program_id"]), str(item["title"]), Path(str(item["path"])), str(item["dna_summary"])) for item in records)
    for index, (study_id, title, path, detail) in enumerate(items):
        x = margin + index * (tile + gap)
        y = header
        image = Image.open(path).convert("RGB").resize((tile, tile), Image.Resampling.LANCZOS)
        sheet.paste(image, (x, y))
        draw.text((x, y + tile + 12), f"{study_id}  {title}", font=_font(20, bold=True), fill="#173247")
        draw.text((x, y + tile + 44), detail, font=_font(16), fill="#627782")
        if index > 0:
            record = records[index - 1]
            draw.text(
                (x, y + tile + 70),
                f"rigidity {float(record['rigidity_residual']):.1e} / hinge {float(record['hinge_residual']):.1e}",
                font=_font(15),
                fill="#627782",
            )
    sheet.save(output, optimize=True)


def _make_generation_strip(output: Path) -> list[str]:
    tile, gap, header = 430, 24, 92
    images: list[Image.Image] = []
    hashes: list[str] = []
    for depth in range(1, 5):
        state = build_radial_panel_tree(depth=depth)
        program = make_fold_programs(depth=depth)[0]
        image = render_crease_pattern(state, program, tile)
        images.append(image)
        hashes.append(hashlib.sha256(image.tobytes()).hexdigest())
    strip = Image.new("RGB", (4 * tile + 3 * gap, header + tile + 54), "#E9E5DE")
    draw = ImageDraw.Draw(strip)
    draw.text((24, 24), "ONE REWRITE RULE / FOUR GENERATIONS", font=_font(30, bold=True), fill="#173247")
    for index, image in enumerate(images):
        x = index * (tile + gap)
        strip.paste(image, (x, header))
        draw.text((x + 16, header + tile + 14), f"generation {index + 1}", font=_font(19, bold=True), fill="#304B5A")
    strip.save(output, optimize=True)
    return hashes


def generate(
    output_dir: Path = OUTPUT_DIR,
    *,
    size: int = 1000,
    include_animation: bool = True,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    initial = build_radial_panel_tree()
    programs = make_fold_programs()

    flat_path = output_dir / "origami-fold-dna-crease-pattern.png"
    render_crease_pattern(initial, programs[0], size).save(flat_path, optimize=True)

    records: list[dict[str, object]] = []
    state_sequences: dict[str, tuple[FoldState, ...]] = {}
    for program in programs:
        states = execute_fold_program(initial, program)
        state_sequences[program.program_id] = states
        final_state = states[-1]
        validation = validate_fold_state(initial, final_state)
        figure = state_to_spatial_figure(final_state, f"origami-{program.program_id}", program)
        path = output_dir / f"origami-fold-dna-{program.program_id}.png"
        render_spatial_figure(figure, _render_spec(program), size=size).save(path, optimize=True)
        records.append(
            {
                "program_id": program.program_id,
                "title": program.title,
                "path": str(path),
                "image_sha256": _sha256(path),
                "semantic_sha256": semantic_hash(figure),
                "gene_count": len(program.genes),
                "dna": program.dna,
                "dna_summary": f"{len(program.genes)} genes / {program.dna[:31]}...",
                "compiled_rotate_steps": sum(len(item.moved_point_ids) for item in final_state.applied),
                "construction_steps": len(figure.construction_trace),
                "operations": sorted(figure.operations_used),
                "new_morphism_count": new_morphism_count(figure),
                "rigidity_residual": validation["panel_rigidity_max_residual"],
                "planarity_residual": validation["panel_planarity_max_residual"],
                "hinge_residual": validation["hinge_coincidence_max_residual"],
                "hinge_graph_is_tree": validation["hinge_graph_is_tree"],
                "validation_passed": validation["passed"],
            }
        )

    strip_path = output_dir / "origami-fold-dna-step-strip.png"
    _make_step_strip(state_sequences["21"], programs[0], strip_path)
    generation_path = output_dir / "origami-fold-dna-generations.png"
    generation_hashes = _make_generation_strip(generation_path)
    animation_path = output_dir / "origami-fold-dna-sequence.gif"
    if include_animation:
        _make_animation(state_sequences["21"], programs[0], animation_path)

    review_path = output_dir / "origami-fold-dna-review.png"
    _make_review(records, flat_path, review_path)
    checks = {
        "one_crease_graph_three_distinct_folded_states": len({item["semantic_sha256"] for item in records}) == 3,
        "all_fold_genes_compile_to_existing_rotate3": all(
            item["new_morphism_count"] == 0 and "Rotate3" in item["operations"] for item in records
        ),
        "all_panel_rigidity_invariants_hold": all(item["validation_passed"] for item in records),
        "all_sequences_have_twenty_four_genes": all(item["gene_count"] == 24 for item in records),
        "all_sequences_expand_beyond_one_hundred_rotations": all(item["compiled_rotate_steps"] > 100 for item in records),
        "all_images_are_distinct": len({item["image_sha256"] for item in records}) == 3,
        "one_rewrite_rule_produces_four_distinct_generations": len(set(generation_hashes)) == 4,
    }
    manifest = {
        "schema": "mortra.origami-fold-dna.v1",
        "generated_at": "2026-09-04",
        "source_model": {
            "panels": len(initial.panels),
            "hinges": len(initial.hinges),
            "hinge_graph": "tree",
            "geometric_operations_added": 0,
        },
        "records": records,
        "checks": checks,
        "passed": all(checks.values()),
        "crease_pattern": str(flat_path),
        "step_strip": str(strip_path),
        "generations": str(generation_path),
        "animation": str(animation_path) if include_animation else None,
        "review_path": str(review_path),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    manifest = generate()
    print(
        json.dumps(
            {
                "output": str(OUTPUT_DIR),
                "passed": manifest["passed"],
                "checks": manifest["checks"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
