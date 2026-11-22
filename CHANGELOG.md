# Changelog

## 0.3.1 (unreleased)

- [#14](https://github.com/tvproductions/gz-mutation-witness/issues/14) stops
  managed test descendants before cleaning the per-run bytecode cache. A
  contained timeout retains its diagnostic, and the sweep continues with a
  fresh cache for the next attempt.
- The execution-session boundary reports unconfirmed shutdown as an
  infrastructure failure and stops scheduling against the affected workspace.
  Process containment covers ordinary descendant processes.
- Document the execution and capture contracts. Update development verification
  to gz-starter 0.12.1 and relocate starter state to `.gz-starter/`.

## 0.3.0 (2026-11-22)

- [#2](https://github.com/tvproductions/gz-mutation-witness/issues/2) adds opt-in
  baseline reuse across sequential sweeps with a caller-owned `BaselineCache`.
  Sweeps without a cache still run a fresh baseline. Reused red observations
  keep mutants inconclusive.
- The cache records baseline evidence within the batch boundary approved in
  [ADR-0001, edition 2](docs/decisions/ADR-0001-002-reuse-baselines-within-an-explicit-batch.md).

## 0.2.1 (2026-11-22)

- Refresh locked development dependencies and release actions. Release CI now
  selects an exact uv version and uses the pinned starter verifier to confirm
  that unittest discovers and runs the product suite.
- Add the pinned, on-demand class cohesion analyzer to the hygiene group.
- Ship the typing marker for the annotated public API and record the selected
  lite profile and repository-scoped Codex activation.
- Starter acceptance is conditional while shared cognitive analyzer
  qualification is deferred under gz-starter 0.12.0.

## 0.2.0 (2026-11-21)

- **What counts as a kill changed** ([#1](https://github.com/tvproductions/gz-mutation-witness/issues/1)).
  Each nominated test is judged on its own: a nominated test that fails on an assertion in
  its own body kills the mutant, whatever else errored in the run. Before, any error
  anywhere made the whole run `inconclusive`. A nominated test that only errors, or fails
  in a fixture, still does not kill.
- `MutationWitness.killing_tests` names the nominated tests that killed the mutant.
- `observations.read_failure_blocks` reads each failed test's own report from unittest output.

## 0.1.0 (2026-11-21)

- Extracted as-is from gzkit's `gzkit.mutation_witness`.
