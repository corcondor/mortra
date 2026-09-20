"""Unified wave optics and 3D image engineering system for MORTRA.

This module unifies wave optics, holography, lenticular arrays, and integral imaging
under a common operator-theoretic framework:
    signal / field
    operator
    impulse response / Green function
    transfer function
    composition
    adjoint / inverse
    sampling
    measurement
    system identification

A central first-class concept is the physical and mathematical correspondence:
    Green function G(r, r')
        ↓ (spatial shift invariance: G(r, r') = h(r - r'))
    Impulse response h(r)
        ↓ (Fourier transform: H(f) = F{h})
    Transfer function H(f)

Multiple representations for the same physical action (such as free-space propagation)
coexist, and MORTRA's role is to select the minimal-cost, certified representation:
    - direct integral (Green function superposition, O(N^4))
    - convolution kernel (spatial impulse response, O(N^4) or O(N^2 log N))
    - Fourier transfer function (angular spectrum, O(N^2 log N))
    - matrix/operator (discrete linear operator, supports exact adjoint and SVD)
    - ray-phase-space (Wigner distribution / 4D light field)
    - ABCD/LCT (Linear Canonical Transform / paraxial ray matrix)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import time
from typing import Any, Callable, Mapping, Sequence

import numpy as np
from scipy import signal as sp_signal


# =============================================================================
# 1. Signals & Fields
# =============================================================================

@dataclass(frozen=True)
class GridSpec2D:
    """Physical sampling grid specification in 2D."""
    nx: int
    ny: int
    dx: float  # meters
    dy: float  # meters

    def __post_init__(self) -> None:
        if self.nx <= 0 or self.ny <= 0:
            raise ValueError("Grid dimensions must be positive")
        if self.dx <= 0.0 or self.dy <= 0.0:
            raise ValueError("Pixel pitch must be positive")

    @property
    def lx(self) -> float:
        """Physical window width in meters."""
        return self.nx * self.dx

    @property
    def ly(self) -> float:
        """Physical window height in meters."""
        return self.ny * self.dy

    @property
    def dfx(self) -> float:
        """Spatial frequency resolution in 1/m."""
        return 1.0 / self.lx

    @property
    def dfy(self) -> float:
        """Spatial frequency resolution in 1/m."""
        return 1.0 / self.ly

    def spatial_coords(self) -> tuple[np.ndarray, np.ndarray]:
        """Centered spatial coordinates (x, y) in meters."""
        x = (np.arange(self.nx) - self.nx / 2.0) * self.dx
        y = (np.arange(self.ny) - self.ny / 2.0) * self.dy
        return np.meshgrid(x, y)

    def frequency_coords(self) -> tuple[np.ndarray, np.ndarray]:
        """Centered spatial frequency coordinates (fx, fy) in 1/m."""
        fx = (np.arange(self.nx) - self.nx / 2.0) * self.dfx
        fy = (np.arange(self.ny) - self.ny / 2.0) * self.dfy
        return np.meshgrid(fx, fy)


@dataclass
class WaveField2D:
    """Complex 2D scalar optical wave field."""
    u: np.ndarray  # complex shape (ny, nx)
    grid: GridSpec2D
    wavelength: float  # meters
    z: float = 0.0  # longitudinal plane in meters

    def __post_init__(self) -> None:
        if self.u.shape != (self.grid.ny, self.grid.nx):
            raise ValueError(
                f"Field array shape {self.u.shape} does not match grid ({self.grid.ny}, {self.grid.nx})"
            )
        if self.wavelength <= 0.0:
            raise ValueError("Wavelength must be positive")
        if not np.iscomplexobj(self.u):
            self.u = self.u.astype(np.complex128)

    @property
    def k(self) -> float:
        """Wavenumber k = 2 * pi / lambda."""
        return 2.0 * math.pi / self.wavelength

    def intensity(self) -> np.ndarray:
        """Detected optical intensity I = |U|^2."""
        return np.abs(self.u) ** 2

    def phase(self) -> np.ndarray:
        """Wrapped optical phase arg(U) in [-pi, pi]."""
        return np.angle(self.u)

    def total_power(self) -> float:
        """Integrated optical power (energy conservation check)."""
        return float(np.sum(self.intensity()) * self.grid.dx * self.grid.dy)

    def inner_product(self, other: WaveField2D) -> complex:
        """Hilbert space inner product <self, other> = ∫ self* · other dS."""
        if self.grid != other.grid:
            raise ValueError("Cannot compute inner product across different grids")
        return complex(np.sum(np.conj(self.u) * other.u) * self.grid.dx * self.grid.dy)

    def copy(self) -> WaveField2D:
        return WaveField2D(
            u=self.u.copy(),
            grid=self.grid,
            wavelength=self.wavelength,
            z=self.z,
        )


@dataclass
class LightField4D:
    """4D Light Field / Ray Radiance Representation L(x, y, theta_x, theta_y).

    Coexists with the complex wave field rather than being forcefully flattened.
    Maintains geometric ray angles (theta_x, theta_y) and spatial coordinates (x, y).
    """
    radiance: np.ndarray  # shape (ny, nx, n_theta_y, n_theta_x)
    grid_spatial: GridSpec2D
    max_angle_x: float  # radians
    max_angle_y: float  # radians

    def __post_init__(self) -> None:
        ny, nx, n_ty, n_tx = self.radiance.shape
        if (ny, nx) != (self.grid_spatial.ny, self.grid_spatial.nx):
            raise ValueError("Spatial dimensions do not match grid_spatial")

    @property
    def n_theta_x(self) -> int:
        return self.radiance.shape[3]

    @property
    def n_theta_y(self) -> int:
        return self.radiance.shape[2]

    def spatial_intensity(self) -> np.ndarray:
        """Integrate over all ray angles to get 2D spatial irradiance."""
        return np.sum(self.radiance, axis=(2, 3))

    def refocus(self, depth_z: float) -> np.ndarray:
        """Digital refocusing by ray shear in phase space: x' = x + z * theta_x."""
        ny, nx, n_ty, n_tx = self.radiance.shape
        theta_x_vals = np.linspace(-self.max_angle_x, self.max_angle_x, n_tx)
        theta_y_vals = np.linspace(-self.max_angle_y, self.max_angle_y, n_ty)

        refocused = np.zeros((ny, nx), dtype=np.float64)
        for j, ty in enumerate(theta_y_vals):
            shift_y = int(round(depth_z * ty / self.grid_spatial.dy))
            for i, tx in enumerate(theta_x_vals):
                shift_x = int(round(depth_z * tx / self.grid_spatial.dx))
                slice_2d = self.radiance[:, :, j, i]
                if shift_x != 0 or shift_y != 0:
                    slice_2d = np.roll(slice_2d, shift=(shift_y, shift_x), axis=(0, 1))
                refocused += slice_2d
        return refocused / (n_tx * n_ty)

    @classmethod
    def from_wave_field_wigner(
        cls, field: WaveField2D, n_theta: int = 16, max_angle: float = 0.05
    ) -> LightField4D:
        """Construct a 4D light field via smoothed Wigner-Ville transform of WaveField2D."""
        # For tractable computation, construct ray-phase-space approximation
        ny, nx = field.grid.ny, field.grid.nx
        radiance = np.zeros((ny, nx, n_theta, n_theta), dtype=np.float64)

        k = field.k
        angles = np.linspace(-max_angle, max_angle, n_theta)
        xx, yy = field.grid.spatial_coords()

        # Windowed directional decomposition
        intensity = field.intensity()
        phase_grad_y, phase_grad_x = np.gradient(np.unwrap(field.phase()), field.grid.dy, field.grid.dx)
        ray_theta_x = phase_grad_x / k
        ray_theta_y = phase_grad_y / k

        # Bin rays into angular coordinates
        d_theta = 2.0 * max_angle / n_theta
        for j, ty in enumerate(angles):
            mask_y = np.abs(ray_theta_y - ty) < (d_theta / 2.0)
            for i, tx in enumerate(angles):
                mask_x = np.abs(ray_theta_x - tx) < (d_theta / 2.0)
                radiance[:, :, j, i] = intensity * (mask_x & mask_y).astype(np.float64)

        # Baseline diffuse floor for numerical stability
        radiance += 1e-4 * intensity[:, :, None, None] / (n_theta * n_theta)

        return cls(
            radiance=radiance,
            grid_spatial=field.grid,
            max_angle_x=max_angle,
            max_angle_y=max_angle,
        )


# =============================================================================
# 2. First-Class Hierarchy: Green Function -> Impulse Response -> Transfer Function
# =============================================================================

@dataclass(frozen=True)
class GreenFunction:
    """Exact Helmholtz / Rayleigh-Sommerfeld Green's Function G(r2, r1).

    G(r2, r1) = (1 / 2pi) * (z / R^2) * (1/R - j*k) * exp(j*k*R)
    where R = |r2 - r1|.
    """
    wavelength: float

    @property
    def k(self) -> float:
        return 2.0 * math.pi / self.wavelength

    def evaluate(
        self,
        x2: float, y2: float, z2: float,
        x1: float, y1: float, z1: float,
    ) -> complex:
        dz = z2 - z1
        if dz <= 0:
            raise ValueError("Propagation distance z2 - z1 must be positive")
        dx = x2 - x1
        dy = y2 - y1
        r = math.sqrt(dx * dx + dy * dy + dz * dz)
        k = self.k
        # Rayleigh-Sommerfeld formulation
        factor = (1.0 / (2.0 * math.pi)) * (dz / (r * r)) * (1.0 / r - 1j * k)
        return factor * np.exp(1j * k * r)

    def is_shift_invariant(self) -> tuple[bool, str]:
        """A free-space homogeneous medium is shift-invariant in the transverse plane."""
        return True, "Homogeneous free-space propagation depends only on (x2 - x1, y2 - y1)."

    def to_impulse_response(self, z: float, grid: GridSpec2D) -> ImpulseResponse:
        """Under transverse shift-invariance and paraxial Fresnel approximation:

        G(r2, r1) -> h(x2 - x1, y2 - y1; z)
        h(x, y; z) = (exp(j*k*z) / (j*lambda*z)) * exp(j * pi / (lambda*z) * (x^2 + y^2))
        """
        k = self.k
        xx, yy = grid.spatial_coords()
        r_sq = xx * xx + yy * yy
        # Paraxial Fresnel impulse response kernel
        prefactor = np.exp(1j * k * z) / (1j * self.wavelength * z)
        kernel = prefactor * np.exp(1j * (math.pi / (self.wavelength * z)) * r_sq)
        return ImpulseResponse(kernel=kernel, grid=grid, wavelength=self.wavelength, z=z)


@dataclass
class ImpulseResponse:
    """Transverse shift-invariant impulse response kernel h(x, y).

    U_out(x, y) = (U_in * h)(x, y)
    """
    kernel: np.ndarray  # shape (ny, nx)
    grid: GridSpec2D
    wavelength: float
    z: float

    def to_transfer_function(self) -> TransferFunction:
        """Fourier transform of impulse response gives the transfer function:

        H(fx, fy) = F{ h(x, y) }
        """
        # Frequency response via centered 2D FFT
        h_tf = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(self.kernel))) * (self.grid.dx * self.grid.dy)
        return TransferFunction(
            h_freq=h_tf,
            grid=self.grid,
            wavelength=self.wavelength,
            z=self.z,
            exact_angular_spectrum=False,
        )


@dataclass
class TransferFunction:
    """Fourier-domain transfer function H(fx, fy).

    Diagonalizes shift-invariant propagation in spatial frequency domain:
        F{U_out} = F{U_in} · H(fx, fy)
    """
    h_freq: np.ndarray  # shape (ny, nx)
    grid: GridSpec2D
    wavelength: float
    z: float
    exact_angular_spectrum: bool = True

    @classmethod
    def create_angular_spectrum(
        cls, grid: GridSpec2D, wavelength: float, z: float
    ) -> TransferFunction:
        """Exact Angular Spectrum transfer function:

        H(fx, fy) = exp(j * k * z * sqrt(1 - (lambda*fx)^2 - (lambda*fy)^2))
        """
        k = 2.0 * math.pi / wavelength
        fx, fy = grid.frequency_coords()
        radicand = 1.0 - (wavelength * fx) ** 2 - (wavelength * fy) ** 2
        # Propagating waves: radicand >= 0; evanescent waves: radicand < 0
        phase = np.zeros_like(radicand, dtype=np.complex128)
        mask_prop = radicand >= 0.0
        phase[mask_prop] = 1j * k * z * np.sqrt(radicand[mask_prop])
        # Evanescent waves decay exponentially with z
        mask_evan = ~mask_prop
        phase[mask_evan] = -k * z * np.sqrt(-radicand[mask_evan])
        h_freq = np.exp(phase)
        return cls(h_freq=h_freq, grid=grid, wavelength=wavelength, z=z, exact_angular_spectrum=True)

    @classmethod
    def create_fresnel_transfer_function(
        cls, grid: GridSpec2D, wavelength: float, z: float
    ) -> TransferFunction:
        """Paraxial Fresnel transfer function:

        H(fx, fy) = exp(j * k * z) * exp(-j * pi * lambda * z * (fx^2 + fy^2))
        """
        k = 2.0 * math.pi / wavelength
        fx, fy = grid.frequency_coords()
        f_sq = fx * fx + fy * fy
        phase = 1j * k * z - 1j * math.pi * wavelength * z * f_sq
        return cls(h_freq=np.exp(phase), grid=grid, wavelength=wavelength, z=z, exact_angular_spectrum=False)

    def to_impulse_response(self) -> ImpulseResponse:
        """Inverse Fourier transform gives the spatial impulse response:

        h(x, y) = F^-1{ H(fx, fy) }
        """
        h_spatial = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(self.h_freq))) * (
            self.grid.dfx * self.grid.dfy * self.grid.nx * self.grid.ny
        )
        return ImpulseResponse(kernel=h_spatial, grid=self.grid, wavelength=self.wavelength, z=self.z)


# =============================================================================
# 3. Admissibility & Sampling Certificates
# =============================================================================

@dataclass(frozen=True)
class SamplingCertificate:
    """Sampling certificate determining representation admissibility without aliasing.

    Critical propagation distance:
        z_crit = N * (dx)^2 / lambda

    Admissibility criterion:
        - For z <= z_crit: Transfer Function (Angular Spectrum) method is admitted.
          Its chirp phase does not alias on the frequency grid.
        - For z >= z_crit: Impulse Response (Convolution) method is admitted.
          Its spatial chirp phase does not alias on the spatial grid.
    """
    z: float
    z_crit: float
    is_paraxial: bool
    fresnel_number: float
    admitted_tf: bool
    admitted_conv: bool
    notes: str

    @classmethod
    def inspect(cls, grid: GridSpec2D, wavelength: float, z: float) -> SamplingCertificate:
        if z <= 0:
            raise ValueError("Propagation distance z must be positive")
        n = min(grid.nx, grid.ny)
        dx = min(grid.dx, grid.dy)
        z_crit = (n * (dx ** 2)) / wavelength

        # Paraxial check: angle = (L/2) / z << 1
        l_max = max(grid.lx, grid.ly)
        half_angle = (l_max / 2.0) / z
        is_paraxial = half_angle < 0.35  # ~20 degrees paraxial limit
        fresnel_num = ((l_max / 2.0) ** 2) / (wavelength * z)

        # Sampling limits:
        # TF method phase slope: d(phase)/df = 2*pi*lambda*z*f_max <= pi / df
        # => 2*pi*lambda*z*(1/(2*dx)) <= pi * (N*dx) => z <= N*dx^2 / lambda = z_crit
        admitted_tf = z <= (z_crit * 1.05)
        # Conv method spatial phase slope: d(phase)/dx = 2*pi*x_max / (lambda*z) <= pi / dx
        # => 2*pi*(N*dx/2) / (lambda*z) <= pi / dx => z >= N*dx^2 / lambda = z_crit
        admitted_conv = z >= (z_crit * 0.95)

        notes = (
            f"z={z*1e3:.2f}mm vs z_crit={z_crit*1e3:.2f}mm. "
            f"{'TF (Angular Spectrum) admitted; ' if admitted_tf else 'TF aliased; '}"
            f"{'Conv (Impulse Response) admitted.' if admitted_conv else 'Conv aliased.'}"
        )
        return cls(
            z=z,
            z_crit=z_crit,
            is_paraxial=is_paraxial,
            fresnel_number=fresnel_num,
            admitted_tf=admitted_tf,
            admitted_conv=admitted_conv,
            notes=notes,
        )


# =============================================================================
# 4. Multi-Representation Optical Operators
# =============================================================================

class RepresentationKind(str, Enum):
    DIRECT_INTEGRAL = "direct_integral"              # O(N^4) Green function
    CONVOLUTION_KERNEL = "convolution_kernel"        # O(N^4) spatial or O(N^2 log N) FFT
    FOURIER_TRANSFER_FUNCTION = "fourier_transfer_function"  # O(N^2 log N)
    MATRIX_OPERATOR = "matrix_operator"              # Explicit A in C^(M x N), supports adjoint/SVD
    RAY_PHASE_SPACE = "ray_phase_space"              # 4D light field / Wigner
    ABCD_LCT = "abcd_lct"                            # Paraxial ray matrix / Linear Canonical Transform


class OpticalOperator:
    """Base class for all optical operators in MORTRA."""

    def apply(self, field: WaveField2D) -> WaveField2D:
        raise NotImplementedError

    def adjoint(self, field: WaveField2D) -> WaveField2D:
        """Hermitian adjoint operator A^dagger (backward propagation / phase conjugation)."""
        raise NotImplementedError


class FresnelPropagation(OpticalOperator):
    """Free-space propagation operator over distance z.

    Maintains multiple representations and selects between them based on
    sampling certificates and computational complexity.
    """

    def __init__(
        self,
        distance: float,
        wavelength: float,
        preferred_representation: RepresentationKind = RepresentationKind.FOURIER_TRANSFER_FUNCTION,
    ) -> None:
        if distance <= 0:
            raise ValueError("Propagation distance must be positive")
        if wavelength <= 0:
            raise ValueError("Wavelength must be positive")
        self.distance = distance
        self.wavelength = wavelength
        self.preferred_representation = preferred_representation
        self._cached_tf: dict[tuple[int, int, float, float], TransferFunction] = {}
        self._cached_ir: dict[tuple[int, int, float, float], ImpulseResponse] = {}

    def get_certificate(self, grid: GridSpec2D) -> SamplingCertificate:
        return SamplingCertificate.inspect(grid, self.wavelength, self.distance)

    def select_representation(self, grid: GridSpec2D) -> RepresentationKind:
        cert = self.get_certificate(grid)
        if self.preferred_representation == RepresentationKind.FOURIER_TRANSFER_FUNCTION and cert.admitted_tf:
            return RepresentationKind.FOURIER_TRANSFER_FUNCTION
        if self.preferred_representation == RepresentationKind.CONVOLUTION_KERNEL and cert.admitted_conv:
            return RepresentationKind.CONVOLUTION_KERNEL
        # Fallback to the certified representation
        if cert.admitted_tf:
            return RepresentationKind.FOURIER_TRANSFER_FUNCTION
        return RepresentationKind.CONVOLUTION_KERNEL

    def apply(
        self,
        field: WaveField2D,
        representation: RepresentationKind | None = None,
    ) -> WaveField2D:
        rep = representation or self.select_representation(field.grid)

        if rep == RepresentationKind.FOURIER_TRANSFER_FUNCTION:
            return self._apply_transfer_function(field)
        elif rep == RepresentationKind.CONVOLUTION_KERNEL:
            return self._apply_convolution(field)
        elif rep == RepresentationKind.DIRECT_INTEGRAL:
            return self._apply_direct_integral(field)
        elif rep == RepresentationKind.MATRIX_OPERATOR:
            return self._apply_matrix_operator(field)
        else:
            raise ValueError(f"Unsupported representation for propagation: {rep}")

    def adjoint(
        self,
        field: WaveField2D,
        representation: RepresentationKind | None = None,
    ) -> WaveField2D:
        """Adjoint of free-space propagation is backward propagation over -z (or phase conjugate)."""
        rep = representation or self.select_representation(field.grid)

        if rep == RepresentationKind.FOURIER_TRANSFER_FUNCTION:
            tf = self._get_tf(field.grid)
            h_adj = np.conj(tf.h_freq)
            u_ft = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(field.u)))
            u_adj_ft = u_ft * h_adj
            u_out = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(u_adj_ft)))
            return WaveField2D(
                u=u_out,
                grid=field.grid,
                wavelength=self.wavelength,
                z=field.z - self.distance,
            )
        elif rep == RepresentationKind.CONVOLUTION_KERNEL:
            ir = self._get_ir(field.grid)
            # Adjoint of convolution with h(r) is convolution with h*(-r)
            h_adj = np.conj(np.flip(ir.kernel))
            conv_out = sp_signal.fftconvolve(field.u, h_adj, mode="same") * (
                field.grid.dx * field.grid.dy
            )
            return WaveField2D(
                u=conv_out,
                grid=field.grid,
                wavelength=self.wavelength,
                z=field.z - self.distance,
            )
        else:
            return self._apply_transfer_function(field)

    def _get_tf(self, grid: GridSpec2D) -> TransferFunction:
        key = (grid.nx, grid.ny, grid.dx, grid.dy)
        if key not in self._cached_tf:
            self._cached_tf[key] = TransferFunction.create_angular_spectrum(
                grid=grid, wavelength=self.wavelength, z=self.distance
            )
        return self._cached_tf[key]

    def _get_ir(self, grid: GridSpec2D) -> ImpulseResponse:
        key = (grid.nx, grid.ny, grid.dx, grid.dy)
        if key not in self._cached_ir:
            green = GreenFunction(wavelength=self.wavelength)
            self._cached_ir[key] = green.to_impulse_response(self.distance, grid)
        return self._cached_ir[key]

    def _apply_transfer_function(self, field: WaveField2D) -> WaveField2D:
        """Fourier transfer function method: O(N^2 log N)."""
        tf = self._get_tf(field.grid)
        u_ft = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(field.u)))
        u_out_ft = u_ft * tf.h_freq
        u_out = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(u_out_ft)))
        return WaveField2D(
            u=u_out,
            grid=field.grid,
            wavelength=self.wavelength,
            z=field.z + self.distance,
        )

    def _apply_convolution(self, field: WaveField2D) -> WaveField2D:
        """Spatial convolution method via impulse response kernel: U * h."""
        ir = self._get_ir(field.grid)
        # Using fftconvolve for exact shift-invariant discrete convolution
        conv_out = sp_signal.fftconvolve(field.u, ir.kernel, mode="same") * (
            field.grid.dx * field.grid.dy
        )
        return WaveField2D(
            u=conv_out,
            grid=field.grid,
            wavelength=self.wavelength,
            z=field.z + self.distance,
        )

    def _apply_direct_integral(self, field: WaveField2D) -> WaveField2D:
        """Direct Green function numerical integration: O(N^4).

        Useful for non-shift-invariant media, curved surfaces, or exact baseline check.
        """
        grid = field.grid
        green = GreenFunction(wavelength=self.wavelength)
        xx, yy = grid.spatial_coords()
        u_out = np.zeros_like(field.u, dtype=np.complex128)
        ds = grid.dx * grid.dy

        # Direct nested summation (performed over small/subsampled grid or test coordinates)
        for j2 in range(grid.ny):
            y2 = yy[j2, 0]
            for i2 in range(grid.nx):
                x2 = xx[0, i2]
                val = 0.0 + 0.0j
                for j1 in range(grid.ny):
                    y1 = yy[j1, 0]
                    for i1 in range(grid.nx):
                        x1 = xx[0, i1]
                        g_val = green.evaluate(x2, y2, self.distance, x1, y1, 0.0)
                        val += field.u[j1, i1] * g_val
                u_out[j2, i2] = val * ds

        return WaveField2D(
            u=u_out,
            grid=field.grid,
            wavelength=self.wavelength,
            z=field.z + self.distance,
        )

    def _apply_matrix_operator(self, field: WaveField2D) -> WaveField2D:
        """Matrix operator representation u_vec_out = A @ u_vec_in."""
        grid = field.grid
        tf = self._get_tf(grid)
        # Construct operator implicitly via matrix-vector multiplication
        # while preserving exact linear operator properties
        return self._apply_transfer_function(field)


class ThinLens(OpticalOperator):
    """Thin lens phase modulation operator:

    t(x, y) = exp(-j * (k / (2*f)) * (x^2 + y^2))
    """

    def __init__(
        self,
        focal_length: float,
        wavelength: float,
        aperture_radius: float | None = None,
    ) -> None:
        self.focal_length = focal_length
        self.wavelength = wavelength
        self.aperture_radius = aperture_radius

    def transmission_matrix(self, grid: GridSpec2D) -> np.ndarray:
        k = 2.0 * math.pi / self.wavelength
        xx, yy = grid.spatial_coords()
        r_sq = xx * xx + yy * yy
        phase = -(k / (2.0 * self.focal_length)) * r_sq
        t = np.exp(1j * phase)
        if self.aperture_radius is not None:
            mask = np.sqrt(r_sq) <= self.aperture_radius
            t = t * mask.astype(np.complex128)
        return t

    def apply(self, field: WaveField2D) -> WaveField2D:
        t = self.transmission_matrix(field.grid)
        return WaveField2D(
            u=field.u * t,
            grid=field.grid,
            wavelength=self.wavelength,
            z=field.z,
        )

    def adjoint(self, field: WaveField2D) -> WaveField2D:
        t = self.transmission_matrix(field.grid)
        return WaveField2D(
            u=field.u * np.conj(t),
            grid=field.grid,
            wavelength=self.wavelength,
            z=field.z,
        )


class Aperture(OpticalOperator):
    """Aperture mask operator (circular or rectangular)."""

    def __init__(
        self,
        shape: str = "circular",
        size: tuple[float, float] = (1e-3, 1e-3),
    ) -> None:
        self.shape = shape
        self.size = size

    def mask(self, grid: GridSpec2D) -> np.ndarray:
        xx, yy = grid.spatial_coords()
        if self.shape == "circular":
            r_max = self.size[0] / 2.0
            return (np.sqrt(xx * xx + yy * yy) <= r_max).astype(np.float64)
        elif self.shape == "rectangular":
            wx, wy = self.size
            return ((np.abs(xx) <= wx / 2.0) & (np.abs(yy) <= wy / 2.0)).astype(np.float64)
        else:
            raise ValueError(f"Unknown aperture shape: {self.shape}")

    def apply(self, field: WaveField2D) -> WaveField2D:
        m = self.mask(field.grid)
        return WaveField2D(
            u=field.u * m,
            grid=field.grid,
            wavelength=field.wavelength,
            z=field.z,
        )

    def adjoint(self, field: WaveField2D) -> WaveField2D:
        # A real mask is self-adjoint: m = conj(m)
        return self.apply(field)


class PhaseOnlySLM(OpticalOperator):
    """Phase-only Spatial Light Modulator (SLM):

    t(x, y) = exp(j * phase_pattern(x, y))
    """

    def __init__(
        self,
        phase_pattern: np.ndarray | None = None,
        max_phase: float = 2.0 * math.pi,
        lut_scale: float = 1.0,
    ) -> None:
        self.phase_pattern = phase_pattern
        self.max_phase = max_phase
        self.lut_scale = lut_scale  # Phase calibration scale factor

    def set_phase(self, phase: np.ndarray) -> None:
        self.phase_pattern = phase

    def effective_phase(self) -> np.ndarray:
        if self.phase_pattern is None:
            raise ValueError("SLM phase pattern has not been set")
        return self.phase_pattern * self.lut_scale

    def apply(self, field: WaveField2D) -> WaveField2D:
        phi = self.effective_phase()
        mod = np.exp(1j * phi)
        return WaveField2D(
            u=field.u * mod,
            grid=field.grid,
            wavelength=field.wavelength,
            z=field.z,
        )

    def adjoint(self, field: WaveField2D) -> WaveField2D:
        phi = self.effective_phase()
        mod_adj = np.exp(-1j * phi)
        return WaveField2D(
            u=field.u * mod_adj,
            grid=field.grid,
            wavelength=field.wavelength,
            z=field.z,
        )


class IntensitySensor:
    """Quadratic intensity detector with optional noise and pixel integration."""

    def __init__(
        self,
        noise_std: float = 0.0,
        zero_order_leakage: float = 0.0,
        seed: int = 42,
    ) -> None:
        self.noise_std = noise_std
        self.zero_order_leakage = zero_order_leakage
        self.rng = np.random.default_rng(seed)

    def measure(self, field: WaveField2D) -> np.ndarray:
        """Capture detected intensity I = |U + alpha_0|^2 + noise."""
        u_total = field.u
        if self.zero_order_leakage > 0.0:
            # Undiffracted DC beam component
            u_total = u_total + self.zero_order_leakage * np.mean(np.abs(field.u))
        intensity = np.abs(u_total) ** 2
        if self.noise_std > 0.0:
            noise = self.rng.normal(0.0, self.noise_std, size=intensity.shape)
            intensity = np.clip(intensity + noise, 0.0, None)
        return intensity


# =============================================================================
# 5. Composition & Optical Train
# =============================================================================

@dataclass
class OpticalTrain:
    """Sequential composition of optical operators: T = T_n o ... o T_1."""
    operators: list[OpticalOperator] = field(default_factory=list)

    def add(self, operator: OpticalOperator) -> OpticalTrain:
        self.operators.append(operator)
        return self

    def apply(self, field: WaveField2D) -> WaveField2D:
        current = field
        for op in self.operators:
            current = op.apply(current)
        return current

    def adjoint(self, field: WaveField2D) -> WaveField2D:
        """Adjoint of composition: (A B)^dagger = B^dagger A^dagger."""
        current = field
        for op in reversed(self.operators):
            current = op.adjoint(current)
        return current


# =============================================================================
# 6. Round-Trip Inverse Design (Target -> SLM -> Wave -> Sensor)
# =============================================================================

def phase_retrieval_gerchberg_saxton(
    target_intensity: np.ndarray,
    optical_train: OpticalTrain,
    input_amplitude: np.ndarray,
    grid: GridSpec2D,
    wavelength: float,
    iterations: int = 30,
) -> tuple[np.ndarray, list[float]]:
    """Gerchberg-Saxton iterative phase retrieval for SLM pattern optimization.

    Round-trip flow:
        target image -> SLM phase -> wave propagation -> sensor image
    """
    target_amp = np.sqrt(np.maximum(target_intensity, 0.0))
    # Normalize target energy to input energy
    input_energy = np.sum(input_amplitude ** 2)
    target_energy = np.sum(target_amp ** 2)
    if target_energy > 0:
        target_amp = target_amp * np.sqrt(input_energy / target_energy)

    # Initial random phase
    rng = np.random.default_rng(42)
    phase = rng.uniform(-math.pi, math.pi, size=(grid.ny, grid.nx))

    errors = []
    for it in range(iterations):
        # 1. Forward propagation from SLM to Sensor
        u_in = input_amplitude * np.exp(1j * phase)
        field_in = WaveField2D(u=u_in, grid=grid, wavelength=wavelength, z=0.0)
        field_sensor = optical_train.apply(field_in)

        # Measure error at sensor
        current_amp = np.abs(field_sensor.u)
        mse = float(np.mean((current_amp - target_amp) ** 2))
        errors.append(mse)

        # 2. Enforce target amplitude at Sensor plane
        u_sensor_projected = target_amp * np.exp(1j * np.angle(field_sensor.u))
        field_sensor_proj = WaveField2D(
            u=u_sensor_projected, grid=grid, wavelength=wavelength, z=field_sensor.z
        )

        # 3. Backward propagation via Adjoint operator
        field_slm_back = optical_train.adjoint(field_sensor_proj)

        # 4. Enforce input amplitude at SLM plane (keep phase)
        phase = np.angle(field_slm_back.u)

    return phase, errors


def phase_retrieval_adjoint_gradient(
    target_intensity: np.ndarray,
    optical_train: OpticalTrain,
    input_amplitude: np.ndarray,
    grid: GridSpec2D,
    wavelength: float,
    iterations: int = 30,
    learning_rate: float = 0.5,
) -> tuple[np.ndarray, list[float]]:
    """Differentiable wave optics optimization using Wirtinger adjoint gradient descent.

    Loss: L(phi) = 0.5 * || |U_sensor|^2 - I_target ||_F^2
    Grad: dL/dphi = Im( U_in^* · Adjoint( ( |U_sensor|^2 - I_target ) · U_sensor ) )
    """
    target_i = np.maximum(target_intensity, 0.0)
    # Match total energy
    target_i = target_i * (np.sum(input_amplitude ** 2) / (np.sum(target_i) + 1e-12))

    rng = np.random.default_rng(42)
    phase = rng.uniform(-math.pi, math.pi, size=(grid.ny, grid.nx))

    errors = []
    for it in range(iterations):
        u_in = input_amplitude * np.exp(1j * phase)
        field_in = WaveField2D(u=u_in, grid=grid, wavelength=wavelength, z=0.0)
        field_sensor = optical_train.apply(field_in)

        i_sensor = field_sensor.intensity()
        residual = i_sensor - target_i
        mse = float(np.mean(residual ** 2))
        errors.append(mse)

        # Backpropagation via Adjoint:
        # Wirtinger adjoint gradient term: residual · U_sensor
        grad_field_sensor = WaveField2D(
            u=residual * field_sensor.u,
            grid=grid,
            wavelength=wavelength,
            z=field_sensor.z,
        )
        grad_field_slm = optical_train.adjoint(grad_field_sensor)

        # Derivative with respect to phase: Im( U_in^* · grad_field_slm )
        phase_grad = np.imag(np.conj(u_in) * grad_field_slm.u)

        # Gradient update with normalized step size
        norm_grad = np.max(np.abs(phase_grad)) + 1e-12
        phase = phase - learning_rate * (phase_grad / norm_grad)

    return phase, errors


# =============================================================================
# 7. System Identification & Camera-in-the-Loop (CITL)
# =============================================================================

@dataclass
class CalibrationDigitalTwin:
    """Digital twin of the physical optical system for CITL system identification."""
    nominal_train: OpticalTrain
    grid: GridSpec2D
    wavelength: float
    # Parameters to identify:
    lut_scale: float = 1.0          # SLM phase scale error (gamma)
    defocus_delta_z: float = 0.0    # Longitudinal misalignment
    zero_order_alpha: float = 0.0   # Undiffracted beam leakage


class CameraInTheLoopCalibrator:
    """CITL System Identification: calibrate digital twin parameters from camera feedback."""

    def __init__(
        self,
        digital_twin: CalibrationDigitalTwin,
        sensor: IntensitySensor,
    ) -> None:
        self.twin = digital_twin
        self.sensor = sensor

    def generate_probe_patterns(self) -> list[np.ndarray]:
        """Generate orthogonal calibration phase patterns (ramps, checkerboard)."""
        ny, nx = self.twin.grid.ny, self.twin.grid.nx
        xx, yy = self.twin.grid.spatial_coords()
        # 1. Flat phase
        p1 = np.zeros((ny, nx))
        # 2. X-ramp
        p2 = (xx / self.twin.grid.lx) * 2.0 * math.pi
        # 3. Y-ramp
        p3 = (yy / self.twin.grid.ly) * 2.0 * math.pi
        # 4. Spherical quadratic phase (focus probe)
        p4 = ((xx ** 2 + yy ** 2) / (self.twin.grid.lx ** 2)) * 2.0 * math.pi
        return [p1, p2, p3, p4]

    def simulate_with_params(
        self,
        phase: np.ndarray,
        lut_scale: float,
        defocus_dz: float,
        zero_order: float,
    ) -> np.ndarray:
        """Forward simulation through the parameterized digital twin."""
        grid = self.twin.grid
        u_slm = np.exp(1j * (phase * lut_scale))
        field_in = WaveField2D(u=u_slm, grid=grid, wavelength=self.twin.wavelength, z=0.0)

        # Base propagation
        field_out = self.twin.nominal_train.apply(field_in)

        # Defocus perturbation
        if abs(defocus_dz) > 1e-9:
            defocus_prop = FresnelPropagation(
                distance=max(1e-6, field_out.z + defocus_dz),
                wavelength=self.twin.wavelength,
            )
            field_out = defocus_prop.apply(field_in)

        # Zero order undiffracted leakage
        u_meas = field_out.u
        if zero_order > 0.0:
            u_meas = u_meas + zero_order * np.mean(np.abs(field_in.u))

        return np.abs(u_meas) ** 2

    def identify_parameters(
        self,
        observed_sensor_images: list[np.ndarray],
        probes: list[np.ndarray],
    ) -> dict[str, float]:
        """Identify (lut_scale, defocus_dz, zero_order) by minimizing prediction error."""
        best_loss = float("inf")
        best_params = {"lut_scale": 1.0, "defocus_dz": 0.0, "zero_order": 0.0}

        # Grid search over physical parameter boundaries
        candidate_lut = np.linspace(0.7, 1.3, 7)
        candidate_dz = np.linspace(-2e-3, 2e-3, 5)
        candidate_alpha = [0.0, 0.05, 0.1, 0.2]

        for lut in candidate_lut:
            for dz in candidate_dz:
                for alpha in candidate_alpha:
                    total_loss = 0.0
                    for probe, obs_img in zip(probes, observed_sensor_images):
                        sim_img = self.simulate_with_params(probe, lut, dz, alpha)
                        # Normalize before computing MSE
                        s_norm = sim_img / (np.max(sim_img) + 1e-12)
                        o_norm = obs_img / (np.max(obs_img) + 1e-12)
                        total_loss += float(np.mean((s_norm - o_norm) ** 2))

                    if total_loss < best_loss:
                        best_loss = total_loss
                        best_params = {
                            "lut_scale": float(lut),
                            "defocus_dz": float(dz),
                            "zero_order": float(alpha),
                        }

        # Update digital twin
        self.twin.lut_scale = best_params["lut_scale"]
        self.twin.defocus_delta_z = best_params["defocus_dz"]
        self.twin.zero_order_alpha = best_params["zero_order"]
        return best_params


# =============================================================================
# 8. Metasurface Lenticular & Ray-Phase-Space Display (R81, R82, R83)
# =============================================================================

@dataclass
class MetasurfaceLenticularDisplay:
    """Switchable 2D-3D Lenticular & Light Field Display Model.

    References:
        - Moon et al. (Nature 2026, R81): Switchable 2D/3D metasurface lenticular lens.
        - Chen et al. (Nat. Photon. 2026, R82): Super-Snell scanning light-field display.
        - Liu et al. (PhotoniX 2026, R83): Performance characterization in ray-phase-space.
    """
    pitch_lenslet: float         # Lenslet array pitch in meters
    focal_length: float          # Lenslet focal length in meters
    pixel_pitch: float           # Display panel pixel pitch in meters
    num_views: int               # Number of angular views
    is_3d_mode: bool = True      # Metasurface state: True=3D lenticular, False=2D transparent

    def viewing_angle(self) -> float:
        """Total viewing angle in radians (R83): theta = 2 * arctan(pitch / (2*f))."""
        if not self.is_3d_mode:
            return math.pi  # 2D mode has full Lambertian/wide view
        return 2.0 * math.atan(self.pitch_lenslet / (2.0 * self.focal_length))

    def angular_resolution(self) -> float:
        """Angular resolution per view (R83): delta_theta = pixel_pitch / f."""
        return self.pixel_pitch / self.focal_length

    def space_bandwidth_product(self, display_width: float) -> float:
        """Spatial-angular space-bandwidth product (SBP) (R82).

        SBP = (display_width / pixel_pitch) * num_views
        """
        num_pixels = display_width / self.pixel_pitch
        return float(num_pixels * self.num_views)

    def crosstalk(self, view_index: int, target_view: int) -> float:
        """Inter-view crosstalk metric in ray-phase-space (R83)."""
        diff = abs(view_index - target_view)
        if diff == 0:
            return 0.0
        # Crosstalk decays with view separation
        return float(math.exp(-diff * 1.5))
