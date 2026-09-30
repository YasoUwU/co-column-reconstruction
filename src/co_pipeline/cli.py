"""Command-line interface shared by humans, CI, and Snakemake."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigurationError, load_config
from .stages import STAGES, run_stage


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, required=True, help="YAML configuration file")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing products")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow provider downloads for commands that support them",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="co-pipeline",
        description="CO total-column reconstruction and validation pipeline",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)
    for stage in STAGES:
        command = commands.add_parser(stage, help=f"Run the {stage} stage")
        _add_common_options(command)
    run = commands.add_parser("run", help="Run the canonical dependency order")
    _add_common_options(run)
    run.add_argument(
        "--from-stage",
        choices=STAGES,
        help="Resume at this stage; prerequisite products must already exist",
    )
    run.add_argument("--until-stage", choices=STAGES, help="Stop after this stage")
    return parser


def _selected_stages(start: str | None, end: str | None) -> tuple[str, ...]:
    start_index = STAGES.index(start) if start else 0
    end_index = STAGES.index(end) + 1 if end else len(STAGES)
    if start_index >= end_index:
        raise ValueError("--from-stage must precede or equal --until-stage")
    return STAGES[start_index:end_index]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        stages = (
            _selected_stages(args.from_stage, args.until_stage)
            if args.command == "run"
            else (args.command,)
        )
        for stage in stages:
            manifest = run_stage(
                stage,
                config,
                overwrite=bool(args.overwrite),
                allow_network=bool(args.allow_network),
            )
            print(f"{stage}: {manifest}")
        return 0
    except (ConfigurationError, FileNotFoundError, PermissionError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
