"""
Autonomous Self-Game-Design Closed Loop for MORTRA.

Verifies the complete closed loop:
    Self-Generate MicroGame
        ↓
    Explore & Learn World Structure (Structural Exploration -> K_support)
        ↓
    Self-Play via Fixed-Field Reasoning (psi = g + 0.90 K psi)
        ↓
    Analyze Experience & Self-Critique
        ↓
    Edit Game World (1 atomic targeted mutation)
        ↓
    Repeat & Accept/Reject via Pre-Registered Lexicographic Criteria

Features:
- Completely frozen MORTRA core (StructuralLearner, q=0.90 fixed-field solver, greedy readout)
- 12x12 MicroGame environment supporting 11 game elements
- 50 self-play trials per evaluation (MORTRA + Random player baseline)
- Structural self-critique engine (TOO_EASY, TOO_HARD, TRIVIAL_STRATEGY, NO_CHOICE, LOOP_TRAP, etc.)
- 20 iterative design cycles
- Strict Control: Random Mutation Designer vs MORTRA Self-Designer on identical G0
- Creation Test across 5 independent seeds
- V2 deliverables: metrics, action/state replays, evolution history, and figures.
"""

import os
import sys
import json
import time
import math
import random
import argparse
import hashlib
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from collections import deque
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(workspace_root, "reports", "self_game_design_v2")

class TeeLogger:
    def __init__(self, filename, stream):
        self.terminal = stream
        self.log = open(filename, "w", encoding="utf-8", buffering=1)
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
    def flush(self):
        self.terminal.flush()
        self.log.flush()

# =========================================================================
# 1. MICROGAME ENVIRONMENT (12 x 12 Grid, 11 Elements)
# =========================================================================

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


# =========================================================================
# 2. FROZEN MORTRA CORE (StructuralLearner + Contracting Fixed-Field)
# =========================================================================

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


# =========================================================================
# 3. SELF-PLAY & COMPREHENSIVE EVALUATION
# =========================================================================

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


# =========================================================================
# 4. SELF-CRITIQUE ENGINE
# =========================================================================

def critique_game(metrics):
    """
    Evaluates self-play metrics and assigns exactly one structural category.
    Completely objective, purely numeric rules.
    """
    succ = metrics["success_rate"]
    rand_succ = metrics["random_success_rate"]
    mean_act = metrics["mean_actions_to_goal"]
    uniq_traj = metrics["unique_successful_trajectories"]
    loop_rate = metrics["repeated_loop_rate"]
    dead_rate = metrics["dead_end_rate"]
    unexplored = metrics["unexplored_regions"]
    states = metrics["state_coverage"]

    # Priority 1: Unsolvable game
    if succ < 0.10:
        return "TOO_HARD"
    # Priority 2: Trivial walk
    if succ >= 0.90 and mean_act <= 6.0 and rand_succ >= 0.35:
        return "TOO_EASY"
    # Priority 3: No real agency / random walk works almost as well
    if rand_succ >= succ * 0.75 and succ > 0:
        return "TOO_RANDOM"
    # Priority 4: Bottlenecked into exactly 1 trajectory
    if succ >= 0.70 and uniq_traj <= 1:
        return "NO_CHOICE"
    # Priority 5: Low trajectory diversity with short actions
    if uniq_traj <= 1 and mean_act <= 9.0:
        return "TRIVIAL_STRATEGY"
    # Priority 6: Severe loop or dead-end trap
    if loop_rate >= 0.35 or dead_rate >= 0.50:
        return "LOOP_TRAP"
    # Priority 7: Vast unused space
    if unexplored >= 15:
        return "DEAD_REGIONS"
    # Priority 8: Low discovery in state space
    if states <= 30:
        return "LOW_DISCOVERY"

    return "GOOD"


# =========================================================================
# 5. ATOMIC MUTATION GENERATOR (Game Editing)
# =========================================================================

def get_free_inner_cells(game):
    inner = [(x, y) for x in range(1, game.width - 1) for y in range(1, game.height - 1)]
    occupied = set(game.walls)
    occupied.add(game.start_pos)
    occupied.add(game.goal_pos)
    if game.key_pos: occupied.add(game.key_pos)
    if game.door_pos: occupied.add(game.door_pos)
    if game.switch_pos: occupied.add(game.switch_pos)
    if game.gate_pos: occupied.add(game.gate_pos)
    if game.block_pos: occupied.add(game.block_pos)
    if game.teleport_a: occupied.add(game.teleport_a)
    if game.teleport_b: occupied.add(game.teleport_b)
    occupied.update(game.hazards)
    return [c for c in inner if c not in occupied]

def apply_targeted_mutation(game, critique, rng):
    """
    Applies exactly 1 atomic modification based on critique.
    """
    cand = game.copy()
    free_cells = get_free_inner_cells(cand)
    inner_walls = [w for w in cand.walls if 0 < w[0] < cand.width - 1 and 0 < w[1] < cand.height - 1]

    if critique == "TOO_HARD":
        # Unblock path: remove a wall, remove a hazard, or add teleporter shortcut
        choice = rng.choice(["remove_wall", "remove_hazard", "add_teleporter"])
        if choice == "remove_wall" and inner_walls:
            w = rng.choice(inner_walls)
            cand.walls.remove(w)
            return cand, f"Remove wall at {w} to unblock passage"
        elif choice == "remove_hazard" and cand.hazards:
            h = rng.choice(list(cand.hazards))
            cand.hazards.remove(h)
            return cand, f"Remove hazard at {h}"
        elif free_cells and len(free_cells) >= 2 and not cand.teleport_a:
            cand.teleport_a = free_cells[0]
            cand.teleport_b = free_cells[1]
            return cand, f"Add teleporter pair ({cand.teleport_a} <-> {cand.teleport_b})"
        elif inner_walls:
            w = rng.choice(inner_walls)
            cand.walls.remove(w)
            return cand, f"Remove wall at {w}"

    elif critique in ["TOO_EASY", "TOO_RANDOM"]:
        # Add challenge: insert wall, add key-door requirement, add hazard, or move goal farther
        choice = rng.choice(["add_wall", "add_key_door", "add_hazard", "move_goal"])
        if choice == "add_wall" and free_cells:
            # Place wall between start and goal
            sx, sy = cand.start_pos
            gx, gy = cand.goal_pos
            mid_c = sorted(free_cells, key=lambda c: abs(c[0] - (sx+gx)//2) + abs(c[1] - (sy+gy)//2))[0]
            cand.walls.add(mid_c)
            return cand, f"Add wall at {mid_c} between start and goal"
        elif choice == "add_key_door" and len(free_cells) >= 2 and not cand.door_pos:
            cand.key_pos = free_cells[0]
            cand.door_pos = free_cells[1]
            return cand, f"Add key at {cand.key_pos} and locked door at {cand.door_pos}"
        elif choice == "add_hazard" and free_cells:
            h = rng.choice(free_cells)
            cand.hazards.add(h)
            return cand, f"Add hazard at {h}"
        elif choice == "move_goal" and free_cells:
            # Pick cell farthest from start
            sx, sy = cand.start_pos
            farthest = max(free_cells, key=lambda c: abs(c[0] - sx) + abs(c[1] - sy))
            cand.goal_pos = farthest
            return cand, f"Move goal farther to {farthest}"

    elif critique in ["NO_CHOICE", "TRIVIAL_STRATEGY"]:
        # Create branching routes: remove wall, add teleporter, or add movable block
        choice = rng.choice(["remove_wall", "add_block", "add_teleporter"])
        if choice == "remove_wall" and inner_walls:
            w = rng.choice(inner_walls)
            cand.walls.remove(w)
            return cand, f"Remove wall at {w} to open alternative branch"
        elif choice == "add_block" and free_cells and not cand.block_pos:
            cand.block_pos = free_cells[0]
            return cand, f"Add movable block at {cand.block_pos}"
        elif choice == "add_teleporter" and len(free_cells) >= 2 and not cand.teleport_a:
            cand.teleport_a = free_cells[0]
            cand.teleport_b = free_cells[1]
            return cand, f"Add teleporter shortcut ({cand.teleport_a} <-> {cand.teleport_b})"

    elif critique == "LOOP_TRAP":
        # Seal dead-end cycle or remove hazard
        if cand.hazards:
            h = rng.choice(list(cand.hazards))
            cand.hazards.remove(h)
            return cand, f"Remove trap hazard at {h}"
        elif inner_walls:
            w = rng.choice(inner_walls)
            cand.walls.remove(w)
            return cand, f"Remove wall at {w} to eliminate cycle trap"

    elif critique == "DEAD_REGIONS":
        # Place key or switch inside dead region
        if free_cells:
            cand.key_pos = free_cells[0]
            return cand, f"Relocate key to {cand.key_pos} in unexplored area"

    elif critique == "LOW_DISCOVERY":
        # Add switch-gate pair to enrich state dynamics
        if len(free_cells) >= 2 and not cand.switch_pos:
            cand.switch_pos = free_cells[0]
            cand.gate_pos = free_cells[1]
            return cand, f"Add switch at {cand.switch_pos} and gate at {cand.gate_pos}"

    # Default / GOOD fallback mutation: move start or wall
    if inner_walls and rng.random() < 0.5:
        w_old = rng.choice(inner_walls)
        cand.walls.remove(w_old)
        if free_cells:
            w_new = rng.choice(free_cells)
            cand.walls.add(w_new)
            return cand, f"Move wall from {w_old} to {w_new}"
        return cand, f"Remove wall at {w_old}"
    elif free_cells:
        w = rng.choice(free_cells)
        cand.walls.add(w)
        return cand, f"Add wall at {w}"

    return cand, "No-op mutation"

def apply_random_mutation(game, rng):
    """Control condition: selects an atomic mutation uniformly at random without critique."""
    cand = game.copy()
    free_cells = get_free_inner_cells(cand)
    inner_walls = [w for w in cand.walls if 0 < w[0] < cand.width - 1 and 0 < w[1] < cand.height - 1]

    possible_ops = []
    if free_cells:
        possible_ops.append("add_wall")
        possible_ops.append("add_hazard")
        possible_ops.append("move_start")
        possible_ops.append("move_goal")
    if inner_walls:
        possible_ops.append("remove_wall")
    if cand.hazards:
        possible_ops.append("remove_hazard")
    if len(free_cells) >= 2 and not cand.key_pos:
        possible_ops.append("add_key_door")
    if cand.key_pos:
        possible_ops.append("remove_key_door")
    if len(free_cells) >= 2 and not cand.switch_pos:
        possible_ops.append("add_switch_gate")
    if cand.switch_pos:
        possible_ops.append("remove_switch_gate")
    if len(free_cells) >= 2 and not cand.teleport_a:
        possible_ops.append("add_teleporter")
    if cand.teleport_a:
        possible_ops.append("remove_teleporter")
    if free_cells and not cand.block_pos:
        possible_ops.append("add_block")
    if cand.block_pos:
        possible_ops.append("remove_block")

    op = rng.choice(possible_ops)
    if op == "add_wall":
        c = rng.choice(free_cells)
        cand.walls.add(c)
        desc = f"Random add wall at {c}"
    elif op == "remove_wall":
        w = rng.choice(inner_walls)
        cand.walls.remove(w)
        desc = f"Random remove wall at {w}"
    elif op == "add_hazard":
        c = rng.choice(free_cells)
        cand.hazards.add(c)
        desc = f"Random add hazard at {c}"
    elif op == "remove_hazard":
        h = rng.choice(list(cand.hazards))
        cand.hazards.remove(h)
        desc = f"Random remove hazard at {h}"
    elif op == "move_start":
        c = rng.choice(free_cells)
        cand.start_pos = c
        desc = f"Random move start to {c}"
    elif op == "move_goal":
        c = rng.choice(free_cells)
        cand.goal_pos = c
        desc = f"Random move goal to {c}"
    elif op == "add_key_door":
        cand.key_pos = free_cells[0]
        cand.door_pos = free_cells[1]
        desc = f"Random add key-door pair"
    elif op == "remove_key_door":
        cand.key_pos = None
        cand.door_pos = None
        desc = "Random remove key-door pair"
    elif op == "add_switch_gate":
        cand.switch_pos = free_cells[0]
        cand.gate_pos = free_cells[1]
        desc = "Random add switch-gate pair"
    elif op == "remove_switch_gate":
        cand.switch_pos = None
        cand.gate_pos = None
        desc = "Random remove switch-gate pair"
    elif op == "add_teleporter":
        cand.teleport_a = free_cells[0]
        cand.teleport_b = free_cells[1]
        desc = "Random add teleporter pair"
    elif op == "remove_teleporter":
        cand.teleport_a = None
        cand.teleport_b = None
        desc = "Random remove teleporter"
    elif op == "add_block":
        cand.block_pos = free_cells[0]
        desc = "Random add block"
    elif op == "remove_block":
        cand.block_pos = None
        desc = "Random remove block"
    else:
        desc = "Random no-op"

    return cand, desc


# =========================================================================
# 6. LEXICOGRAPHIC ACCEPT / REJECT EVALUATION
# =========================================================================

def decide_acceptance(m_curr, m_cand, curr_critique):
    """
    Fixed pre-registered lexicographic comparison:
    1. Avoid unsolvable game (success > 0)
    2. Strategic gap over random player (succ - rand_succ)
    3. Avoid trivial strategy (mean actions >= 8, action entropy)
    4. Successful trajectory diversity (unique trajectories)
    5. Reduce useless loops / dead ends
    6. State coverage / discovery
    """
    s_curr = m_curr["success_rate"]
    s_cand = m_cand["success_rate"]
    gap_curr = m_curr["strategic_gap"]
    gap_cand = m_cand["strategic_gap"]
    act_curr = m_curr["mean_actions_to_goal"]
    act_cand = m_cand["mean_actions_to_goal"]
    uniq_curr = m_curr["unique_successful_trajectories"]
    uniq_cand = m_cand["unique_successful_trajectories"]
    loop_curr = m_curr["repeated_loop_rate"]
    loop_cand = m_cand["repeated_loop_rate"]
    cov_curr = m_curr["state_coverage"]
    cov_cand = m_cand["state_coverage"]

    # Criterion 1: Solvability gate
    if s_curr > 0.0 and s_cand == 0.0:
        return False, "Rejected: candidate rendered game unsolvable"
    if s_curr == 0.0 and s_cand > 0.0:
        return True, "Accepted: rescued unsolvable game to solvable"

    # Criterion 2: Strategy advantage over random
    if gap_cand >= gap_curr + 0.10:
        return True, f"Accepted: significantly increased strategic advantage (+{gap_cand - gap_curr:.2f})"
    if gap_cand <= gap_curr - 0.15:
        return False, f"Rejected: degraded strategic advantage ({gap_cand - gap_curr:.2f})"

    # Criterion 3: Non-triviality (escaped trivial / too-easy rush)
    if curr_critique in ["TOO_EASY", "TRIVIAL_STRATEGY"]:
        if act_cand >= 8.0 and s_cand >= 0.70 and gap_cand >= gap_curr - 0.05:
            return True, f"Accepted: cured trivial rush (mean actions {act_curr} -> {act_cand})"

    # Criterion 4: Trajectory diversity
    if uniq_cand >= uniq_curr + 1 and s_cand >= 0.70:
        return True, f"Accepted: expanded trajectory diversity ({uniq_curr} -> {uniq_cand})"
    if uniq_cand < uniq_curr and s_cand <= s_curr:
        return False, "Rejected: reduced trajectory diversity"

    # Criterion 5: Loop reduction
    if loop_cand <= loop_curr - 0.08 and s_cand >= s_curr - 0.05:
        return True, f"Accepted: reduced loop cycles ({loop_curr:.2f} -> {loop_cand:.2f})"

    # Criterion 6: State richness
    if cov_cand >= cov_curr + 6 and s_cand >= 0.70 and gap_cand >= gap_curr - 0.05:
        return True, f"Accepted: increased state richness ({cov_curr} -> {cov_cand})"

    return False, "Rejected: neutral or insufficient lexicographic improvement"


# =========================================================================
# 7. CLOSED-LOOP SELF-DESIGN RUNNER
# =========================================================================

def run_self_design_loop(initial_game, num_iterations=20, is_control=False, seed=42):
    rng = random.Random(seed)
    current_game = initial_game.copy()
    
    # Initial evaluation
    current_metrics = evaluate_game(current_game)
    current_critique = critique_game(current_metrics)

    history = [{
        "iteration": 0,
        "critique": current_critique,
        "mutation": "Initial G0",
        "accepted": True,
        "metrics": current_metrics,
        "game": current_game.to_dict()
    }]

    print(f"  Iter  0 | Critique: {current_critique:16s} | Succ: {current_metrics['success_rate']*100:5.1f}% | Rand: {current_metrics['random_success_rate']*100:5.1f}% | Gap: {current_metrics['strategic_gap']:+5.2f} | Traj: {current_metrics['unique_successful_trajectories']:2d} | States: {current_metrics['state_coverage']:3d}")

    accepted_count = 0

    for it in range(1, num_iterations + 1):
        if is_control:
            cand_game, mutation_desc = apply_random_mutation(current_game, rng)
        else:
            cand_game, mutation_desc = apply_targeted_mutation(current_game, current_critique, rng)

        cand_metrics = evaluate_game(cand_game)
        cand_critique = critique_game(cand_metrics)

        accepted, reason = decide_acceptance(current_metrics, cand_metrics, current_critique)

        if accepted:
            current_game = cand_game
            current_metrics = cand_metrics
            current_critique = cand_critique
            accepted_count += 1
            verdict_str = "ACCEPTED"
        else:
            verdict_str = "REJECTED"

        history.append({
            "iteration": it,
            "critique": current_critique,
            "mutation": mutation_desc,
            "accepted": accepted,
            "decision_reason": reason,
            "metrics": current_metrics,
            "candidate_metrics": cand_metrics,
            "candidate_game": cand_game.to_dict(),
            "game": current_game.to_dict()
        })

        print(f"  Iter {it:2d} | {verdict_str:8s} | Critique: {current_critique:16s} | Succ: {current_metrics['success_rate']*100:5.1f}% | Rand: {current_metrics['random_success_rate']*100:5.1f}% | Gap: {current_metrics['strategic_gap']:+5.2f} | Traj: {current_metrics['unique_successful_trajectories']:2d} | Edit: {mutation_desc[:35]}")

    return current_game, history, accepted_count


# =========================================================================
# 8. EXECUTION: EXPERIMENTAL CONDITION VS RANDOM CONTROL
# =========================================================================

def run_experiment():
    print("-" * 80)
    print("1. GENERATING INITIAL GAME G0")
    print("-" * 80)
    G0 = MicroGame(seed=101)
    G0.generate_random(wall_density=0.18)
    print(f"  G0 Created: Start={G0.start_pos}, Goal={G0.goal_pos}, Walls={len(G0.walls)}")
    print(f"  Mechanics in G0: Key={G0.key_pos}, Door={G0.door_pos}, Switch={G0.switch_pos}, Gate={G0.gate_pos}, Teleport=({G0.teleport_a} <-> {G0.teleport_b}), Hazards={len(G0.hazards)}\n")

    print("-" * 80)
    print("2. RUNNING CONDITION B: MORTRA SELF-DESIGNER (Targeted by Self-Critique)")
    print("-" * 80)
    G_final_designer, history_designer, accepted_designer = run_self_design_loop(G0, num_iterations=20, is_control=False, seed=42)

    print("\n" + "-" * 80)
    print("3. RUNNING CONDITION A: RANDOM MUTATION CONTROL (Uniform Mutation, No Critique)")
    print("-" * 80)
    G_final_control, history_control, accepted_control = run_self_design_loop(G0, num_iterations=20, is_control=True, seed=42)


    # =========================================================================
    # 9. CREATION TEST: 5 INDEPENDENT SEEDS
    # =========================================================================
    print("\n" + "-" * 80)
    print("4. CREATION TEST: Evaluating 5 Independent Seeds from Scratch")
    print("-" * 80)

    creation_test_results = []
    creation_seeds = [201, 302, 403, 504, 605]

    for idx, s in enumerate(creation_seeds, start=1):
        print(f"\n  [Seed {s} (Game {idx})]")
        g_init = MicroGame(seed=s)
        g_init.generate_random(wall_density=0.18)
        g_fin, hist, acc = run_self_design_loop(g_init, num_iterations=10, is_control=False, seed=s)
        
        init_m = hist[0]["metrics"]
        fin_m = hist[-1]["metrics"]
        
        unique_edits = set(h["mutation"] for h in hist if h["accepted"] and h["iteration"] > 0)
        surviving_mechanics = []
        if g_fin.door_pos: surviving_mechanics.append("KeyDoor")
        if g_fin.gate_pos: surviving_mechanics.append("SwitchGate")
        if g_fin.teleport_a: surviving_mechanics.append("Teleporter")
        if g_fin.hazards: surviving_mechanics.append(f"Hazard({len(g_fin.hazards)})")
        if g_fin.block_pos: surviving_mechanics.append("MovableBlock")

        res_entry = {
            "game_id": idx,
            "seed": s,
            "start": g_fin.start_pos,
            "goal": g_fin.goal_pos,
            "accepted_edits": acc,
            "unique_edits_count": len(unique_edits),
            "initial_gap": init_m["strategic_gap"],
            "final_gap": fin_m["strategic_gap"],
            "initial_diversity": init_m["unique_successful_trajectories"],
            "final_diversity": fin_m["unique_successful_trajectories"],
            "surviving_mechanics": surviving_mechanics,
            "collapsed": False
        }
        creation_test_results.append(res_entry)
        print(f"  --> Seed {s} Summary: Gap {init_m['strategic_gap']:+.2f} -> {fin_m['strategic_gap']:+.2f} | Diversity {init_m['unique_successful_trajectories']} -> {fin_m['unique_successful_trajectories']} | Mechanics: {', '.join(surviving_mechanics)}")


    # Check if 5 games collapsed to identical form
    layouts = [tuple(sorted(list(r["surviving_mechanics"]))) for r in creation_test_results]
    distinct_layouts = len(set(layouts))
    no_collapse = (distinct_layouts >= 3)
    print(f"\n  Distinct final mechanic configurations: {distinct_layouts} / 5 (Collapsed: {not no_collapse})")


    # =========================================================================
    # 10. GENERATING PUBLICATION FIGURES & ARTIFACTS
    # =========================================================================
    print("\n" + "-" * 80)
    print("5. Generating Visual Artifacts & Reports...")
    print("-" * 80)

    def render_game_map(ax, game, title, trajectories=None):
        ax.set_xlim(-0.5, game.width - 0.5)
        ax.set_ylim(-0.5, game.height - 0.5)
        ax.set_aspect('equal')
        ax.invert_yaxis()
        ax.set_xticks(range(game.width))
        ax.set_yticks(range(game.height))
        ax.grid(color='#d0d0d0', linestyle='--', linewidth=0.5)

        # Walls
        for (wx, wy) in game.walls:
            ax.add_patch(patches.Rectangle((wx - 0.5, wy - 0.5), 1, 1, facecolor='#2b2d42', edgecolor='#1a1a24'))

        # Hazards
        for (hx, hy) in game.hazards:
            ax.add_patch(patches.Rectangle((hx - 0.5, hy - 0.5), 1, 1, facecolor='#ef233c', alpha=0.7, edgecolor='red'))
            ax.text(hx, hy, "X", color='white', ha='center', va='center', fontweight='bold', fontsize=9)

        # Teleporters
        if game.teleport_a:
            ax.add_patch(patches.Circle((game.teleport_a[0], game.teleport_a[1]), 0.4, facecolor='#8338ec', edgecolor='#5a189a'))
            ax.text(game.teleport_a[0], game.teleport_a[1], "T1", color='white', ha='center', va='center', fontsize=8, fontweight='bold')
        if game.teleport_b:
            ax.add_patch(patches.Circle((game.teleport_b[0], game.teleport_b[1]), 0.4, facecolor='#8338ec', edgecolor='#5a189a'))
            ax.text(game.teleport_b[0], game.teleport_b[1], "T2", color='white', ha='center', va='center', fontsize=8, fontweight='bold')

        # Switch & Gate
        if game.switch_pos:
            ax.add_patch(patches.Rectangle((game.switch_pos[0] - 0.35, game.switch_pos[1] - 0.35), 0.7, 0.7, facecolor='#ffbe0b', edgecolor='#fb5607'))
            ax.text(game.switch_pos[0], game.switch_pos[1], "SW", color='black', ha='center', va='center', fontsize=7, fontweight='bold')
        if game.gate_pos:
            ax.add_patch(patches.Rectangle((game.gate_pos[0] - 0.45, game.gate_pos[1] - 0.45), 0.9, 0.9, facecolor='#ff006e', edgecolor='#c1121f', hatch='//'))
            ax.text(game.gate_pos[0], game.gate_pos[1], "GT", color='white', ha='center', va='center', fontsize=7, fontweight='bold')

        # Key & Door
        if game.key_pos:
            ax.add_patch(patches.Circle((game.key_pos[0], game.key_pos[1]), 0.35, facecolor='#ffd166', edgecolor='#e76f51'))
            ax.text(game.key_pos[0], game.key_pos[1], "K", color='black', ha='center', va='center', fontsize=8, fontweight='bold')
        if game.door_pos:
            ax.add_patch(patches.Rectangle((game.door_pos[0] - 0.45, game.door_pos[1] - 0.45), 0.9, 0.9, facecolor='#06d6a0', edgecolor='#073b4c'))
            ax.text(game.door_pos[0], game.door_pos[1], "D", color='black', ha='center', va='center', fontsize=8, fontweight='bold')

        # Block
        if game.block_pos:
            ax.add_patch(patches.Rectangle((game.block_pos[0] - 0.4, game.block_pos[1] - 0.4), 0.8, 0.8, facecolor='#adb5bd', edgecolor='#495057'))
            ax.text(game.block_pos[0], game.block_pos[1], "B", color='black', ha='center', va='center', fontsize=8, fontweight='bold')

        # Start & Goal
        ax.add_patch(patches.Circle((game.start_pos[0], game.start_pos[1]), 0.45, facecolor='#3a86ff', edgecolor='#023e8a'))
        ax.text(game.start_pos[0], game.start_pos[1], "S", color='white', ha='center', va='center', fontsize=9, fontweight='bold')
        ax.add_patch(patches.Circle((game.goal_pos[0], game.goal_pos[1]), 0.45, facecolor='#38b000', edgecolor='#007200'))
        ax.text(game.goal_pos[0], game.goal_pos[1], "G", color='white', ha='center', va='center', fontsize=9, fontweight='bold')

        # Plot sample trajectories
        if trajectories:
            colors = ['#0077b6', '#0096c7', '#48cae4', '#90e0ef', '#023e8a']
            for i, traj in enumerate(trajectories[:5]):
                xs = [p[0] for p in traj]
                ys = [p[1] for p in traj]
                ax.plot(xs, ys, color=colors[i % len(colors)], linewidth=2.0, alpha=0.7, linestyle='-')

        ax.set_title(title, fontsize=11, fontweight='bold', pad=8)

    # 1. Figure: initial_vs_final.png
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    init_m = history_designer[0]["metrics"]
    fin_m = history_designer[-1]["metrics"]
    render_game_map(axes[0], G0, f"Initial Game G0\nGap: {init_m['strategic_gap']:+.2f} | Traj: {init_m['unique_successful_trajectories']}", trajectories=init_m["sample_trajectories"])
    render_game_map(axes[1], G_final_designer, f"MORTRA Self-Designed Game (Iter 20)\nGap: {fin_m['strategic_gap']:+.2f} | Traj: {fin_m['unique_successful_trajectories']} | Accepted Edits: {accepted_designer}", trajectories=fin_m["sample_trajectories"])
    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "initial_vs_final.png"), dpi=200)
    plt.close(fig)

    # 2. Figure: evolution_grid.png (4x5 showing all 20 iterations)
    fig, axes = plt.subplots(4, 5, figsize=(20, 16))
    axes = axes.flatten()
    for it in range(1, 21):
        step_info = history_designer[it]
        step_game = MicroGame()
        step_game.walls = set(tuple(p) for p in step_info["game"]["walls"])
        step_game.hazards = set(tuple(p) for p in step_info["game"]["hazards"])
        step_game.start_pos = tuple(step_info["game"]["start_pos"])
        step_game.goal_pos = tuple(step_info["game"]["goal_pos"])
        step_game.key_pos = tuple(step_info["game"]["key_pos"]) if step_info["game"]["key_pos"] else None
        step_game.door_pos = tuple(step_info["game"]["door_pos"]) if step_info["game"]["door_pos"] else None
        step_game.switch_pos = tuple(step_info["game"]["switch_pos"]) if step_info["game"]["switch_pos"] else None
        step_game.gate_pos = tuple(step_info["game"]["gate_pos"]) if step_info["game"]["gate_pos"] else None
        step_game.teleport_a = tuple(step_info["game"]["teleport_a"]) if step_info["game"]["teleport_a"] else None
        step_game.teleport_b = tuple(step_info["game"]["teleport_b"]) if step_info["game"]["teleport_b"] else None
        step_game.block_pos = tuple(step_info["game"]["block_pos"]) if step_info["game"]["block_pos"] else None

        badge = "[ACC]" if step_info["accepted"] else "[REJ]"
        render_game_map(axes[it - 1], step_game, f"It {it:2d} {badge}: {step_info['critique']}\nGap: {step_info['metrics']['strategic_gap']:+.2f}")
    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "evolution_grid.png"), dpi=180)
    plt.close(fig)

    # 3. Figure: trajectory_examples.png
    fig, ax = plt.subplots(figsize=(8, 8))
    render_game_map(ax, G_final_designer, f"MORTRA Multi-Path Trajectory Diversity (Final Game)\n{fin_m['unique_successful_trajectories']} Unique Successful Paths Discovered", trajectories=fin_m["sample_trajectories"])
    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "trajectory_examples.png"), dpi=200)
    plt.close(fig)

    # 4. Figure: control_comparison.png
    iters = list(range(21))
    gap_des = [h["metrics"]["strategic_gap"] for h in history_designer]
    gap_ctrl = [h["metrics"]["strategic_gap"] for h in history_control]
    div_des = [h["metrics"]["unique_successful_trajectories"] for h in history_designer]
    div_ctrl = [h["metrics"]["unique_successful_trajectories"] for h in history_control]
    loop_des = [h["metrics"]["repeated_loop_rate"] for h in history_designer]
    loop_ctrl = [h["metrics"]["repeated_loop_rate"] for h in history_control]
    cov_des = [h["metrics"]["state_coverage"] for h in history_designer]
    cov_ctrl = [h["metrics"]["state_coverage"] for h in history_control]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    # Plot 1: Strategic Gap
    axes[0, 0].plot(iters, gap_des, 'o-', color='#2a9d8f', linewidth=2.5, label='MORTRA Self-Designer')
    axes[0, 0].plot(iters, gap_ctrl, 's--', color='#e76f51', linewidth=2.0, label='Random Mutation Control')
    axes[0, 0].set_title('Strategic Gap (MORTRA vs Random Player)', fontweight='bold')
    axes[0, 0].set_xlabel('Iteration')
    axes[0, 0].set_ylabel('Success Rate Gap')
    axes[0, 0].grid(True, linestyle='--', alpha=0.6)
    axes[0, 0].legend()

    # Plot 2: Trajectory Diversity
    axes[0, 1].plot(iters, div_des, 'o-', color='#3a86ff', linewidth=2.5, label='MORTRA Self-Designer')
    axes[0, 1].plot(iters, div_ctrl, 's--', color='#f4a261', linewidth=2.0, label='Random Mutation Control')
    axes[0, 1].set_title('Trajectory Diversity (Unique Success Paths)', fontweight='bold')
    axes[0, 1].set_xlabel('Iteration')
    axes[0, 1].set_ylabel('Unique Trajectories')
    axes[0, 1].grid(True, linestyle='--', alpha=0.6)
    axes[0, 1].legend()

    # Plot 3: Repeated Loop Rate
    axes[1, 0].plot(iters, loop_des, 'o-', color='#8338ec', linewidth=2.5, label='MORTRA Self-Designer')
    axes[1, 0].plot(iters, loop_ctrl, 's--', color='#d62828', linewidth=2.0, label='Random Mutation Control')
    axes[1, 0].set_title('Repeated Loop Rate (Cycle Traps)', fontweight='bold')
    axes[1, 0].set_xlabel('Iteration')
    axes[1, 0].set_ylabel('Loop Rate')
    axes[1, 0].grid(True, linestyle='--', alpha=0.6)
    axes[1, 0].legend()

    # Plot 4: State Coverage
    axes[1, 1].plot(iters, cov_des, 'o-', color='#06d6a0', linewidth=2.5, label='MORTRA Self-Designer')
    axes[1, 1].plot(iters, cov_ctrl, 's--', color='#6c757d', linewidth=2.0, label='Random Mutation Control')
    axes[1, 1].set_title('Discovered State Richness', fontweight='bold')
    axes[1, 1].set_xlabel('Iteration')
    axes[1, 1].set_ylabel('Unique States')
    axes[1, 1].grid(True, linestyle='--', alpha=0.6)
    axes[1, 1].legend()

    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "control_comparison.png"), dpi=200)
    plt.close(fig)


    # The creation-seed loop uses the same local names; export the main run.
    init_m = history_designer[0]["metrics"]
    fin_m = history_designer[-1]["metrics"]
    # 12. SAVE JSON & MARKDOWN ARTIFACTS
    with open(os.path.join(OUTPUT_DIR, "game_initial.json"), "w", encoding="utf-8") as f:
        json.dump(G0.to_dict(), f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "game_final.json"), "w", encoding="utf-8") as f:
        json.dump(G_final_designer.to_dict(), f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "evolution_history.json"), "w", encoding="utf-8") as f:
        json.dump({
            "designer_history": history_designer,
            "control_history": history_control
        }, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "self_play_metrics.json"), "w", encoding="utf-8") as f:
        json.dump({
            "initial_metrics": init_m,
            "final_designer_metrics": fin_m,
            "final_control_metrics": history_control[-1]["metrics"],
            "accepted_designer_count": accepted_designer,
            "accepted_control_count": accepted_control,
            "creation_test": creation_test_results
        }, f, indent=2)

    # Generate critique_history.md
    critique_md = [
        "# Autonomous Self-Game-Design Critique History\n",
        "| Iteration | Self-Critique | Proposed Mutation | Decision | Success Rate | Random Player | Strategic Gap | Trajectory Diversity |",
        "| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |"
    ]
    for h in history_designer:
        it = h["iteration"]
        crit = h["critique"]
        mut = h["mutation"]
        dec = "ACCEPTED" if h["accepted"] else "REJECTED"
        m = h["metrics"]
        critique_md.append(f"| {it:2d} | `{crit}` | {mut} | **{dec}** | {m['success_rate']*100:.1f}% | {m['random_success_rate']*100:.1f}% | {m['strategic_gap']:+.2f} | {m['unique_successful_trajectories']} |")

    with open(os.path.join(OUTPUT_DIR, "critique_history.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(critique_md) + "\n")

    print(f"\nAll artifacts successfully saved to: {OUTPUT_DIR}")
    print("Closed-loop self-game-design experiment complete.")


def prepare_output(path):
    target = Path(path).resolve()
    legacy = Path(workspace_root, "reports", "self_game_design").resolve()
    if target == legacy or legacy in target.parents:
        raise ValueError("The legacy experiment is immutable; use a new output directory")
    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        raise ValueError(f"Refusing to overwrite existing artifacts: {target}")
    return target


def main():
    global OUTPUT_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=OUTPUT_DIR)
    args = parser.parse_args()
    output = prepare_output(args.output)
    OUTPUT_DIR = str(output)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace_root, text=True).strip()
    source = Path(__file__).resolve()
    metadata = {
        "experiment_id": "self-game-design-v2-20260923", "version": 2,
        "repository": "corcondor/mortra", "commit_sha": sha,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(),
        "dependencies": {"numpy": np.__version__, "matplotlib": matplotlib.__version__},
        "command": [sys.executable, *sys.argv],
        "config": {"generation_seed": 101, "mutation_seed": 42, "random_player_seed": 999,
                   "creation_seeds": [201, 302, 403, 504, 605], "exploration_steps": 2500,
                   "trials": 50, "max_play_steps": 100, "design_iterations": 20,
                   "creation_iterations": 10, "q": 0.90, "wall_density": 0.18},
        "replay_selection": "Trial 0, selected before outcomes; states include all game variables",
        "limitations": ["Fixed 12x12 rules and hand-written critique/mutation/acceptance policies",
                        "Fresh structural learner per evaluation; no cross-world persistent memory",
                        "Trials share one deterministic layout and learned graph; not independent worlds"]
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    terminal = sys.stdout
    if hasattr(terminal, "reconfigure"):
        terminal.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    logger = TeeLogger(output / "run.log", terminal)
    sys.stdout = logger
    started = time.perf_counter()
    try:
        print("MORTRA AUTONOMOUS SELF-GAME-DESIGN V2: FRESH FULL RUN")
        print(json.dumps(metadata, indent=2))
        run_experiment()
        metadata["status"] = "complete"
    except BaseException:
        metadata["status"] = "failed"
        raise
    finally:
        metadata["wall_seconds"] = time.perf_counter() - started
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        sys.stdout = terminal
        logger.log.close()


if __name__ == "__main__":
    main()
