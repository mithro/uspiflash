"""The size ledger: ``sizes/ledger.json``, every :data:`~uspiflash.measure.CONFIGS`
entry measured on every :data:`~uspiflash.measure.TARGETS` entry, and
``sizes/README.md``, the tables generated from it. The top-level README
quotes two figures from it, between markers that ``--write`` rewrites.

The ledger holds only what determines the numbers: the spiflash version,
each configuration's selection, each tool's version line and each target's
flags. It has no timestamp, host name or uspiflash version, so measuring the
same inputs with the same tools writes the same bytes, and
``uspiflash measure --check`` can compare a fresh measurement with the
committed one byte for byte.

Tool versions come first: the numbers are only reproducible with the tools
that made them, so :func:`check` compares the installed tools' version lines
with the ledger's before measuring, and a mismatch means "regenerate in the
pinned environment", not "the code changed".

Format 1 is one compiler per target. Spec §7.2-7.3's compiler x libc matrix
(M2) adds targets named for their compiler, and rows per commit."""

from __future__ import annotations

import difflib
import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import spiflash
from spiflash.db import FORMAT as DB_FORMAT

from . import measure

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .measure import Target
    from .provenance import Config

FORMAT = 1
LEDGER = Path("sizes/ledger.json")
README = Path("sizes/README.md")
TOP_README = Path("README.md")
#: The lines around the top-level README's size figures.
BEGIN = "<!-- sizes: generated from sizes/ledger.json by `uspiflash measure --write` -->"
END = "<!-- sizes: end -->"
REGENERATE = "uv run python -m uspiflash.sandbox -- uv run uspiflash measure --write"
#: The container image the ledger is made and checked in: Debian trixie for
#: linux/amd64, pinned by digest. CI's ``sizes`` job runs in exactly this
#: image (a test checks), and the ledger records it, so changing the pin
#: makes ``--check`` fail until the ledger is regenerated in the new image.
#: RELEASING.md says how to bump it.
IMAGE = "debian:trixie@sha256:d5ce19d4736f0ebbacd686d1040271a5aeb0cc920f5990c1bfae1717627f0674"
#: The Debian packages the image needs for :data:`~uspiflash.measure.TARGETS`.
PACKAGES = ("clang-19", "llvm-19", "gcc", "libc6-dev")
_REPO = "https://github.com/mithro/uspiflash/blob/main"
_STATS = "2026-09-28-database-statistics"


def _options(config: Config) -> list[str]:
    """``config``'s ``uspiflash generate`` options, without the default
    output file and prefix (every measured configuration uses those)."""
    args = config.args()
    out: list[str] = []
    for key, value in zip(args[::2], args[1::2], strict=True):
        if (key, value) not in {("-o", "uspiflash.h"), ("--prefix", "usf")}:
            out += [key, value]
    return out


def tools(targets: Sequence[Target]) -> list[str]:
    """Every tool measuring ``targets`` needs, sorted."""
    return sorted({t.compiler for t in targets} | {measure.SIZE_TOOL})


def build(
    workdir: Path,
    configs: Sequence[tuple[str, Config]] | None = None,
    targets: Sequence[Target] | None = None,
) -> dict[str, Any]:
    """Measure every configuration on every target (by default,
    :data:`~uspiflash.measure.CONFIGS` and :data:`~uspiflash.measure.TARGETS`),
    with scratch files in ``workdir``."""
    configs = measure.CONFIGS if configs is None else configs
    targets = measure.TARGETS if targets is None else targets
    versions = {name: measure.version(name) for name in tools(targets)}
    sizes = {
        t.name: {
            name: measure.measure(config, t, workdir / t.name / name).to_json()
            for name, config in configs
        }
        for t in targets
    }
    return {
        "format": FORMAT,
        "environment": {"image": IMAGE, "packages": list(PACKAGES)},
        "spiflash": {"version": spiflash.__version__, "database_format": DB_FORMAT},
        "tools": versions,
        "configs": [
            {"name": name, "options": _options(config), "config": config.to_json()}
            for name, config in configs
        ],
        "targets": [
            {"name": t.name, "compiler": t.compiler, "flags": list(t.flags)} for t in targets
        ],
        "sizes": sizes,
    }


def dumps(ledger: dict[str, Any]) -> str:
    """The ledger's file content: sorted keys, indent 1, a final newline."""
    return json.dumps(ledger, sort_keys=True, indent=1) + "\n"


def _table(ledger: dict[str, Any], target: str) -> list[str]:
    rows = ["| Configuration | text | rodata | total |", "|---|--:|--:|--:|"]
    for c in ledger["configs"]:
        s = ledger["sizes"][target][c["name"]]
        rows.append(f"| `{c['name']}` | {s['text']:,} | {s['rodata']:,} | **{s['total']:,}** |")
    return rows


def tables(ledger: dict[str, Any]) -> str:
    """One Markdown table per target (what ``uspiflash measure`` prints)."""
    out: list[str] = []
    for t in ledger["targets"]:
        cmd = " ".join([t["compiler"], *t["flags"], "-c"])
        out += [
            f"## {t['name']}",
            "",
            f"{ledger['tools'][t['compiler']]}: `{cmd}`",
            "",
            *_table(ledger, t["name"]),
            "",
        ]
    return "\n".join(out)


def readme(ledger: dict[str, Any]) -> str:
    """``sizes/README.md``, generated from ``ledger``."""
    sf = ledger["spiflash"]
    env = ledger["environment"]
    lines = [
        "# Sizes",
        "",
        "<!-- Generated from ledger.json by `uspiflash measure --write`: do not edit. -->",
        "",
        "What the generated library costs in flash, in bytes, for each configuration",
        "and target. Each configuration's header is generated with the default prefix,",
        "its implementation compiled on its own (`-c`, no unwind tables), and the",
        "object's sections read with `llvm-readobj --sections`. Sections count by",
        "their ELF flags, not their names: **text** is every allocated, executable",
        "section (code); **rodata** is every other allocated, read-only one (tables",
        "and strings, plus anything else that lands in flash, such as the",
        "`.ARM.exidx` entries clang emits for Arm even without unwind tables); and",
        "**total** is text + rodata, everything the object puts in flash. Every",
        "object has no allocated writable section (data and bss are 0; the",
        "measurement refuses otherwise), so the library needs no RAM beyond its",
        "stack. Linking can add compiler helpers and alignment. `ledger.json` lists",
        "every allocated section of every object.",
        "",
        f"Measured against spiflash {sf['version']} (database format {sf['database_format']}).",
        "These are compiled objects; the",
        f"[database-statistics experiment]({_REPO}/experiments/{_STATS}/README.md)",
        "counts the raw table bytes before compiling.",
        "",
        "## Configurations",
        "",
        "| Configuration | `uspiflash generate` options |",
        "|---|---|",
        *(f"| `{c['name']}` | `{' '.join(c['options'])}` |" for c in ledger["configs"]),
        "",
        tables(ledger),
        "## Regenerate",
        "",
        "Tools:",
        "",
        *(f"- `{name}`: {v}" for name, v in sorted(ledger["tools"].items())),
        "",
        f"These are the Debian packages {', '.join(f'`{p}`' for p in env['packages'])}",
        f"in `{env['image']}`, the image CI's `sizes` job checks the ledger in. On a",
        "machine with the same versions, regenerate with:",
        "",
        "```sh",
        REGENERATE,
        "```",
        "",
        "`uv run uspiflash measure --check` exits 1 when this ledger is stale, and 2",
        "when the installed tools differ from the ones above. The image changes only",
        "deliberately: a new digest and a ledger regenerated in it, in one commit",
        f"(see [RELEASING.md]({_REPO}/RELEASING.md#the-size-ledgers-image)).",
    ]
    return "\n".join(lines) + "\n"


def tool_mismatches(ledger: dict[str, Any]) -> list[str]:
    """How the installed tools differ from the ones that made ``ledger``,
    one line per tool (empty when they are the same)."""
    out = []
    for name, want in sorted(ledger["tools"].items()):
        have = measure.version(name)
        if have != want:
            out.append(f"{name}: the ledger has {want!r}, installed is {have!r}")
    return out


def summary(ledger: dict[str, Any]) -> str:
    """The headline figures the top-level README quotes: ``read`` and
    ``full`` on the first target (Cortex-M0)."""
    t = ledger["targets"][0]
    sizes = ledger["sizes"][t["name"]]
    return "\n".join(
        [
            f"Compiled for `{t['name']}` with {ledger['tools'][t['compiler']]} at `-Os`,",
            f"the `read` level costs **{sizes['read']['total']:,} bytes** of flash and `full`",
            f"**{sizes['full']['total']:,} bytes**, code and tables together, with no static RAM.",
            "Every configuration and target, and how they are measured:",
            f"[`sizes/README.md`]({_REPO}/sizes/README.md).",
        ]
    )


def splice(text: str, ledger: dict[str, Any]) -> str:
    """``text`` (the top-level README) with the lines between its
    :data:`BEGIN` and :data:`END` markers replaced by :func:`summary`."""
    head, begin, rest = text.partition(BEGIN + "\n")
    _, end, tail = rest.partition(END + "\n")
    if not (begin and end):
        msg = f"{TOP_README} has no {BEGIN} ... {END} lines to put the sizes between"
        raise ValueError(msg)
    return f"{head}{BEGIN}\n{summary(ledger)}\n{END}\n{tail}"


def files(ledger: dict[str, Any], root: Path) -> dict[Path, str]:
    """Every file generated from ``ledger``, by path from the repository
    ``root``: the ledger, its README, and the top-level README's size
    figures (when ``root`` has a README)."""
    out = {LEDGER: dumps(ledger), README: readme(ledger)}
    top = root / TOP_README
    if top.is_file():
        out[TOP_README] = splice(top.read_text(encoding="utf-8"), ledger)
    return out


def write(root: Path, ledger: dict[str, Any]) -> None:
    """Write every file generated from ``ledger`` under ``root``."""
    for path, text in files(ledger, root).items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")


def diff(root: Path, ledger: dict[str, Any]) -> str:
    """A unified diff from the committed files to those ``ledger`` generates
    (empty when they match)."""
    out: list[str] = []
    for path, want in files(ledger, root).items():
        p = root / path
        have = p.read_text(encoding="utf-8") if p.is_file() else ""
        out += difflib.unified_diff(
            have.splitlines(keepends=True),
            want.splitlines(keepends=True),
            f"{path} (committed)",
            f"{path} (measured)",
        )
    return "".join(out)


def committed(root: Path) -> dict[str, Any] | None:
    """The committed ledger under ``root``, or ``None`` if there is none."""
    p = root / LEDGER
    if not p.is_file():
        return None
    data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    return data


def measure_fresh() -> dict[str, Any]:
    """:func:`build`, with its scratch files in a temporary directory."""
    with tempfile.TemporaryDirectory(prefix="uspiflash-measure-") as d:
        return build(Path(d))
