---
id: ADR-0001
title: Reuse baselines within a caller-declared snapshot
revision: 1
state:
decision_date:
revision_date: 2026-11-22
approved_by:
approved_revision:
approval_ref:
---

# Reuse baselines within a caller-declared snapshot

Proposal, edition 1. Architectural approval is pending.

## Scope

[Issue #2](https://github.com/tvproductions/gz-mutation-witness/issues/2) asks
repeated sweeps of the same tree, source, and command to reuse one baseline.
A changed target digest or command requires a fresh run. A red baseline
keeps every mutant inconclusive. Existing callers must keep their current
behavior. The decision covers sequential sweeps within one process.

## Alternatives

- Run every baseline afresh. This needs no caller bookkeeping and preserves
  current behavior, but leaves the repeated work reported in issue #2.
- Accept a precomputed observation. The adopter would explicitly manage
  evidence acquisition and replacement. This exposes a second workflow and
  requires deciding whether callers may construct or serialize evidence.
- Use a caller-owned, in-memory cache. The library can record observations,
  check its own reuse keys, and leave the lifetime and snapshot identity
  with the adopter. This is the proposed approach.

## Proposed design

Export `BaselineCache` and extend `run_mutation_sweep` with the optional
keyword arguments `baseline_cache` and `snapshot_id`. Reuse is opt-in.
Supply both arguments or neither. A snapshot ID must be a nonempty string.

Each entry is keyed by the caller's snapshot ID, resolved project and source
paths, the SHA-256 of the original source bytes, and the exact command
arguments. The adopter must change the snapshot ID when any other input
capable of changing the baseline changes. That includes tests, other source
files, configuration, environment or executable resolution, and external
fixtures. Callers unable to identify a stable snapshot should use fresh runs.
A commit SHA suffices only when it identifies the actual effective test
inputs.

Only the witness runner creates cache entries. Each completed observation
preserves the existing baseline verdict, test identities, count, and output
tail. Cached red observations leave every mutant inconclusive, and a
completed run without usable test evidence stays inconclusive. A timeout
produces the existing inconclusive result and is retried on the next sweep.
Launch errors retain their existing behavior.

Reuse only covers the baseline observation. Each mutant still runs with
its own bytecode cache, uses the same verdict rules, and restores the
source bytes. The caller owns cache lifetime. There is no process-global or
persistent cache. Overlapping in-place sweeps of the same checkout remain
unsupported because the runner edits that checkout while testing.

## Confirmation

Tests must count baseline and mutant invocations across the public API.
Cover matching reuse, changes to source bytes, command and snapshot ID,
separation across checkouts and target paths, red and timed-out baselines,
and the existing behavior without a cache. Check byte restoration, retained
observations, and the full pre-commit gate. This is a compatible feature
candidate for 0.3.0 under the existing draft 1.0.0 PRD.
