"""The layout round-trips: decoding the bytes gives back spiflash's values."""

from __future__ import annotations

import random
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import pytest
from spiflash.db import Database, database
from spiflash.enums import FlashType, IdFamily
from spiflash.model import Voltage
from spiflash.opcodes import OPERATIONS

from uspiflash import decode, layout
from uspiflash.levels import LEVELS, ChipFilter, Field, Selection
from uspiflash.model import FAMILIES, Snapshot

if TYPE_CHECKING:
    from spiflash.model import Flash, Record


@pytest.fixture(scope="module")
def snap() -> Snapshot:
    return Snapshot.build()


def expected(sel: Selection, flash: Flash) -> dict[str, object]:
    """What decode.entry must return for ``flash`` under ``sel``."""
    out: dict[str, object] = {"bank": flash.bank}
    if sel.has(Field.SIZE):
        out["size"] = flash.size
    if sel.has(Field.PAGE_SIZE):
        out["page_size"] = flash.page_size
    if sel.has(Field.SECTOR_SIZE):
        out["sector_size"] = flash.sector_size
    if sel.has(Field.VOLTAGE):
        out["voltage"] = tuple(flash.voltage) if flash.voltage else None
    if sel.has(Field.FEATURES):
        out["features"] = sorted(flash.features)
    if sel.has(Field.MANUFACTURER):
        out["manufacturer"] = flash.manufacturer
    if sel.has(Field.NAMES):
        out["names"] = list(flash.names)
    if sel.has(Field.SOURCES):
        out["sources"] = list(flash.sources)
    if sel.has(Field.OPERATIONS):
        ops = [o for o in flash.opcodes.values() if o.operation.kind in sel.op_kinds]
        out["operations"] = [
            (o.name, list(o.sources)) if sel.has(Field.SOURCES) else (o.name, None) for o in ops
        ]
    if sel.has(Field.CONFLICTS):
        out["conflicts"] = {
            a: [(tuple(v) if isinstance(v, tuple) else v, list(s)) for v, s in vals.items()]
            for a, vals in flash.conflicts.items()
        }
    return out


def ordered(d: dict[str, object]) -> dict[str, object]:
    """``d`` with its conflicts as a list, so their order is compared too."""
    conf = d.get("conflicts")
    return {**d, "conflicts": list(conf.items())} if isinstance(conf, dict) else d


@pytest.mark.parametrize("level", list(LEVELS))
def test_every_entry_round_trips(snap: Snapshot, level: str) -> None:
    sel = Selection.make(level)
    lay = layout.build(snap, sel)
    for i, e in enumerate(snap.entries):
        assert ordered(decode.entry(lay, i)) == ordered(expected(sel, e.flash)), (level, i)


@pytest.mark.parametrize("level", ["read", "full"])
def test_lookup_in_the_bytes_matches_the_snapshot(snap: Snapshot, level: str) -> None:
    lay = layout.build(snap, Selection.make(level))
    rng = random.Random(7)
    for i in range(snap.n_base):
        f = snap.entries[i].flash
        fam = FAMILIES.index(f.family)
        for tail in (b"", bytes(rng.randrange(256) for _ in range(rng.randint(1, 3)))):
            assert decode.lookup(lay, fam, f.id + tail) == snap.lookup(f.family, f.id + tail)
        for probe in snap.ext.get(i, ()):
            assert decode.lookup(lay, fam, f.id + probe) == snap.lookup(f.family, f.id + probe)
        sent = b"\x7f" * f.bank + f.id  # as a chip in a later JEP106 bank sends it
        assert decode.lookup(lay, fam, sent) == snap.lookup(f.family, sent)
        # A continuation code before a bank-0 id: skipped, as spiflash does.
        sent = b"\x7f" + f.id
        assert decode.lookup(lay, fam, sent) == snap.lookup(f.family, sent)


def test_lookup_misses_as_spiflash_does(snap: Snapshot) -> None:
    lay = layout.build(snap, Selection.make("full"))
    nothing = b"\x00\x00\x00"
    assert snap.lookup(IdFamily.JEDEC, nothing) == []
    assert decode.lookup(lay, 0, nothing) == []
    # Every chip's id asked for under every other family.
    misses = 0
    for i in range(snap.n_base):
        f = snap.entries[i].flash
        for fam, family in enumerate(FAMILIES):
            if family is not f.family:
                want = snap.lookup(family, f.id)
                assert decode.lookup(lay, fam, f.id) == want, (i, family)
                misses += not want
    assert misses > 0


def test_lookup_without_ext_answers_the_base_entry(snap: Snapshot) -> None:
    """Without EXT (the ``id`` level) nothing narrows: the bytes after the id
    are ignored and the answer is the chip id's base entry."""
    lay = layout.build(snap, Selection.make("id"))
    assert "HAVE_EXT" not in lay.defines
    for i, ids in snap.ext.items():
        f = snap.entries[i].flash
        fam = FAMILIES.index(f.family)
        for probe in ids:
            want = [snap.entries[j].base for j in snap.lookup(f.family, f.id + probe)]
            assert decode.lookup(lay, fam, f.id + probe) == want
    assert any(
        snap.lookup(snap.entries[i].flash.family, snap.entries[i].flash.id + probe) != [i]
        for i, ids in snap.ext.items()
        for probe in ids
    )


def test_build_is_deterministic(snap: Snapshot) -> None:
    sel = Selection.make("full", with_=["records", "provenance", "jep106"])
    assert layout.build(snap, sel).tables == layout.build(snap, sel).tables


def test_string_pool_refuses_what_c_would_have_to_escape() -> None:
    pool = layout.StringPool()
    for bad in ('say "hi"', "back\\slash", "tab\there", "café"):
        with pytest.raises(ValueError, match="printable ASCII"):
            pool.add(bad)
    assert pool.add("W25Q128") == 0
    assert pool.add("W25Q128") == 0  # deduplicated


def test_stable_operation_ids_cover_spiflash() -> None:
    assert sorted(layout.ALL_OPS) == sorted(OPERATIONS)


def test_extras_add_their_tables(snap: Snapshot) -> None:
    lay = layout.build(snap, Selection.make("full", with_=["records", "provenance", "jep106"]))
    assert {"records", "jep106"} <= lay.tables.keys()
    assert lay.defines["JEP106_COUNT"] == len(database().manufacturers)


def test_records_and_jep106_round_trip(snap: Snapshot) -> None:
    for extras in (["records"], ["records", "provenance", "jep106"]):
        sel = Selection.make("full", with_=extras)
        lay = layout.build(snap, sel)
        for i, e in enumerate(snap.entries):
            want = [
                (r.source, r.name, r.ext_id, r.url if sel.has(Field.PROVENANCE) else None)
                for r in e.flash.records
            ]
            assert decode.records(lay, i) == want, (extras, i)
    want_jep = sorted((m.bank, m.id, m.name) for m in snap.database.manufacturers)
    assert decode.jep106(lay) == want_jep


def test_every_entry_field_has_an_offset_define(snap: Snapshot) -> None:
    lay = layout.build(snap, Selection.make("full"))
    d = lay.defines
    offsets = sorted(v for k, v in d.items() if k.startswith("E_"))
    assert offsets[0] == 0
    assert d["ENTRY_SIZE"] > offsets[-1]
    assert d["ENTRY_COUNT"] == len(snap.entries)
    assert d["BASE_COUNT"] == snap.n_base
    assert d["RDID_LEN"] >= 6
    assert all(d[f"HAVE_{f.name}"] == 1 for f in lay.selection.fields)
    assert len(lay.tables["entries"]) == d["ENTRY_SIZE"] * d["ENTRY_COUNT"]
    idl = layout.build(snap, Selection.make("id")).defines
    assert {k for k in idl if k.startswith("E_")} == {"E_BANK"}
    assert idl["ENTRY_SIZE"] == 1


@pytest.mark.parametrize(("keep", "other"), [(FlashType.NOR, "NAND"), (FlashType.NAND, "NOR")])
def test_single_type_selections(keep: FlashType, other: str) -> None:
    one = Snapshot.build(ChipFilter(types=(keep,)).apply(database()))
    sel = Selection.make("full")
    lay = layout.build(one, sel)
    assert lay.defines[f"HAVE_{keep.name}"] == 1
    assert f"HAVE_{other}" not in lay.defines
    families = {one.entries[i].flash.family for i in range(one.n_base)}
    assert {k for k in lay.defines if k.startswith("HAVE_FAMILY_")} == {
        f"HAVE_FAMILY_{f.name}" for f in families
    }
    for i, e in enumerate(one.entries):
        assert ordered(decode.entry(lay, i)) == ordered(expected(sel, e.flash)), (keep, i)


def test_full_database_has_both_types_and_every_family(snap: Snapshot) -> None:
    d = layout.build(snap, Selection.make("id")).defines
    assert d["HAVE_NOR"] == d["HAVE_NAND"] == 1
    assert all(d[f"HAVE_FAMILY_{f.name}"] == 1 for f in FAMILIES)


def test_string_returns_what_was_added(snap: Snapshot) -> None:
    pool = layout.StringPool()
    at = pool.add("ab")
    lay = layout.Layout(Selection.make("id"), snap, 2, tables={"str": pool.data})
    assert decode.string(lay, at) == "ab"


def _chip_records() -> list[Record]:
    """The records of one ordinary JEDEC NOR chip."""
    f = next(
        f for f in database().flashes if f.family is IdFamily.JEDEC and f.type is FlashType.NOR
    )
    return list(f.records)


def _build(records: list[Record], level: str) -> layout.Layout:
    db = database()
    small = Database(records, db.manufacturers, db.sources, db.datasheets)
    return layout.build(Snapshot.build(small), Selection.make(level))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"size": 1 << 32}, "size 4294967296 does not fit 32 bits"),
        ({"page_size": 1 << 16}, "page_size 65536 does not fit 16 bits"),
        ({"sector_size": 1 << 32}, "sector_size 4294967296 does not fit 32 bits"),
        ({"voltage": Voltage(1800, 1 << 16)}, "voltage 65536 does not fit 16 bits"),
    ],
)
def test_a_value_too_wide_for_its_table_is_refused(change: dict[str, Any], message: str) -> None:
    records = [replace(r, **change) for r in _chip_records()]
    with pytest.raises(ValueError, match=message):
        _build(records, "describe")


def test_more_than_254_distinct_values_is_refused() -> None:
    r = _chip_records()[0]
    records = [replace(r, id=bytes([0xEF, i >> 8, i & 0xFF]), size=i + 1) for i in range(300)]
    with pytest.raises(ValueError, match="more than 254 distinct values"):
        _build(records, "read")
