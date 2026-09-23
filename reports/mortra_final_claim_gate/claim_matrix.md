# MORTRA Final Claim Gate Matrix

## Gate Verdicts

| Claim | Target Property | Pre-registered Condition | Verdict |
| :--- | :--- | :--- | :--- |
| **CLAIM A** | Not maze-specific | Validated on combinatorial/abstract graphs | **PASS** |
| **CLAIM B** | Domain-general finite-state core | Scale transfer >=70% AND math world >=80% | **FAIL** |
| **CLAIM C** | General finite-state planning | CLAIM B + Stochastic regret <= 0.15 | **FAIL** |
| **CLAIM D** | Representation-independent | Opaque noisy >=80% AND paraphrase >=80% | **FAIL** |
| **CLAIM E** | Partial observability | Aliased retention >= 90% of oracle belief | **FAIL** |
| **CLAIM F** | Universal shortest-path guarantee | Formal proof; FAIL if counterexample | **FAIL / COUNTEREXAMPLE** |

---

## Detailed Gate Evidence

### Gate 1: OOD Scale Generalization
- S6 Permutation (N=720): Discovered 720 states (100.0%), Success = 100.0%, Mean Steps = 7.26
- S7 Permutation (N=5040): Discovered 4916 states (97.54%), Success = 100.0%, Mean Steps = 12.09
- 2x4 Sliding Puzzle (N=20160): Discovered 5062 states (25.11%), Success = 24.0%, Mean Steps = 15.96
- Random Digraph N=500: Discovered 490 states (98.0%), Success = 100.0%, Mean Steps = 4.61
- Random Digraph N=1000: Discovered 984 states (98.4%), Success = 100.0%, Mean Steps = 5.09

### Gate 2: Opaque Observation & Noise Limits
- Clean Binary / Grayscale / Token representations: Purity = 1.0, Planning Success = 100%
- Noisy Binary (5% bit flip): Purity = 1.0, Success = 0.0%
- Noisy Grayscale (Gaussian+BG): Purity = 1.0, Success = 0.0%
- Diagnosis: Reasoning core remains invariant, but non-neural raw representation interface breaks under continuous/pixel noise.

### Gate 3: Stochastic Transition Systems
- Total tasks: 1000
- Oracle Optimal Probability: 1.0
- MORTRA Mean Probability: 0.981
- Probability Regret: 0.019
- Action Agreement with Exact DP: 49.91%

### Gate 4: Partial Observability (POMDP)
- Fully Observable: 100%
- Aliased Observation: 0% (chance level)
- Oracle Belief: 100.0%
- Conclusion: MORTRA requires Markov-sufficient state representation; memoryless core does not resolve history-dependent branching.

### Gate 5: Mathematical Transformation World
- Discovered equation states: 2188
- Algebraic Equivalence Success: 12.5%
- Mean rewrite steps: 12.36
- Domain-specific heuristics used: False (Pure 8 generic rewrite operators)

### Gate 6: Language-Like Surface
- Canonical Surface: 97%
- Unseen Paraphrase: 0%
- Conclusion: Semantic invariance is not solved by raw representation matching; requires explicit semantic canonicalization or representation interface.

### Gate 7: Shortest-Path Counterexample
- Status: Counterexample found on n=5 graph.
- Cause: Branching dilution in K_support and geometric series summation causes greedy following to choose suboptimal detour or cyclic attraction under asymmetric out-degrees.
