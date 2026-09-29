import numpy as np
import pytest

from experiments.accelerator import device_info, fft2_batch, resolve_device, z_score_rgb_batches


def test_cpu_device_is_always_available():
    assert resolve_device("cpu") == "cpu"
    info = device_info("cpu")
    assert info["resolved"] == "cpu"


def test_cpu_rgb_z_score_matches_direct_formula():
    rng = np.random.default_rng(29)
    a = rng.integers(0, 256, size=(32, 5, 4, 3), dtype=np.uint8)
    b = rng.integers(0, 256, size=(32, 5, 4, 3), dtype=np.uint8)
    actual = z_score_rgb_batches(a, b, noise_floor=.01, reference_n=32, device="cpu")

    xa = a.reshape(32, -1).astype(np.float32)/255.
    xb = b.reshape(32, -1).astype(np.float32)/255.
    ma, mb = xa.mean(0), xb.mean(0)
    va, vb = xa.var(0, ddof=1), xb.var(0, ddof=1)
    expected = np.sqrt(np.mean((ma-mb)**2/(va/32+vb/32+.01**2)))
    assert actual == pytest.approx(float(expected), rel=2e-6, abs=2e-6)


def test_cpu_fft_batch_matches_numpy():
    rng = np.random.default_rng(30)
    x = rng.normal(size=(3, 8, 8)).astype(np.float32)
    mag, phase = fft2_batch(x, device="cpu")
    centered = x-x.mean(axis=(-2,-1), keepdims=True)
    reference = np.fft.fftshift(np.fft.fft2(centered, axes=(-2,-1)), axes=(-2,-1))
    assert np.allclose(mag, np.abs(reference), rtol=1e-5, atol=1e-5)
    assert np.allclose(np.exp(1j*phase), np.exp(1j*np.angle(reference)), rtol=1e-5, atol=1e-5)


def test_explicit_cuda_fails_cleanly_when_unavailable():
    info = device_info("auto")
    if not info["cuda_available"]:
        with pytest.raises(RuntimeError):
            resolve_device("cuda")
