"""The helper-free arithmetic gives exactly the portable code's answers:
on the host, with the switches forced on, the lookup, the accessors and
both printers still match spiflash."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from harness import check, name, parity, snapshot
from uspiflash import oracle
from uspiflash.levels import Field, Selection
from uspiflash.model import FAMILIES
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

#: Every switch forced on (Task 8 adds USF_SOFT_SHIFT).
SOFT = ["-DUSF_SOFT_MUL=1"]
CONFIGS = [
    Config(Selection.make("full")),
    Config(Selection.make("full", with_=["datasheets"])),
]


@pytest.mark.parametrize("config", CONFIGS, ids=name)
def test_lookup_and_accessors(tmp_path: Path, compilers: list[str], config: Config) -> None:
    snap = snapshot(config)
    sel = config.selection

    def answers(fam: int, data: bytes) -> list[int]:
        found = snap.lookup(FAMILIES[fam], data)
        return found if sel.has(Field.EXT) else [snap.entries[j].base for j in found]

    def lookup(fam: int, data: bytes) -> str:
        found = answers(fam, data)
        return f"{len(found)}\n" + "".join(f"{j} {snap.entries[j].base}\n" for j in found)

    def accessors(fam: int, data: bytes) -> str:
        return "".join(oracle.accessors(snap.entries[j].flash, sel) for j in answers(fam, data))

    check(tmp_path, compilers, config, {"L": lookup, "A": accessors}, defines=SOFT)


@parity
@pytest.mark.parametrize("config", CONFIGS, ids=name)
def test_printers(tmp_path: Path, compilers: list[str], config: Config) -> None:
    db = snapshot(config).database
    sel = config.selection

    def text(fam: int, data: bytes) -> str:
        return oracle.text(db, FAMILIES[fam], data, sel, opcodes=True)

    def json_text(fam: int, data: bytes) -> str:
        return oracle.json_text(db, FAMILIES[fam], data, sel)

    check(tmp_path, compilers, config, {"T": text, "J": json_text}, defines=SOFT)
