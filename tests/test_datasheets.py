"""Datasheets, when selected, print exactly as spiflash prints them."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from harness import check, name, no_datasheet, parity, snapshot
from uspiflash import layout, oracle
from uspiflash.levels import Selection
from uspiflash.model import FAMILIES
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

CONFIGS = [
    *(
        Config(Selection.make("full", with_=extras))
        for extras in (["datasheet"], ["datasheets"], ["datasheet", "datasheets", "records"])
    ),
    # A chip without a datasheet: DS_COUNT is 0, and the text line and the
    # JSON list are absent and empty.
    Config(Selection.make("full", with_=["datasheet", "datasheets"], chips=no_datasheet())),
]


@parity
@pytest.mark.parametrize("config", CONFIGS, ids=name)
def test_text_and_json_with_datasheets(
    tmp_path: Path, compilers: list[str], config: Config
) -> None:
    db = snapshot(config).database
    sel = config.selection

    def text(fam: int, data: bytes) -> str:
        return oracle.text(db, FAMILIES[fam], data, sel, opcodes=True)

    def json_text(fam: int, data: bytes) -> str:
        return oracle.json_text(db, FAMILIES[fam], data, sel)

    check(tmp_path, compilers, config, {"T": text, "J": json_text})


@pytest.mark.parametrize(
    ("title", "stored"),
    [
        ("512K \u00d7 8, -40\u00b0C", b"512K \\u00d7 8, -40\\u00b0C"),
        ('the "W25Q" family', b'the \\"W25Q\\" family'),
        ("C:\\flash", b"C:\\\\flash"),
        ("two\nlines", b"two\\nlines"),
    ],
)
def test_json_escaped_titles_are_stored_escaped(title: str, stored: bytes) -> None:
    pool = layout.StringPool()
    off = pool.add_json(title)
    assert pool.data[off:].split(b"\0")[0] == stored
    assert json.loads(b'"' + stored + b'"') == title


def test_an_escaped_string_is_never_handed_out_unescaped() -> None:
    """``add`` refuses what ``add_json`` stored escaped, so a string the
    printers write raw can never share an escaped one's bytes; plain ASCII is
    stored once whichever way it is added."""
    pool = layout.StringPool()
    escaped = pool.add_json("40\u00b0C")
    with pytest.raises(ValueError, match="printable ASCII"):
        pool.add("40\\u00b0C")
    assert pool.add("plain") == pool.add_json("plain")
    assert pool.add_json("40\u00b0C") == escaped
