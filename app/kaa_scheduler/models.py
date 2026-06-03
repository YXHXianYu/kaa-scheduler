"""Shared data models for the scheduler."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RunOptions:
    """Runtime options parsed from the command line."""

    command: str
    timeout_seconds: int
    log_level: str
    dry_run: bool = False


@dataclass
class StepResult:
    """Result for a single scheduler step."""

    name: str
    success: bool
    message: str = ""
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    """Final result for one CLI command execution."""

    command: str
    success: bool
    exit_code: int
    message: str
    steps: List[StepResult] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class UuStatus:
    """Snapshot of the current UU state."""

    process_running: bool
    window_attached: bool
    accelerating_target: Optional[bool]
    message: str = ""
    active_game_name: Optional[str] = None


@dataclass
class KaaStatus:
    """Snapshot of the current kaa state."""

    process_running: bool
    pid: Optional[int]
    exit_code: Optional[int] = None
    message: str = ""
