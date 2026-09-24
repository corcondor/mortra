from __future__ import annotations
import json
import numpy as np

from mortra_predictive_perception import PredictiveMDLSymbolizer


def predictive_vs_nuisance():
    model = PredictiveMDLSymbolizer(actions=["go"])

    # Feature 0 is nuisance: it varies strongly but has no effect on response.
    # Feature 1 determines the action-conditioned change.
    for nuisance in (-12.0, -7.0, -2.0, 3.0, 8.0, 13.0):
        model.add_episode(
            [
                np.array([nuisance, 0.0]),
                np.array([nuisance + 1.0, 2.0]),
            ],
            ["go"],
        )
        model.add_episode(
            [
                np.array([nuisance, 1.0]),
                np.array([nuisance - 1.0, -2.0]),
            ],
            ["go"],
        )

    report = model.fit()
    return model.export_tree()


def memory_without_fixed_history_depth():
    model = PredictiveMDLSymbolizer(actions=["advance", "choose"])

    # Current junction observation [9] is identical.  Only the earlier cue
    # predicts the response to "choose".
    for _ in range(8):
        model.add_episode(
            [
                np.array([0.0]),
                np.array([5.0]),
                np.array([9.0]),
                np.array([20.0]),
            ],
            ["advance", "advance", "choose"],
        )
        model.add_episode(
            [
                np.array([1.0]),
                np.array([5.0]),
                np.array([9.0]),
                np.array([-20.0]),
            ],
            ["advance", "advance", "choose"],
        )

    report = model.fit()
    return model.export_tree()


def main():
    print(json.dumps({
        "predictive_vs_nuisance": predictive_vs_nuisance(),
        "memory_without_fixed_history_depth": memory_without_fixed_history_depth(),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
