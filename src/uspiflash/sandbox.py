"""Run a command in a resource-limited systemd scope, with limits sized from
the machine's *current* load, so test suites cannot exhaust memory or make
the desktop unresponsive.

Memory: what is available now, less a reserve for everything else (4 GiB or
15 % of RAM, whichever is larger), clamped to 1-16 GiB. CPUs: all of them,
less the current one-minute load and two for the desktop, at least one. When
the kernel reports memory pressure (PSI ``some avg10`` above 10 %), both are
halved. Swap is disallowed, so a runaway job is killed rather than thrashing.

Usage::

    uv run python -m uspiflash.sandbox -- uv run pytest -n {jobs}

``{jobs}`` becomes the CPU count the limits allow.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

GIB = 1 << 30


@dataclass(frozen=True)
class Limits:
    """How much of the machine one sandboxed command may use."""

    memory_bytes: int
    cpus: int
    tasks: int = 1024

    def properties(self) -> list[str]:
        """The systemd resource-control properties for these limits."""
        return [
            f"MemoryMax={self.memory_bytes}",
            "MemorySwapMax=0",
            f"CPUQuota={self.cpus * 100}%",
            f"TasksMax={self.tasks}",
        ]


def _meminfo(text: str) -> dict[str, int]:
    """``/proc/meminfo`` as bytes by field name."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        fields = rest.split()
        if fields:
            out[key.strip()] = int(fields[0]) * 1024
    return out


def _pressure(text: str) -> float:
    """PSI's ``some avg10`` percentage, 0 when unavailable."""
    for line in text.splitlines():
        if line.startswith("some"):
            for part in line.split():
                if part.startswith("avg10="):
                    return float(part.removeprefix("avg10="))
    return 0.0


def compute_limits(meminfo: str, loadavg: str, pressure: str, ncpu: int) -> Limits:
    """Limits from the text of ``/proc/meminfo``, ``/proc/loadavg`` and
    ``/proc/pressure/memory`` and the CPU count."""
    mem = _meminfo(meminfo)
    reserve = max(4 * GIB, mem["MemTotal"] * 15 // 100)
    memory = min(max(mem["MemAvailable"] - reserve, GIB), 16 * GIB)
    cpus = max(1, ncpu - math.ceil(float(loadavg.split(maxsplit=1)[0])) - 2)
    if _pressure(pressure) > 10.0:
        memory = max(memory // 2, GIB)
        cpus = max(1, cpus // 2)
    return Limits(memory, cpus)


def current_limits() -> Limits:
    """Limits for this machine, right now."""
    psi = Path("/proc/pressure/memory")
    return compute_limits(
        Path("/proc/meminfo").read_text(encoding="ascii"),
        Path("/proc/loadavg").read_text(encoding="ascii"),
        psi.read_text(encoding="ascii") if psi.exists() else "",
        os.cpu_count() or 1,
    )


def wrap(argv: Sequence[str], limits: Limits, timeout: int) -> list[str]:
    """``argv`` run in a transient systemd user scope with ``limits``, at low
    priority, killed after ``timeout`` seconds. ``{jobs}`` arguments become
    the CPU count."""
    inner = [str(limits.cpus) if a == "{jobs}" else a for a in argv]
    return [
        "systemd-run",
        "--user",
        "--scope",
        "--quiet",
        "--collect",
        *(f"-p{p}" for p in limits.properties()),
        "nice",
        "-n",
        "10",
        "timeout",
        "--kill-after=30",
        str(timeout),
        *inner,
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m uspiflash.sandbox [--timeout S] [--print-limits] -- CMD...``"""
    ap = argparse.ArgumentParser(prog="python -m uspiflash.sandbox")
    ap.add_argument("--timeout", type=int, default=3600, help="seconds (default 3600)")
    ap.add_argument("--print-limits", action="store_true")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    limits = current_limits()
    if args.print_limits:
        print(f"memory {limits.memory_bytes // (1 << 20)} MiB, cpus {limits.cpus}")
    cmd = [a for a in args.command if a != "--"]
    if not cmd:
        return 0
    if shutil.which("systemd-run") is None:
        msg = "systemd-run is not available: refusing to run unsandboxed"
        raise SystemExit(msg)
    return subprocess.run(wrap(cmd, limits, args.timeout), check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
