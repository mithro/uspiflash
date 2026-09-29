"""usf_print is byte-identical to `spiflash id` (and `--opcodes`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from spiflash.cli import describe
from spiflash.db import database
from spiflash.enums import FlashType

from harness import check, name, parity, snapshot
from uspiflash import oracle
from uspiflash.levels import ChipFilter, Selection
from uspiflash.model import FAMILIES
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

CONFIGS = [
    Config(Selection.make("describe")),
    Config(Selection.make("full")),
    # describe and full print the sfdp: lines (11 NOR chip ids and 2
    # variants carry dumps); without the summary, and before a datasheet line.
    Config(Selection.make("full", without=["sfdp_summary"])),
    Config(Selection.make("full", with_=["datasheet"])),
    # No NAND chip has an operation, a voltage or a conflict.
    Config(Selection.make("full", chips=ChipFilter(types=(FlashType.NAND,)))),
]


@parity
@pytest.mark.parametrize("config", CONFIGS, ids=name)
def test_text_matches_spiflash(tmp_path: Path, compilers: list[str], config: Config) -> None:
    db = snapshot(config).database
    sel = config.selection

    def with_opcodes(fam: int, data: bytes) -> str:
        return oracle.text(db, FAMILIES[fam], data, sel, opcodes=True)

    def without(fam: int, data: bytes) -> str:
        return oracle.text(db, FAMILIES[fam], data, sel, opcodes=False)

    check(tmp_path, compilers, config, {"T": with_opcodes, "t": without})


@parity
def test_cli_describe_is_the_reference() -> None:
    # Guard against spiflash changing its format under us: pin one example.
    (f,) = database().lookup("ef4018")
    assert describe(f).splitlines()[0].startswith("ef4018  Winbond  W25Q128")
