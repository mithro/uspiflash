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

VALUES = [
    0,
    1,
    1023,
    1024,
    1025,
    1536,
    3 << 10,
    1 << 20,
    (1 << 20) + 1024,
    5 << 20,
    1 << 30,
    3 << 30,
    (1 << 30) + (1 << 20),
    0x80000000,
    0xFFFFFFFF,
    0xFFFFFC00,
]


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
