"""
MORTRA Agent v0.1: Multi-Step Planning with Obstacle Avoidance & Detours.
Features:
1. 2D Environment with walls/obstacles (Direct, Simple Detour, Temporary Retreat).
2. Repaired Complex Dynamics World Model trained end-to-end on obstacle physics.
3. Explicit Image Prediction Check (1-step prediction & 10-step open-loop rollout).
4. Multi-step MPC (horizon=18) vs 1-step Greedy Controller.
5. Evaluation on 5 fixed episodes across Map A, B, and C.
6. Detection of temporary retreat (goal distance increase then decrease to arrival).
"""

import os
import sys
import json
import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
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

OUTPUT_DIR = os.path.join(workspace_root, "reports", "agent_v01_obstacles")
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
# 1. Obstacle Environment with 3 Map Types
# ---------------------------------------------------------
class Obstacle2DWorldEnv:
    def __init__(self, grid_size=64, step_size=3.0):
        self.N = grid_size
        self.step_size = step_size
        y, x = np.ogrid[0:grid_size, 0:grid_size]
        self.x_grid = x.astype(np.float32)
        self.y_grid = y.astype(np.float32)
        
        self.ctrl_pos = np.zeros(2, dtype=np.float32)
        self.goal_pos = np.zeros(2, dtype=np.float32)
        self.walls = [] # List of [x0, x1, y0, y1] bounding boxes
        self.map_type = "direct"

    def reset(self, map_type=None, seed=None, is_eval=False):
        if seed is not None:
            np.random.seed(seed)
            
        if map_type is None:
            map_type = np.random.choice(["direct", "simple_detour", "temporary_retreat"])
        self.map_type = map_type
        self.walls = []
        
        if map_type == "direct":
            # Map A: Direct line of sight
            if is_eval:
                self.ctrl_pos = np.array([16.0, 16.0], dtype=np.float32)
                self.goal_pos = np.array([48.0, 48.0], dtype=np.float32)
            else:
                self.ctrl_pos = np.random.uniform(10.0, 54.0, size=2).astype(np.float32)
                self.goal_pos = np.random.uniform(10.0, 54.0, size=2).astype(np.float32)
            
        elif map_type == "simple_detour":
            # Map B: Vertical wall blocking middle
            # Wall at x in [29, 35], y in [16, 48]
            self.walls.append([29.0, 35.0, 16.0, 48.0])
            if is_eval:
                self.ctrl_pos = np.array([16.0, 32.0], dtype=np.float32)
                self.goal_pos = np.array([48.0, 32.0], dtype=np.float32)
            else:
                for _ in range(100):
                    cand = np.random.uniform(8.0, 56.0, size=2).astype(np.float32)
                    if not self.check_collision(cand):
                        self.ctrl_pos = cand
                        break
                for _ in range(100):
                    cand_g = np.random.uniform(8.0, 56.0, size=2).astype(np.float32)
                    if not self.check_collision(cand_g) and np.linalg.norm(cand_g - self.ctrl_pos) > 10.0:
                        self.goal_pos = cand_g
                        break
            
        elif map_type == "temporary_retreat":
            # Map C: U-shaped pocket blocking goal at right.
            # Must move LEFT to escape, increasing goal distance!
            # Top wall
            self.walls.append([18.0, 37.0, 21.0, 25.0])
            # Right wall (blocks goal)
            self.walls.append([33.0, 37.0, 21.0, 43.0])
            # Bottom wall
            self.walls.append([18.0, 37.0, 39.0, 43.0])
            
            if is_eval:
                self.ctrl_pos = np.array([27.0, 32.0], dtype=np.float32)
                self.goal_pos = np.array([50.0, 32.0], dtype=np.float32)
            else:
                # 50% inside pocket, 50% outside pocket
                if np.random.rand() < 0.5:
                    self.ctrl_pos = np.random.uniform([20.0, 27.0], [30.0, 37.0]).astype(np.float32)
                else:
                    for _ in range(100):
                        cand = np.random.uniform(8.0, 56.0, size=2).astype(np.float32)
                        if not self.check_collision(cand):
                            self.ctrl_pos = cand
                            break
                for _ in range(100):
                    cand_g = np.random.uniform(8.0, 56.0, size=2).astype(np.float32)
                    if not self.check_collision(cand_g) and np.linalg.norm(cand_g - self.ctrl_pos) > 10.0:
                        self.goal_pos = cand_g
                        break
            
        return self.render_observation(), self.render_goal_image()

    def check_collision(self, pos):
        """Checks if pos is inside any wall or out of bounds."""
        r = 2.5 # collision radius
        if pos[0] - r < 4.0 or pos[0] + r > 60.0 or pos[1] - r < 4.0 or pos[1] + r > 60.0:
            return True
        for (x0, x1, y0, y1) in self.walls:
            if (pos[0] + r >= x0 and pos[0] - r <= x1 and
                pos[1] + r >= y0 and pos[1] - r <= y1):
                return True
        return False

    def step(self, action: np.ndarray):
        act = np.clip(action, -1.0, 1.0)
        cand_pos = self.ctrl_pos + self.step_size * act
        
        # Collision handling: full step -> sliding step -> stop
        if not self.check_collision(cand_pos):
            self.ctrl_pos = cand_pos
        else:
            # Try sliding in X only
            cand_x = np.array([cand_pos[0], self.ctrl_pos[1]])
            if not self.check_collision(cand_x):
                self.ctrl_pos = cand_x
            else:
                # Try sliding in Y only
                cand_y = np.array([self.ctrl_pos[0], cand_pos[1]])
                if not self.check_collision(cand_y):
                    self.ctrl_pos = cand_y
                # Else stop (blocked)
                
        obs = self.render_observation()
        dist_to_goal = float(np.linalg.norm(self.ctrl_pos - self.goal_pos))
        done = dist_to_goal < 4.5
        return obs, dist_to_goal, done

    def _render_scene(self, ctrl_pos):
        canvas = np.zeros((self.N, self.N), dtype=np.float32)
        
        # Render static walls
        for (x0, x1, y0, y1) in self.walls:
            ix0, ix1 = int(round(x0)), int(round(x1))
            iy0, iy1 = int(round(y0)), int(round(y1))
            canvas[iy0:iy1, ix0:ix1] = 0.85
            
        # Render goal marker (ring)
        gd2 = (self.x_grid - self.goal_pos[0])**2 + (self.y_grid - self.goal_pos[1])**2
        ring = np.exp(-((np.sqrt(gd2 + 1e-6) - 4.5)**2) / (2.0 * 1.2**2)) * 0.75
        canvas = np.maximum(canvas, ring)
        
        # Render controllable Gaussian blob
        cd2 = (self.x_grid - ctrl_pos[0])**2 + (self.y_grid - ctrl_pos[1])**2
        blob = 1.0 * np.exp(-cd2 / (2.0 * 3.0**2))
        canvas = np.maximum(canvas, blob)
        
        return np.clip(canvas, 0.0, 1.0).astype(np.float32)

    def render_observation(self):
        return self._render_scene(self.ctrl_pos)

    def render_goal_image(self):
        return self._render_scene(self.goal_pos)

# ---------------------------------------------------------
# 2. Data Collection (20,000 transitions + 5,000 pairs)
# ---------------------------------------------------------
def collect_obstacle_dataset(num_transitions=20000, num_pairs=5000, seed=42):
    print(f"Collecting {num_transitions} transitions in obstacle environments...")
    np.random.seed(seed)
    env = Obstacle2DWorldEnv()
    
    obs_list, next_obs_list, act_list = [], [], []
    t = 0
    while t < num_transitions:
        m_type = np.random.choice(["direct", "simple_detour", "temporary_retreat"])
        obs, _ = env.reset(map_type=m_type)
        ep_len = np.random.randint(15, 40)
        for _ in range(ep_len):
            act = np.random.uniform(-1.0, 1.0, size=2).astype(np.float32)
            next_obs, _, _ = env.step(act)
            obs_list.append(obs[np.newaxis, ...])
            next_obs_list.append(next_obs[np.newaxis, ...])
            act_list.append(act)
            obs = next_obs
            t += 1
            if t >= num_transitions:
                break
                
    print(f"Collecting {num_pairs} paired transitions for Action-Difference Learning...")
    p_xt, p_a1, p_a2, p_xn1, p_xn2 = [], [], [], [], []
    for i in range(num_pairs):
        m_type = np.random.choice(["direct", "simple_detour", "temporary_retreat"])
        obs, _ = env.reset(map_type=m_type, seed=seed + 10000 + i)
        pos_backup = env.ctrl_pos.copy()
        
        a1 = np.random.uniform(-1.0, 1.0, size=2).astype(np.float32)
        next_obs1, _, _ = env.step(a1)
        
        env.ctrl_pos = pos_backup.copy()
        a2 = np.random.uniform(-1.0, 1.0, size=2).astype(np.float32)
        next_obs2, _, _ = env.step(a2)
        
        p_xt.append(obs[np.newaxis, ...])
        p_a1.append(a1)
        p_a2.append(a2)
        p_xn1.append(next_obs1[np.newaxis, ...])
        p_xn2.append(next_obs2[np.newaxis, ...])
        
    return (
        np.array(obs_list, dtype=np.float32),
        np.array(next_obs_list, dtype=np.float32),
        np.array(act_list, dtype=np.float32),
        np.array(p_xt, dtype=np.float32),
        np.array(p_a1, dtype=np.float32),
        np.array(p_a2, dtype=np.float32),
        np.array(p_xn1, dtype=np.float32),
        np.array(p_xn2, dtype=np.float32)
    )

# ---------------------------------------------------------
# 3. Model: Encoder + Repaired Complex Dynamics + Decoder
# ---------------------------------------------------------
class Encoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(16),
            nn.LeakyReLU(0.2),
            nn.Conv2d(16, 16, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(16),
            nn.LeakyReLU(0.2),
            nn.Conv2d(16, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.LeakyReLU(0.2),
        )
    def forward(self, x):
        return self.net(x)

class Decoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.ConvTranspose2d(16, 16, kernel_size=4, stride=2, padding=1),
            nn.BatchNorm2d(16),
            nn.LeakyReLU(0.2),
            nn.ConvTranspose2d(16, 16, kernel_size=4, stride=2, padding=1),
            nn.BatchNorm2d(16),
            nn.LeakyReLU(0.2),
            nn.Conv2d(16, 1, kernel_size=3, padding=1),
            nn.Sigmoid()
        )
    def forward(self, z):
        return self.net(z)

class RepairedComplexDynamics(nn.Module):
    def __init__(self):
        super().__init__()
        # Block 1
        self.act_proj1_r = nn.Sequential(nn.Linear(2, 16), nn.LeakyReLU(0.2), nn.Linear(16, 8))
        self.act_proj1_i = nn.Sequential(nn.Linear(2, 16), nn.LeakyReLU(0.2), nn.Linear(16, 8))
        self.conv1_r = nn.Conv2d(16, 16, kernel_size=3, padding=1)
        self.conv1_i = nn.Conv2d(16, 16, kernel_size=3, padding=1)
        self.bn1_r = nn.BatchNorm2d(16)
        self.bn1_i = nn.BatchNorm2d(16)
        self.bias_mod1 = nn.Parameter(torch.ones(16, 1, 1) * 0.5)
        
        # Block 2
        self.act_proj2_r = nn.Linear(2, 16)
        self.act_proj2_i = nn.Linear(2, 16)
        self.conv2_r = nn.Conv2d(32, 8, kernel_size=3, padding=1)
        self.conv2_i = nn.Conv2d(32, 8, kernel_size=3, padding=1)
        self.bn2_r = nn.BatchNorm2d(8)
        self.bn2_i = nn.BatchNorm2d(8)
        self.bias_mod2 = nn.Parameter(torch.ones(8, 1, 1) * 0.5)

    def forward_delta(self, z, a):
        z_r, z_i = z[:, :8], z[:, 8:]
        a1_r = self.act_proj1_r(a)[:, :, None, None].expand(-1, 8, 16, 16)
        a1_i = self.act_proj1_i(a)[:, :, None, None].expand(-1, 8, 16, 16)
        
        in1_r = torch.cat([z_r, a1_r], dim=1)
        in1_i = torch.cat([z_i, a1_i], dim=1)
        
        h1_r = self.bn1_r(self.conv1_r(in1_r) - self.conv1_i(in1_i))
        h1_i = self.bn1_i(self.conv1_r(in1_i) + self.conv1_i(in1_r))
        mag1 = torch.sqrt(h1_r**2 + h1_i**2 + 1e-6)
        scale1 = torch.relu(mag1 + self.bias_mod1) / (mag1 + 1e-6)
        act1_r, act1_i = h1_r * scale1, h1_i * scale1
        
        a2_r = self.act_proj2_r(a)[:, :, None, None].expand(-1, 16, 16, 16)
        a2_i = self.act_proj2_i(a)[:, :, None, None].expand(-1, 16, 16, 16)
        in2_r = torch.cat([act1_r, a2_r], dim=1)
        in2_i = torch.cat([act1_i, a2_i], dim=1)
        
        h2_r = self.bn2_r(self.conv2_r(in2_r) - self.conv2_i(in2_i))
        h2_i = self.bn2_i(self.conv2_r(in2_i) + self.conv2_i(in2_r))
        mag2 = torch.sqrt(h2_r**2 + h2_i**2 + 1e-6)
        scale2 = torch.relu(mag2 + self.bias_mod2) / (mag2 + 1e-6)
        dz_r, dz_i = h2_r * scale2, h2_i * scale2
        
        return torch.cat([dz_r, dz_i], dim=1)

    def forward(self, z, a):
        return z + self.forward_delta(z, a)

class WorldModelObstacles(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = Encoder()
        self.decoder = Decoder()
        self.dynamics = RepairedComplexDynamics()

    def forward(self, x_t, a_t):
        z_t = self.encoder(x_t)
        dz = self.dynamics.forward_delta(z_t, a_t)
        z_next = z_t + dz
        x_recon = self.decoder(z_t)
        x_next_pred = self.decoder(z_next)
        return z_t, dz, z_next, x_recon, x_next_pred

# ---------------------------------------------------------
# 4. Training
# ---------------------------------------------------------
def train_model(epochs=6, batch_size=64):
    X_t, X_next, A_t, P_xt, P_a1, P_a2, P_xn1, P_xn2 = collect_obstacle_dataset(num_transitions=20000, num_pairs=5000)
    
    base_loader = DataLoader(
        TensorDataset(torch.tensor(X_t), torch.tensor(X_next), torch.tensor(A_t)),
        batch_size=batch_size, shuffle=True
    )
    pair_loader = DataLoader(
        TensorDataset(torch.tensor(P_xt), torch.tensor(P_a1), torch.tensor(P_a2), torch.tensor(P_xn1), torch.tensor(P_xn2)),
        batch_size=batch_size, shuffle=True
    )
    
    model = WorldModelObstacles()
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    mse = nn.MSELoss()
    
    print(f"\nTraining World Model on Obstacle Physics ({epochs} Epochs, Batch Size {batch_size})...")
    t0 = time.time()
    
    for ep in range(1, epochs + 1):
        model.train()
        ep_tot, ep_next, ep_del, ep_diff = 0.0, 0.0, 0.0, 0.0
        pair_iter = iter(pair_loader)
        
        for xt, xnext, at in base_loader:
            optimizer.zero_grad()
            
            z_t, dz, z_next_pred, x_recon, x_next_pred = model(xt, at)
            with torch.no_grad():
                z_next_gt = model.encoder(xnext)
                delta_z_gt = z_next_gt - z_t
                
            l_recon = mse(x_recon, xt)
            l_next = mse(z_next_pred, z_next_gt) + mse(x_next_pred, xnext)
            l_delta = mse(dz, delta_z_gt)
            
            # Pair batch
            try:
                p_xt, p_a1, p_a2, p_xn1, p_xn2 = next(pair_iter)
            except StopIteration:
                pair_iter = iter(pair_loader)
                p_xt, p_a1, p_a2, p_xn1, p_xn2 = next(pair_iter)
                
            with torch.no_grad():
                p_zt = model.encoder(p_xt)
                diff_gt = model.encoder(p_xn1) - model.encoder(p_xn2)
            p1 = model.dynamics(p_zt, p_a1)
            p2 = model.dynamics(p_zt, p_a2)
            l_diff = mse(p1 - p2, diff_gt)
            
            loss = l_recon + l_next + 1.0 * l_delta + 1.0 * l_diff
            loss.backward()
            optimizer.step()
            
            ep_tot += loss.item()
            ep_next += l_next.item()
            ep_del += l_delta.item()
            ep_diff += l_diff.item()
            
        N_b = len(base_loader)
        print(f"Epoch {ep:2d}/{epochs} ({time.time()-t0:.1f}s) | "
              f"L_tot={ep_tot/N_b:.4f} (Next={ep_next/N_b:.4f}, Delta={ep_del/N_b:.4f}, Diff={ep_diff/N_b:.4f})")

    # Save checkpoint
    ckpt_path = os.path.join(OUTPUT_DIR, "checkpoint.pt")
    torch.save(model.state_dict(), ckpt_path)
    print(f"Checkpoint saved: {ckpt_path}")
    return model, X_t, X_next, A_t

# ---------------------------------------------------------
# 5. Explicit Image Prediction Check
# ---------------------------------------------------------
def run_image_prediction_check(model: WorldModelObstacles, X_t, X_next, A_t):
    print("\nRunning Explicit Image Prediction Check (100 transitions)...")
    model.eval()
    
    # 1. 100 transitions prediction MSE
    idx_100 = np.random.choice(len(X_t), 100, replace=False)
    sub_xt = torch.tensor(X_t[idx_100], dtype=torch.float32)
    sub_xnext = X_next[idx_100]
    sub_at = torch.tensor(A_t[idx_100], dtype=torch.float32)
    
    with torch.no_grad():
        _, _, _, _, pred_next = model(sub_xt, sub_at)
        pred_arr = pred_next.numpy()
        
    mse_100 = float(np.mean((pred_arr - sub_xnext)**2))
    print(f"Predicted Next-Image MSE (100 transitions): {mse_100:.6f}")
    
    # Visualization: 6 sample transitions
    fig, axes = plt.subplots(6, 5, figsize=(15, 18))
    for i in range(6):
        xt_i = sub_xt[i, 0].numpy()
        xn_gt = sub_xnext[i, 0]
        xn_pd = pred_arr[i, 0]
        err_i = np.abs(xn_pd - xn_gt)
        act_i = sub_at[i].numpy()
        
        axes[i, 0].imshow(xt_i, cmap='gray', vmin=0, vmax=1)
        axes[i, 0].set_title(f"X_t (Sample {i+1})")
        axes[i, 0].axis('off')
        
        axes[i, 1].imshow(xn_gt, cmap='gray', vmin=0, vmax=1)
        axes[i, 1].set_title("True X_{t+1}")
        axes[i, 1].axis('off')
        
        axes[i, 2].imshow(xn_pd, cmap='gray', vmin=0, vmax=1)
        axes[i, 2].set_title(f"Pred X_{{t+1}}\nAct: ({act_i[0]:.2f}, {act_i[1]:.2f})")
        axes[i, 2].axis('off')
        
        axes[i, 3].imshow(err_i, cmap='hot', vmin=0, vmax=0.5)
        axes[i, 3].set_title(f"Abs Error (MSE={np.mean(err_i**2):.4f})")
        axes[i, 3].axis('off')
        
        # Overlay
        overlay = np.zeros((64, 64, 3), dtype=np.float32)
        overlay[..., 0] = xn_gt # Red: Ground truth
        overlay[..., 1] = xn_pd # Green: Predicted
        axes[i, 4].imshow(overlay)
        axes[i, 4].set_title("Overlay (R:True, G:Pred)")
        axes[i, 4].axis('off')
        
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "next_image_predictions.png"), dpi=150)
    plt.close()
    print("Saved next_image_predictions.png.")
    
    # 2. Multi-step Open-Loop Rollout (t to t+10)
    print("Running 10-step open-loop rollout...")
    env = Obstacle2DWorldEnv()
    obs, _ = env.reset(map_type="simple_detour", seed=888)
    
    rollout_actions = [np.array([1.0, 0.0]) for _ in range(10)] # Move right towards wall
    true_images = [obs]
    for act in rollout_actions:
        next_o, _, _ = env.step(act)
        true_images.append(next_o)
        
    # Open-loop imagined rollout
    imagined_images = [obs]
    with torch.no_grad():
        z_curr = model.encoder(torch.tensor(obs[np.newaxis, np.newaxis, ...], dtype=torch.float32))
        for act in rollout_actions:
            a_t = torch.tensor(act[np.newaxis, ...], dtype=torch.float32)
            z_curr = model.dynamics(z_curr, a_t)
            x_dec = model.decoder(z_curr).squeeze().numpy()
            imagined_images.append(x_dec)
            
    fig, axes = plt.subplots(2, 11, figsize=(22, 5))
    for t_step in range(11):
        axes[0, t_step].imshow(true_images[t_step], cmap='gray', vmin=0, vmax=1)
        axes[0, t_step].set_title(f"True t={t_step}")
        axes[0, t_step].axis('off')
        
        axes[1, t_step].imshow(imagined_images[t_step], cmap='gray', vmin=0, vmax=1)
        axes[1, t_step].set_title(f"Imagined t={t_step}")
        axes[1, t_step].axis('off')
        
    plt.suptitle("10-Step Open-Loop Imagined Rollout vs True Physics (Hitting Wall)", fontsize=13)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "multistep_rollout.png"), dpi=150)
    plt.close()
    print("Saved multistep_rollout.png.")
    
    return mse_100

# ---------------------------------------------------------
# 6. Planners: Multi-step MPC vs 1-step Greedy
# ---------------------------------------------------------
class MultiStepMPCPlanner:
    def __init__(self, model: WorldModelObstacles, horizon=20, K=512, cem_iters=4):
        self.model = model
        self.horizon = horizon
        self.K = K
        self.cem_iters = cem_iters
        self.elites = max(2, int(K * 0.1))

    def _generate_candidate_actions(self, mean, std, it):
        # 1. AR(1) temporally smoothed Gaussian noise
        raw_eps = torch.randn(self.K, self.horizon, 2)
        eps = torch.zeros_like(raw_eps)
        cur = raw_eps[:, 0, :]
        for h in range(self.horizon):
            cur = 0.65 * cur + 0.35 * raw_eps[:, h, :]
            eps[:, h, :] = cur
        eps = eps / (eps.std(dim=(1, 2), keepdim=True) + 1e-6)
        actions = torch.clamp(mean.unsqueeze(0) + std.unsqueeze(0) * eps, -1.0, 1.0)
        
        # 2. In iteration 0, inject diverse motion primitives (cardinal, diagonals, turn sequences)
        if it == 0:
            dirs = [
                [-1.0, 0.0], [1.0, 0.0], [0.0, -1.0], [0.0, 1.0],
                [-0.7, -0.7], [-0.7, 0.7], [0.7, -0.7], [0.7, 0.7]
            ]
            idx = 0
            # Constant straight lines
            for d in dirs:
                actions[idx, :, 0] = d[0]
                actions[idx, :, 1] = d[1]
                idx += 1
            # 2-phase turns (e.g. retreat left then turn up/down, or detour around wall)
            for d1 in dirs:
                for d2 in dirs:
                    if idx >= self.K // 4:
                        break
                    mid = self.horizon // 2
                    actions[idx, :mid, 0] = d1[0]
                    actions[idx, :mid, 1] = d1[1]
                    actions[idx, mid:, 0] = d2[0]
                    actions[idx, mid:, 1] = d2[1]
                    idx += 1
        return actions

    @torch.no_grad()
    def plan_action(self, obs, goal_img, rng_seed=None):
        if rng_seed is not None:
            torch.manual_seed(rng_seed)
            
        x_t = torch.tensor(obs[np.newaxis, np.newaxis, ...], dtype=torch.float32)
        x_g = torch.tensor(goal_img[np.newaxis, np.newaxis, ...], dtype=torch.float32)
        
        z_t = self.model.encoder(x_t)
        z_goal = self.model.encoder(x_g)
        
        mean = torch.zeros(self.horizon, 2)
        std = torch.ones(self.horizon, 2) * 0.6
        
        for it in range(self.cem_iters):
            actions = self._generate_candidate_actions(mean, std, it)
            
            z_curr = z_t.expand(self.K, -1, -1, -1)
            dists = []
            for h in range(self.horizon):
                z_curr = self.model.dynamics(z_curr, actions[:, h, :])
                diff_h = z_curr - z_goal.expand(self.K, -1, -1, -1)
                dists.append(torch.mean(diff_h**2, dim=[1, 2, 3]))
                
            dists = torch.stack(dists, dim=1) # (K, horizon)
            min_d, min_h = torch.min(dists, dim=1)
            scores = min_d + 0.01 * (min_h.float() / self.horizon)
            
            elite_idx = torch.topk(scores, self.elites, largest=False).indices
            elites = actions[elite_idx]
            mean = torch.mean(elites, dim=0)
            std = torch.clamp(torch.std(elites, dim=0), min=0.1)
            
        return mean[0].numpy()

class GreedyPlanner:
    """1-step greedy planner: chooses action minimizing 1-step predicted goal distance."""
    def __init__(self, model: WorldModelObstacles, K=512):
        self.model = model
        self.K = K

    @torch.no_grad()
    def plan_action(self, obs, goal_img, rng_seed=None):
        if rng_seed is not None:
            torch.manual_seed(rng_seed)
            
        x_t = torch.tensor(obs[np.newaxis, np.newaxis, ...], dtype=torch.float32)
        x_g = torch.tensor(goal_img[np.newaxis, np.newaxis, ...], dtype=torch.float32)
        
        z_t = self.model.encoder(x_t)
        z_goal = self.model.encoder(x_g)
        
        actions = torch.tensor(np.random.uniform(-1.0, 1.0, size=(self.K, 2)), dtype=torch.float32)
        z_curr = z_t.expand(self.K, -1, -1, -1)
        z_next = self.model.dynamics(z_curr, actions)
        
        diff = z_next - z_goal.expand(self.K, -1, -1, -1)
        scores = torch.mean(diff**2, dim=[1, 2, 3])
        best_idx = torch.argmin(scores).item()
        return actions[best_idx].numpy()

# ---------------------------------------------------------
# 7. Evaluation across 5 Fixed Episodes (Maps A, B, C)
# ---------------------------------------------------------
def run_evaluation_5_episodes(model: WorldModelObstacles):
    print("\n" + "=" * 70)
    print("CRITICAL EVALUATION: MULTI-STEP MPC VS GREEDY CONTROLLER (5 EPISODES)")
    print("=" * 70)
    
    test_episodes = [
        {"ep": 1, "map": "direct", "seed": 70001},
        {"ep": 2, "map": "simple_detour", "seed": 70002},
        {"ep": 3, "map": "simple_detour", "seed": 70003},
        {"ep": 4, "map": "temporary_retreat", "seed": 70004},
        {"ep": 5, "map": "temporary_retreat", "seed": 70005}
    ]
    
    env = Obstacle2DWorldEnv()
    mpc_planner = MultiStepMPCPlanner(model, horizon=20, K=512, cem_iters=4)
    greedy_planner = GreedyPlanner(model, K=512)
    
    eval_records = {"mpc": [], "greedy": []}
    
    for cfg in test_episodes:
        ep_num = cfg["ep"]
        m_type = cfg["map"]
        s = cfg["seed"]
        
        print(f"\n--- Episode {ep_num}/5 | Map: {m_type} (Seed {s}) ---")
        
        # 1. Run Greedy
        obs, goal_img = env.reset(map_type=m_type, seed=s, is_eval=True)
        p_start = env.ctrl_pos.copy()
        p_goal = env.goal_pos.copy()
        dist_start = float(np.linalg.norm(p_start - p_goal))
        
        gr_traj = [p_start.copy()]
        gr_dists = [dist_start]
        done = False
        step = 0
        while not done and step < 40:
            act = greedy_planner.plan_action(obs, goal_img, rng_seed=s*100 + step)
            obs, dist, done = env.step(act)
            gr_traj.append(env.ctrl_pos.copy())
            gr_dists.append(dist)
            step += 1
            
        gr_succ = 1.0 if gr_dists[-1] < 4.5 else 0.0
        eval_records["greedy"].append({
            "ep": ep_num, "map": m_type, "success": gr_succ,
            "start_dist": dist_start, "final_dist": gr_dists[-1], "steps": step,
            "traj": np.array(gr_traj), "dists": gr_dists, "walls": env.walls,
            "p_start": p_start, "p_goal": p_goal
        })
        print(f"  Greedy: Success={int(gr_succ)}, FinalDist={gr_dists[-1]:.2f}px, Steps={step}")
        
        # 2. Run MPC
        obs, goal_img = env.reset(map_type=m_type, seed=s, is_eval=True)
        mpc_traj = [p_start.copy()]
        mpc_dists = [dist_start]
        done = False
        step = 0
        while not done and step < 40:
            act = mpc_planner.plan_action(obs, goal_img, rng_seed=s*100 + step)
            obs, dist, done = env.step(act)
            mpc_traj.append(env.ctrl_pos.copy())
            mpc_dists.append(dist)
            step += 1
            
        mpc_succ = 1.0 if mpc_dists[-1] < 4.5 else 0.0
        
        # Detect temporary retreat: goal distance increased then decreased to arrival
        max_d = max(mpc_dists)
        retreat_detected = (max_d > dist_start + 2.0) and (mpc_dists[-1] < 5.0)
        
        eval_records["mpc"].append({
            "ep": ep_num, "map": m_type, "success": mpc_succ,
            "start_dist": dist_start, "final_dist": mpc_dists[-1], "steps": step,
            "traj": np.array(mpc_traj), "dists": mpc_dists, "walls": env.walls,
            "p_start": p_start, "p_goal": p_goal,
            "retreat_detected": retreat_detected,
            "min_dist": min(mpc_dists), "max_dist": max_d
        })
        print(f"  MPC   : Success={int(mpc_succ)}, FinalDist={mpc_dists[-1]:.2f}px, Steps={step}, RetreatDetected={retreat_detected}")

    # Summary
    mpc_succ_count = int(sum([r["success"] for r in eval_records["mpc"]]))
    gr_succ_count = int(sum([r["success"] for r in eval_records["greedy"]]))
    
    # Check Temporary Retreat map (Episodes 4 and 5)
    retreat_succ_mpc = any([r["success"] == 1.0 for r in eval_records["mpc"] if r["map"] == "temporary_retreat"])
    retreat_succ_gr = any([r["success"] == 1.0 for r in eval_records["greedy"] if r["map"] == "temporary_retreat"])
    
    summary = {
        "mpc_success_count": mpc_succ_count,
        "mpc_success_rate": mpc_succ_count / 5.0,
        "greedy_success_count": gr_succ_count,
        "greedy_success_rate": gr_succ_count / 5.0,
        "temporary_retreat_mpc_success": retreat_succ_mpc,
        "temporary_retreat_greedy_success": retreat_succ_gr,
        "episodes_mpc": [{k: v for k, v in r.items() if k not in ["traj", "walls", "p_start", "p_goal"]} for r in eval_records["mpc"]],
        "episodes_greedy": [{k: v for k, v in r.items() if k not in ["traj", "walls", "p_start", "p_goal"]} for r in eval_records["greedy"]]
    }
    
    with open(os.path.join(OUTPUT_DIR, "metrics.json"), 'w') as f:
        json.dump(summary, f, indent=2)
    print("Saved metrics.json.")
    
    # Visualizations
    # 1. Trajectory Examples (MPC)
    fig, axes = plt.subplots(1, 5, figsize=(25, 5))
    for idx, r in enumerate(eval_records["mpc"]):
        ax = axes[idx]
        ax.set_title(f"Ep {idx+1}: {r['map']}\nMPC Succ={int(r['success'])}, Dist={r['final_dist']:.1f}px")
        ax.set_xlim(0, 64)
        ax.set_ylim(0, 64)
        ax.invert_yaxis()
        ax.grid(True, alpha=0.3)
        
        # Walls
        for (x0, x1, y0, y1) in r["walls"]:
            ax.fill([x0, x1, x1, x0], [y0, y0, y1, y1], color='black', alpha=0.8)
            
        # Trajectory
        tr = r["traj"]
        ax.plot(tr[:, 0], tr[:, 1], '-o', color='purple', markersize=3, label="MPC Path")
        ax.plot(r["p_start"][0], r["p_start"][1], 'go', markersize=8, label="Start")
        ax.plot(r["p_goal"][0], r["p_goal"][1], 'r*', markersize=12, label="Goal")
        ax.legend(loc='lower left', fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "trajectory_examples.png"), dpi=150)
    plt.close()
    
    # 2. Greedy vs MPC Comparison (especially for Map C / Ep 4)
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    ep_c = 3 # Ep 4 (index 3: temporary_retreat)
    r_gr = eval_records["greedy"][ep_c]
    r_mpc = eval_records["mpc"][ep_c]
    
    # Greedy plot
    axes[0].set_title(f"Greedy Controller (Ep 4: Temporary Retreat)\nSuccess={int(r_gr['success'])}, FinalDist={r_gr['final_dist']:.1f}px")
    axes[0].set_xlim(0, 64); axes[0].set_ylim(0, 64); axes[0].invert_yaxis(); axes[0].grid(True, alpha=0.3)
    for (x0, x1, y0, y1) in r_gr["walls"]:
        axes[0].fill([x0, x1, x1, x0], [y0, y0, y1, y1], color='black', alpha=0.8)
    axes[0].plot(r_gr["traj"][:, 0], r_gr["traj"][:, 1], '-o', color='red', markersize=4, label="Greedy (Stuck)")
    axes[0].plot(r_gr["p_start"][0], r_gr["p_start"][1], 'go', markersize=9, label="Start")
    axes[0].plot(r_gr["p_goal"][0], r_gr["p_goal"][1], 'r*', markersize=14, label="Goal")
    axes[0].legend()
    
    # MPC plot
    axes[1].set_title(f"Multi-Step MPC (Ep 4: Temporary Retreat)\nSuccess={int(r_mpc['success'])}, FinalDist={r_mpc['final_dist']:.1f}px")
    axes[1].set_xlim(0, 64); axes[1].set_ylim(0, 64); axes[1].invert_yaxis(); axes[1].grid(True, alpha=0.3)
    for (x0, x1, y0, y1) in r_mpc["walls"]:
        axes[1].fill([x0, x1, x1, x0], [y0, y0, y1, y1], color='black', alpha=0.8)
    axes[1].plot(r_mpc["traj"][:, 0], r_mpc["traj"][:, 1], '-o', color='purple', markersize=4, label="MPC (Detour)")
    axes[1].plot(r_mpc["p_start"][0], r_mpc["p_start"][1], 'go', markersize=9, label="Start")
    axes[1].plot(r_mpc["p_goal"][0], r_mpc["p_goal"][1], 'r*', markersize=14, label="Goal")
    axes[1].legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "greedy_vs_mpc.png"), dpi=150)
    plt.close()
    
    # 3. Goal Distance Over Time (Showing temporary retreat)
    plt.figure(figsize=(10, 5))
    for idx, r in enumerate(eval_records["mpc"]):
        lbl = f"Ep {idx+1} ({r['map']})"
        plt.plot(r["dists"], label=lbl, linewidth=2)
    plt.axhline(4.5, color='black', linestyle='--', label='Goal Arrival Threshold (4.5px)')
    plt.xlabel("Planning Step")
    plt.ylabel("Distance to Goal (px)")
    plt.title("Goal Distance Over Time (Multi-Step MPC)\nNotice Temporary Distance Increase in Ep 4 & 5 (Detour / Retreat)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "goal_distance_over_time.png"), dpi=150)
    plt.close()
    
    return summary

def main():
    t0 = time.time()
    # 1. Train model on obstacle physics
    model, X_t, X_next, A_t = train_model(epochs=6, batch_size=64)
    
    # 2. Image prediction check
    pred_mse = run_image_prediction_check(model, X_t, X_next, A_t)
    
    # 3. Critical evaluation: Multi-step MPC vs Greedy on 5 fixed episodes
    summary = run_evaluation_5_episodes(model)
    
    print("\n" + "=" * 70)
    print("FINAL SUMMARY REPORT")
    print("=" * 70)
    print(f"Multi-step MPC Success: {summary['mpc_success_count']}/5 ({summary['mpc_success_rate']*100:.0f}%)")
    print(f"Greedy Controller Success: {summary['greedy_success_count']}/5 ({summary['greedy_success_rate']*100:.0f}%)")
    print(f"Temporary Retreat Map Success (MPC): {summary['temporary_retreat_mpc_success']}")
    print(f"Predicted Next-Image MSE: {pred_mse:.6f}")
    print(f"Total time: {time.time()-t0:.1f}s")
    print("=" * 70)

if __name__ == "__main__":
    main()
