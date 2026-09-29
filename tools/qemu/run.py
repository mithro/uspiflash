"""Boot riscv64 Linux under QEMU's ``sifive_u`` and run uspiflash-linux on its
emulated SPI flash (an ``is25wp256``, with SFDP) through spidev.

Everything runs in a docker image (``tools/qemu/Dockerfile``), so the host
needs only docker: the image build, the guest build (``build_image.py``) and
QEMU. Every ``docker run`` is limited as ``uspiflash.sandbox`` would limit a
local job. Files go only under ``tmp/qemu/`` in the repository.

Prints the guest tool's output (the lines between ``=== uspiflash-linux ===``
and ``=== end ===``, without the ``=== exit N ===`` line, with ``\\r\\n`` turned
into ``\\n``) and exits with the tool's exit code, or 3 if the markers never
appear; then the end of the console and docker's exit code go to stderr.
``--verbose`` boots without ``quiet`` and copies the whole console to stderr.

Usage::

    uv run tools/qemu/run.py [--verbose]
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
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
#: The image's repository. Its tag is a hash of the Dockerfile and the build
#: arguments, and an image with that tag is used as it is, not rebuilt: it
#: is kept as a cache of the packages (about 720 MB), and CI restores it.
REPOSITORY = "uspiflash-qemu"
#: The riscv64 packages the guest is made of, from ledger.SNAPSHOT, and the
#: sha256s of their .debs, which the Dockerfile checks.
KERNEL = "6.12.107+deb13-riscv64"
KERNEL_VERSION = "6.12.107-1"
KERNEL_SHA256 = "abe9f65d74b434692149482b031db7a2aaf832921e09f69f775293c0e0c5799c"
BUSYBOX_VERSION = "1:1.37.0-6+b9"
BUSYBOX_SHA256 = "4add476d2b185c5b487c285b38d790f0881a7e4a8e2ddde835f917e770eb8633"
#: How long the guest may take, from power-on to power-off.
TIMEOUT = 300
#: How long building the guest may take.
BUILD_TIMEOUT = 600
#: The boot container's name, so it can be killed if docker hangs.
BOOT_CONTAINER = f"uspiflash-qemu-boot-{os.getpid()}"
BEGIN = "=== uspiflash-linux ==="
END = "=== end ==="
EXIT = re.compile(r"^=== exit (\d+) ===$")
#: The exit code when the guest never prints the markers.
NO_MARKERS = 3
#: How much of the console to show when the markers are missing.
TAIL = 200


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


def docker_run(
    *args: str, timeout: int, name: str | None = None
) -> subprocess.CompletedProcess[str]:
    """``docker run --rm`` with the sandbox's limits. After ``timeout``
    seconds the container (named ``name``, if given) is killed."""
    limits = current_limits()
    cmd = [
        "docker",
        "run",
        "--rm",
        *([f"--name={name}"] if name else []),
        f"--memory={limits.memory_bytes}",
        f"--memory-swap={limits.memory_bytes}",
        f"--cpus={limits.cpus}",
        "--pids-limit=512",
        *args,
    ]
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        if name:
            subprocess.run(["docker", "kill", name], check=False)
        msg = f"docker run timed out after {timeout} s: {shlex.join(cmd)}"
        raise SystemExit(msg) from None


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


def image() -> str:
    """The image, built unless an image of its tag exists."""
    build_args = {
        "IMAGE": ledger.IMAGE,
        "SNAPSHOT": ledger.SNAPSHOT,
        "KERNEL": KERNEL,
        "KERNEL_VERSION": KERNEL_VERSION,
        "KERNEL_SHA256": KERNEL_SHA256,
        "BUSYBOX_VERSION": BUSYBOX_VERSION,
        "BUSYBOX_SHA256": BUSYBOX_SHA256,
    }
    key = hashlib.sha256((HERE / "Dockerfile").read_bytes())
    key.update(repr(sorted(build_args.items())).encode())
    tag = f"{REPOSITORY}:{key.hexdigest()[:16]}"
    inspect = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", tag],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspect.returncode == 0:
        return tag
    # Not limited: `docker build` (BuildKit) ignores --memory. The build is
    # apt-get and dpkg-deb only.
    res = subprocess.run(
        [
            "docker",
            "build",
            "--tag",
            tag,
            *(f"--build-arg={k}={v}" for k, v in build_args.items()),
            str(HERE),
        ],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        timeout=BUILD_TIMEOUT,
    )
    check(res, "docker build")
    return tag


def build_guest(tag: str) -> None:
    """The guest's kernel and initramfs in ``OUT``."""
    makefile = MAKEFILE.read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    header = OUT / "uspiflash.h"
    if uspiflash_main(["generate", "-o", str(header), *make_variable(makefile, "GENERATE")]):
        msg = "uspiflash generate failed"
        raise SystemExit(msg)
    res = docker_run(
        f"--user={os.getuid()}:{os.getgid()}",
        f"--volume={ROOT}:/src:ro",
        f"--volume={OUT}:/out",
        tag,
        "python3",
        "/src/tools/qemu/build_image.py",
        "--source=/src/examples/linux/uspiflash-linux.c",
        "--include=/out",
        "--init=/src/tools/qemu/init",
        f'--version-define="{version()}"',
        *(f"--cflag={f}" for f in make_variable(makefile, "CFLAGS")),
        "--out=/out",
        timeout=BUILD_TIMEOUT,
    )
    check(res, "build_image.py")


def boot(tag: str, *, verbose: bool) -> tuple[str, int]:
    """Boot the guest: its console output, ``\\r\\n`` turned into ``\\n``,
    and ``docker run``'s exit code."""
    append = "console=ttySIF0 panic=-1" if verbose else "console=ttySIF0 quiet loglevel=0 panic=-1"
    res = docker_run(
        f"--volume={OUT}:/out:ro",
        tag,
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
        name=BOOT_CONTAINER,
    )
    console = (res.stdout + res.stderr).replace("\r\n", "\n")
    if verbose:
        sys.stderr.write(console)
    return console, res.returncode


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
    tag = image()
    build_guest(tag)
    console, docker_code = boot(tag, verbose=args.verbose)
    output, code = extract(console)
    sys.stdout.write(output)
    if code == NO_MARKERS or docker_code != 0:
        if not args.verbose:
            tail = console.split("\n")[-TAIL:]
            sys.stderr.write(f"run.py: the console's last {len(tail)} lines:\n")
            sys.stderr.write("\n".join(tail) + "\n")
        sys.stderr.write(f"run.py: docker run exited {docker_code}\n")
    if code == NO_MARKERS:
        sys.stderr.write("run.py: the guest never printed the markers\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
