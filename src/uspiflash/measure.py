"""Measure what a generated file costs: compile its implementation for a
target and read the object's section sizes (spec §7.1, per-object part).

Each :class:`Target` is a compiler and its target flags. The implementation
is compiled on its own (``-c``, freestanding, ``-Os``, one section per
function and per table) and ``llvm-size -A`` reads the object. Sections are
summed into ``text`` (``.text*``), ``rodata`` (``.rodata*``, ``.srodata*``),
``data`` (``.data*``, ``.sdata*``) and ``bss`` (``.bss*``, ``.sbss*``); the
flash cost is ``total = text + rodata + data``. Anything else (unwind tables
such as ``.ARM.exidx`` and ``.eh_frame``, notes, attributes) is kept in
:attr:`Sizes.sections` but counted in none of them.

The library has no writable static data, so :func:`measure` refuses an
object with a non-empty ``data`` or ``bss``.

The committed record of these numbers is :mod:`uspiflash.ledger`'s."""

from __future__ import annotations

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
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Wundef",
    "-Werror",
)

#: The size tool (LLVM's reads every target's objects), and its package.
SIZE_TOOL = "llvm-size"
_PACKAGES = {"clang": "clang", "gcc": "gcc", "llvm-size": "llvm"}


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


def _config(level: str, with_: Iterable[str] = (), types: tuple[FlashType, ...] = ()) -> Config:
    return Config(Selection.make(level, with_=with_, chips=ChipFilter(types=types)))


#: The measured configurations, by stable name (default prefix and file name).
CONFIGS: tuple[tuple[str, Config], ...] = (
    ("id", _config("id")),
    ("read", _config("read")),
    ("write", _config("write")),
    ("describe", _config("describe")),
    ("full", _config("full")),
    ("full+datasheet", _config("full", ["datasheet"])),
    ("full+datasheets", _config("full", ["datasheets"])),
    ("full+records+provenance+jep106", _config("full", ["records", "provenance", "jep106"])),
    ("read:nor", _config("read", types=(FlashType.NOR,))),
    ("read:nand", _config("read", types=(FlashType.NAND,))),
    ("full:nor", _config("full", types=(FlashType.NOR,))),
    ("full:nand", _config("full", types=(FlashType.NAND,))),
)


@dataclass(frozen=True)
class Sizes:
    """One object's section sizes, in bytes."""

    sections: Mapping[str, int]

    def _sum(self, pattern: str) -> int:
        rx = re.compile(pattern)
        return sum(n for s, n in self.sections.items() if rx.fullmatch(s))

    @property
    def text(self) -> int:
        """Code: ``.text`` and ``.text.*``."""
        return self._sum(r"\.text(\..*)?")

    @property
    def rodata(self) -> int:
        """Constant data: ``.rodata*`` and ``.srodata*``."""
        return self._sum(r"\.s?rodata(\..*)?")

    @property
    def data(self) -> int:
        """Initialised writable data: ``.data*`` and ``.sdata*``."""
        return self._sum(r"\.s?data(\..*)?")

    @property
    def bss(self) -> int:
        """Zeroed writable data: ``.bss*`` and ``.sbss*``."""
        return self._sum(r"\.s?bss(\..*)?")

    @property
    def total(self) -> int:
        """What the object puts in flash: ``text + rodata + data``."""
        return self.text + self.rodata + self.data

    def to_json(self) -> dict[str, object]:
        """The sums, and every section."""
        return {
            "text": self.text,
            "rodata": self.rodata,
            "data": self.data,
            "bss": self.bss,
            "total": self.total,
            "sections": dict(self.sections),
        }


def find_tool(name: str) -> str | None:
    """``name`` on ``PATH``, else the highest-numbered ``name-NN`` there
    (Debian installs ``clang-19`` and ``llvm-size-19`` without the plain
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
    containing ``version`` (clang's and llvm-size's), else the first line
    (gcc's). It names the build exactly, e.g. ``Debian clang version 19.1.7
    (3+b1)``."""
    res = subprocess.run([tool(name), "--version"], capture_output=True, text=True, check=False)
    lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    if res.returncode != 0 or not lines:
        msg = f"{name} --version failed:\n{res.stderr}"
        raise MeasureError(msg)
    return next((line for line in lines if re.search(r"\bversion\b", line)), lines[0])


def section_sizes(obj: Path) -> dict[str, int]:
    """Every section of ``obj`` and its size (``llvm-size -A``)."""
    res = subprocess.run(
        [tool(SIZE_TOOL), "-A", str(obj)], capture_output=True, text=True, check=False
    )
    if res.returncode != 0:
        msg = f"{SIZE_TOOL} -A {obj} failed:\n{res.stderr}"
        raise MeasureError(msg)
    out: dict[str, int] = {}
    for line in res.stdout.splitlines():
        m = re.fullmatch(r"(\.\S+)\s+(\d+)\s+\d+", line.strip())
        if m:
            out[m[1]] = out.get(m[1], 0) + int(m[2])
    return out


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
    sizes = Sizes(section_sizes(obj))
    if sizes.data or sizes.bss:
        msg = (
            f"{target.name}: the library has writable static data "
            f"(data {sizes.data}, bss {sizes.bss} bytes)"
        )
        raise MeasureError(msg)
    return sizes
