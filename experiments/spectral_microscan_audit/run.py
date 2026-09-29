"""Exact post-hoc audit of micro-scanning and screen-frequency change.

This experiment uses the frozen PhysicsArena3D renderer only as an environment.
The audit may inspect raw states to score correctness, but the sensor signatures
are computed only from the first-person RGB image.

It tests three questions:
1. Can four half-cell detector offsets recover spatial frequencies lost by one
   coarse sampling lattice?
2. Do those offsets reduce predictive aliasing without a fixed hand-selected
   probe?
3. Does Fourier magnitude/phase change detect action-induced visual state
   changes?

No control policy is evaluated here.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import json
from pathlib import Path

import numpy as np

from experiments.accelerator import device_info, fft2_batch
from experiments.noisy_rgb_discovery.reference.physics3d import PhysicsArena3D

FFT_DEVICE = "cpu"
OFFSETS = ((0, 0), (2, 0), (0, 2), (2, 2))
ACTIONS = tuple(range(5))


def reachable(game):
    seen = {game.start_raw}
    queue = deque([game.start_raw])
    while queue:
        state = queue.popleft()
        for action in ACTIONS:
            nxt = game.raw_step(state, action)
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return sorted(seen)


def gray_screen(game, state):
    rgb = game.render_views(state, 48)[3].astype(np.float64)
    # Fixed luminance map; scoring never sees raw state variables.
    return (0.2126*rgb[...,0] + 0.7152*rgb[...,1] + 0.0722*rgb[...,2])


def sample(image, offset):
    dx, dy = offset
    return image[dy:48:4, dx:48:4].copy()


def microscan(image):
    result = np.empty((24, 24), dtype=np.float64)
    result[0::2, 0::2] = sample(image, (0, 0))
    result[0::2, 1::2] = sample(image, (2, 0))
    result[1::2, 0::2] = sample(image, (0, 2))
    result[1::2, 1::2] = sample(image, (2, 2))
    return result


def target24(image):
    return image[0:48:2, 0:48:2].copy()


def baseline24(image):
    return np.repeat(np.repeat(sample(image, (0, 0)), 2, axis=0), 2, axis=1)


def quantize(array, bits=3):
    levels = 1 << bits
    q = np.floor(np.clip(array, 0, 255) * levels / 256.).astype(np.uint8)
    return q.tobytes()


def fft_parts(image):
    magnitude, phase = fft2_batch(np.asarray(image), device=FFT_DEVICE)
    return magnitude[0], phase[0]


def normalized_magnitude_code(image, bins=16):
    mag, _ = fft_parts(image)
    scale = float(np.max(mag))
    if scale <= 1e-12:
        q = np.zeros_like(mag, dtype=np.uint8)
    else:
        x = np.log1p(mag) / np.log1p(scale)
        q = np.floor(np.clip(x, 0, 1) * (bins-1) + 1e-12).astype(np.uint8)
    return q.tobytes()


def spectral_change(a, b):
    ma, pa = fft_parts(a)
    mb, pb = fft_parts(b)
    denom = max(float(np.linalg.norm(ma)), float(np.linalg.norm(mb)), 1e-12)
    magnitude_change = float(np.linalg.norm(ma-mb) / denom)
    support = (ma > 1e-8*max(float(ma.max()), 1.0)) & (mb > 1e-8*max(float(mb.max()), 1.0))
    if np.any(support):
        delta = np.angle(np.exp(1j*(pb-pa)))
        phase_rms = float(np.sqrt(np.mean(delta[support]**2)))
    else:
        phase_rms = 0.0
    return magnitude_change, phase_rms


def high_frequency_energy(image):
    mag, _ = fft_parts(image)
    n = image.shape[0]
    coords = np.arange(-n//2, n//2)
    yy, xx = np.meshgrid(coords, coords, indexing="ij")
    # Frequencies beyond the 12x12 detector's axis Nyquist (6 cycles / field).
    mask = (np.abs(xx) > 5) | (np.abs(yy) > 5)
    return float(np.sum(mag[mask]**2))


def predictive_partition(states, game, screens):
    """Exact first-person predictive quotient used only for post-hoc scoring."""
    index={s:i for i,s in enumerate(states)}
    observation=[screens[s].astype(np.float32).tobytes() for s in states]
    labels={}
    next_label=0
    obs_to_label={}
    for i,obs in enumerate(observation):
        if obs not in obs_to_label:
            obs_to_label[obs]=next_label
            next_label+=1
        labels[i]=obs_to_label[obs]
    depth=0
    while True:
        sig_to_label={}
        refined={}
        for i,s in enumerate(states):
            sig=(labels[i], tuple(labels[index[game.raw_step(s,a)]] for a in ACTIONS))
            if sig not in sig_to_label:
                sig_to_label[sig]=len(sig_to_label)
            refined[i]=sig_to_label[sig]
        depth+=1
        if all(refined[i]==labels[i] for i in range(len(states))):
            break
        # Canonical numeric ids can permute even when the partition is stable.
        old_groups=defaultdict(set)
        new_groups=defaultdict(set)
        for i in range(len(states)):
            old_groups[labels[i]].add(i)
            new_groups[refined[i]].add(i)
        if {frozenset(v) for v in old_groups.values()} == {frozenset(v) for v in new_groups.values()}:
            labels=refined
            break
        labels=refined
    return {s:labels[index[s]] for s in states}, depth


def predictive_conflicts(states, game, code_by_state, truth_class):
    groups = defaultdict(list)
    for s in states:
        groups[code_by_state[s]].append(s)
    conflict_groups = 0
    conflict_state_actions = 0
    total_repeated_state_actions = 0
    examples = []
    for code, members in groups.items():
        if len(members) < 2:
            continue
        for action in ACTIONS:
            outcomes = defaultdict(list)
            for s in members:
                nxt = game.raw_step(s, action)
                outcomes[truth_class[nxt]].append(s)
            total_repeated_state_actions += len(members)
            if len(outcomes) > 1:
                conflict_groups += 1
                conflict_state_actions += len(members)
                if len(examples) < 4:
                    examples.append(dict(group_size=len(members), action=action,
                                         outcome_count=len(outcomes)))
    alias_states=sum(len(v) for v in groups.values()
                     if len({truth_class[s] for s in v})>1)
    total_state_actions=len(states)*len(ACTIONS)
    return dict(
        groups=len(groups),
        alias_groups=sum(len({truth_class[s] for s in v})>1 for v in groups.values()),
        alias_states=alias_states,
        alias_state_fraction=alias_states/max(1,len(states)),
        max_alias=max(map(len, groups.values()), default=0),
        conflict_group_actions=conflict_groups,
        conflict_state_actions=conflict_state_actions,
        total_state_actions=total_state_actions,
        repeated_state_actions=total_repeated_state_actions,
        conflict_fraction_within_repeated=(
            conflict_state_actions/total_repeated_state_actions
            if total_repeated_state_actions else 0.0),
        conflict_fraction_all=conflict_state_actions/max(1,total_state_actions),
        examples=examples,
    )


def active_offset_depth(states, codes, truth_class):
    base_groups = defaultdict(list)
    for s in states:
        base_groups[codes[s][(0,0)]].append(s)

    depth_counts = Counter()
    unresolved = 0
    for members in base_groups.values():
        if len({truth_class[s] for s in members}) <= 1:
            depth_counts[0] += len(members)
            continue
        for target in members:
            candidates = set(members)
            remaining = [(2,0),(0,2),(2,2)]
            depth = 0
            while len({truth_class[s] for s in candidates}) > 1 and remaining:
                # Generic minimax split: no fixed preferred offset.
                scored = []
                for off in remaining:
                    buckets = Counter(codes[s][off] for s in candidates)
                    scored.append((max(buckets.values()), -len(buckets), off))
                _, _, chosen = min(scored)
                remaining.remove(chosen)
                target_code = codes[target][chosen]
                candidates = {s for s in candidates if codes[s][chosen] == target_code}
                depth += 1
            if len({truth_class[s] for s in candidates}) == 1:
                depth_counts[depth] += 1
            else:
                unresolved += 1
    total = len(states)
    initial_ambiguous=sum(len(v) for v in base_groups.values()
                          if len({truth_class[s] for s in v})>1)
    resolved_from_ambiguous=initial_ambiguous-unresolved
    mean_depth = sum(k*v for k,v in depth_counts.items()) / max(1, total)
    return dict(depth_histogram=dict(sorted(depth_counts.items())),
                initial_ambiguous_states=initial_ambiguous,
                resolved_from_ambiguous=resolved_from_ambiguous,
                resolution_rate=(resolved_from_ambiguous/max(1,initial_ambiguous)),
                unresolved_states=unresolved, total_states=total,
                mean_extra_offsets=mean_depth,
                max_resolved_depth=max(depth_counts, default=0))


def audit_world(seed):
    game = PhysicsArena3D(seed, "state_opaque")
    states = reachable(game)
    screens = {s: gray_screen(game, s) for s in states}
    truth_class, refinement_depth = predictive_partition(states, game, screens)

    base_codes = {s: quantize(sample(screens[s], (0,0)), 3) for s in states}
    micro_codes = {s: quantize(microscan(screens[s]), 3) for s in states}
    spectral_codes = {s: base_codes[s] + normalized_magnitude_code(microscan(screens[s]))
                      for s in states}
    offset_codes = {
        s: {off: quantize(sample(screens[s], off), 3) for off in OFFSETS}
        for s in states
    }

    base_mse = []
    micro_mse = []
    target_hf = []
    baseline_hf_error = []
    micro_hf_error = []
    for s in states:
        target = target24(screens[s])
        base = baseline24(screens[s])
        micro = microscan(screens[s])
        base_mse.append(float(np.mean((base-target)**2)))
        micro_mse.append(float(np.mean((micro-target)**2)))
        target_energy = high_frequency_energy(target)
        target_hf.append(target_energy)
        baseline_hf_error.append(abs(high_frequency_energy(base)-target_energy))
        micro_hf_error.append(abs(high_frequency_energy(micro)-target_energy))

    changed = unchanged = 0
    base_detect = mag_detect = phase_detect = 0
    base_false = mag_false = phase_false = 0
    spectral_samples = []
    for s in states:
        for action in ACTIONS:
            nxt = game.raw_step(s, action)
            state_changed = truth_class[nxt] != truth_class[s]
            base_changed = base_codes[nxt] != base_codes[s]
            mchange, pchange = spectral_change(microscan(screens[s]), microscan(screens[nxt]))
            mag_changed = mchange > 1e-12
            phase_changed = pchange > 1e-12
            if state_changed:
                changed += 1
                base_detect += base_changed
                mag_detect += mag_changed
                phase_detect += phase_changed
            else:
                unchanged += 1
                base_false += base_changed
                mag_false += mag_changed
                phase_false += phase_changed
            if len(spectral_samples) < 8 and state_changed:
                spectral_samples.append(dict(action=action,
                    magnitude_change=mchange, phase_rms=pchange,
                    base_changed=base_changed))

    return dict(
        seed=seed, states=len(states),
        reconstruction=dict(
            base_mse_mean=float(np.mean(base_mse)),
            micro_mse_mean=float(np.mean(micro_mse)),
            micro_exact_count=sum(x == 0.0 for x in micro_mse),
            states=len(states),
            target_high_frequency_energy_mean=float(np.mean(target_hf)),
            baseline_high_frequency_energy_abs_error_mean=float(np.mean(baseline_hf_error)),
            micro_high_frequency_energy_abs_error_mean=float(np.mean(micro_hf_error)),
        ),
        predictive_aliasing=dict(
            predictive_classes=len(set(truth_class.values())),
            refinement_depth=refinement_depth,
            base=predictive_conflicts(states, game, base_codes, truth_class),
            micro=predictive_conflicts(states, game, micro_codes, truth_class),
            base_plus_spectrum=predictive_conflicts(states, game, spectral_codes, truth_class),
        ),
        active_microscan=active_offset_depth(states, offset_codes, truth_class),
        action_effect_detection=dict(
            predictive_changed_transitions=changed, predictive_unchanged_transitions=unchanged,
            base_detect_rate=base_detect/max(1,changed),
            magnitude_detect_rate=mag_detect/max(1,changed),
            phase_detect_rate=phase_detect/max(1,changed),
            base_false_positive_rate=base_false/max(1,unchanged),
            magnitude_false_positive_rate=mag_false/max(1,unchanged),
            phase_false_positive_rate=phase_false/max(1,unchanged),
            samples=spectral_samples,
        ),
    )


def aggregate(rows):
    def mean(path):
        vals=[]
        for row in rows:
            x=row
            for key in path:
                x=x[key]
            vals.append(float(x))
        return float(np.mean(vals))
    return dict(
        worlds=len(rows),
        states=sum(r["states"] for r in rows),
        reconstruction=dict(
            base_mse_mean=mean(("reconstruction","base_mse_mean")),
            micro_mse_mean=mean(("reconstruction","micro_mse_mean")),
            micro_exact_states=sum(r["reconstruction"]["micro_exact_count"] for r in rows),
            total_states=sum(r["states"] for r in rows),
            baseline_high_frequency_error_mean=mean(("reconstruction","baseline_high_frequency_energy_abs_error_mean")),
            micro_high_frequency_error_mean=mean(("reconstruction","micro_high_frequency_energy_abs_error_mean")),
        ),
        predictive_aliasing=dict(
            base_conflict_fraction_all=mean(("predictive_aliasing","base","conflict_fraction_all")),
            micro_conflict_fraction_all=mean(("predictive_aliasing","micro","conflict_fraction_all")),
            spectral_conflict_fraction_all=mean(("predictive_aliasing","base_plus_spectrum","conflict_fraction_all")),
            base_alias_state_fraction=mean(("predictive_aliasing","base","alias_state_fraction")),
            micro_alias_state_fraction=mean(("predictive_aliasing","micro","alias_state_fraction")),
            spectral_alias_state_fraction=mean(("predictive_aliasing","base_plus_spectrum","alias_state_fraction")),
            base_alias_groups=sum(r["predictive_aliasing"]["base"]["alias_groups"] for r in rows),
            micro_alias_groups=sum(r["predictive_aliasing"]["micro"]["alias_groups"] for r in rows),
            spectral_alias_groups=sum(r["predictive_aliasing"]["base_plus_spectrum"]["alias_groups"] for r in rows),
        ),
        active_microscan=dict(
            initial_ambiguous_states=sum(r["active_microscan"]["initial_ambiguous_states"] for r in rows),
            resolved_from_ambiguous=sum(r["active_microscan"]["resolved_from_ambiguous"] for r in rows),
            resolution_rate=(sum(r["active_microscan"]["resolved_from_ambiguous"] for r in rows)/
                             max(1,sum(r["active_microscan"]["initial_ambiguous_states"] for r in rows))),
            unresolved_states=sum(r["active_microscan"]["unresolved_states"] for r in rows),
            mean_extra_offsets=mean(("active_microscan","mean_extra_offsets")),
            max_resolved_depth=max(r["active_microscan"]["max_resolved_depth"] for r in rows),
        ),
        action_effect_detection=dict(
            base_detect_rate=mean(("action_effect_detection","base_detect_rate")),
            magnitude_detect_rate=mean(("action_effect_detection","magnitude_detect_rate")),
            phase_detect_rate=mean(("action_effect_detection","phase_detect_rate")),
            base_false_positive_rate=mean(("action_effect_detection","base_false_positive_rate")),
            magnitude_false_positive_rate=mean(("action_effect_detection","magnitude_false_positive_rate")),
            phase_false_positive_rate=mean(("action_effect_detection","phase_false_positive_rate")),
        ),
    )


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed-start", type=int, default=99029000)
    parser.add_argument("--worlds", type=int, default=16)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    args=parser.parse_args()
    global FFT_DEVICE
    FFT_DEVICE=args.device
    args.output.mkdir(parents=True, exist_ok=False)
    rows=[audit_world(seed) for seed in range(args.seed_start,args.seed_start+args.worlds)]
    result=dict(
        protocol=dict(
            environment="frozen PhysicsArena3D first-person 48x48 RGB",
            seeds=[args.seed_start,args.seed_start+args.worlds-1],
            base_detector="12x12 point samples, 3-bit luminance",
            micro_offsets=OFFSETS,
            micro_reconstruction="four half-cell lattices interleaved to 24x24",
            spectral="FFT magnitude/phase of 24x24 micro-scan",
            policy_use="none; post-hoc structural audit only",
            accelerator=device_info(args.device),
            hidden_state_use="reachable enumeration and scoring only; never sensor code",
        ),
        worlds=rows,
        aggregate=aggregate(rows),
    )
    (args.output/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result["aggregate"],indent=2))


if __name__=="__main__":
    main()
