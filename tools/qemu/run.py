"""Boot riscv64 Linux under QEMU's ``sifive_u`` and run uspiflash-linux on its
emulated SPI flash (an ``is25wp256``, with SFDP) through spidev.

Everything runs in a docker image (``tools/qemu/Dockerfile``), so the host
needs only docker: the image build, the guest build (``build_image.py``) and
QEMU. Every ``docker run`` is limited as ``uspiflash.sandbox`` would limit a
local job. Files go only under ``tmp/qemu/`` in the repository.

Prints the guest tool's output (the lines between ``=== uspiflash-linux ===``
and ``=== end ===``, without the ``=== exit N ===`` line, with ``\\r\\n`` turned
into ``\\n``) and exits with the tool's exit code, or 3 if the markers never
appear. ``--verbose`` boots without ``quiet`` and copies the whole console to
stderr.

Usage::

    uv run tools/qemu/run.py [--verbose]
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from uspiflash import ledger
from uspiflash.cli import main as uspiflash_main
from uspiflash.sandbox import current_limits

ROOT = Path(__file__).resolve().parent.parent.parent
HERE = ROOT / "tools/qemu"
MAKEFILE = ROOT / "examples/linux/Makefile"
OUT = ROOT / "tmp/qemu"
#: The image run.py builds and keeps, as a cache of the packages (about 1 GB).
TAG = "uspiflash-qemu"
#: The riscv64 packages the guest is made of, from ledger.SNAPSHOT.
KERNEL = "6.12.107+deb13-riscv64"
KERNEL_VERSION = "6.12.107-1"
BUSYBOX_VERSION = "1:1.37.0-6+b9"
#: How long the guest may take, from power-on to power-off.
TIMEOUT = 300
BEGIN = "=== uspiflash-linux ==="
END = "=== end ==="
EXIT = re.compile(r"^=== exit (\d+) ===$")
#: The exit code when the guest never prints the markers.
NO_MARKERS = 3


def make_variable(text: str, name: str) -> list[str]:
    """The words of the Makefile's ``name = ...`` or ``override name += ...``
    line, continuation lines included."""
    joined = text.replace("\\\n", " ")
    pattern = rf"^(?:override )?{name}\s*\+?=(.*)$"
    match = re.search(pattern, joined, re.MULTILINE)
    if match is None:
        msg = f"{MAKEFILE} has no {name}"
        raise SystemExit(msg)
    return shlex.split(match.group(1))


def docker_run(*args: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """``docker run --rm`` with the sandbox's limits, in the image."""
    limits = current_limits()
    cmd = [
        "docker",
        "run",
        "--rm",
        f"--memory={limits.memory_bytes}",
        f"--memory-swap={limits.memory_bytes}",
        f"--cpus={limits.cpus}",
        "--pids-limit=512",
        *args,
    ]
    return subprocess.run(
        cmd, capture_output=True, text=True, errors="replace", check=False, timeout=timeout
    )


def check(res: subprocess.CompletedProcess[str], what: str) -> None:
    """Exit with ``res``'s output if it failed."""
    if res.returncode != 0:
        sys.stderr.write(res.stdout + res.stderr)
        msg = f"{what} failed (exit {res.returncode})"
        raise SystemExit(msg)


def version() -> str:
    """``uspiflash --version``'s line, as the Makefile's ``VERSION``."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
        uspiflash_main(["--version"])
    return out.getvalue().strip()


def build_image() -> None:
    """The docker image, then the guest's kernel and initramfs in ``OUT``."""
    makefile = MAKEFILE.read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    header = OUT / "uspiflash.h"
    if uspiflash_main(["generate", "-o", str(header), *make_variable(makefile, "GENERATE")]):
        msg = "uspiflash generate failed"
        raise SystemExit(msg)

    limits = current_limits()
    build_args = {
        "IMAGE": ledger.IMAGE,
        "SNAPSHOT": ledger.SNAPSHOT,
        "KERNEL": KERNEL,
        "KERNEL_VERSION": KERNEL_VERSION,
        "BUSYBOX_VERSION": BUSYBOX_VERSION,
    }
    res = subprocess.run(
        [
            "docker",
            "build",
            f"--memory={limits.memory_bytes}",
            "--tag",
            TAG,
            *(f"--build-arg={k}={v}" for k, v in build_args.items()),
            str(HERE),
        ],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    check(res, "docker build")

    res = docker_run(
        f"--user={os.getuid()}:{os.getgid()}",
        f"--volume={ROOT}:/src:ro",
        f"--volume={OUT}:/out",
        TAG,
        "python3",
        "/src/tools/qemu/build_image.py",
        "--source=/src/examples/linux/uspiflash-linux.c",
        "--include=/out",
        "--init=/src/tools/qemu/init",
        f'--version-define="{version()}"',
        *(f"--cflag={f}" for f in make_variable(makefile, "CFLAGS")),
        "--out=/out",
    )
    check(res, "build_image.py")


def boot(*, verbose: bool) -> str:
    """Boot the guest; its console output, ``\\r\\n`` turned into ``\\n``."""
    append = "console=ttySIF0 panic=-1" if verbose else "console=ttySIF0 quiet loglevel=0 panic=-1"
    res = docker_run(
        f"--volume={OUT}:/out:ro",
        TAG,
        "timeout",
        str(TIMEOUT),
        "qemu-system-riscv64",
        "-M",
        "sifive_u",
        "-nographic",
        "-bios",
        "default",
        "-kernel",
        "/out/Image",
        "-initrd",
        "/out/initramfs.cpio.gz",
        "-append",
        append,
        "-no-reboot",
        timeout=TIMEOUT + 60,
    )
    console = (res.stdout + res.stderr).replace("\r\n", "\n")
    if verbose:
        sys.stderr.write(console)
    return console


def extract(console: str) -> tuple[str, int]:
    """The tool's output and exit code from the console, or ``("",
    NO_MARKERS)`` if the markers are missing."""
    lines = console.split("\n")
    if BEGIN not in lines or END not in lines:
        return "", NO_MARKERS
    body = lines[lines.index(BEGIN) + 1 : lines.index(END)]
    if not body or (match := EXIT.match(body[-1])) is None:
        return "", NO_MARKERS
    return "".join(f"{line}\n" for line in body[:-1]), int(match.group(1))


def main() -> int:
    """Build, boot, print the tool's output, exit with its code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--verbose", action="store_true", help="the whole console, to stderr")
    args = parser.parse_args()
    build_image()
    output, code = extract(boot(verbose=args.verbose))
    sys.stdout.write(output)
    if code == NO_MARKERS:
        sys.stderr.write("run.py: the guest never printed the markers\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
