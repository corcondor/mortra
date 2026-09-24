"""Opaque-experience player; the only imported algorithm is the frozen 9/23 core."""
import hashlib
import pickle
import time

import numpy as np

from .frozen import StructuralLearner, solve_fixed_field


def fingerprint(learner):
    return hashlib.sha256(pickle.dumps(learner.__dict__, protocol=5)).hexdigest()


def rollout(port, learner, psi, max_steps, rng):
    """Baseline modal-successor/argmax readout with the public is_goal predicate.

    Same unknown-state checks, field cutoff, missing-action score and tie order
    as run_fixed_field_policy. No exploration updates are made here.
    """
    obs = port.reset()
    actions, observations = [], [obs]
    reason = "readout_error"
    for _ in range(max_steps):
        if port.is_goal():
            reason = "success"
            break
        if obs not in learner.state_to_id:
            reason = "unmatched_state"
            break
        u = learner.state_to_id[obs]
        if psi[u] < 1e-7:
            reason = "disconnected"
            break
        scores = np.zeros(len(port.available_actions())) - 1.0
        for a in port.available_actions():
            if (u, a) in learner.counts:
                v = max(learner.counts[(u, a)].items(), key=lambda it: it[1])[0]
                scores[a] = psi[v]
        action = int(rng.integers(len(scores))) if np.max(scores) < 0 else int(np.argmax(scores))
        obs = port.step(action)
        actions.append(action)
        observations.append(obs)
    success = bool(port.is_goal())
    if success:
        reason = "success"
    return {"success": success, "steps": len(actions), "reason": reason,
            "actions": actions, "observations": observations}


def evaluate_frozen(learner, goals, port, trials, max_steps, seed):
    before = fingerprint(learner)
    t0 = time.process_time()
    K = learner.build_k_support()
    # The original NumPy indexing accepts a list of experienced goal nodes.
    # This is g=1 on observed goals, never on oracle-supplied or unseen states.
    goal_nodes = sorted(learner.state_to_id[g] for g in goals)
    if goal_nodes:
        psi, iterations, residual, converged = solve_fixed_field(K, goal_nodes, q=0.90)
    else:
        psi, iterations, residual, converged = np.zeros(len(K)), 0, None, None
    solve_cpu = time.process_time() - t0
    rng = np.random.default_rng(seed)
    records = [rollout(port, learner, psi, max_steps, rng) for _ in range(trials)]
    assert before == fingerprint(learner), "evaluation changed learner"
    successes = sum(r["success"] for r in records)
    assert 0 <= successes <= trials
    compact = []
    for i, r in enumerate(records):
        compact.append({**{k: r[k] for k in ("success", "steps", "reason")}, "trial": i,
                        "trajectory_sha256": hashlib.sha256(pickle.dumps((r["actions"], r["observations"]))).hexdigest()})
    return {"successes": successes, "trials": trials, "success_rate": successes / trials,
            "mean_steps": sum(r["steps"] for r in records) / trials,
            "mean_success_steps": (sum(r["steps"] for r in records if r["success"]) / successes if successes else None),
            "trials_detail": compact, "first_trial": records[0], "q": 0.90,
            "fixed_field_iterations": iterations, "fixed_field_residual": residual,
            "fixed_field_converged": converged, "observed_goal_count": len(goals),
            "learner_fingerprint": before, "evaluation_updates": 0,
            "reasoning_cpu_seconds": solve_cpu, "evaluation_cpu_seconds": time.process_time() - t0,
            "K_bytes": K.nbytes, "K_nonzero": int(np.count_nonzero(K))}


def random_policy(port, trials, max_steps, seed):
    rng = np.random.default_rng(seed)
    results = []
    for trial in range(trials):
        port.reset()
        steps = 0
        actions = []
        while steps < max_steps and not port.is_goal():
            a = int(rng.integers(len(port.available_actions())))
            port.step(a)
            actions.append(a)
            steps += 1
        results.append({"trial": trial, "success": bool(port.is_goal()), "steps": steps,
                        "actions": actions if trial == 0 else None})
    successes = sum(r["success"] for r in results)
    assert 0 <= successes <= trials
    return {"successes": successes, "trials": trials, "success_rate": successes / trials, "trials_detail": results}


def learn_game(train_port, eval_port, checkpoints, trials, max_steps, seed):
    """Fresh model per candidate; continuous training, separate evaluation session."""
    learner = StructuralLearner(len(train_port.available_actions()))
    obs = train_port.reset()
    u = learner.get_or_add_id(obs)
    goals = {obs} if train_port.is_goal() else set()
    output = []
    previous = 0
    train_cpu = 0.0
    for budget in checkpoints:
        t0 = time.process_time()
        for _ in range(previous, budget):
            action = learner.select_action(u)
            nxt = train_port.step(action)
            v = learner.get_or_add_id(nxt)
            learner.record_transition(u, action, v)
            if train_port.is_goal():
                goals.add(nxt)
            u = v
        train_cpu += time.process_time() - t0
        current_obs = train_port.current_observation()
        evaluation = evaluate_frozen(learner, goals, eval_port, trials, max_steps, seed + budget)
        assert train_port.current_observation() == current_obs, "evaluation changed training environment"
        n = len(learner.id_to_state)
        edges = sum(len(v) for v in learner.counts.values())
        output.append({"budget": budget, "learned_states": n, "learned_transitions": edges,
                       "unique_graph_edges": len({(s, v) for (s, _), values in learner.counts.items() for v in values}),
                       "tried_state_action_fraction": len(learner.counts) / (n * learner.num_actions),
                       "training_cpu_seconds": train_cpu,
                       "learner_serialized_bytes": len(pickle.dumps(learner.__dict__, protocol=5)),
                       "evaluation": evaluation})
        previous = budget
    return output
