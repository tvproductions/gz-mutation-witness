"""Read which tests a verbose unittest run executed and which failed.

Extracted as-is from gzkit.unit_run_provenance (``read_test_observations`` and its helpers).
"""

import re

_RAN_RE = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
# unittest -v writes `test_name (module.Class.test_name) ... FAIL` and a
# `FAIL: test_name (...)` block; the summary line is the reliable one to read.
_TEST_LINE = re.compile(r"^\s*(\w+) \(([^)]+)\)(?: \(.*\))? \.\.\. (ok|FAIL|ERROR|skipped.*)$")
_TEST_ID_LINE = re.compile(r"^\s*(\w+) \(([^)]+)\)(?: \(.*\))?$")
_STATUS_TAIL = re.compile(r" \.\.\. (ok|FAIL|ERROR|skipped.*)$")
_INTERRUPTED = re.compile(r"^(.*?) \.\.\. (?!(?:ok|FAIL|ERROR|skipped.*)$)")
_STATUS_ALONE = re.compile(r"^(ok|FAIL|ERROR|skipped.*)$")
_FAILURE_LINE = re.compile(r"^(FAIL|ERROR): (\w+) \(([^)]+)\)")
_BLOCK_END = re.compile(r"^(?:={70}|Ran \d+ tests? in )")


def _test_id(method: str, context: str) -> str:
    """Normalize the two stdlib unittest identity display formats."""
    return context if context.endswith("." + method) else f"{context}.{method}"


def _one_line_descriptions(output: str) -> list[str]:
    """Fold unittest's TWO-line verbose description back into the one-line form.

    ``TextTestResult.getDescription`` joins ``str(test)`` and the docstring's
    first line with a newline whenever the test is documented, so the trailing
    ``... ok`` lands on the SECOND line and a parser keyed to the one-line form
    sees no result at all -- a green baseline reads red and every mutation is
    graded ``inconclusive`` (GHI #986). Undocumented output is returned
    unchanged, so the one-line form keeps its existing behaviour exactly.

    Returns:
        The output's lines with each two-line test description folded onto one line ending "...
        <status>"; other lines unchanged.

    """
    lines = output.splitlines()
    folded: list[str] = []
    index = 0
    while index < len(lines):
        following = lines[index + 1] if index + 1 < len(lines) else ""
        status = _STATUS_TAIL.search(following) if _TEST_ID_LINE.match(lines[index]) else None
        if status:
            folded.append(f"{lines[index]} ... {status.group(1)}")
            index += 2
            continue
        if interrupted := _interrupted(lines, index):
            line, end = interrupted
            folded.append(line)
            folded.extend(lines[index:end])
            index = end + 1
            continue
        folded.append(lines[index])
        index += 1
    return folded


def _interrupted(lines: list[str], index: int) -> tuple[str, int] | None:
    """Fold a result the test's own output interrupted, as one line ending "... <status>".

    The verbose result line goes to stderr, where the code under test writes too, so a
    test that announces something lands its text after `` ... `` and its status alone
    on a later line. Read from *index*: the test's identity (one line, or two with a
    docstring), then the first line that is a status alone, before the next test.

    Returns:
        The folded line and the index of its status line, or None.

    """
    head = lines[index]
    if not _TEST_ID_LINE.match(head.split(" ... ", 1)[0]):
        return None
    dots = index if " ... " in head else index + 1
    if dots >= len(lines) or not _INTERRUPTED.match(lines[dots]):
        return None
    identity = head.split(" ... ", 1)[0]
    for end in range(dots + 1, len(lines)):
        if _TEST_ID_LINE.match(lines[end].split(" ... ", 1)[0]):
            return None
        if status := _STATUS_ALONE.match(lines[end]):
            return f"{identity} ... {status.group(1)}", end
    return None


def read_test_observations(output: str) -> tuple[set[str], list[str], int]:
    """Read completed, non-skipped unittest IDs and failure identities.

    Unknown/custom runner output is inconclusive. This parses execution reports;
    it does not decide whether an assertion expresses the intended requirement.

    Returns:
        The executed (non-skipped or failed) test IDs, the failed test IDs in first-seen order
        without repeats, and the Ran count, which is 0 unless the output holds exactly one Ran
        summary.

    """
    executed: set[str] = set()
    failures: list[str] = []
    for line in _one_line_descriptions(output):
        if match := _TEST_LINE.match(line):
            method, context, status = match.groups()
            if not status.startswith("skipped"):
                executed.add(_test_id(method, context))
        if match := _FAILURE_LINE.match(line):
            _, method, context = match.groups()
            identity = _test_id(method, context)
            executed.add(identity)
            if identity not in failures:
                failures.append(identity)
    summaries = _RAN_RE.findall(output)
    count = int(summaries[0]) if len(summaries) == 1 else 0
    return executed, failures, count


def read_failure_blocks(output: str) -> dict[str, tuple[str, str]]:
    """Read each failed test's own report: its kind and the text of its block.

    unittest prints one block per failed test, headed ``FAIL: name (context)`` or
    ``ERROR: name (context)`` and ending at the next ``=`` separator or the ``Ran``
    summary. A test reported more than once (subtests) keeps ``FAIL`` if any of its
    blocks is an assertion failure, and the blocks' text is joined.

    Returns:
        Each failed test's ID mapped to ``("FAIL" | "ERROR", block text)``.

    """
    blocks: dict[str, tuple[str, str]] = {}
    current: str | None = None
    lines: list[str] = []

    def close() -> None:
        if current is None:
            return
        kind, text = blocks[current]
        blocks[current] = (kind, text + "\n".join(lines) + "\n")

    for line in output.splitlines():
        if match := _FAILURE_LINE.match(line):
            close()
            kind, method, context = match.groups()
            current, lines = _test_id(method, context), []
            previous = blocks.get(current)
            merged = "FAIL" if kind == "FAIL" or (previous and previous[0] == "FAIL") else "ERROR"
            blocks[current] = (merged, previous[1] if previous else "")
            continue
        if current is not None and _BLOCK_END.match(line):
            close()
            current, lines = None, []
            continue
        if current is not None:
            lines.append(line)
    close()
    return blocks
