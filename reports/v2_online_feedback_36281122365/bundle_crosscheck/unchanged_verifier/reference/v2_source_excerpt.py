"""Selected definitions copied from the pinned V2 source, not a new game engine.
Original: corcondor/mortra, commit 5f8b36744a29327928c87d6db888f2f045dbea79,
scripts/evaluate_autonomous_game_design_loop.py (Git blob 9560ba0d2b1782cf6c54d69e43b5ad906810063b).
This is a source excerpt, NOT a byte-identical copy of the full script.
Use verify_checkout.py to compare selected ASTs with a full checkout.
"""
import random
import numpy as np
ACTIONS = ["UP", "DOWN", "LEFT", "RIGHT", "INTERACT"]
NUM_ACTIONS = 5

class MicroGame:
    def __init__(self, width=12, height=12, seed=42):
        self.width = width
        self.height = height
        self.rng = random.Random(seed)
        self.walls = set()
        self.hazards = set()
        self.start_pos = (1, 1)
        self.goal_pos = (10, 10)
        self.key_pos = None
        self.door_pos = None
        self.switch_pos = None
        self.gate_pos = None
        self.block_pos = None
        self.teleport_a = None
        self.teleport_b = None
        self.rules = {"hazard_reset": True}

    def copy(self):
        g = MicroGame(self.width, self.height)
        g.walls = set(self.walls)
        g.hazards = set(self.hazards)
        g.start_pos = tuple(self.start_pos)
        g.goal_pos = tuple(self.goal_pos)
        g.key_pos = tuple(self.key_pos) if self.key_pos else None
        g.door_pos = tuple(self.door_pos) if self.door_pos else None
        g.switch_pos = tuple(self.switch_pos) if self.switch_pos else None
        g.gate_pos = tuple(self.gate_pos) if self.gate_pos else None
        g.block_pos = tuple(self.block_pos) if self.block_pos else None
        g.teleport_a = tuple(self.teleport_a) if self.teleport_a else None
        g.teleport_b = tuple(self.teleport_b) if self.teleport_b else None
        g.rules = dict(self.rules)
        return g

    def to_dict(self):
        return {
            "width": self.width,
            "height": self.height,
            "walls": sorted(list(self.walls)),
            "hazards": sorted(list(self.hazards)),
            "start_pos": list(self.start_pos),
            "goal_pos": list(self.goal_pos),
            "key_pos": list(self.key_pos) if self.key_pos else None,
            "door_pos": list(self.door_pos) if self.door_pos else None,
            "switch_pos": list(self.switch_pos) if self.switch_pos else None,
            "gate_pos": list(self.gate_pos) if self.gate_pos else None,
            "block_pos": list(self.block_pos) if self.block_pos else None,
            "teleport_a": list(self.teleport_a) if self.teleport_a else None,
            "teleport_b": list(self.teleport_b) if self.teleport_b else None,
            "rules": self.rules
        }

    def generate_random(self, wall_density=0.18):
        """Generates G0 with outer walls, random obstacles, and elements without human bias."""
        self.walls = set()
        for x in range(self.width):
            self.walls.add((x, 0))
            self.walls.add((x, self.height - 1))
        for y in range(self.height):
            self.walls.add((0, y))
            self.walls.add((self.width - 1, y))

        all_inner = [(x, y) for x in range(1, self.width - 1) for y in range(1, self.height - 1)]
        num_walls = int(len(all_inner) * wall_density)
        wall_sample = self.rng.sample(all_inner, num_walls)
        for w in wall_sample:
            self.walls.add(w)

        free_cells = [c for c in all_inner if c not in self.walls]
        self.rng.shuffle(free_cells)

        self.start_pos = free_cells[0]
        self.goal_pos = free_cells[1]

        rem = free_cells[2:]
        if len(rem) >= 8:
            self.key_pos = rem[0]
            self.door_pos = rem[1]
            self.switch_pos = rem[2]
            self.gate_pos = rem[3]
            self.teleport_a = rem[4]
            self.teleport_b = rem[5]
            self.hazards.add(rem[6])
            self.block_pos = rem[7]

    def get_initial_state(self):
        bx, by = self.block_pos if self.block_pos else (-1, -1)
        # Canonical state tuple: (px, py, has_key, door_open, switch_on, gate_open, bx, by)
        return (self.start_pos[0], self.start_pos[1], 0, 0, 0, 0, bx, by)

    def is_goal(self, state):
        return (state[0], state[1]) == self.goal_pos

    def step(self, state, action):
        px, py, has_key, door_open, switch_on, gate_open, bx, by = state
        dx, dy = 0, 0
        if action == 0: dy = -1   # UP
        elif action == 1: dy = 1  # DOWN
        elif action == 2: dx = -1 # LEFT
        elif action == 3: dx = 1  # RIGHT

        if action in [0, 1, 2, 3]:
            nx, ny = px + dx, py + dy
            # Check boundaries
            if not (0 <= nx < self.width and 0 <= ny < self.height):
                nx, ny = px, py
            elif (nx, ny) in self.walls:
                nx, ny = px, py # Wall collision
            elif self.door_pos and (nx, ny) == self.door_pos and not door_open:
                if has_key:
                    door_open = 1 # Unlock door
                else:
                    nx, ny = px, py # Locked
            elif self.gate_pos and (nx, ny) == self.gate_pos and not gate_open:
                nx, ny = px, py # Closed gate
            elif self.block_pos and (nx, ny) == (bx, by):
                bbx, bby = bx + dx, by + dy
                # Push block if target is open floor
                if (0 < bbx < self.width - 1 and 0 < bby < self.height - 1 and
                    (bbx, bby) not in self.walls and
                    (not self.door_pos or (bbx, bby) != self.door_pos or door_open) and
                    (not self.gate_pos or (bbx, bby) != self.gate_pos or gate_open) and
                    (bbx, bby) not in self.hazards):
                    bx, by = bbx, bby
                else:
                    nx, ny = px, py # Block immovable
            elif (nx, ny) in self.hazards:
                if self.rules.get("hazard_reset", True):
                    nx, ny = self.start_pos # Hazard penalty
                else:
                    nx, ny = px, py
            elif self.teleport_a and (nx, ny) == self.teleport_a and self.teleport_b:
                nx, ny = self.teleport_b
            elif self.teleport_b and (nx, ny) == self.teleport_b and self.teleport_a:
                nx, ny = self.teleport_a

            px, py = nx, ny

            # Floor triggers on arrival
            if self.key_pos and (px, py) == self.key_pos:
                has_key = 1
            if self.switch_pos and (px, py) == self.switch_pos:
                switch_on = 1 - switch_on
                gate_open = switch_on

        elif action == 4: # INTERACT
            for dxx, dyy in [(0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)]:
                cx, cy = px + dxx, py + dyy
                if self.key_pos and (cx, cy) == self.key_pos:
                    has_key = 1
                if self.switch_pos and (cx, cy) == self.switch_pos:
                    switch_on = 1 - switch_on
                    gate_open = switch_on
                if self.door_pos and (cx, cy) == self.door_pos and has_key:
                    door_open = 1

        return (px, py, has_key, door_open, switch_on, gate_open, bx, by)


def solve_fixed_field(K, goal_indices, q=0.90, max_iters=300, tol=1e-8):
    """
    Fixed-field equation: psi = g + q * K * psi
    q = 0.90 completely frozen.
    """
    N = K.shape[0]
    g = np.zeros(N, dtype=float)
    for g_idx in goal_indices:
        g[g_idx] = 1.0
    psi = np.zeros(N, dtype=float)
    for it in range(1, max_iters + 1):
        psi_next = g + q * (K @ psi)
        res = float(np.max(np.abs(psi_next - psi)))
        psi = psi_next
        if res < tol:
            return psi, it, res, True
    return psi, max_iters, res, False

class StructuralLearner:
    """
    General task-agnostic structural learner.
    Explores world without map topology, purely through (s, a, s').
    """
    def __init__(self, num_actions=5):
        self.num_actions = num_actions
        self.state_to_id = {}
        self.id_to_state = []
        self.node_visits = {}
        self.action_visits = {}
        self.counts = {}
        self.dest_map = {}

    def get_or_add_id(self, state):
        if state not in self.state_to_id:
            idx = len(self.id_to_state)
            self.state_to_id[state] = idx
            self.id_to_state.append(state)
            return idx
        return self.state_to_id[state]

    def select_action(self, u):
        self.node_visits[u] = self.node_visits.get(u, 0) + 1
        untried = [a for a in range(self.num_actions) if self.action_visits.get((u, a), 0) == 0]
        if untried:
            return untried[0] # Priority 1: Untried actions
        
        # Priority 2: Lowest visit count with neighbor tie-break
        best_a = 0
        best_score = 1e9
        for a in range(self.num_actions):
            n_ua = self.action_visits.get((u, a), 0)
            v = self.dest_map.get((u, a), u)
            n_v = self.node_visits.get(v, 0)
            score = n_ua * 10000.0 + n_v
            if score < best_score:
                best_score = score
                best_a = a
        return best_a

    def record_transition(self, u, a, v):
        self.action_visits[(u, a)] = self.action_visits.get((u, a), 0) + 1
        key = (u, a)
        if key not in self.counts:
            self.counts[key] = {}
        self.counts[key][v] = self.counts[key].get(v, 0) + 1
        self.dest_map[key] = max(self.counts[key].items(), key=lambda it: it[1])[0]

    def build_k_support(self):
        N = len(self.id_to_state)
        K = np.zeros((N, N), dtype=float)
        for u in range(N):
            tried_acts = [a for a in range(self.num_actions) if (u, a) in self.counts]
            if not tried_acts:
                K[u, u] = 1.0
                continue
            prob = 1.0 / len(tried_acts)
            for a in tried_acts:
                v = self.dest_map[(u, a)]
                K[u, v] += prob
        return K


def evaluate_random_player(game, trials=50, max_steps=100, seed=999):
    """Count each trial once, including a goal reached on its last action."""
    if trials < 1 or max_steps < 0:
        raise ValueError("trials must be positive and max_steps nonnegative")
    rng = random.Random(seed)
    successes = 0
    first_trial = None
    for trial in range(trials):
        state = game.get_initial_state()
        states, actions = [state], []
        for _ in range(max_steps):
            if game.is_goal(state):
                break
            action = rng.randrange(NUM_ACTIONS)
            state = game.step(state, action)
            actions.append(action)
            states.append(state)
        reached = bool(game.is_goal(state))
        successes += int(reached)
        if trial == 0:
            first_trial = {"trial": trial, "actions": actions, "states": states,
                           "reached_goal": reached}
    return {"successes": successes, "trials": trials, "seed": seed,
            "success_rate": successes / trials, "replay": first_trial}


def evaluate_game(game, explore_steps=2500, self_play_trials=50, max_play_steps=100):
    """
    Full closed-loop evaluation:
    1. Structural Exploration (learn K_support)
    2. Fixed-field reasoning (psi)
    3. 50 Self-Play trials with MORTRA
    4. 50 Random-Player trials
    5. Goal reuse on auxiliary objective
    """
    if self_play_trials < 1 or max_play_steps < 0:
        raise ValueError("self_play_trials must be positive and max_play_steps nonnegative")
    learner = StructuralLearner(num_actions=NUM_ACTIONS)
    curr_state = game.get_initial_state()
    curr_u = learner.get_or_add_id(curr_state)

    # 1. Structural Exploration
    for _ in range(explore_steps):
        a = learner.select_action(curr_u)
        next_state = game.step(curr_state, a)
        next_u = learner.get_or_add_id(next_state)
        learner.record_transition(curr_u, a, next_u)
        curr_state = next_state
        curr_u = next_u

    K = learner.build_k_support()
    N = len(learner.id_to_state)

    # Find goal states in learned graph
    goal_indices = [u for u, st in enumerate(learner.id_to_state) if game.is_goal(st)]

    # 2. Fixed-Field Reasoning
    psi = np.zeros(N, dtype=float)
    if goal_indices:
        psi, iters, res, conv = solve_fixed_field(K, goal_indices, q=0.90)

    # 3. MORTRA Self-Play (50 trials)
    mortra_successes = 0
    mortra_steps_list = []
    mortra_trajectories = []
    unique_trajs = set()
    action_counts = np.zeros(NUM_ACTIONS, dtype=int)
    total_loop_steps = 0
    total_play_steps = 0
    dead_end_count = 0
    visited_cells_in_play = set()

    init_state = game.get_initial_state()
    mortra_replay = None

    for trial in range(self_play_trials):
        st = init_state
        traj = [(st[0], st[1])]
        recorded_states, recorded_actions = [st], []
        visited_in_trial = {st}
        visited_cells_in_play.add((st[0], st[1]))
        loop_steps_trial = 0
        reached = False

        for step_i in range(max_play_steps):
            total_play_steps += 1
            if game.is_goal(st):
                reached = True
                break
            
            u = learner.state_to_id.get(st, -1)
            # Greedy field readout
            best_a = None
            best_val = -1e9
            if u != -1:
                # Explore ties slightly across trials with small deterministic jitter
                for a in range(NUM_ACTIONS):
                    if (u, a) in learner.dest_map:
                        v = learner.dest_map[(u, a)]
                        val = psi[v]
                        if val > best_val:
                            best_val = val
                            best_a = a
                        elif abs(val - best_val) < 1e-12 and best_a is not None:
                            # Use trial number to sample alternate optimal branches
                            if (trial + a) % 2 == 0:
                                best_a = a

            if best_a is None or best_val <= 1e-8:
                # No learned gradient towards goal: fallback to uniform random
                best_a = trial % NUM_ACTIONS

            action_counts[best_a] += 1
            next_st = game.step(st, best_a)
            recorded_actions.append(best_a)
            recorded_states.append(next_st)
            traj.append((next_st[0], next_st[1]))
            visited_cells_in_play.add((next_st[0], next_st[1]))

            if next_st in visited_in_trial:
                loop_steps_trial += 1
            visited_in_trial.add(next_st)
            st = next_st

        if game.is_goal(st):
            reached = True
        if trial == 0:
            mortra_replay = {"trial": trial, "actions": recorded_actions,
                             "states": recorded_states, "reached_goal": reached}

        total_loop_steps += loop_steps_trial
        if reached:
            mortra_successes += 1
            mortra_steps_list.append(len(traj) - 1)
            traj_tuple = tuple(traj)
            unique_trajs.add(traj_tuple)
            mortra_trajectories.append(traj)
        else:
            dead_end_count += 1

    # 4. Random Player Baseline (50 trials)
    random_result = evaluate_random_player(game, self_play_trials, max_play_steps)
    random_successes = random_result["successes"]

    # 5. Goal Reuse Performance (Auxiliary Goal: Key or Switch)
    reuse_successes = 0
    aux_target = game.key_pos if game.key_pos else game.switch_pos
    if aux_target:
        aux_indices = [u for u, st in enumerate(learner.id_to_state) if (st[0], st[1]) == aux_target]
        if aux_indices:
            psi_aux, _, _, _ = solve_fixed_field(K, aux_indices, q=0.90)
            st = init_state
            for _ in range(max_play_steps):
                if (st[0], st[1]) == aux_target:
                    reuse_successes += 1
                    break
                u = learner.state_to_id.get(st, -1)
                best_a = None
                best_val = -1e9
                if u != -1:
                    for a in range(NUM_ACTIONS):
                        if (u, a) in learner.dest_map:
                            v = learner.dest_map[(u, a)]
                            if psi_aux[v] > best_val:
                                best_val = psi_aux[v]
                                best_a = a
                if best_a is None or best_val <= 1e-8:
                    break
                st = game.step(st, best_a)

    # Metrics computation
    succ_rate = mortra_successes / self_play_trials
    rand_succ_rate = random_successes / self_play_trials
    mean_actions = float(np.mean(mortra_steps_list)) if mortra_steps_list else float(max_play_steps)
    edge_cov = sum(len(dests) for dests in learner.counts.values())
    
    # Action distribution entropy
    act_probs = action_counts / max(1, np.sum(action_counts))
    act_entropy = float(-np.sum([p * np.log2(p) for p in act_probs if p > 0]))

    loop_rate = total_loop_steps / max(1, total_play_steps)
    dead_rate = dead_end_count / self_play_trials
    
    # Floor reachable cells vs visited cells
    all_floor = [(x, y) for x in range(1, game.width - 1) for y in range(1, game.height - 1) if (x, y) not in game.walls]
    unexplored_count = len(all_floor) - len(visited_cells_in_play.intersection(set(all_floor)))

    return {
        "trials": self_play_trials,
        "successes": mortra_successes,
        "random_successes": random_successes,
        "explore_steps": explore_steps,
        "max_play_steps": max_play_steps,
        "mortra_replay": mortra_replay,
        "random_replay": random_result["replay"],
        "success_rate": round(succ_rate, 4),
        "random_success_rate": round(rand_succ_rate, 4),
        "strategic_gap": round(succ_rate - rand_succ_rate, 4),
        "mean_actions_to_goal": round(mean_actions, 2),
        "state_coverage": N,
        "edge_coverage": edge_cov,
        "unique_successful_trajectories": len(unique_trajs),
        "action_entropy": round(act_entropy, 3),
        "repeated_loop_rate": round(loop_rate, 4),
        "dead_end_rate": round(dead_rate, 4),
        "unexplored_regions": max(0, unexplored_count),
        "goal_reuse_rate": round(reuse_successes / 1.0, 4) if aux_target else 1.0,
        "sample_trajectories": mortra_trajectories[:5]
    }
