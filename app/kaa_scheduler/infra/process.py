"""Process helpers for GUI apps controlled by the scheduler."""

import csv
import io
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence


def find_processes_by_name(process_name: str) -> List[Dict[str, str]]:
    """Return matching Windows processes using tasklist output."""

    result = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH", "/FI", "IMAGENAME eq " + process_name],
        capture_output=True,
        text=True,
        check=False,
    )
    rows: List[Dict[str, str]] = []
    reader = csv.reader(io.StringIO(result.stdout))
    for row in reader:
        if not row or row[0].startswith("INFO:"):
            continue
        if row[0].lower() != process_name.lower():
            continue
        rows.append(
            {
                "image_name": row[0],
                "pid": row[1],
                "session_name": row[2],
                "session_number": row[3],
                "memory_usage": row[4],
            }
        )
    return rows


def is_process_running(process_name: str) -> bool:
    """Return whether a process with the given image name is running."""

    return bool(find_processes_by_name(process_name))


def launch_process(command: Sequence[str], cwd: Optional[Path] = None) -> subprocess.Popen:
    """Launch a process without involving the shell."""

    normalized = [str(part) for part in command]
    return subprocess.Popen(normalized, cwd=str(cwd) if cwd else None)


def wait_for_process_start(process_name: str, timeout_seconds: int, poll_interval: float = 0.5) -> bool:
    """Poll until the named process appears or the timeout is reached."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_process_running(process_name):
            return True
        time.sleep(poll_interval)
    return False


def wait_for_process_exit(process: subprocess.Popen, timeout_seconds: int) -> int:
    """Wait for a launched process to exit and return its exit code."""

    return process.wait(timeout=timeout_seconds)


def list_process_details() -> List[Dict[str, str]]:
    """Return detailed process records from Win32_Process via PowerShell."""

    command = (
        "$items = Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name, ExecutablePath, CommandLine; "
        "$items | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    payload = json.loads(result.stdout)
    if isinstance(payload, dict):
        payload = [payload]

    rows: List[Dict[str, str]] = []
    for item in payload:
        rows.append(
            {
                "pid": str(item.get("ProcessId") or ""),
                "parent_pid": str(item.get("ParentProcessId") or ""),
                "image_name": str(item.get("Name") or ""),
                "executable_path": str(item.get("ExecutablePath") or ""),
                "command_line": str(item.get("CommandLine") or ""),
            }
        )
    return rows
