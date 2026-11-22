"""Execution information consumed by sweep orchestration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    """The command's status and output, or a confirmed timeout."""

    exit_status: int | None
    output: str


class ContainmentError(RuntimeError):
    """The runner could not establish containment or confirm shutdown."""


class ExecutionSession(Protocol):
    """Run the commands for one attempt with a common bytecode cache."""

    @property
    def cache_path(self) -> Path: ...

    def run(self, command: list[str]) -> CommandResult: ...
