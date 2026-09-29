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
    images = damaged()
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
