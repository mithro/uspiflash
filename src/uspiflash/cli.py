"""The ``uspiflash`` command. Subcommands are added by later modules:
``generate`` and ``check`` (the C file), and ``research`` (experiments)."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import spiflash

from . import __version__

if TYPE_CHECKING:
    from collections.abc import Sequence


def parser() -> argparse.ArgumentParser:
    """The command line; each subcommand registers itself here."""
    ap = argparse.ArgumentParser(
        prog="uspiflash",
        description="Generate a single-file C library that detects SPI flash chips.",
    )
    ap.add_argument(
        "--version",
        action="version",
        version=f"uspiflash {__version__} (spiflash {spiflash.__version__})",
    )
    ap.add_subparsers(dest="command")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; the return value is the exit status."""
    args = parser().parse_args(argv)
    if args.command is None:
        parser().print_help()
        return 2
    return 0
