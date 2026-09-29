"""Measure what a generated file costs: compile its implementation for a
target and read the object's section sizes (spec §7.1, per-object part).

Each :class:`Target` is a compiler and its target flags. The implementation
is compiled on its own (``-c``, freestanding, ``-Os``, one section per
function and per table, no unwind tables) and ``llvm-readobj --sections``
reads the object. Sections are classified by their ELF flags, not their
names, so everything that would occupy target memory is counted whatever it
is called:

- ``text``: ``SHF_ALLOC`` and ``SHF_EXECINSTR``, the code;
- ``rodata``: every other ``SHF_ALLOC`` section that is not writable: tables
  and strings, and anything else that lands in flash (``.ARM.exidx``, which
  clang emits for Arm even without unwind tables, ``.srodata``, ...);
- ``data``: ``SHF_ALLOC`` and ``SHF_WRITE``, with contents;
- ``bss``: ``SHF_ALLOC`` and ``SHF_WRITE``, ``SHT_NOBITS``.

The flash cost is ``total = text + rodata``: every allocated, non-writable
section. Sections that are not allocated (symbols, relocations, notes,
attributes) occupy no target memory and are not recorded. The library has
no writable static data, so :func:`measure` refuses an object with a
non-empty ``data`` or ``bss``; and it links nothing (no libc, no compiler
helper), so :func:`measure` also refuses an object with an undefined symbol
(``llvm-nm -u``), for every measured target.

The committed record of these numbers is :mod:`uspiflash.ledger`'s."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from spiflash.enums import FlashType

from . import emit
from .levels import ChipFilter, Selection
from .provenance import Config

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

#: Flags every target compiles with: the project's warnings, and what an
#: embedded build that cares about size uses.
FLAGS = (
    "-std=c99",
    "-Os",
    "-ffreestanding",
    "-fno-common",
    "-ffunction-sections",
    "-fdata-sections",
    "-fno-unwind-tables",
    "-fno-asynchronous-unwind-tables",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Wundef",
    "-Werror",
)

#: The tool that reads section sizes and flags (LLVM's reads every target's
#: objects), and each tool's Debian package.
SIZE_TOOL = "llvm-readobj"
#: The tool that lists an object's undefined symbols (LLVM's reads every
#: target's objects).
NM_TOOL = "llvm-nm"
_PACKAGES = {"clang": "clang", "gcc": "gcc", "llvm-readobj": "llvm", "llvm-nm": "llvm"}
KINDS = ("text", "rodata", "data", "bss")
_SHF_WRITE, _SHF_ALLOC, _SHF_EXECINSTR = 0x1, 0x2, 0x4
_SHT_NOBITS = 8


class MeasureError(Exception):
    """A measurement could not be made: a tool is missing, the compiler
    failed, or the object breaks the library's invariants."""


@dataclass(frozen=True)
class Target:
    """A compiler and the flags that select its target."""

    name: str
    compiler: str
    target_flags: tuple[str, ...] = ()

    @property
    def flags(self) -> tuple[str, ...]:
        """Every flag after the compiler's name."""
        return (*self.target_flags, *FLAGS)


#: The measured targets.
TARGETS: tuple[Target, ...] = (
    Target("cortex-m0", "clang", ("--target=thumbv6m-none-eabi", "-mcpu=cortex-m0", "-mthumb")),
    Target("rv32imc", "clang", ("--target=riscv32-unknown-elf", "-march=rv32imc", "-mabi=ilp32")),
    Target("x86_64", "gcc"),
)


def _config(
    level: str,
    with_: Iterable[str] = (),
    types: tuple[FlashType, ...] = (),
    without: Iterable[str] = (),
) -> Config:
    return Config(
        Selection.make(level, with_=with_, without=without, chips=ChipFilter(types=types))
    )


_NOR = (FlashType.NOR,)
_NAND = (FlashType.NAND,)

#: The measured configurations, by stable name (default prefix and file
#: name). SPI NOR is the primary target (and ``uspiflash generate``'s
#: default), so its builds (``--type nor``) come first, at every level; the
#: all-types (the library's default, ``ChipFilter()``) and NAND-only builds
#: follow for comparison.
CONFIGS: tuple[tuple[str, Config], ...] = (
    ("id:nor", _config("id", types=_NOR)),
    ("read:nor", _config("read", types=_NOR)),
    ("write:nor", _config("write", types=_NOR)),
    ("describe:nor", _config("describe", types=_NOR)),
    ("full:nor", _config("full", types=_NOR)),
    ("id+sfdp:nor", _config("id", ["sfdp"], types=_NOR)),
    ("read+sfdp:nor", _config("read", ["sfdp"], types=_NOR)),
    ("full-sfdp_summary:nor", _config("full", types=_NOR, without=["sfdp_summary"])),
    ("full+sfdp_dumps:nor", _config("full", ["sfdp_dumps"], types=_NOR)),
    ("id", _config("id")),
    ("read", _config("read")),
    ("write", _config("write")),
    ("describe", _config("describe")),
    ("full", _config("full")),
    ("full+datasheet", _config("full", ["datasheet"])),
    ("full+datasheets", _config("full", ["datasheets"])),
    ("full+records+provenance+jep106", _config("full", ["records", "provenance", "jep106"])),
    ("full+sfdp+sfdp_dumps", _config("full", ["sfdp", "sfdp_dumps"])),
    ("read:nand", _config("read", types=_NAND)),
    ("full:nand", _config("full", types=_NAND)),
)


def kind(flags: int, sh_type: int) -> str | None:
    """Which of :data:`KINDS` a section with ELF ``flags`` and type
    ``sh_type`` counts towards, or ``None`` if it is not allocated."""
    if not flags & _SHF_ALLOC:
        return None
    if flags & _SHF_WRITE:
        return "bss" if sh_type == _SHT_NOBITS else "data"
    return "text" if flags & _SHF_EXECINSTR else "rodata"


@dataclass(frozen=True)
class Sizes:
    """One object's allocated sections, by kind (one of :data:`KINDS`),
    then name, in bytes."""

    sections: Mapping[str, Mapping[str, int]]

    def _sum(self, k: str) -> int:
        return sum(self.sections.get(k, {}).values())

    @property
    def text(self) -> int:
        """Code: allocated, executable sections."""
        return self._sum("text")

    @property
    def rodata(self) -> int:
        """Every other allocated, non-writable section."""
        return self._sum("rodata")

    @property
    def data(self) -> int:
        """Allocated, writable sections with contents."""
        return self._sum("data")

    @property
    def bss(self) -> int:
        """Allocated, writable sections without contents."""
        return self._sum("bss")

    @property
    def total(self) -> int:
        """What the object puts in flash: every allocated, non-writable
        section (``text + rodata``; ``data`` is 0, as :func:`measure` checks)."""
        return self.text + self.rodata

    def to_json(self) -> dict[str, object]:
        """The sums, and every allocated section by kind."""
        return {
            "text": self.text,
            "rodata": self.rodata,
            "data": self.data,
            "bss": self.bss,
            "total": self.total,
            "sections": {k: dict(v) for k, v in self.sections.items() if v},
        }


def find_tool(name: str) -> str | None:
    """``name`` on ``PATH``, else the highest-numbered ``name-NN`` there
    (Debian installs ``clang-19`` and ``llvm-readobj-19`` without the plain
    names); ``None`` if neither exists."""
    if found := shutil.which(name):
        return found
    rx = re.compile(re.escape(name) + r"-(\d+)")
    best: tuple[int, str] | None = None
    for d in os.get_exec_path():
        p = Path(d)
        if not p.is_dir():
            continue
        for f in p.iterdir():
            m = rx.fullmatch(f.name)
            if m and os.access(f, os.X_OK) and (best is None or int(m[1]) > best[0]):
                best = (int(m[1]), str(f))
    return best[1] if best else None


def tool(name: str) -> str:
    """:func:`find_tool`, or a :class:`MeasureError` naming the package to install."""
    found = find_tool(name)
    if found is None:
        msg = f"{name} not found on PATH (install {_PACKAGES.get(name, name)})"
        raise MeasureError(msg)
    return found


def version(name: str) -> str:
    """The version line of tool ``name``'s ``--version``: the first line
    containing ``version`` (clang's and LLVM's), else the first line
    (gcc's). It names the build exactly, e.g. ``Debian clang version 19.1.7
    (3+b1)``."""
    res = subprocess.run([tool(name), "--version"], capture_output=True, text=True, check=False)
    lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    if res.returncode != 0 or not lines:
        msg = f"{name} --version failed:\n{res.stderr}"
        raise MeasureError(msg)
    return next((line for line in lines if re.search(r"\bversion\b", line)), lines[0])


def section_sizes(obj: Path) -> Sizes:
    """``obj``'s allocated sections, classified by their flags
    (``llvm-readobj --sections``, as JSON)."""
    res = subprocess.run(
        [tool(SIZE_TOOL), "--elf-output-style=JSON", "--sections", str(obj)],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        msg = f"{SIZE_TOOL} --sections {obj} failed:\n{res.stderr}"
        raise MeasureError(msg)
    out: dict[str, dict[str, int]] = {k: {} for k in KINDS}
    for entry in json.loads(res.stdout)[0]["Sections"]:
        sec = entry["Section"]
        k = kind(sec["Flags"]["Value"], sec["Type"]["Value"])
        if k is not None:
            name = sec["Name"]["Name"]
            out[k][name] = out[k].get(name, 0) + sec["Size"]
    return Sizes(out)


def undefined_symbols(obj: Path) -> list[str]:
    """The symbols ``obj`` needs from elsewhere (``llvm-nm -u``)."""
    res = subprocess.run(
        [tool(NM_TOOL), "--undefined-only", "--format=just-symbols", str(obj)],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        msg = f"{NM_TOOL} --undefined-only {obj} failed:\n{res.stderr}"
        raise MeasureError(msg)
    return res.stdout.split()


def compile_command(target: Target, source: Path, obj: Path) -> list[str]:
    """The command that compiles ``source`` to ``obj`` for ``target``."""
    return [tool(target.compiler), *target.flags, "-c", str(source), "-o", str(obj)]


def measure(config: Config, target: Target, workdir: Path) -> Sizes:
    """Generate ``config``'s file in ``workdir``, compile its implementation
    for ``target`` and size the object."""
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / config.filename).write_text(emit.render(config), encoding="ascii")
    source = workdir / "impl.c"
    # As tests/harness.py's impl_source: the implementation, on its own.
    source.write_text(
        f'#define {config.prefix.upper()}_IMPLEMENTATION\n#include "{config.filename}"\n',
        encoding="ascii",
    )
    obj = workdir / f"impl-{target.name}.o"
    cmd = compile_command(target, source, obj)
    res = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=workdir)
    if res.returncode != 0 or res.stderr:
        msg = f"{' '.join(cmd)} failed:\n{res.stderr}"
        raise MeasureError(msg)
    sizes = section_sizes(obj)
    if sizes.data or sizes.bss:
        msg = (
            f"{target.name}: the library has writable static data "
            f"(data {sizes.data}, bss {sizes.bss} bytes)"
        )
        raise MeasureError(msg)
    if needed := undefined_symbols(obj):
        msg = f"{target.name}: the library needs symbols from elsewhere: {', '.join(needed)}"
        raise MeasureError(msg)
    return sizes
