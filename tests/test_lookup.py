"""The C lookup and accessors agree with spiflash for every entry, at every
level, and for single-type selections."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from spiflash.enums import FlashType

from harness import check, name, snapshot
from uspiflash import oracle
from uspiflash.levels import LEVELS, ChipFilter, Field, Selection
from uspiflash.model import FAMILIES
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

CONFIGS = [
    *(Config(Selection.make(level)) for level in LEVELS),
    *(Config(Selection.make("full", chips=ChipFilter(types=(t,)))) for t in FlashType),
]


@pytest.mark.parametrize("config", CONFIGS, ids=name)
def test_lookup_and_accessors(tmp_path: Path, compilers: list[str], config: Config) -> None:
    snap = snapshot(config)
    sel = config.selection

    def answers(fam: int, data: bytes) -> list[int]:
        found = snap.lookup(FAMILIES[fam], data)
        # Without EXT nothing narrows: the answer is the chip id's base entry.
        return found if sel.has(Field.EXT) else [snap.entries[j].base for j in found]

    def lookup(fam: int, data: bytes) -> str:
        found = answers(fam, data)
        return f"{len(found)}\n" + "".join(f"{j} {snap.entries[j].base}\n" for j in found)

    def accessors(fam: int, data: bytes) -> str:
        return "".join(oracle.accessors(snap.entries[j].flash, sel) for j in answers(fam, data))

    check(tmp_path, compilers, config, {"L": lookup, "A": accessors})
