"""Command line interface package for SnipeTrade."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from snipetrade.config import Config

from .scan import add_scan_subparser


def build_parser() -> argparse.ArgumentParser:
    """Build the root argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="snipetrade",
        description="SnipeTrade – modular scanner pipeline",
    )
    parser.add_argument("--version", action="version", version="SnipeTrade 0.1.0")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    add_scan_subparser(subparsers)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for the console script."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    cfg = Config()
    result = args.func(args, cfg)

    if isinstance(result, int):
        return result

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point guard
    sys.exit(main())
