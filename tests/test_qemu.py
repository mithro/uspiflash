"""uspiflash-linux inside QEMU finds QEMU's emulated flash, and its SFDP.

``tools/qemu/run.py`` boots riscv64 Linux on QEMU's ``sifive_u`` (in docker),
binds its SPI flash, an ``is25wp256``, to spidev, and runs the tool with
``--opcodes --sfdp``. Slow (a docker image build the first time), so it runs
only with ``USPIFLASH_QEMU=1``; with that set, a missing docker is a failure,
not a skip. The rest are quick unit tests of ``run.py``."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from spiflash.db import database
from spiflash.enums import IdFamily

from harness import parity
from uspiflash import oracle
from uspiflash.levels import Selection

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
EXTRAS = ["sfdp", "sfdp_dumps", "datasheet", "datasheets", "records", "provenance"]


@pytest.mark.skipif(os.environ.get("USPIFLASH_QEMU") != "1", reason="set USPIFLASH_QEMU=1")
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


def load_run_py() -> ModuleType:
    """``tools/qemu/run.py``, a script, imported as a module."""
    spec = importlib.util.spec_from_file_location("qemu_run", ROOT / "tools/qemu/run.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_docker_build_timeout_is_a_clean_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``docker build`` that times out ends run.py with a message, as a
    ``docker run`` that does, not a traceback."""
    run_py = load_run_py()

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["docker", "image", "inspect"]:  # no cached image
            return subprocess.CompletedProcess(cmd, 1, "", "")
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        run_py.image()
    msg = str(exc.value.code)
    assert msg.startswith(f"docker build timed out after {run_py.BUILD_TIMEOUT} s: docker build ")
    assert "--tag uspiflash-qemu:" in msg
