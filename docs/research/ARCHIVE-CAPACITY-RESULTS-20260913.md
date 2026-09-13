# Archive Capacity: Fresh Actions Result

Increasing the concept archive from128 to256 did not improve the fixed held-out
score. This is an archive-capacity result, NOT a term-size sweep result.

- Repository: `corcondor/mortra`
- Mathematical SHA: `14d18a42c3a7c640a7c54c86c36b7238c419df56`
- Control SHA: `4c06d309105495debba6598210e6c42b8f215e69`
- [Actions run34725274254](https://github.com/corcondor/mortra/actions/runs/34725274254)
- [Fresh artifact10307968075](https://github.com/corcondor/mortra/actions/runs/34725274254/artifacts/10307968075)
- Local artifact: `C:/Users/81808/.openclaw/reports/capacity-study-20260913/actions-34725274254`
- Protocol: `docs/handoff/CONCEPT-CAPACITY-STUDY-20260913.md`

Both conditions started from K0 in the same Actions job, sequentially. Exact
domain, seed20260913, held-out seed739182, term-size9, active target32,
cycle cap12000, action-body600s limit, and representation cap4 were identical.
The mathematical implementation was unchanged. No candidates, auxiliary
observables or answers were added after launch. Full definitions, decisions,
certificates, downstream reductions, configs and commands are in the artifact.

| Measured quantity | Algebra128 | Algebra256 | Fold128 | Fold256 |
| --- | ---: | ---: | ---: | ---: |
| Final cycle | 3679 | 6229 | 12000 | 12000 |
| Stored concepts, including seeds | 128 | 256 | 128 | 256 |
| Theorems | 91 | 104 | 487 | 499 |
| Representation records | 0 | 0 | 4 | 4 |
| Distinct measured representation row spaces | 0 | 0 | 2 | 2 |
| Maximum recorded concept-parent depth | 2 | 2 | 1 | 1 |
| Maximum theorem-proof dependency depth | 3 | 3 | 2 | 2 |
| Held-out solved, of64 | 51 | 51 | 54 | 54 |
| Existing exact-prover calls during learning | 3311 | 5599 | 11338 | 11376 |
| Rule candidates inspected during learning | 3574595 | 7708633 | 38682013 | 34319838 |
| Action-body seconds | 160.842 | 297.850 | 85.543 | 138.478 |
| Replay checks / failures | 3331 / 0 | 5622 / 0 | 11356 / 0 | 11394 / 0 |

Algebra stopped after exhausting its bounded frontier in both conditions. Fold
stopped at the cycle cap. Action-body timing excludes scheduling, serialization
and held-out evaluation; it is not total runtime. Whole measurement commands
for both domains took619s for128 and862s for256, measured to1s resolution.
The complete Actions verification job took28m46s including tests and analysis.

## Did Newly Stored Concepts Affect Later Work?

Algebra: all128 additional concepts were expanded.20 new theorems referenced
additional concepts. No additional concept had a recorded later child concept.
Fold: none of the128 additional concepts had been expanded at the cutoff.
Nevertheless131 theorems referenced additional concepts as comparison peers;
a concept need not be expanded to be used as a peer in a conjecture.

The recorded parent genealogy only records the expanded parent, not every
operand. Its maximum depth must not be presented as a complete semantic DAG.

The predeclared ablation disabled all high-condition-only theorems and their
proof descendants as executable rules. Scores stayed51/64 and54/64. No new
representation was acquired in the high condition. This experiment therefore
shows additional autonomous mathematical work, but no additional held-out
capability from doubling archive capacity at this fixed term bound.

## Overhead and Nonclaims

On freshly repeated held-out evaluations, algebra median matching time rose
from24.081ms to28.281ms. Fold matching time changed from4.197ms to3.548ms;
its effective rewrite-rule set was not simply a superset, so this decrease
must not be interpreted as evidence that more knowledge always speeds lookup.
Function-level matching and scheduling diagnosis belongs to the separate
bottleneck study, not this archive comparison.

These held-out questions test same-domain transfer under a32-node exact-prover
input bound. They do not demonstrate a new solver, new mathematics, transfer
to a new mathematical domain, or continuous unbounded capability growth.
The finite fold model certifies24 orientations and does not preserve collision
or physical fold legality. This report does not broaden any certificate scope.
