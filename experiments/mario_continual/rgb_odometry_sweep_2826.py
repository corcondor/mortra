"""Exhaustive RGB-only ranking of the 110 second-stage Mario interventions.

The candidate set is fixed before this test: ten positions immediately before
failure, eleven alternative actions at each position.  The selector is frozen
as RGB phase-odometry frontier reached in the dominant direction learned from
the common prefix.  completion_audit_only is excluded from selector records
and used only after selection for audit/correlation.
"""
from __future__ import annotations

from pathlib import Path
import json
import shutil

import numpy as np
from scipy.stats import spearmanr

from experiments.mario_continual.backward_causal_improved_2826 import BASE, SWEEP_OFFSETS
from experiments.mario_continual.rgb_odometry_2826 import (
    LEARN_DIRECTION_END,
    replay_with_odometry,
    compact,
)

OUT = Path("/tmp/rgb-odometry-sweep-2826")


def selector_record(row):
    # Deliberately construct a new object that contains no audit outcome.
    return dict(
        candidate_id=row["candidate_id"],
        offset=row["offset"],
        index=row["index"],
        original_action=row["original_action"],
        action=row["action"],
        max_projected_position=row["max_projected_position"],
        net_projected_position=row["net_projected_position"],
        min_projected_position=row["min_projected_position"],
    )


def rank_key(r):
    # RGB-only.  No terminal status, survival duration, completion, or world x.
    return (
        r["max_projected_position"],
        r["net_projected_position"],
        r["min_projected_position"],
        -r["offset"],
        -r["action"],
    )


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    learn = replay_with_odometry(
        "learn_direction", BASE[:LEARN_DIRECTION_END], OUT)
    signed = float(sum(learn["prefix_dx"]))
    if signed == 0.0:
        signed = float(np.median(learn["prefix_dx"])) if learn["prefix_dx"] else 0.0
    direction = 1.0 if signed >= 0 else -1.0

    audits = []
    selector_rows = []
    for offset in SWEEP_OFFSETS:
        index = len(BASE) - offset
        original = BASE[index]
        for action in range(12):
            if action == original:
                continue
            candidate_id = f"off{offset}_a{action}"
            planned = list(BASE)
            planned[index] = action
            raw = replay_with_odometry(
                candidate_id, tuple(planned), OUT,
                direction=direction, continue_pad=True)
            row = compact(raw)
            row.update(
                candidate_id=candidate_id,
                offset=offset,
                index=index,
                original_action=original,
                action=action,
                net_projected_position=direction*row["cumulative_x"],
            )
            audits.append(row)
            selector_rows.append(selector_record(row))
            print("RGB_CANDIDATE", json.dumps({
                **selector_rows[-1],
                "audit_completion": row["completion_audit_only"],
                "audit_status": row["status"],
            }, sort_keys=True), flush=True)

    selected_policy = max(selector_rows, key=rank_key)
    audit_by_id = {r["candidate_id"]: r for r in audits}
    selected_audit = audit_by_id[selected_policy["candidate_id"]]

    comparable = [
        r for r in audits if r["completion_audit_only"] is not None
    ]
    x = np.asarray([r["max_projected_position"] for r in comparable], dtype=float)
    y = np.asarray([r["completion_audit_only"] for r in comparable], dtype=float)
    pearson = float(np.corrcoef(x, y)[0, 1]) if len(x) > 1 and np.ptp(x) > 0 and np.ptp(y) > 0 else None
    spear = spearmanr(x, y)
    spearman = float(spear.statistic) if np.isfinite(spear.statistic) else None

    audit_best = max(comparable, key=lambda r: r["completion_audit_only"])
    top_rgb = sorted(selector_rows, key=rank_key, reverse=True)[:10]
    top_rgb_audit = [
        dict(**r, completion_audit_only=audit_by_id[r["candidate_id"]]["completion_audit_only"],
             status=audit_by_id[r["candidate_id"]]["status"],
             executed=audit_by_id[r["candidate_id"]]["executed"])
        for r in top_rgb
    ]

    result = dict(
        experiment="exhaustive_rgb_only_odometry_ranking_second_stage_2826",
        candidates=len(audits),
        selector_inputs=["RGB phase odometry", "executed action boundaries"],
        selector_excludes=[
            "completion_audit_only", "world coordinates", "Mario position",
            "terminal status", "survival duration",
        ],
        learned_direction=direction,
        learned_prefix_signed_sum=signed,
        selected_by_rgb=selected_policy,
        selected_audit=dict(
            completion_audit_only=selected_audit["completion_audit_only"],
            status=selected_audit["status"],
            executed=selected_audit["executed"],
        ),
        selected_over_50=bool(
            (selected_audit["completion_audit_only"] or 0.0) >= 0.5
        ),
        audit_best_posthoc=dict(
            candidate_id=audit_best["candidate_id"],
            offset=audit_best["offset"],
            index=audit_best["index"],
            action=audit_best["action"],
            completion_audit_only=audit_best["completion_audit_only"],
            max_projected_position=audit_best["max_projected_position"],
        ),
        selected_is_audit_best=(
            selected_policy["candidate_id"] == audit_best["candidate_id"]
        ),
        posthoc_correlation=dict(
            terminal_candidates=len(comparable),
            pearson_frontier_vs_completion=pearson,
            spearman_frontier_vs_completion=spearman,
        ),
        top10_rgb_with_posthoc_audit=top_rgb_audit,
    )
    Path("/tmp/rgb_odometry_sweep_2826.json").write_text(
        json.dumps(result, indent=2, sort_keys=True))
    print("RGB_SWEEP_RESULT", json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
