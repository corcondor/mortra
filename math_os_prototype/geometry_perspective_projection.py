"""Geometric 3D perspective projection and wireframe generation.

Provides central perspective projection from a camera center through 3D vertices
onto a specified image plane, generating 3D ray lines and 2D image coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence


@dataclass(frozen=True)
class ProjectedVertex:
    original_3d: tuple[Fraction, Fraction, Fraction]
    projected_2d: tuple[Fraction, Fraction]
    ray_parameter_t: Fraction


@dataclass(frozen=True)
class PerspectiveProjectionResult:
    camera_center: tuple[Fraction, Fraction, Fraction]
    image_plane_z: Fraction
    vertices_3d: list[tuple[Fraction, Fraction, Fraction]]
    edges: list[tuple[int, int]]
    projected_vertices: list[ProjectedVertex]
    projected_edges: list[tuple[tuple[Fraction, Fraction], tuple[Fraction, Fraction]]]


def project_central_perspective(
    vertices: Sequence[tuple[int | float | Fraction, int | float | Fraction, int | float | Fraction]],
    edges: Sequence[tuple[int, int]],
    camera_center: tuple[int | float | Fraction, int | float | Fraction, int | float | Fraction] = (0, 0, 0),
    image_plane_z: int | float | Fraction = 1,
) -> PerspectiveProjectionResult:
    """Project 3D vertices and edges onto image plane z = image_plane_z from camera_center.

    For camera at (0,0,0) and image plane at z = z_img:
    Ray equation: P(t) = C + t * (V - C) = t * V.
    Intersection with z = z_img:
    t * V_z = z_img => t = z_img / V_z.
    Projected coordinates on the image plane:
    x' = t * V_x = (z_img / V_z) * V_x
    y' = t * V_y = (z_img / V_z) * V_y
    """
    c_x, c_y, c_z = Fraction(camera_center[0]), Fraction(camera_center[1]), Fraction(camera_center[2])
    z_img = Fraction(image_plane_z)

    v3d_list = [
        (Fraction(v[0]), Fraction(v[1]), Fraction(v[2]))
        for v in vertices
    ]

    projected_verts: list[ProjectedVertex] = []
    for v in v3d_list:
        vx, vy, vz = v
        dz = vz - c_z
        if dz == 0:
            raise ValueError(f"Vertex {v} lies on camera plane z = {c_z}")
        t = (z_img - c_z) / dz
        px = c_x + t * (vx - c_x)
        py = c_y + t * (vy - c_y)

        projected_verts.append(
            ProjectedVertex(
                original_3d=v,
                projected_2d=(px, py),
                ray_parameter_t=t,
            )
        )

    projected_edges_coords = []
    for i, j in edges:
        p1 = projected_verts[i].projected_2d
        p2 = projected_verts[j].projected_2d
        projected_edges_coords.append((p1, p2))

    return PerspectiveProjectionResult(
        camera_center=(c_x, c_y, c_z),
        image_plane_z=z_img,
        vertices_3d=v3d_list,
        edges=list(edges),
        projected_vertices=projected_verts,
        projected_edges=projected_edges_coords,
    )


def create_cube_geometry(
    x_range: tuple[int | float | Fraction, int | float | Fraction] = (-1, 1),
    y_range: tuple[int | float | Fraction, int | float | Fraction] = (-1, 1),
    z_range: tuple[int | float | Fraction, int | float | Fraction] = (4, 6),
) -> tuple[list[tuple[Fraction, Fraction, Fraction]], list[tuple[int, int]]]:
    """Generate 8 vertices and 12 edges of an axis-aligned 3D cube."""
    x0, x1 = Fraction(x_range[0]), Fraction(x_range[1])
    y0, y1 = Fraction(y_range[0]), Fraction(y_range[1])
    z0, z1 = Fraction(z_range[0]), Fraction(z_range[1])

    # 8 vertices: near face (z0), far face (z1)
    # Order:
    # 0: (x0, y0, z0), 1: (x1, y0, z0), 2: (x1, y1, z0), 3: (x0, y1, z0)
    # 4: (x0, y0, z1), 5: (x1, y0, z1), 6: (x1, y1, z1), 7: (x0, y1, z1)
    vertices = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]

    edges = [
        # Near face
        (0, 1), (1, 2), (2, 3), (3, 0),
        # Far face
        (4, 5), (5, 6), (6, 7), (7, 4),
        # Connecting edges
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]

    return vertices, edges
