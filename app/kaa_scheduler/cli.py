"""CLI entry point for the scheduler package."""

import argparse
from typing import Optional, Sequence

from kaa_scheduler.config import build_default_config
from kaa_scheduler.models import RunOptions
from kaa_scheduler.scheduler import Scheduler
from kaa_scheduler.infra.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""

    parser = argparse.ArgumentParser(prog="kaa-scheduler", description="UU + kaa daily scheduler")
    subparsers = parser.add_subparsers(dest="command")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true", help="Run without launching or clicking external apps")
    common.add_argument("--timeout", type=int, default=None, help="Override the default timeout in seconds")
    common.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logger verbosity",
    )

    subparsers.add_parser("run", parents=[common], help="Run the full scheduler flow")
    subparsers.add_parser("probe-uu", parents=[common], help="Probe UU launch and window attach only")
    subparsers.add_parser("probe-kaa", parents=[common], help="Probe kaa launch and wait only")
    step_parser = subparsers.add_parser("step", parents=[common], help="Run a single scheduler step")
    step_parser.add_argument("step_name", help="Step name such as uu.ensure_target_accelerating or kaa.launch")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse CLI arguments and run the requested command."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.command:
        parser.print_help()
        return 0

    if args.timeout is not None and args.timeout <= 0:
        parser.error("--timeout must be a positive integer")

    config = build_default_config()
    logger, _run_id = configure_logging(config, args.log_level)

    options = RunOptions(
        command=args.command,
        timeout_seconds=args.timeout or config.default_timeout_seconds,
        log_level=args.log_level,
        dry_run=args.dry_run,
        step_name=getattr(args, "step_name", None),
    )

    scheduler = Scheduler(config, logger)
    result = scheduler.run(options)
    logger.info(
        "Command finished: command=%s success=%s exit_code=%s message=%s",
        result.command,
        result.success,
        result.exit_code,
        result.message,
    )
    return result.exit_code
