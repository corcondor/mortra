"""Geometry Shadow Projection Module (Task S2).

Simulates the perspective shadow projection of 3D spatial planar objects
onto planar receiving surfaces (such as the floor z = 0) from point light sources.
Provides exact analytical vertex projection, polygon clipping/area calculation,
and visualization functions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np


@dataclass
class PointLight:
    name: str
    position: np.ndarray  # [x, y, z]
    intensity: float = 1.0


@dataclass
class PlanarPolygon:
    name: str
    vertices: np.ndarray  # (N, 3)


def project_polygon_to_floor(polygon: PlanarPolygon, light: PointLight, floor_z: float = 0.0) -> dict[str, Any]:
    """Calculate the exact analytical shadow of a planar 3D polygon on floor_z.
    
    Ray: R(t) = L + t * (P - L)
    Floor intersection: z_L + t * (z_P - z_L) = floor_z
    => t = (floor_z - z_L) / (z_P - z_L) = (z_L - floor_z) / (z_L - z_P)
    """
    L = np.asarray(light.position, dtype=np.float64)
    V = np.asarray(polygon.vertices, dtype=np.float64)
    
    # Check that light is above the polygon and polygon is above floor
    z_L = L[2]
    z_P = V[:, 2]
    
    if np.any(z_L <= z_P):
        raise ValueError("Light source must be strictly above all polygon vertices.")
    if np.any(z_P <= floor_z):
        raise ValueError("Polygon must be strictly above the floor surface.")
    
    # Scale factors for each vertex
    t = (z_L - floor_z) / (z_L - z_P)  # Shape (N,)
    
    # Projected coordinates on floor
    # P' = L + t * (P - L)
    P_proj = L + t[:, np.newaxis] * (V - L)
    P_proj[:, 2] = floor_z  # Ensure exact floor_z
    
    # Calculate polygon area using Shoelace formula on the (x, y) coordinates
    x = P_proj[:, 0]
    y = P_proj[:, 1]
    # Shoelace formula: 0.5 * |sum(x_i * y_{i+1} - x_{i+1} * y_i)|
    area = 0.5 * np.abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    
    return {
        "light_name": light.name,
        "light_pos": L.tolist(),
        "polygon_name": polygon.name,
        "original_vertices": V.tolist(),
        "shadow_vertices": P_proj.tolist(),
        "floor_z": floor_z,
        "t_scale": float(np.mean(t)),
        "shadow_area": float(area),
    }


def compute_two_light_shadow_system(
    light1: PointLight,
    light2: PointLight,
    plate: PlanarPolygon,
    floor_z: float = 0.0
) -> dict[str, Any]:
    """Compute shadow system under two lights, including individual shadows and overlap (umbra)."""
    s1 = project_polygon_to_floor(plate, light1, floor_z)
    s2 = project_polygon_to_floor(plate, light2, floor_z)
    
    # Compute bounding boxes
    v1 = np.array(s1["shadow_vertices"])
    v2 = np.array(s2["shadow_vertices"])
    
    bbox1 = [float(np.min(v1[:, 0])), float(np.max(v1[:, 0])), float(np.min(v1[:, 1])), float(np.max(v1[:, 1]))]
    bbox2 = [float(np.min(v2[:, 0])), float(np.max(v2[:, 0])), float(np.min(v2[:, 1])), float(np.max(v2[:, 1]))]
    
    # Overlap of axis-aligned rectangular shadows (if applicable)
    overlap_x_min = max(bbox1[0], bbox2[0])
    overlap_x_max = min(bbox1[1], bbox2[1])
    overlap_y_min = max(bbox1[2], bbox2[2])
    overlap_y_max = min(bbox1[3], bbox2[3])
    
    overlap_area = 0.0
    if overlap_x_max > overlap_x_min and overlap_y_max > overlap_y_min:
        overlap_area = (overlap_x_max - overlap_x_min) * (overlap_y_max - overlap_y_min)
        
    return {
        "shadow_light_1": s1,
        "shadow_light_2": s2,
        "bbox_1": bbox1,
        "bbox_2": bbox2,
        "overlap_area": float(overlap_area),
        "total_shadow_area": float(s1["shadow_area"] + s2["shadow_area"] - overlap_area),
    }
