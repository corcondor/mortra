# Algebraic structures: preregistered result

Design and preregistration: `docs/research/ALGEBRAIC-STRUCTURES-20260917.md`, section 5.
Freezing commit: `0732d38f56d7f5afbd605987ca31907c9ff5dfa5` (config committed at unix time
1789661714). Binding run: GitHub Actions run `35246474788`, the first workflow_dispatch of
`configs/algebraic-structures-20260917.json` at that SHA, created 2026-09-17T16:25:18Z,
18 seconds after drand round 6474376 was published (1789662300). Evidence artifact:
`semantic-geometry-0732d38f56d7f5afbd605987ca31907c9ff5dfa5-35246474788`.

Seeds (derived inside the run): fresh 2554164160, training 3224785382, from the
randomness of round 6474376 returned by `https://api.drand.sh`. The second endpoint,
`https://drand.cloudflare.com`, returned HTTP 403 and was recorded as an error; the seed
depends only on the round's signature, so one endpoint suffices.

Binding checks passed: GitHub Actions run, integer round published after the commit that
fixed it, loaded modules tracked and unchanged before and after, seeds distinct from the
development seeds and from each other, no fresh task identical to a training or
development task (overlap list empty). CI tests in the same job: 328 passed and 1 skipped
(including the 17 algebraic tests and the relational DSL suites), upstream Newclid 237
passed and 5 skipped, bridge regressions 10 passed; vendored bytes verified before and
after.

## Primary: Betti numbers with representatives, collapse against direct

48 fresh Vietoris-Rips complexes (93 to 2,231 cells; annulus 12, two circles 11, blob 10,
figure eight 8, circle 7). Every answer audited with python-flint (Betti numbers,
representative count, degree, cycle, independence modulo boundaries).

| | direct | collapse |
|---|---:|---:|
| solved and audited | 48 / 48 | 48 / 48 |
| incorrect claims | 0 | 0 |
| total counted operations | 418,896 | 386,915 |
| elimination | 385,892 | 350,119 |
| move records | 33,004 | 29,460 |
| collapse selection and reindexing | 0 | 7,336 |

* Ratio of totals collapse / direct: **0.924**; 95% bootstrap interval (10,000 task
  resamples seeded by the fresh seed): **[0.894, 0.946]**.
* Per task: collapse cheaper on 47, more expensive on 1 (task 29, two circles, 145 cells:
  549 against 534). Per-task ratio: minimum 0.563, median 0.919, maximum 1.028.

Preregistered criterion: binding true, sources unchanged true, no overlap true, zero
incorrect answers in every condition true, all tasks solved by both true, collapse total
lower true, bootstrap upper bound below 1 true. **Improvement: true.**

## Secondary (reported without a claim): minimal models

All seven conditions solved 48 of 48 with zero incorrect claims (zero remaining
differential, Betti numbers and representatives audited).

| condition | algebraic work | ratio to min-fill | total including queue |
|---|---:|---:|---:|
| min-fill (default) | 309,404 | 1.000 | 2,179,528 |
| acquired rule | 301,799 | 0.975 | 1,707,177 |
| bottom-first | 304,348 | 0.984 | 1,697,604 |
| few-cofaces | 313,318 | 1.013 | 2,463,198 |
| short-boundary | 319,480 | 1.033 | 2,341,052 |
| top-first | 328,337 | 1.061 | 2,513,069 |
| exploration | 773,129 | 2.499 | 3,233,910 |
| per-task oracle | | 0.954 | |

* Acquired rule (learned from 24 training complexes): size <= 576 cells -> top-first,
  otherwise bottom-first; chosen top-first 28 times and bottom-first 20 times. Ratio
  0.975, bootstrap interval [0.956, 0.998], 35 wins and 13 losses against min-fill. The
  rule's algebraic work was lower than every fixed ordering; it recovered about half of
  the oracle's 4.6% margin.
* Exploration paid for its race: 2.5 times min-fill.
* These are secondary observations. The preregistration made no claim for them, and the
  development runs had shown held-out rules at 0.991 and 1.014, so this single cohort is
  not evidence that ordering acquisition reliably helps.

## What this does and does not show

* Shown: on fresh complexes drawn after the code was frozen, composing certified
  free-face collapses (homotopy equivalences) with elimination computes Betti numbers
  and valid representatives with about 7.6% fewer counted operations than elimination
  alone, with no incorrect answer, at the declared cost model.
* Not shown: wall-time speedups; novelty of the mathematics (collapses and minimal models
  are classical); benefit on complexes outside the generator's range; semi-algebraic
  homology, multivariate syzygies or gluing of local charts, which are not implemented.
* The operations of this layer (kernels, presentation maps with `FA = BS`, chain maps,
  homotopy equivalences and their composition, persistence, dual-number Jacobians,
  Plucker coordinates) are exercised by the connection tests listed in the design
  document, section 3; the preregistered test measured only the reduction pipeline.

Machine-readable summary: `docs/research/ALGEBRAIC-STRUCTURES-RESULTS-20260917.json`.
