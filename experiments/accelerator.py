"""Optional numerical acceleration for MORTRA image/evidence workloads.

The game engine, structural graph and field planner stay on CPU.  CUDA is used
only for dense image statistics / Fourier transforms where batching is useful.
This preserves the existing control semantics while allowing Colab T4/L4/A100
runtimes to accelerate the expensive perception side.

PyTorch is optional.  CPU-only environments do not need it.
"""
from __future__ import annotations

from functools import lru_cache
import os

import numpy as np


def _torch():
    try:
        import torch
    except ImportError:
        return None
    return torch


@lru_cache(maxsize=None)
def resolve_device(requested="auto"):
    requested = str(requested or "auto").lower()
    env = os.getenv("MORTRA_DEVICE")
    if env and requested == "auto":
        requested = env.lower()
    if requested not in ("auto", "cpu", "cuda"):
        raise ValueError("device must be auto, cpu, or cuda")
    torch = _torch()
    if requested == "cpu":
        return "cpu"
    if requested == "cuda":
        if torch is None:
            raise RuntimeError("CUDA requested but PyTorch is not installed")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
        return "cuda"
    if torch is not None and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def device_info(requested="auto"):
    resolved = resolve_device(requested)
    result = {
        "requested": str(requested),
        "resolved": resolved,
        "torch_available": _torch() is not None,
        "cuda_available": False,
        "device_name": "CPU",
    }
    torch = _torch()
    if torch is not None:
        result["torch_version"] = str(torch.__version__)
        result["cuda_available"] = bool(torch.cuda.is_available())
        if resolved == "cuda":
            result["device_name"] = torch.cuda.get_device_name(0)
            result["cuda_version"] = str(torch.version.cuda)
            result["vram_bytes"] = int(torch.cuda.get_device_properties(0).total_memory)
    return result


def z_score_rgb_batches(a, b, *, noise_floor=.01, reference_n=32, device="auto"):
    """Return the same scalar RGB z-score as Statistics.z, optionally on CUDA.

    Inputs are uint8 arrays [samples,height,width,3] with equal sample count.
    Only the final scalar crosses from GPU to CPU.
    """
    a = np.asarray(a, dtype=np.uint8)
    b = np.asarray(b, dtype=np.uint8)
    if a.shape != b.shape or a.ndim != 4 or a.shape[-1] != 3:
        raise ValueError("RGB batches must have equal [n,h,w,3] shape")
    n = int(a.shape[0])
    if n < 1:
        raise ValueError("empty RGB batch")
    floor = float(noise_floor) * (float(reference_n) / n) ** .25
    resolved = resolve_device(device)
    if resolved == "cpu":
        xa = a.reshape(n, -1).astype(np.float32) / 255.
        xb = b.reshape(n, -1).astype(np.float32) / 255.
        ma, mb = xa.mean(0), xb.mean(0)
        if n == 1:
            va = np.zeros_like(ma)
            vb = np.zeros_like(mb)
        else:
            va = xa.var(0, ddof=1)
            vb = xb.var(0, ddof=1)
        den = va/n + vb/n + floor**2
        numerator = (ma-mb)**2
        if np.all(den == 0):
            return 0.0 if np.all(numerator == 0) else float("inf")
        terms = np.divide(numerator, den, out=np.full_like(numerator, np.inf),
                          where=den>0)
        return float(np.sqrt(np.mean(terms)))

    torch = _torch()
    with torch.inference_mode():
        xa = torch.as_tensor(a, device="cuda", dtype=torch.float32).reshape(n, -1).div_(255.)
        xb = torch.as_tensor(b, device="cuda", dtype=torch.float32).reshape(n, -1).div_(255.)
        ma, mb = xa.mean(0), xb.mean(0)
        if n == 1:
            va = torch.zeros_like(ma)
            vb = torch.zeros_like(mb)
        else:
            va = xa.var(0, unbiased=True)
            vb = xb.var(0, unbiased=True)
        den = va/n + vb/n + floor**2
        numerator = (ma-mb).square()
        if bool(torch.all(den == 0)):
            return 0.0 if bool(torch.all(numerator == 0)) else float("inf")
        score = torch.sqrt(torch.mean(numerator / den))
        return float(score.item())


def fft2_batch(images, *, device="auto"):
    """FFT-shifted magnitude and phase for [batch,h,w] real images.

    Returns NumPy arrays so downstream semantics stay unchanged.
    """
    x = np.asarray(images)
    if x.ndim == 2:
        x = x[None, ...]
    if x.ndim != 3:
        raise ValueError("expected [batch,h,w] or [h,w]")
    resolved = resolve_device(device)
    # Inputs already live on the host. Share the original centering operation
    # so CUDA reduction order cannot introduce a different near-zero DC phase.
    values = x.astype(np.float32)
    centered = values - values.mean(axis=(-2, -1), keepdims=True)
    if resolved == "cpu":
        spectrum = np.fft.fftshift(np.fft.fft2(centered, axes=(-2,-1)), axes=(-2,-1))
        return np.abs(spectrum), np.angle(spectrum)

    torch = _torch()
    with torch.inference_mode():
        tensor = torch.as_tensor(centered, device="cuda", dtype=torch.float32)
        spectrum = torch.fft.fftshift(torch.fft.fft2(tensor), dim=(-2,-1))
        magnitude = torch.abs(spectrum).cpu().numpy()
        phase = torch.angle(spectrum).cpu().numpy()
    return magnitude, phase
