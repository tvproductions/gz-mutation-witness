# Changelog

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
