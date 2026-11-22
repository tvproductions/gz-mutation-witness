# Baseline Reuse Implementation Plan

Execute the steps in order using unittest and a red-green test cycle.

**Goal** Enable adopters to reuse observed baselines across sequential sweeps.

**Architecture** Keep observations in a caller-owned cache for one batch.
Verify each lookup against the canonical paths, target bytes, and arguments.

**Spec** [ADR-0001, edition 2](../../decisions/ADR-0001-002-reuse-baselines-within-an-explicit-batch.md)

- [x] Add public API tests in `tests/test_witness.py`. Check baseline and
  mutant invocation counts, command alternation, changed bytes, distinct paths
  and roots, a fresh cache, timeout retry, and red or empty test observations.
  Exercise the old call signature and verify source restoration.
- [x] Run `uv run --locked python -m unittest tests.test_witness.TestBaselineCache -v`
  and observe that the baseline cache API is missing.
- [x] Add `BaselineCache` and the baseline observation lookup in
  `src/gz_mutation_witness/witness.py`. Re-export it from
  `src/gz_mutation_witness/__init__.py` and require no new runtime dependencies.
- [x] Run the focused tests. Document the batch lifetime in `README.md`
  and reconcile `pyproject.toml`, `uv.lock`, and `CHANGELOG.md` at 0.3.0.
- [x] Run the full pre-commit gate, check the lock, and build and smoke-test
  both distributions outside the checkout. Review the diff against the ADR.
- [x] Reproduce Windows path case folding with a portable regression and
  preserve the spelling of resolved paths in the cache key.
