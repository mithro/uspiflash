"""Every level, extra and single-type selection compiles warning-free with gcc
and clang, reads every table it carries, and needs nothing from any library."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
from spiflash.db import database
from spiflash.enums import FlashType

from harness import compile_c, generate, impl_source, name, undefined_symbols
from uspiflash.levels import LEVELS, ChipFilter, Selection
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

ONE_TYPE = [ChipFilter(types=(FlashType.NOR,)), ChipFilter(types=(FlashType.NAND,))]
_BARE = next(f for f in database().flashes if not f.datasheets)
#: One chip id without a datasheet: DS_COUNT is 0 (every type has chips with one).
NO_DATASHEET = ChipFilter(ids=(_BARE.id,), types=(_BARE.type,), families=(_BARE.family,))
CONFIGS = [
    *(Config(Selection.make(level)) for level in LEVELS),
    Config(Selection.make("full", with_=["records", "provenance", "jep106"])),
    Config(Selection.make("id", with_=["jep106"])),
    # Fields added on their own.
    Config(Selection.make("read", with_=["descriptions"])),
    Config(Selection.make("describe", with_=["conflicts"])),
    # Conflicts without a printer (stored nowhere).
    Config(Selection.make("write", with_=["conflicts"])),
    # JSON without TEXT (Task 11).
    Config(Selection.make("write", with_=["json"])),
    Config(Selection.make("full", without=["text"])),
    # Datasheets (Task 11b), and with no datasheet among the chips.
    Config(Selection.make("full", with_=["datasheet"])),
    Config(Selection.make("full", with_=["datasheets"])),
    Config(Selection.make("describe", with_=["datasheet"])),
    Config(Selection.make("full", with_=["datasheet", "datasheets"], chips=ONE_TYPE[1])),
    Config(Selection.make("full", with_=["datasheet", "datasheets"], chips=NO_DATASHEET)),
    # A renamed header: every symbol and table under another prefix.
    Config(Selection.make("full"), "fl", "flashid.h"),
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
    impl.write_text(impl_source(config))
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
        '#include "uspiflash.h"\n'  # then the implementation (stb style)
    )
    impl = tmp_path / "impl.cpp"
    impl.write_text('#define USF_IMPLEMENTATION\n#include "uspiflash.h"\n')  # or on its own
    for unit in (src, impl):
        cmd = [cxx, "-std=c++11", "-Wall", "-Wextra", "-Wpedantic", "-Wundef", "-Werror", "-c"]
        cmd += [f"-I{tmp_path}", str(unit), "-o", str(unit.with_suffix(".o"))]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert res.returncode == 0, res.stderr
        assert not res.stderr, res.stderr


STB = """\
#include "uspiflash.h"
#include "uspiflash.h"
#define USF_IMPLEMENTATION
#include "uspiflash.h"
#include "uspiflash.h"
"""


def test_declarations_then_implementation_in_one_file(tmp_path: Path, compilers: list[str]) -> None:
    """The stb pattern: the declarations, then USF_IMPLEMENTATION and the
    file again, compile the implementation exactly once; more includes of
    either kind change nothing."""
    generate(tmp_path, Config(Selection.make("full")))
    unit = tmp_path / "stb.c"
    unit.write_text(STB)
    for cc in compilers:
        obj = tmp_path / f"stb-{cc}.o"
        compile_c(cc, [unit], obj, ["-c", "-ffreestanding", f"-I{tmp_path}"])
        assert undefined_symbols(obj) == [], cc
        res = subprocess.run(
            ["nm", "--defined-only", "--format=just-symbols", str(obj)],
            capture_output=True,
            text=True,
            check=True,
        )
        assert {"usf_lookup", "usf_probe", "usf_print"} <= set(res.stdout.split()), cc


def test_has_feature_is_0_past_the_last_feature(tmp_path: Path, compilers: list[str]) -> None:
    # A feature number past USF_FEATURE_COUNT must not read beyond the
    # chip's 3-byte feature set (the next row's bits would show through).
    config = Config(Selection.make("read"))
    generate(tmp_path, config)
    src = tmp_path / "features.c"
    src.write_text(
        impl_source(config)
        + """
int main(void)
{
    usf_chip c;
    unsigned f, bad = 0;
    c.base = 0;
    for (c.entry = 0; c.entry < USF_ENTRY_COUNT; c.entry++)
        for (f = USF_FEATURE_COUNT; f < 256; f++)
            bad += usf_has_feature(&c, (uint8_t)f);
    return bad != 0;
}
"""
    )
    for cc in compilers:
        exe = tmp_path / f"features-{cc}"
        compile_c(cc, [src], exe)
        assert subprocess.run([str(exe)], check=False).returncode == 0, cc


@pytest.mark.parametrize("config", CONFIGS, ids=name)
def test_every_table_is_read(tmp_path: Path, compilers: list[str], config: Config) -> None:
    """Compiled as the main file, so -Wunused-const-variable sees the tables:
    one that nothing reads fails here. (Neither compiler warns about an
    unused table in an included header, which is how the other tests
    compile it.)"""
    header = generate(tmp_path, config)
    impl = f"-D{config.prefix.upper()}_IMPLEMENTATION"
    for cc in compilers:
        obj = tmp_path / f"main-{cc}.o"
        compile_c(cc, [header], obj, ["-c", "-ffreestanding", "-x", "c", impl])


MACRO_XFER = """\
#include <stdint.h>
struct usf_bus { int unused; };
void my_xfer(const uint8_t *tx, uint8_t txlen, uint8_t *rx, uint8_t rxlen);
#define USF_XFER(bus, tx, txlen, rx, rxlen) ((void)(bus), my_xfer((tx), (txlen), (rx), (rxlen)))
#define USF_IMPLEMENTATION
#include "uspiflash.h"
"""


def test_probe_through_a_macro_transport(tmp_path: Path, compilers: list[str]) -> None:
    generate(tmp_path, Config(Selection.make("id")))
    unit = tmp_path / "macro.c"
    unit.write_text(MACRO_XFER)
    for cc in compilers:
        obj = tmp_path / f"macro-{cc}.o"
        compile_c(cc, [unit], obj, ["-Os", "-c", "-ffreestanding", f"-I{tmp_path}"])
        assert undefined_symbols(obj) == ["my_xfer"]


DELAY_HOOK = """\
#include <stdio.h>
#include <stdint.h>
static void my_delay(unsigned us) { printf("delay %u\\n", us); }
#define USF_DELAY_US(us) my_delay(us)
#define USF_IMPLEMENTATION
#include "uspiflash.h"

static void xfer(void *ctx, const uint8_t *tx, uint8_t txlen, uint8_t *rx, uint8_t rxlen)
{
    uint8_t i;
    (void)ctx;
    (void)txlen;
    for (i = 0; i < rxlen; i++)
        rx[i] = 0xFF;
    printf("xfer %02x\\n", tx[0]);
}

int main(void)
{
    usf_bus bus;
    usf_probe_result r;
    bus.xfer = xfer;
    bus.ctx = NULL;
    return usf_probe(&bus, &r);
}
"""


def test_the_probe_waits_trs1_after_res(tmp_path: Path, compilers: list[str]) -> None:
    """USF_DELAY_US(30) runs right after RES, before any other command."""
    generate(tmp_path, Config(Selection.make("id")))
    src = tmp_path / "delay.c"
    src.write_text(DELAY_HOOK)
    for cc in compilers:
        exe = tmp_path / f"delay-{cc}"
        compile_c(cc, [src], exe, [f"-I{tmp_path}"])
        res = subprocess.run([str(exe)], capture_output=True, text=True, check=True)
        assert res.stdout.splitlines()[:3] == ["xfer ab", "delay 30", "xfer 9f"], cc
        assert res.stdout.count("delay") == 1, cc
