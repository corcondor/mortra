"""Stippled Diffuse Sphere Rendering Module (Task R1).

Simulates 3D ray-casting of a diffuse sphere with floor shadow, lit by two point lights:
- Sphere: x^2 + y^2 + (z - 1)^2 = 1 (Center (0, 0, 1), Radius 1).
- Floor: Plane z = 0.
- Camera: Eye (4, -6, 4), Target (0, 0, 1), Up (0, 0, 1), FOV 40 deg.
- Lighting: L1 = (-3, -4, 8), L2 = (3, -4, 8).
- Shading: B = 0.1 + 0.9 * (V1 * max(0, n.l1) + V2 * max(0, n.l2)) / 2.
- Stippling: High-contrast point-based representation with dot density representing shading.
"""
from __future__ import annotations

from typing import Any
import numpy as np


def ray_sphere_intersect(ray_origin: np.ndarray, ray_dir: np.ndarray, sphere_center: np.ndarray, sphere_radius: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized ray-sphere intersection.
    
    ray_origin: (..., 3)
    ray_dir: (..., 3) normalized
    Returns: (hit_mask, t_vals)
    """
    oc = ray_origin - sphere_center
    a = np.sum(ray_dir * ray_dir, axis=-1)
    b = 2.0 * np.sum(oc * ray_dir, axis=-1)
    c = np.sum(oc * oc, axis=-1) - sphere_radius**2
    
    discriminant = b**2 - 4 * a * c
    hit = discriminant >= 0
    
    t = np.full(discriminant.shape, np.inf)
    valid_disc = np.maximum(0.0, discriminant)
    t1 = (-b - np.sqrt(valid_disc)) / (2.0 * a)
    t2 = (-b + np.sqrt(valid_disc)) / (2.0 * a)
    
    # Take smallest positive t
    t_cand = np.where((t1 > 1e-4) & hit, t1, np.where((t2 > 1e-4) & hit, t2, np.inf))
    hit_mask = (t_cand < np.inf) & hit
    return hit_mask, t_cand


def ray_plane_intersect(ray_origin: np.ndarray, ray_dir: np.ndarray, plane_z: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized ray-plane intersection with z = plane_z."""
    dz = ray_dir[..., 2]
    hit = np.abs(dz) > 1e-6
    t = (plane_z - ray_origin[..., 2]) / np.where(hit, dz, 1.0)
    hit_mask = hit & (t > 1e-4)
    t_vals = np.where(hit_mask, t, np.inf)
    return hit_mask, t_vals


def render_scene(
    width: int = 400,
    height: int = 400,
    camera_pos: np.ndarray = np.array([4.0, -6.0, 4.0]),
    camera_target: np.ndarray = np.array([0.0, 0.0, 1.0]),
    camera_up: np.ndarray = np.array([0.0, 0.0, 1.0]),
    fov_deg: float = 40.0,
    lights: list[np.ndarray] = [np.array([-3.0, -4.0, 8.0]), np.array([3.0, -4.0, 8.0])],
) -> dict[str, Any]:
    """Ray-cast the scene and compute analytical diffuse shading with shadows."""
    # Camera coordinate frame
    forward = camera_target - camera_pos
    forward = forward / np.linalg.norm(forward)
    
    right = np.cross(forward, camera_up)
    right = right / np.linalg.norm(right)
    
    up = np.cross(right, forward)
    up = up / np.linalg.norm(up)
    
    aspect = width / height
    fov_rad = np.radians(fov_deg)
    half_h = np.tan(fov_rad / 2.0)
    half_w = aspect * half_h
    
    # Pixel grid
    u = np.linspace(-half_w, half_w, width)
    v = np.linspace(half_h, -half_h, height)
    U, V = np.meshgrid(u, v)
    
    # Ray directions
    ray_dirs = forward[np.newaxis, np.newaxis, :] + U[..., np.newaxis] * right + V[..., np.newaxis] * up
    ray_dirs = ray_dirs / np.linalg.norm(ray_dirs, axis=-1, keepdims=True)
    
    ray_orig = np.broadcast_to(camera_pos, ray_dirs.shape)
    
    # Intersections
    sphere_center = np.array([0.0, 0.0, 1.0])
    hit_sph, t_sph = ray_sphere_intersect(ray_orig, ray_dirs, sphere_center, 1.0)
    hit_flr, t_flr = ray_plane_intersect(ray_orig, ray_dirs, 0.0)
    
    # Floor boundary clipping for aesthetic ground plane
    P_flr = ray_orig + t_flr[..., np.newaxis] * ray_dirs
    flr_bound = (np.abs(P_flr[..., 0]) <= 5.0) & (np.abs(P_flr[..., 1]) <= 5.0)
    hit_flr = hit_flr & flr_bound
    t_flr = np.where(hit_flr, t_flr, np.inf)
    
    # Depth buffer
    hit_anything = (t_sph < np.inf) | (t_flr < np.inf)
    is_sphere = (t_sph <= t_flr) & hit_sph
    is_floor = (t_flr < t_sph) & hit_flr
    
    t_final = np.where(is_sphere, t_sph, np.where(is_floor, t_flr, np.inf))
    P_hit = ray_orig + t_final[..., np.newaxis] * ray_dirs
    
    # Surface normals
    normals = np.zeros_like(P_hit)
    normals[is_sphere] = (P_hit[is_sphere] - sphere_center) / 1.0  # Normalized sphere normal
    normals[is_floor] = np.array([0.0, 0.0, 1.0])  # Upward floor normal
    
    # Shading computation
    brightness = np.zeros((height, width), dtype=np.float64)
    ambient = 0.1
    diffuse_weight = 0.9
    
    # For each light source
    light_contributions = np.zeros((height, width), dtype=np.float64)
    
    for light_pos in lights:
        L_dir = light_pos - P_hit
        dist_L = np.linalg.norm(L_dir, axis=-1, keepdims=True)
        L_dir = L_dir / np.maximum(dist_L, 1e-12)
        
        # Shadow ray from hit point to light
        # Sphere shadow test
        P_offset = P_hit + 1e-3 * normals
        shadow_hit_sph, t_shadow = ray_sphere_intersect(P_offset, L_dir, sphere_center, 1.0)
        in_shadow = shadow_hit_sph & (t_shadow < dist_L[..., 0])
        
        # Lambertian cosine
        n_dot_l = np.maximum(0.0, np.sum(normals * L_dir, axis=-1))
        vis = np.where(in_shadow, 0.0, 1.0)
        
        light_contributions += vis * n_dot_l
        
    avg_diffuse = light_contributions / len(lights)
    brightness = np.where(hit_anything, ambient + diffuse_weight * avg_diffuse, 0.0)
    brightness = np.clip(brightness, 0.0, 1.0)
    
    return {
        "brightness": brightness,
        "is_sphere": is_sphere,
        "is_floor": is_floor,
        "hit_mask": hit_anything,
        "camera_pos": camera_pos.tolist(),
        "lights": [l.tolist() for l in lights],
    }


def generate_stippled_image(brightness: np.ndarray, hit_mask: np.ndarray, num_dots: int = 12000) -> tuple[np.ndarray, np.ndarray]:
    """Generate high-contrast stippled point representation (black dots on white background).
    
    Dot density is chosen according to brightness / darkness.
    """
    H, W = brightness.shape
    # Darkness or shading intensity
    # White background: dots represent shadows and surface texture
    # In artistic stippling:
    # High dot density in shadows / midtones, sparse in highlights, none in background
    shading_density = np.where(hit_mask, (1.0 - brightness)**1.5 + 0.05, 0.0)
    total_density = np.sum(shading_density)
    
    if total_density <= 0:
        return np.array([]), np.array([])
        
    prob = shading_density.ravel() / total_density
    np.random.seed(42)
    indices = np.random.choice(H * W, size=num_dots, p=prob)
    
    y_dots = indices // W
    x_dots = indices % W
    
    # Add slight jitter for natural hand-stippled appearance
    jitter_x = np.random.uniform(-0.4, 0.4, size=num_dots)
    jitter_y = np.random.uniform(-0.4, 0.4, size=num_dots)
    
    x_final = x_dots + jitter_x
    y_final = y_dots + jitter_y
    
    return x_final, y_final
