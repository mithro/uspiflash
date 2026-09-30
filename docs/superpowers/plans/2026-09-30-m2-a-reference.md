# M2 part A: catch-up, the ELF reader, stack, linked image, sizes in the header (Tasks 1–5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Read [the M2 index](2026-09-30-m2-measurement.md) (Global Constraints,
decisions 14–24) and the spec's §7 first.

Branch and worktree: `m2a` in `.worktrees/m2a`, from `origin/main`:

```bash
git fetch origin && git worktree add -b m2a .worktrees/m2a origin/main
```

Every `uv run pytest` below runs from the worktree root. The full suite
goes through the sandbox:

```bash
uv run python -m uspiflash.sandbox -- uv run pytest -n {jobs}
```

**What this part leaves behind:**
- the reference ledger (`sizes/ledger.json`) is measured by uspiflash's
  own ELF reader;
- it records per-symbol sizes, a static stack peak and the linked image;
- every generated header states its measured size when its selection is
  in the ledger;
- uspiflash is verified against the newest spiflash.

---

### Task 1: Catch up with the newest spiflash; record amendments 14–24

**Files:**
- Modify: `uv.lock`, `src/uspiflash/__init__.py` (`VERIFIED_SPIFLASH`),
  `pyproject.toml` (the comment above `dependencies`)
- Modify (regenerated): `sizes/ledger.json`, `sizes/README.md`, `README.md`
  (the size figures), `experiments/2026-09-28-database-statistics/results/stats.json`
  and that experiment's `README.md` numbers
- Modify: `tests/test_sfdp.py` (the comment naming the dump count's spiflash
  version, if the count changed)
- Modify: `docs/superpowers/specs/2026-09-28-uspiflash-design.md` (new §14)

**Interfaces:**
- Consumes: RELEASING.md's "A data update" and "The size ledger's image"
  procedures, unchanged.
- Produces: `VERIFIED_SPIFLASH` equal to the newest release; later tasks
  measure against it.

- [ ] **Step 1: Find the newest release**

Run: `curl -fsS https://pypi.org/pypi/spiflash/json | jq -r .info.version`
Expected: `0.0.post106` when this plan was written (2026-09-30), or newer.
Use whatever it prints as `<NEW>` below. The daily drift check
(`spiflash-latest.yml`) passed against 0.0.post106, 459 comparisons
identical (issue #7).

- [ ] **Step 2: Move the lock and the verified version**

```bash
uv lock --upgrade-package spiflash
grep -A2 '^name = "spiflash"' uv.lock
```

Expected: `version = "<NEW>"`. In `src/uspiflash/__init__.py` set
`VERIFIED_SPIFLASH = "<NEW>"`. In `pyproject.toml`, change the comment's
"verified byte-identical to 0.0.post92" to `<NEW>`. Leave the `>=` minimum
alone: nothing in this task needs a newer one.

- [ ] **Step 3: Run the whole suite**

Run: `uv run python -m uspiflash.sandbox -- uv run pytest -n {jobs}`
Expected: PASS, parity tests included.

On a mismatch, follow superpowers:systematic-debugging. The fix belongs in
the generator or the oracle (`src/uspiflash/oracle.py`), never in the test.
Any comment naming a count at 0.0.post92 (e.g. `tests/test_sfdp.py`'s
"12 at spiflash 0.0.post92") is updated to the new count and version.

- [ ] **Step 4: Regenerate the reference ledger in its pinned image**

RELEASING.md's step 3 command, from the worktree root, with the
sandbox's limits (Docker runs outside the sandbox's scope, so they are
passed to it). First run `uv run python -m uspiflash.sandbox --print-limits`:
it prints `memory <N> MiB, cpus <C>`. Put those values in:

```bash
IMAGE=debian:trixie@sha256:d5ce19d4736f0ebbacd686d1040271a5aeb0cc920f5990c1bfae1717627f0674
docker run --rm --memory=<N>m --memory-swap=<N>m --cpus=<C> --pids-limit=1024 -v "$PWD:/w" -w /w \
  -e UV_PROJECT_ENVIRONMENT=/venv "$IMAGE" bash -ec '
  rm -f /etc/apt/sources.list.d/debian.sources
  echo "deb http://snapshot.debian.org/archive/debian/20260918T000000Z/ trixie main" > /etc/apt/sources.list
  echo "Acquire::Check-Valid-Until \"false\";" > /etc/apt/apt.conf.d/99snapshot
  apt-get update -q
  apt-get install -y -q --no-install-recommends \
    clang-19 llvm-19 gcc libc6-dev python3 ca-certificates git curl
  curl -LsSf https://astral.sh/uv/install.sh | sh
  git config --global --add safe.directory /w
  ~/.local/bin/uv run --locked uspiflash measure --write
  chown -R "$(stat -c %u:%g /w)" /w'
```

Then run `git diff --stat sizes/ README.md`. Expected:
- `sizes/ledger.json`, `sizes/README.md` and `README.md` change;
- the ledger's `spiflash.version` is `<NEW>`.

- [ ] **Step 5: Rerun the database-statistics experiment**

```bash
uv run uspiflash research run 2026-09-28-database-statistics
git diff experiments/2026-09-28-database-statistics/results/stats.json
```

For every value that changed, update the same number where the
experiment's `README.md` quotes it. Search for the old value, and change
nothing the results did not change. The numbers come from the results file,
never from arithmetic by hand.

- [ ] **Step 6: Commit the catch-up**

```bash
git add uv.lock src/uspiflash/__init__.py pyproject.toml sizes README.md \
  experiments/2026-09-28-database-statistics tests
git commit -m "Catch up with spiflash <NEW>

uv.lock, VERIFIED_SPIFLASH, the size ledger and the database statistics
move to spiflash <NEW>; the parity tests pass against it.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```

- [ ] **Step 7: Record amendments 14–24 in the spec**

Append to `docs/superpowers/specs/2026-09-28-uspiflash-design.md` a new
section:
- the heading is `## 14. Amendments (M2 plan, 2026-09-30)`;
- under it go the M2 index's "Decisions this plan adds to the spec" items
  14–24, copied verbatim, keeping their numbers (14–24).

Also, in §9 (Python tool), change the `uspiflash[measure]: pyelftools`
bullet to "(no extra: amendment 14)".

Run: `uv run pytest tests/test_docs.py -q`
Expected: PASS (the spec is not in the Sphinx toctree, but the docs build
must stay clean).

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/specs/2026-09-28-uspiflash-design.md
git commit -m "spec: M2 amendments 14-24

The ELF reader, git-held ledger history, the toolchain inventory, runtime
symbols per CPU, helper-free arithmetic, SDCC, AVR, the libc matrix's
scope, stack and linked-image measurement, LiteX's hard CPUs, and what M2
defers.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```

---

### Task 2: `uspiflash.elf`, a stdlib ELF reader, in place of llvm-readobj and llvm-nm

**Files:**
- Create: `src/uspiflash/elf.py`, `tests/test_elf.py`
- Modify: `src/uspiflash/measure.py` (`section_sizes`, `undefined_symbols`,
  drop `SIZE_TOOL`, `NM_TOOL`)
- Modify: `src/uspiflash/ledger.py` (`tools`, `PACKAGES`, the README text)
- Modify: `tests/test_measure.py`, `.github/workflows/deb.yml` (`sizes`
  job), `RELEASING.md` (the regeneration command's package list)
- Modify (regenerated): `sizes/ledger.json`, `sizes/README.md`

**Interfaces:**
- Produces:
  - `elf.read(path: Path) -> elf.Elf`, raising `elf.ElfError` (a
    `ValueError`);
  - `Elf.sections: tuple[Section, ...]`, `Elf.symbols: tuple[Symbol, ...]`,
    and `Elf.relocations: Mapping[int, tuple[int, ...]]` (the section index
    a relocation section applies to, mapped to the symbol indices it
    refers to);
  - `Elf.undefined() -> list[str]` and `Elf.defined_sizes() -> dict[str, int]`;
  - `Section(index, name, type, flags, size, link, info, offset, entsize)`;
  - `Symbol(name, value, size, type, bind, shndx)` and `Symbol.defined`;
  - the constants `STT_OBJECT`, `STT_FUNC`, `STT_SECTION`, `STB_LOCAL`,
    `SHN_UNDEF`.
  - `measure.section_sizes(obj)` and `measure.undefined_symbols(obj)` keep
    their signatures, and raise `MeasureError("cannot read …")` on a bad
    file.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing tests**

`tests/test_elf.py`:

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_elf.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: FAIL at collection: `ImportError: cannot import name 'elf' from 'uspiflash'`.

- [ ] **Step 3: Write the reader**

`src/uspiflash/elf.py`:

```python
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
STT_OBJECT, STT_FUNC, STT_SECTION = 1, 2, 3
STB_LOCAL = 0
SHN_UNDEF = 0
_SHN_XINDEX = 0xFFFF


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


def _cstr(data: bytes, at: int) -> str:
    end = data.index(b"\0", at)
    return data[at:end].decode("ascii", errors="replace")


def read(path: Path) -> Elf:
    """Read ``path``'s section headers, its symbol table and its
    relocations."""
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
        if is64:
            (shoff,) = struct.unpack_from(e + "Q", data, 0x28)
            shentsize, shnum, shstrndx = struct.unpack_from(e + "HHH", data, 0x3A)
            shfmt = e + "IIQQQQIIQQ"
        else:
            (shoff,) = struct.unpack_from(e + "I", data, 0x20)
            shentsize, shnum, shstrndx = struct.unpack_from(e + "HHH", data, 0x2E)
            shfmt = e + "IIIIIIIIII"
        raw = [struct.unpack_from(shfmt, data, shoff + i * shentsize) for i in range(max(shnum, 1))]
        if shnum == 0:  # extended numbering: the count is section 0's size
            shnum = raw[0][5]
            raw = [struct.unpack_from(shfmt, data, shoff + i * shentsize) for i in range(shnum)]
        if shstrndx == _SHN_XINDEX:
            shstrndx = raw[0][6]
        names_at = raw[shstrndx][4]
        sections = tuple(
            Section(i, _cstr(data, names_at + r[0]), r[1], r[2], r[5], r[6], r[7], r[4], r[9])
            for i, r in enumerate(raw)
        )
        symbols = _symbols(data, e, sections, is64=is64)
        relocations = _relocations(data, e, sections, is64=is64)
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
    strings = sections[tab.link].offset
    size = 24 if is64 else 16
    out = []
    for at in range(tab.offset, tab.offset + tab.size, size):
        if is64:
            name, info, _other, shndx, value, sym_size = struct.unpack_from(e + "IBBHQQ", data, at)
        else:
            name, value, sym_size, info, _other, shndx = struct.unpack_from(e + "IIIBBH", data, at)
        sym_name = _cstr(data, strings + name)
        out.append(Symbol(sym_name, value, sym_size, info & 0xF, info >> 4, shndx))
    return tuple(out)


def _relocations(
    data: bytes, e: str, sections: tuple[Section, ...], *, is64: bool
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
        refs = tuple(
            struct.unpack_from(fmt, data, at)[1] >> shift
            for at in range(s.offset, s.offset + s.size, size)
        )
        out[s.info] = out.get(s.info, ()) + refs
    return out
```

(`is64` is keyword-only in both helpers: ruff's FBT001 rejects a
positional boolean parameter.)

- [ ] **Step 4: Measure with it**

In `src/uspiflash/measure.py`:
- import `elf` (`from . import elf, emit`);
- delete `SIZE_TOOL`, `NM_TOOL` and their comments;
- set `_PACKAGES = {"clang": "clang", "gcc": "gcc"}`;
- replace `section_sizes` and `undefined_symbols` with:

```python
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
```

In the module docstring, replace "``llvm-readobj --sections`` reads the
object" with "uspiflash's own ELF reader (:mod:`uspiflash.elf`) reads the
object", and "(``llvm-nm -u``)" with "(its undefined symbols)".

- [ ] **Step 5: The ledger lists compilers only**

In `src/uspiflash/ledger.py`:
- `tools()` becomes `return sorted({t.compiler for t in targets})`, with
  the docstring "Every compiler measuring ``targets`` needs, sorted.";
- `PACKAGES = ("clang-19", "gcc", "libc6-dev")`;
- in the module docstring, change "each tool's version line" to "each
  compiler's version line";
- in `readme()`, replace the sentence "object's sections read with
  `llvm-readobj --sections`." with "object's sections read by uspiflash's
  own ELF reader (`uspiflash.elf`).";
- in `readme()`, replace "(`llvm-nm -u` is empty, or" with "(the object's
  undefined symbols are none, or".

In `.github/workflows/deb.yml`'s `sizes` job:
- remove `llvm-19` from the `apt-get install` line;
- make the "Tool versions" step `clang-19 --version && gcc --version`.

In RELEASING.md's step 3 command, remove `llvm-19` too.

- [ ] **Step 6: Update the measure tests**

In `tests/test_measure.py`:
- `available(target)` becomes
  `return measure.find_tool(target.compiler) is not None`, with the
  docstring "Whether ``target``'s compiler is installed.";
- the `skip` messages lose "or llvm-readobj";
- `test_a_missing_tool_names_its_package` is parametrized over
  `[("clang", "clang"), ("gcc", "gcc")]`;
- in `test_an_undefined_symbol_is_refused` and `test_a_compiler_helper_is_refused`,
  the skip condition becomes `if not available(target):`;
- delete `test_an_unreadable_object_has_no_symbol_list` and
  `test_an_unreadable_object_is_an_error`: `tests/test_elf.py`'s
  `test_not_an_elf_file` replaces them;
- in `test_the_ledger_is_deterministic`, the tools assertion becomes
  `assert set(data["tools"]) == {t.compiler for t in small}`.

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_elf.py tests/test_measure.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: PASS. `test_agrees_with_llvm_readobj_and_nm` runs for every
target whose compiler and LLVM tools the machine has; it checks that the
new reader classifies exactly as M1's did.

Run: `uv run ruff check && uv run ruff format --check && uv run mypy`
Expected: clean.

- [ ] **Step 8: Regenerate the ledger; only the tool list may change**

Run Task 1 Step 4's command with `llvm-19` removed from its package list.
Then:

```bash
git diff sizes/ledger.json | grep '^[-+] ' | grep -v -e llvm -e '"tools"' -e '"packages"'
```

Expected output: nothing but the `packages` list's lines. Every size
number is unchanged: the reader classifies as llvm-readobj did.

- [ ] **Step 9: Commit**

```bash
git add src/uspiflash/elf.py src/uspiflash/measure.py src/uspiflash/ledger.py \
  tests/test_elf.py tests/test_measure.py .github/workflows/deb.yml RELEASING.md sizes
git commit -m "measure: read objects with uspiflash.elf, not llvm-readobj

A stdlib ELF reader (sections, symbols, relocations; 32/64-bit, either byte
order) measures every environment the same way, whatever LLVM it has. The
ledger's numbers are unchanged; its tools are now the compilers alone.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```

---

### Task 3: Per-symbol sizes and the static stack peak

**Files:**
- Modify: `src/uspiflash/measure.py` (`Stack`, `stack_frames`, `call_graph`,
  `stack_peak`, `Sizes.symbols`, `Sizes.stack`, `Target.stack`)
- Modify: `src/uspiflash/ledger.py` (tables and README: a `stack` column)
- Create: `tests/test_stack.py`
- Modify (regenerated): `sizes/ledger.json`, `sizes/README.md`

**Interfaces:**
- Consumes: `elf.read`, `Elf.relocations`, `Elf.symbols`, `STT_FUNC`,
  `STT_SECTION`, `STB_LOCAL` (Task 2).
- Produces:
  - `Stack(frames: Mapping[str, int], peak: int, path: tuple[str, ...])`
    with `Stack.to_json()`;
  - `stack_frames(text: str) -> dict[str, int]`;
  - `call_graph(obj: elf.Elf) -> dict[str, set[str]]`;
  - `stack_peak(graph, frames, roots) -> tuple[int, tuple[str, ...]]`;
  - `Sizes.symbols: Mapping[str, int]` and `Sizes.stack: Stack | None`,
    both in `Sizes.to_json()` (`"symbols"`, `"stack"`);
  - `Target.stack: bool = True`: compile with `-fstack-usage`.

- [ ] **Step 1: Write the failing tests**

`tests/test_stack.py`:

```python
"""The stack a library call can use: each function's frame from
-fstack-usage, and the deepest path through the call graph."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from uspiflash import measure
from uspiflash.levels import Selection
from uspiflash.measure import TARGETS, MeasureError, Target
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

GCC_SU = "uspiflash.h:765:15:usf__idrec\t8\tstatic\nuspiflash.h:812:9:usf_lookup\t32\tstatic\n"
CLANG_SU = "./uspiflash.h:812:usf_lookup\t44\tstatic\n./uspiflash.h:860:usf_id\t16\tstatic\n"


def test_frames_from_gcc_and_clang() -> None:
    assert measure.stack_frames(GCC_SU) == {"usf__idrec": 8, "usf_lookup": 32}
    assert measure.stack_frames(CLANG_SU) == {"usf_lookup": 44, "usf_id": 16}


#: gcc 14 for i386 (Debian's i386 package build runs these tests): stack
#: realignment makes a frame "dynamic,bounded", the size an upper bound.
I386_SU = (
    "uspiflash.h:812:9:usf_lookup\t44\tdynamic,bounded\nuspiflash.h:860:9:usf_id\t20\tstatic\n"
)


def test_a_bounded_dynamic_frame_counts_its_bound() -> None:
    assert measure.stack_frames(I386_SU) == {"usf_lookup": 44, "usf_id": 20}


def test_an_unbounded_frame_is_refused() -> None:
    with pytest.raises(MeasureError, match="usf_f has an unbounded stack frame"):
        measure.stack_frames("x.h:1:2:usf_f\t16\tdynamic\n")


def test_peak_is_the_deepest_path() -> None:
    graph = {"a": {"b", "c"}, "b": {"d"}, "c": set(), "d": set(), "e": {"c"}}
    frames = {"a": 10, "b": 20, "c": 50, "d": 5, "e": 1}
    assert measure.stack_peak(graph, frames, ["a", "e"]) == (60, ("a", "c"))


def test_a_clone_takes_its_functions_frame() -> None:
    graph = {"a": {"b.constprop.0"}, "b.constprop.0": set()}
    assert measure.stack_peak(graph, {"a": 8, "b": 16}, ["a"]) == (24, ("a", "b.constprop.0"))
    # GCC's .su file names the clone b.isra for the symbol b.isra.0 (gcc 14).
    graph = {"a": {"b.isra.0"}, "b.isra.0": set()}
    frames = {"a": 8, "b.isra": 12, "b": 99}
    assert measure.stack_peak(graph, frames, ["a"]) == (20, ("a", "b.isra.0"))


def test_recursion_is_refused() -> None:
    graph = {"a": {"b"}, "b": {"a"}}
    with pytest.raises(MeasureError, match="recursion: a -> b -> a"):
        measure.stack_peak(graph, {"a": 1, "b": 1}, ["a"])


def test_a_function_without_a_frame_is_refused() -> None:
    with pytest.raises(MeasureError, match="no -fstack-usage entry for b"):
        measure.stack_peak({"a": {"b"}, "b": set()}, {"a": 1}, ["a"])


@pytest.mark.parametrize("target", TARGETS, ids=lambda t: t.name)
def test_measured_objects_have_a_stack_and_symbols(tmp_path: Path, target: Target) -> None:
    if measure.find_tool(target.compiler) is None:
        pytest.skip(f"{target.compiler} not installed")
    sizes = measure.measure(Config(Selection.make("id")), target, tmp_path)
    assert sizes.stack is not None
    assert sizes.stack.path[0] in {"usf_probe", "usf_lookup", "usf_id"}
    assert sizes.stack.peak == sum(measure.frame(sizes.stack.frames, f) for f in sizes.stack.path)
    assert sizes.symbols["usf_probe"] > 0
    assert "usf__ids" in sizes.symbols
    assert sizes.to_json()["stack"] == sizes.stack.to_json()
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_stack.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: FAIL: `AttributeError: module 'uspiflash.measure' has no attribute 'stack_frames'`.

- [ ] **Step 3: Implement**

In `src/uspiflash/measure.py`:
- add `field` and `replace` to the `dataclasses` import;
- add `Mapping`, `Sequence` to the `TYPE_CHECKING` imports.

Then add:

```python
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
```

In `Sizes`:
- add two fields after `sections`:

  ```python
      #: The size of every function and table, by symbol name.
      symbols: Mapping[str, int] = field(default_factory=dict)
      #: The stack, where the compiler reports frames (``Target.stack``).
      stack: Stack | None = None
  ```

- in `to_json()`, add
  `"symbols": dict(sorted(self.symbols.items()))` and
  `"stack": self.stack.to_json() if self.stack else None`.

In `Target`:
- add the field `stack: bool = True` with the comment "#: Whether the
  compiler takes ``-fstack-usage`` (clang 13 and later, every GCC in the
  inventory).";
- make `flags` return
  `(*self.target_flags, *FLAGS, *(("-fstack-usage",) if self.stack else ()))`.

In `measure()`, replace everything after the compile's error check with:

```python
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
    return replace(sizes, symbols=e.defined_sizes(), stack=stack)
```

Both compilers name the `-fstack-usage` file after `-o`: `impl-x.o`
gets `impl-x.su` (checked with gcc 14 and clang 19, 2026-09-30).

- [ ] **Step 4: A stack column in the tables**

In `src/uspiflash/ledger.py`, `_table()` becomes:

```python
def _table(ledger: dict[str, Any], target: str) -> list[str]:
    rows = ["| Configuration | text | rodata | total | stack |", "|---|--:|--:|--:|--:|"]
    for c in ledger["configs"]:
        s = ledger["sizes"][target][c["name"]]
        stack = f"{s['stack']['peak']:,}" if s.get("stack") else "-"
        rows.append(
            f"| `{c['name']}` | {s['text']:,} | {s['rodata']:,} | **{s['total']:,}** | {stack} |"
        )
    return rows
```

In `readme()`, add this paragraph after the one ending "`ledger.json`
lists every allocated section of every object.":

```python
        "",
        "**stack** is the deepest path through the library's call graph, in",
        "bytes: each function's frame as the compiler reports it",
        "(`-fstack-usage`), added along the calls its relocations show,",
        "from any public function. Your `putc` and `xfer` callbacks' own",
        "frames come on top. `ledger.json` has every frame, the peak's path,",
        "and every function's and table's size.",
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_stack.py tests/test_measure.py tests/test_elf.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: PASS.

If `test_measured_objects_have_a_stack_and_symbols` fails with "no
-fstack-usage entry for X", print the `.su` file and the symbols. Then
extend `frame()`'s clone rule to the compiler's actual naming, with a
test. Never skip the check.

- [ ] **Step 6: Regenerate the ledger and commit**

Run Task 1 Step 4's command (without `llvm-19`). Check `sizes/README.md`
shows a stack column for all three targets. Then:

```bash
git add src/uspiflash/measure.py src/uspiflash/ledger.py tests/test_stack.py sizes
git commit -m "measure: per-symbol sizes and the static stack peak

-fstack-usage frames, added along the call graph the object's relocations
show, from every public function; recursion and dynamic frames are
refused. The ledger records every frame and symbol; its tables add a stack
column.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```

---

### Task 4: The linked-image cost

**Files:**
- Modify: `src/uspiflash/measure.py` (`Target.link_flags`, `linked`,
  `Sizes.linked`, `TARGETS`)
- Modify: `src/uspiflash/ledger.py` (`PACKAGES` adds `lld-19`; a
  `linked` column; README text)
- Modify: `.github/workflows/deb.yml` (`sizes` job installs `lld-19`),
  `RELEASING.md` (the command's package list)
- Create: `tests/test_linked.py`
- Modify (regenerated): `sizes/ledger.json`, `sizes/README.md`

**Interfaces:**
- Consumes: `_read`, `sizes_of`, `elf.STT_FUNC`, `elf.STB_LOCAL`.
- Produces:
  - `Target.link_flags: tuple[str, ...] | None = ()`, where `None` means
    no linker is packaged for the target;
  - `linked(target: Target, obj: Path) -> int | None`;
  - `can_link(target: Target) -> bool`, `default_machine(compiler: str) -> str`
    and `usable(target: Target) -> bool`;
  - `linker(target: Target) -> str | None`: the linker's name (`ld.lld`, or
    what `<compiler> -print-prog-name=ld` prints);
  - `ledger.tools()` lists the linkers with the compilers.
  - `Sizes.linked: int | None` (`"linked"` in `to_json()`).

- [ ] **Step 1: Write the failing tests**

`tests/test_linked.py`:

```python
"""The linked-image cost: the implementation linked on its own, every
public function kept, no C library."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from uspiflash import measure
from uspiflash.levels import Selection
from uspiflash.measure import TARGETS, MeasureError, Target
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

FULL = Config(Selection.make("full"))


def _usable(target: Target) -> None:
    if measure.find_tool(target.compiler) is None:
        pytest.skip(f"{target.compiler} not installed")
    if not measure.can_link(target):
        pytest.skip(f"no linker for {target.name} ({target.compiler} finds no ld.lld)")


def test_can_link_asks_the_compiler_for_lld(tmp_path: Path) -> None:
    fake = tmp_path / "clang"
    fake.write_text("#!/bin/sh\necho ld.lld\n")  # what clang prints when it has none
    fake.chmod(0o755)
    assert not measure.can_link(Target("m0", str(fake), link_flags=("-fuse-ld=lld",)))
    assert measure.can_link(Target("x", str(fake), link_flags=None))
    assert measure.can_link(Target("x", str(fake), link_flags=("-no-pie",)))


@pytest.mark.parametrize("target", TARGETS, ids=lambda t: t.name)
def test_the_linked_image_is_close_to_the_object(tmp_path: Path, target: Target) -> None:
    _usable(target)
    sizes = measure.measure(FULL, target, tmp_path)
    assert sizes.linked is not None
    # Padding and pools add a little; merged strings and unwind entries
    # take a little away (clang's Arm image is smaller than its object).
    assert abs(sizes.linked - sizes.total) < sizes.total // 50
    assert sizes.to_json()["linked"] == sizes.linked


def test_no_linker_means_no_number(tmp_path: Path) -> None:
    target = replace(TARGETS[-1], link_flags=None)
    _usable(target)
    assert measure.measure(Config(Selection.make("id")), target, tmp_path).linked is None


def test_a_failed_link_is_an_error(tmp_path: Path) -> None:
    target = replace(TARGETS[-1], link_flags=("-Wl,--no-such-option",))
    _usable(target)
    with pytest.raises(MeasureError, match="no-such-option"):
        measure.measure(Config(Selection.make("id")), target, tmp_path)
```

(`TARGETS[-1]` is the x86_64 gcc target.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_linked.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: FAIL: `AttributeError: 'Sizes' object has no attribute 'linked'`.

- [ ] **Step 3: Implement**

In `Target`, add:

```python
    #: The flags that link for this target: ``-fuse-ld=lld`` for clang,
    #: ``-no-pie`` for a Linux host; ``None`` where no linker is packaged
    #: with the compiler (msp430, AVR with clang, SDCC).
    link_flags: tuple[str, ...] | None = ()
```

In `Sizes`, add `linked: int | None = None` with the comment "#: The
linked image's allocated bytes (:func:`linked`)", and
`"linked": self.linked` in `to_json()`.

Add:

```python
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
```

```python
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
```

At the end of `measure()`:
`return replace(sizes, symbols=e.defined_sizes(), stack=stack, linked=linked(target, obj))`.

And the one test every measuring test asks first:

```python
def default_machine(compiler: str) -> str:
    """The CPU part of the triple ``compiler`` builds for by default
    (``<compiler> -dumpmachine``: ``x86_64`` from ``x86_64-linux-gnu``,
    ``i686`` from ``i686-linux-gnu``); ``""`` if it cannot say."""
    res = subprocess.run(
        [tool(compiler), "-dumpmachine"], capture_output=True, text=True, check=False
    )
    return res.stdout.strip().split("-", 1)[0] if res.returncode == 0 else ""


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
```

A test, in `tests/test_linked.py`:

```python
def test_a_default_cpu_target_needs_that_default(tmp_path: Path) -> None:
    fake = tmp_path / "gcc"
    fake.write_text("#!/bin/sh\necho i686-linux-gnu\n")  # Debian's i386 gcc
    fake.chmod(0o755)
    assert not measure.usable(Target("x86_64", str(fake), link_flags=("-no-pie",)))
    assert measure.default_machine(str(fake)) == "i686"
```

This matters now: before Task 2 the
measuring tests needed `llvm-readobj`, which the Debian builds do not
install, so they always skipped there. From Task 2 on they run in every
Debian build.

In `tests/test_measure.py`, `available(target)` becomes
`return measure.usable(target)`, with the docstring "Whether ``target``
can be measured here (:func:`uspiflash.measure.usable`).". Change
`tests/test_stack.py`'s skip to `if not measure.usable(target):`.
`tests/test_linked.py`'s `_usable` becomes:

```python
def _usable(target: Target) -> None:
    if not measure.usable(target):
        pytest.skip(f"{target.name} cannot be measured here")
```

A machine with clang but no lld then skips the clang targets' measuring
tests rather than failing them. The `sizes` job installs `lld-19`, so the
ledger check always links.

`TARGETS` gains the link flags. clang uses LLVM's linker; the x86_64
image is static and not position-independent (Debian's gcc defaults to
PIE):

```python
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
```

These commands were checked by hand on 2026-09-30 (gcc 14.2 and clang 19
with ld.lld-19, `full:nor`):
- x86_64 linked `.text` 6,831 + `.rodata` 47,184 bytes, against the
  object's 53,716 (rodata aligned to 32);
- Cortex-M0 linked 54,276, against 54,547 (merged strings and unwind
  entries).

- [ ] **Step 4: The ledger needs lld and records the linkers; a linked column**

The numbers depend on the linkers too, so their version lines go in the
ledger beside the compilers', and `measure --check` compares them. In
`measure.py`:

```python
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
```

`version()` must read linkers right. GNU ld's `--version` says "version"
only in its licence line ("the GNU General Public License version 3"), so
the rule becomes "the first line holding a dotted version number":

```python
    return next((line for line in lines if re.search(r"\d+\.\d+", line)), lines[0])
```

with the docstring's example list extended: "gcc's first line, clang's
`Debian clang version 19.1.7 (3+b1)`, GNU ld's `GNU ld (GNU Binutils for
Debian) 2.44`, lld's `Debian LLD 19.1.7 (compatible with GNU linkers)`".
In `tests/test_measure.py`'s `test_version_is_the_line_naming_the_version`,
add to `fake`:

```python
        "ld": (
            "GNU ld (GNU Binutils for Debian) 2.44\nCopyright (C) 2025\n"
            "the GNU General Public License version 3 or later.\n"
        ),
```

and `assert measure.version("ld") == "GNU ld (GNU Binutils for Debian) 2.44"`.
The existing `llvm-readobj` case still passes: its first line
(`llvm-readobj-19`) has no dotted number.

`ledger.tools()` becomes:

```python
def tools(targets: Sequence[Target]) -> list[str]:
    """Every compiler and linker measuring ``targets`` needs, sorted."""
    names = {t.compiler for t in targets}
    names |= {n for t in targets if (n := measure.linker(t)) is not None}
    return sorted(names)
```

(The reference ledger's `tools` then holds `clang`, `gcc`, `ld` and
`ld.lld`.) In `test_the_ledger_is_deterministic`, the tools assertion
becomes `assert set(data["tools"]) == set(ledger.tools(small))`.

What "linked" measures differs from spec §7.1's wording ("a minimal
program that calls the API, linked with and without the library"): this
is the implementation linked alone, every public function kept as an
entry. It needs no per-target start-up code or `main` and counts exactly
the library's bytes after linking. Amendment 22 records this.

- `ledger.PACKAGES = ("clang-19", "lld-19", "gcc", "libc6-dev")`.
- `deb.yml`'s `sizes` job adds `lld-19` to its `apt-get install`
  (`test_ci_checks_the_ledger_in_the_pinned_image` checks the packages are
  a subset of that line).
- RELEASING.md's step 3 command adds `lld-19`.
- `_table()` gains a `linked` column before `stack`. The header becomes
  `| Configuration | text | rodata | total | linked | stack |` and the
  alignment row `|---|--:|--:|--:|--:|--:|`. The cell is
  `f"{s['linked']:,}" if s.get("linked") is not None else "-"` (an ASCII
  hyphen: ruff's RUF001 rejects an en dash in a string).
- In `readme()`, extend the sentence "Linking can add alignment." to:
  "**linked** is the implementation linked on its own (every public
  function kept, no C library): it adds alignment, pools and veneers, and
  merges duplicate strings, so it can come out smaller."

- [ ] **Step 5: Run the tests; regenerate; commit**

Run: `uv run pytest tests/test_linked.py tests/test_measure.py tests/test_stack.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: PASS.

Regenerate with Task 1 Step 4's command. Its package list becomes
`clang-19 lld-19 gcc libc6-dev python3 ca-certificates git curl`. Then:

```bash
git add src/uspiflash/measure.py src/uspiflash/ledger.py tests/test_linked.py \
  .github/workflows/deb.yml RELEASING.md sizes
git commit -m "measure: the linked-image cost

The implementation linked on its own with no C library and every public
function kept (lld for clang, non-PIE on x86_64): alignment, pools and
veneers the object's sections miss. A linked column in the ledger.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```

---

### Task 5: The generated header states its measured size (spec §5.5)

**Files:**
- Modify: `src/uspiflash/ledger.py` (`REFERENCE`, `reference_sizes()`,
  `files()`)
- Modify: `src/uspiflash/provenance.py` (`selection_key()`,
  `size_lines()`, `header()`)
- Create (generated): `src/uspiflash/reference_sizes.json`
- Create: `tests/test_reference_sizes.py`
- Modify: `tests/test_measure.py` (`test_the_committed_files_match_the_committed_ledger`)

**Interfaces:**
- Consumes: the committed ledger's `configs[].config.selection`, and its
  `sizes[target][config]["total"]`.
- Produces:
  - `provenance.selection_key(sel: Selection) -> str`: the sha256 of the
    selection's canonical JSON;
  - `provenance.size_lines(config: Config) -> list[str]`;
  - `ledger.REFERENCE = Path("src/uspiflash/reference_sizes.json")`, one of
    `ledger.files()`;
  - `ledger.reference_sizes(ledger) -> dict[str, Any]`, in the form
    `{"spiflash": str, "targets": [str], "configs": {key: {"name": str, "total": {target: int}}}}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_reference_sizes.py`:

```python
"""A generated header quotes its measured size, from the committed ledger,
when its selection is one the ledger measures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import spiflash
from spiflash.enums import FlashType

from uspiflash import ledger, provenance
from uspiflash.levels import ChipFilter, Selection
from uspiflash.provenance import Config

ROOT = Path(__file__).resolve().parent.parent
FULL_NOR = Selection.make("full", chips=ChipFilter(types=(FlashType.NOR,)))


def committed() -> dict[str, Any]:
    data = ledger.committed(ROOT)
    if data is None:
        pytest.skip("no committed ledger (an sdist without sizes/)")
    return data


def test_a_measured_selection_quotes_the_ledger() -> None:
    data = committed()
    if data["spiflash"]["version"] != spiflash.__version__:
        pytest.skip("the ledger was measured against another spiflash")
    text = " ".join(provenance.size_lines(Config(FULL_NOR)))
    for target in data["targets"]:
        total = data["sizes"][target["name"]]["full:nor"]["total"]
        assert f"{target['name']} {total:,}" in text
    assert "full:nor" in text


def test_the_prefix_and_file_name_do_not_matter() -> None:
    committed()
    assert provenance.size_lines(Config(FULL_NOR, "fl", "flash.h")) == provenance.size_lines(
        Config(FULL_NOR)
    )


def test_an_unmeasured_selection_says_so() -> None:
    lines = provenance.size_lines(Config(Selection.make("id", with_=["jep106"])))
    assert "not in the size ledger" in " ".join(lines)


def test_another_spiflash_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spiflash, "__version__", "0.0.0")
    assert "not in the size ledger" in " ".join(provenance.size_lines(Config(FULL_NOR)))


def test_the_header_has_the_lines() -> None:
    config = Config(FULL_NOR)
    header = provenance.header(config)
    for line in provenance.size_lines(config):
        assert f" * {line}\n" in header


def test_the_packaged_file_is_generated_from_the_ledger() -> None:
    data = committed()
    packaged = json.loads((ROOT / ledger.REFERENCE).read_text(encoding="utf-8"))
    assert packaged == ledger.reference_sizes(data)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_reference_sizes.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: FAIL: `AttributeError: module 'uspiflash.provenance' has no attribute 'size_lines'`.

- [ ] **Step 3: Implement the ledger side**

In `src/uspiflash/ledger.py`:

```python
#: The sizes the generated header quotes (spec §5.5), shipped in the
#: package; generated from the ledger like its README.
REFERENCE = Path("src/uspiflash/reference_sizes.json")


def reference_sizes(ledger: dict[str, Any]) -> dict[str, Any]:
    """Each measured selection's total on each target, keyed by
    :func:`uspiflash.provenance.selection_key`, for the header's size
    lines."""
    targets = [t["name"] for t in ledger["targets"]]
    configs = {}
    for c in ledger["configs"]:
        key = provenance.selection_key(Selection.from_json(c["config"]["selection"]))
        configs[key] = {
            "name": c["name"],
            "total": {t: ledger["sizes"][t][c["name"]]["total"] for t in targets},
        }
    return {"spiflash": ledger["spiflash"]["version"], "targets": targets, "configs": configs}
```

(Imports: `from . import measure, provenance` and
`from .levels import Selection`.)

In `files()`, add
`REFERENCE: json.dumps(reference_sizes(ledger), sort_keys=True, indent=1) + "\n"`
to `out`. Update `files()`'s docstring to list it.

- [ ] **Step 4: Implement the header side**

In `src/uspiflash/provenance.py` (add `import functools`, `import
textwrap`, `from importlib import resources`):

```python
def selection_key(sel: Selection) -> str:
    """The sha256 of ``sel``'s canonical JSON: what the size ledger's
    numbers depend on (the prefix and file name do not change them)."""
    text = json.dumps(sel.to_json(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


@functools.cache
def _reference() -> dict[str, Any]:
    text = resources.files("uspiflash").joinpath("reference_sizes.json").read_text("utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


def size_lines(config: Config) -> list[str]:
    """The header's size lines: the reference targets' totals for this
    selection from the size ledger, when the ledger measured it with the
    installed spiflash; else a line saying it is not measured."""
    ref = _reference()
    entry = ref["configs"].get(selection_key(config.selection))
    if entry is None or ref["spiflash"] != spiflash.__version__:
        return [
            "Size: this selection is not in the size ledger; `uspiflash measure`",
            "sizes the ones that are (sizes/README.md in the repository).",
        ]
    sizes = ", ".join(f"{t} {entry['total'][t]:,}" for t in ref["targets"])
    return textwrap.wrap(
        f"Size ({entry['name']} in sizes/ledger.json, spiflash {ref['spiflash']}): "
        f"{sizes} bytes of flash for code and tables at -Os, and no static RAM.",
        width=72,
        break_on_hyphens=False,
        break_long_words=False,
    )
```

In `header()`, insert `"", *size_lines(config),` after the line
`f"Check a committed copy is current with: uspiflash check {config.filename}",`.

- [ ] **Step 5: Generate the packaged file**

Run Task 1 Step 4's command. It writes
`src/uspiflash/reference_sizes.json` with the rest.

In `tests/test_measure.py`'s
`test_the_committed_files_match_the_committed_ledger`, add
`assert ledger.REFERENCE in files`.

Run: `uv run python -m uspiflash.sandbox -- uv run pytest -n {jobs}`
Expected: PASS. Nothing compares whole generated headers with a golden
copy (`test_emit`'s determinism tests compare two renders), so no fixture
changes.

- [ ] **Step 6: Commit**

```bash
git add src/uspiflash/ledger.py src/uspiflash/provenance.py \
  src/uspiflash/reference_sizes.json tests/test_reference_sizes.py tests/test_measure.py sizes
git commit -m "Generated headers state their measured size

The provenance header quotes the reference targets' totals from the size
ledger when the selection is measured and the installed spiflash is the
ledger's (spec 5.5). measure --write generates the packaged
reference_sizes.json from the ledger; --check keeps it current.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```

- [ ] **Step 7: Open the part's PR**

After the whole-part review:

```bash
git push -u origin m2a
gh pr create --title "M2a: catch-up, ELF reader, stack, linked image, sizes in the header" \
  --body "Part A of the M2 plan (docs/superpowers/plans/2026-09-30-m2-a-reference.md).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```
