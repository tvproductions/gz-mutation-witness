"""Classify a unittest run's failure (extracted as-is from gzkit.red_witness).

``errors`` dominates ``failures``: see :func:`classify_failure`.
"""

import re
from typing import Literal

FailureClass = Literal["assertion", "error", "none", "not-applicable"]

# `FAILED (failures=2, errors=1)` — unittest's own summary line.
_FAILED_SUMMARY_RE = re.compile(r"FAILED\s*\((?P<body>[^)]*)\)")
_FAILURES_RE = re.compile(r"failures=(\d+)")
_ERRORS_RE = re.compile(r"errors=(\d+)")


def classify_failure(exit_status: int, output: str) -> FailureClass:
    """Classify a base-tree test run into its RED failure class.

    ``errors`` dominates ``failures``: a run that raised (ImportError, TypeError)
    failed for the wrong reason even if some other test in the scope failed on an
    assertion. Collapsing the two would launder a weak RED into a strong one — the
    exact equivalence GHI #642 forbids.

    Returns:
        "none" for a zero exit status; "error" when the run reported errors, crashed without a
        unittest summary, or failed without a failure count; "assertion" when it reported failures
        and no errors.

    """
    if exit_status == 0:
        return "none"
    match = _FAILED_SUMMARY_RE.search(output)
    if match is None:
        # Non-zero with no unittest summary: a crash or a collection error. A run that
        # exceeds the hang bound raises before any exit status exists and is voided
        # by the caller.
        return "error"
    body = match.group("body")
    errors = _ERRORS_RE.search(body)
    if errors and int(errors.group(1)) > 0:
        return "error"
    failures = _FAILURES_RE.search(body)
    if failures and int(failures.group(1)) > 0:
        return "assertion"
    return "error"
