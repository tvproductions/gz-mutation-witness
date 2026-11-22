"""Local execution and the lifetime of an attempt's bytecode cache."""

import locale
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Protocol

from gz_mutation_witness.executables import resolve_argv
from gz_mutation_witness.run_contract import CommandResult, ContainmentError

_SHUTDOWN_TIMEOUT = 5.0


class _CaptureFile(Protocol):
    def fileno(self) -> int: ...

    def seek(self, offset: int, /) -> int: ...

    def read(self, size: int, /) -> bytes: ...


class LocalExecutionSession:
    """Keep the cache until all commands have finished or been stopped."""

    def __init__(
        self, cwd: Path, runner: Callable[[list[str], Path, Path], subprocess.CompletedProcess[str]]
    ) -> None:
        self._cwd = cwd
        self._runner = runner
        self.cache_path = Path(tempfile.mkdtemp())
        self.cleanup_diagnostic = ""

    def __enter__(self) -> LocalExecutionSession:
        return self

    def __exit__(self, exc_type, error, traceback) -> None:
        if isinstance(error, ContainmentError):
            error.add_note(
                f"Bytecode cache retained because shutdown is uncertain: {self.cache_path}"
            )
            return
        try:
            shutil.rmtree(self.cache_path)
        except OSError as cleanup_error:
            self.cleanup_diagnostic = f"Could not remove bytecode cache: {cleanup_error}"
            if error is not None:
                error.add_note(self.cleanup_diagnostic)

    def run(self, command: list[str]) -> CommandResult:
        try:
            result = self._runner(command, self._cwd, self.cache_path)
        except subprocess.TimeoutExpired as error:
            output = []
            for stream in (error.stdout, error.stderr):
                if isinstance(stream, bytes):
                    stream = stream.decode(errors="replace")
                output.append(stream or "")
            return CommandResult(None, "".join(output))
        return CommandResult(result.returncode, (result.stdout or "") + (result.stderr or ""))


if sys.platform != "win32":

    def _stop_process_group(pid: int) -> None:
        with suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGKILL)

    def _wait_for_process_group(pid: int) -> None:
        deadline = time.monotonic() + _SHUTDOWN_TIMEOUT
        while time.monotonic() < deadline:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return
            if sys.platform == "linux" and _only_zombies(pid, Path("/proc")):
                return
            time.sleep(0.01)
        raise TimeoutError(f"Process group {pid} did not exit")


def _only_zombies(group: int, proc: Path) -> bool:
    """A Linux process group can persist after exit while its zombies await reaping."""
    group_id = str(group).encode()
    found = False
    try:
        for entry in proc.iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                stat = (entry / "stat").read_bytes()
            except FileNotFoundError, ProcessLookupError:
                continue
            # The command name in parentheses can itself contain spaces or ')'.
            fields = stat.rpartition(b") ")[2].split()
            if len(fields) < 3:
                return False
            if fields[2] == group_id:
                if fields[0] != b"Z":
                    return False
                found = True
    except OSError:
        return False
    return found


def _capture(
    process: subprocess.Popen[bytes],
    argv: list[str],
    timeout: float,
    stop: Callable[[], None],
    confirm: Callable[[], None],
    stdout_file: _CaptureFile,
    stderr_file: _CaptureFile,
) -> subprocess.CompletedProcess[str]:
    failure: BaseException | None = None
    try:
        process.wait(timeout=timeout)
    except BaseException as error:
        failure = error

    encoding = "utf-8" if sys.flags.utf8_mode else locale.getencoding()
    try:
        stop()
        if failure is not None:
            process.wait(timeout=_SHUTDOWN_TIMEOUT)
        confirm()
    except (OSError, subprocess.TimeoutExpired) as error:
        containment = ContainmentError(f"Could not confirm test process shutdown: {error}")
        if failure is not None:
            containment.add_note(str(failure))
        try:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=_SHUTDOWN_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as direct_error:
            containment.add_note(f"Could not stop the direct child: {direct_error}")
        try:
            partial = _read_output(stdout_file, encoding) + _read_output(stderr_file, encoding)
            if partial:
                containment.add_note(f"Captured output: {partial}")
        except OSError as output_error:
            containment.add_note(f"Could not read the captured output: {output_error}")
        raise containment from error

    stdout = _read_output(stdout_file, encoding)
    stderr = _read_output(stderr_file, encoding)
    if isinstance(failure, subprocess.TimeoutExpired):
        raise subprocess.TimeoutExpired(argv, timeout, output=stdout, stderr=stderr) from failure
    if failure is not None:
        raise failure
    assert process.returncode is not None
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def _read_output(stream: _CaptureFile, encoding: str) -> str:
    # A failed containment check can leave a writer. Read one bounded snapshot.
    size = os.fstat(stream.fileno()).st_size
    stream.seek(0)
    text = stream.read(size).decode(encoding, errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def run_command(
    command: list[str],
    cwd: Path,
    cache_path: Path,
    timeout: float,
    extra_env: dict[str, str] | None = None,
    pythonpath_prefix: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Capture a command and shut down its managed descendants before returning."""
    env = {**os.environ, **(extra_env or {})}
    if pythonpath_prefix:
        inherited = env.get("PYTHONPATH")
        env["PYTHONPATH"] = os.pathsep.join(p for p in (pythonpath_prefix, inherited) if p)
    env["PYTHONPYCACHEPREFIX"] = str(cache_path)
    argv = resolve_argv(command)
    # A descendant can hold its output handles open after the command exits.
    # Regular files let shutdown proceed without waiting on pipe readers.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        if sys.platform == "win32":
            from gz_mutation_witness.windows_job import WindowsJob

            with WindowsJob() as job:
                process = job.start(argv, cwd, env, stdout.fileno(), stderr.fileno())
                return _capture(process, argv, timeout, job.stop, job.confirm, stdout, stderr)

        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        return _capture(
            process,
            argv,
            timeout,
            lambda: _stop_process_group(process.pid),
            lambda: _wait_for_process_group(process.pid),
            stdout,
            stderr,
        )
