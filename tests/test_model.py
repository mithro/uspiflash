"""The snapshot answers exactly as spiflash's lookup does."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest
from spiflash.db import database

from uspiflash.model import FAMILIES, Snapshot, compatible, ext_mask, reaching_probes

if TYPE_CHECKING:
    from spiflash.enums import IdFamily


@pytest.fixture(scope="module")
def snap() -> Snapshot:
    return Snapshot.build()


def test_family_codes_are_fixed() -> None:
    assert [f.value for f in FAMILIES] == ["jedec", "rems", "res1", "res2", "at25f", "st95"]


def test_compatible_is_spiflash_rule() -> None:
    assert compatible(b"\x4d\x00", b"\x4d")
    assert compatible(b"\x4d", b"\x4d\x00\x81")
    assert not compatible(b"\x4d\x00", b"\x4d\x01")


def test_reaching_probes_reach_every_mask() -> None:
    ids = (b"\x4d\x00", b"\x4d\x01", b"\x4d\x01\x80")
    reached = {ext_mask(ids, p) for p in reaching_probes(ids)}
    rng = random.Random(1)
    for _ in range(5000):
        probe = bytes(rng.choice((0x4D, 0x00, 0x01, 0x80, 0x55)) for _ in range(rng.randint(1, 4)))
        assert ext_mask(ids, probe) in reached


def test_base_entries_are_the_database_in_order(snap: Snapshot) -> None:
    db = database()
    assert snap.n_base == len(db.flashes)
    assert all(snap.entries[i].flash is f for i, f in enumerate(db.flashes))
    assert all(e.base == i and e.ext_mask == 0 for i, e in enumerate(snap.entries[: snap.n_base]))


def _expected(family: IdFamily, data: bytes) -> list[tuple[object, ...]]:
    return [f.records for f in database().lookup(data, method=family)]


def _got(snap: Snapshot, family: IdFamily, data: bytes) -> list[tuple[object, ...]]:
    return [snap.entries[i].flash.records for i in snap.lookup(family, data)]


def test_every_id_and_every_reaching_probe(snap: Snapshot) -> None:
    for i in range(snap.n_base):
        f = snap.entries[i].flash
        assert _got(snap, f.family, f.id) == _expected(f.family, f.id)
        for probe in reaching_probes(snap.ext.get(i, ())):
            data = f.id + probe
            assert _got(snap, f.family, data) == _expected(f.family, data), data.hex()


def test_random_ids(snap: Snapshot) -> None:
    rng = random.Random(20260928)
    bases = [snap.entries[i].flash for i in range(snap.n_base)]
    for _ in range(20000):
        f = rng.choice(bases)
        tail = bytes(rng.randrange(256) for _ in range(rng.randint(0, 3)))
        head = bytes(rng.randrange(256) for _ in range(rng.randint(0, 2)))
        for data in (f.id + tail, head + f.id, b"\x7f" * rng.randint(0, 7) + f.id + tail):
            if data:
                assert _got(snap, f.family, data) == _expected(f.family, data), data.hex()


def test_variants_differ_from_their_base(snap: Snapshot) -> None:
    for base, table in snap.variants.items():
        for entry in table.values():
            assert snap.entries[entry].flash.records != snap.entries[base].flash.records
