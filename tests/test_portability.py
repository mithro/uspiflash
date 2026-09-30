"""The generated library calls no compiler helper on CPUs without a
multiplier or a barrel shifter (spec amendment 18): clang for rv32i,
rv32ec and msp430, which every clang can build for without a C library.
Also covers the GCC cross compilers for cortex-m0, cortex-m3, cortex-a9,
rv32i and rv32ec (issue #7): GCC on Thumb-1 can need libgcc helpers that
clang does not."""

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
#: clang (19 and 22, 2026-09-30) crashes compiling these for msp430
#: (issue #7); they are past what a 16-bit pointer addresses anyway (the
#: generated file's USF_ROM comment says so).
TOO_BIG_FOR_16_BIT = {"full+datasheet", "full+datasheets", "full+records+provenance+jep106"}
CONFIGS = list(measure.CONFIGS)


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


#: GCC cross compilers and the CPUs they build for (Debian's names).
GCC_CROSS = {
    "cortex-m0": "arm-none-eabi-gcc",
    "cortex-m3": "arm-none-eabi-gcc",
    "cortex-a9": "arm-none-eabi-gcc",
    "rv32i": "riscv64-unknown-elf-gcc",
    "rv32ec": "riscv64-unknown-elf-gcc",
}


@pytest.mark.parametrize("cpu", sorted(GCC_CROSS))
@pytest.mark.parametrize(("name", "config"), measure.CONFIGS, ids=[n for n, _ in measure.CONFIGS])
def test_no_helper_with_gcc(tmp_path: Path, cpu: str, name: str, config: Config) -> None:
    del name
    cc = GCC_CROSS[cpu]
    if measure.find_tool(cc) is None:
        pytest.skip(f"{cc} not installed")
    target = replace(measure.target(cpu, cc), link_flags=None)
    try:
        measure.measure(config, target, tmp_path)
    except MeasureError as e:
        pytest.fail(str(e).splitlines()[0])
