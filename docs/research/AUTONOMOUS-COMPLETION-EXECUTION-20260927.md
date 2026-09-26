# MORTRA autonomous completion: execution boundary

This specification fixes an entrypoint capability check before running it.
It is not a new game-design algorithm or a confirmatory ability benchmark.

- User objective: MORTRA, not Codex, generates, tries, diagnoses and improves a
  playable game. Preserve genuine stops and failures. No oracle answer data.
- Source base: 19f79f3b6973b72cafc6ad311e38ad580f7e1c54.
- Run the existing adaptive Designer v1.2 public entrypoint `evolve(1,3101,...)`.
  Use its first existing smoke seed, unmodified configuration and code.
  This is deliberately not advertised as a fresh independent game.
- Inspection identifies `v1.1.runner.prepare` as requiring a complete-world
  oracle before task creation, self-play, and feedback. That is an expected
  dependency conflict, not an outcome discovered by MORTRA.
- Do not substitute a newly invented reward, task population, rule, problem
  diagnosis, strategy or mutation when that dependency is denied.
- Observe the generated candidate at function return and preserve it before
  preparation. Deny oracle function entry before its body. Never supply a
  guessed result, learned-graph stand-in, false value or hidden-state label.
- Repeat the unchanged execution once to verify the same stop. The second
  attempt is reproduction, not improvement. Record both attempts independently.
- No policy score is available if self-play is never reached. Do not report
  random-control or player success rates with a zero denominator.
- Preserve actual entrypoint logs, candidate, event/call counts, action records,
  exceptions, source hashes, command, exact runtime, CPU/wall time and process
  peak memory. Hash frozen source files before and after execution.
- GitHub Actions executes the process. Only harness code is added. The original
  research modules are unchanged. Tests verify the access guard and recording,
  not game quality or MORTRA task success.
- The finite test checks the named entrypoint only. Do not generalize its stop
  to all MORTRA algorithms. Report the artifact objective as NOT_COMPLETED when
  it stops before gameplay. Stop rather than fabricate autonomous revisions.

Reproduction: checkout the eventual recorded exact commit with full history;
install the same dependencies as the v1.2 workflow (Python 3.12, numpy 1.26.4,
matplotlib 3.10.5, psutil 7.0.0, pytest 8.4.1). Exact resolved Python version is
saved at execution. Run the six observer tests unchanged, then
`python -m experiments.autonomous_completion.probe --output <unused-path>`.
