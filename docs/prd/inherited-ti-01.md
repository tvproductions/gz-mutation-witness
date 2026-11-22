# Inherited from gzkit: TI-01 and its evidence

Moved verbatim on 2026-11-21 from gzkit's
[`ADR-pool.test-integrity-tooling`](https://github.com/tvproductions/gzkit/blob/a7b243474584d4da88fbde73f2e2807164c4be54/docs/design/adr/pool/ADR-pool.test-integrity-tooling.md) when its item TI-01 was withdrawn
there (operator, verbatim: *"withdraw TI-01 from the pool ADR, keep the rest"*, then
*"move to new project"*, *"it can use those"*). It is working material for
[PRD-1.0.0](PRD-1.0.0.md) and its backlog, not a decision of this project: the
wording speaks of gzkit, its promotion and its modules as they stood. Its links
point into gzkit at that commit.

## TI-01, as gzkit's pool ADR scoped it

- **TI-01 — `mutate`:** reproducible mutation diagnostics for explicitly named
  enforcement modules. Run a clean baseline, isolate every mutant, invoke
  `python -m unittest` on declared tests, enforce timeouts, and retain distinct
  killed, survived, incompetent, and timed-out outcomes. A nonzero exit is not
  automatically a semantic kill; classify import, setup and infrastructure
  errors separately. Retain mutant identity, actual diff, source commit,
  dependency versions, command, test outcomes, and raw output as CI artifacts.

## Its gate, from the 2026-09-24 audit's § 10

- **TI-01** carries § 10 "General mutation diagnostic completeness". Fail on
  missing jobs, a failed baseline, wrong import origin or an unclassified
  outcome. Raw survivor percentage alone never fails quality.

## Pilot evidence — 2026-09-24

Baseline source commit: `5d9885a08c438b0aa546716b20a181c55342612e`.

| Module | Mutants | Killed | Survived | Incompetent | Timed out | Survival |
|---|---:|---:|---:|---:|---:|---:|
| covers | 247 | 163 | 84 | 0 | 0 | 34.01% (n=247) |
| mutation_witness | 336 | 245 | 90 | 0 | 1 | 26.79% (n=336) |
| red_parity | 164 | 114 | 50 | 0 | 0 | 30.49% (n=164) |
| red_witness | 355 | 204 | 151 | 0 | 0 | 42.54% (n=355) |
| req_coverage | 46 | 28 | 18 | 0 | 0 | 39.13% (n=46) |
| tautological_tests | 580 | 239 | 341 | 0 | 0 | 58.79% (n=580) |
| test_shape | 117 | 50 | 67 | 0 | 0 | 57.26% (n=117) |
| validate_commit_trailers | 59 | 38 | 19 | 2 | 0 | 32.20% (n=59) |
| verifier_pipe_gate | 1130 | 554 | 573 | 0 | 3 | 50.71% (n=1130) |

All nine selected baselines passed. The pilot generated 3,034 mutants across
nine modules and selected 600 distinct unittest methods. Raw kills include
nonzero error exits; the audit separately distinguishes assertion output.
Two reviewed non-equivalent survivors in req_coverage.py (comparison at line
130 and continue at line 131) pass the selected 24 tests and fail an independent
exact-filter discriminator. The attempted full-suite replay stopped on its
clean-baseline timeout before either mutation, so full-suite survival is not
established. See [docs/evals/test-suite-integrity-audit-2026-09-24.md](https://github.com/tvproductions/gzkit/blob/a7b243474584d4da88fbde73f2e2807164c4be54/docs/evals/test-suite-integrity-audit-2026-09-24.md) for every
outcome, source/test command, equivalence limits and machine-readable identities.

This is a scoped diagnostic. It establishes no repository-wide mutation score
floor and does not establish that a survivor is non-equivalent merely because
it survived. Evidence is keyed to a mutant and test command, not to a line
alone. A script must reject missing, baseline-failing, or unclassified runs.

## Proposed machine-decidable trigger for promotion consideration

Recommend a promotion discussion when at least one enforcement module has:
(a) a passing baseline, (b) at least one conclusive, reviewed non-equivalent
mutant, and (c) a reviewed non-equivalent survival rate greater than **0%**.
Compute `survived_non_equivalent / (killed_non_equivalent + survived_non_equivalent)`
from retained records; no denominator means INSUFFICIENT_EVIDENCE, not 0%.
Timed-out, incompetent, equivalent and unreviewed cases are reported separately.
Bind each review disposition to the mutant diff and source commit so an
unreviewed survivor cannot satisfy the predicate.

The threshold is a diagnostic trigger, not a score floor: one confirmed
undetected enforcement fault establishes the gap without rewarding tests that
kill irrelevant mutants. It does not authorize promotion or execution. Sponsor,
clear acceptance criteria, settled dependencies, capacity, campaign order and
explicit operator initiation still govern under the pool-curation policy.

## Decision required at promotion — Stdlib-First

First evaluate the existing `mutation_witness` harness with stdlib `ast`,
`unittest`, `subprocess`, `tempfile`, and `sqlite3`. That path supports bounded,
hand-authored fault experiments and may be enough for the required contract.
Python can implement a general mutator; do not claim otherwise. The stdlib
has no supplied general mutation-operator catalog, source mutation engine, and
persistent mutation-session scheduler. Building those would make gzkit their
maintainer.

The promoted ADR must choose whether the measured breadth and repeatability
of Cosmic Ray justify adopting and maintaining that external engine instead.
Name its pinned version, transitive dependency and platform costs, runtime
budget, and retained-evidence contract. If adopted, approve it explicitly as
optional test tooling, retain unittest as the test runner, and keep it out of
gzkit's runtime dependency set unless a separately justified contract requires
otherwise. The present audit installs nothing in gzkit.

## Alternatives and tradeoff

1. Continue stdlib-only, hand-authored mutation experiments. Small dependency
   surface, but operator selection and experiment implementation remain work.
2. Adopt Cosmic Ray as scoped optional tooling. General fault generation and
   reproducible sessions, with new dependency, execution and triage costs.
3. Require a repository-wide kill score. Rejected as this proposal's design:
   equivalent or irrelevant mutants would reward implementation-pinning tests.

## The 2026-07-18 recommendation

The 2026-07-18 enforcement audit recommends Cosmic Ray scoped to enforcement
modules as a diagnostic with no repository-wide score floor; this proposal
preserves that boundary. See
[enforcement-claim-nc-audit-2026-07-18.md](https://github.com/tvproductions/gzkit/blob/a7b243474584d4da88fbde73f2e2807164c4be54/docs/governance/enforcement-claim-nc-audit-2026-07-18.md)
