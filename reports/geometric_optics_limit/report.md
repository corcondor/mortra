# MORTRA Geometric Optics Limit Verification Report

## Executive Results

- **Counterexample switches to shortest path at high beta**: **YES**
- **Small-graph shortest-path agreement**:
  - $\beta = 0.1$: **81.36%**
  - $\beta = 1.0$: **100.0%**
  - $\beta = 4.0$: **100.0%**
  - $\beta = 16.0$: **100.0%**
- **Large-beta shortest-distance ordering**:
  - Spearman ($\beta=16.0$) = **0.8407**
- **Finite-beta path-multiplicity distinction**: **YES**

---

## Pre-Registered Generalization Claims

| Claim ID | Proposition | Result |
| :--- | :--- | :--- |
| **Claim A** | Current field is a weighted path-sum | **YES** |
| **Claim B** | Finite beta retains multi-path / connectivity information | **YES** |
| **Claim C** | Large beta approaches shortest-path geometry | **YES** |
| **Claim D** | Geometric optics can be interpreted as a limiting regime of the generalized MORTRA field | **YES** |

---

## Detailed Evidence and Mathematical Interpretation

1. **Removal of Degree Bias via Global Normalization**:
   By setting $K = A / \rho(A)$, local branching dilution ($1/\text{outdegree}$) is completely removed. All walk weights of length $L$ scale uniformly as $(e^{-\beta} / \rho(A))^L$.

2. **Transition on the Counterexample**:
   - At $\beta = 0.05 \sim 0.2$, the detour path $3 \to 1 \to 4 \to 2$ is competitive or preferred due to loop interactions.
   - At $\beta \ge 0.5$, $\psi[0]$ strictly overtakes $\psi[1]$. At $\beta=4.0$, $\psi[0] \gg \psi[1]$, causing greedy field following to choose the exact BFS shortest path $3 \to 0 \to 2$ (length 2).

3. **Exhaustive Small-Graph Verification ($n \le 5$)**:
   Agreement with BFS shortest path grows monotonically from **67.98%** at $\beta=0.05$ to **100.0%** at $\beta=16.0$.

4. **Multiplicity vs Metric Duality**:
   - At $\beta \le 0.5$, states with 5 parallel paths have $2.5\times \sim 4.5\times$ higher potential than single-path states of identical distance.
   - At $\beta \ge 8.0$, the effective temperature metric $T_\beta(s) = -(1/\beta) \log \psi(s)$ matches the true shortest distance $d(s, g)$ with Spearman correlation **0.8407**.
