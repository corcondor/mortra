import numpy as np
import pytest

from experiments.accelerator import device_info
from experiments.accelerator import fft2_batch
from experiments.mario_continual import validate_cuda


def test_validation_uses_explicit_devices_and_complex_spectrum(monkeypatch):
    calls = []

    def z(a, b, *, device):
        calls.append(("z", device))
        return 0.0

    def fft(a, *, device):
        calls.append(("fft", device))
        # Zero amplitude must not compare meaningless phase values.
        return np.zeros(a.shape), np.ones(a.shape) * (1 if device == "cpu" else -1)

    monkeypatch.setattr(validate_cuda, "z_score_rgb_batches", z)
    monkeypatch.setattr(validate_cuda, "fft2_batch", fft)
    a = np.zeros((2, 2, 2, 3), dtype=np.uint8)
    result = validate_cuda.check_kernels(a, a)
    assert calls == [("z", "cpu"), ("z", "cuda"), ("fft", "cpu"), ("fft", "cuda")]
    assert result["fft_max_normalized_error"] == 0


def test_validation_rejects_wrong_cuda_result(monkeypatch):
    monkeypatch.setattr(validate_cuda, "z_score_rgb_batches",
                        lambda a, b, *, device: 0.0 if device == "cpu" else 1.0)
    with pytest.raises(AssertionError):
        validate_cuda.check_kernels(np.zeros((2, 2, 2, 3), dtype=np.uint8),
                                   np.zeros((2, 2, 2, 3), dtype=np.uint8))


def test_fft_centering_preserves_cpu_reference():
    rng = np.random.default_rng(20260930)
    gray = rng.integers(0, 256, (32, 24, 24, 3), dtype=np.uint8).astype(np.float32).mean(-1)
    centered = gray - gray.mean(axis=(-2, -1), keepdims=True)
    expected = np.fft.fftshift(np.fft.fft2(centered), axes=(-2, -1))
    magnitude, phase = fft2_batch(gray, device="cpu")
    np.testing.assert_allclose(magnitude * np.exp(1j * phase), expected,
                               rtol=2e-6, atol=2e-3)


@pytest.mark.skipif(not device_info("auto")["cuda_available"], reason="CUDA hardware required")
@pytest.mark.parametrize("n", [1, 8, 32, 128])
def test_actual_cuda_kernels(n):
    rng = np.random.default_rng(20260929 + n)
    a = rng.integers(0, 256, (n, 24, 24, 3), dtype=np.uint8)
    b = rng.integers(0, 256, a.shape, dtype=np.uint8)
    validate_cuda.check_kernels(a, b)
