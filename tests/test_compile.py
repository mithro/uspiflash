"""Every level, extra and single-type selection compiles warning-free with gcc
and clang, reads every table it carries, and needs nothing from any library."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
from spiflash.enums import FlashType

from harness import compile_c, generate, name, undefined_symbols
from uspiflash.levels import LEVELS, ChipFilter, Selection
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

ONE_TYPE = [ChipFilter(types=(FlashType.NOR,)), ChipFilter(types=(FlashType.NAND,))]
CONFIGS = [
    *(Config(Selection.make(level)) for level in LEVELS),
    Config(Selection.make("full", with_=["records", "provenance", "jep106"])),
    Config(Selection.make("id", with_=["jep106"])),
    # Fields added on their own.
    Config(Selection.make("read", with_=["descriptions"])),
    Config(Selection.make("describe", with_=["conflicts"])),
    # Single-type selections, whose counted tables can be empty.
    *(Config(Selection.make(level, chips=chips)) for chips in ONE_TYPE for level in LEVELS),
]


@pytest.mark.parametrize("config", CONFIGS, ids=name)
@pytest.mark.parametrize("opt", ["-O0", "-Os", "-O2", "-O3"])
def test_implementation_compiles_and_needs_no_symbols(
    tmp_path: Path, compilers: list[str], config: Config, opt: str
) -> None:
    generate(tmp_path, config)
    impl = tmp_path / "impl.c"
    impl.write_text('#define USF_IMPLEMENTATION\n#include "uspiflash.h"\n')
    for cc in compilers:
        obj = tmp_path / f"impl-{cc}.o"
        compile_c(cc, [impl], obj, [opt, "-c", "-ffreestanding", f"-I{tmp_path}"])
        assert undefined_symbols(obj) == [], f"{cc} {opt}"


@pytest.mark.parametrize("cxx", ["g++", "clang++"])
def test_header_and_implementation_compile_as_cpp(tmp_path: Path, cxx: str) -> None:
    if shutil.which(cxx) is None:
        pytest.skip(f"{cxx} not installed")
    generate(tmp_path, Config(Selection.make("full", with_=["jep106"])))
    src = tmp_path / "use.cpp"
    src.write_text(
        '#include "uspiflash.h"\n'  # declarations, as a C++ user sees them
        "#define USF_IMPLEMENTATION\n"
        '#include "uspiflash.h"\n'  # the guard makes this a no-op...
    )
    impl = tmp_path / "impl.cpp"
    impl.write_text('#define USF_IMPLEMENTATION\n#include "uspiflash.h"\n')  # ...so test both
    for unit in (src, impl):
        cmd = [cxx, "-std=c++11", "-Wall", "-Wextra", "-Wpedantic", "-Wundef", "-Werror", "-c"]
        cmd += [f"-I{tmp_path}", str(unit), "-o", str(unit.with_suffix(".o"))]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert res.returncode == 0, res.stderr
        assert not res.stderr, res.stderr
