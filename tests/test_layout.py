"""The layout's tables, and the constants the C template needs."""

from __future__ import annotations

import pytest
from spiflash.db import database
from spiflash.opcodes import OPERATIONS

from uspiflash import layout
from uspiflash.levels import Selection
from uspiflash.model import FAMILIES, Snapshot


@pytest.fixture(scope="module")
def snap() -> Snapshot:
    return Snapshot.build()


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


def test_full_database_has_both_types_and_every_family(snap: Snapshot) -> None:
    d = layout.build(snap, Selection.make("id")).defines
    assert d["HAVE_NOR"] == d["HAVE_NAND"] == 1
    assert all(d[f"HAVE_FAMILY_{f.name}"] == 1 for f in FAMILIES)
