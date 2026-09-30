"""Measure what a generated file costs: compile its implementation for a
target and read the object's section sizes (spec §7.1, per-object part).

Each :class:`Target` is a compiler and its target flags. The implementation
is compiled on its own (``-c``, freestanding, ``-Os``, one section per
function and per table, no unwind tables) and uspiflash's own ELF reader
(:mod:`uspiflash.elf`) reads the object. Sections are classified by their
ELF flags, not their names, so everything that would occupy target memory
is counted whatever it is called:

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
(its undefined symbols), for every measured target.

The committed record of these numbers is :mod:`uspiflash.ledger`'s."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from spiflash.enums import FlashType

from . import elf, emit
from .levels import ChipFilter, Selection
from .provenance import Config

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

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

#: Each compiler's or linker's Debian package.
_PACKAGES = {"clang": "clang", "gcc": "gcc", "ld.lld": "lld", "ld": "binutils"}
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
    #: Whether the compiler takes ``-fstack-usage`` (clang 13 and later, every
    #: GCC in the inventory).
    stack: bool = True
    #: The flags that link for this target: ``-fuse-ld=lld`` for clang,
    #: ``-no-pie`` for a Linux host; ``None`` where no linker is packaged
    #: with the compiler (msp430, AVR with clang, SDCC).
    link_flags: tuple[str, ...] | None = ()

    @property
    def flags(self) -> tuple[str, ...]:
        """Every flag after the compiler's name."""
        return (*self.target_flags, *FLAGS, *(("-fstack-usage",) if self.stack else ()))


#: The measured targets.
#: clang links with LLVM's linker; the x86_64 image is static and not
#: position-independent (Debian's gcc defaults to PIE).
TARGETS: tuple[Target, ...] = (
    Target(
        "cortex-m0",
        "clang",
        ("--target=thumbv6m-none-eabi", "-mcpu=cortex-m0", "-mthumb"),
        link_flags=("-fuse-ld=lld",),
    ),
    Target(
        "rv32imc",
        "clang",
        ("--target=riscv32-unknown-elf", "-march=rv32imc", "-mabi=ilp32"),
        link_flags=("-fuse-ld=lld",),
    ),
    Target("x86_64", "gcc", link_flags=("-no-pie",)),
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
class Stack:
    """The stack one library call can use (spec §7.1): each function's own
    frame (``-fstack-usage``), and the deepest path through the object's
    call graph from any public function. Callbacks (``putc``, ``xfer``)
    are the caller's functions: their frames are not included."""

    frames: Mapping[str, int]
    peak: int
    path: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        """The peak, its path, and every frame."""
        frames = dict(sorted(self.frames.items()))
        return {"peak": self.peak, "path": list(self.path), "frames": frames}


@dataclass(frozen=True)
class Sizes:
    """One object's allocated sections, by kind (one of :data:`KINDS`),
    then name, in bytes; its symbols' sizes; and its stack."""

    sections: Mapping[str, Mapping[str, int]]
    #: The size of every function and table, by symbol name.
    symbols: Mapping[str, int] = field(default_factory=dict)
    #: The stack, where the compiler reports frames (``Target.stack``).
    stack: Stack | None = None
    #: The linked image's allocated bytes (:func:`linked`).
    linked: int | None = None

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
            "symbols": dict(sorted(self.symbols.items())),
            "stack": self.stack.to_json() if self.stack else None,
            "linked": self.linked,
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
    holding a dotted version number, else the first line. It names the
    build exactly: gcc's first line, clang's ``Debian clang version 19.1.7
    (3+b1)``, GNU ld's ``GNU ld (GNU Binutils for Debian) 2.44``, lld's
    ``Debian LLD 19.1.7 (compatible with GNU linkers)``."""
    res = subprocess.run([tool(name), "--version"], capture_output=True, text=True, check=False)
    lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    if res.returncode != 0 or not lines:
        msg = f"{name} --version failed:\n{res.stderr}"
        raise MeasureError(msg)
    return next((line for line in lines if re.search(r"\d+\.\d+", line)), lines[0])


def _read(obj: Path) -> elf.Elf:
    try:
        return elf.read(obj)
    except (OSError, elf.ElfError) as err:
        msg = f"cannot read {obj}: {err}"
        raise MeasureError(msg) from err


def sizes_of(obj: elf.Elf) -> Sizes:
    """``obj``'s allocated sections, classified by their flags."""
    out: dict[str, dict[str, int]] = {k: {} for k in KINDS}
    for sec in obj.sections:
        k = kind(sec.flags, sec.type)
        if k is not None:
            out[k][sec.name] = out[k].get(sec.name, 0) + sec.size
    return Sizes(out)


def section_sizes(obj: Path) -> Sizes:
    """``obj``'s allocated sections, classified by their flags."""
    return sizes_of(_read(obj))


def undefined_symbols(obj: Path) -> list[str]:
    """The symbols ``obj`` needs from elsewhere, sorted."""
    return _read(obj).undefined()


def stack_frames(text: str) -> dict[str, int]:
    """Each function's frame, in bytes, from a ``-fstack-usage`` file. GCC
    writes ``file:line:column:name<TAB>bytes<TAB>static``, clang
    ``file:line:name``. ``dynamic,bounded`` (GCC realigning the stack, as
    on i386) gives an upper bound, which is what counts. A plain
    ``dynamic`` frame (a VLA or ``alloca``) has no bound: it is refused."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        where, size, qualifiers = line.split("\t")
        name = where.rsplit(":", 1)[-1]
        q = set(qualifiers.split(","))
        if "dynamic" in q and "bounded" not in q:
            msg = f"{name} has an unbounded stack frame ({qualifiers})"
            raise MeasureError(msg)
        out[name] = max(out.get(name, 0), int(size))
    return out


def frame(frames: Mapping[str, int], name: str) -> int:
    """``name``'s frame. GCC lists a clone's symbol ``f.isra.0`` as
    ``f.isra``; failing that, a clone is taken to use its function's
    frame (``f.constprop.0`` as ``f``)."""
    for key in (name, re.sub(r"\.\d+$", "", name), name.split(".", 1)[0]):
        if key in frames:
            return frames[key]
    msg = f"no -fstack-usage entry for {name}"
    raise MeasureError(msg)


def call_graph(obj: elf.Elf) -> dict[str, set[str]]:
    """Which functions each function's code refers to, from the
    relocations of its section (every function has its own:
    ``-ffunction-sections``). A reference is a function symbol, or a
    section symbol standing for the function in that section."""
    by_section = {
        s.shndx: s.name for s in obj.symbols if s.type == elf.STT_FUNC and s.defined and s.name
    }
    graph: dict[str, set[str]] = {name: set() for name in by_section.values()}
    for index, refs in obj.relocations.items():
        caller = by_section.get(index)
        if caller is None:
            continue
        for i in refs:
            sym = obj.symbols[i]
            if sym.type == elf.STT_FUNC and sym.defined:
                callee: str | None = sym.name
            elif sym.type == elf.STT_SECTION:
                callee = by_section.get(sym.shndx)
            else:
                callee = None
            if callee is not None and callee != caller:
                graph[caller].add(callee)
    return graph


def stack_peak(
    graph: Mapping[str, set[str]], frames: Mapping[str, int], roots: Sequence[str]
) -> tuple[int, tuple[str, ...]]:
    """The deepest path from any of ``roots``: its total frame bytes and
    its functions, outermost first. Ties go to the first in sorted order,
    so the answer is deterministic. The library has no recursion; a cycle
    is refused."""
    memo: dict[str, tuple[int, tuple[str, ...]]] = {}

    def visit(fn: str, active: tuple[str, ...]) -> tuple[int, tuple[str, ...]]:
        if fn in active:
            msg = "recursion: " + " -> ".join((*active, fn))
            raise MeasureError(msg)
        if fn not in memo:
            best: tuple[int, tuple[str, ...]] = (0, ())
            for callee in sorted(graph.get(fn, ())):
                got = visit(callee, (*active, fn))
                if got[0] > best[0]:
                    best = got
            memo[fn] = (frame(frames, fn) + best[0], (fn, *best[1]))
        return memo[fn]

    best: tuple[int, tuple[str, ...]] = (0, ())
    for root in sorted(roots):
        got = visit(root, ())
        if got[0] > best[0]:
            best = got
    return best


def stack_of(obj: elf.Elf, su: Path) -> Stack:
    """The object's :class:`Stack`, with the frames from ``su``."""
    frames = stack_frames(su.read_text(encoding="utf-8"))
    roots = [
        s.name
        for s in obj.symbols
        if s.type == elf.STT_FUNC and s.defined and s.bind != elf.STB_LOCAL
    ]
    peak, path = stack_peak(call_graph(obj), frames, roots)
    return Stack(frames, peak, path)


def default_machine(compiler: str) -> str:
    """The CPU part of the triple ``compiler`` builds for by default
    (``<compiler> -dumpmachine``: ``x86_64`` from ``x86_64-linux-gnu``,
    ``i686`` from ``i686-linux-gnu``); ``""`` if it cannot say."""
    res = subprocess.run(
        [tool(compiler), "-dumpmachine"], capture_output=True, text=True, check=False
    )
    return res.stdout.strip().split("-", 1)[0] if res.returncode == 0 else ""


def can_link(target: Target) -> bool:
    """Whether :func:`linked` can link for ``target``: always without a
    linker (``link_flags`` ``None``) or with the compiler's own (GCC's
    binutils); with ``-fuse-ld=lld``, when the compiler finds an
    ``ld.lld`` (``-print-prog-name`` prints a bare name when it finds
    none)."""
    if target.link_flags is None or "-fuse-ld=lld" not in target.link_flags:
        return True
    res = subprocess.run(
        [tool(target.compiler), "-print-prog-name=ld.lld"],
        capture_output=True,
        text=True,
        check=False,
    )
    path = Path(res.stdout.strip())
    return res.returncode == 0 and path.is_absolute() and path.is_file()


def usable(target: Target) -> bool:
    """Whether ``target`` can be measured on this machine: its compiler is
    installed, :func:`can_link` holds, and a target without target flags
    (a compiler's default CPU: the ``x86_64`` reference target) is what
    that compiler builds for by default. The machine's own CPU does not
    decide it: Debian's i386 package build runs on an x86_64 kernel
    (``platform.machine()`` says ``x86_64``) with a gcc that builds for
    ``i686``."""
    if find_tool(target.compiler) is None:
        return False
    if not target.target_flags and default_machine(target.compiler) != target.name:
        return False
    return can_link(target)


def linker(target: Target) -> str | None:
    """The linker :func:`linked` uses for ``target``: ``ld.lld`` with
    ``-fuse-ld=lld``, else the compiler's own (``-print-prog-name=ld``:
    ``ld`` for a native gcc, a full path for a cross one); ``None``
    without one."""
    if target.link_flags is None:
        return None
    if "-fuse-ld=lld" in target.link_flags:
        return "ld.lld"
    res = subprocess.run(
        [tool(target.compiler), "-print-prog-name=ld"], capture_output=True, text=True, check=False
    )
    return res.stdout.strip() or "ld"


def linked(target: Target, obj: Path) -> int | None:
    """The linked-image cost (spec §7.1): ``obj`` linked on its own, every
    public function kept, with no C library, no start files, unused
    sections removed and no build id. It counts what an object's sections
    miss: alignment between sections, and the literal pools and veneers
    a linker adds. It also merges duplicate strings and unwind entries, so
    it can be smaller than the object. ``None`` when ``target`` has no
    linker (``link_flags`` is ``None``)."""
    if target.link_flags is None:
        return None
    keep = sorted(
        s.name
        for s in _read(obj).symbols
        if s.defined and s.type == elf.STT_FUNC and s.bind != elf.STB_LOCAL
    )
    exe = obj.with_suffix(".elf")
    cmd = [
        tool(target.compiler),
        *target.target_flags,
        *target.link_flags,
        "-nostdlib",
        "-nostartfiles",
        "-static",
        "-Wl,--gc-sections",
        "-Wl,--build-id=none",
        f"-Wl,-e,{keep[0]}",
        *(f"-Wl,-u,{name}" for name in keep),
        str(obj),
        "-o",
        str(exe),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=obj.parent)
    if res.returncode != 0:
        msg = f"{' '.join(cmd)} failed:\n{res.stderr}"
        raise MeasureError(msg)
    sizes = section_sizes(exe)
    if sizes.data or sizes.bss:
        msg = f"{target.name}: the linked image has writable data ({sizes.data + sizes.bss} bytes)"
        raise MeasureError(msg)
    return sizes.total


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
    e = _read(obj)
    sizes = sizes_of(e)
    if sizes.data or sizes.bss:
        msg = (
            f"{target.name}: the library has writable static data "
            f"(data {sizes.data}, bss {sizes.bss} bytes)"
        )
        raise MeasureError(msg)
    if needed := e.undefined():
        msg = f"{target.name}: the library needs symbols from elsewhere: {', '.join(needed)}"
        raise MeasureError(msg)
    stack = stack_of(e, obj.with_suffix(".su")) if target.stack else None
    return replace(sizes, symbols=e.defined_sizes(), stack=stack, linked=linked(target, obj))
