"""The ``uspiflash`` command. Subcommands are added by later modules:
``generate`` and ``check`` (the C file), and ``research`` (experiments)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import spiflash

from . import __version__, research

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
    sub = ap.add_subparsers(dest="command")

    research_ap = sub.add_parser("research", help="reproduce a research experiment")
    research_sub = research_ap.add_subparsers(dest="research_command")
    run_ap = research_sub.add_parser("run", help="run one experiment")
    run_ap.add_argument("slug", help="the experiment's directory name")
    research_sub.add_parser("list", help="list every experiment, oldest first")

    return ap


def _research(args: argparse.Namespace) -> int:
    """Dispatch ``research run`` and ``research list``."""
    root = research.find_root(Path.cwd())
    if args.research_command == "run":
        if args.slug not in research.slugs(root):
            known = ", ".join(research.slugs(root))
            print(f"uspiflash: no experiment {args.slug!r} (known: {known})", file=sys.stderr)
            return 2
        return research.run(args.slug, root)
    if args.research_command == "list":
        for slug in research.slugs(root):
            print(slug)
        return 0
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; the return value is the exit status."""
    args = parser().parse_args(argv)
    if args.command is None:
        parser().print_help()
        return 2
    if args.command == "research":
        return _research(args)
    return 0
