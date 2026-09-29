"""The ``uspiflash`` command. Subcommands are added by later modules:
``generate`` and ``check`` (the C file), ``research`` (experiments) and
``measure`` (the size ledger)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import spiflash
from spiflash.enums import FlashType, IdFamily

from . import __version__, emit, ledger, research
from .levels import LEVELS, ChipFilter, Field, Selection
from .measure import MeasureError
from .model import FAMILIES
from .provenance import Config

if TYPE_CHECKING:
    from collections.abc import Sequence


def _generate_options(ap: argparse.ArgumentParser) -> None:
    """The options of ``generate``, shared with :func:`config_from_args`."""
    fields = [f.value for f in Field]
    ap.add_argument(
        "-o",
        "--output",
        default="uspiflash.h",
        metavar="PATH",
        help="the file to write, or - for standard output (default: uspiflash.h)",
    )
    ap.add_argument("--prefix", default="usf", help="the C symbol prefix (default: usf)")
    ap.add_argument("--level", default="full", choices=list(LEVELS), help="default: full")
    ap.add_argument(
        "--with",
        dest="with_",
        action="append",
        default=[],
        choices=fields,
        metavar="FIELD",
        help="add a field or extra, and what it needs",
    )
    ap.add_argument(
        "--without",
        action="append",
        default=[],
        choices=fields,
        metavar="FIELD",
        help="leave a field out",
    )
    ap.add_argument(
        "--manufacturer",
        action="append",
        default=[],
        metavar="NAME",
        help="keep this manufacturer's chips",
    )
    ap.add_argument(
        "--id",
        dest="ids",
        action="append",
        default=[],
        type=bytes.fromhex,
        metavar="HEX",
        help="keep this chip: matched on the chip id, after stripping 0x7f continuation "
        "codes; extended-id bytes are not part of an id",
    )
    ap.add_argument(
        "--type",
        dest="types",
        action="append",
        default=[],
        choices=[t.value for t in FlashType],
        help="keep chips of this type",
    )
    ap.add_argument(
        "--family",
        dest="families",
        action="append",
        default=[],
        choices=[f.value for f in FAMILIES],
        help="keep chips of this id family",
    )
    ap.add_argument("--min-size", type=int, metavar="BYTES", help="keep chips at least this big")
    ap.add_argument("--max-size", type=int, metavar="BYTES", help="keep chips at most this big")


def _config(args: argparse.Namespace) -> Config:
    chips = ChipFilter(
        manufacturers=tuple(args.manufacturer),
        ids=tuple(args.ids),
        types=tuple(FlashType(t) for t in args.types),
        families=tuple(IdFamily(f) for f in args.families),
        min_size=args.min_size,
        max_size=args.max_size,
    )
    selection = Selection.make(args.level, args.with_, args.without, chips)
    # The file's own name (not its directory) goes in the include guard and
    # the provenance; standard output gets the default name.
    filename = "uspiflash.h" if args.output == "-" else Path(args.output).name
    return Config(selection, args.prefix, filename)


def config_from_args(argv: Sequence[str]) -> Config:
    """The ``generate`` options in ``argv`` as a :class:`~uspiflash.provenance.Config`;
    :meth:`Config.args` produces arguments this accepts."""
    ap = argparse.ArgumentParser(prog="uspiflash generate")
    _generate_options(ap)
    return _config(ap.parse_args(argv))


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

    _generate_options(sub.add_parser("generate", help="write a generated C file"))

    research_ap = sub.add_parser("research", help="reproduce a research experiment")
    research_sub = research_ap.add_subparsers(dest="research_command")
    run_ap = research_sub.add_parser("run", help="run one experiment")
    run_ap.add_argument("slug", help="the experiment's directory name")
    research_sub.add_parser("list", help="list every experiment, oldest first")

    measure_ap = sub.add_parser(
        "measure",
        help="measure the generated library's compiled size",
        description="Compile every measured configuration for every target and print "
        "its size, or write or check the committed ledger (sizes/ in the repository).",
    )
    mode = measure_ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--write",
        action="store_true",
        help="rewrite sizes/ledger.json, sizes/README.md and README.md's size figures",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the committed ledger differs from a fresh measurement, "
        "2 if the installed tools differ from the ledger's",
    )
    measure_ap.add_argument(
        "--root",
        type=Path,
        metavar="DIR",
        help="the repository (default: the nearest directory holding experiments/)",
    )

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


def _check_ledger(root: Path) -> int:
    """``measure --check``: 2 if the tools differ from the ledger's, 1 if a
    fresh measurement differs from the committed files, else 0."""
    old = ledger.committed(root)
    if old is not None:
        mismatches = ledger.tool_mismatches(old)
        if mismatches:
            print(
                "uspiflash: the installed tools differ from the ones that made "
                f"{ledger.LEDGER}:\n"
                + "".join(f"  {m}\n" for m in mismatches)
                + f"Regenerate the ledger with those tools (in {ledger.IMAGE}; "
                "see sizes/README.md), or check it there.",
                file=sys.stderr,
            )
            return 2
    changes = ledger.diff(root, ledger.measure_fresh())
    if changes:
        sys.stdout.write(changes)
        print(
            f"uspiflash: the size ledger is stale; regenerate it with: {ledger.REGENERATE}",
            file=sys.stderr,
        )
        return 1
    print(f"{ledger.LEDGER} is current")
    return 0


def _measure(args: argparse.Namespace) -> int:
    """Print the sizes, or write or check the committed ledger."""
    try:
        if not (args.write or args.check):
            sys.stdout.write(ledger.tables(ledger.measure_fresh()))
            return 0
        root = args.root or research.find_root(Path.cwd())
        if args.check:
            return _check_ledger(root)
        ledger.write(root, ledger.measure_fresh())
    except (MeasureError, FileNotFoundError, ValueError) as e:
        print(f"uspiflash: {e}", file=sys.stderr)
        return 2
    return 0


def _generate(args: argparse.Namespace) -> int:
    """Write the generated file (``-o -``: to standard output)."""
    try:
        text = emit.render(_config(args))
    except ValueError as e:
        print(f"uspiflash: {e}", file=sys.stderr)
        return 2
    if args.output == "-":
        sys.stdout.write(text)
    else:
        with Path(args.output).open("w", encoding="ascii", newline="\n") as f:
            f.write(text)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; the return value is the exit status."""
    args = parser().parse_args(argv)
    if args.command is None:
        parser().print_help()
        return 2
    if args.command == "research":
        return _research(args)
    if args.command == "generate":
        return _generate(args)
    if args.command == "measure":
        return _measure(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
