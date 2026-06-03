"""Configuration helpers for the scheduler."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    """Resolved configuration for one scheduler run."""

    project_root: Path
    app_root: Path
    logs_dir: Path
    scripts_dir: Path
    lock_file: Path
    uu_exe_path: Path
    uu_process_name: str
    uu_window_title: str
    target_game_name: str
    kaa_exe_path: Path
    kaa_process_name: str
    kaa_working_dir: Path
    default_timeout_seconds: int

    def ensure_runtime_dirs(self) -> None:
        """Create runtime directories that must exist before execution."""

        self.logs_dir.mkdir(parents=True, exist_ok=True)


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return default
    return Path(value).expanduser().resolve()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    return int(value)


def build_default_config(project_root: Optional[Path] = None) -> AppConfig:
    """Build the default app configuration for the current repository."""

    if project_root is None:
        project_root = Path(__file__).resolve().parents[2]

    project_root = Path(project_root).resolve()
    app_root = project_root / "app"
    logs_dir = project_root / "logs"
    scripts_dir = project_root / "scripts"
    lock_file = logs_dir / "kaa_scheduler.lock"

    return AppConfig(
        project_root=project_root,
        app_root=app_root,
        logs_dir=logs_dir,
        scripts_dir=scripts_dir,
        lock_file=lock_file,
        uu_exe_path=_env_path(
            "KAA_SCHEDULER_UU_EXE",
            Path(r"C:\Program Files (x86)\Netease\UU\uu_launcher.exe"),
        ),
        uu_process_name=os.getenv("KAA_SCHEDULER_UU_PROCESS", "uu.exe"),
        uu_window_title=os.getenv("KAA_SCHEDULER_UU_WINDOW", "UU加速器"),
        target_game_name=os.getenv("KAA_SCHEDULER_TARGET_GAME", "学园偶像大师"),
        kaa_exe_path=_env_path(
            "KAA_SCHEDULER_KAA_EXE",
            Path(r"D:\Programs\kaa-bootstrap-0.5.1\kaa.exe"),
        ),
        kaa_process_name=os.getenv("KAA_SCHEDULER_KAA_PROCESS", "kaa.exe"),
        kaa_working_dir=_env_path(
            "KAA_SCHEDULER_KAA_WORKDIR",
            Path(r"D:\Programs\kaa-bootstrap-0.5.1"),
        ),
        default_timeout_seconds=_env_int("KAA_SCHEDULER_TIMEOUT", 20 * 60),
    )
