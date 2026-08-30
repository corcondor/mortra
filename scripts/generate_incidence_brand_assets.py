from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_os_prototype.generative_geometry_basis import (
    SemanticFigure,
    _build_composition,
    semantic_hash,
)


SOURCE_MANIFEST = ROOT / "artifacts" / "cross-domain-geometry-basis-20260830" / "manifest.json"
OUTPUT_DIR = ROOT / "brand" / "social"
PUBLIC_BRAND_DIR = ROOT / "public" / "brand"
EXPECTED_HASH = "e6523b41e3883cc66f665f09930d10ae27c980d30a7c79f175e73277e23017cb"

BACKGROUND = "#071A2C"
PRIMARY = "#DDF8FF"
SECONDARY = "#50B9D8"
MUTED = "#287A9B"
ACCENT = "#50E3C2"
TEXT_MUTED = "#8EADBC"


def _rgb(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.removeprefix("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
        alpha,
    )


def _load_source() -> tuple[SemanticFigure, dict[str, Any]]:
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    source = next(
        item for item in manifest["examples"] if item["semantic_hash"] == EXPECTED_HASH
    )
    figure = _build_composition(source["program_parameters"], source["figure_id"])
    actual_hash = semantic_hash(figure)
    if actual_hash != EXPECTED_HASH:
        raise RuntimeError(f"semantic figure drifted: {actual_hash} != {EXPECTED_HASH}")
    return figure, source


def _bounds(figure: SemanticFigure) -> tuple[float, float, float, float]:
    xs = [point[0] for point in figure.points.values()]
    ys = [point[1] for point in figure.points.values()]
    for circle in figure.circles:
        center = figure.points[circle.center_id]
        xs.extend((center[0] - circle.radius, center[0] + circle.radius))
        ys.extend((center[1] - circle.radius, center[1] + circle.radius))
    return min(xs), max(xs), min(ys), max(ys)


def _projector(
    figure: SemanticFigure,
    box: tuple[float, float, float, float],
    padding_ratio: float,
):
    x_min, x_max, y_min, y_max = _bounds(figure)
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    padding = min(width, height) * padding_ratio
    usable_width = max(width - 2 * padding, 1.0)
    usable_height = max(height - 2 * padding, 1.0)
    scale = min(usable_width / (x_max - x_min), usable_height / (y_max - y_min))
    offset_x = left + width / 2 - scale * (x_min + x_max) / 2
    offset_y = top + height / 2 + scale * (y_min + y_max) / 2

    def project(point: tuple[float, float]) -> tuple[float, float]:
        return offset_x + scale * point[0], offset_y - scale * point[1]

    return project, scale


def _segment_style(element_id: str) -> tuple[str, int, float]:
    if element_id.startswith("edge-K"):
        return ACCENT, 225, 1.22
    if element_id.startswith("edge-A"):
        return PRIMARY, 238, 1.38
    if element_id.startswith("edge-M"):
        return PRIMARY, 205, 1.12
    if element_id.startswith("edge-B"):
        return SECONDARY, 185, 1.04
    if element_id.startswith("radial"):
        return MUTED, 145, 0.84
    if element_id.startswith("spoke"):
        return SECONDARY, 150, 0.84
    return PRIMARY, 175, 1.0


def _render_mark(
    image: Image.Image,
    figure: SemanticFigure,
    box: tuple[int, int, int, int],
    *,
    padding_ratio: float = 0.07,
    supersample: int = 3,
) -> None:
    scaled_box = tuple(value * supersample for value in box)
    layer = Image.new(
        "RGBA",
        (image.width * supersample, image.height * supersample),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(layer)
    project, _ = _projector(figure, scaled_box, padding_ratio)
    base_width = max(1.0, min(box[2] - box[0], box[3] - box[1]) / 390.0)

    for circle in figure.circles:
        center = project(figure.points[circle.center_id])
        _, scale = _projector(figure, scaled_box, padding_ratio)
        radius = circle.radius * scale
        draw.ellipse(
            (
                center[0] - radius,
                center[1] - radius,
                center[0] + radius,
                center[1] + radius,
            ),
            outline=_rgb(SECONDARY, 142),
            width=max(1, round(base_width * 0.92 * supersample)),
        )

    for segment in figure.segments:
        color, alpha, weight = _segment_style(segment.element_id)
        draw.line(
            (
                project(figure.points[segment.start_id]),
                project(figure.points[segment.end_id]),
            ),
            fill=_rgb(color, alpha),
            width=max(1, round(base_width * weight * supersample)),
        )

    center = project((0.0, 0.0))
    center_radius = max(2.0, min(box[2] - box[0], box[3] - box[1]) * 0.014) * supersample
    draw.ellipse(
        (
            center[0] - center_radius,
            center[1] - center_radius,
            center[0] + center_radius,
            center[1] + center_radius,
        ),
        fill=_rgb(ACCENT),
        outline=_rgb(PRIMARY),
        width=max(1, 2 * supersample),
    )

    layer = layer.resize(image.size, Image.Resampling.LANCZOS)
    image.alpha_composite(layer)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ["segoeuib.ttf", "segoeui.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, format="PNG", optimize=True, compress_level=9)


def _avatar(figure: SemanticFigure, size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), _rgb(BACKGROUND))
    inset = round(size * 0.075)
    _render_mark(image, figure, (inset, inset, size - inset, size - inset), padding_ratio=0.03)
    return image


def _x_header(figure: SemanticFigure) -> Image.Image:
    image = Image.new("RGBA", (1500, 500), _rgb(BACKGROUND))
    draw = ImageDraw.Draw(image)
    _render_mark(image, figure, (900, -65, 1515, 550), padding_ratio=0.035)
    draw.text((286, 139), "MORTRA", font=_font(72, bold=True), fill=_rgb(PRIMARY))
    draw.text(
        (289, 235),
        "Finite primitives. Infinite mathematics.",
        font=_font(27),
        fill=_rgb(TEXT_MUTED),
    )
    draw.line((289, 299, 420, 299), fill=_rgb(ACCENT), width=3)
    draw.text((289, 328), "mortra.ai", font=_font(20), fill=_rgb(PRIMARY, 220))
    return image


def _share_card(figure: SemanticFigure, size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, _rgb(BACKGROUND))
    draw = ImageDraw.Draw(image)
    mark_size = round(min(height * 0.92, width * 0.48))
    _render_mark(
        image,
        figure,
        (width - mark_size - 24, (height - mark_size) // 2, width - 24, (height + mark_size) // 2),
        padding_ratio=0.035,
    )
    left = round(width * 0.065)
    title_size = round(height * 0.105)
    line_size = round(height * 0.058)
    meta_size = round(height * 0.031)
    draw.text((left, round(height * 0.25)), "MORTRA", font=_font(title_size, bold=True), fill=_rgb(PRIMARY))
    draw.text((left, round(height * 0.45)), "Finite primitives.", font=_font(line_size, bold=True), fill=_rgb(PRIMARY))
    draw.text((left, round(height * 0.54)), "Infinite mathematics.", font=_font(line_size, bold=True), fill=_rgb(PRIMARY))
    draw.line(
        (left, round(height * 0.69), left + round(width * 0.11), round(height * 0.69)),
        fill=_rgb(ACCENT),
        width=max(2, round(height * 0.004)),
    )
    draw.text((left, round(height * 0.75)), "mortra.ai", font=_font(meta_size), fill=_rgb(TEXT_MUTED))
    return image


def _circle_crop(image: Image.Image) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, image.width - 1, image.height - 1), fill=255)
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.paste(image, (0, 0), mask)
    return result


def _review_sheet(figure: SemanticFigure, avatar: Image.Image, header: Image.Image, github: Image.Image) -> Image.Image:
    image = Image.new("RGBA", (1800, 1240), _rgb("#E9EEF0"))
    draw = ImageDraw.Draw(image)
    draw.text((70, 44), "MORTRA / INCIDENCE WEAVE", font=_font(34, bold=True), fill=_rgb(BACKGROUND))
    draw.text(
        (70, 91),
        f"same semantic figure  {EXPECTED_HASH[:16]}...",
        font=_font(17),
        fill=_rgb(MUTED),
    )

    legacy_path = ROOT / "brand" / "icon-x-400.png"
    if legacy_path.exists():
        legacy = Image.open(legacy_path).convert("RGBA").resize((280, 280), Image.Resampling.LANCZOS)
        image.alpha_composite(legacy, (70, 160))
        draw.text((70, 456), "LEGACY PROOF BARS", font=_font(16, bold=True), fill=_rgb(BACKGROUND))

    avatar_280 = avatar.resize((280, 280), Image.Resampling.LANCZOS)
    image.alpha_composite(avatar_280, (420, 160))
    draw.text((420, 456), "NEW SQUARE", font=_font(16, bold=True), fill=_rgb(BACKGROUND))

    round_avatar = _circle_crop(avatar_280)
    image.alpha_composite(round_avatar, (770, 160))
    draw.text((770, 456), "X CIRCULAR CROP", font=_font(16, bold=True), fill=_rgb(BACKGROUND))

    chip_x = 1125
    for size in (128, 64, 48, 32):
        chip = _circle_crop(avatar.resize((size, size), Image.Resampling.LANCZOS))
        image.alpha_composite(chip, (chip_x, 260 - size // 2))
        draw.text((chip_x, 338), f"{size}px", font=_font(14), fill=_rgb(BACKGROUND))
        chip_x += size + 42

    header_preview = header.resize((1500, 500), Image.Resampling.LANCZOS)
    image.alpha_composite(header_preview, (150, 530))
    draw.text((150, 1044), "X HEADER 1500 x 500", font=_font(16, bold=True), fill=_rgb(BACKGROUND))

    github_preview = github.resize((640, 320), Image.Resampling.LANCZOS)
    image.alpha_composite(github_preview, (1030, 888))
    draw.text((1030, 1214), "GITHUB SOCIAL PREVIEW", font=_font(16, bold=True), fill=_rgb(BACKGROUND))
    return image


def _svg_mark(figure: SemanticFigure) -> str:
    project, scale = _projector(figure, (0, 0, 100, 100), 0.075)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">',
        f"<metadata>MORTRA Incidence weave {EXPECTED_HASH}</metadata>",
        f'<rect width="100" height="100" rx="8" fill="{BACKGROUND}"/>',
        '<g fill="none" stroke-linecap="round" stroke-linejoin="round">',
    ]
    for circle in figure.circles:
        center = project(figure.points[circle.center_id])
        radius = circle.radius * scale
        parts.append(
            f'<circle cx="{center[0]:.4f}" cy="{center[1]:.4f}" r="{radius:.4f}" '
            f'stroke="{SECONDARY}" stroke-opacity=".56" stroke-width=".52"/>'
        )
    for segment in figure.segments:
        color, alpha, weight = _segment_style(segment.element_id)
        start = project(figure.points[segment.start_id])
        end = project(figure.points[segment.end_id])
        parts.append(
            f'<line x1="{start[0]:.4f}" y1="{start[1]:.4f}" '
            f'x2="{end[0]:.4f}" y2="{end[1]:.4f}" stroke="{color}" '
            f'stroke-opacity="{alpha / 255:.3f}" stroke-width="{0.48 * weight:.3f}"/>'
        )
    center = project((0.0, 0.0))
    parts.extend(
        [
            "</g>",
            f'<circle cx="{center[0]:.4f}" cy="{center[1]:.4f}" r="1.55" fill="{ACCENT}" stroke="{PRIMARY}" stroke-width=".42"/>',
            "</svg>",
        ]
    )
    return "".join(parts)


def _asset_record(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    record: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    if path.suffix.lower() == ".png":
        with Image.open(path) as image:
            record["dimensions"] = list(image.size)
    return record


def main() -> None:
    figure, source = _load_source()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_BRAND_DIR.mkdir(parents=True, exist_ok=True)

    avatar_1024 = _avatar(figure, 1024)
    avatar_400 = avatar_1024.resize((400, 400), Image.Resampling.LANCZOS)
    header = _x_header(figure)
    github = _share_card(figure, (1280, 640))
    og = _share_card(figure, (1200, 630))

    targets = {
        OUTPUT_DIR / "mortra-avatar-1024.png": avatar_1024,
        OUTPUT_DIR / "mortra-avatar-x-400.png": avatar_400,
        OUTPUT_DIR / "mortra-x-header-1500x500.png": header,
        OUTPUT_DIR / "mortra-github-social-preview-1280x640.png": github,
        OUTPUT_DIR / "mortra-web-og-1200x630.png": og,
        ROOT / "app" / "opengraph-image.png": og,
        ROOT / "app" / "twitter-image.png": og,
    }
    for path, image in targets.items():
        _save_png(image, path)

    review = _review_sheet(figure, avatar_1024, header, github)
    _save_png(review, OUTPUT_DIR / "mortra-brand-review.png")

    svg = _svg_mark(figure)
    svg_targets: Iterable[Path] = (
        OUTPUT_DIR / "mortra-incidence-mark.svg",
        PUBLIC_BRAND_DIR / "mortra-incidence-mark.svg",
        ROOT / "public" / "favicon.svg",
        ROOT / "public" / "apple-icon.svg",
    )
    for path in svg_targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")

    generated_paths = list(targets) + [OUTPUT_DIR / "mortra-brand-review.png", *svg_targets]
    manifest = {
        "brand_system": "MORTRA Incidence weave",
        "source_pdf": "output/pdf/MORTRA-cross-domain-geometry-basis-20260830.pdf",
        "source_figure": source["title"],
        "figure_id": source["figure_id"],
        "semantic_hash": EXPECTED_HASH,
        "semantic_hash_verified": True,
        "operations_used": sorted(figure.operations_used),
        "rendering_note": "All assets use the same verified semantic figure; only render policy, crop, and typography vary.",
        "assets": [_asset_record(path) for path in generated_paths],
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    github_record = next(item for item in manifest["assets"] if "github-social-preview" in item["path"])
    if github_record["bytes"] >= 1_000_000:
        raise RuntimeError("GitHub social preview must be under 1 MB")

    print(json.dumps({
        "semantic_hash": EXPECTED_HASH,
        "assets": len(manifest["assets"]),
        "github_preview_bytes": github_record["bytes"],
    }, indent=2))


if __name__ == "__main__":
    main()
