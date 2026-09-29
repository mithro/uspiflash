"""Test helpers for the C side: generating headers and compiling them with
the strict flags. (Task 9 adds the harness driver.)"""

from __future__ import annotations

import functools
import subprocess
from typing import TYPE_CHECKING

from uspiflash import emit
from uspiflash.levels import LEVELS

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from uspiflash.provenance import Config

CFLAGS = ["-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Wundef", "-Werror"]


@functools.cache
def render(config: Config) -> str:
    """``emit.render(config)``, once per test session."""
    return emit.render(config)


def generate(tmp: Path, config: Config) -> Path:
    """Write the header ``config`` describes into ``tmp``; return its path."""
    path = tmp / config.filename
    path.write_text(render(config), encoding="ascii")
    return path


def compile_c(cc: str, sources: Sequence[str | Path], out: Path, extra: Sequence[str] = ()) -> None:
    """Compile with the strict flags; any diagnostic fails the test."""
    cmd = [cc, *CFLAGS, *extra, *(str(s) for s in sources), "-o", str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"{' '.join(cmd)}\n{res.stderr}"
    assert not res.stderr, f"{' '.join(cmd)}\n{res.stderr}"


def impl_source(config: Config) -> str:
    """A C file that compiles the implementation of ``config``'s header."""
    return f'#define {config.prefix.upper()}_IMPLEMENTATION\n#include "{config.filename}"\n'


def undefined_symbols(obj: Path) -> list[str]:
    """The symbols ``obj`` needs from elsewhere (``nm -u``, names only)."""
    res = subprocess.run(
        ["nm", "-u", "--format=just-symbols", str(obj)],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.split()


def name(config: Config) -> str:
    """A test id: the level, then ``+extra``, ``-removed`` and ``:type``
    filters, and ``@prefix`` when the prefix is not ``usf``."""
    sel = config.selection
    base = LEVELS[sel.level]
    return "".join(
        [
            sel.level,
            *(f"+{f}" for f in sorted(sel.fields - base)),
            *(f"-{f}" for f in sorted(base - sel.fields)),
            *(f":{t.value}" for t in sel.chips.types),
            *([f"@{config.prefix}"] if config.prefix != "usf" else []),
        ]
    )
