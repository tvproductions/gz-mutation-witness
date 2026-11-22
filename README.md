# gz-mutation-witness

A mutation-sweep witness for `unittest` suites. It applies text mutations to one
source file, runs a test command per mutant in an isolated subprocess with its own
bytecode cache, and reports four outcomes, keeping claims about the guard apart
from claims about the run:

- `killed`: a nominated test failed on an assertion in its own body (errors in other
  tests do not disqualify it);
- `survived`: the mutant activated and no test caught it;
- `invalid`: the run graded nothing (absent target, no-op edit, mutant does not compile);
- `inconclusive`: the failure cannot be attributed to the guard (errors, fixtures,
  unrelated tests, red baseline, hang).

```python
from gz_mutation_witness import Mutation, run_mutation_sweep
```

## Reuse a baseline across sweeps

Create one cache for a batch of sequential sweeps over stable test inputs.

```python
from gz_mutation_witness import BaselineCache, run_mutation_sweep

cache = BaselineCache()
run_mutation_sweep(root, source, first_mutations, command, baseline_cache=cache)
run_mutation_sweep(root, source, follow_up_mutations, command, baseline_cache=cache)
```

A baseline is reused when the project, target path, target bytes, and command
match an observation in that cache. Create a fresh cache if other test inputs
change, including other source files, tests, configuration, dependencies,
the environment, executable resolution, or external fixtures. A red baseline
keeps the affected mutants inconclusive. A timed-out baseline is retried on the
next sweep. Omitting the cache runs a fresh baseline each time.

## Provenance

Extracted as-is from [gzkit](https://github.com/tvproductions/gzkit) at commit
`a06a4f36a8e3fc538d8f20b61df91b9bf42d1ee7`: `src/gzkit/mutation_witness.py`, `src/gzkit/executables.py`,
`classify_failure` from `src/gzkit/red_witness.py` and `read_test_observations`
from `src/gzkit/unit_run_provenance.py`, with their tests. Only import paths changed.

## Development

```bash
uv sync --locked
uv run --locked pre-commit run --all-files
```

Run the project verifier and its unittest suite directly with
`uv run --locked gz-starter verify --project .`. For on-demand class cohesion,
run `uv run --locked --group hygiene cohesion -d src`.
