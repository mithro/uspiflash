# M2 part B: CPUs, SDCC, arithmetic without helpers (Tasks 6–9)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Read [the M2 index](2026-09-30-m2-measurement.md) first (decisions 17–20).
Branch and worktree: `m2b` in `.worktrees/m2b`, from `origin/main` after
M2a merged.

**What this part leaves behind:**
- `measure` knows every CPU of the matrix, and how each compiler family
  selects it.
- It measures SDCC's objects, and allows exactly each port's listed
  runtime symbols.
- The generated C calls no multiply, divide or variable-shift helper on
  rv32i, rv32ec, msp430, AVR or SDCC's ports.
- SDCC's non-reentrant ports compile it in their default memory model.

**Research behind this part** (2026-09-30, all in the pinned trixie image
at `20260918T000000Z` or with the host's clang 19; nothing committed).
Undefined symbols of the M1 template's implementation, `--type nor`:

| Compiler, CPU | id | read | full | id+sfdp |
|---|---|---|---|---|
| clang 19 rv32i | none | none | `__mulsi3` (`usf_print`: a row × 12) | none |
| clang 19 rv32e | none | none | `__mulsi3` | none |
| clang 19/22 msp430 | none | `__mspabi_mpyi` (`usf__row`, `usf__oprow`, `usf_has_feature`) | `__mspabi_mpyi`, `__mspabi_slll`, `__mspabi_srll` (`usf__human`) | `__mspabi_slll`, `__mspabi_srll` (`usf_sfdp_read`) |
| clang 19 rv32i, `full+datasheets` (all types) | | | `__mulsi3`, `__udivsi3` (`usf_print_json`: `usf__dec2`'s subtract-ten loop) | |
| gcc 14 avr, ATmega328P | `__do_copy_data` | `__do_copy_data` | `__do_copy_data` | `__do_copy_data` |
| gcc 14 avr, ATmega4809 | none | none | none | – |
| clang 19 avr, ATmega4809 (`id+sfdp`, Part B's template) | | | | `__do_copy_data` |
| clang 19 ppc64le | `.TOC.` | `.TOC.` | `.TOC.` | `.TOC.` |
| SDCC 4.5.0 mcs51 | error 92: "Functions called via pointers must be 'reentrant'" | same | same | same |
| SDCC 4.5.0 mcs51, `--stack-auto` | `__gptrget`, `__gptrput`, `_bp` | + `__mulint` | + `__mulint` | `_bp`, … |
| gcc 14 rv32i, rv32imc, rv32ec; or1k; arm-none-eabi M0/M4; x86_64 gcc 12/13 | none | none | none | none |

With this part's template changes applied to a scratch copy:
- rv32i, rv32e and msp430 (clang 19) had no undefined symbol at any
  measured configuration. The exception is msp430's three large extras,
  where clang crashes; issue #7 records that, and they pass 64 KiB anyway.
- The host suite passed with the switches off (275 tests) and forced on
  (parity, lookup and SFDP).
- SDCC 4.5.0 with `__reentrant` callbacks, in the default model:
  - mcs51: `__gptrget`, `__gptrput`;
  - hc08 and s08: `___SDCC_hc08_ret2`, `___SDCC_hc08_ret3`;
  - mos6502: `REGTEMP`, `DPTR`, `__sdcc_indirect_jsr`,
    `___SDCC_m6502_ret2`, `___SDCC_m6502_ret3`, plus `__mulint` (which is
    why its ports join `USF_SOFT_MUL`'s list);
  - stm8, z80, r2k, sm83 and f8 reject `__reentrant` (a syntax error), so
    `USF_REENTRANT` is empty there. Without it, stm8 had no undefined
    symbol and z80 `___sdcc_call_iy`, `___sdcc_enter_ix`.

---

### Task 6: CPUs, SDCC objects, and runtime symbols

**Files:**
- Modify: `src/uspiflash/measure.py` (`Cpu`, `CPUS`, `family_of`,
  `target()`, `Target.family`, `Target.runtime`, `SDCC_FLAGS`,
  `rel_contents`, `KINDS` adds `"frames"`, `Sizes.frames`, `TARGETS` via
  `target()`, `measure()` dispatch)
- Create: `tests/test_cpus.py`
- Modify (regenerated): `sizes/ledger.json` (every entry gains
  `"frames": 0`)

**Interfaces:**
- Consumes: `Target.link_flags`, `Target.stack`, `linked`, `stack_of`,
  `sizes_of`, `_read` (Part A).
- Produces:
  - `Cpu(name, clang, gcc, sdcc, runtime, host, link)`;
  - `CPUS: dict[str, Cpu]`, in this order: x86_64, aarch64, ppc64le,
    cortex-m0, cortex-m4, rv32i, rv32imc, rv32ec, msp430, avr, or1k, mcs51,
    hc08, stm8, z80, mos6502;
  - `family_of(compiler: str) -> str`, one of `"gcc"`, `"clang"`,
    `"sdcc"`;
  - `target(cpu: str, compiler: str, *, name: str | None = None, stack: bool = True) -> Target`,
    raising `ValueError` when the family cannot build for the CPU;
  - `Target.family` and `Target.runtime: frozenset[str]`;
  - `rel_contents(text: str) -> tuple[Sizes, list[str]]`;
  - `Sizes.frames`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cpus.py`:

```python
"""Each CPU, how each compiler family selects it, SDCC's objects, and the
runtime symbols a port may need (spec amendment 17)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from spiflash.enums import FlashType

from uspiflash import emit, measure
from uspiflash.levels import ChipFilter, Selection
from uspiflash.measure import CPUS, TARGETS, MeasureError
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

#: SDCC 4.5.0's object for the mcs51 id:nor implementation (areas and
#: symbols only; 2026-09-30).
MCS51_REL = """\
XH3
H 1B areas E global symbols
M s
O -mmcs51 --model-small
S __gptrput Ref000000
S .__.ABS. Def000000
S __gptrget Ref000000
A _CODE size 0 flags 0 addr 0
A REG_BANK_0 size 8 flags 4 addr 0
A DSEG size 39 flags 0 addr 0
S _usf_probe_PARM_2 Def000015
A OSEG size 13 flags 4 addr 0
S _usf_lookup_PARM_2 Def000000
A BSEG size 1 flags 80 addr 0
A CSEG size 742 flags 20 addr 0
S _usf_lookup Def000000
A CONST size D04 flags 20 addr 0
"""


def test_an_sdcc_object_is_read() -> None:
    sizes, undefined = measure.rel_contents(MCS51_REL)
    assert sizes.text == 0x742
    assert sizes.rodata == 0xD04
    assert sizes.frames == 0x39 + 0x13 + 1
    assert (sizes.data, sizes.bss) == (0, 0)
    assert sizes.total == 0x742 + 0xD04
    assert undefined == ["__gptrget", "__gptrput"]


def test_decimal_sdcc_objects_are_read() -> None:
    sizes, _ = measure.rel_contents("DL2\nA CSEG size 100 flags 0 addr 0\n")
    assert sizes.text == 100


def test_an_unknown_sdcc_area_is_refused() -> None:
    with pytest.raises(MeasureError, match="unknown SDCC area INITIALIZED"):
        measure.rel_contents("XH3\nA INITIALIZED size 4 flags 0 addr 0\n")


def test_the_reference_targets_are_cpus() -> None:
    assert [t.name for t in TARGETS] == ["cortex-m0", "rv32imc", "x86_64"]
    assert TARGETS[0] == measure.target("cortex-m0", "clang")
    assert TARGETS[0].link_flags == ("-fuse-ld=lld",)
    assert TARGETS[2].link_flags == ("-no-pie",)


def test_families() -> None:
    assert measure.family_of("clang-19") == "clang"
    assert measure.family_of("/opt/toolchains/x/bin/riscv-none-elf-gcc") == "gcc"
    assert measure.family_of("sdcc") == "sdcc"
    assert measure.target("mcs51", "sdcc").family == "sdcc"


def test_sdcc_targets_are_unlinked_and_list_their_runtime() -> None:
    t = measure.target("mcs51", "sdcc")
    assert t.link_flags is None
    assert not t.stack
    assert t.runtime == {"__gptrget", "__gptrput"}
    assert "--Werror" in t.flags
    assert "-fstack-usage" not in t.flags


def test_a_family_that_cannot_build_a_cpu_is_refused() -> None:
    with pytest.raises(ValueError, match="gcc cannot build for msp430"):
        measure.target("msp430", "gcc")


def test_every_cpu_is_buildable_and_explains_its_runtime() -> None:
    for cpu in CPUS.values():
        assert (cpu.clang, cpu.gcc, cpu.sdcc) != (None, None, None), cpu.name
        for symbol, why in cpu.runtime:
            assert symbol
            assert len(why) > 20, (cpu.name, symbol)
        if cpu.sdcc is not None:
            assert not cpu.link, cpu.name


def test_a_listed_runtime_symbol_is_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = replace(TARGETS[-1], runtime=frozenset({"usf_ext"}), link_flags=None)
    if not measure.usable(target):
        pytest.skip("the x86_64 target cannot be measured here")
    code = "int usf_ext(int x);\nint usf_f(int x);\nint usf_f(int x) { return usf_ext(x); }\n"
    monkeypatch.setattr(emit, "render", lambda _c: code)
    measure.measure(Config(Selection.make("id")), target, tmp_path)  # no MeasureError


def test_sdcc_measures_stm8(tmp_path: Path) -> None:
    if measure.find_tool("sdcc") is None:
        pytest.skip("sdcc not installed")
    config = Config(Selection.make("id", chips=ChipFilter(types=(FlashType.NOR,))))
    sizes = measure.measure(config, measure.target("stm8", "sdcc"), tmp_path)
    assert sizes.text > 0
    assert sizes.rodata > 0
    assert sizes.stack is None
    assert sizes.linked is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_cpus.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: FAIL: `ImportError: cannot import name 'CPUS'`.

- [ ] **Step 3: Implement**

In `src/uspiflash/measure.py`, set `KINDS = ("text", "rodata", "data",
"bss", "frames")` and add, after `FLAGS`:

```python
#: SDCC's flags: C99, size first, every warning an error. Warning 110
#: ("conditional flow changed by optimizer") reports the optimiser deleting
#: a branch a one-type header makes constant (USF_LOOKUP_MAX 1); it is not
#: about the source (spec amendment 19).
SDCC_FLAGS = ("--std-c99", "--opt-code-size", "--Werror", "--disable-warning", "110")

_GPTR = "generic-pointer access: part of SDCC's mcs51 calling convention, not code"
_HC08_RET = "the return-value registers of SDCC's hc08 calling convention"
_Z80_CALL = "the frame and indirect-call entry of SDCC's z80 calling convention"
_M6502 = "the pseudo-registers and indirect call of SDCC's 6502 calling convention"
_RV = "--target=riscv32-unknown-elf"


@dataclass(frozen=True)
class Cpu:
    """A CPU the library is measured on: how each compiler family selects
    it, and what its port may need from elsewhere."""

    name: str
    #: clang's flags for it; ``None`` when clang cannot build for it.
    clang: tuple[str, ...] | None = None
    #: The flags a GCC built for its triple takes; ``None``: no GCC.
    gcc: tuple[str, ...] | None = None
    #: SDCC's flags (the port); ``None``: not an SDCC port.
    sdcc: tuple[str, ...] | None = None
    #: The runtime symbols the port's calling convention needs, each with
    #: the reason (spec amendment 17). Nothing else may be undefined, and an
    #: arithmetic helper never is.
    runtime: tuple[tuple[str, str], ...] = ()
    #: A Linux host CPU: the linked image is static and not
    #: position-independent.
    host: bool = False
    #: Whether its GCC, and clang's lld, can link for it.
    link: bool = True


CPUS: dict[str, Cpu] = {
    c.name: c
    for c in (
        Cpu("x86_64", clang=(), gcc=(), host=True),
        Cpu("aarch64", clang=("--target=aarch64-linux-gnu",), gcc=(), host=True),
        Cpu(
            "ppc64le",
            clang=("--target=powerpc64le-linux-gnu",),
            gcc=(),
            host=True,
            runtime=((".TOC.", "the ELFv2 ABI's table-of-contents base, which the linker defines"),),
        ),
        Cpu(
            "cortex-m0",
            clang=("--target=thumbv6m-none-eabi", "-mcpu=cortex-m0", "-mthumb"),
            gcc=("-mcpu=cortex-m0", "-mthumb"),
        ),
        Cpu(
            "cortex-m4",
            clang=("--target=thumbv7em-none-eabi", "-mcpu=cortex-m4", "-mthumb"),
            gcc=("-mcpu=cortex-m4", "-mthumb"),
        ),
        Cpu("rv32i", clang=(_RV, "-march=rv32i", "-mabi=ilp32"), gcc=("-march=rv32i", "-mabi=ilp32")),
        Cpu(
            "rv32imc",
            clang=(_RV, "-march=rv32imc", "-mabi=ilp32"),
            gcc=("-march=rv32imc", "-mabi=ilp32"),
        ),
        Cpu(
            "rv32ec",
            clang=(_RV, "-march=rv32ec", "-mabi=ilp32e"),
            gcc=("-march=rv32ec", "-mabi=ilp32e"),
        ),
        Cpu("msp430", clang=("--target=msp430",), link=False),
        # avr-gcc only: clang 19's AVR backend still references
        # __do_copy_data for ATmega4809 (2026-09-30), copying tables to RAM.
        Cpu("avr", gcc=("-mmcu=atmega4809",), link=False),
        Cpu("or1k", gcc=()),
        Cpu(
            "mcs51",
            sdcc=("-mmcs51", "-DUSF_ROM=__code"),
            runtime=(("__gptrget", _GPTR), ("__gptrput", _GPTR)),
            link=False,
        ),
        Cpu(
            "hc08",
            sdcc=("-mhc08",),
            runtime=(("___SDCC_hc08_ret2", _HC08_RET), ("___SDCC_hc08_ret3", _HC08_RET)),
            link=False,
        ),
        Cpu("stm8", sdcc=("-mstm8",), link=False),
        Cpu(
            "z80",
            sdcc=("-mz80",),
            runtime=(("___sdcc_call_iy", _Z80_CALL), ("___sdcc_enter_ix", _Z80_CALL)),
            link=False,
        ),
        Cpu(
            "mos6502",
            sdcc=("-mmos6502",),
            runtime=tuple(
                (s, _M6502)
                for s in (
                    "DPTR",
                    "REGTEMP",
                    "__sdcc_indirect_jsr",
                    "___SDCC_m6502_ret2",
                    "___SDCC_m6502_ret3",
                )
            ),
            link=False,
        ),
    )
}


def family_of(compiler: str) -> str:
    """``"sdcc"``, ``"clang"`` or ``"gcc"``, from the compiler's file name."""
    base = Path(compiler).name
    if base.startswith("sdcc"):
        return "sdcc"
    return "clang" if "clang" in base else "gcc"
```

`Target` gains `runtime: frozenset[str] = frozenset()`, with the comment
"#: Undefined symbols allowed: the port's calling-convention runtime
(:attr:`Cpu.runtime`).", and:

```python
    @property
    def family(self) -> str:
        """The compiler's family (:func:`family_of`)."""
        return family_of(self.compiler)

    @property
    def flags(self) -> tuple[str, ...]:
        """Every flag after the compiler's name."""
        if self.family == "sdcc":
            return (*self.target_flags, *SDCC_FLAGS)
        return (*self.target_flags, *FLAGS, *(("-fstack-usage",) if self.stack else ()))
```

Then:

```python
def target(cpu: str, compiler: str, *, name: str | None = None, stack: bool = True) -> Target:
    """``compiler`` building for ``cpu`` (a :data:`CPUS` name)."""
    c = CPUS[cpu]
    family = family_of(compiler)
    flags = {"clang": c.clang, "gcc": c.gcc, "sdcc": c.sdcc}[family]
    if flags is None:
        msg = f"{family} cannot build for {cpu}"
        raise ValueError(msg)
    link: tuple[str, ...] | None = None
    if family != "sdcc" and c.link:
        link = (*(("-fuse-ld=lld",) if family == "clang" else ()), *(("-no-pie",) if c.host else ()))
    return Target(
        name or cpu,
        compiler,
        flags,
        runtime=frozenset(s for s, _ in c.runtime),
        link_flags=link,
        stack=stack and family != "sdcc",
    )


#: The reference targets: the size ledger and the README's headline.
TARGETS: tuple[Target, ...] = (
    target("cortex-m0", "clang"),
    target("rv32imc", "clang"),
    target("x86_64", "gcc"),
)
```

(`target()` and `CPUS` sit above `TARGETS`, which now replaces Part A's
literal tuple.)

SDCC's objects:

```python
#: SDCC's areas, by what they hold: code, constant tables, or the static
#: frames (locals and parameters) of a port that keeps them out of a stack.
_SDCC_AREAS = {
    "text": frozenset({"CSEG", "CODE", "HOME"}),
    "rodata": frozenset({"CONST", "RODATA"}),
    "frames": frozenset(
        {"DSEG", "OSEG", "ISEG", "XSEG", "PSEG", "BSEG", "BIT_BANK", "ZP", "BSS", "DATA"}
    ),
}
#: Areas every program has, not the library's: the 8051's register bank 0.
_SDCC_IGNORED = frozenset({"REG_BANK_0"})


def rel_contents(text: str) -> tuple[Sizes, list[str]]:
    """An SDCC object's (``.rel``) areas, by kind, and the symbols it
    refers to without defining. The first line's letter gives the numbers'
    radix: ``X`` hex, ``D`` decimal, ``Q`` octal."""
    radix = {"X": 16, "D": 10, "Q": 8}.get(text[:1], 16)
    out: dict[str, dict[str, int]] = {k: {} for k in KINDS}
    refs: set[str] = set()
    defs: set[str] = set()
    for line in text.splitlines():
        f = line.split()
        if len(f) >= 4 and f[0] == "A" and f[2] == "size":
            area, size = f[1], int(f[3], radix)
            if size == 0 or area in _SDCC_IGNORED:
                continue
            k = next((k for k, names in _SDCC_AREAS.items() if area in names), None)
            if k is None:
                msg = f"unknown SDCC area {area} ({size} bytes)"
                raise MeasureError(msg)
            out[k][area] = out[k].get(area, 0) + size
        elif len(f) >= 3 and f[0] == "S" and not f[1].startswith("."):
            (refs if f[2].startswith("Ref") else defs).add(f[1])
    return Sizes(out), sorted(refs - defs)
```

`Sizes` gains:

```python
    @property
    def frames(self) -> int:
        """SRAM an SDCC port gives the library's locals and parameters in
        place of a stack (0 for GCC and clang, which use the stack)."""
        return self._sum("frames")
```

and `"frames": self.frames` in `to_json()`.

`measure()`'s compile and after become:

```python
    suffix = "rel" if target.family == "sdcc" else "o"
    obj = workdir / f"impl-{target.name}.{suffix}"
    cmd = compile_command(target, source, obj)
    res = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=workdir)
    if res.returncode != 0 or res.stderr:
        msg = f"{' '.join(cmd)} failed:\n{res.stderr}{res.stdout}"
        raise MeasureError(msg)
    e: elf.Elf | None = None
    if target.family == "sdcc":
        sizes, undefined = rel_contents(obj.read_text(encoding="ascii"))
    else:
        e = _read(obj)
        sizes, undefined = sizes_of(e), e.undefined()
    if sizes.data or sizes.bss:
        msg = (
            f"{target.name}: the library has writable static data "
            f"(data {sizes.data}, bss {sizes.bss} bytes)"
        )
        raise MeasureError(msg)
    if needed := [s for s in undefined if s not in target.runtime]:
        msg = f"{target.name}: the library needs symbols from elsewhere: {', '.join(needed)}"
        raise MeasureError(msg)
    if e is None:
        return sizes
    stack = stack_of(e, obj.with_suffix(".su")) if target.stack else None
    return replace(sizes, symbols=e.defined_sizes(), stack=stack, linked=linked(target, obj))
```

(SDCC reports its errors on stdout as well as stderr, hence
`{res.stdout}`.)

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_cpus.py tests/test_measure.py tests/test_linked.py tests/test_stack.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: PASS. `test_sdcc_measures_stm8` skips where SDCC is not
installed; install it (`sudo apt-get install sdcc`) to run it locally once.

- [ ] **Step 5: Regenerate the reference ledger; commit**

Run Part A Task 1 Step 4's command, with the package list
`clang-19 lld-19 gcc libc6-dev python3 ca-certificates git curl`. The
only change is a `"frames": 0` in every entry.

```bash
git add src/uspiflash/measure.py tests/test_cpus.py sizes
git commit -m "measure: CPUs, SDCC objects and per-port runtime symbols

measure.CPUS says how clang, GCC and SDCC select each CPU and which
calling-convention runtime symbols its port may need (amendment 17);
measure.target() builds a Target from a CPU and a compiler. SDCC's .rel
areas are read as code, tables and static frames.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```

---

### Task 7: Row offsets without a multiply helper (`USF_SOFT_MUL`)

**Files:**
- Modify: `src/uspiflash/templates/uspiflash.h.in`
- Modify: `tests/harness.py` (`Harness.build(..., defines=())`,
  `check(..., defines=())`)
- Create: `tests/test_portability.py`, `tests/test_soft_arith.py`

**Interfaces:**
- Consumes: `measure.target`, `measure.CONFIGS`, `harness.check`,
  `oracle.text`, `oracle.json_text`, `oracle.accessors`.
- Produces:
  - the template macros `USF_SOFT_MUL` (0 or 1, user-overridable),
    `USF__NOINLINE` and `USF__MUL(a, k)`;
  - `harness.Harness.build(tmp, config, cc, defines: Sequence[str] = ())`;
  - `harness.check(tmp, compilers, config, oracles, defines: Sequence[str] = ())`.

- [ ] **Step 1: Write the failing tests**

`tests/test_portability.py`:

```python
"""The generated library calls no compiler helper on CPUs without a
multiplier or a barrel shifter (spec amendment 18): clang for rv32i,
rv32ec and msp430, which every clang can build for without a C library."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from uspiflash import measure
from uspiflash.measure import MeasureError

if TYPE_CHECKING:
    from pathlib import Path

    from uspiflash.provenance import Config

#: The CPUs, and the LLVM backend each needs.
PORTABLE = {"rv32i": "riscv32", "rv32ec": "riscv32", "msp430": "msp430"}
#: Task 7: the configurations without a printer or the SFDP reader (Task 8
#: widens this to every configuration).
CONFIGS = [(n, c) for n, c in measure.CONFIGS if n.split(":")[0] in {"id", "read", "write"}]


def backends() -> set[str]:
    clang = measure.find_tool("clang")
    if clang is None:
        return set()
    res = subprocess.run([clang, "--print-targets"], capture_output=True, text=True, check=False)
    return {line.split()[0] for line in res.stdout.splitlines()[1:] if line.strip()}


BACKENDS = backends()


@pytest.mark.parametrize("cpu", sorted(PORTABLE))
@pytest.mark.parametrize(("name", "config"), CONFIGS, ids=[n for n, _ in CONFIGS])
def test_no_helper_is_needed(tmp_path: Path, cpu: str, name: str, config: Config) -> None:
    del name
    if PORTABLE[cpu] not in BACKENDS:
        pytest.skip(f"clang without the {PORTABLE[cpu]} backend")
    # Compiling and the undefined symbols are what matter; the linker may
    # be missing (lld), and msp430 has none.
    target = replace(measure.target(cpu, "clang"), link_flags=None)
    try:
        measure.measure(config, target, tmp_path)
    except MeasureError as e:
        pytest.fail(str(e).splitlines()[0])
```

`tests/test_soft_arith.py`:

```python
"""The helper-free arithmetic gives exactly the portable code's answers:
on the host, with the switches forced on, the lookup, the accessors and
both printers still match spiflash."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from harness import check, name, parity, snapshot
from uspiflash import oracle
from uspiflash.levels import Field, Selection
from uspiflash.model import FAMILIES
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

#: Every switch forced on (Task 8 adds USF_SOFT_SHIFT).
SOFT = ["-DUSF_SOFT_MUL=1"]
CONFIGS = [
    Config(Selection.make("full")),
    Config(Selection.make("full", with_=["datasheets"])),
]


@pytest.mark.parametrize("config", CONFIGS, ids=name)
def test_lookup_and_accessors(tmp_path: Path, compilers: list[str], config: Config) -> None:
    snap = snapshot(config)
    sel = config.selection

    def answers(fam: int, data: bytes) -> list[int]:
        found = snap.lookup(FAMILIES[fam], data)
        return found if sel.has(Field.EXT) else [snap.entries[j].base for j in found]

    def lookup(fam: int, data: bytes) -> str:
        found = answers(fam, data)
        return f"{len(found)}\n" + "".join(f"{j} {snap.entries[j].base}\n" for j in found)

    def accessors(fam: int, data: bytes) -> str:
        return "".join(oracle.accessors(snap.entries[j].flash, sel) for j in answers(fam, data))

    check(tmp_path, compilers, config, {"L": lookup, "A": accessors}, defines=SOFT)


@parity
@pytest.mark.parametrize("config", CONFIGS, ids=name)
def test_printers(tmp_path: Path, compilers: list[str], config: Config) -> None:
    db = snapshot(config).database
    sel = config.selection

    def text(fam: int, data: bytes) -> str:
        return oracle.text(db, FAMILIES[fam], data, sel, opcodes=True)

    def json_text(fam: int, data: bytes) -> str:
        return oracle.json_text(db, FAMILIES[fam], data, sel)

    check(tmp_path, compilers, config, {"T": text, "J": json_text}, defines=SOFT)
```

In `tests/harness.py`:
- `Harness.build` gains `defines: Sequence[str] = ()`, appended to `extra`
  after `SANITIZE`. Its docstring ends "…, with ``defines`` (``-D``
  flags) added."
- `check` gains `defines: Sequence[str] = ()` and passes it on:
  `h = Harness.build(tmp / cc, config, cc, defines)`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_portability.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: FAIL for msp430 at `read`, `write`, `read:nor`, `write:nor` and
`read:nand`: "msp430: the library needs symbols from elsewhere:
__mspabi_mpyi". It skips where clang lacks a backend.

Run: `uv run pytest tests/test_soft_arith.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: PASS already, since the switch does not exist yet. It turns
into a real check in Step 4.

- [ ] **Step 3: Implement in the template**

In `src/uspiflash/templates/uspiflash.h.in`, right after
`typedef const USF_ROM uint8_t *usf__p;`, insert:

```c
/*
 * Arithmetic that calls no compiler helper, on any CPU.
 *
 * USF_SOFT_MUL is 1 where the CPU has no multiply instruction: rv32i and
 * rv32e without M or Zmmul, msp430 (whose multiplier is an optional
 * peripheral), the 8051, the 68HC08/S08, the 6502 and the Padauk. A
 * multiply by a table's row size (12, 5, 3, ...) calls __mulsi3,
 * __mspabi_mpyi or _mulint there, so USF__MUL shifts and adds instead.
 * Define USF_SOFT_MUL as 0 or 1 to override the guess.
 *
 * USF__NOINLINE keeps GCC and clang from inlining such a helper into a
 * caller with a constant argument: they would fold the loop back into the
 * multiply the helper is there to avoid.
 */
#if defined(__GNUC__)
#define USF__NOINLINE __attribute__((noinline))
#else
#define USF__NOINLINE
#endif

#ifndef USF_SOFT_MUL
#if (defined(__riscv) && !defined(__riscv_mul) && !defined(__riscv_zmmul)) \
    || defined(__MSP430__) || defined(__SDCC_mcs51) || defined(__SDCC_ds390) \
    || defined(__SDCC_hc08) || defined(__SDCC_s08) || defined(__SDCC_mos6502) \
    || defined(__SDCC_mos65c02) || defined(__SDCC_pdk13) || defined(__SDCC_pdk14) \
    || defined(__SDCC_pdk15)
#define USF_SOFT_MUL 1
#else
#define USF_SOFT_MUL 0
#endif
#endif

#if USF_SOFT_MUL
static USF__NOINLINE uint16_t usf__mul(uint16_t a, uint8_t k)
{
    uint16_t r = 0;
    for (; k; k >>= 1, a = (uint16_t)(a << 1))
        if (k & 1)
            r = (uint16_t)(r + a);
    return r;
}
#define USF__MUL(a, k) usf__mul((uint16_t)(a), (uint8_t)(k))
#else
#define USF__MUL(a, k) ((uint16_t)((uint16_t)(a) * (uint16_t)(k)))
#endif
```

Then replace each multiply by a constant that need not be a power of
two:

| Old | New |
|---|---|
| `usf__entries + (uint16_t)(c->entry * (uint16_t)USF_ENTRY_SIZE)` | `usf__entries + USF__MUL(c->entry, USF_ENTRY_SIZE)` |
| `usf__featsets + 3 * usf__row(c)[USF_E_FEAT]` | `usf__featsets + USF__MUL(usf__row(c)[USF_E_FEAT], 3)` |
| `usf__ops + (uint16_t)(USF_OP_SIZE * item[0])` | `usf__ops + USF__MUL(item[0], USF_OP_SIZE)` |
| `usf__dsrows + (uint16_t)(USF_DS_ROW * usf__u16(item))` | `usf__dsrows + USF__MUL(usf__u16(item), USF_DS_ROW)` |
| `usf__mfrs + USF_OFF_BYTES * i` | `usf__mfrs + USF__MUL(i, USF_OFF_BYTES)` |
| `p + 1 + USF_OFF_BYTES * i` (twice) | `p + 1 + USF__MUL(i, USF_OFF_BYTES)` |
| `names + USF_OFF_BYTES * i` (twice) | `names + USF__MUL(i, USF_OFF_BYTES)` |

(`USF_OFF_BYTES` is 2 or 3; `layout` picks it.) The multiplies by 2, 4 and
8 stay: every compiler shifts for them.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_portability.py tests/test_soft_arith.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: PASS. `test_soft_arith` now runs the shift-and-add path under
ASan and UBSan against spiflash.

Run: `uv run python -m uspiflash.sandbox -- uv run pytest -n {jobs}`
Expected: PASS. `test_compile` builds the header at `-O0` to `-O3` with
gcc and clang; `usf__mul` is compiled only where `USF_SOFT_MUL` is 1, so
no unused-function warning appears on the host.

- [ ] **Step 5: Check the reference ledger**

Run Part A Task 1 Step 4's command, then `git diff --stat sizes/`.
Expected: no change. None of the three reference targets takes the soft
path, and `USF__MUL`'s other expansion is the old expression; the
research run found `id`, `read` and `write` unchanged on Cortex-M0. If a
number moves anyway (a compiler treats the explicit `uint16_t` casts
differently), commit the regenerated files with this task and say so in
the commit message.

- [ ] **Step 6: Commit**

```bash
git add src/uspiflash/templates/uspiflash.h.in tests/harness.py \
  tests/test_portability.py tests/test_soft_arith.py
git commit -m "Row offsets without a multiply helper on CPUs without MUL

USF_SOFT_MUL (automatic on rv32i/rv32e, msp430 and SDCC's 8051, 68HC08,
6502 and Padauk ports) computes table row offsets by shift and add, in a
function GCC and clang may not inline back into a multiply. Tested on the
host with the switch forced on, and with clang for rv32i, rv32ec and
msp430 (issue #7).

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```

---

### Task 8: No variable shift or division helper: `usf__human`, `usf__dec2`, the SFDP reader

**Files:**
- Modify: `src/uspiflash/templates/uspiflash.h.in`
- Modify: `tests/test_portability.py` (every configuration),
  `tests/test_soft_arith.py` (`USF_SOFT_SHIFT`)
- Create: `tests/test_human.py`
- Modify (regenerated): `sizes/ledger.json`, `sizes/README.md`,
  `README.md`, `src/uspiflash/reference_sizes.json`

**Interfaces:**
- Consumes: `USF__NOINLINE` (Task 7).
- Produces: the template macro `USF_SOFT_SHIFT` (0 or 1,
  user-overridable). `usf_sfdp_read` reads each field from its byte
  address, so it sends more RDSFDP transactions, each still `5a` + 3
  address bytes + 1 dummy.

- [ ] **Step 1: Widen the portability test; add the soft-shift switch and a direct test of `usf__human`**

In `tests/test_portability.py`, replace `CONFIGS` and its comment with:

```python
#: clang (19 and 22, 2026-09-30) crashes compiling these for msp430
#: (issue #7); they are past what a 16-bit pointer addresses anyway (the
#: generated file's USF_ROM comment says so).
TOO_BIG_FOR_16_BIT = {"full+datasheet", "full+datasheets", "full+records+provenance+jep106"}
CONFIGS = list(measure.CONFIGS)
```

and replace `test_no_helper_is_needed` with:

```python
@pytest.mark.parametrize("cpu", sorted(PORTABLE))
@pytest.mark.parametrize(("name", "config"), CONFIGS, ids=[n for n, _ in CONFIGS])
def test_no_helper_is_needed(tmp_path: Path, cpu: str, name: str, config: Config) -> None:
    if PORTABLE[cpu] not in BACKENDS:
        pytest.skip(f"clang without the {PORTABLE[cpu]} backend")
    if cpu == "msp430" and name in TOO_BIG_FOR_16_BIT:
        pytest.skip("past a 16-bit address space; clang crashes (issue #7)")
    # Compiling and the undefined symbols are what matter; the linker may
    # be missing (lld), and msp430 has none.
    target = replace(measure.target(cpu, "clang"), link_flags=None)
    try:
        measure.measure(config, target, tmp_path)
    except MeasureError as e:
        pytest.fail(str(e).splitlines()[0])
```

In `tests/test_soft_arith.py`, `SOFT = ["-DUSF_SOFT_MUL=1", "-DUSF_SOFT_SHIFT=1"]`
and the comment "#: Every switch forced on.".

`tests/test_human.py`:

```python
"""usf__human prints a size as spiflash does (a whole number of the largest
unit, else bytes), with and without variable shifts."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from harness import compile_c, generate
from uspiflash.levels import Selection
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

VALUES = [0, 1, 1023, 1024, 1025, 1536, 3 << 10, 1 << 20, (1 << 20) + 1024, 5 << 20,
          1 << 30, 3 << 30, (1 << 30) + (1 << 20), 0x80000000, 0xFFFFFFFF, 0xFFFFFC00]


def human(n: int) -> str:
    """What spiflash prints (and the M1 C printed)."""
    for shift, unit in ((30, "G"), (20, "M"), (10, "K")):
        scale = 1 << shift
        if n >= scale and n % scale == 0:
            return f"{n >> shift} {unit}iB"
    return f"{n} B"


PROGRAM = """\
#include <stdio.h>
#define USF_IMPLEMENTATION
#include "uspiflash.h"
static void put(void *ctx, char ch) { (void)ctx; putchar(ch); }
int main(void)
{
    static const uint32_t v[] = {%s};
    unsigned i;
    for (i = 0; i < sizeof v / sizeof v[0]; i++) {
        usf__human(v[i], put, NULL);
        putchar('\\n');
    }
    return 0;
}
"""


@pytest.mark.parametrize("soft", ["0", "1"])
def test_human(tmp_path: Path, compilers: list[str], soft: str) -> None:
    generate(tmp_path, Config(Selection.make("describe")))
    src = tmp_path / "human.c"
    src.write_text(PROGRAM % ", ".join(f"{v}UL" for v in VALUES))
    for cc in compilers:
        exe = tmp_path / f"human-{cc}"
        compile_c(cc, [src], exe, [f"-I{tmp_path}", f"-DUSF_SOFT_SHIFT={soft}"])
        out = subprocess.run([str(exe)], capture_output=True, text=True, check=True).stdout
        assert out.splitlines() == [human(v) for v in VALUES], (cc, soft)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_portability.py tests/test_human.py -q -o addopts="--basetemp=tmp/pytest"`
Expected:
- `test_portability` FAILs for msp430 at `describe`, `full` and every
  `sfdp` configuration (`__mspabi_srll`, `__mspabi_slll`), and for rv32i
  and rv32ec at `full+datasheets` (`__udivsi3`);
- `test_human` PASSes for `soft=0` and `soft=1` alike: the switch does not
  exist yet. It pins the behaviour before Step 3 changes the code.

- [ ] **Step 3: `USF_SOFT_SHIFT` and `usf__human`**

In the template, after the `USF_SOFT_MUL` block from Task 7, add:

```c
/*
 * USF_SOFT_SHIFT is 1 where a 32-bit shift by a variable count calls a
 * helper (__mspabi_srll on msp430; SDCC's ports). There, usf__human
 * divides by 1024 one step at a time, through a function the optimiser
 * may not merge into one variable shift. Define it as 0 or 1 to
 * override the guess.
 */
#ifndef USF_SOFT_SHIFT
#if defined(__MSP430__) || defined(__SDCC)
#define USF_SOFT_SHIFT 1
#else
#define USF_SOFT_SHIFT 0
#endif
#endif
```

Replace `usf__human` with:

```c
#if USF_SOFT_SHIFT
/* n >> 10, as a function of its own: see USF__NOINLINE. */
static USF__NOINLINE uint32_t usf__shr10(uint32_t n)
{
    return n >> 10;
}

static void usf__human(uint32_t n, usf_putc_fn sink, void *ctx)
{
    static const USF_ROM char units[] = "KMG";
    uint8_t u = 0;
    while (u < 3 && n && !(n & 0x3FFUL)) {
        n = usf__shr10(n);
        u++;
    }
    usf__dec(n, sink, ctx);
    if (u) {
        sink(ctx, ' ');
        sink(ctx, units[u - 1]);
        usf__lit("iB", sink, ctx);
    } else {
        usf__lit(" B", sink, ctx);
    }
}
#else
static void usf__human(uint32_t n, usf_putc_fn sink, void *ctx)
{
    static const USF_ROM char units[] = "GMK";
    uint8_t u, shift = 30;
    for (u = 0; u < 3; u++, shift = (uint8_t)(shift - 10)) {
        uint32_t scale = (uint32_t)1 << shift;
        if (n >= scale && !(n & (scale - 1))) {
            usf__dec(n >> shift, sink, ctx);
            sink(ctx, ' ');
            sink(ctx, units[u]);
            usf__lit("iB", sink, ctx);
            return;
        }
    }
    usf__dec(n, sink, ctx);
    usf__lit(" B", sink, ctx);
}
#endif
```

(The `#else` branch is M1's function unchanged: the reference targets keep
their bytes.) The two agree because:
- dividing by 1024 while the value is non-zero and a multiple of 1024
  stops at the largest unit that divides `n`;
- that unit is at most G after three steps;
- a non-zero multiple of 1024 is at least 1024.

- [ ] **Step 4: `usf__dec2` without a subtract-ten loop**

Replace `usf__dec2`'s body (clang turns the loop into a division:
`__udivsi3` on rv32i):

```c
static void usf__dec2(uint8_t v, usf_putc_fn sink, void *ctx)
{
    /* Two digits. Not a subtract-ten loop: compilers turn that into a
     * division (__udivsi3 on rv32i). */
    if (v < 10)
        sink(ctx, '0');
    usf__dec(v, sink, ctx);
}
```

(`usf__dec` is compiled with TEXT or JSON; `usf__dec2` only with JSON's
datasheets, so it is always there.)

- [ ] **Step 5: The SFDP reader reads fields at their byte addresses**

Replace the mode table and its comment:

```c
/* Per fast-read mode (USF_SFDP_READ_* order): the byte offset in the BFPT
 * of its 16-bit settings (opcode in the high byte, mode clocks in 7:5, wait
 * states in 4:0), and the byte offset and mask of its support bit (in DW1;
 * for 2-2-2 and 4-4-4, in DW5). Byte offsets rather than bit numbers: each
 * is read from its own address, so no 32-bit value is shifted by a
 * variable count (a helper call on msp430 and SDCC's ports). */
static const USF_ROM uint8_t usf__sfdp_modes[6][3] = {
    {12, 2, 0x01}, {14, 2, 0x10}, {10, 2, 0x40}, {8, 2, 0x20},
    {22, 16, 0x01}, {26, 16, 0x10},
};
```

Each old entry `{dword, shift, bit}` became `{4 * (dword - 1) + shift / 8,
4 * (bit's dword - 1) + bit / 8 % 4, 1 << bit % 8}`. For example
`{4, 16, 20}`: settings at byte 14, support bit 20 of DW1 in byte 2, mask
0x10.

In `usf_sfdp_read`:
- the declaration becomes `uint32_t d, d1, ptr = 0;` (`d5` goes);
- delete the line `d5 = len >= 7 ? usf__sfdp_dw(bus, ptr + 16) : 0;`;
- the density's power of two becomes a doubling loop:

```c
            if (d >= 3 && d < 35)             /* 2^(d-3) bytes, doubling */
                for (out->size = 1; d > 3; d--)
                    out->size += out->size;
```

- the fast-read loop's test and read become:

```c
        if (len >= 7 && (usf__sfdp_dw(bus, ptr + m[1]) & m[2])) {
            d = usf__sfdp_dw(bus, ptr + m[0]);
```

- the erase loop's read becomes `d = usf__sfdp_dw(bus, ptr + 28 + 2 * (uint32_t)k);`
  (DW8's low half at 28, high at 30; DW9's at 32 and 34).

The rest of the function is unchanged. The fields are read from the low
bits of each dword read (`(uint8_t)d`, `(uint8_t)(d >> 8)`): constant
shifts only.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_portability.py tests/test_human.py tests/test_soft_arith.py tests/test_sfdp.py tests/test_json.py tests/test_print.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: PASS.
- `test_sfdp` decodes spiflash's 12 dumps and 4,500 damaged images
  byte-identically to `spiflash.sfdp`, and still sends only RDSFDP, 5
  bytes each.
- `test_json` covers `usf__dec2` (the `datasheets` dates).

Run: `uv run python -m uspiflash.sandbox -- uv run pytest -n {jobs}`
Expected: PASS, the Linux tool's `--sfdp` tests included.

- [ ] **Step 7: Regenerate the reference ledger; commit**

Run Part A Task 1 Step 4's command. Expected changes, from the research
run on Cortex-M0:
- `id+sfdp:nor` and `read+sfdp:nor` shrink (by 48 bytes there);
- `full+datasheets` and `full+sfdp+sfdp_dumps` shrink;
- nothing grows: the host targets keep M1's `usf__human`.

The regenerated files are the record; quote no number that is not in
them.

```bash
git add src/uspiflash/templates/uspiflash.h.in tests/test_portability.py \
  tests/test_soft_arith.py tests/test_human.py sizes README.md src/uspiflash/reference_sizes.json
git commit -m "No variable-shift or division helper on any CPU

The SFDP reader reads each field at its byte address instead of shifting
dwords by table-driven counts (smaller everywhere); usf__dec2 prints two
digits without a subtract loop (clang made it __udivsi3); and with
USF_SOFT_SHIFT (automatic on msp430 and SDCC) usf__human divides by 1024
through a non-inlined helper. clang for rv32i, rv32ec and msp430 now needs
no symbol at any measured configuration (issue #7).

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```

---

### Task 9: SDCC acceptance: `USF_REENTRANT` callbacks, every SDCC port measured

**Files:**
- Modify: `src/uspiflash/templates/uspiflash.h.in` (`USF_REENTRANT`, the
  two callback typedefs, the `USF_ROM` comment)
- Modify: `src/uspiflash/measure.py` (`MATRIX_CONFIGS`)
- Create: `tests/test_sdcc.py`
- Modify: `docs/generated-file.md` (a section "SDCC and CPUs without a
  multiplier")

**Interfaces:**
- Consumes: `measure.target`, `CPUS` (the SDCC ports), `measure.CONFIGS`.
- Produces:
  - the template macro `USF_REENTRANT`;
  - `measure.MATRIX_CONFIGS: tuple[str, ...] = ("id:nor", "read:nor", "write:nor", "describe:nor", "full:nor", "id+sfdp:nor")`:
    the configurations the matrix measures (Part C). They are SPI NOR
    first, and every one fits a 16-bit address space.

- [ ] **Step 1: Write the failing tests**

`tests/test_sdcc.py`:

```python
"""SDCC accepts the generated C (C99, every warning an error) on each of
its ports the matrix measures, in the default memory model, and the
implementation needs nothing but the port's calling-convention runtime
(spec amendments 17 and 19)."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest
from spiflash.enums import FlashType

from harness import generate
from uspiflash import measure
from uspiflash.levels import ChipFilter, Selection
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

SDCC = measure.find_tool("sdcc")
pytestmark = pytest.mark.skipif(SDCC is None, reason="sdcc not installed")
PORTS = [c.name for c in measure.CPUS.values() if c.sdcc is not None]
CONFIGS = [(n, c) for n, c in measure.CONFIGS if n in measure.MATRIX_CONFIGS]


def ports() -> set[str]:
    """The ports this SDCC has (its --version's first line lists them)."""
    if SDCC is None:
        return set()
    res = subprocess.run([SDCC, "--version"], capture_output=True, text=True, check=False)
    first = res.stdout.splitlines()[0]
    return set(first.split(":", 1)[1].split()[0].split("/"))


def test_the_matrix_configurations_are_spi_nor_and_measured() -> None:
    names = [n for n, _ in measure.CONFIGS]
    assert set(measure.MATRIX_CONFIGS) <= set(names)
    assert all(n.endswith(":nor") for n in measure.MATRIX_CONFIGS)


@pytest.mark.parametrize("port", PORTS)
@pytest.mark.parametrize(("name", "config"), CONFIGS, ids=[n for n, _ in CONFIGS])
def test_every_port_builds_and_links_only_its_runtime(
    tmp_path: Path, port: str, name: str, config: Config
) -> None:
    del name
    if port not in ports():
        pytest.skip(f"this SDCC has no {port} port")
    sizes = measure.measure(config, measure.target(port, "sdcc"), tmp_path)
    assert sizes.text > 0


USER = """\
#include <stdint.h>
#define USF_IMPLEMENTATION
#include "uspiflash.h"

static void put(void *ctx, char ch) USF_REENTRANT
{
    (void)ctx;
    (void)ch;
}

static void xfer(void *ctx, const uint8_t *tx, uint8_t txlen, uint8_t *rx, uint8_t rxlen)
    USF_REENTRANT
{
    uint8_t i;
    (void)ctx;
    (void)tx;
    (void)txlen;
    for (i = 0; i < rxlen; i++)
        rx[i] = 0xFF;
}

void run(void);
void run(void)
{
    usf_bus bus;
    usf_probe_result r;
    bus.xfer = xfer;
    bus.ctx = 0;
    usf_probe(&bus, &r);
    usf_print(r.chip, r.count, 0, put, 0);
}
"""


@pytest.mark.parametrize("port", PORTS)
def test_a_user_program_with_callbacks_compiles(tmp_path: Path, port: str) -> None:
    """The callbacks, declared USF_REENTRANT as the header asks, can be
    called through the library's function pointers."""
    if port not in ports():
        pytest.skip(f"this SDCC has no {port} port")
    config = Config(Selection.make("describe", chips=ChipFilter(types=(FlashType.NOR,))))
    generate(tmp_path, config)
    (tmp_path / "user.c").write_text(USER)
    t = measure.target(port, "sdcc")
    res = subprocess.run(
        [measure.tool("sdcc"), *t.flags, f"-I{tmp_path}", "-c", "user.c", "-o", "user.rel"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert not res.stderr
```

- [ ] **Step 2: Run them to see them fail (with SDCC installed)**

Install SDCC once for this task: `sudo apt-get install sdcc`. The host's
Debian gives 4.5.0. CI runs this file in the trixie matrix job (Part C,
Task 13).

Run: `uv run pytest tests/test_sdcc.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: FAIL with
- `AttributeError: module 'uspiflash.measure' has no attribute 'MATRIX_CONFIGS'`;
- then, once Step 3's constant exists, mcs51, hc08 and mos6502 fail on
  "error 92: Functions called via pointers must be 'reentrant'".

- [ ] **Step 3: Implement**

In `src/uspiflash/measure.py`, after `CONFIGS`:

```python
#: The configurations the size matrix measures on every toolchain and CPU:
#: SPI NOR first and only, every level, and the SFDP reader. Each fits a
#: 16-bit address space (the extras do not).
MATRIX_CONFIGS: tuple[str, ...] = (
    "id:nor",
    "read:nor",
    "write:nor",
    "describe:nor",
    "full:nor",
    "id+sfdp:nor",
)
```

In the template, after the `USF_ROM` block (before `USF_ID_MAX`), add:

```c
/*
 * SDCC's non-reentrant ports (the 8051, the 68HC08/S08, the 6502, the
 * Padauk) call through a pointer only a function declared __reentrant
 * when it takes more than a few bytes of arguments. The callbacks below
 * are declared so there, and yours must be too: define them with
 * USF_REENTRANT after the parameter list. Elsewhere it is empty (SDCC's
 * other ports are reentrant already, and reject the keyword).
 */
#ifndef USF_REENTRANT
#if defined(__SDCC_mcs51) || defined(__SDCC_ds390) || defined(__SDCC_hc08) \
    || defined(__SDCC_s08) || defined(__SDCC_mos6502) || defined(__SDCC_mos65c02) \
    || defined(__SDCC_pdk13) || defined(__SDCC_pdk14) || defined(__SDCC_pdk15)
#define USF_REENTRANT __reentrant
#else
#define USF_REENTRANT
#endif
#endif
```

The two typedefs become:

```c
typedef void (*usf_putc_fn)(void *ctx, char ch) USF_REENTRANT;
```

```c
typedef void (*usf_xfer_fn)(void *ctx, const uint8_t *tx, uint8_t txlen, uint8_t *rx,
                            uint8_t rxlen) USF_REENTRANT;
```

In the `USF_ROM` comment, add after its first sentence: "SDCC's 8051 port
is measured with `-DUSF_ROM=__code`."

In the comment above `USF_XFER` ("Whatever you define (USF_XFER,
USF_DELAY_US, USF_ROM, USF_NO_STDINT) must be the same…"), add
`USF_REENTRANT, USF_SOFT_MUL, USF_SOFT_SHIFT` to the list.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_sdcc.py tests/test_compile.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: PASS for mcs51, hc08, stm8, z80 and mos6502 at every matrix
configuration. `test_compile`'s C++ build is unaffected: the macro is
empty outside SDCC.

If a port reports a runtime symbol not in its `Cpu.runtime`, decide what
it is:
- a calling-convention or pointer-access routine: add it to that
  `Cpu.runtime` with the reason, and add it to the index's decision 17
  list for the maintainer;
- a multiply, divide or shift helper: fix the C, as Tasks 7–8 did.

If `describe:nor` or `full:nor` does not fit a port's 64 KiB, drop that
configuration for that port. Do it in `CONFIGS`' comprehension here, and
in Part C's matrix through a `Cpu.max_config` field with the reason.
Neither happened for mcs51, hc08, s08 or mos6502 in the research: `full`
is about 60 KiB.

- [ ] **Step 5: Document**

Append to `docs/generated-file.md`:

````markdown
## SDCC and CPUs without a multiplier

The generated file builds with SDCC (`--std-c99 --Werror`) on the 8051,
68HC08/S08, STM8, Z80 and 6502 ports, and with GCC and clang on CPUs that
have no multiply instruction or barrel shifter. It calls no multiply,
divide or shift helper on any of them.

- **Callbacks on SDCC's non-reentrant ports** (8051, 68HC08/S08, 6502,
  Padauk) must be declared reentrant. Write `USF_REENTRANT` after the
  parameter list:

  ```c
  static void my_putc(void *ctx, char ch) USF_REENTRANT { /* ... */ }
  ```

  It is `__reentrant` there and empty everywhere else.
- **Tables in program memory on the 8051:** define `USF_ROM` as `__code`.
- **`USF_SOFT_MUL` and `USF_SOFT_SHIFT`** are set automatically:
  - on rv32i/rv32e without M, msp430 and SDCC's ports, table row offsets
    are computed by shift and add;
  - on msp430 and SDCC, sizes are printed without a shift by a variable
    count.

  Define either as 0 or 1 to override. The generated file behaves
  identically either way (the tests run both).
- **What an SDCC port still links:** its own calling-convention runtime,
  such as the 8051's generic-pointer routines (`__gptrget`). The size
  matrix lists them per port (`sizes/matrix/README.md`).
````

Run: `uv run pytest tests/test_docs.py tests/test_docs_samples.py -q -o addopts="--basetemp=tmp/pytest"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/uspiflash/templates/uspiflash.h.in src/uspiflash/measure.py \
  tests/test_sdcc.py docs/generated-file.md
git commit -m "SDCC: reentrant callbacks; every port the matrix measures builds

USF_REENTRANT marks the putc and xfer callback types __reentrant on SDCC's
non-reentrant ports (8051, 68HC08/S08, 6502, Padauk), so the default model
compiles them; it is empty elsewhere. Tests build every matrix
configuration for mcs51, hc08, stm8, z80 and mos6502 with --Werror, and a
user program with USF_REENTRANT callbacks (issue #7).

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```

- [ ] **Step 7: Open the part's PR** (after the whole-part review)

```bash
git push -u origin m2b
gh pr create --title "M2b: CPUs, SDCC, arithmetic without helpers" \
  --body "Part B of the M2 plan (docs/superpowers/plans/2026-09-30-m2-b-portability.md).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
```
