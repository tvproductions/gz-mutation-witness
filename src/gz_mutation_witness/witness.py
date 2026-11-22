"""Mutation-sweep witness with a four-way verdict (GHI #963).

A mutation sweep is how gzkit distinguishes a load-bearing guard from a vacuous
test: delete the guard, and a test that still passes was never testing it. The
verdict is used as governance evidence, so the sweep has to be at least as
trustworthy as the tests it grades.

**A failing mutant run is not a kill.** That inference — "the suite failed, so
the mutation took effect and a relevant assertion caught it" — is wrong in four
distinct ways, and each one produces a non-zero exit that looks like a kill:

* the mutation's target text was never present, so nothing was mutated;
* the edit was a no-op, leaving the tree identical to baseline;
* the mutant does not import, so every test fails for a reason that says nothing
  about any guard (the same weak-vs-strong distinction :mod:`gzkit.red_witness`
  refuses to collapse);
* the failures are unrelated tests, or the baseline was already red.

**A surviving run is equally unsafe** — it can conceal a mutation that never
activated, or a test tree that did not really run. That is exactly what GHI #963
observed: CPython validates a cached ``.pyc`` on ``(mtime-seconds, size)``, two
byte-identical-length mutations landed in the same clock second, and the second
subprocess imported the first mutant's bytecode. Its verdict described a tree it
had not tested, and the contamination runs in both directions.

So this module reports **four** outcomes, and the split is the point:
``killed`` and ``survived`` are claims about the GUARD; ``invalid`` and
``inconclusive`` are claims about the RUN. A sweep that lumps them together
reports coverage it never observed.

Isolation is unconditional: every mutant runs in a subprocess with its own
``PYTHONPYCACHEPREFIX``, so there is no stale cache entry for the ``(mtime,
size)`` heuristic to match and each run must compile from source.
"""

import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gz_mutation_witness.failure import classify_failure
from gz_mutation_witness.local_execution import LocalExecutionSession, run_command
from gz_mutation_witness.observations import read_failure_blocks, read_test_observations
from gz_mutation_witness.run_contract import ExecutionSession

MutationOutcome = Literal["killed", "survived", "invalid", "inconclusive"]

_RUN_TIMEOUT_S = 600
_FIXTURE_FRAME = re.compile(
    r"^  File .*, line \d+, in (?:setUp|tearDown|setUpClass|tearDownClass|"
    r"setUpModule|tearDownModule|asyncSetUp|asyncTearDown|_callCleanup)$",
    re.MULTILINE,
)


class Mutation(BaseModel):
    """One text substitution to apply to the source under sweep."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    find: str = Field(..., min_length=1, description="Exact text to replace")
    replace: str = Field(..., description="Replacement text")
    label: str = Field(..., min_length=1, description="Short name for this mutation")
    expected_tests: list[str] = Field(
        default_factory=list,
        description="Nominated unittest IDs; short method names must resolve unambiguously",
    )


class MutationWitness(BaseModel):
    """The observed result of running the tree with one mutation applied."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(..., description="Mutation label")
    outcome: MutationOutcome = Field(..., description="killed | survived | invalid | inconclusive")
    reason: str = Field(default="", description="Why this outcome, when it is not a plain kill")
    target_present: bool = Field(default=False, description="The find-text existed in the source")
    source_changed: bool = Field(default=False, description="The edit actually altered the bytes")
    imports: bool = Field(
        default=False, description="Legacy field: source compiled; runtime import is not proven"
    )
    compiles: bool = Field(default=False, description="The mutated source compiled successfully")
    source_sha256: str = Field(default="", description="Digest of exact mutated source bytes")
    executed_tests: list[str] = Field(default_factory=list, description="Observed non-skipped IDs")
    tests_run: int = Field(default=0, description="unittest's reported run count")
    exit_status: int = Field(default=-1, description="Exit code of the mutated test run")
    failure_class: str = Field(default="", description="assertion | error | none")
    failing_tests: list[str] = Field(default_factory=list, description="Tests that failed")
    killing_tests: list[str] = Field(
        default_factory=list,
        description="Nominated tests that failed on an assertion in their own body",
    )
    pycache_prefix: str = Field(default="", description="Isolated bytecode cache for this run")
    output_tail: str = Field(default="", description="Tail of the mutated run's output")


class MutationSweep(BaseModel):
    """All witnesses from one sweep, with run verdicts kept apart from guard verdicts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(..., description="File that was mutated")
    baseline_green: bool = Field(..., description="The unmutated tree passed")
    baseline_output_tail: str = Field(default="", description="Tail of the baseline run")
    source_sha256: str = Field(default="", description="Original source byte digest")
    restored_source_sha256: str = Field(default="", description="Restored source byte digest")
    baseline_executed_tests: list[str] = Field(default_factory=list)
    baseline_tests_run: int = Field(default=0)
    witnesses: list[MutationWitness] = Field(default_factory=list, description="Per-mutation")

    @property
    def killed(self) -> int:
        """Mutations a named, relevant test caught."""
        return sum(1 for w in self.witnesses if w.outcome == "killed")

    @property
    def survived(self) -> int:
        """Mutations that activated and no test caught."""
        return sum(1 for w in self.witnesses if w.outcome == "survived")

    @property
    def invalid(self) -> int:
        """Runs that graded nothing — absent target, no-op edit, unimportable mutant."""
        return sum(1 for w in self.witnesses if w.outcome == "invalid")

    @property
    def inconclusive(self) -> int:
        """Runs whose failure cannot be attributed to the guard under test."""
        return sum(1 for w in self.witnesses if w.outcome == "inconclusive")

    @property
    def is_conclusive(self) -> bool:
        """True only when every mutation produced a verdict about its guard.

        Deliberately not ``killed == len(witnesses)``: a sweep may legitimately
        contain a surviving mutant. What it may not contain, and still be quoted
        as evidence, is a row that graded nothing.
        """
        return bool(self.witnesses) and not (self.invalid or self.inconclusive)


@dataclass(frozen=True)
class _BaselineObservation:
    green: bool
    executed_tests: frozenset[str]
    test_count: int
    output_tail: str
    timed_out: bool = False


type _BaselineKey = tuple[str, str, str, tuple[str, ...]]


class BaselineCache:
    """Reuse baseline observations across sequential sweeps in one batch.

    Create a fresh cache when any test inputs outside the target file change,
    including other source files, tests, configuration, or the environment.
    """

    def __init__(self) -> None:
        self._observations: dict[_BaselineKey, _BaselineObservation] = {}

    def _observe(
        self, project_root: Path, source: Path, source_sha256: str, command: list[str]
    ) -> _BaselineObservation:
        # Windows path objects case-fold even for case-sensitive directories.
        key = (str(project_root.resolve()), str(source.resolve()), source_sha256, tuple(command))
        observation = self._observations.get(key)
        if observation is None:
            observation = _run_baseline(project_root, command)
            if not observation.timed_out:
                self._observations[key] = observation
        return observation


def _resolve_tests(selectors: list[str], executed: frozenset[str]) -> set[str] | None:
    """Require each nominated selector to identify one actually executed test."""
    if not selectors:
        return None
    resolved: set[str] = set()
    for selector in selectors:
        matches = {identity for identity in executed if identity == selector}
        if "." not in selector:
            matches = {identity for identity in executed if identity.rsplit(".", 1)[-1] == selector}
        if len(matches) != 1:
            return None
        resolved.update(matches)
    return resolved


def _run(
    command: list[str],
    cwd: Path,
    pycache_prefix: Path,
    extra_env: dict[str, str] | None = None,
    pythonpath_prefix: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the test command with an isolated bytecode cache (GHI #963).

    ``pythonpath_prefix`` goes first on any inherited ``PYTHONPATH`` (GHI #1260).

    Returns:
        The completed process with text-decoded stdout and stderr; a non-zero exit is not raised.

    """
    return run_command(command, cwd, pycache_prefix, _RUN_TIMEOUT_S, extra_env, pythonpath_prefix)


def hang_reason(subject: str) -> str:
    """Say that ``subject`` exceeded the hang bound, which is a fact about the run."""
    return (
        f"{subject} exceeded the {_RUN_TIMEOUT_S}s hang bound and was stopped — "
        "a run that did not finish grades nothing"
    )


def _run_baseline(project_root: Path, command: list[str]) -> _BaselineObservation:
    with LocalExecutionSession(project_root, _run) as session:
        result = session.run(command)
    output_tail = _output_tail(result.output, session.cleanup_diagnostic)
    if result.exit_status is None:
        return _BaselineObservation(
            green=False,
            executed_tests=frozenset(),
            test_count=0,
            output_tail=_output_tail(output_tail, hang_reason("the baseline run")),
            timed_out=True,
        )
    executed, _, count = read_test_observations(result.output)
    return _BaselineObservation(
        green=result.exit_status == 0 and count > 0 and bool(executed),
        executed_tests=frozenset(executed),
        test_count=count,
        output_tail=output_tail,
    )


def _output_tail(output: str, diagnostic: str = "") -> str:
    if diagnostic:
        output = f"{output}\n{diagnostic}" if output else diagnostic
    return "\n".join(output.splitlines()[-40:])


def _compile_command(source: Path) -> list[str]:
    # The sweep's interpreter supports the project's syntax regardless of PATH.
    return [
        sys.executable,
        "-c",
        f"import py_compile; py_compile.compile({str(source)!r}, doraise=True)",
    ]


def _witness_one(
    mutation: Mutation,
    *,
    source: Path,
    original: str,
    cwd: Path,
    command: list[str],
    baseline_tests: frozenset[str],
) -> MutationWitness:
    """Apply one mutation, run the tree in isolation, and classify what happened."""
    if mutation.find not in original:
        return MutationWitness(
            label=mutation.label,
            outcome="invalid",
            reason="mutation target absent from the source — nothing was mutated",
        )
    mutated = original.replace(mutation.find, mutation.replace, 1)
    if mutated == original:
        return MutationWitness(
            label=mutation.label,
            outcome="invalid",
            reason="mutation is a no-op — the tree is identical to baseline",
            target_present=True,
        )

    source.write_bytes(mutated.encode("utf-8"))
    with LocalExecutionSession(cwd, _run) as session:
        witness = _grade_attempt(mutation, source, mutated, command, baseline_tests, session)
    if session.cleanup_diagnostic:
        witness = witness.model_copy(
            update={"output_tail": _output_tail(witness.output_tail, session.cleanup_diagnostic)},
        )
    return witness


def _grade_attempt(
    mutation: Mutation,
    source: Path,
    mutated: str,
    command: list[str],
    baseline_tests: frozenset[str],
    session: ExecutionSession,
) -> MutationWitness:
    prefix = str(session.cache_path)
    compile_result = session.run(_compile_command(source))
    if compile_result.exit_status is not None and compile_result.exit_status != 0:
        return MutationWitness(
            label=mutation.label,
            outcome="invalid",
            reason="mutated source does not compile — the failure is the edit, not a guard",
            target_present=True,
            source_changed=True,
            pycache_prefix=prefix,
        )
    compiles = compile_result.exit_status == 0
    result = session.run(command) if compiles else compile_result
    exit_status = result.exit_status
    if exit_status is None:
        subject = "the mutant's test run" if compiles else "the mutant's syntax check"
        return MutationWitness(
            label=mutation.label,
            outcome="inconclusive",
            reason=hang_reason(subject),
            target_present=True,
            source_changed=True,
            compiles=compiles,
            source_sha256=hashlib.sha256(mutated.encode("utf-8")).hexdigest(),
            pycache_prefix=prefix,
            output_tail=_output_tail(result.output),
        )
    output = result.output
    executed, failing, count = read_test_observations(output)

    def observed(
        outcome: MutationOutcome, reason: str = "", killing: list[str] | None = None
    ) -> MutationWitness:
        """Build the witness from what this run actually observed."""
        return MutationWitness(
            label=mutation.label,
            outcome=outcome,
            reason=reason,
            killing_tests=killing or [],
            target_present=True,
            source_changed=True,
            imports=True,
            compiles=True,
            source_sha256=hashlib.sha256(mutated.encode("utf-8")).hexdigest(),
            executed_tests=sorted(executed),
            tests_run=count,
            exit_status=exit_status,
            failure_class=classify_failure(exit_status, output),
            failing_tests=failing,
            pycache_prefix=prefix,
            output_tail=_output_tail(output),
        )

    nominated = _resolve_tests(mutation.expected_tests, baseline_tests)
    if nominated is None:
        return observed(
            "inconclusive", "nominated tests are absent, skipped, or ambiguous in baseline"
        )
    if count == 0 or not nominated.issubset(executed):
        return observed("inconclusive", "nominated tests did not execute in a completed mutant run")
    if exit_status == 0:
        return observed("survived")
    # Each nominated test is judged on its own (issue #1, maintainer ruling 2026-11-21:
    # "judge each nominated test on its own, errors elsewhere don't disqualify"): an
    # assertion failure in a nominated test's own body kills, whatever else errored.
    blocks = read_failure_blocks(output)
    failed = {test: blocks[test] for test in nominated if test in blocks}
    killing = sorted(
        test
        for test, (kind, text) in failed.items()
        if kind == "FAIL" and not _FIXTURE_FRAME.search(text)
    )
    if killing:
        return observed("killed", killing=killing)
    if any(kind == "FAIL" for kind, _ in failed.values()):
        return observed("inconclusive", "a fixture assertion failed outside the test body")
    if failed:
        return observed("inconclusive", "the nominated tests errored; none failed on an assertion")
    return observed(
        "inconclusive",
        "no expected test failed — the run witnessed collateral, not this guard's "
        f"coverage (expected any of {mutation.expected_tests})",
    )


def run_mutation_sweep(
    project_root: Path,
    source: Path,
    mutations: list[Mutation],
    command: list[str],
    *,
    baseline_cache: BaselineCache | None = None,
) -> MutationSweep:
    """Run a mutation sweep, verifying baseline, activation, isolation and cause.

    The source file is always restored, including when a mutant leaves it
    unimportable — a sweep that can strand a broken tree is worse than no sweep.

    Pass a shared baseline_cache to reuse observations across sequential sweeps
    in one batch. Start a fresh cache when other test inputs or the environment change.

    Returns:
        MutationSweep recording whether the baseline was green, the original and restored source
        hashes, the baseline's executed tests, count and output tail, and one witness per mutation
        (each ``inconclusive`` when the baseline is not green).

    """
    original_bytes = source.read_bytes()
    original = original_bytes.decode("utf-8")
    source_sha256 = hashlib.sha256(original_bytes).hexdigest()
    baseline = (
        _run_baseline(project_root, command)
        if baseline_cache is None
        else baseline_cache._observe(project_root, source, source_sha256, command)
    )

    witnesses: list[MutationWitness] = []
    try:
        for mutation in mutations:
            if not baseline.green:
                witnesses.append(
                    MutationWitness(
                        label=mutation.label,
                        outcome="inconclusive",
                        reason="baseline is not green — no mutant's failure can be attributed",
                    )
                )
                continue
            witnesses.append(
                _witness_one(
                    mutation,
                    source=source,
                    original=original,
                    cwd=project_root,
                    command=command,
                    baseline_tests=baseline.executed_tests,
                )
            )
            source.write_bytes(original_bytes)
    except BaseException as error:
        try:
            source.write_bytes(original_bytes)
        except OSError as restore_error:
            error.add_note(f"Could not restore the original source: {restore_error}")
        raise
    else:
        source.write_bytes(original_bytes)

    return MutationSweep(
        source=str(source),
        baseline_green=baseline.green,
        source_sha256=source_sha256,
        restored_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        baseline_executed_tests=sorted(baseline.executed_tests),
        baseline_tests_run=baseline.test_count,
        baseline_output_tail=baseline.output_tail,
        witnesses=witnesses,
    )
