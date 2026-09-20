"""Stippled Diffuse Sphere Rendering Module (Task R1).

Simulates 3D ray-casting of a diffuse sphere with floor shadow under:
- Case A: Single directional light d1 = normalize(-3, -4, 8)
- Case B: Single directional light d2 = normalize( 3, -4, 8)
- Dual point-light reference scene (lights at (-3,-4,8) and (3,-4,8))

Features:
- Analytical sphere and floor ray-casting with exact surface normals.
- Shadow ray test against sphere.
- Diffuse Lambertian shading: B = 0.1 + 0.9 * V * max(0, n . d).
- High-contrast point stippling (black dots on white background).
- Quantitative coverage fidelity metrics: local black coverage ratio vs target brightness error.
- Multi-resolution evaluation (256x256 and 512x512).
"""
from __future__ import annotations

from typing import Any
import numpy as np
from scipy.ndimage import uniform_filter


def ray_sphere_intersect(
    ray_origin: np.ndarray,
    ray_dir: np.ndarray,
    sphere_center: np.ndarray,
    sphere_radius: float = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized ray-sphere intersection.
    
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
    
    t_cand = np.where((t1 > 1e-4) & hit, t1, np.where((t2 > 1e-4) & hit, t2, np.inf))
    hit_mask = (t_cand < np.inf) & hit
    return hit_mask, t_cand


def ray_plane_intersect(
    ray_origin: np.ndarray,
    ray_dir: np.ndarray,
    plane_z: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized ray-plane intersection with z = plane_z."""
    dz = ray_dir[..., 2]
    hit = np.abs(dz) > 1e-6
    t = (plane_z - ray_origin[..., 2]) / np.where(hit, dz, 1.0)
    hit_mask = hit & (t > 1e-4)
    t_vals = np.where(hit_mask, t, np.inf)
    return hit_mask, t_vals


def render_directional_light_scene(
    direction: np.ndarray,
    width: int = 256,
    height: int = 256,
    camera_pos: np.ndarray = np.array([4.0, -6.0, 4.0]),
    camera_target: np.ndarray = np.array([0.0, 0.0, 1.0]),
    camera_up: np.ndarray = np.array([0.0, 0.0, 1.0]),
    fov_deg: float = 40.0,
) -> dict[str, Any]:
    """Render scene with a single directional light source."""
    d = np.asarray(direction, dtype=np.float64)
    d = d / np.linalg.norm(d)
    
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
    
    # Floor boundary clipping
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
    normals[is_sphere] = (P_hit[is_sphere] - sphere_center) / 1.0
    normals[is_floor] = np.array([0.0, 0.0, 1.0])
    
    # Shadow ray test towards directional light d
    P_offset = P_hit + 1e-3 * normals
    dir_broadcast = np.broadcast_to(d, P_hit.shape)
    shadow_hit_sph, t_shadow = ray_sphere_intersect(P_offset, dir_broadcast, sphere_center, 1.0)
    in_shadow = shadow_hit_sph & (t_shadow < np.inf)
    
    # Lambertian diffuse model
    n_dot_d = np.maximum(0.0, np.sum(normals * d, axis=-1))
    vis = np.where(in_shadow, 0.0, 1.0)
    
    ambient = 0.1
    diffuse_weight = 0.9
    brightness = np.where(hit_anything, ambient + diffuse_weight * vis * n_dot_d, 0.0)
    brightness = np.clip(brightness, 0.0, 1.0)
    
    return {
        "width": width,
        "height": height,
        "direction": d.tolist(),
        "brightness": brightness,
        "visibility": vis,
        "is_sphere": is_sphere,
        "is_floor": is_floor,
        "hit_mask": hit_anything,
        "camera_pos": camera_pos.tolist(),
    }


render_scene_directional = render_directional_light_scene


def render_scene(
    width: int = 400,
    height: int = 400,
    camera_pos: np.ndarray = np.array([4.0, -6.0, 4.0]),
    camera_target: np.ndarray = np.array([0.0, 0.0, 1.0]),
    camera_up: np.ndarray = np.array([0.0, 0.0, 1.0]),
    fov_deg: float = 40.0,
    lights: list[np.ndarray] = [np.array([-3.0, -4.0, 8.0]), np.array([3.0, -4.0, 8.0])],
) -> dict[str, Any]:
    """Dual point light scene (kept as reference / additional example)."""
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
    
    u = np.linspace(-half_w, half_w, width)
    v = np.linspace(half_h, -half_h, height)
    U, V = np.meshgrid(u, v)
    
    ray_dirs = forward[np.newaxis, np.newaxis, :] + U[..., np.newaxis] * right + V[..., np.newaxis] * up
    ray_dirs = ray_dirs / np.linalg.norm(ray_dirs, axis=-1, keepdims=True)
    ray_orig = np.broadcast_to(camera_pos, ray_dirs.shape)
    
    sphere_center = np.array([0.0, 0.0, 1.0])
    hit_sph, t_sph = ray_sphere_intersect(ray_orig, ray_dirs, sphere_center, 1.0)
    hit_flr, t_flr = ray_plane_intersect(ray_orig, ray_dirs, 0.0)
    
    P_flr = ray_orig + t_flr[..., np.newaxis] * ray_dirs
    flr_bound = (np.abs(P_flr[..., 0]) <= 5.0) & (np.abs(P_flr[..., 1]) <= 5.0)
    hit_flr = hit_flr & flr_bound
    t_flr = np.where(hit_flr, t_flr, np.inf)
    
    hit_anything = (t_sph < np.inf) | (t_flr < np.inf)
    is_sphere = (t_sph <= t_flr) & hit_sph
    is_floor = (t_flr < t_sph) & hit_flr
    
    t_final = np.where(is_sphere, t_sph, np.where(is_floor, t_flr, np.inf))
    P_hit = ray_orig + t_final[..., np.newaxis] * ray_dirs
    
    normals = np.zeros_like(P_hit)
    normals[is_sphere] = (P_hit[is_sphere] - sphere_center) / 1.0
    normals[is_floor] = np.array([0.0, 0.0, 1.0])
    
    ambient = 0.1
    diffuse_weight = 0.9
    light_contributions = np.zeros((height, width), dtype=np.float64)
    
    for light_pos in lights:
        L_dir = light_pos - P_hit
        dist_L = np.linalg.norm(L_dir, axis=-1, keepdims=True)
        L_dir = L_dir / np.maximum(dist_L, 1e-12)
        
        P_offset = P_hit + 1e-3 * normals
        shadow_hit_sph, t_shadow = ray_sphere_intersect(P_offset, L_dir, sphere_center, 1.0)
        in_shadow = shadow_hit_sph & (t_shadow < dist_L[..., 0])
        
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


def generate_stippled_image(
    brightness: np.ndarray,
    hit_mask: np.ndarray,
    num_dots: int = 12000,
    seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    """Generate high-contrast stippled point representation (black dots on white background)."""
    H, W = brightness.shape
    shading_density = np.where(hit_mask, (1.0 - brightness)**1.5 + 0.05, 0.0)
    total_density = np.sum(shading_density)
    
    if total_density <= 0:
        return np.array([]), np.array([])
        
    prob = shading_density.ravel() / total_density
    rng = np.random.default_rng(seed)
    indices = rng.choice(H * W, size=num_dots, p=prob)
    
    y_dots = indices // W
    x_dots = indices % W
    
    jitter_x = rng.uniform(-0.35, 0.35, size=num_dots)
    jitter_y = rng.uniform(-0.35, 0.35, size=num_dots)
    
    return x_dots + jitter_x, y_dots + jitter_y


def evaluate_stipple_coverage(
    x_dots: np.ndarray,
    y_dots: np.ndarray,
    brightness: np.ndarray,
    hit_mask: np.ndarray,
    window_size: int = 16
) -> dict[str, float]:
    """Evaluate fidelity of stippling to the continuous brightness field.
    
    Computes local black dot coverage ratio and error against target darkness (1 - B).
    """
    H, W = brightness.shape
    # Dot density accumulation on pixel grid
    dot_grid = np.zeros((H, W), dtype=np.float64)
    xi = np.clip(np.round(x_dots).astype(int), 0, W - 1)
    yi = np.clip(np.round(y_dots).astype(int), 0, H - 1)
    for x, y in zip(xi, yi):
        dot_grid[y, x] += 1.0
        
    # Local coverage via spatial uniform filter
    local_dot_count = uniform_filter(dot_grid, size=window_size, mode="constant")
    # Normalize by max density observed on object
    max_count = np.max(local_dot_count[hit_mask]) if np.any(hit_mask) else 1.0
    local_coverage_ratio = local_dot_count / max(max_count, 1e-12)
    
    # Target darkness on object
    target_darkness = np.where(hit_mask, 1.0 - brightness, 0.0)
    
    # Compute error only on surface (hit_mask)
    if np.any(hit_mask):
        err = np.abs(local_coverage_ratio[hit_mask] - target_darkness[hit_mask])
        mae = float(np.mean(err))
        rmse = float(np.sqrt(np.mean(err**2)))
        corr = float(np.corrcoef(local_coverage_ratio[hit_mask], target_darkness[hit_mask])[0, 1])
    else:
        mae, rmse, corr = 0.0, 0.0, 0.0
        
    return {
        "mae": mae,
        "rmse": rmse,
        "correlation": corr,
        "mean_coverage": float(np.mean(local_coverage_ratio[hit_mask])) if np.any(hit_mask) else 0.0,
    }
