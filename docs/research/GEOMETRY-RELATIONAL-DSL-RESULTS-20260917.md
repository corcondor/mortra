# Relational geometry DSL: binding preregistered result

Preregistration: `docs/research/GEOMETRY-RELATIONAL-DSL-20260917.md` at the frozen
commit `a62e93143520e90154e1e1d9992207f031d463c0`.

Binding run: https://github.com/corcondor/mortra/actions/runs/35242997436
(workflow_dispatch, the only run at the frozen commit; clean tree; loaded modules
unchanged before and after; tests 283+ passed in the same job).
Artifact: `semantic-geometry-a62e931...-35242997436` (82 KB).

## Timeline and seed

* 11:51:40 UTC: freezing commit pushed with drand round 6473927 in the configuration.
  At that time the latest published round was 6473829 and round 6473927 returned
  HTTP 425 (not yet published).
* 12:40:30 UTC: round 6473927 published.
* 15:52:01 UTC: binding dispatch. The delay of about three hours after publication
  was caused by a usage limit of the operator's session; the code and configuration
  had been frozen and pushed before the round existed, and the fresh cohort was not
  generated locally at any time.
* Seed 2867789487 from randomness `ab44cf20e3e59b99...` fetched from
  `https://api.drand.sh`. The second endpoint (`https://drand.cloudflare.com`)
  answered HTTP 403 from the runner; the runner accepts one agreeing record by
  design, and verified randomness = sha256(signature).
* No overlap with the exposed regression cohort or the development cohorts.

## Primary result (fresh cohort, 48 tasks, 112 applications per task)

| condition | solved (audited) | applications | exact checks | warm-cache seconds |
| --- | ---: | ---: | ---: | ---: |
| A existing order | 12 | 4,523 | 149,503 | 90.6 |
| B existing contract-guided order (baseline) | 17 | 3,886 | 130,553 | 88.9 |
| N0 direct contract production | 11 | 114 | 1,720 | 0.4 |
| N + certified MR-transfer | 17 | 341 | 169,513 | 22.3 |
| NL + enumerated producer index | 31 | 278 | 28,033 | 11.6 |
| NLF + fallback B (primary) | 31 | 1,970 | 92,802 | 99.1 |

* Discordant tasks: NLF-only 14, B-only 0; exact one-sided binomial p = 6.1e-5.
* False solutions: 0 in every condition (independent primitive replay and exact goal
  atoms with prerequisites).
* Regression cohort (16 exposed tasks): NLF 14, B 8, A 8; NLF lost no task that B
  solved.
* Preregistered criterion: complete, binding, sources unchanged, more solved,
  p < 0.05, zero false solutions, no regression losses: **met**.

## Robustness and ablations (reported, not part of the criterion)

* Budget unit: each of the 14 NLF-only tasks was re-run with B at 448 applications
  (four times the budget). B solved 1 of 14 (at 219 applications). The NLF solutions
  used 2 to 7 applications each and none came from the fallback.
* Ablations on the fresh cohort: N0 11, N 17 (+6 from the transfer metarule), NL 31
  (+14 from the task-independent producer index), NLF 31 (+0 from the fallback).
* Tasks NLF did not solve involve mostly `cyclic` and `eqangle` goals (circle loci
  through a constructed centre, angle conditions), which the certified transfer
  shapes and the depth-2 producer index do not cover.

## What this establishes and what it does not

* On freshly generated point-construction tasks drawn by a preregistered rule, the
  contract-directed synthesis over the relational DSL, with certified MR-transfer
  and the enumerated producer index, solved more tasks than the strongest existing
  primitive-only search at the same application budget, with fewer applications and
  fewer exact checks, and without a false solution.
* Solutions are instance-level constructions at exact rational coordinates, not
  universal theorems. Metarules, the producer enumeration grammar and the fallback
  are supplied search machinery. A charged application is not the same unit in B
  and N; the four-times-budget re-run bounds that effect for this cohort.
* The solve comparison does not exercise the edit and abstraction operations
  (R2, R3); those are covered by the structural tests only.
* The JGEX exact-proof route is unchanged; this result does not change its 17/24.
