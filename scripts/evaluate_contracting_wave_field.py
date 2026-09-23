"""
Evaluate Contracting Wave Field Planning on Fixed 5 Obstacle Environments.

Isolates the planner principle:
- No NN, no world model training, no CEM.
- Discretizes environment into state graph G = (V, E) using simulator transitions.
- Evaluates:
  A. Complex coherent fixed-field: psi_{n+1} = g_source + q K psi_n (q=0.90)
  B. Magnitude-only fixed-field: psi^{mag}_{n+1} = g_source^{mag} + q |K| psi^{mag}_n
  C. Independent (baseline)
  D. Greedy & 40D CEM (recorded baselines)

Outputs:
reports/contracting_wave_field/
    metrics.json
    convergence.png
    field_maps.png
    trajectory_comparison.png
    path_order_expansion.png
    run.log
"""

import os
import sys
import json
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from scripts.mortra_agent_v01_obstacles import Obstacle2DWorldEnv

OUTPUT_DIR = os.path.join(workspace_root, "reports", "contracting_wave_field")
os.makedirs(OUTPUT_DIR, exist_ok=True)
LOG_FILE = os.path.join(OUTPUT_DIR, "run.log")

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

sys.stdout = TeeLogger(LOG_FILE, sys.stdout)

# ---------------------------------------------------------
# 1. State Graph Construction from Simulator
# ---------------------------------------------------------
def build_state_graph(env: Obstacle2DWorldEnv, grid_res=2.0):
    """Discretizes arena into valid non-colliding nodes and 8-action transition graph."""
    xs = np.arange(4.0, 60.0, grid_res)
    ys = np.arange(4.0, 60.0, grid_res)
    
    nodes = []
    for y in ys:
        for x in xs:
            pos = np.array([x, y], dtype=np.float32)
            if not env.check_collision(pos):
                nodes.append(pos)
    nodes = np.array(nodes, dtype=np.float32) # (N, 2)
    N = len(nodes)
    
    # 8 directional actions (unit vectors)
    angles = np.linspace(0, 2.0 * np.pi, 8, endpoint=False)
    actions = np.stack([np.cos(angles), np.sin(angles)], axis=1).astype(np.float32)
    
    # Transition table: T[s, a] = next_s
    T = np.zeros((N, 8), dtype=int)
    for i in range(N):
        for a_idx, a in enumerate(actions):
            env.ctrl_pos = nodes[i].copy()
            _, _, _ = env.step(a)
            next_pos = env.ctrl_pos
            # Find nearest node
            d2 = np.sum((nodes - next_pos)**2, axis=1)
            T[i, a_idx] = np.argmin(d2)
            
    # Find goal node and start node
    goal_node = np.argmin(np.sum((nodes - env.goal_pos)**2, axis=1))
    start_node = np.argmin(np.sum((nodes - env.ctrl_pos)**2, axis=1))
    
    return nodes, actions, angles, T, start_node, goal_node

# ---------------------------------------------------------
# 2. Complex Propagation Operator K & Contraction Fixed Point
# ---------------------------------------------------------
def build_propagation_operator(N, T, angles, condition="complex"):
    """
    Constructs sparse propagation operator K (N x N).
    K[s, s'] is non-zero when action from s leads to s'.
    Normalized so ||K||_inf <= 1.
    """
    K = np.zeros((N, N), dtype=complex if condition == "complex" else float)
    
    for s in range(N):
        for a_idx in range(8):
            next_s = T[s, a_idx]
            if condition == "complex":
                # Action phase theta_a
                phase = np.exp(1j * angles[a_idx])
                K[s, next_s] += phase / 8.0
            else:
                # Magnitude only
                K[s, next_s] += 1.0 / 8.0
                
    # Verify row normalization: ||K||_inf <= 1
    row_sums = np.sum(np.abs(K), axis=1)
    max_row = np.max(row_sums)
    assert max_row <= 1.0 + 1e-6, f"||K||_inf exceeds 1: {max_row}"
    return K

def compute_fixed_field(K, goal_node, q=0.90, max_iters=200, tol=1e-8, init_psi=None):
    """
    Computes fixed point psi* = g_source + q K psi via contraction mapping.
    Tracks residuals and order expansion terms.
    """
    N = K.shape[0]
    is_complex = np.iscomplexobj(K)
    g_source = np.zeros(N, dtype=complex if is_complex else float)
    g_source[goal_node] = 1.0 + (0j if is_complex else 0.0)
    
    if init_psi is None:
        psi = np.zeros(N, dtype=complex if is_complex else float)
    else:
        psi = init_psi.copy()
        
    residuals = []
    order_terms = [g_source.copy()] # order 0 = g_source
    curr_order = g_source.copy()
    
    t0 = time.time()
    for it in range(1, max_iters + 1):
        psi_next = g_source + q * (K @ psi)
        res = float(np.max(np.abs(psi_next - psi)))
        residuals.append(res)
        
        # Track Neumann expansion term: q^m K^m g
        if it <= 20:
            curr_order = q * (K @ curr_order)
            order_terms.append(curr_order.copy())
            
        if res < tol:
            break
        psi = psi_next
        
    converged = (residuals[-1] < tol)
    return psi, residuals, order_terms, converged

# ---------------------------------------------------------
# 3. Action Readout & Policy Execution
# ---------------------------------------------------------
def run_fixed_field_episode(env, nodes, actions, angles, T, psi_field, is_complex=True, max_steps=40):
    """Executes closed-loop episode using local action readout from psi_field."""
    p_start = env.ctrl_pos.copy()
    p_goal = env.goal_pos.copy()
    dist_start = float(np.linalg.norm(p_start - p_goal))
    
    traj = [p_start.copy()]
    dists = [dist_start]
    done = False
    step = 0
    
    while not done and step < max_steps:
        # Find nearest node to current continuous position
        curr_node = np.argmin(np.sum((nodes - env.ctrl_pos)**2, axis=1))
        
        # Local action readout: evaluate next states s_a = T[curr_node, a]
        action_scores = np.zeros(8, dtype=float)
        for a_idx in range(8):
            next_node = T[curr_node, a_idx]
            if is_complex:
                # Local complex flux: Re(exp(-i * theta_a) * psi[next_node]) or magnitude
                # Projecting incoming phase along action direction
                score_flux = float(np.real(np.exp(-1j * angles[a_idx]) * psi_field[next_node]))
                score_mag = float(np.abs(psi_field[next_node]))
                action_scores[a_idx] = score_mag + 0.1 * score_flux
            else:
                # Magnitude only: psi^{mag}[next_node]
                action_scores[a_idx] = float(np.real(psi_field[next_node]))
                
        # Pick action with maximum field reachability
        best_a_idx = int(np.argmax(action_scores))
        chosen_action = actions[best_a_idx]
        
        # Step in real simulator
        _, dist, done = env.step(chosen_action)
        traj.append(env.ctrl_pos.copy())
        dists.append(dist)
        step += 1
        
    success = 1.0 if dists[-1] < 4.5 else 0.0
    return {
        "success": success,
        "start_dist": dist_start,
        "final_dist": dists[-1],
        "steps": step,
        "traj": np.array(traj),
        "dists": dists,
        "min_dist": min(dists),
        "max_dist": max(dists),
        "retreat_detected": (max(dists) > dist_start + 1.5) and (dists[-1] < 4.5)
    }

# ---------------------------------------------------------
# 4. Main Experiment & Comparison
# ---------------------------------------------------------
def main():
    print("=" * 70)
    print("EVALUATING CONTRACTING WAVE FIELD (q = 0.90)")
    print("=" * 70)
    
    test_episodes = [
        {"ep": 1, "map": "direct", "seed": 70001},
        {"ep": 2, "map": "simple_detour", "seed": 70002},
        {"ep": 3, "map": "simple_detour", "seed": 70003},
        {"ep": 4, "map": "temporary_retreat", "seed": 70004},
        {"ep": 5, "map": "temporary_retreat", "seed": 70005}
    ]
    
    env = Obstacle2DWorldEnv()
    
    # Storage for results
    records_complex = []
    records_mag = []
    convergence_data = []
    
    # Verify contraction from different initial states on Ep 1
    env.reset(map_type="direct", seed=70001, is_eval=True)
    nodes_ep1, acts, angs, T, s0, g = build_state_graph(env, grid_res=2.0)
    K_c = build_propagation_operator(len(nodes_ep1), T, angs, condition="complex")
    
    psi_zero, res_zero, order_terms, conv_zero = compute_fixed_field(K_c, g, q=0.90)
    init_rand1 = np.random.randn(len(nodes_ep1)) + 1j * np.random.randn(len(nodes_ep1))
    psi_rand1, _, _, _ = compute_fixed_field(K_c, g, q=0.90, init_psi=init_rand1)
    init_rand2 = np.ones(len(nodes_ep1), dtype=complex) * (5.0 - 3.0j)
    psi_rand2, _, _, _ = compute_fixed_field(K_c, g, q=0.90, init_psi=init_rand2)
    
    diff1 = float(np.max(np.abs(psi_zero - psi_rand1)))
    diff2 = float(np.max(np.abs(psi_zero - psi_rand2)))
    same_fixed_point = (diff1 < 1e-7 and diff2 < 1e-7)
    
    print(f"Contraction test: diff(zero, rand1) = {diff1:.2e}, diff(zero, rand2) = {diff2:.2e}")
    print(f"Same fixed point from different initial states: {'YES' if same_fixed_point else 'NO'}\n")
    
    nodes_ep4 = None
    psi_c_ep4 = None
    psi_m_ep4 = None
    goal_ep4 = None

    # Evaluate all 5 episodes
    for cfg in test_episodes:
        ep_num = cfg["ep"]
        m_type = cfg["map"]
        s = cfg["seed"]
        
        print(f"--- Episode {ep_num}/5 | Map: {m_type} (Seed {s}) ---")
        
        # Build state graph for this environment
        env.reset(map_type=m_type, seed=s, is_eval=True)
        nodes, acts, angs, T, s0, g = build_state_graph(env, grid_res=2.0)
        
        # 1. Complex coherent field
        K_c = build_propagation_operator(len(nodes), T, angs, condition="complex")
        psi_c, res_c, _, conv_c = compute_fixed_field(K_c, g, q=0.90)
        env.reset(map_type=m_type, seed=s, is_eval=True)
        rec_c = run_fixed_field_episode(env, nodes, acts, angs, T, psi_c, is_complex=True)
        records_complex.append(rec_c)
        print(f"  Complex Field  : Succ={int(rec_c['success'])}, Dist={rec_c['final_dist']:.2f}px, Steps={rec_c['steps']}, Retreat={rec_c['retreat_detected']}")
        
        # 2. Magnitude-only field
        K_m = build_propagation_operator(len(nodes), T, angs, condition="magnitude")
        psi_m, res_m, _, conv_m = compute_fixed_field(K_m, g, q=0.90)
        env.reset(map_type=m_type, seed=s, is_eval=True)
        rec_m = run_fixed_field_episode(env, nodes, acts, angs, T, psi_m, is_complex=False)
        records_mag.append(rec_m)
        print(f"  Magnitude Field: Succ={int(rec_m['success'])}, Dist={rec_m['final_dist']:.2f}px, Steps={rec_m['steps']}, Retreat={rec_m['retreat_detected']}")
        
        if ep_num == 4:
            nodes_ep4 = nodes.copy()
            psi_c_ep4 = psi_c.copy()
            psi_m_ep4 = psi_m.copy()
            goal_ep4 = env.goal_pos.copy()

        convergence_data.append({
            "ep": ep_num,
            "map": m_type,
            "nodes": len(nodes),
            "iters_complex": len(res_c),
            "final_res_complex": res_c[-1],
            "residuals": res_c,
            "converged": conv_c and conv_m
        })
        
    # Summarize successes
    succ_c = int(sum([r["success"] for r in records_complex]))
    succ_m = int(sum([r["success"] for r in records_mag]))
    all_converged = all([c["converged"] for c in convergence_data])
    
    dir_c = sum([r["success"] for r_i, r in enumerate(records_complex) if test_episodes[r_i]["map"] == "direct"])
    det_c = sum([r["success"] for r_i, r in enumerate(records_complex) if test_episodes[r_i]["map"] == "simple_detour"])
    ret_c = sum([r["success"] for r_i, r in enumerate(records_complex) if test_episodes[r_i]["map"] == "temporary_retreat"])
    
    dir_m = sum([r["success"] for r_i, r in enumerate(records_mag) if test_episodes[r_i]["map"] == "direct"])
    det_m = sum([r["success"] for r_i, r in enumerate(records_mag) if test_episodes[r_i]["map"] == "simple_detour"])
    ret_m = sum([r["success"] for r_i, r in enumerate(records_mag) if test_episodes[r_i]["map"] == "temporary_retreat"])
    
    print("\n" + "=" * 70)
    print("PLANNER / FIELD COMPARISON TABLE")
    print("=" * 70)
    print(f"{'Planner / Field':<24} {'Direct':<8} {'Detour':<8} {'Retreat':<8} {'Total'}")
    print(f"{'Greedy':<24} {1:<8} {0:<8} {0:<8} 1/5")
    print(f"{'40D CEM':<24} {1:<8} {0:<8} {0:<8} 1/5")
    print(f"{'Complex fixed-field':<24} {int(dir_c):<8} {int(det_c):<8} {int(ret_c):<8} {succ_c}/5")
    print(f"{'Magnitude fixed-field':<24} {int(dir_m):<8} {int(det_m):<8} {int(ret_m):<8} {succ_m}/5")
    print("=" * 70)
    
    # Print required header
    print("\n" + "=" * 70)
    print(f"1. contraction converged: {'YES' if all_converged else 'NO'}")
    print(f"2. same fixed point from different initial states: {'YES' if same_fixed_point else 'NO'}")
    print(f"3. Complex success: {succ_c}/5")
    print(f"4. Magnitude-only success: {succ_m}/5")
    print("=" * 70)
    
    # Save metrics.json
    summary = {
        "contraction_converged": all_converged,
        "same_fixed_point_from_different_inits": same_fixed_point,
        "complex_success_count": succ_c,
        "magnitude_success_count": succ_m,
        "convergence_data": convergence_data,
        "episodes_complex": [{k: v for k, v in r.items() if k not in ["traj"]} for r in records_complex],
        "episodes_magnitude": [{k: v for k, v in r.items() if k not in ["traj"]} for r in records_mag]
    }
    with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
        json.dump(summary, f, indent=2)
        
    # ---------------------------------------------------------
    # Visualizations
    # ---------------------------------------------------------
    # 1. Convergence plot
    plt.figure(figsize=(8, 5))
    for c_d in convergence_data:
        plt.plot(c_d['residuals'], label=f"Ep {c_d['ep']} ({c_d['map']})")
    plt.axhline(1e-8, color='black', linestyle='--', label='Tolerance 1e-8')
    plt.yscale('log')
    plt.xlabel("Iteration")
    plt.ylabel("Residual ||psi_{n+1} - psi_n||_inf")
    plt.title("Contraction Mapping Geometric Convergence (q = 0.90)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "convergence.png"), dpi=150)
    plt.close()

    # 2. Path-order expansion plot (orders 0, 1, 2, 5, 10, 20)
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    orders_to_show = [0, 1, 2, 5, 10, 20]
    for idx, ord_k in enumerate(orders_to_show):
        ax = axes[idx // 3, idx % 3]
        term = order_terms[min(ord_k, len(order_terms)-1)]
        val = np.abs(term)
        sc = ax.scatter(nodes_ep1[:, 0], nodes_ep1[:, 1], c=val, cmap='viridis', s=20)
        ax.set_title(f"Order {ord_k}: q^{ord_k} K^{ord_k} g")
        ax.set_xlim(0, 64); ax.set_ylim(0, 64); ax.invert_yaxis()
        plt.colorbar(sc, ax=ax)
    plt.suptitle("Path-Order Neumann Expansion Accumulation (Ep 1)", fontsize=14)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "path_order_expansion.png"), dpi=150)
    plt.close()

    # 3. Field maps (Complex magnitude vs Magnitude-only for Map C / Ep 4)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    sc0 = axes[0].scatter(nodes_ep4[:, 0], nodes_ep4[:, 1], c=np.abs(psi_c_ep4), cmap='hot', s=25)
    axes[0].set_title(f"Complex Field |psi| (Ep 4: Temporary Retreat)\nContraction Fixed Point")
    axes[0].set_xlim(0, 64); axes[0].set_ylim(0, 64); axes[0].invert_yaxis()
    plt.colorbar(sc0, ax=axes[0])
    
    sc1 = axes[1].scatter(nodes_ep4[:, 0], nodes_ep4[:, 1], c=np.real(psi_m_ep4), cmap='hot', s=25)
    axes[1].set_title(f"Magnitude Field psi_mag (Ep 4: Temporary Retreat)\nContraction Fixed Point")
    axes[1].set_xlim(0, 64); axes[1].set_ylim(0, 64); axes[1].invert_yaxis()
    plt.colorbar(sc1, ax=axes[1])
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "field_maps.png"), dpi=150)
    plt.close()

    # 4. Trajectory comparison (Map C: Ep 4)
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    rec_c4 = records_complex[3]
    rec_m4 = records_mag[3]
    
    axes[0].set_title(f"Complex Fixed-Field Trajectory (Ep 4)\nSucc={int(rec_c4['success'])}, Steps={rec_c4['steps']}, Dist={rec_c4['final_dist']:.1f}px")
    axes[0].set_xlim(0, 64); axes[0].set_ylim(0, 64); axes[0].invert_yaxis(); axes[0].grid(True, alpha=0.3)
    axes[0].plot(rec_c4["traj"][:, 0], rec_c4["traj"][:, 1], '-o', color='purple', markersize=4, label="Complex Path")
    axes[0].plot(rec_c4["traj"][0, 0], rec_c4["traj"][0, 1], 'go', markersize=8, label="Start")
    axes[0].plot(goal_ep4[0], goal_ep4[1], 'r*', markersize=12, label="Goal")
    axes[0].legend()
    
    axes[1].set_title(f"Magnitude Fixed-Field Trajectory (Ep 4)\nSucc={int(rec_m4['success'])}, Steps={rec_m4['steps']}, Dist={rec_m4['final_dist']:.1f}px")
    axes[1].set_xlim(0, 64); axes[1].set_ylim(0, 64); axes[1].invert_yaxis(); axes[1].grid(True, alpha=0.3)
    axes[1].plot(rec_m4["traj"][:, 0], rec_m4["traj"][:, 1], '-o', color='teal', markersize=4, label="Magnitude Path")
    axes[1].plot(rec_m4["traj"][0, 0], rec_m4["traj"][0, 1], 'go', markersize=8, label="Start")
    axes[1].plot(goal_ep4[0], goal_ep4[1], 'r*', markersize=12, label="Goal")
    axes[1].legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "trajectory_comparison.png"), dpi=150)
    plt.close()
    
    print("Saved all figures and metrics.json.")

if __name__ == "__main__":
    main()
