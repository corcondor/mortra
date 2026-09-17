# Discovering structures that change what a computation costs

Repository: `corcondor/mortra`. Branch: `codex/operation-contracts-20260918`.
Base: `10ddc72` (the shared operation contract).
Status: implementation and its execution record. No preregistered comparison.

## 1. What changed about the target

The earlier layer acquired operations: a composition that met a specification was
registered and used again. That makes a search shorter; it does not make a
computation cheaper, and an operation acquired for one goal is close to
remembering a route.

What is looked for here is different. The object to be discovered is a
**mathematical structure of the operations themselves**, certified exactly, that
turns a whole family of problems into a computation of a lower order:

| discovered structure | what it removes |
|---|---|
| which histories need not be told apart (a minimal linear representation) | the number of states that are searched separately |
| a polynomial relation `p(A) = 0` | the number of iterations: `L` becomes `log L` |
| a bilinear decomposition with fewer multiplications | the exponent of a recursion |

None of these is a route to an answer. Each is a statement about operations,
proved once, that every instance of the family then uses — including the
instances no discovery run has seen.

## 2. The identity that starts it

For operations `M_a`, a start `s` and a functional `g`, summing over every
sequence of length `L` is one operator power:

```
sum over a_1..a_L of  <g| M_{a_L} ... M_{a_1} |s>  =  <g| (sum_a M_a)^L |s>
```

Enumerating the sequences costs `b^L`. The right-hand side costs `L` applications
of one operator. That is the first order change, and it is the one MORTRA's own
search does not make when it re-derives the same partial result along thousands of
plans.

Two further structures are then discovered from the operator.

**Merging.** The reachable subspace keeps only what the start can produce; the
annihilator of the smallest functional-containing row space closed under the
transposes is invisible to every word. Restricting to the first and quotienting by
the second changes no word's value. What comes out is the smallest linear
representation, so its dimension `r` is a property of the question, not of how the
question was written down.

**Relation.** In that representation, the first `r` Krylov vectors either stay
independent or produce the smallest relation `A^r s = sum c_i A^i s`. Then

```
x^L mod p  =  q(x),  deg q < r     gives     y_L = sum_i q_i y_i
```

so a computation of length `L` becomes a remainder computation of `O(r^2 log L)`
coefficient operations plus `r` initial values. When `p(A) = 0` holds as a matrix
identity — checked exactly — the same relation serves every start vector.

## 3. What was run

`scripts/run_structure_scaling_eval.py` writes the record to `reports/structure-scaling/result.json`; like the other evaluations here it is a produced artifact and is not kept in the tree. The numbers below are from the run of 2026-09-18 on the commit that adds this document.

**Families whose description is more detailed than their answer.** Binary strings
with no `11`, described by remembering the last `w` symbols, so the given
description has `2^w` states:

| given states | merged | relation | discovery | L = 65,536: iterate | structure | same answer |
|---:|---:|---|---:|---:|---:|---|
| 16 | 2 | `x² = x + 1` | 292 ops | 917,478 ops | 97 ops | yes |
| 256 | 2 | `x² = x + 1` | 1,188 ops | 5,897,724 ops | 97 ops | yes |
| 1,024 | 2 | `x² = x + 1` | 2,746 ops | 15,333,612 ops | 97 ops | yes |

The relation was certified as a matrix identity, so it holds for every start. The
answer at `L = 65,536` has 13,697 digits and agrees with iteration; at every length
up to 4,096 it also agrees with an independent matrix power that keeps all `2^w`
states. Empirical exponents over the measured lengths: iteration `1.04` to `1.24`,
the discovered route `0.19`.

**MORTRA's own vocabulary.** States are the sorts of the shared operation
contract, letters are the given contracts of one argument. Given 3, merged 2,
relation of degree 2; at `L = 65,536`, 131,072 operations become 20.

**Families generated from seeds after the code was written.** Six random operation
systems of 12 states: merged dimensions 11, 0, 7, 12, 2, 7. One of them compresses
to nothing (12 stays 12) and that is what the run reports. Every compiled answer
agreed with iteration. This is the check that the procedure, and not a remembered
answer, is what runs.

**A bilinear decomposition found by search.** Starting from the obvious 8-term
decomposition of the 2×2 matrix product, a walk of flips over GF(2) — each flip an
identity, so every state of the walk is an exact decomposition — reached 7 terms
in 21,500 counted operations. The supports were then lifted to the rationals by
searching the signs and solving exactly for the output factors: the residual
against the tensor is empty, so the decomposition is exact over `QQ`.

A recursive multiplier built from the discovered terms — not from a supplied
algorithm — gives, on random exact matrices:

| n | multiplications | obvious | additions | obvious | same output |
|---:|---:|---:|---:|---:|---|
| 2 | 7 | 8 | 36 | 8 | yes |
| 4 | 49 | 64 | 396 | 64 | yes |
| 8 | 343 | 512 | 3,348 | 512 | yes |
| 16 | 2,401 | 4,096 | 25,740 | 4,096 | yes |
| 32 | 16,807 | 32,768 | 189,396 | 32,768 | yes |

The fitted exponent of the multiplication count is `2.807` against `3.000`: the
exponent, not a constant, is what changed. The 3×3 tensor was searched the same
way with a target of 23; the best reached was 24 over GF(2), and its lift to the
rationals was not found within the sign budget, so nothing is claimed for it
beyond GF(2).

## 4. What this does not say

* Operation counts ignore the size of the numbers. An answer with 13,697 digits
  costs more per operation than a short one, and the counts do not say so; wall
  times are recorded beside them.
* The discovered decomposition lowers the number of multiplications and raises the
  number of additions. In this implementation it is slower in wall time at the
  sizes measured; the exponent claim is about multiplications, which is the
  classical measure of bilinear complexity.
* The flip search certifies a decomposition over GF(2). A decomposition over the
  rationals is claimed only when the lift is found and its residual against the
  tensor is empty.
* Nothing is claimed about families whose merged dimension grows with the input.
  The measured families have a fixed small `r`; that is a property of those
  families, discovered and reported, not a general theorem.
* Discovering a structure costs something, and that cost is reported separately
  from using it, because a structure is discovered once and used at every length.
* No preregistered evaluation is affected. The frozen configurations, runners and
  results are untouched.

## 5. The discovered structure as an operation

A structure is only useful to the system if the system can hold it the way it
holds every other operation. `structure_contracts.py` registers a discovered
structure in the registry of `OPERATION-CONTRACTS-20260918.md`:

* type: `(Family, Length) -> Count`;
* object identity: the family is identified by its operations, start and
  functional, so the operation refuses a family it was not discovered on;
* guarantee: `counts_sequences(F, L, v)` — the answer is the one the expensive
  route would have given;
* proof: the two certificates of the discovery, recorded as the derivation. In a
  session that verifies derivations, the expensive route runs as well and has to
  agree;
* cost: charged to the same counter. On the family with 64 states, at `L = 8192`,
  the registered operation costs more than a hundred times less than the
  operation it was derived from, and returns the same integer;
* provenance: `acquired`, with `count_by_iterating` as its parent, so what was
  found stays distinguishable from what was given.

What is stored is therefore not a solved instance. It is an operation with a
proof, whose cost grows with the logarithm of the length, and which answers every
instance of its family, including the lengths no discovery run ever saw.
