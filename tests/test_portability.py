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
