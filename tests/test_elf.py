"""uspiflash.elf reads what measuring needs from any ELF object: section
sizes and flags, symbols, and relocations, 32- and 64-bit, either byte
order."""

from __future__ import annotations

import json
import struct
import subprocess
from typing import TYPE_CHECKING

import pytest

from uspiflash import elf, measure

if TYPE_CHECKING:
    from pathlib import Path


def build_elf(bits: int, order: str) -> bytes:
    """A relocatable object: .text (4 bytes; function ``f``, whose
    relocations name the undefined ``ext`` and .text's section symbol),
    .rodata (3 bytes; object ``table``), .bss (8 bytes), with a symbol
    table and .rela.text."""
    e = "<" if order == "little" else ">"
    is64 = bits == 64
    names = b"\0.text\0.rodata\0.bss\0.symtab\0.strtab\0.shstrtab\0.rela.text\0"
    strtab = b"\0f\0ext\0table\0"

    def at(table: bytes, name: str) -> int:
        return table.index(b"\0" + name.encode() + b"\0") + 1

    def sym(name: int, size: int, typ: int, bind: int, shndx: int) -> bytes:
        info = bind << 4 | typ
        if is64:
            return struct.pack(e + "IBBHQQ", name, info, 0, shndx, 0, size)
        return struct.pack(e + "IIIBBH", name, 0, size, info, 0, shndx)

    symtab = b"".join(
        [
            sym(0, 0, 0, 0, 0),
            sym(0, 0, elf.STT_SECTION, 0, 1),
            sym(at(strtab, "table"), 3, elf.STT_OBJECT, 0, 2),
            sym(at(strtab, "f"), 4, elf.STT_FUNC, 1, 1),
            sym(at(strtab, "ext"), 0, 0, 1, elf.SHN_UNDEF),
        ]
    )

    def rela(offset: int, symbol: int) -> bytes:
        if is64:
            return struct.pack(e + "QQq", offset, symbol << 32 | 1, 0)
        return struct.pack(e + "IIi", offset, symbol << 8 | 1, 0)

    relas = rela(0, 4) + rela(2, 1)
    contents = [b"\0" * 4, b"abc", b"", symtab, strtab, names, relas]
    offsets, pos = [], 64 if is64 else 52
    for c in contents:
        offsets.append(pos)
        pos += len(c)
    sym_size, rel_size = (24, 24) if is64 else (16, 12)
    heads = [
        (0, 0, 0, 0, 0, 0, 0, 0),
        (at(names, ".text"), 1, 0x6, offsets[0], 4, 0, 0, 0),
        (at(names, ".rodata"), 1, 0x2, offsets[1], 3, 0, 0, 0),
        (at(names, ".bss"), 8, 0x3, offsets[2], 8, 0, 0, 0),
        (at(names, ".symtab"), 2, 0, offsets[3], len(symtab), 5, 3, sym_size),
        (at(names, ".strtab"), 3, 0, offsets[4], len(strtab), 0, 0, 0),
        (at(names, ".shstrtab"), 3, 0, offsets[5], len(names), 0, 0, 0),
        (at(names, ".rela.text"), 4, 0x40, offsets[6], len(relas), 4, 1, rel_size),
    ]
    fmt = e + ("IIQQQQIIQQ" if is64 else "IIIIIIIIII")
    shdrs = b"".join(
        struct.pack(fmt, n, t, fl, 0, o, sz, link, info, 1, ent)
        for n, t, fl, o, sz, link, info, ent in heads
    )
    ident = b"\x7fELF" + bytes([2 if is64 else 1, 1 if order == "little" else 2, 1, 0]) + bytes(8)
    if is64:
        fields = (1, 0, 1, 0, 0, pos, 0, 64, 0, 0, 64, len(heads), 6)
        header = struct.pack(e + "HHIQQQIHHHHHH", *fields)
    else:
        fields = (1, 0, 1, 0, 0, pos, 0, 52, 0, 0, 40, len(heads), 6)
        header = struct.pack(e + "HHIIIIIHHHHHH", *fields)
    return ident + header + b"".join(contents) + shdrs


@pytest.mark.parametrize("bits", [32, 64])
@pytest.mark.parametrize("order", ["little", "big"])
def test_reads_sections_symbols_and_relocations(tmp_path: Path, bits: int, order: str) -> None:
    path = tmp_path / "t.o"
    path.write_bytes(build_elf(bits, order))
    obj = elf.read(path)
    assert [(s.name, s.size) for s in obj.sections[1:4]] == [
        (".text", 4),
        (".rodata", 3),
        (".bss", 8),
    ]
    assert obj.undefined() == ["ext"]
    assert obj.defined_sizes() == {"f": 4, "table": 3}
    assert obj.relocations == {1: (4, 1)}
    assert [s.name for s in obj.symbols] == ["", "", "table", "f", "ext"]
    assert obj.symbols[3].defined
    assert not obj.symbols[4].defined


def test_mips64el_relocations(tmp_path: Path) -> None:
    """MIPS64 little-endian stores ``r_info`` as ``r_sym`` (32 bits) then
    four type bytes, so read as one 64-bit number its symbol is the low
    half, not the high one as on every other 64-bit target."""
    data = bytearray(build_elf(64, "little"))
    struct.pack_into("<H", data, 0x12, 8)  # e_machine: EM_MIPS
    path = tmp_path / "t.o"
    path.write_bytes(data)
    rela = elf.read(path).sections[7]
    for n, symbol in enumerate((4, 1)):
        struct.pack_into("<IBBBB", data, rela.offset + n * 24 + 8, symbol, 0, 0, 0, 1)
    path.write_bytes(data)
    assert elf.read(path).relocations == {1: (4, 1)}


def test_extended_section_numbering(tmp_path: Path) -> None:
    """With ``e_shnum`` 0 and ``e_shstrndx`` ``SHN_XINDEX``, section 0's
    ``sh_size`` and ``sh_link`` hold the count and the names' index."""
    data = bytearray(build_elf(64, "little"))
    (shoff,) = struct.unpack_from("<Q", data, 0x28)
    struct.pack_into("<HH", data, 0x3C, 0, 0xFFFF)
    struct.pack_into("<Q", data, shoff + 32, 8)  # section 0's sh_size: the count
    struct.pack_into("<I", data, shoff + 40, 6)  # section 0's sh_link: .shstrtab
    path = tmp_path / "t.o"
    path.write_bytes(data)
    obj = elf.read(path)
    assert [s.name for s in obj.sections][-2:] == [".shstrtab", ".rela.text"]


def test_an_unknown_class_or_a_damaged_file(tmp_path: Path) -> None:
    good = build_elf(32, "little")
    path = tmp_path / "t.o"
    path.write_bytes(good[:4] + b"\x03" + good[5:])
    with pytest.raises(elf.ElfError, match="unknown ELF class 3"):
        elf.read(path)
    path.write_bytes(good[:-8])
    with pytest.raises(elf.ElfError, match="damaged ELF file"):
        elf.read(path)


def test_classifies_as_measure_did(tmp_path: Path) -> None:
    path = tmp_path / "t.o"
    path.write_bytes(build_elf(32, "big"))
    sizes = measure.section_sizes(path)
    assert (sizes.text, sizes.rodata, sizes.data, sizes.bss) == (4, 3, 0, 8)


def test_not_an_elf_file(tmp_path: Path) -> None:
    path = tmp_path / "junk.o"
    path.write_text("not an object")
    with pytest.raises(elf.ElfError, match="not an ELF file"):
        elf.read(path)
    with pytest.raises(measure.MeasureError, match="cannot read"):
        measure.section_sizes(path)
    with pytest.raises(measure.MeasureError, match="cannot read"):
        measure.undefined_symbols(path)


def _readobj_sections(readobj: str, obj: Path) -> dict[str, dict[str, int]]:
    """What M1's measure read with llvm-readobj: the oracle."""
    res = subprocess.run(
        [readobj, "--elf-output-style=JSON", "--sections", str(obj)],
        capture_output=True,
        text=True,
        check=True,
    )
    out: dict[str, dict[str, int]] = {k: {} for k in measure.KINDS}
    for entry in json.loads(res.stdout)[0]["Sections"]:
        sec = entry["Section"]
        k = measure.kind(sec["Flags"]["Value"], sec["Type"]["Value"])
        if k is not None:
            name = sec["Name"]["Name"]
            out[k][name] = out[k].get(name, 0) + sec["Size"]
    return out


@pytest.mark.parametrize("target", measure.TARGETS, ids=lambda t: t.name)
def test_agrees_with_llvm_readobj_and_nm(tmp_path: Path, target: measure.Target) -> None:
    readobj = measure.find_tool("llvm-readobj")
    nm = measure.find_tool("llvm-nm")
    if not (readobj and nm and measure.find_tool(target.compiler)):
        pytest.skip("needs the target's compiler, llvm-readobj and llvm-nm")
    src = tmp_path / "t.c"
    src.write_text(
        "extern int ext(int);\n"
        'static const char table[5] = "abcd";\n'
        "int f(int i);\n"
        "int f(int i) { return ext(table[i]); }\n"
    )
    obj = tmp_path / "t.o"
    cc = measure.tool(target.compiler)
    cmd = [cc, *target.target_flags, "-Os", "-c", str(src), "-o", str(obj)]
    subprocess.run(cmd, check=True)
    assert measure.section_sizes(obj).sections == _readobj_sections(readobj, obj)
    res = subprocess.run(
        [nm, "--undefined-only", "--format=just-symbols", str(obj)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert measure.undefined_symbols(obj) == sorted(res.stdout.split())
