"""T4/L4/A100 validation for MORTRA's accelerated perception path.

This script is intentionally strict:
- requires a real CUDA device;
- compares CUDA RGB z-scores against the CPU reference on several batch sizes;
- compares CUDA FFT magnitude/phase against NumPy;
- captures actual Mario frames through the hash+mmap bridge and compares
  CPU/CUDA evidence on those real frames;
- writes one machine-readable receipt.

The Java game, predictive graph and planners remain CPU-side by design.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics as py_statistics
import time

import numpy as np

from experiments.accelerator import device_info, fft2_batch, z_score_rgb_batches
from experiments.mario_continual.port import MarioRGBPort


def timed(call, warmup=3, repeats=8):
    for _ in range(warmup):
        call()
    values=[]
    for _ in range(repeats):
        t=time.perf_counter()
        call()
        values.append(time.perf_counter()-t)
    return dict(
        repeats=repeats,
        mean_ms=1000*py_statistics.mean(values),
        median_ms=1000*py_statistics.median(values),
        min_ms=1000*min(values),
        max_ms=1000*max(values),
    )


def compare_z(rng):
    rows=[]
    for n in (8,32,128):
        a=rng.integers(0,256,size=(n,64,64,3),dtype=np.uint8)
        b=rng.integers(0,256,size=(n,64,64,3),dtype=np.uint8)
        cpu=z_score_rgb_batches(a,b,device="cpu")
        cuda=z_score_rgb_batches(a,b,device="cuda")
        abs_error=abs(cpu-cuda)
        rel_error=abs_error/max(abs(cpu),1e-12)
        if not (abs_error <= 3e-5 or rel_error <= 3e-5):
            raise AssertionError(
                f"RGB z-score CPU/CUDA mismatch n={n}: cpu={cpu} cuda={cuda}")
        rows.append(dict(n=n,cpu=cpu,cuda=cuda,
                         abs_error=abs_error,rel_error=rel_error))
    return rows


def compare_fft(rng):
    x=rng.normal(size=(8,64,64)).astype(np.float32)
    cpu_mag,cpu_phase=fft2_batch(x,device="cpu")
    gpu_mag,gpu_phase=fft2_batch(x,device="cuda")
    mag_error=float(np.max(np.abs(cpu_mag-gpu_mag)))
    mag_scale=max(float(np.max(cpu_mag)),1e-12)
    mag_rel=mag_error/mag_scale
    # Phase is undefined where magnitude is effectively zero; compare unit
    # phasors only on supported coefficients.
    support=cpu_mag > 1e-5*mag_scale
    phase_complex_cpu=np.exp(1j*cpu_phase[support])
    phase_complex_gpu=np.exp(1j*gpu_phase[support])
    phase_error=float(np.max(np.abs(phase_complex_cpu-phase_complex_gpu))) if np.any(support) else 0.0
    if mag_rel > 2e-5:
        raise AssertionError(f"FFT magnitude mismatch: rel={mag_rel}")
    if phase_error > 2e-4:
        raise AssertionError(f"FFT phase mismatch: unit-phasor error={phase_error}")
    return dict(
        shape=list(x.shape),
        magnitude_max_abs_error=mag_error,
        magnitude_relative_error=mag_rel,
        phase_unit_phasor_max_error=phase_error,
        compared_phase_coefficients=int(np.sum(support)),
    )


def benchmark_synthetic(rng):
    a=rng.integers(0,256,size=(128,64,64,3),dtype=np.uint8)
    b=rng.integers(0,256,size=(128,64,64,3),dtype=np.uint8)
    x=rng.normal(size=(64,128,128)).astype(np.float32)
    return dict(
        z_cpu=timed(lambda:z_score_rgb_batches(a,b,device="cpu"),warmup=2,repeats=6),
        z_cuda=timed(lambda:z_score_rgb_batches(a,b,device="cuda"),warmup=4,repeats=12),
        fft_cpu=timed(lambda:fft2_batch(x,device="cpu"),warmup=2,repeats=5),
        fft_cuda=timed(lambda:fft2_batch(x,device="cuda"),warmup=4,repeats=10),
    )


def real_mario_check(args):
    directory=args.output/"real_mario"
    port=MarioRGBPort(
        args.game_dir,args.build_dir,args.bridge_source,args.level,directory,
        seconds=60,frames_per_action=8)
    try:
        _,initial_packet=port.start()
        first,_=port.repeated_observation(32)
        _,step_packet=port.step(4)
        if step_packet["kind"] != "observation":
            raise RuntimeError(f"Mario terminated during GPU validation: {step_packet}")
        second,_=port.repeated_observation(32)
        if first.shape != second.shape:
            raise AssertionError((first.shape,second.shape))

        cpu=z_score_rgb_batches(first,second,device="cpu")
        cuda=z_score_rgb_batches(first,second,device="cuda")
        err=abs(cpu-cuda)
        if not (err <= 3e-5 or err/max(abs(cpu),1e-12) <= 3e-5):
            raise AssertionError(f"real Mario CPU/CUDA evidence mismatch {cpu} {cuda}")

        # Real-frame FFT parity on luminance.
        def gray(batch):
            x=batch.astype(np.float32)
            return .2126*x[...,0]+.7152*x[...,1]+.0722*x[...,2]
        c_mag,c_phase=fft2_batch(gray(first[:8]),device="cpu")
        g_mag,g_phase=fft2_batch(gray(first[:8]),device="cuda")
        mag_scale=max(float(np.max(c_mag)),1e-12)
        mag_rel=float(np.max(np.abs(c_mag-g_mag)))/mag_scale
        support=c_mag > 1e-5*mag_scale
        phase_err=float(np.max(np.abs(
            np.exp(1j*c_phase[support])-np.exp(1j*g_phase[support])
        ))) if np.any(support) else 0.0
        if mag_rel > 3e-5 or phase_err > 3e-4:
            raise AssertionError(
                f"real Mario FFT parity failed mag={mag_rel} phase={phase_err}")

        return dict(
            initial_packet={k:v for k,v in initial_packet.items()
                            if not k.startswith("_")},
            after_action_packet={k:v for k,v in step_packet.items()
                                 if not k.startswith("_")},
            batch_shape=list(first.shape),
            cpu_z=cpu,cuda_z=cuda,abs_error=err,
            fft_magnitude_relative_error=mag_rel,
            fft_phase_unit_phasor_error=phase_err,
            port_metrics=port.metrics(),
        )
    finally:
        port.close()


def main():
    p=argparse.ArgumentParser()
    root=Path(__file__).resolve().parent
    p.add_argument("--game-dir",type=Path,default=root/"game")
    p.add_argument("--build-dir",type=Path,default=root/"build")
    p.add_argument("--bridge-source",type=Path,default=root/"java"/"MortraBridge.java")
    p.add_argument("--level",default="levels/notch/lvl-1.txt")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--skip-real-mario",action="store_true")
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)

    info=device_info("cuda")
    if info["resolved"]!="cuda" or not info["cuda_available"]:
        raise RuntimeError(f"real CUDA device required: {info}")

    rng=np.random.default_rng(20260929)
    result=dict(
        status="STARTED",
        device=info,
        synthetic_z_parity=compare_z(rng),
        synthetic_fft_parity=compare_fft(rng),
        synthetic_benchmark=benchmark_synthetic(rng),
    )
    if not args.skip_real_mario:
        result["real_mario"]=real_mario_check(args)
    result["status"]="CUDA_VALIDATION_PASS"
    (args.output/"GPU_VALIDATION.json").write_text(
        json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf8")
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
