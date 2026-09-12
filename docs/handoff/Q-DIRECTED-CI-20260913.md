# Shared q-directed verification

The repository remains `corcondor/mortra`. The research baseline is
`dd196832d5fb73861e1b01893b6e0e347db9f90b`, whose parent is the Claude handoff
`6eedcb7888c3f164933115b94392a557e4b78dca`. This change adds verification
infrastructure and dependency declarations, not a new representation-selection
algorithm. Historical results in the handoff are not fresh CI evidence.

## Existing workflow audit

Audited all eight files at the research baseline before editing. The default
branch reported by GitHub was `release/mortra-1-beta`; its scheduled runs used
`74675e48b3638fee8d82e00f1216f6b00617ebc3`. GitHub's commit comparison reported
the research baseline 17 commits ahead, with no workflow changes. No Actions
run was returned for the baseline SHA when queried.

In the following table, "filtered" means the file's existing path filters.
"unset" means no workflow-level setting, not that the token has no permissions.

| File | Trigger / schedule | Python / dependencies | Executed checks | Artifact | Concurrency / permissions |
|---|---|---|---|---|---|
| generate.yml | repository_dispatch: generate-problem | 3.12; worker/requirements.txt, npm install | worker npm test and build, then process-job | none | unset / unset |
| research-sweep.yml | every 5 minutes; manual | 3.12; worker requirements, npm install | worker npm test/build, then research-sweep | none | mathos-autonomous-research, cancel false / unset |
| sync-mathos.yml | minute 20 every 3 hours; filtered master push; manual | no Python; npm install/ci | Supabase upsert and feedback exports, not the representation suite | selection/fusion feedback | mathos-supabase-sync, cancel false / unset |
| worker-ci.yml | filtered master push; filtered PR; manual | 3.12; worker requirements, npm ci | worker tests/build, visual/diagram/construction checks | none | mortra-worker-kernel per ref, cancel true / contents read |
| mortra-paper-guided-geometry-ci.yml | filtered push/PR; manual | 3.12; worker requirements + pytest, pandas, pyarrow | exact geometry portfolio pytest | none | unset / contents read |
| real-symbolic-coordination.yml | filtered push/PR; manual external-reproduction option | 3.12; worker requirements, pinned Newclid; pytest/flint for Linux job | coordination unittest/pytest; optional Windows GCLC reproduction | optional external-reproduction.json | unset / contents read |
| reversible-symbolic-geometry.yml | filtered research/reversible-synthesis push; filtered PR; manual | 3.12; pinned Newclid, pytest, SymPy | bridge pytest, compilation, published artifact checks | none | unset / contents read |
| typed-logic-circuit.yml | filtered push/PR; manual | 3.12; NumPy | circuit unittest and two fresh experiments | two experiment JSONs | unset / unset |

The scheduled jobs are operational research resumption and distribution, not
the q-directed reproduction suite. They are unchanged. Instead of a duplicate
workflow, `worker-ci.yml` now has a second, isolated research job. Its displayed
name is **Verify MORTRA Kernels**. The original Worker job and its concurrency
remain for non-research triggers. Research-branch push/PR and a manual
q-directed request select the research job only, with read-only contents
permissions and no production secrets. Research runs queue rather than cancel
one another. Existing scheduled production workflows are not dispatched by
this procedure.

## Triggers

- Push to `codex/q-directed-closure-20260913` when the included source,
  configuration, dependency, handoff or workflow paths change.
- A matching PR whose source or target is that research branch.
- Manual execution using the already registered `worker-ci.yml`. Default
  manual mode remains `worker`; choose `q-directed` for this suite.

Example, testing the original baseline with the committed new harness:

```bash
gh workflow run worker-ci.yml --repo corcondor/mortra \
  --ref codex/q-directed-closure-20260913 \
  -f verification_suite=q-directed \
  -f target_ref=dd196832d5fb73861e1b01893b6e0e347db9f90b \
  -f expected_sha=dd196832d5fb73861e1b01893b6e0e347db9f90b
```

For a branch target, supply its name as `target_ref`. Supplying `expected_sha`
detects a moved branch before tests. With no target input, the triggering exact
SHA is used and checked. For PRs this is the PR merge commit, explicitly recorded
as such through `ref`, not falsely labelled the source-branch HEAD.

GitHub requires a manually triggered workflow to exist on the default branch;
this file already does. The selected research ref supplies the extended version.
Sources: [workflow_dispatch](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch),
[workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).

## Exact source and environment

Two read-only checkouts make old-commit verification possible:
`ci-control` contains the harness at the triggering workflow SHA;
`target` contains the requested research code. `verification.json` records
`harness_sha`, `workflow_sha` and target `sha` separately. Tests and all four
normal executions use the same target checkout. The harness does not import
mathematics from the control checkout. Test import paths are recorded and must
all belong to the target. Credentials are not persisted in either checkout.

Python is 3.12.10. The control commit's formal `requirements-test.txt` installs
its runtime requirements and test pins. This deliberately supplies the corrected
dependency definition when the target is the older baseline; the baseline source
is not edited. Environment and freeze files identify every installed version.
NumPy is a runtime dependency, pytest a test dependency. Installation and
`pip check` have separate logs. This same dependency file works outside CI.

## Fresh evidence and acceptance

`configs/q-directed-verification.json` fixes the 17-module, 351-test set and
four ordinary CLI commands before execution. The wrapper does not supply a
basis, matrices, readout or expected answer. A separate verifier test suite uses
synthetic fixtures solely to test fail-closed reporting; it is not counted in
the 351 or as a MORTRA discovery.

1. Run the related unittest suite and save structured counts/import locations.
2. Run `axis1` by q-directed closure, with independent enumeration at n=3,5
   and answer n=6. Require a newly derived basis, matrices, symbolic residual
   checks, derived readout and all-finite-words scope. Later reuse at n=9 must
   succeed. The workload selector may legitimately prefer the existing exact
   answer route; the newly certified representation is still stored and tested.
3. Read that exact store in a separate process for `axis1-from-AG`, answer n=12
   and reuse at n=14. Require zero candidates, acquisition and Task-certifier
   calls, matching source store, unchanged scope and a changed initial state.
4. Run collision-free q-directed acquisition. Require an in-layer legality
   counterexample, refusal of the reduced representation and exact fallback.
   Run reuse-only against the open-fold store and require a stop with no answer
   and no reacquisition.

The underlying CLI checks full distributions against independent enumeration;
the wrapper also rejects missing lengths, answer mismatches, missing
distributions, absent certificates, failed source seals, timeouts and missing
output. Exit zero alone never passes a stage. The plan and source hashes are
checked before every run. These are reproducibility checks, not a cryptographic
proof of the absence of intervention.

Packaged historical Windows ledgers are not used for CI acceptance. Their
raw-file fingerprints can correctly reject a Linux checkout with different line
endings. That optional portability experiment remains documented in the
reproduction guide; the compatibility guard is not bypassed.

## Artifacts

Each run uploads `q-directed-<run-id>-<attempt>` for 30 days, even on failure:

- `verification.json`: repository, ref, exact SHA, run ID, harness SHA, test
  counts, normal/reuse/refusal verdicts, errors and generation time.
- `plan.json`, `config.json`, `git-sha.txt`, source/harness hashes.
- Environment summaries, dependency freeze, installation/check logs.
- Test log, structured test result and all loaded test/source locations.
- Four CLI logs and complete per-run traces, ledgers, configurations and seals.
- `representation-summary.json` and `refusal-summary.json`, derived from the
  new run's records, with no new mathematical interpretation.

A prepared record has false verdicts until execution completes. Failed or
incomplete dependency setup must never appear as successful reproduction.
The workflow summary links the record to its GitHub run. Use the run's artifact
link to share results among Claude, Codex and human reviewers.

For local development of the verifier (not Cloud evidence):

```bash
python scripts/verify_q_directed_ci.py --prepare --repo . --output ../q-ci-fresh
python scripts/verify_q_directed_ci.py --execute --repo . --output ../q-ci-fresh
```

Use a clean committed target and a new output directory. No merge into release,
master or main is part of this change.
