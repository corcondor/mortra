"""Plots of recorded experiments only; no new game generation or decisions."""
import math
import numpy as np

from .run import SEEDS, CONDITIONS
from .proposal import FAMILIES


def plot(out, flat, generations, arms, endpoints, events, proposal_runs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"adaptive": "#187f63", "uniform": "#436fa9", "random": "#bd5752", "size_only": "#8a6cac"}

    def grid():
        return plt.subplots(4, 2, figsize=(13, 15), constrained_layout=True)

    def save(fig, name, title):
        fig.suptitle(title)
        fig.savefig(out / (name + ".png"), dpi=140)
        plt.close(fig)

    fig, axes = grid()
    for ax, seed in zip(axes.flat, SEEDS):
        matrix = [[next(r["probability"] for r in generations if (r["seed"], r["condition"], r["generation"], r["arm"]) == (seed, "adaptive", g, arm)) for g in range(1, 11)] for arm in FAMILIES]
        im = ax.imshow(matrix, aspect="auto", vmin=0, vmax=1, cmap="viridis", origin="upper")
        ax.set_yticks(range(len(FAMILIES)), FAMILIES, fontsize=7)
        ax.set_xticks(range(10), range(1, 11))
        ax.set(title=f"Seed {seed}", xlabel="Generation")
    fig.colorbar(im, ax=list(axes.flat), label="Mean proposal probability in generation")
    save(fig, "proposal_probability", "Adaptive UCB probabilities; Uniform assigns 1/14 throughout")

    fig, axes = grid()
    for ax, seed in zip(axes.flat, SEEDS):
        for offset, cond in ((-.18, "adaptive"), (.18, "uniform")):
            values = [next(r["mean_reward"] for r in arms if (r["seed"], r["condition"], r["arm"]) == (seed, cond, a)) for a in FAMILIES]
            ax.bar(np.arange(14)+offset, [np.nan if x is None else x for x in values], width=.36, label=cond, color=colors[cond])
        ax.set_xticks(range(14), FAMILIES, rotation=90, fontsize=6)
        ax.set(title=f"Seed {seed}", ylabel="Observed mean reward")
        ax.legend(fontsize=7)
    save(fig, "mutation_reward_estimates", "Observed-arm rewards; untried arms are missing, not zero")

    for name, field, title, all_arms in (
        ("adaptive_uniform_holdout_D", "D_holdout", "Holdout D (higher can include permanent failure)", False),
        ("holdout_D_generations", "D_holdout", "All conditions: holdout D by generation", True)):
        fig, axes = grid()
        for ax, seed in zip(axes.flat, SEEDS):
            for cond in CONDITIONS if all_arms else CONDITIONS[:2]:
                rows = [r for r in flat if (r["seed"], r["condition"]) == (seed, cond)]
                ax.plot([r["generation"] for r in rows], [r[field] for r in rows], marker=".", label=cond, color=colors[cond])
            ax.set(title=f"Seed {seed}", xlabel="Generation", ylabel="D", xticks=range(11))
            ax.legend(fontsize=7)
        save(fig, name, title)

    for name, field, title in (("final_success", "final_holdout_success", "Final holdout success at 8192 interactions"),
                               ("B80", "final_B80_holdout", "Final B80; x means not reached by 8192"),
                               ("first_eligibility", "first_eligible_generation", "First eligible generation; x means never eligible")):
        fig, ax = plt.subplots(figsize=(11, 5), constrained_layout=True)
        for offset, cond in ((-.18, "adaptive"), (.18, "uniform")):
            rows = [next(e for e in endpoints if (e["seed"], e["condition"]) == (s, cond)) for s in SEEDS]
            values = [r[field] for r in rows]
            cap = 10000 if field == "final_B80_holdout" else 11 if field == "first_eligible_generation" else 1.05
            ax.bar(np.arange(8)+offset, [np.nan if v is None else v for v in values], width=.36, color=colors[cond], label=cond)
            for i, v in enumerate(values):
                if v is None:
                    ax.scatter(i+offset, cap, marker="x", color=colors[cond])
        ax.set_xticks(range(8), SEEDS)
        ax.legend()
        if field == "final_holdout_success": ax.set_ylim(0, 1.05)
        if field == "final_B80_holdout": ax.set_yscale("log", base=2)
        save(fig, name, title)

    fig, axes = grid()
    for ax, seed in zip(axes.flat, SEEDS):
        for cond in CONDITIONS[:2]:
            rows = [r for r in flat if (r["seed"], r["condition"]) == (seed, cond)]
            ax.plot([8*r["generation"] for r in rows], [r["D_selection"] for r in rows], marker=".", color=colors[cond], label=f"{cond}: selection")
            ax.plot([8*r["generation"] for r in rows], [r["D_holdout"] for r in rows], linestyle="--", color=colors[cond], label=f"{cond}: holdout")
        ax.set(title=f"Seed {seed}", xlabel="Consumed candidate slots (invalid included)", ylabel="D")
        ax.legend(fontsize=7)
    save(fig, "frontier_by_candidate_budget", "Equal proposal budget; G0 preparation excluded")

    fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
    bottom = np.zeros(4)
    for label, color in (("LEARNED_SUCCESS", "#258568"), ("EXPLORATION_LIMITED", "#d3a53e"), ("REASONER_LIMITED", "#bf5454"), ("UNMEASURED", "#888888")):
        values = [sum(r["final_classification"] == label for r in endpoints if r["condition"] == c) for c in CONDITIONS]
        ax.bar(CONDITIONS, values, bottom=bottom, label=label, color=color)
        bottom += values
    ax.set(ylabel="Final worlds", ylim=(0, 9))
    ax.legend(fontsize=8)
    save(fig, "failure_taxonomy", "Frozen 80% diagnostic categories, not an experiment pass criterion")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, metric in zip(axes, ("valid_rate", "eligible_rate")):
        for offset, cond in ((-.18, "adaptive"), (.18, "uniform")):
            vals = [next(r[metric] for r in proposal_runs if (r["seed"], r["condition"]) == (s, cond)) for s in SEEDS]
            ax.bar(np.arange(8)+offset, vals, width=.36, color=colors[cond], label=cond)
        ax.set_xticks(range(8), SEEDS, rotation=45)
        ax.set(title=metric, ylim=(0, 1.05))
        ax.legend()
    save(fig, "candidate_quality", "Rates per 80 candidate slots; no discarded invalid slots")

    fig, axes = grid()
    for ax, seed in zip(axes.flat, SEEDS):
        for cond, marker in (("adaptive", "o"), ("uniform", "x")):
            hs = [h for h in events if h["seed"] == seed and h["condition"] == cond and h["selected"]]
            ax.scatter([h["generation"] for h in hs], [FAMILIES.index(h["mutation"]) for h in hs], marker=marker, color=colors[cond], label=cond)
        ax.set_yticks(range(14), FAMILIES, fontsize=6)
        ax.set(title=f"Seed {seed}", xlabel="Generation", xticks=range(1, 11))
        ax.legend(fontsize=7)
    save(fig, "selected_mutation_sequence", "Selected candidate primitives; blank means parent retained")

    fig, axes = plt.subplots(1, 2, figsize=(11, 5), constrained_layout=True)
    for ax, field, label in zip(axes, ("G10_D_holdout", "final_holdout_success"), ("Final holdout D", "Final holdout success")):
        for seed in SEEDS:
            a, b = [next(e[field] for e in endpoints if (e["seed"], e["condition"]) == (seed, c)) for c in CONDITIONS[:2]]
            if a is not None and b is not None:
                ax.scatter(b, a, color=colors["adaptive"])
                ax.annotate(str(seed), (b, a), fontsize=7, xytext=(3, 3), textcoords="offset points")
        lo = min(ax.get_xlim()[0], ax.get_ylim()[0])
        hi = max(ax.get_xlim()[1], ax.get_ylim()[1])
        ax.plot([lo, hi], [lo, hi], color="#888888", linestyle="--")
        ax.set(title=label, xlabel="Uniform", ylabel="Adaptive")
    save(fig, "paired_comparison", "Per-seed paired comparison; D alone is not a success metric")
