"""Test helpers for the C side: generating headers, compiling them with the
strict flags, and building and driving tests/c/harness.c."""

from __future__ import annotations

import functools
import os
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import spiflash
from spiflash.db import database

from uspiflash import VERIFIED_SPIFLASH, emit, layout
from uspiflash.levels import LEVELS, ChipFilter
from uspiflash.model import FAMILIES, Snapshot, reaching_probes

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from uspiflash.provenance import Config

#: Set to 1 to run the parity tests whatever spiflash is installed (the
#: daily drift alarm, .github/workflows/spiflash-latest.yml, does).
FORCE_PARITY = "USPIFLASH_FORCE_PARITY"


def parity_skip_reason() -> str | None:
    """Why the parity tests (the C's printed output against spiflash's) are
    skipped, or ``None`` when they run: they run against the spiflash the
    output is verified with, or anywhere with ``USPIFLASH_FORCE_PARITY=1``."""
    if spiflash.__version__ == VERIFIED_SPIFLASH or os.environ.get(FORCE_PARITY) == "1":
        return None
    return (
        f"output parity is verified against spiflash {VERIFIED_SPIFLASH}; spiflash "
        f"{spiflash.__version__} is installed ({FORCE_PARITY}=1 runs it anyway)"
    )


_REASON = parity_skip_reason()
#: Marks a test comparing the C's output with what spiflash prints.
parity = pytest.mark.skipif(_REASON is not None, reason=_REASON or "")

CFLAGS = ["-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Wundef", "-Wshadow", "-Werror"]
HERE = Path(__file__).parent
SEP = "\x1e\n"
SANITIZE = ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all"]


def no_datasheet() -> ChipFilter:
    """A filter keeping one chip id that has no datasheet, so DS_COUNT is 0.
    Fails, saying why, if every chip in the database has one."""
    bare = [f for f in database().flashes if not f.datasheets]
    if not bare:
        msg = "every chip has a datasheet now: no configuration with DS_COUNT 0 is tested"
        raise AssertionError(msg)
    f = bare[0]
    return ChipFilter(ids=(f.id,), types=(f.type,), families=(f.family,))


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
    """A test id: the level, then ``+extra``, ``-removed``, ``:type`` and
    ``#id`` filters, and ``@prefix`` when the prefix is not ``usf``."""
    sel = config.selection
    base = LEVELS[sel.level]
    return "".join(
        [
            sel.level,
            *(f"+{f}" for f in sorted(sel.fields - base)),
            *(f"-{f}" for f in sorted(base - sel.fields)),
            *(f":{t.value}" for t in sel.chips.types),
            *(f"#{i.hex()}" for i in sel.chips.ids),
            *([f"@{config.prefix}"] if config.prefix != "usf" else []),
        ]
    )


@functools.cache
def snapshot(config: Config) -> Snapshot:
    """The snapshot ``config``'s file is generated from (its chips only)."""
    return Snapshot.build(config.selection.chips.apply(database()))


def queries(snap: Snapshot, seed: int = 20260928) -> list[tuple[int, bytes]]:
    """Every chip id, every extended-id probe (also after continuation
    codes), each id padded to the 255 bytes ``usf_lookup`` takes and to the
    256 the harness reads, and random near-misses."""
    rng = random.Random(seed)
    out: list[tuple[int, bytes]] = []
    for i in range(snap.n_base):
        f = snap.entries[i].flash
        fam = FAMILIES.index(f.family)
        cont = b"\x7f" * f.bank
        out.append((fam, f.id))
        out.extend((fam, f.id + p) for p in reaching_probes(snap.ext.get(i, ())))
        out.append((fam, cont + f.id))
        if i in snap.ext:
            # At least one code, so bank-0 chips strip one before narrowing too.
            lead = cont or b"\x7f"
            out.extend((fam, lead + f.id + p) for p in reaching_probes(snap.ext[i]))
        out.extend((fam, f.id.ljust(n, b"\x00")) for n in (255, 256))
    out.extend(
        (rng.randrange(len(FAMILIES)), bytes(rng.randrange(256) for _ in range(rng.randint(1, 6))))
        for _ in range(3000)
    )
    return out


def _names_header() -> str:
    def arr(name: str, items: Sequence[object]) -> str:
        values = ", ".join(f'"{i}"' for i in items)
        return f"static const char *const {name}[] = {{{values}}};\n"

    return (
        arr("FAMILY_NAMES", [f.value for f in FAMILIES])
        + arr("KIND_NAMES", [k.value for k in layout.KINDS])
        + arr("PROTO_NAMES", layout.PROTOCOLS)
        + arr("FEATURE_NAMES", [f.value for f in layout.FEATURES])
        + arr("SOURCE_NAMES", [s.value for s in layout.SOURCES])
        + arr("OP_NAMES", layout.ALL_OPS)
    )


@dataclass
class Harness:
    """A compiled harness binary for one generated header."""

    binary: Path

    @classmethod
    def build(cls, tmp: Path, config: Config, cc: str) -> Harness:
        """Generate ``config``'s header in ``tmp`` and compile the harness
        against it with ``cc``, under ASan and UBSan."""
        tmp.mkdir(parents=True, exist_ok=True)
        generate(tmp, config)
        (tmp / "harness_names.h").write_text(_names_header(), encoding="ascii")
        binary = tmp / "harness"
        extra = [*SANITIZE, f"-I{tmp}", f"-I{HERE / 'c'}", f'-DUSF_HEADER="{config.filename}"']
        compile_c(cc, [HERE / "c" / "harness.c"], binary, extra)
        return cls(binary)

    def run(self, commands: Sequence[str]) -> list[str]:
        """Run ``commands`` in one process; one output per command."""
        res = subprocess.run(
            [str(self.binary)],
            input="".join(c + "\n" for c in commands),
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        assert res.returncode == 0, res.stderr
        assert not res.stderr, res.stderr
        parts = res.stdout.split(SEP)
        assert parts[-1] == ""
        assert len(parts) == len(commands) + 1
        return parts[:-1]


def check(
    tmp: Path,
    compilers: Sequence[str],
    config: Config,
    oracles: Mapping[str, Callable[[int, bytes], str]],
) -> None:
    """For each compiler, build the harness for ``config``; run each harness
    command in ``oracles`` on every query of its snapshot; and compare each
    output with the oracle's ``(family, data)`` answer."""
    qs = queries(snapshot(config))
    for cc in compilers:
        h = Harness.build(tmp / cc, config, cc)
        for cmd, oracle in oracles.items():
            got = h.run([f"{cmd} {fam} {data.hex()}" for fam, data in qs])
            for (fam, data), out in zip(qs, got, strict=True):
                want = oracle(fam, data)
                assert out == want, (
                    f"{cc} {name(config)} {cmd} {fam} {data.hex()}\n--- want\n{want}--- got\n{out}"
                )
