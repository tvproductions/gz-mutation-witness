"""Windows process containment behind the local execution adapter."""

import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from gz_mutation_witness.run_contract import ContainmentError

if sys.platform == "win32":
    from ctypes import WinDLL, WinError

    _kernel = WinDLL("kernel32", use_last_error=True)

_CREATE_SUSPENDED = 0x00000004
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100
_THREAD_SUSPEND_RESUME = 0x0002
_SNAPSHOT_THREADS = 0x00000004
_JOB_BASIC_ACCOUNTING = 1
_JOB_EXTENDED_LIMITS = 9
_KILL_ON_JOB_CLOSE = 0x00002000
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_SHUTDOWN_TIMEOUT = 5.0


class _ThreadEntry(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("usage", wintypes.DWORD),
        ("thread_id", wintypes.DWORD),
        ("owner_pid", wintypes.DWORD),
        ("base_priority", wintypes.LONG),
        ("delta_priority", wintypes.LONG),
        ("flags", wintypes.DWORD),
    ]


class _JobAccounting(ctypes.Structure):
    _fields_ = [
        ("total_user_time", ctypes.c_longlong),
        ("total_kernel_time", ctypes.c_longlong),
        ("period_user_time", ctypes.c_longlong),
        ("period_kernel_time", ctypes.c_longlong),
        ("page_faults", wintypes.DWORD),
        ("total_processes", wintypes.DWORD),
        ("active_processes", wintypes.DWORD),
        ("terminated_processes", wintypes.DWORD),
    ]


class _BasicJobLimits(ctypes.Structure):
    _fields_ = [
        ("process_time_limit", ctypes.c_longlong),
        ("job_time_limit", ctypes.c_longlong),
        ("flags", wintypes.DWORD),
        ("minimum_working_set", ctypes.c_size_t),
        ("maximum_working_set", ctypes.c_size_t),
        ("active_process_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority_class", wintypes.DWORD),
        ("scheduling_class", wintypes.DWORD),
    ]


class _ExtendedJobLimits(ctypes.Structure):
    _fields_ = [
        ("basic", _BasicJobLimits),
        ("io_counters", ctypes.c_uint64 * 6),
        ("process_memory_limit", ctypes.c_size_t),
        ("job_memory_limit", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


if sys.platform == "win32":
    _kernel.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    _kernel.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel.OpenProcess.restype = wintypes.HANDLE
    _kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    _kernel.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    _kernel.SetInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    _kernel.QueryInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
    )
    _kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    _kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel.Thread32First.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ThreadEntry))
    _kernel.Thread32Next.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ThreadEntry))
    _kernel.OpenThread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel.OpenThread.restype = wintypes.HANDLE
    _kernel.ResumeThread.argtypes = (wintypes.HANDLE,)
    _kernel.ResumeThread.restype = wintypes.DWORD
    _kernel.CloseHandle.argtypes = (wintypes.HANDLE,)


def _initial_thread(pid: int) -> int:
    """Find the initial thread of a process that has never been resumed."""
    snapshot = _kernel.CreateToolhelp32Snapshot(_SNAPSHOT_THREADS, 0)
    if snapshot == _INVALID_HANDLE:
        raise WinError(ctypes.get_last_error())
    try:
        entry = _ThreadEntry()
        entry.size = ctypes.sizeof(entry)
        available = _kernel.Thread32First(snapshot, ctypes.byref(entry))
        while available:
            if entry.owner_pid == pid:
                return entry.thread_id
            entry.size = ctypes.sizeof(entry)
            available = _kernel.Thread32Next(snapshot, ctypes.byref(entry))
        raise OSError(f"Could not find the initial thread of suspended process {pid}")
    finally:
        _kernel.CloseHandle(snapshot)


class WindowsJob:
    """Start a command in a job before it can spawn any children."""

    _handle: int

    def __enter__(self) -> WindowsJob:
        self._handle = _kernel.CreateJobObjectW(None, None)
        if not self._handle:
            error = WinError(ctypes.get_last_error())
            raise ContainmentError(f"Could not create the Windows test job: {error}") from error
        limits = _ExtendedJobLimits()
        limits.basic.flags = _KILL_ON_JOB_CLOSE
        if not _kernel.SetInformationJobObject(
            self._handle,
            _JOB_EXTENDED_LIMITS,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            error = WinError(ctypes.get_last_error())
            _kernel.CloseHandle(self._handle)
            raise ContainmentError(f"Could not configure the Windows test job: {error}") from error
        return self

    def __exit__(self, exc_type, error, traceback) -> None:
        _kernel.CloseHandle(self._handle)

    def start(
        self,
        argv: list[str],
        cwd: Path,
        env: dict[str, str],
        stdout: int,
        stderr: int,
    ) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdout=stdout,
            stderr=stderr,
            creationflags=_CREATE_SUSPENDED,
        )
        try:
            self._attach(process.pid)
            return process
        except BaseException as error:
            containment = ContainmentError(f"Could not start test process in its job: {error}")
            try:
                self.stop()
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=_SHUTDOWN_TIMEOUT)
                self.confirm()
            except (OSError, subprocess.TimeoutExpired) as shutdown_error:
                containment.add_note(f"Could not stop the suspended process: {shutdown_error}")
                raise containment from error
            if not isinstance(error, Exception):
                raise
            raise containment from error

    def _attach(self, pid: int) -> None:
        process_handle = _kernel.OpenProcess(_PROCESS_TERMINATE | _PROCESS_SET_QUOTA, False, pid)
        if not process_handle:
            raise WinError(ctypes.get_last_error())
        try:
            if not _kernel.AssignProcessToJobObject(self._handle, process_handle):
                raise WinError(ctypes.get_last_error())
            thread = _kernel.OpenThread(_THREAD_SUSPEND_RESUME, False, _initial_thread(pid))
            if not thread:
                raise WinError(ctypes.get_last_error())
            try:
                if _kernel.ResumeThread(thread) == 0xFFFFFFFF:
                    raise WinError(ctypes.get_last_error())
            finally:
                _kernel.CloseHandle(thread)
        finally:
            _kernel.CloseHandle(process_handle)

    def _active_processes(self) -> int:
        data = _JobAccounting()
        if not _kernel.QueryInformationJobObject(
            self._handle,
            _JOB_BASIC_ACCOUNTING,
            ctypes.byref(data),
            ctypes.sizeof(data),
            None,
        ):
            raise WinError(ctypes.get_last_error())
        return data.active_processes

    def stop(self) -> None:
        if self._active_processes() and not _kernel.TerminateJobObject(self._handle, 1):
            raise WinError(ctypes.get_last_error())

    def confirm(self) -> None:
        deadline = time.monotonic() + _SHUTDOWN_TIMEOUT
        while self._active_processes():
            if time.monotonic() >= deadline:
                raise TimeoutError("Windows test job still contains active processes")
            time.sleep(0.01)
