# Fresh 70-world virtual-frontier experiment



Confirmatory status: INCOMPLETE

Analyzable worlds: 65 / 70

Scope: PARTIAL / DESCRIPTIVE; conditional on task-generatable and completed worlds



Negative D or G means the first policy uses fewer capped steps.

Bootstrap resampling uses worlds, never individual tasks.

Primary D: {'n_worlds': 65, 'mean': -1.0192307692307692, 'median': 0.0, 'ci95': [-1.9666987179487176, -0.24102564102564106], 'lower': 18, 'higher': 6, 'tied': 41, 'raw_world_values': [-0.08333333333333333, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, -5.166666666666667, 0.0, -3.0833333333333335, -1.1666666666666667, 0.0, 0.0, -0.08333333333333333, 0.0, -1.5, -1.75, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -5.666666666666667, 0.0, 0.0, 0.0, 0.0, -18.166666666666668, -1.5, -3.9166666666666665, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0, -2.0, 0.0, 0.0, 0.0, -0.5833333333333334, 0.0, 0.0, 5.416666666666667, -0.6666666666666666, 0.0, 0.0, 0.0, -10.583333333333334, -16.0, 0.0, 0.0, 0.0, 0.3333333333333333, 0.0, 0.0, 0.0, 0.16666666666666666, 5.666666666666667, 0.0, -1.0833333333333333, -5.833333333333333]}

Secondary G: {'n_worlds': 65, 'mean': -19.97948717948718, 'median': 0.0, 'ci95': [-31.993621794871796, -10.243397435897451], 'lower': 32, 'higher': 7, 'tied': 26, 'raw_world_values': [-0.3333333333333333, 0.0, 0.0, 0.0, -12.0, 0.0, 0.0, -9.25, -2.0833333333333335, 0.0, -30.666666666666668, -37.5, 0.0, 0.0, -202.58333333333334, 0.0, -80.58333333333333, -1.5, 2.0, 0.0, 0.08333333333333333, 0.0, -2.0833333333333335, 0.0, -147.33333333333334, -30.083333333333332, 0.0, -55.75, -9.083333333333334, -88.0, -3.3333333333333335, -26.416666666666668, 0.0, -14.333333333333334, -8.0, -3.0833333333333335, -3.4166666666666665, 0.0, 0.0, -29.083333333333332, 2.0, -3.6666666666666665, 0.0, 3.4166666666666665, 0.0, 0.0, -55.333333333333336, -38.166666666666664, 10.083333333333334, 0.0, 0.0, -2.9166666666666665, -211.25, 0.0, -49.25, 0.0, 0.25, 0.0, 0.0, 0.0, -35.166666666666664, -123.0, 16.25, -16.333333333333332, -1.1666666666666667]}

Relative R: {'n_worlds': 65, 'mean': -0.005644968499809927, 'median': 0.0, 'ci95': [-0.010459308311661968, -0.0014797430583151357], 'lower': 18, 'higher': 6, 'tied': 41, 'raw_world_values': [-0.001557632398753894, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.02857142857142857, -0.07217694994179279, 0.0, -0.028861154446177848, -0.012903225806451613, 0.0, 0.0, -0.00016160310277957336, 0.0, -0.009268795056642637, -0.014373716632443531, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.023834560112162638, 0.0, 0.0, 0.0, 0.0, -0.046323841903952404, -0.01541095890410959, -0.05037513397642015, 0.0, 0.0, 0.008119079837618403, 0.0, 0.0, 0.0, 0.0, -0.0038247011952191236, 0.0, 0.0, 0.0, -0.0037940379403794042, 0.0, 0.0, 0.022329096530401923, -0.005270092226613965, 0.0, 0.0, 0.0, -0.08657123381049762, -0.022333372106548798, 0.0, 0.0, 0.0, 0.0006194827319188477, 0.0, 0.0, 0.0, 0.0018315018315018315, 0.02944997834560416, 0.0, -0.031476997578692496, -0.029325513196480937]}

Confirmatory practical equivalence: None



## Mechanism and interpretation

Source variation: 15966/71673; action changes: 91/71673.

Changes conditional on signal: 91/15966; changed worlds: 27/65.

Zero source variation supports no available task information on these decisions.

Source variation without action changes separates information from behavioral effect.

Behavioral change and performance equivalence require both action changes and the preregistered relative CI criterion.

Improvement/harm requires the frozen world-level D comparison; nonsignificance is not equivalence.

When status is INCOMPLETE, these are conditional descriptive results, not the 70-world primary claim.

Task-generation unavailability is not a policy failure. No worlds were replaced.

Process peak RSS is cumulative within each shard, not isolated per-policy allocation.
