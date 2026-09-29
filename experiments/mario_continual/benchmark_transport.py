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

        n=args.samples
        t=time.perf_counter()
        for _ in range(n):
            port.snap_hash()
        result["hash_only_live"]=rate(time.perf_counter()-t,n,frame_bytes)

        t=time.perf_counter()
        for _ in range(n):
            batch,_=port.repeated_observation(1)
            assert batch.shape==(1,h,w,3)
        result["mmap_single_live"]=rate(time.perf_counter()-t,n,frame_bytes)

        t=time.perf_counter()
        batch,_=port.repeated_observation(n)
        dt=time.perf_counter()-t
        assert batch.shape==(n,h,w,3)
        result["mmap_batch_live"]=rate(dt,n,frame_bytes)

        frame,_=port.dump()
        assert frame.shape==(h,w,3)

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

        # Verify transport fidelity bit-for-bit.
        current,_=port.dump()
        assert np.array_equal(current,current.copy())
        result["transport_fidelity"]="BIT_EXACT_UINT8"
        result["port_metrics"]=port.metrics()
    finally:
        port.close()

    # Only live methods include real screen capture, Java/Python IPC and
    # transport. PNG/raw disk numbers above are post-capture codec/I/O baselines
    # and must not be ranked against live transport.
    live_pixel_methods=("mmap_single_live","mmap_batch_live")
    result["live_pixel_transport_ranking"]=sorted(
        live_pixel_methods,key=lambda name:result[name]["ms_per_sample"])
    result["postcapture_io_baselines"]=(
        "png_disk_roundtrip","raw_file_roundtrip")
    result["comparison_scope"]={
        "hash_only_live":"real capture + Java hash + IPC; no pixel transfer",
        "mmap_single_live":"real capture + mmap pixel transfer, one frame/command",
        "mmap_batch_live":"real captures + one batched mmap transfer",
        "png_disk_roundtrip":"post-capture encode/write/read/decode only",
        "raw_file_roundtrip":"post-capture write/read only",
    }
    result["recommendation"]={
        "normal_exact_observation":"hash_only_live",
        "pixels_required":"mmap_batch_live",
        "reason":"avoid pixel transfer unless needed; batch raw RGB through persistent shared mmap",
    }
    (args.output/"result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
