---
id: ADR-0001
title: Reuse baselines within an explicit batch
revision: 2
state:
decision_date:
revision_date: 2026-11-22
approved_by:
approved_revision:
approval_ref:
---

# Reuse baselines within an explicit batch

Proposal, edition 2. Architectural approval is pending.

## Scope

[Issue #2](https://github.com/tvproductions/gz-mutation-witness/issues/2) asks
repeated sweeps of the same tree, source, and command to reuse one baseline.
A changed target digest or command requires a fresh run for that input.
A red baseline keeps every mutant inconclusive. The API applies to any
adopter, including projects without version control. It covers sequential
sweeps within one process and preserves existing callers' behavior.

## Alternatives

- Run every baseline afresh. This is the existing default and leaves the
  repeated work described in issue #2.
- Accept a precomputed observation. Adopters would need to acquire and
  replace evidence using a separate public workflow.
- Detect changes across the whole checkout. Scanning adds work to each
  sweep and misses changes to test inputs outside the checkout.
- Use an explicit batch. The caller owns the lifetime of an in-memory cache,
  while the library records and checks the observations within that batch.
  This is the selected design for review.

## Proposed design

Export `BaselineCache`. Add one optional keyword argument, `baseline_cache`,
to `run_mutation_sweep`. The caller creates one cache for a batch whose test
inputs are stable and passes it to every sweep in that batch. Omitting the
cache runs a fresh baseline every time.

Each entry uses the resolved project and target paths, the SHA-256 of the
original target bytes, and the exact command arguments. Distinct commands
can coexist so a batch can run command A, then B, then reuse A. The library
checks the target bytes on each call.

The caller creates a fresh cache when other test inputs change, including
tests, other source files, configuration, dependencies, environment,
executable resolution, or external fixtures. Creating a fresh cache also
lets the caller rerun a completed red baseline. There is no snapshot token,
checkout scan, global cache, or persistent cache.

Only the witness runner records observations. A completed baseline retains
its verdict, test identities, count, and output tail. A cached red baseline
or completed run without usable test evidence keeps mutants inconclusive.
A timed-out baseline produces the existing inconclusive result and is retried
on the next sweep. Launch errors retain their existing behavior.

Reuse affects only the baseline. Each mutant keeps its isolated bytecode
cache and existing verdict rules, and the sweep restores the source bytes.
Overlapping in-place sweeps of the same checkout remain unsupported.

## Confirmation

Public API tests count invocations for identical sweeps, alternating
commands, changed target bytes, distinct target paths and roots, and fresh
cache instances. Cover cached red and timed-out baselines, unchanged
behavior without a cache, retained observations, and source restoration.
Run the full pre-commit gate. This is a compatible feature candidate for
0.3.0 under the existing draft 1.0.0 PRD.

## Revision history

Edition 2 records the maintainer's choice of an explicit batch and replaces
the snapshot ID proposed in [edition 1](ADR-0001-001-reuse-baselines-within-a-caller-declared-snapshot.md).
Both editions are proposals. Selection of the batch design does not record
architectural approval of this edition.
