# Persistent Learning: First Frozen Theory-Formation Audit

This experiment demonstrates bounded target-free concept/conjecture generation,
exact settling and persistent reuse with measured downstream effects. It does
not demonstrate the full long-term objective, new mathematics, general algorithm
synthesis, or continuously expanding mathematical capability.

## Authoritative Runs

Repository: corcondor/mortra. Branch: codex/theory-formation-20260913.

- Code freeze: `0e66e613f4d6ca783e5342575a94cfc6b15c7c8d`.
  [A/B run 34717633700](https://github.com/corcondor/mortra/actions/runs/34717633700),
  [artifact 10305900996](https://github.com/corcondor/mortra/actions/runs/34717633700/artifacts/10305900996).
- Held-out data commit: `f9f80e39ca92035bfc37490ad5a072289c9cd80f`.
  [A/B/C run 34718259018](https://github.com/corcondor/mortra/actions/runs/34718259018),
  [artifact 10305776221](https://github.com/corcondor/mortra/actions/runs/34718259018/artifacts/10305776221).

The second commit changes only a model configuration and its declaration. The
recorded code hashes in the two runs agree. A/B completed before the held-out
model was declared. No implementation was tuned on the held-out result.

Fresh Linux verification: Python 3.12.10, SymPy 1.14.0, NumPy 1.26.4,
python-flint 0.9.0, pytest 8.4.1. All dependency versions, commands, platform,
workflow SHA and target SHA are in environment.json and input.json files.

Both Actions runs passed the existing 351-test suite and normal q-directed,
stored reuse, collision-free refusal and reuse-only refusal checks. Both passed
the 22 new theory guard tests. The A/B/C experiment has 18 normal processes:
three domains, three conditions, and two persisted phases. Prior Windows
development logs are not used for these results.

## Measured Effects

Each learned run continued from cycle 240 to 480 without source modifications.
The baseline conditions either disable theorem reuse or reacquire representations.
Reported times below are engine time, not whole CI duration.

| Domain | Shared completed equality queries | Prover calls avoided on shared queries | Paired closure reproofs avoided | Learned time | No theorem reuse | No representation reuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A: differential ring | 101 | 6 | 0 | 5.294 s | 3.896 s | 5.319 s |
| B: fold orientations | 388 | 0 | 8 | 2.213 s | 7.186 s | 7.252 s |
| C: bounded counter | 366 | 0 | 6 | 6.067 s | 7.010 s | 7.356 s |

A pruned 144 later candidates and seven pending conjectures. Only six of those
conjectures were completed in both compared runs, hence six paired avoided
prover calls. Its whole engine was slower: learned-rule matching and auditing
have overhead. Do not report a general speedup.

B and C did not demonstrate more term/conjecture pruning. They avoided repeated
certified closure construction on matched recurrence requests. Reacquisition
alone cost 4.976 s for B and 1.260 s for C in the respective controls.
B acquired two 3-dimensional spaces from a 24-state ambient encoding. C acquired
two 5-dimensional spaces from a 5-state encoding: C has no dimension reduction.
Persisting an applicable certificate still avoided repeat acquisition.

The comparison tests matrices, readout, scope and outcomes, not just task names.
Original certificates and counterexamples were independently replayed after both
phases. The final learned-state replay checks were 429 for A, 443 for B and 436
for C, with no failures. This is regression evidence in the declared fragments,
not proof of all future retention.

## Concrete Acquired Objects

### A: certified reductions and proof dependencies

At cycle 8 the engine proved `u + 0 = u`
(`T-2eef120eb58487c9`). It compiled the universal identity into a typed
substitution rule. Later candidate generation read that rule. Further examples
include `(-u) + u = 0` at cycle 248 and double negation at cycle 283.
These are elementary known identities, not advanced discoveries.

The actual proof dependency chain includes:

- Cycle 105: `(v+u)+1 = (u+1)+v`, theorem `T-de658cdcbedec083`.
- Cycle 125: `u+(1+v) = (u+1)+v`, theorem `T-a2e48f19dd120ffd`,
  proved after rewriting with the preceding theorem.
- Cycle 137: `(1+v)+(u+1) = 1+((u+1)+v)`,
  theorem `T-01b9102f8aeeadfd`, with recorded dependencies including both.

Depth is three for this executed proof, not a lower bound on mathematical
difficulty: direct ring normalization can prove these identities without the
learned lemmas. The later half also records 70 candidate rewrites using theorems
already present at the checkpoint. This is persistent use, not just retention.

One false conjecture equated `u+v` with `u+u`; the engine found the exact
assignment u=0, v=1. Finite probe agreement is not treated as proof.

### B: a concept, its representation, and a later procedure

The engine selected `C-b8f032907b167b70 = pull_A(F11)`: read frame coordinate
F11 after applying fold action A. It derived representation
`R-b8f032907b167b70` with three basis functions and readout [1,0,0].
Its stored A action matrix is:

```text
 0  1  0
-1  0  0
 0  0  1
```

This matrix was not a run input. Closure was checked for all four actions
on the complete finite orientation model. The acquired closure theorem then
served as the premise of `T-recurrence-4380b586bf287038`:

```text
a[n+2] = -a[n], a[0] = 0, a[1] = 1
```

The stored procedure computed a[11]=-1 and a[12]=0, with acquisition and proof
calls both zero for those uses. Independent model execution agreed. Its evaluator
was supplied in development; the concept, representation and recurrence
parameters were derived during execution. Collision and panel geometry are not
preserved by this representation.

### C: new model, unchanged code

The engine selected `pull_advance(position)`, acquired a five-dimensional
closure, and derived the recurrence with initial values [1,2,3,4] and
coefficients [0,0,0,1]. It evaluated positions at lengths 17 and 18 as 4 using
that saved procedure, then independently checked the model.

It also disproved `pull_retreat(position)=0` using model state 2, where the
left side is 1. The run kept one recurrence request unknown rather than
inventing a certificate. B similarly retained two unknown recurrence requests;
the existing kernel refuses the identically-zero sequence in these cases.

## Required A--I Findings

A. Target-free concepts: yes, semantically distinct definitions were generated
within the supplied signatures. Counts include simple negatives/compositions,
not only mathematically sophisticated concepts.

B. Self-generated conjectures: yes; equations and finite predicates were formed
from current concepts/probes, and closure/recurrence questions from selected
observables. No target theorem or q was accepted.

C. Exact proof/counterexample: yes within the universal differential identity
fragment or the complete declared finite model. Unknown is retained separately.

D. Earlier mathematics used later: yes; saved reductions changed candidates and
proof inputs, and acquired closure certificates supported later recurrence proofs.

E. Dependency depth at least two: yes (A:3, B:2, C:2), for the actual saved proof
graphs. This is not irreducible discovery depth.

F. Reduced work: yes for specific measured work, not universally for runtime.
The paired ablations identify avoided prover calls or repeated certified closure.

G. Held-out domain: yes for the same exploration machinery on one small
non-permutation model. The archives started empty per domain; learned knowledge
was not transferred from A/B to C.

H. No intervention: frozen source/configuration, isolated normal processes, no
interactive input channel, source hashes unchanged, all decisions recorded.
This is operational evidence, not a cryptographic proof against all interference.

I. Novelty: the displayed A identities are rediscoveries of standard ring laws.
The B recurrence is an elementary rotation-period consequence; C is an elementary
saturation consequence. Novelty of other exact finite-model formulations remains
unassessed. No new mathematical formula is claimed.

The post-run reference check used the primary
[Mathlib ring definitions](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Algebra/Ring/Defs.html):
its ring hierarchy and algebraic laws cover the elementary algebra displayed
above. This is a known-result classification, not a comprehensive literature
search or a Lean verification of MORTRA's outputs. The source of the B/C
interpretation is their saved matrices and recurrence certificates.

## Code Cost And Remaining Research

The initial development added 1,094 lines of Python runtime/verification code
and 196 lines of tests, plus configuration, CI and documentation. Zero Python,
test or workflow lines were added between code freeze and the held-out run;
zero source edits occurred between the first and resumed normal phases.
These separate numbers are more informative than dividing benefit by zero.

The full long-term objective is NOT complete. Important missing capabilities:

- Synthesizing a general executable procedure or search strategy, rather than
  specializing an existing interpreter with rules or recurrence coefficients.
- Procedures that construct further procedures.
- Improving a fixed externally held-out task set through acquired mathematics.
- Escaping the present bounded grammar/finite model, not just exploring it.
- Cross-domain transfer of learned knowledge and long-run diversity/retention.
- Proving formerly unsolved mathematics through indispensable new intermediate
  lemmas. The current kernels could directly settle the displayed identities.
- A cost-sensitive active vocabulary: A's learned-rule overhead currently
  outweighs its reduction in prover calls.

Continue from this measured limitation, not from theorem counts. A future
procedure-synthesis extension must be generic, separately frozen and evaluated
against fixed unseen tasks with primitive execution, acquisition, proof and
reuse costs separated. It must not relabel this experiment as general
algorithmic self-improvement.
