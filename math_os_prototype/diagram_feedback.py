"""Raster feedback for exact geometric charts.

Pixels are never accepted as a proof of the mathematical claim.  They are an
independent observation channel used to detect blank, clipped, asymmetric, or
mis-scaled diagrams before a diagram is shown to a user.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


INK = (20, 184, 166)
BACKGROUND = (250, 250, 249)


@dataclass(frozen=True)
class DiagramObservationCertificate:
    object_kind: str
    nonblank: bool
    ink_bbox: tuple[int, int, int, int] | None
    horizontal_symmetry: float
    vertical_symmetry: float
    radius_error_pixels: float
    clipped: bool
    repair_attempts: int
    verified: bool
    image_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def observe_circle_witness(
    witness: dict[str, Any],
    *,
    image_path: str | Path | None = None,
    size: int = 384,
    max_repairs: int = 2,
) -> dict[str, Any]:
    center = tuple(float(item) for item in witness["center"])
    radius = float(witness["radius_squared"]) ** 0.5
    if radius <= 0:
        raise ValueError("circle witness has a non-positive radius")

    margin = 1.04
    final_image: Image.Image | None = None
    final_certificate: DiagramObservationCertificate | None = None
    for attempt in range(max_repairs + 1):
        image, expected_radius = render_circle(center, radius, size=size, margin=margin)
        certificate = inspect_circle_pixels(image, expected_radius, repair_attempts=attempt)
        final_image, final_certificate = image, certificate
        if certificate.verified:
            break
        margin *= 1.35

    assert final_image is not None and final_certificate is not None
    path_text = None
    if image_path is not None:
        path = Path(image_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        final_image.save(path)
        path_text = str(path.resolve())
    return {**final_certificate.to_dict(), "image_path": path_text}


def render_circle(
    center: tuple[float, float],
    radius: float,
    *,
    size: int,
    margin: float,
) -> tuple[Image.Image, float]:
    image = Image.new("RGB", (size, size), BACKGROUND)
    draw = ImageDraw.Draw(image)
    world_radius = radius * margin
    scale = (size - 1) / (2 * world_radius)
    cx = (size - 1) / 2
    cy = (size - 1) / 2
    pixel_radius = radius * scale
    box = (cx - pixel_radius, cy - pixel_radius, cx + pixel_radius, cy + pixel_radius)
    draw.ellipse(box, outline=INK, width=max(2, size // 128))
    draw.line((cx - 5, cy, cx + 5, cy), fill=(31, 41, 55), width=1)
    draw.line((cx, cy - 5, cx, cy + 5), fill=(31, 41, 55), width=1)
    return image, pixel_radius


def inspect_circle_pixels(
    image: Image.Image,
    expected_radius: float,
    *,
    repair_attempts: int,
) -> DiagramObservationCertificate:
    width, height = image.size
    ink = {
        (x, y)
        for y in range(height)
        for x in range(width)
        if image.getpixel((x, y)) == INK
    }
    if not ink:
        return DiagramObservationCertificate("circle", False, None, 0.0, 0.0, float("inf"), False, repair_attempts, False)
    xs = [point[0] for point in ink]
    ys = [point[1] for point in ink]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    reflected_h = {(width - 1 - x, y) for x, y in ink}
    reflected_v = {(x, height - 1 - y) for x, y in ink}
    horizontal = tolerant_overlap(ink, reflected_h, tolerance=1)
    vertical = tolerant_overlap(ink, reflected_v, tolerance=1)
    observed_radius = ((bbox[2] - bbox[0]) + (bbox[3] - bbox[1])) / 4
    radius_error = abs(observed_radius - expected_radius)
    clipped = bbox[0] <= 0 or bbox[1] <= 0 or bbox[2] >= width - 1 or bbox[3] >= height - 1
    verified = not clipped and horizontal >= 0.96 and vertical >= 0.96 and radius_error <= 2.5
    return DiagramObservationCertificate(
        object_kind="circle",
        nonblank=True,
        ink_bbox=bbox,
        horizontal_symmetry=horizontal,
        vertical_symmetry=vertical,
        radius_error_pixels=radius_error,
        clipped=clipped,
        repair_attempts=repair_attempts,
        verified=verified,
    )


def tolerant_overlap(reference: set[tuple[int, int]], reflected: set[tuple[int, int]], *, tolerance: int) -> float:
    matched = 0
    for x, y in reflected:
        if any((x + dx, y + dy) in reference for dx in range(-tolerance, tolerance + 1) for dy in range(-tolerance, tolerance + 1)):
            matched += 1
    return matched / len(reflected) if reflected else 0.0
