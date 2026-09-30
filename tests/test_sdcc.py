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
CONFIGS = [(n, c) for n, c in measure.CONFIGS if n in measure.SMALL_CONFIGS]


def ports() -> set[str]:
    """The ports this SDCC has (its --version's first line lists them)."""
    if SDCC is None:
        return set()
    res = subprocess.run([SDCC, "--version"], capture_output=True, text=True, check=False)
    first = res.stdout.splitlines()[0]
    return set(first.split(":", 1)[1].split()[0].split("/"))


def test_the_small_configurations_are_spi_nor_and_measured() -> None:
    names = [n for n, _ in measure.CONFIGS]
    assert set(measure.SMALL_CONFIGS) <= set(names)
    assert all(n.endswith(":nor") for n in measure.SMALL_CONFIGS)
    assert [n for n, _ in measure.configs_for("mcs51")] == list(measure.SMALL_CONFIGS)
    assert measure.configs_for("cortex-m0") == list(measure.CONFIGS)


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
