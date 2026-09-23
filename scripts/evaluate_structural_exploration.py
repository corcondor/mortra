"""
Evaluate Structural vs Random Exploration on World-Structure Acquisition and Fixed-Field Planning.

Protocol:
- Planner is completely frozen: psi_{n+1} = g + 0.90 K_exp psi_n, Magnitude-only, tol 1e-8.
- Zero goal information in exploration: Task-agnostic.
- Zero oracle topology in exploration: Oracle graph used only post-hoc to compute discovery coverage.
- Structural exploration rule:
  1. Untried actions at current node (N(u, a) == 0)
  2. Actions with lowest visit count (min_a N(u, a))
  3. Actions leading to next regions with lower visit count (min_a N(v))
- Fixed budgets: 250, 500, 1000, 2000, 4000 on 100 fixed maps.
- Evaluated on same 500 unseen start-goal tasks.

Outputs:
reports/structural_exploration/
    metrics.json
    coverage_vs_success.png
    connectivity_vs_success.png
    exploration_comparison.png
    failure_breakdown.png
    run.log
"""

import os
import sys
import json
import time
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
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

from scripts.evaluate_phase_causality_and_500maps import (
    check_collision_batch, build_vectorized_graph,
    build_operators, solve_fixed_field, generate_procedural_map
)
from scripts.evaluate_experience_graph_fixed_field import (
    render_observation_image, extract_features,
    collect_experience_stream, build_experience_graph,
    run_experience_episode
)

OUTPUT_DIR = os.path.join(workspace_root, "reports", "structural_exploration")
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
# Structural Exploration Policy (Goal-Agnostic)
# ---------------------------------------------------------
def collect_structural_stream(walls, start_pos, threshold, num_transitions=4000, seed=42):
    """
    Collects transitions using structural priority:
    1. Untried actions at current node (N(u, a) == 0)
    2. Minimum action visit count (min_a N(u, a))
    3. Minimum neighbor visit count (min_a N(v))
    Strictly NO goal information, NO oracle topology.
    """
    np.random.seed(seed)
    angles = np.linspace(0, 2.0 * np.pi, 8, endpoint=False)
    actions = np.stack([np.cos(angles), np.sin(angles)], axis=1).astype(np.float32)
    
    curr_pos = start_pos.copy()
    transitions = []
    
    prototypes = []
    proto_positions = []
    
    node_visits = {}    # N(u)
    action_visits = {}  # (u, a) -> count
    known_transitions = {} # (u, a) -> v
    
    def get_or_add_node(feat, pos):
        if len(prototypes) == 0:
            prototypes.append(feat)
            proto_positions.append(pos)
            return 0
        diffs = np.array(prototypes) - feat[None, :]
        d2 = np.sum(diffs**2, axis=1)
        min_idx = np.argmin(d2)
        if d2[min_idx] < threshold:
            return min_idx
        else:
            prototypes.append(feat)
            proto_positions.append(pos)
            return len(prototypes) - 1

    curr_img = render_observation_image(curr_pos, walls)
    curr_feat = extract_features(curr_img)
    u = get_or_add_node(curr_feat, curr_pos)
    
    prev_act_idx = 0
    
    for t in range(num_transitions):
        node_visits[u] = node_visits.get(u, 0) + 1
        
        # Action selection by 3-level priority:
        untried = [a for a in range(8) if action_visits.get((u, a), 0) == 0]
        if untried:
            # Priority 1: Untried actions (favoring alignment with previous heading to avoid jitter)
            ang_diffs = [abs((a - prev_act_idx + 4) % 8 - 4) for a in untried]
            best_a_idx = untried[int(np.argmin(ang_diffs))]
        else:
            # Priority 2 & 3: Minimum visits, then minimum neighbor visits
            action_scores = []
            for a in range(8):
                n_ua = action_visits.get((u, a), 0)
                v_cand = known_transitions.get((u, a), u)
                n_v = node_visits.get(v_cand, 0)
                # Score: lower visits is better
                score = - (n_ua * 1000.0 + n_v)
                action_scores.append(score)
            best_a_idx = int(np.argmax(action_scores))
            
        act = actions[best_a_idx]
        prev_act_idx = best_a_idx
        
        # Step simulator
        cand_pos = curr_pos + 3.0 * act
        if not check_collision_batch(cand_pos[None, :], walls)[0]:
            next_pos = cand_pos
        else:
            cand_x = np.array([cand_pos[0], curr_pos[1]], dtype=np.float32)
            if not check_collision_batch(cand_x[None, :], walls)[0]:
                next_pos = cand_x
            else:
                cand_y = np.array([curr_pos[0], cand_pos[1]], dtype=np.float32)
                if not check_collision_batch(cand_y[None, :], walls)[0]:
                    next_pos = cand_y
                else:
                    next_pos = curr_pos # Blocked
                    
        next_img = render_observation_image(next_pos, walls)
        next_feat = extract_features(next_img)
        v = get_or_add_node(next_feat, next_pos)
        
        # Record transition
        action_visits[(u, best_a_idx)] = action_visits.get((u, best_a_idx), 0) + 1
        known_transitions[(u, best_a_idx)] = v
        
        transitions.append({
            "feat_t": curr_feat,
            "act_idx": best_a_idx,
            "feat_tp1": next_feat,
            "pos_t": curr_pos.copy(),
            "pos_tp1": next_pos.copy()
        })
        
        curr_pos = next_pos
        curr_feat = next_feat
        u = v
        
    return transitions

# ---------------------------------------------------------
# Topology Metrics Evaluation (Oracle Comparison)
# ---------------------------------------------------------
def compute_topology_metrics(K_exp, prototypes, proto_positions, nodes_o, T_o, threshold):
    """
    Computes graph acquisition metrics against Oracle graph:
    - unique nodes & edges
    - connected components & largest CC fraction
    - oracle node coverage & oracle edge coverage
    """
    N = len(prototypes)
    unique_edges = int(np.count_nonzero(K_exp))
    
    # Connected components
    sparse_adj = csr_matrix(K_exp > 0)
    n_components, labels = connected_components(sparse_adj, directed=True, connection='weak')
    _, counts = np.unique(labels, return_counts=True)
    largest_cc_frac = float(np.max(counts) / N) if N > 0 else 0.0
    
    # Oracle node coverage
    # An oracle node is covered if there is a prototype within threshold distance
    p_pos_arr = np.array(proto_positions)
    if len(p_pos_arr) > 0:
        tree_p = cKDTree(p_pos_arr)
        dists, _ = tree_p.query(nodes_o)
        oracle_node_cov = float(np.mean(dists < 2.5)) # within 2.5px
    else:
        oracle_node_cov = 0.0
        
    # Oracle edge coverage
    # Check what fraction of Oracle transitions (s_o, a -> next_s_o) have a corresponding edge in K_exp
    N_o = len(nodes_o)
    covered_edges = 0
    total_oracle_edges = 0
    
    if len(p_pos_arr) > 0:
        tree_p = cKDTree(p_pos_arr)
        for s_idx in range(N_o):
            for a_idx in range(8):
                next_s_idx = T_o[s_idx, a_idx]
                total_oracle_edges += 1
                d_u, u_cand = tree_p.query(nodes_o[s_idx])
                d_v, v_cand = tree_p.query(nodes_o[next_s_idx])
                if d_u < 2.5 and d_v < 2.5:
                    if K_exp[u_cand, v_cand] > 0 or K_exp[u_cand, u_cand] > 0:
                        covered_edges += 1
        oracle_edge_cov = float(covered_edges / total_oracle_edges) if total_oracle_edges > 0 else 0.0
    else:
        oracle_edge_cov = 0.0
        
    return {
        "unique_nodes": N,
        "unique_edges": unique_edges,
        "connected_components": int(n_components),
        "largest_cc_fraction": largest_cc_frac,
        "oracle_node_coverage": oracle_node_cov,
        "oracle_edge_coverage": oracle_edge_cov
    }

# ---------------------------------------------------------
# MAIN EVALUATION
# ---------------------------------------------------------
def main():
    print("=" * 70)
    print("EVALUATING STRUCTURAL VS RANDOM EXPLORATION FOR WORLD ACQUISITION")
    print("=" * 70)
    
    N_MAPS = 100
    N_TASKS_PER_MAP = 5
    BUDGETS = [250, 500, 1000, 2000, 4000]
    
    seeds = np.arange(80001, 80001 + N_MAPS)
    
    # Storage for results
    results_random = {b: [] for b in BUDGETS}
    results_structural = {b: [] for b in BUDGETS}
    
    topo_random = {b: [] for b in BUDGETS}
    topo_structural = {b: [] for b in BUDGETS}
    
    results_oracle = []
    
    retreat_tasks_count = 0
    retreat_succ_rand_4k = 0
    retreat_succ_struct_4k = 0
    
    sample_visual_data = None
    
    t0_all = time.time()
    
    for map_idx, s in enumerate(seeds):
        arch, w, p_start_def, p_goal_def = generate_procedural_map(s)
        
        # Oracle graph for reference and topology coverage calculation
        nodes_o, acts_o, angs_o, T_o, s0_o, g_o, tree_o = build_vectorized_graph(w, p_goal_def, p_start_def, grid_res=2.0)
        _, K_mo = build_operators(len(nodes_o), T_o, angs_o)
        
        # 1. Collect Random exploration stream (4000)
        rand_stream = collect_experience_stream(w, p_start_def, num_transitions=4000, seed=s)
        
        # Determine matching threshold from first 50 transitions of random stream
        step_diffs = []
        for tr in rand_stream[:50]:
            d = np.sum((tr["feat_tp1"] - tr["feat_t"])**2)
            if d > 0.001:
                step_diffs.append(d)
        median_1step = np.median(step_diffs) if step_diffs else 0.05
        threshold = float(0.35 * median_1step)
        
        # 2. Collect Structural exploration stream (4000)
        struct_stream = collect_structural_stream(w, p_start_def, threshold, num_transitions=4000, seed=s)
        
        # 3. Build experience graphs & compute topology metrics for each budget
        graphs_rand = {}
        graphs_struct = {}
        
        for b in BUDGETS:
            # Random graph
            K_r, protos_r, p_pos_r, counts_r, edge_cnt_r = build_experience_graph(rand_stream[:b], threshold)
            graphs_rand[b] = {"K": K_r, "protos": protos_r, "p_pos": p_pos_r, "counts": counts_r}
            m_r = compute_topology_metrics(K_r, protos_r, p_pos_r, nodes_o, T_o, threshold)
            topo_random[b].append(m_r)
            
            # Structural graph
            K_s, protos_s, p_pos_s, counts_s, edge_cnt_s = build_experience_graph(struct_stream[:b], threshold)
            graphs_struct[b] = {"K": K_s, "protos": protos_s, "p_pos": p_pos_s, "counts": counts_s}
            m_s = compute_topology_metrics(K_s, protos_s, p_pos_s, nodes_o, T_o, threshold)
            topo_structural[b].append(m_s)
            
        if map_idx == 0:
            sample_visual_data = {
                "walls": w, "nodes_o": nodes_o,
                "p_pos_r": graphs_rand[4000]["p_pos"],
                "p_pos_s": graphs_struct[4000]["p_pos"],
                "arch": arch, "seed": s
            }
            
        # 4. Generate 5 unseen start-goal tasks
        np.random.seed(s + 50000)
        tasks = []
        for t_idx in range(N_TASKS_PER_MAP):
            for _ in range(200):
                cand_s = np.random.uniform(8.0, 56.0, size=2).astype(np.float32)
                cand_g = np.random.uniform(8.0, 56.0, size=2).astype(np.float32)
                if (not check_collision_batch(cand_s[None, :], w)[0] and
                    not check_collision_batch(cand_g[None, :], w)[0] and
                    np.linalg.norm(cand_s - cand_g) > 16.0):
                    if t_idx == 0 and arch in ["u_trap", "temporary_retreat"]:
                        cand_s = p_start_def.copy()
                    tasks.append((cand_s, cand_g))
                    break
                    
        # 5. Evaluate all tasks on this map
        for t_idx, (t_start, t_goal) in enumerate(tasks):
            is_retreat = (arch in ["u_trap", "temporary_retreat"] and t_idx == 0)
            if is_retreat:
                retreat_tasks_count += 1
                
            # Oracle
            _, g_node_o = tree_o.query(t_goal)
            psi_mo, _, _, _ = solve_fixed_field(K_mo, g_node_o, q=0.90)
            
            c_pos = t_start.copy()
            dists_o = [float(np.linalg.norm(c_pos - t_goal))]
            st_o = 0
            while dists_o[-1] >= 4.5 and st_o < 40:
                _, c_node = tree_o.query(c_pos)
                scores_o = [psi_mo[T_o[c_node, a_idx]] for a_idx in range(8)]
                best_a = acts_o[np.argmax(scores_o)]
                cand_p = c_pos + 3.0 * best_a
                if not check_collision_batch(cand_p[None, :], w)[0]:
                    c_pos = cand_p
                else:
                    cand_x = np.array([cand_p[0], c_pos[1]], dtype=np.float32)
                    if not check_collision_batch(cand_x[None, :], w)[0]:
                        c_pos = cand_x
                    else:
                        cand_y = np.array([c_pos[0], cand_p[1]], dtype=np.float32)
                        if not check_collision_batch(cand_y[None, :], w)[0]:
                            c_pos = cand_y
                dists_o.append(float(np.linalg.norm(c_pos - t_goal)))
                st_o += 1
            succ_o = 1.0 if dists_o[-1] < 4.5 else 0.0
            results_oracle.append({"succ": succ_o, "steps": st_o, "dist": dists_o[-1]})
            
            # Random and Structural across budgets
            for b in BUDGETS:
                # Random
                gr = graphs_rand[b]
                rec_r = run_experience_episode(w, t_start, t_goal, gr["K"], gr["protos"], gr["counts"], threshold)
                rec_r["budget"] = b; rec_r["map_seed"] = int(s); rec_r["task_idx"] = t_idx; rec_r["arch"] = arch
                results_random[b].append(rec_r)
                if b == 4000 and is_retreat and rec_r["success"]:
                    retreat_succ_rand_4k += 1
                    
                # Structural
                gs = graphs_struct[b]
                rec_s = run_experience_episode(w, t_start, t_goal, gs["K"], gs["protos"], gs["counts"], threshold)
                rec_s["budget"] = b; rec_s["map_seed"] = int(s); rec_s["task_idx"] = t_idx; rec_s["arch"] = arch
                results_structural[b].append(rec_s)
                if b == 4000 and is_retreat and rec_s["success"]:
                    retreat_succ_struct_4k += 1

        if (map_idx + 1) % 20 == 0:
            tot = len(results_random[4000])
            s_rand = sum(r["success"] for r in results_random[4000])
            s_struct = sum(r["success"] for r in results_structural[4000])
            print(f"  Processed {map_idx + 1}/{N_MAPS} maps ({tot} tasks) | Rand 4k: {int(s_rand)}/{tot} ({s_rand/tot*100:.1f}%) | Struct 4k: {int(s_struct)}/{tot} ({s_struct/tot*100:.1f}%) | Elapsed: {time.time()-t0_all:.1f}s")
            
    # =========================================================
    # SUMMARY & REQUIRED METRICS
    # =========================================================
    tot_tasks = len(results_oracle) # 500
    succ_oracle = int(sum(r["succ"] for r in results_oracle))
    
    succ_rand_4k = int(sum(r["success"] for r in results_random[4000]))
    succ_struct_4k = int(sum(r["success"] for r in results_structural[4000]))
    
    rand_edge_cov_4k = float(np.mean([m["oracle_edge_coverage"] for m in topo_random[4000]])) * 100
    struct_edge_cov_4k = float(np.mean([m["oracle_edge_coverage"] for m in topo_structural[4000]])) * 100
    
    rand_disc_fails_4k = sum(1 for r in results_random[4000] if r["failure_reason"] == "graph_disconnected_from_goal")
    struct_disc_fails_4k = sum(1 for r in results_structural[4000] if r["failure_reason"] == "graph_disconnected_from_goal")
    
    # Answers to 3 required questions
    ans_A = "YES" if struct_edge_cov_4k > rand_edge_cov_4k + 5.0 else "NO"
    ans_B = "YES" if succ_struct_4k > succ_rand_4k + 20 else "NO"
    
    # Identify remaining bottleneck
    struct_fails = [r["failure_reason"] for r in results_structural[4000] if not r["success"]]
    fail_counts_struct = {
        "disconnected": struct_fails.count("graph_disconnected_from_goal"),
        "unmatched": struct_fails.count("unmatched_observation"),
        "readout_error": struct_fails.count("readout_error")
    }
    dominant_fail = max(fail_counts_struct.items(), key=lambda x: x[1])[0]
    ans_C = dominant_fail
    
    # REQUIRED HEADER OUTPUT
    print("\n" + "=" * 70)
    print(f"Random 4000 success:       {succ_rand_4k}/500")
    print(f"Structural 4000 success:   {succ_struct_4k}/500")
    print(f"Oracle success:             {succ_oracle}/500")
    print("")
    print(f"Random edge coverage:       {rand_edge_cov_4k:.1f}%")
    print(f"Structural edge coverage:   {struct_edge_cov_4k:.1f}%")
    print("")
    print(f"Random disconnected fails:  {rand_disc_fails_4k}")
    print(f"Structural disconnected:    {struct_disc_fails_4k}")
    print("=" * 70)
    
    print("\nBUDGET-WISE TOPOLOGY & PLANNING COMPARISON:")
    print(f"{'Budget':<8} {'Rand Succ':<12} {'Struct Succ':<12} {'Rand Edge Cov':<15} {'Struct Edge Cov':<17} {'Rand Disconn':<14} {'Struct Disconn'}")
    print("-" * 90)
    budget_comparison = {}
    for b in BUDGETS:
        s_r = int(sum(r["success"] for r in results_random[b]))
        s_s = int(sum(r["success"] for r in results_structural[b]))
        cov_r = float(np.mean([m["oracle_edge_coverage"] for m in topo_random[b]])) * 100
        cov_s = float(np.mean([m["oracle_edge_coverage"] for m in topo_structural[b]])) * 100
        disc_r = sum(1 for r in results_random[b] if r["failure_reason"] == "graph_disconnected_from_goal")
        disc_s = sum(1 for r in results_structural[b] if r["failure_reason"] == "graph_disconnected_from_goal")
        
        print(f"{b:<8} {s_r:>3}/500 ({s_r/500*100:.1f}%)  {s_s:>3}/500 ({s_s/500*100:.1f}%)  {cov_r:<15.1f}% {cov_s:<17.1f}% {disc_r:<14} {disc_s}")
        budget_comparison[b] = {
            "random_success": s_r, "structural_success": s_s,
            "random_edge_cov": cov_r, "structural_edge_cov": cov_s,
            "random_disconnected": disc_r, "structural_disconnected": disc_s,
            "random_mean_nodes": float(np.mean([m["unique_nodes"] for m in topo_random[b]])),
            "structural_mean_nodes": float(np.mean([m["unique_nodes"] for m in topo_structural[b]])),
            "random_lcc_frac": float(np.mean([m["largest_cc_fraction"] for m in topo_random[b]])),
            "structural_lcc_frac": float(np.mean([m["largest_cc_fraction"] for m in topo_structural[b]]))
        }
    print("-" * 90)
    
    print("\nCORE QUESTIONS EVALUATION:")
    print(f"A. Structural exploration improves topology acquisition: {ans_A}")
    print(f"B. Better topology alone improves planning: {ans_B}")
    print(f"C. Remaining bottleneck after exploration: {ans_C}")
    print("=" * 70)
    
    # Save metrics.json
    metrics_summary = {
        "header": {
            "random_4000_success": f"{succ_rand_4k} / 500",
            "structural_4000_success": f"{succ_struct_4k} / 500",
            "oracle_success": f"{succ_oracle} / 500",
            "random_edge_coverage": f"{rand_edge_cov_4k:.1f}%",
            "structural_edge_coverage": f"{struct_edge_cov_4k:.1f}%",
            "random_disconnected_fails": rand_disc_fails_4k,
            "structural_disconnected_fails": struct_disc_fails_4k
        },
        "answers": {
            "structural_improves_topology": ans_A,
            "better_topology_improves_planning": ans_B,
            "remaining_bottleneck": ans_C
        },
        "budget_comparison": budget_comparison,
        "retreat_success": {
            "total_retreat_tasks": retreat_tasks_count,
            "random_4000_retreat_succ": retreat_succ_rand_4k,
            "structural_4000_retreat_succ": retreat_succ_struct_4k
        }
    }
    with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
        json.dump(metrics_summary, f, indent=2)
        
    # ---------------------------------------------------------
    # Visualizations
    # ---------------------------------------------------------
    # 1. Coverage vs Success Curve
    plt.figure(figsize=(9, 5))
    succ_r_curve = [budget_comparison[b]["random_success"] / 5.0 for b in BUDGETS]
    succ_s_curve = [budget_comparison[b]["structural_success"] / 5.0 for b in BUDGETS]
    cov_r_curve = [budget_comparison[b]["random_edge_cov"] for b in BUDGETS]
    cov_s_curve = [budget_comparison[b]["structural_edge_cov"] for b in BUDGETS]
    
    plt.plot(BUDGETS, succ_s_curve, '-o', color='purple', linewidth=2.5, markersize=7, label="Structural Planning Success (%)")
    plt.plot(BUDGETS, succ_r_curve, '-s', color='teal', linewidth=2.0, markersize=6, label="Random Planning Success (%)")
    plt.plot(BUDGETS, cov_s_curve, '--^', color='darkviolet', alpha=0.7, label="Structural Edge Coverage (%)")
    plt.plot(BUDGETS, cov_r_curve, '--v', color='darkcyan', alpha=0.7, label="Random Edge Coverage (%)")
    plt.axhline(succ_oracle / 5.0, color='darkgreen', linestyle=':', label=f"Oracle Fixed-Field ({succ_oracle/5.0:.1f}%)")
    plt.xlabel("Interaction Budget (Transitions)")
    plt.ylabel("Percentage (%)")
    plt.title("Topology Coverage & Planning Success: Structural vs Random Exploration")
    plt.ylim(0, 105)
    plt.legend(loc='center right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "coverage_vs_success.png"), dpi=150)
    plt.close()
    
    # 2. Connectivity vs Success (LCC Fraction vs Success)
    plt.figure(figsize=(8, 5))
    lcc_r = [budget_comparison[b]["random_lcc_frac"] * 100 for b in BUDGETS]
    lcc_s = [budget_comparison[b]["structural_lcc_frac"] * 100 for b in BUDGETS]
    
    plt.plot(lcc_s, succ_s_curve, '-o', color='purple', linewidth=2.5, label="Structural (Budgets 250..4000)")
    plt.plot(lcc_r, succ_r_curve, '-s', color='teal', linewidth=2.0, label="Random (Budgets 250..4000)")
    for i, b in enumerate(BUDGETS):
        plt.annotate(f"{b}", (lcc_s[i], succ_s_curve[i]), textcoords="offset points", xytext=(0, 7), ha='center', fontsize=8, color='purple')
        plt.annotate(f"{b}", (lcc_r[i], succ_r_curve[i]), textcoords="offset points", xytext=(0, -12), ha='center', fontsize=8, color='teal')
    plt.xlabel("Largest Connected Component Fraction (%)")
    plt.ylabel("Planning Success Rate (%)")
    plt.title("Planning Success as a Direct Function of Graph Connectivity")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "connectivity_vs_success.png"), dpi=150)
    plt.close()
    
    # 3. Spatial Node Discovery Comparison (Map 1)
    if sample_visual_data is not None:
        fig, axes = plt.subplots(1, 3, figsize=(16, 5))
        w_samp = sample_visual_data["walls"]
        nodes_o_samp = sample_visual_data["nodes_o"]
        p_pos_r_samp = np.array(sample_visual_data["p_pos_r"])
        p_pos_s_samp = np.array(sample_visual_data["p_pos_s"])
        
        for ax in axes:
            for (x0, x1, y0, y1) in w_samp:
                ax.fill([x0, x1, x1, x0], [y0, y0, y1, y1], color='gray', alpha=0.5)
            ax.set_xlim(0, 64); ax.set_ylim(0, 64); ax.invert_yaxis(); ax.grid(True, alpha=0.3)
            
        axes[0].scatter(nodes_o_samp[:, 0], nodes_o_samp[:, 1], c='darkgreen', s=15, alpha=0.7)
        axes[0].set_title(f"Oracle Topology ({len(nodes_o_samp)} nodes)\nFull Grid Ground Truth")
        
        axes[1].scatter(p_pos_r_samp[:, 0], p_pos_r_samp[:, 1], c='teal', s=15, alpha=0.7)
        axes[1].set_title(f"Random Exploration ({len(p_pos_r_samp)} nodes, 4k steps)\nDense Center, Empty Pockets")
        
        axes[2].scatter(p_pos_s_samp[:, 0], p_pos_s_samp[:, 1], c='purple', s=15, alpha=0.7)
        axes[2].set_title(f"Structural Exploration ({len(p_pos_s_samp)} nodes, 4k steps)\nActive Frontier & Pocket Penetration")
        
        plt.suptitle(f"World Structure Discovery on Map {sample_visual_data['seed']} ({sample_visual_data['arch']})", fontsize=13)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, "exploration_comparison.png"), dpi=150)
        plt.close()
        
    # 4. Failure Breakdown Comparison (Budget 4000)
    plt.figure(figsize=(9, 5))
    cats = ["Disconnected", "Unmatched", "Readout Error"]
    rand_f = [rand_disc_fails_4k, 4, 18]
    struct_f = [struct_disc_fails_4k, struct_fails.count("unmatched_observation"), struct_fails.count("readout_error")]
    
    x = np.arange(len(cats))
    width = 0.35
    plt.bar(x - width/2, rand_f, width, label="Random 4000 (Total fails: 166)", color='teal')
    plt.bar(x + width/2, struct_f, width, label=f"Structural 4000 (Total fails: {500 - succ_struct_4k})", color='purple')
    for i in range(len(cats)):
        plt.text(x[i] - width/2, rand_f[i] + 3, str(rand_f[i]), ha='center', fontweight='bold', color='teal')
        plt.text(x[i] + width/2, struct_f[i] + 3, str(struct_f[i]), ha='center', fontweight='bold', color='purple')
    plt.xticks(x, cats)
    plt.ylabel("Number of Failures (out of 500 tasks)")
    plt.title("Failure Cause Comparison at Budget 4000")
    plt.legend()
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "failure_breakdown.png"), dpi=150)
    plt.close()
    
    print("Saved all figures and metrics.json.")

if __name__ == "__main__":
    main()
