"""Module entry point for python -m kaa_scheduler."""

import ctypes
import subprocess
import sys


def _restart_as_admin() -> bool:
    """Relaunch the current Python process with administrator privileges.

    Returns True if a new elevated process was started, False otherwise.
    """
    # Can't reliably restart from -c mode (sys.argv is only ['-c'])
    if sys.argv[0] == "-c":
        return False

    # Skip elevation for dry-run since it doesn't interact with windows
    if "--dry-run" in sys.argv:
        return False

    # Rebuild the command-line arguments using Windows quoting rules.
    params = subprocess.list2cmdline(sys.argv[1:])

    print("[kaa-scheduler] Not running as administrator. Requesting elevation...", flush=True)

    # ShellExecuteW with "runas" triggers the UAC elevation prompt.
    result = ctypes.windll.shell32.ShellExecuteW(
        None,        # hwnd
        "runas",     # lpVerb
        sys.executable,  # lpFile
        params,      # lpParameters
        None,        # lpDirectory
        1,           # nShowCmd (SW_SHOWNORMAL)
    )
    # ShellExecuteW returns an HINSTANCE; > 32 means success.
    return result > 32


if __name__ == "__main__":
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False

    if not is_admin:
        if _restart_as_admin():
            sys.exit(0)  # Successfully elevated; let the new process take over.
        # Fall through: couldn't restart (e.g. -c mode). cli.py will print a warning.

    from kaa_scheduler.cli import main

    raise SystemExit(main())
