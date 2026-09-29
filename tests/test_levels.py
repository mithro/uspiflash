"""Levels are cumulative, requirements are closed over, filters mirror spiflash."""

from __future__ import annotations

from itertools import pairwise

import pytest
from spiflash.db import database
from spiflash.enums import FlashType, IdFamily, OperationKind

from uspiflash.levels import LEVELS, REQUIRES, ChipFilter, Field, Selection
from uspiflash.model import Snapshot

ORDER = ["id", "read", "write", "describe", "full"]


def test_levels_are_cumulative() -> None:
    for lower, higher in pairwise(ORDER):
        assert LEVELS[lower] < LEVELS[higher]


def test_every_level_is_closed_under_requirements() -> None:
    for fields in LEVELS.values():
        for f in fields:
            assert REQUIRES.get(f, frozenset()) <= fields


def test_extras_are_off_by_default() -> None:
    full = Selection.make()
    for extra in (
        Field.RECORDS,
        Field.PROVENANCE,
        Field.DATASHEET,
        Field.DATASHEETS,
        Field.JEP106,
        Field.SFDP,
    ):
        assert not full.has(extra)


def test_with_pulls_in_requirements() -> None:
    sel = Selection.make("id", with_=["text"])
    assert REQUIRES[Field.TEXT] <= sel.fields


def test_without_refuses_to_break_a_requirement() -> None:
    with pytest.raises(ValueError, match="text needs names"):
        Selection.make("full", without=["names"])


def test_read_level_keeps_only_read_side_operations() -> None:
    assert Selection.make("read").op_kinds == {
        OperationKind.ID,
        OperationKind.READ,
        OperationKind.MODE,
    }
    assert Selection.make("write").op_kinds == set(OperationKind)


def test_json_round_trip() -> None:
    sel = Selection.make("write", with_=["sfdp"], chips=ChipFilter(manufacturers=("Winbond",)))
    assert Selection.from_json(sel.to_json()) == sel


def test_filter_by_manufacturer_type_and_size() -> None:
    db = database()
    kept = ChipFilter(manufacturers=("winbond",), types=(FlashType.NOR,), min_size=1 << 20).apply(
        db
    )
    assert kept.flashes
    for f in kept.flashes:
        assert f.manufacturer == "Winbond"
        assert f.type is FlashType.NOR
        assert (f.size or 0) >= 1 << 20


def test_filter_by_id_keeps_those_chips_and_their_variants() -> None:
    db = database()
    kept = ChipFilter(ids=(bytes.fromhex("ef4018"), bytes.fromhex("010219"))).apply(db)
    assert sorted(f.id.hex() for f in kept.flashes) == ["010219", "ef4018"]
    snap = Snapshot.build(kept)
    assert snap.n_base == 2


def test_filtered_lookup_matches_a_filtered_spiflash() -> None:
    # A subset changes answers (dropping c22018 makes Linux's generic c2 match).
    kept = ChipFilter(families=(IdFamily.JEDEC,), ids=(bytes.fromhex("c2"),)).apply(database())
    assert [f.id.hex() for f in kept.lookup("c22018")] == ["c2"]


def test_filter_keeps_a_kept_chips_datasheets() -> None:
    # Controller ruling: ChipFilter.apply must pass db.datasheets through to
    # the filtered Database (its 4th constructor argument), or every kept
    # chip would lose its datasheets.
    db = database()
    with_sheets = next(f for f in db.flashes if f.datasheets)
    kept = ChipFilter(ids=(with_sheets.id,), types=(with_sheets.type,)).apply(db)
    (found,) = [f for f in kept.flashes if f.id == with_sheets.id and f.type == with_sheets.type]
    assert found.datasheets == with_sheets.datasheets
