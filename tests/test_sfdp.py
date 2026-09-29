"""usf_sfdp_read decodes a chip's own SFDP tables as spiflash.sfdp does: on
every dump spiflash ships and thousands of damaged ones, under ASan and
UBSan, sending nothing but RDSFDP."""

from __future__ import annotations

import random

import pytest
from spiflash.db import database
from spiflash.enums import FlashType

from harness import Harness
from uspiflash import oracle
from uspiflash.levels import ChipFilter, Selection
from uspiflash.provenance import Config

#: Every distinct SFDP dump in the database (12 at spiflash 0.0.post74, all QEMU's).
DUMPS = sorted({r.sfdp for f in database().flashes for r in f.records if r.sfdp})
#: The smallest header with the reader: NOR chips, id level.
CONFIG = Config(Selection.make("id", with_=["sfdp"], chips=ChipFilter(types=(FlashType.NOR,))))


@pytest.fixture(scope="module")
def harnesses(tmp_path_factory: pytest.TempPathFactory, compilers: list[str]) -> dict[str, Harness]:
    return {cc: Harness.build(tmp_path_factory.mktemp(cc), CONFIG, cc) for cc in compilers}


def damaged(seed: int = 20260929, n: int = 4000) -> list[bytes]:
    """Each dump with up to eight bytes changed (mostly in the headers,
    where a change moves or hides the BFPT), cut short at random; random
    bytes after a signature; and the degenerate cases."""
    rng = random.Random(seed)
    out: list[bytes] = []
    for _ in range(n):
        img = bytearray(rng.choice(DUMPS))
        for _ in range(rng.randint(1, 8)):
            reach = rng.choice((16, 64, len(img)))
            img[rng.randrange(min(len(img), reach))] = rng.randrange(256)
        out.append(bytes(img[: rng.randrange(0, len(img) + 1)]))
    out += [b"SFDP" + rng.randbytes(rng.randrange(0, 96)) for _ in range(500)]
    return [*out, b"", b"SFD", b"SFDP", b"\xff" * 64]


def edges() -> list[bytes]:
    """The boundaries random damage misses: every BFPT length from 0 to 20,
    every 2^N density exponent and the N + 1 density's edges, a table at the
    end of the 24-bit space and at the end of the sim's 4 KiB image, and two
    BFPTs competing."""
    base = next(d for d in DUMPS if d[8] == 0 and d[11] == 16 and d[15] == 0xFF)
    ptr = int.from_bytes(base[12:15], "little")
    table = base[ptr : ptr + 64]

    def put(img: bytes, at: int, data: bytes) -> bytes:
        return img[:at] + data + img[at + len(data) :]

    out = [put(base, 11, bytes([n])) for n in range(21)]
    dw2 = [0x80000000 | e for e in range(65)]
    dw2 += [0, 1, 6, 7, 8, 9, 0x7FFFFFFE, 0x7FFFFFFF, 0xFFFFFFFF]
    out += [put(base, ptr + 4, v.to_bytes(4, "little")) for v in dw2]
    for p in (0xFFC, 0xFFF, 0x1000, 0xFFFFC0, 0xFFFFFC, 0xFFFFFF):
        img = put(base, 12, p.to_bytes(3, "little"))
        if p < 4096:  # the sim holds 4 KiB: the table as far as that goes
            img = (img.ljust(p, b"\xff") + table)[:4096]
        out.append(img)

    def two(first: tuple[int, int, int], second: tuple[int, int, int]) -> bytes:
        """Two BFPT headers, (major, minor, length) each: the first's table
        at 0x40, the second's at 0x80, told apart by the 4 KiB erase opcode."""
        img = b"SFDP" + bytes([6, 1, 1, 0xFF])
        for (major, minor, n), at in ((first, 0x40), (second, 0x80)):
            img += bytes([0, minor, major, n]) + at.to_bytes(3, "little") + b"\xff"
        return img.ljust(0x40, b"\xff") + table + put(table, 1, b"\x21")

    out += [
        two((1, 6, 16), (1, 6, 16)),  # a tie: the first
        two((1, 5, 16), (1, 6, 16)),  # a higher minor second
        two((1, 6, 16), (1, 6, 9)),  # a shorter second
        two((1, 6, 9), (1, 6, 16)),  # a longer second
        two((1, 6, 16), (2, 7, 16)),  # a second with major 2
        two((2, 7, 16), (1, 5, 16)),  # a first with major 2
        two((1, 6, 0), (1, 5, 9)),  # an empty first
        two((1, 6, 16), (1, 7, 0)),  # an empty second, higher minor
    ]
    return out


def decoded(out: str) -> str:
    """The harness output without its transaction log."""
    return "".join(line + "\n" for line in out.splitlines() if not line.startswith("> "))


def test_there_are_dumps() -> None:
    assert len(DUMPS) >= 12


def test_every_shipped_dump(harnesses: dict[str, Harness]) -> None:
    for cc, h in harnesses.items():
        got = h.run([f"S sfdp={d.hex()}" for d in DUMPS])
        for d, out in zip(DUMPS, got, strict=True):
            assert decoded(out) == oracle.sfdp_fields(d), (cc, d.hex())
            assert not decoded(out).startswith("sfdp=none")


def test_damaged_dumps(harnesses: dict[str, Harness]) -> None:
    images = damaged() + edges()
    want = [oracle.sfdp_fields(i) for i in images]
    assert 1000 < sum(w != "sfdp=none\n" for w in want) < len(images)  # both kinds, many
    for cc, h in harnesses.items():
        got = h.run([f"S sfdp={i.hex()}" for i in images])
        for i, w, out in zip(images, want, got, strict=True):
            assert decoded(out) == w, (cc, i.hex())


def test_only_rdsfdp_is_sent(harnesses: dict[str, Harness]) -> None:
    h = next(iter(harnesses.values()))
    for out in h.run([f"S sfdp={d.hex()}" for d in DUMPS[:3]] + ["S fill=ff"]):
        sent = [line.split()[1] for line in out.splitlines() if line.startswith("> ")]
        assert sent
        assert {s[:2] for s in sent} == {"5a"}
        assert {len(s) for s in sent} == {10}  # 5a, 3 address bytes, a dummy byte


def test_a_blank_bus_has_no_sfdp(harnesses: dict[str, Harness]) -> None:
    for spec in ("fill=ff", "fill=00"):
        (out,) = next(iter(harnesses.values())).run([f"S {spec}"])
        assert decoded(out) == "sfdp=none\n"


def test_the_space_is_padded_as_far_as_the_reader_reads() -> None:
    d = DUMPS[0]
    assert oracle.sfdp_space(d)[: len(d)] == d
    assert oracle.sfdp_space(b"") == b"\xff" * (8 + 8 * 256)
    # A BFPT header pointing past the dump: its table reads as 0xFF.
    image = bytes.fromhex("53464450 0001 00ff 0001 0110 000100ff")
    assert oracle.sfdp_space(image) == image.ljust(0x100 + 4 * 16, b"\xff")
