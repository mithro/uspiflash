"""A small ELF reader: the sections, symbols and relocations of an object
file, 32- or 64-bit, either byte order, with the standard library only.

:mod:`uspiflash.measure` reads every compiler's objects with it (spec
amendment 14). The numbers then never depend on which binutils or LLVM an
environment has, or on which targets that build supports."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

SHT_SYMTAB, SHT_RELA, SHT_NOBITS, SHT_REL = 2, 4, 8, 9
_SHT_NULL = 0
STT_OBJECT, STT_FUNC, STT_SECTION = 1, 2, 3
STB_LOCAL = 0
SHN_UNDEF = 0
_SHN_XINDEX = 0xFFFF
_EM_MIPS = 8


class ElfError(ValueError):
    """The file is not an ELF object this reader understands."""


@dataclass(frozen=True)
class Section:
    """One section header."""

    index: int
    name: str
    type: int
    flags: int
    size: int
    link: int
    info: int
    offset: int
    entsize: int


@dataclass(frozen=True)
class Symbol:
    """One symbol-table entry."""

    name: str
    value: int
    size: int
    type: int
    bind: int
    shndx: int

    @property
    def defined(self) -> bool:
        """Whether the object defines it (it is in one of its sections)."""
        return self.shndx != SHN_UNDEF


@dataclass(frozen=True)
class Elf:
    """What :func:`read` found."""

    sections: tuple[Section, ...]
    symbols: tuple[Symbol, ...]
    #: For each section that relocation sections apply to (by index): the
    #: indices into :attr:`symbols` its relocations refer to, in file order.
    relocations: Mapping[int, tuple[int, ...]]

    def undefined(self) -> list[str]:
        """The names of the symbols the object needs from elsewhere, sorted."""
        return sorted({s.name for s in self.symbols[1:] if not s.defined and s.name})

    def defined_sizes(self) -> dict[str, int]:
        """The size of each function and data object the object defines,
        by name (two of one name are added together)."""
        out: dict[str, int] = {}
        for s in self.symbols:
            if s.defined and s.type in (STT_FUNC, STT_OBJECT) and s.name:
                out[s.name] = out.get(s.name, 0) + s.size
        return out


def _cstr(data: bytes, table: Section, at: int) -> str:
    """The NUL-terminated string at ``at`` in string table ``table``."""
    end = data.find(b"\0", table.offset + at, table.offset + table.size)
    if at >= table.size or end < 0:
        msg = f"name {at} is outside string table {table.index}"
        raise ValueError(msg)
    return data[table.offset + at : end].decode("ascii", errors="replace")


def _entries(sec: Section, size: int, what: str) -> range:
    """The file offsets of ``sec``'s entries, each at least ``size`` bytes
    (its ``sh_entsize`` apart)."""
    if sec.entsize < size:
        msg = f"{what} section {sec.index} has entry size {sec.entsize}, not at least {size}"
        raise ValueError(msg)
    return range(sec.offset, sec.offset + sec.size - size + 1, sec.entsize)


def read(path: Path) -> Elf:
    """Read ``path``'s section headers, its symbol table and its
    relocations.

    Every table is bounded by the file: a header or a section that would
    run past its end, a table without a usable entry size, or a name
    outside its string table is an :class:`ElfError`, so a damaged or
    crafted file is refused rather than read without end."""
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or len(data) < 64:
        msg = f"{path}: not an ELF file"
        raise ElfError(msg)
    cls, order = data[4], data[5]
    if cls not in (1, 2) or order not in (1, 2):
        msg = f"{path}: unknown ELF class {cls} or byte order {order}"
        raise ElfError(msg)
    e = "<" if order == 1 else ">"
    is64 = cls == 2
    try:
        (machine,) = struct.unpack_from(e + "H", data, 0x12)
        if is64:
            (shoff,) = struct.unpack_from(e + "Q", data, 0x28)
            shentsize, shnum, shstrndx = struct.unpack_from(e + "HHH", data, 0x3A)
            shfmt = e + "IIQQQQIIQQ"
        else:
            (shoff,) = struct.unpack_from(e + "I", data, 0x20)
            shentsize, shnum, shstrndx = struct.unpack_from(e + "HHH", data, 0x2E)
            shfmt = e + "IIIIIIIIII"

        def headers(count: int) -> list[tuple[int, ...]]:
            if shentsize < struct.calcsize(shfmt) or shoff + count * shentsize > len(data):
                msg = f"{count} section headers of {shentsize} bytes at {shoff} do not fit"
                raise ValueError(msg)
            return [struct.unpack_from(shfmt, data, shoff + i * shentsize) for i in range(count)]

        raw = headers(max(shnum, 1))
        if shnum == 0:  # extended numbering: the count is section 0's size
            raw = headers(raw[0][5])
        if shstrndx == _SHN_XINDEX:
            shstrndx = raw[0][6]
        unnamed = [
            Section(i, "", r[1], r[2], r[5], r[6], r[7], r[4], r[9]) for i, r in enumerate(raw)
        ]
        for sec in unnamed:
            if sec.type not in (_SHT_NULL, SHT_NOBITS) and sec.offset + sec.size > len(data):
                msg = f"section {sec.index} runs past the end of the file"
                raise ValueError(msg)
        names = unnamed[shstrndx]
        sections = tuple(
            Section(i, _cstr(data, names, r[0]), r[1], r[2], r[5], r[6], r[7], r[4], r[9])
            for i, r in enumerate(raw)
        )
        symbols = _symbols(data, e, sections, is64=is64)
        # MIPS64 stores r_info as r_sym (32 bits) then four type bytes, in
        # file order: read as one little-endian number, r_sym is the low half.
        low = is64 and order == 1 and machine == _EM_MIPS
        relocations = _relocations(data, e, sections, is64=is64, sym_in_low_half=low)
    except (struct.error, IndexError, ValueError) as err:
        msg = f"{path}: damaged ELF file ({err})"
        raise ElfError(msg) from err
    return Elf(sections, symbols, relocations)


def _symbols(
    data: bytes, e: str, sections: tuple[Section, ...], *, is64: bool
) -> tuple[Symbol, ...]:
    tab = next((s for s in sections if s.type == SHT_SYMTAB), None)
    if tab is None:
        return ()
    strings = sections[tab.link]
    out = []
    for at in _entries(tab, 24 if is64 else 16, "symbol table"):
        if is64:
            name, info, _other, shndx, value, sym_size = struct.unpack_from(e + "IBBHQQ", data, at)
        else:
            name, value, sym_size, info, _other, shndx = struct.unpack_from(e + "IIIBBH", data, at)
        sym_name = _cstr(data, strings, name)
        out.append(Symbol(sym_name, value, sym_size, info & 0xF, info >> 4, shndx))
    return tuple(out)


def _relocations(
    data: bytes, e: str, sections: tuple[Section, ...], *, is64: bool, sym_in_low_half: bool
) -> dict[int, tuple[int, ...]]:
    out: dict[int, tuple[int, ...]] = {}
    for s in sections:
        if s.type not in (SHT_REL, SHT_RELA):
            continue
        rela = s.type == SHT_RELA
        if is64:
            fmt, size, shift = e + ("QQq" if rela else "QQ"), 24 if rela else 16, 32
        else:
            fmt, size, shift = e + ("IIi" if rela else "II"), 12 if rela else 8, 8
        infos = (struct.unpack_from(fmt, data, at)[1] for at in _entries(s, size, "relocation"))
        refs = tuple(i & 0xFFFFFFFF if sym_in_low_half else i >> shift for i in infos)
        out[s.info] = out.get(s.info, ()) + refs
    return out
