"""RGB-only odometry audit for the Mario 2826 causal routes.

Hypothesis
----------
A useful internal progress signal should not be "survival time".  It should
measure whether the visual world has advanced into a new region.  This probe
derives a dominant horizontal screen-motion direction from a common saved
prefix and then scores candidate routes by the furthest RGB-only odometry
position reached in that learned direction.

No completion value, Mario coordinate, engine position, or terminal percentage
is read by the odometry or candidate selector.  completion_audit_only is
attached only after each terminal trial for post-hoc validation.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import shutil

import numpy as np

from experiments.mario_continual.port import MarioRGBPort
from experiments.mario_continual.backward_causal_2826 import SEED, PAD

ROOT = Path(__file__).resolve().parent
MAX_ACTIONS = 250
ODOM_START = 145
LEARN_DIRECTION_END = 171
MAX_SHIFT = 64

BASE = list(SEED)
assert BASE[171] == 9
BASE[171] = 8
BASE.extend(PAD[:6])
BASE = tuple(BASE)
assert len(BASE) == 181

SURVIVAL = list(BASE)
assert SURVIVAL[177] == 2
SURVIVAL[177] = 3
SURVIVAL = tuple(SURVIVAL)

PROGRESS = list(BASE)
assert PROGRESS[176] == 1
PROGRESS[176] = 11
PROGRESS = tuple(PROGRESS)


def _gray(rgb):
    # Exclude HUD/top border and the extreme bottom.  This is a fixed camera
    # crop, not a Mario/world-coordinate feature.
    x = np.asarray(rgb, dtype=np.float32)[28:224]
    if x.ndim != 3 or x.shape[-1] != 3:
        raise ValueError("expected RGB frame")
    y = 0.299*x[..., 0] + 0.587*x[..., 1] + 0.114*x[..., 2]
    # Remove per-row/column brightness offsets and window the image so the FFT
    # is dominated by translated structure rather than hard frame boundaries.
    y = y - y.mean()
    wy = np.hanning(y.shape[0]).astype(np.float32)
    wx = np.hanning(y.shape[1]).astype(np.float32)
    return y * wy[:, None] * wx[None, :]


def phase_shift(previous_rgb, current_rgb):
    """Return (dx, dy, confidence) from RGB only.

    dx/dy are the integer translation of current relative to previous under
    phase correlation.  The sign convention does not matter: the progress
    direction is learned from the common prefix.
    """
    a = _gray(previous_rgb)
    b = _gray(current_rgb)
    fa = np.fft.rfft2(a)
    fb = np.fft.rfft2(b)
    cross = fa * np.conj(fb)
    mag = np.abs(cross)
    cross /= np.maximum(mag, 1e-7)
    corr = np.fft.irfft2(cross, s=a.shape).real

    # Ignore impossible large inter-action translations.
    h, w = corr.shape
    ys = np.concatenate([np.arange(0, min(MAX_SHIFT+1, h)),
                         np.arange(max(0, h-MAX_SHIFT), h)])
    xs = np.concatenate([np.arange(0, min(MAX_SHIFT+1, w)),
                         np.arange(max(0, w-MAX_SHIFT), w)])
    window = corr[np.ix_(ys, xs)]
    iy, ix = np.unravel_index(np.argmax(window), window.shape)
    py, px = int(ys[iy]), int(xs[ix])
    dy = py if py <= h//2 else py-h
    dx = px if px <= w//2 else px-w

    peak = float(window[iy, ix])
    # A robust local confidence proxy; used only for telemetry.
    flat = window.ravel()
    if flat.size > 1:
        second = float(np.partition(flat, -2)[-2])
    else:
        second = 0.0
    confidence = peak - second
    return float(dx), float(dy), confidence


def replay_with_odometry(name, planned, out_root, *, direction=None, continue_pad=False):
    directory = out_root / name
    if directory.exists():
        shutil.rmtree(directory)
    port = MarioRGBPort(
        ROOT/"game", ROOT/"build", ROOT/"java"/"MortraBridge.java",
        "levels/notch/lvl-1.txt", directory, seconds=60, frames_per_action=8)
    executed = 0
    samples = []
    previous = None
    x = 0.0
    max_pos = 0.0
    min_pos = 0.0
    prefix_dx = []
    try:
        _, packet = port.start()
        for action in planned:
            if packet["kind"] != "observation":
                break
            if executed >= ODOM_START and previous is None:
                previous, _ = port.dump()
            _, packet = port.step(action)
            executed += 1
            if packet["kind"] == "observation" and executed >= ODOM_START:
                current, _ = port.dump()
                if previous is not None:
                    dx, dy, conf = phase_shift(previous, current)
                    x += dx
                    if ODOM_START < executed <= LEARN_DIRECTION_END:
                        prefix_dx.append(dx)
                    if direction is not None:
                        pos = direction * x
                        max_pos = max(max_pos, pos)
                        min_pos = min(min_pos, pos)
                    samples.append(dict(step=executed, dx=dx, dy=dy,
                                        confidence=conf, cumulative_x=x))
                previous = current

        pad_index = 0
        while continue_pad and packet["kind"] == "observation" and executed < MAX_ACTIONS:
            action = PAD[pad_index % len(PAD)]
            _, packet = port.step(action)
            pad_index += 1
            executed += 1
            if packet["kind"] == "observation" and executed >= ODOM_START:
                current, _ = port.dump()
                if previous is not None:
                    dx, dy, conf = phase_shift(previous, current)
                    x += dx
                    if direction is not None:
                        pos = direction * x
                        max_pos = max(max_pos, pos)
                        min_pos = min(min_pos, pos)
                    samples.append(dict(step=executed, dx=dx, dy=dy,
                                        confidence=conf, cumulative_x=x))
                previous = current

        terminal = packet["kind"] == "terminal"
        return dict(
            executed=executed,
            status=packet.get("status") if terminal else "SURVIVED_SEQUENCE",
            terminal=terminal,
            completion_audit_only=packet.get("completion_audit_only") if terminal else None,
            cumulative_x=x,
            max_projected_position=max_pos if direction is not None else None,
            min_projected_position=min_pos if direction is not None else None,
            prefix_dx=prefix_dx,
            samples=samples,
        )
    finally:
        port.close()


def compact(row):
    return {k:v for k,v in row.items() if k not in ("samples", "prefix_dx")}


def main():
    out = Path("/tmp/rgb-odometry-2826")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # Learn the sign from the shared RGB prefix only.
    learn = replay_with_odometry("learn_direction", BASE[:LEARN_DIRECTION_END], out)
    signed = float(sum(learn["prefix_dx"]))
    if signed == 0.0:
        signed = float(np.median(learn["prefix_dx"])) if learn["prefix_dx"] else 0.0
    direction = 1.0 if signed >= 0 else -1.0

    rows = {}
    rows["stage1_48pct"] = replay_with_odometry(
        "stage1_48pct", BASE, out, direction=direction)
    rows["survival_45pct"] = replay_with_odometry(
        "survival_45pct", SURVIVAL, out, direction=direction, continue_pad=True)
    rows["progress_51pct"] = replay_with_odometry(
        "progress_51pct", PROGRESS, out, direction=direction)

    # Selector uses RGB odometry only.
    selected_name, selected = max(
        rows.items(),
        key=lambda kv: (kv[1]["max_projected_position"],
                        kv[1]["cumulative_x"]*direction,
                        -kv[1]["executed"],
                        kv[0])
    )

    result = dict(
        experiment="rgb_only_phase_odometry_progress_probe",
        odometry_inputs=["RGB frames", "executed action boundaries"],
        forbidden_selector_inputs=[
            "completion_audit_only", "world coordinates", "Mario position",
            "terminal percentage"
        ],
        learned_direction=direction,
        learned_prefix_signed_sum=signed,
        rows={k: compact(v) for k,v in rows.items()},
        selected_by_rgb_odometry=selected_name,
        selected_completion_audit_only=selected["completion_audit_only"],
        selected_over_50=bool((selected["completion_audit_only"] or 0.0) >= 0.5),
    )
    Path("/tmp/rgb_odometry_2826.json").write_text(
        json.dumps(result, indent=2, sort_keys=True))
    print("RGB_ODOMETRY_RESULT", json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
