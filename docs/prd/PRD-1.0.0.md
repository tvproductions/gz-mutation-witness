# PRD: gz-mutation-witness 1.0.0

**Status:** Draft, awaiting the maintainer's approval. Written 2026-11-21 from the advice gzkit
gathered while this engine lived inside it (sources below). It governs the 1.0.0 major; minors
before it are driven by the backlog items it names.

## Purpose

Tell a load-bearing guard from a vacuous test. Delete or bend a guard, run the tests that should
catch it, and say honestly what happened. A failing mutant run is not automatically a kill, and a
passing one is not automatically a survival, so the engine keeps claims about the **guard** apart
from claims about the **run**:

| Outcome | Claim about | Meaning |
|---|---|---|
| `killed` | the guard | a nominated test failed on an assertion |
| `survived` | the guard | the mutant activated and no test caught it |
| `invalid` | the run | nothing was graded: absent target, no-op edit, mutant does not compile |
| `inconclusive` | the run | the failure cannot be attributed to the guard |

## Consumers

- **gzkit**: acceptance proofs (`acceptance_execution`, `obpi_acceptance`), the commit-grain red
  witness (`gz arb red --commit`, `commit_witness`), reviewed guard canaries (`guard_canary`), and
  its drydock dock trials.
- **gz-starter** and the projects built from it, beside its `hygiene` tooling.
- Any `unittest` project that wants mutation evidence without pytest.

## Product outcomes for 1.0.0

1. **Verdicts a reviewer can trust and reproduce.** Every result carries what is needed to re-run
   and check it, and the four-way verdict never collapses a run fault into a guard claim.
2. **A sweep sized for daily use.** A sweep of the scale gzkit's O4 dock trial ran (574 mutants,
   more than four hours on 2026-11-21) completes in minutes on a multi-core machine.
3. **Operable long runs.** Progress is visible, results survive an interruption, and a re-run
   resumes rather than restarting.
4. **A public API consumers do not have to reach past.**

## Requirements

- **Runner.** `unittest` only; no runtime or test dependency on pytest or coverage.py.
- **Platforms.** Windows, macOS and Linux are co-equal; every feature works on all three, or is an
  explicitly optional accelerator that refuses clearly where it cannot run.
- **Dependencies.** Python 3.14 standard library plus Pydantic at runtime.
- **Isolation.** Every mutant runs with its own bytecode cache, and the original tree's bytes are
  restored after every sweep, including one whose mutant does not compile.
- **No score floor.** The library reports; it never sets a repository-wide kill-score threshold
  (Google, *Practical Mutation Testing at Scale*, IEEE TSE 2022; gzkit's 2026-07-18 audit).

## Backlog

| Theme | Issues |
|---|---|
| Verdict correctness | [#1](https://github.com/tvproductions/gz-mutation-witness/issues/1) judge each test, not the run *(decided)*; [#12](https://github.com/tvproductions/gz-mutation-witness/issues/12) retained-evidence contract; [#13](https://github.com/tvproductions/gz-mutation-witness/issues/13) equivalent-mutant review |
| Speed | [#2](https://github.com/tvproductions/gz-mutation-witness/issues/2) baseline once; [#3](https://github.com/tvproductions/gz-mutation-witness/issues/3) parallel within a file; [#4](https://github.com/tvproductions/gz-mutation-witness/issues/4) relative hang bound; [#5](https://github.com/tvproductions/gz-mutation-witness/issues/5) coverage-guided selection; [#6](https://github.com/tvproductions/gz-mutation-witness/issues/6) in-process compile; [#7](https://github.com/tvproductions/gz-mutation-witness/issues/7) optional warm worker |
| Operability | [#8](https://github.com/tvproductions/gz-mutation-witness/issues/8) stream, progress and resume; [#9](https://github.com/tvproductions/gz-mutation-witness/issues/9) timings |
| Public API | [#10](https://github.com/tvproductions/gz-mutation-witness/issues/10) isolated runner and apply-in-a-copy helper |
| Generation | [#11](https://github.com/tvproductions/gz-mutation-witness/issues/11) generation by contract with adopters *(decided)* |

## Boundaries

- **Not a governance tool.** Binding mutants to claims, ledgers or registries stays with the
  consumer; gzkit's guard canaries are the worked example of a consumer, not a feature here.
- **Not a pytest plugin**, and not a wrapper around a pytest-based tool.
- **No LLM-generated mutants.** Generation is mechanical, from the adopter's declared contract.
- **Not a score.** Survival rates are reported only over reviewed non-equivalent mutants, with
  INSUFFICIENT_EVIDENCE when there is no denominator.

## Open decisions

None at this draft.

## Decisions

- **Each nominated test is judged on its own** (maintainer, 2026-11-21, verbatim: *"judge each
  nominated test on its own, errors elsewhere don't disqualify"*;
  [#1](https://github.com/tvproductions/gz-mutation-witness/issues/1)). A nominated test that
  fails on an assertion in its own body kills the mutant; errors in other tests do not
  disqualify it.
- **Mutant generation belongs here, by contract with adopters** (maintainer, 2026-11-21,
  verbatim: *"yes, mutant gen, but in collaboration with adopters (design-by-contract)"*;
  [#11](https://github.com/tvproductions/gz-mutation-witness/issues/11)). The adopter declares
  the contract; the generator produces the mutants that violate it. The contract's shape is
  still to be designed.

## Acceptance for 1.0.0

- Every backlog item above is closed, resolved by a recorded decision, or explicitly deferred past
  1.0.0 in this document.
- The O4-scale benchmark completes, with its timing recorded by the library itself (#9).
- The release workflow's three-platform test matrix passes at the 1.0.0 tag.

## Sources

- [Inherited from gzkit: TI-01 and its evidence](inherited-ti-01.md): the pool item, its gate, the
  2026-09-24 pilot, the promotion trigger, the Stdlib-First decision and the engine alternatives,
  moved here verbatim when gzkit withdrew TI-01.

All at gzkit commit `a7b243474584d4da88fbde73f2e2807164c4be54`:

- [ADR-pool.test-integrity-tooling](https://github.com/tvproductions/gzkit/blob/a7b243474584d4da88fbde73f2e2807164c4be54/docs/design/adr/pool/ADR-pool.test-integrity-tooling.md): TI-01's mutation contract, the promotion trigger, the stdlib-first decision.
- [Enforcement-claim audit, 2026-07-18](https://github.com/tvproductions/gzkit/blob/a7b243474584d4da88fbde73f2e2807164c4be54/docs/governance/enforcement-claim-nc-audit-2026-07-18.md): mutation testing as the missing machine; no score floor.
- [Test-suite integrity audit, 2026-09-24](https://github.com/tvproductions/gzkit/blob/a7b243474584d4da88fbde73f2e2807164c4be54/docs/evals/test-suite-integrity-audit-2026-09-24.md): the Cosmic Ray pilot.
- [O4 dock-trial record, 2026-11-21](https://github.com/tvproductions/gzkit/blob/a7b243474584d4da88fbde73f2e2807164c4be54/docs/governance/harbor-ro12-dock-trial-evidence/o4-sweep-2026-11-21.json): the follow-up and timing measurements.
