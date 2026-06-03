"""Logging helpers for the scheduler."""

import logging as std_logging
from datetime import datetime
from pathlib import Path
from typing import Tuple

from kaa_scheduler.config import AppConfig


def build_run_id() -> str:
    """Build a timestamp-based run id for the current execution."""

    return datetime.now().strftime("%Y%m%d-%H%M%S")


def configure_logging(config: AppConfig, log_level: str = "INFO") -> Tuple[std_logging.Logger, str]:
    """Configure the project logger and return it with the current run id."""

    config.ensure_runtime_dirs()
    run_id = build_run_id()
    log_file = Path(config.logs_dir) / (run_id + ".log")

    logger = std_logging.getLogger("kaa_scheduler")
    logger.handlers.clear()
    logger.setLevel(getattr(std_logging, log_level.upper(), std_logging.INFO))
    logger.propagate = False

    formatter = std_logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = std_logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = std_logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.debug("Logging configured. run_id=%s log_file=%s", run_id, log_file)
    return logger, run_id
