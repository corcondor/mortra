# Self-game-design v2: fresh experiment and website source

Experiment: `self-game-design-v2-20260923`.
Frozen experiment commit: `4ab73eda40daf15d00dc0f00bd33e46ce5499e16`.
Source base: `483d1592e5cd0d2b23d474cc79e217b121fd1fbe`.

## Reproduce

Python 3.12.10, numpy 1.26.4, matplotlib 3.10.5 were used.

```sh
python -m pip install -r requirements-game-tests.txt
python -m pytest tests/test_self_game_design_v2.py -q
python scripts/evaluate_autonomous_game_design_loop.py --output reports/self_game_design_v2_reproduction
```

The output directory must be new or empty. The old `reports/self_game_design`
directory is explicitly refused. The checked-in v2 artifacts are not overwritten.
All conditions regenerate from the original seeds, with a newly learned graph
for every evaluation. No old mutation sequence is loaded.

```sh
python scripts/export_self_game_design_web.py
npm ci
npm run test:game-run
npm run build:web
npm run dev:web
```

`build:web` delegates to `npm run build`, retaining the Python dependency-closure
check and adding experiment hash verification and static asset synchronization.
The initial research baseline failed this check because `api/solve.py` imported
four absent runtime modules:
`runtime_mobius_cycle_synthesis`, `runtime_rational_unit_sum_synthesis`,
`runtime_trigonometric_triangle_synthesis`, and
`runtime_triangle_radii_exponential_synthesis`. Staged deployment also returned
HTTP 500 for that API, while the previous production deployment returned 200.
The four files were recovered byte-for-byte from the previous production source,
not reimplemented. See `production_runtime_snapshot.json` for provenance and
hashes. The API entrypoint also matches that production source byte-for-byte.
This is runtime preservation, not a new research mechanism. The Web game demo
does not call that API.

## Fresh results

| Condition | MORTRA successes | Random successes | Mean successful actions | Observed states | Unique successful paths |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial | 50/50 | 16/50 | 45 | 536 | 1 |
| Targeted edits, final | 50/50 | 15/50 | 23 | 682 | 1 |
| Random-mutation control, final | 50/50 | 2/50 | 21 | 728 | 1 |

Targeted edits accepted: 5/20. Control edits accepted: 4/20.
Five additional creation seeds (201, 302, 403, 504, 605) were rerun with ten
edits each. Full stdout is in `run.log`. The observed wall time was 9.686 seconds
on this machine, not a portable speed claim.

The random-mutation control has a larger success-rate gap than targeted editing
in this run. Therefore this run does not establish superiority of targeted
editing. Neither success-rate gap nor path diversity establishes human fun.
All 50 trials in a condition share one layout and learned graph; they are not
50 independent held-out games.

## Change and preservation

The random baseline now increments its success total only once after each
trial, including a last-action goal. Logging and execution are protected by a
main entrypoint and refuse artifact replacement. Replay records contain the
actual trial-0 actions and full eight-component states, whether successful or
not. Trial 0 was chosen independently of outcomes.

AST comparison against the base confirmed that MicroGame, StructuralLearner,
solve_fixed_field, critique_game, both mutation generators, and
decide_acceptance were unchanged. Corrected metrics nevertheless change the
selected sequence: the old targeted run accepted 4 edits, the fresh v2 accepts 5.

The legacy experiment remains unmodified, with its original incorrect random
percentages. `export_verification.json` labels it UNREPAIRED, records its file
hashes, and compares historical and fresh v2 results without relabelling the
historical run as corrected.

## Web source boundary

The canonical export is `web/public/mortra/runs/self-game-design-v2-20260923/`.
The existing Next.js application serves an identical generated copy from
`public/mortra/runs/`. `manifest.json` records SHA-256 hashes, with byte-preserving
Git attributes. The exporter refuses to change already-published bytes.

- Manual mode runs only the game transition rules; it does not choose actions.
- Replay reads stored states, not a browser solver. Its label is
  `Recorded MORTRA experiment`.
- All 42 main/control history entries and candidate evaluations are checked:
  random counts are recalculated, trajectories replayed, and accepted/rejected
  world states compared.
- Web transition parity covers 15,000 Python-generated transitions and four
  complete recorded initial/final, MORTRA/random trajectories.
- The transition fixture is a bounded test, not a proof of all possible states.

The new Web view contains no `computeFixedField` substitute. Legacy HTML remains
only in the preserved old experiment; the v2 runner no longer emits that HTML.

## Release verification

The user authorized production publication after verification. Deployed source:
`3f286369e10d05d1e09bf1fb1a354e899a01ef01`. Production deployment:
`dpl_6Sqq6yAfnxYQWyGAk46j2kyXTLZW` (READY, promoted).

Fresh checks: 22 v2 tests, 152 existing public-solver tests, 2 production-source
preservation tests, and 6 browser/Python parity tests pass. Local and remote
production builds pass, including the 68-module Python dependency check.
The deployed browser was checked at 1440, 390, and 320 pixels; manual goal play,
keyboard/reset, replay controls, vertical comparison, timeline, metric metadata,
English/Japanese research/archive routes, and exact JSON equality pass without
page errors. The deployed math API returns its health response and the expected
derivative answer. `web_verification.json` records the browser checks.

Vercel aliases for mortra.ai and www.mortra.ai point to the new deployment.
However, public DNS still points elsewhere, using ns1/ns2.emailverification.info.
The domain registrar listed by RDAP is Key-Systems GmbH; the retailer and the
reason for these nameservers are not established. Vercel recommends A
`76.76.21.21`. A TLS-verified request directed to that server for mortra.ai
returns the new homepage with HTTP 200. This is NOT evidence that public DNS
is repaired. Domain recovery remains an external blocker.

`site_release_verification.json` preserves the deployment IDs, failed staging
attempt, corrected test-hash assumption, final results, and DNS limitation.
No previous experiment is relabelled as corrected.
