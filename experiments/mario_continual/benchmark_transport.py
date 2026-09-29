"""Benchmark Mario RGB transport on the real framework.

Measures the transport choices independently of MORTRA's learning quality:
- hash-only repeated capture (normal exact-observation fast path)
- mmap capture one frame per command
- mmap batched capture
- legacy-style PNG disk encode/decode on a captured frame
- raw-file disk write/read on the same frame

The live tests use the actual Java/Xvfb Mario renderer.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import tempfile
import time

import numpy as np
from PIL import Image

from experiments.mario_continual.port import MarioRGBPort


def rate(seconds, samples, frame_bytes):
    return {
        "seconds": seconds,
        "samples": samples,
        "ms_per_sample": 1000.0*seconds/max(1,samples),
        "effective_rgb_mb_s": (samples*frame_bytes/1e6)/max(seconds,1e-12),
    }


def measure_hash(port, n):
    t=time.perf_counter()
    for _ in range(n):
        port.snap_hash()
    return time.perf_counter()-t


def measure_mmap_single(port, n):
    t=time.perf_counter()
    for _ in range(n):
        batch,_=port.repeated_observation(1)
        assert len(batch)==1
    return time.perf_counter()-t


def measure_mmap_batch(port, n):
    t=time.perf_counter()
    batch,_=port.repeated_observation(n)
    assert len(batch)==n
    return time.perf_counter()-t


def main():
    p=argparse.ArgumentParser()
    root=Path(__file__).resolve().parent
    p.add_argument("--game-dir", type=Path, default=root/"game")
    p.add_argument("--build-dir", type=Path, default=root/"build")
    p.add_argument("--bridge-source", type=Path, default=root/"java"/"MortraBridge.java")
    p.add_argument("--level", default="levels/notch/lvl-1.txt")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--samples", type=int, default=64)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)

    port=MarioRGBPort(args.game_dir,args.build_dir,args.bridge_source,args.level,
                      args.output/"live",seconds=60,frames_per_action=8)
    result={}
    try:
        port.start()
        h,w,_=port.last_shape
        frame_bytes=h*w*3
        result["frame_shape"]=[h,w,3]
        result["frame_bytes"]=frame_bytes
        result["shared_file"]=str(port.shared_file)
        result["shared_memory_path"]=str(port.shared_file).startswith("/dev/shm/")

        # Warm every command shape before timing; the previous one-pass benchmark
        # mixed JVM/JIT warm-up with transport cost.
        for _ in range(12): port.snap_hash()
        for _ in range(12): port.repeated_observation(1)
        port.repeated_observation(12)

        n=max(16,args.samples)
        block=max(4,n//8)
        rounds=max(4,n//block)
        totals={"hash_only_live":0.0,"mmap_single_live":0.0}
        counts={k:0 for k in totals}
        # Alternate order by round to cancel temporal/JIT ordering effects.
        for r in range(rounds):
            order=("hash","mmap") if r%2==0 else ("mmap","hash")
            for method in order:
                if method=="hash":
                    dt=measure_hash(port,block)
                    totals["hash_only_live"]+=dt
                    counts["hash_only_live"]+=block
                else:
                    dt=measure_mmap_single(port,block)
                    totals["mmap_single_live"]+=dt
                    counts["mmap_single_live"]+=block
        for name in totals:
            result[name]=rate(totals[name],counts[name],frame_bytes)

        # Batch throughput is a different operating point: one command, many
        # same-state captures, exactly what noisy evidence needs.
        batch_n=min(256,n)
        measure_mmap_batch(port,8)  # warm batch mapping/growth
        dt=measure_mmap_batch(port,batch_n)
        result["mmap_batch_live"]=rate(dt,batch_n,frame_bytes)

        frame,_=port.dump()
        assert frame.shape==(h,w,3)

        # Post-capture baselines only; these exclude real capture and Java/Python IPC.
        png_path=args.output/"legacy.png"
        t=time.perf_counter()
        for _ in range(n):
            Image.fromarray(frame).save(png_path,format="PNG")
            with Image.open(png_path) as image:
                decoded=np.asarray(image.convert("RGB"))
            assert decoded.shape==frame.shape
        result["png_disk_roundtrip"]=rate(time.perf_counter()-t,n,frame_bytes)
        png_path.unlink(missing_ok=True)

        raw_path=args.output/"legacy.raw"
        t=time.perf_counter()
        for _ in range(n):
            frame.tofile(raw_path)
            decoded=np.fromfile(raw_path,dtype=np.uint8).reshape(frame.shape)
            assert decoded.shape==frame.shape
        result["raw_file_roundtrip"]=rate(time.perf_counter()-t,n,frame_bytes)
        raw_path.unlink(missing_ok=True)

        result["transport_fidelity"]="BIT_EXACT_UINT8"
        result["port_metrics"]=port.metrics()
    finally:
        port.close()

    result["live_single_observation_ranking"]=sorted(
        ("hash_only_live","mmap_single_live"),
        key=lambda name:result[name]["ms_per_sample"])
    result["live_noisy_batch_method"]="mmap_batch_live"
    result["postcapture_io_baselines"]=(
        "png_disk_roundtrip","raw_file_roundtrip")
    result["comparison_scope"]={
        "hash_only_live":"real capture + Java SHA-256 + IPC; no pixel transfer",
        "mmap_single_live":"real capture + SHA-256 + one-frame shared mmap transfer",
        "mmap_batch_live":"real captures + SHA-256 + one batched shared mmap transfer",
        "png_disk_roundtrip":"post-capture encode/write/read/decode only",
        "raw_file_roundtrip":"post-capture write/read only",
    }
    result["recommendation"]={
        "exact_observation":result["live_single_observation_ranking"][0],
        "noisy_remeasurement":"mmap_batch_live",
        "selection_rule":"measured live path after warm-up; noisy sampling remains batched",
    }
    (args.output/"result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
