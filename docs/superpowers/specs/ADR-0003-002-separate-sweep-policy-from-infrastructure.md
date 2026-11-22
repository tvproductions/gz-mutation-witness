# ADR-0003, edition 2 · Separate sweep policy from infrastructure

Proposed 2026-11-22 for the [1.0.0 PRD](../../prd/PRD-1.0.0.md). The first
implementation slice supports [#14](https://github.com/tvproductions/gz-mutation-witness/issues/14).
This proposal revises [edition 1](ADR-0003-001-separate-sweep-policy-from-infrastructure.md)
to define execution-session ownership and the limits of timeout recovery.
The library was extracted from gzkit with its behavior and tests intact. Today
`_witness_one` grades a mutant while handling file writes, process results and
cache lifetime. `BaselineCache` starts a baseline on a miss. gzkit's commit
witness reaches into the private `_run` function. These seams are where the
planned isolation, parallelism, alternate runners, and replay would otherwise
acquire dependencies on the same concrete code.

## Proposed design

- **Domain.** Own the meaning of mutation identity, nominations, observations,
  four-way verdicts, and evidence validity. Evaluate verdicts with plain Python
  values. Keep process, filesystem, clock, parser, and database mechanisms at
  the boundary.
- **Application.** Coordinate baseline observation and reuse, mutation
  attempts, verdicts, restoration and progress. Own narrowly scoped contracts
  for the external effects each use case needs. A runner returns an application
  observation or a typed run failure. A workspace provides the effectful file
  and isolation operations the sweep needs. Add clock and evidence-store
  contracts as their use cases arrive. Let the application own when to reuse an
  observation. Preserve the caller-owned batch and timeout rules in
  [ADR-0001, edition 2](../../decisions/ADR-0001-002-reuse-baselines-within-an-explicit-batch.md).
- **Adapters and composition.** Process adapters own child and descendant
  lifetime plus platform-specific errors. Workspace adapters own file and copy
  operations. The `unittest` translation layer turns output into observations
  carrying named test identities and failure evidence. The public library
  boundary wires these collaborators and maps to the existing Pydantic API.
  Preserve documented imports, the serial call, result meanings, and existing
  serialization in the architecture-only changes. Add new public contracts
  through their owning backlog items. gzkit uses the published API. Its canary
  registration and governance rules stay with gzkit.

## First slice · #14 timeout recovery

The application opens one isolated execution session for a baseline or mutation
attempt and supplies the working directory, command, and existing timeout. The
session owns the per-attempt bytecode cache and coordinates it with process
control. Both the syntax check and the mutant test can use the same session.
The workspace remains responsible for source edits and restoration. The
application receives typed execution results and owns their effect on the sweep.

- **Ordinary timeout.** Stop the process tree, confirm that monitored processes
  have exited, and collect available output before releasing the cache or
  restoring the target. Report the mutant as `inconclusive` with the timeout
  reason and continue. A timed-out baseline remains ineligible for reuse.
- **Cache cleanup failure after confirmed shutdown.** Preserve the original
  timeout or run diagnostic, report the cache cleanup problem, and continue if
  the workspace can be restored and the next attempt gets a fresh cache.
- **Containment failure.** If the adapter cannot establish containment at launch
  or confirm shutdown, surface an infrastructure failure with the original
  diagnostic and stop scheduling against that workspace. Report what failed
  and attempt recovery without claiming a clean shutdown.

On Linux and macOS, use a dedicated POSIX session and process-group control for
ordinary subprocess trees. On Windows, evaluate a Job Object that contains
the command before user code runs, including when the test launcher already
runs in a Job Object. Windows console groups by themselves only provide console
signaling. The patch requires native integration evidence on all three systems.
These mechanisms do not provide portable containment for commands that
deliberately detach or arrange execution through an external service. Those
commands are outside the supported #14 contract. No new runtime dependency is
proposed. [Python subprocess](https://docs.python.org/3.14/library/subprocess.html#subprocess.Popen) · [Python process-group signaling](https://docs.python.org/3.14/library/os.html#os.killpg) · [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) · [Windows console process groups](https://learn.microsoft.com/en-us/windows/console/console-process-groups)

Use a native test that starts a descendant which writes to the cache past the
deadline. Verify descendant exit, the timeout diagnostic, restoration, and a
successful subsequent mutation. Verify the ordering and secondary failure
paths with deterministic tests. Preserve the existing public sweep signature
and result schema in this patch. Public runner APIs belong to #10, timings to
#9, and changes to the timeout value to #4.

Temporary copies protect the original checkout from project-relative writes
when the adapter runs tests from the copy. Define how the adapter handles
commands, paths and imports that might still refer to the original checkout.
Copying alone provides no process sandbox for absolute paths or unrelated
external effects.

## Approaches considered

- **Recommended · Refactor in behavior-preserving slices.** Establish the
  process and workspace boundaries with real consumers, beginning with timeout
  recovery. Extract verdict policy against existing examples and introduce ports
  as the corresponding use cases need them. Keep the published entry point
  usable throughout and enforce inward dependencies as boundaries land.
- **Extract pure grading only.** This makes verdict rules easier to test but
  leaves timeout recovery, isolation, and workspace ownership entangled with
  sweep coordination.
- **Replace the engine behind the API in one change.** This can define every
  boundary at once but increases the risk of changing verdicts, cache reuse,
  restoration, and downstream behavior together.

## Refactoring sequence and confirmation

1. Characterize current public verdicts, cache reuse, isolation, and result
   shapes. Establish the runner seam and its application-owned timeout result.
   For #14, verify that real descendant processes exit, the mutant is reported
   as inconclusive, and the next mutant runs on each supported platform.
2. Separate policy and orchestration from effectful runners and workspaces.
   Verify rules and sequencing with fake ports. Verify source restoration,
   working-directory writes, import origin, and runner-output translation
   through real adapters. Add an automated dependency check that would fail if
   policy or orchestration imported a concrete adapter.
3. Route execution variants and replay through the established seams. Verify
   public runner and copy-helper use from an installed gzkit consumer. Check
   that named killing tests survive export, including when another test errors.

Detailed process launch and shutdown mechanics, retained-evidence and resume
formats, and public helper signatures need design at their owning seams.
