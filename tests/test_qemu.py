"""uspiflash-linux inside QEMU finds QEMU's emulated flash, and its SFDP.

``tools/qemu/run.py`` boots riscv64 Linux on QEMU's ``sifive_u`` (in docker),
binds its SPI flash, an ``is25wp256``, to spidev, and runs the tool with
``--opcodes --sfdp``. Slow (a docker image build the first time), so it runs
only with ``USPIFLASH_QEMU=1``; with that set, a missing docker is a failure,
not a skip."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from spiflash.db import database
from spiflash.enums import IdFamily

from harness import parity
from uspiflash import oracle
from uspiflash.levels import Selection

ROOT = Path(__file__).resolve().parent.parent
EXTRAS = ["sfdp", "sfdp_dumps", "datasheet", "datasheets", "records", "provenance"]
pytestmark = pytest.mark.skipif(
    os.environ.get("USPIFLASH_QEMU") != "1", reason="set USPIFLASH_QEMU=1"
)


@parity
def test_tool_in_qemu_describes_the_emulated_flash() -> None:
    if shutil.which("docker") is None:
        pytest.fail("USPIFLASH_QEMU=1 is set, but docker is not installed")
    res = subprocess.run(
        [sys.executable, str(ROOT / "tools/qemu/run.py")],
        capture_output=True,
        text=True,
        check=False,
        timeout=1800,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    (chip,) = database().lookup("9d7019")
    assert chip.sfdp is not None
    # m25p80.c:1419-1431 at 81ce3a87: the id, zeros to 6 bytes, then idle
    # NOPs, which read 0x00 too.
    rdid = bytes.fromhex("9d7019") + bytes(7)
    sel = Selection.make("full", with_=EXTRAS)
    text = oracle.text(database(), IdFamily.JEDEC, rdid, sel, opcodes=True)
    assert res.stdout == text + oracle.sfdp_fields(chip.sfdp.data)
