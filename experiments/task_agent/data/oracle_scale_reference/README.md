# Oracle diagnostic reproduction bundle

This bundle contains the exact Python scripts preserved from the oracle diagnostics and the four output shards used to construct the 65-world / 780-task `oracle_source_linear_result_780.json` result.

## Primary script for the 780-task oracle-source result

`run_oracle_source_linear_shard.py`

Expected external inputs:

- `/mnt/data/reg70/registration/<seed>/genome.json`
- `/mnt/data/reg70/registration/<seed>/snapshot_512.json`
- `/mnt/data/reg70/registration/<seed>/tasks.json`
- `/mnt/data/fresh70_episodes.csv`

Constants:

- `Q = 0.90`
- episode cap `CAP = 4096`

### Exact oracle distance definition

`TrueOracle` closes the true deterministic world transition graph from every state known in the episode-start 512-step snapshot. It then builds the full product graph `(world_state, task_memory)` under every action.

Accepting product states have distance 0. Distances to acceptance are computed by reverse unweighted BFS on the full product graph. Thus distance is the exact minimum number of future actions to an accepting product state in the true deterministic world.

For a virtual frontier `(u,m,a)`, the code evaluates the true successor of action `a`, advances task memory once on that successor, looks up its exact remaining distance `d`, and assigns

    source = Q ** d

If the product state cannot reach acceptance, source is `0.0`.

Note: the source does NOT include an extra factor of `Q` for the unknown action itself; `d` starts *after* that true transition. The linear field propagation through the current real node contributes its own `Q` factor.

### Linear propagation

The augmented known/virtual frontier graph uses equal mass `1/A` for every action from each real product node, including an untried action leading to its terminal virtual node. The field is solved by

    (I - Q K_plus) phi = source

using SciPy sparse LU (`splu`).

### Tie handling

- Known modal successor: `max(counts, key=(count, -successor_id))`, so equal counts choose the lower successor id.
- Planner action: `max((psi[next], -action, action))`, so equal field values choose the lower action id.
- Generic/current virtual action: `max(..., key=(score, -action))`, so equal scores choose the lower action id.
- Exact oracle action: minimizes `(distance, action)`, so equal exact distances choose the lower action id.
- Oracle-source linear action: `max(..., key=(field_value, -action))`, so equal field values choose the lower action id.

### Four shards used for the 780 result

The script internally sorts the 65 `registration.json` entries whose `status == "ready"`. The preserved run used:

    START_I=0  END_I=17 OUT=/mnt/data/osrc_0.json python run_oracle_source_linear_shard.py
    START_I=17 END_I=34 OUT=/mnt/data/osrc_1.json python run_oracle_source_linear_shard.py
    START_I=34 END_I=51 OUT=/mnt/data/osrc_2.json python run_oracle_source_linear_shard.py
    START_I=51 END_I=65 OUT=/mnt/data/osrc_3.json python run_oracle_source_linear_shard.py

Shard sizes are 204, 204, 204, and 168 task rows, totaling 780.

The five preregistered worlds that were not `ready` are therefore absent, matching the fresh70 incomplete analysis.

## Preserved aggregate

The four shards concatenate to:

- 65 worlds
- 780 unique `(seed, task_id)` rows
- oracle-source success: 780 / 780
- oracle-source mean steps: `23.694871794871794`
- generic mean steps: `103.25128205128205`
- current task-virtual mean steps: `102.23205128205129`

`oracle_source_linear_result_780.json` is a concatenation of the four preserved shard rows plus an aggregate summary; the shard row values are unchanged.

## Other diagnostic scripts

- `run_oracle_headroom.py`: full oracle-guided exploration diagnostic.
- `run_oracle_same_state.py`: same-learned-state comparison diagnostic.
- `run_oracle_alignment.py`: direction/alignment diagnostic for current task perturbations against oracle actions.

These are included to pin the implementations used for the other reported oracle analyses.
