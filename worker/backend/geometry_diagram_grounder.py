"""Deterministic diagram-label grounding without a language model.

This module does not try to solve geometry from pixels.  It performs the
smaller, testable operation needed before symbolic reasoning: detect expected
point labels and bind each label to a nearby line endpoint/intersection.  The
result is a typed observation with confidence and explicit unresolved labels.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class GroundedLabel:
    label: str
    label_position: tuple[float, float]
    point_position: tuple[float, float] | None
    confidence: float
    distance: float | None


@dataclass
class DiagramGrounding:
    status: str
    labels: list[GroundedLabel]
    line_count: int
    circle_count: int
    candidate_point_count: int
    unresolved_labels: list[str]
    uses_language_model: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["labels"] = [asdict(item) for item in self.labels]
        return value


def ground_diagram(image_source: str, expected_labels: list[str]) -> DiagramGrounding:
    image = _load_image(image_source)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detections: dict[str, tuple[tuple[float, float] | None, float]] = {}
    for label in dict.fromkeys(value.upper() for value in expected_labels if len(value) == 1):
        detections[label] = _detect_label(gray, label)
    geometry_gray = gray.copy()
    for position, confidence in detections.values():
        if position is not None and confidence >= 0.58:
            x, y = (int(round(value)) for value in position)
            cv2.rectangle(geometry_gray, (x - 12, y - 10), (x + 12, y + 10), 255, -1)
    lines = _detect_lines(geometry_gray)
    circles = _detect_circles(gray)
    candidates = _candidate_points(lines, gray.shape)
    labels: list[GroundedLabel] = []
    unresolved: list[str] = []
    for label, (position, confidence) in detections.items():
        if position is None or confidence < 0.58:
            unresolved.append(label)
            continue
        point, distance = _nearest_candidate(position, candidates, max_distance=max(gray.shape) * 0.16)
        if point is None:
            unresolved.append(label)
        labels.append(GroundedLabel(label, position, point, confidence, distance))
    status = "grounded" if not unresolved and labels else "partial" if labels else "unresolved"
    return DiagramGrounding(status, labels, len(lines), len(circles), len(candidates), unresolved)


def _load_image(source: str) -> np.ndarray:
    if source.startswith("data:image/"):
        payload = source.split(",", 1)[1]
        data = np.frombuffer(base64.b64decode(payload), dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    else:
        image = cv2.imread(str(Path(source).expanduser().resolve()), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("diagram image could not be decoded")
    return image


def _detect_lines(gray: np.ndarray) -> list[tuple[float, float, float, float]]:
    edges = cv2.Canny(gray, 60, 160)
    raw = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=35,
        minLineLength=max(20, min(gray.shape) // 8), maxLineGap=8,
    )
    if raw is None:
        return []
    return [tuple(float(value) for value in item[0]) for item in raw]


def _detect_circles(gray: np.ndarray) -> list[tuple[float, float, float]]:
    blurred = cv2.medianBlur(gray, 5)
    raw = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.2,
        minDist=max(15, min(gray.shape) // 8), param1=100, param2=30,
        minRadius=max(5, min(gray.shape) // 20), maxRadius=min(gray.shape) // 2,
    )
    if raw is None:
        return []
    return [tuple(float(value) for value in item) for item in raw[0]]


def _candidate_points(
    lines: list[tuple[float, float, float, float]],
    shape: tuple[int, ...],
) -> list[tuple[float, float]]:
    candidates = [(line[0], line[1]) for line in lines] + [(line[2], line[3]) for line in lines]
    for index, first in enumerate(lines):
        for second in lines[index + 1:]:
            point = _line_intersection(first, second)
            if point and -3 <= point[0] <= shape[1] + 3 and -3 <= point[1] <= shape[0] + 3:
                candidates.append(point)
    clustered: list[tuple[float, float]] = []
    for point in candidates:
        match = next((i for i, value in enumerate(clustered) if math.dist(point, value) <= 9), None)
        if match is None:
            clustered.append(point)
        else:
            old = clustered[match]
            clustered[match] = ((old[0] + point[0]) / 2, (old[1] + point[1]) / 2)
    return clustered


def _line_intersection(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> tuple[float, float] | None:
    x1, y1, x2, y2 = first
    x3, y3, x4, y4 = second
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denominator) < 1e-8:
        return None
    cross1, cross2 = x1 * y2 - y1 * x2, x3 * y4 - y3 * x4
    x = (cross1 * (x3 - x4) - (x1 - x2) * cross2) / denominator
    y = (cross1 * (y3 - y4) - (y1 - y2) * cross2) / denominator
    return x, y


def _detect_label(gray: np.ndarray, label: str) -> tuple[tuple[float, float] | None, float]:
    best_position: tuple[float, float] | None = None
    best_score = -1.0
    inverted = 255 - gray
    for scale in (0.45, 0.55, 0.65, 0.75, 0.9):
        size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        template = np.zeros((size[1] + baseline + 8, size[0] + 8), dtype=np.uint8)
        cv2.putText(template, label, (4, size[1] + 3), cv2.FONT_HERSHEY_SIMPLEX, scale, 255, 1, cv2.LINE_AA)
        if template.shape[0] >= inverted.shape[0] or template.shape[1] >= inverted.shape[1]:
            continue
        scores = cv2.matchTemplate(inverted, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(scores)
        if score > best_score:
            best_score = float(score)
            best_position = (location[0] + template.shape[1] / 2, location[1] + template.shape[0] / 2)
    return best_position, best_score


def _nearest_candidate(
    label_position: tuple[float, float],
    candidates: list[tuple[float, float]],
    *,
    max_distance: float,
) -> tuple[tuple[float, float] | None, float | None]:
    if not candidates:
        return None, None
    point = min(candidates, key=lambda value: math.dist(label_position, value))
    distance = math.dist(label_position, point)
    return (point, distance) if distance <= max_distance else (None, distance)


def _self_test() -> dict[str, Any]:
    image = np.full((300, 360, 3), 255, dtype=np.uint8)
    vertices = {"A": (80, 235), "B": (290, 235), "C": (180, 55)}
    cv2.line(image, vertices["A"], vertices["B"], (0, 0, 0), 2)
    cv2.line(image, vertices["B"], vertices["C"], (0, 0, 0), 2)
    cv2.line(image, vertices["C"], vertices["A"], (0, 0, 0), 2)
    offsets = {"A": (-23, 25), "B": (8, 25), "C": (-8, -10)}
    for label, point in vertices.items():
        offset = offsets[label]
        cv2.putText(image, label, (point[0] + offset[0], point[1] + offset[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 1, cv2.LINE_AA)
    rng = np.random.default_rng(20260810)
    noise = rng.normal(0, 3.0, image.shape).astype(np.int16)
    noisy = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    variants = {
        "base": image,
        "noisy": noisy,
        "resized": cv2.resize(image, None, fx=1.2, fy=1.2, interpolation=cv2.INTER_CUBIC),
    }
    reports: dict[str, dict[str, Any]] = {}
    for name, variant in variants.items():
        ok, encoded = cv2.imencode(".png", variant)
        if not ok:
            raise RuntimeError("self-test image encoding failed")
        source = "data:image/png;base64," + base64.b64encode(encoded).decode("ascii")
        reports[name] = ground_diagram(source, ["A", "B", "C"]).to_dict()
    return {
        "passed": all(report["status"] == "grounded" for report in reports.values()),
        "grounding": reports["base"],
        "perturbations": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(_self_test(), ensure_ascii=False))
        return 0
    payload = json.load(__import__("sys").stdin)
    result = ground_diagram(str(payload["image"]), list(payload.get("expected_labels", [])))
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
