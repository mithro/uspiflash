"""usf_print_json is byte-identical to `spiflash id --json`, less what the
selection leaves out."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from spiflash.enums import FlashType

from harness import check, name, parity, snapshot
from uspiflash import oracle
from uspiflash.levels import ChipFilter, Selection
from uspiflash.model import FAMILIES
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

CONFIGS = [
    Config(Selection.make("full")),
    Config(Selection.make("full", with_=["records"])),
    Config(Selection.make("full", with_=["records", "provenance"])),
    Config(Selection.make("full", chips=ChipFilter(types=(FlashType.NAND,)))),
    # The "sfdp" list, alone and after every other extra key.
    Config(Selection.make("full", with_=["sfdp_dumps"])),
    Config(Selection.make("full", with_=["sfdp_dumps", "datasheets", "records", "provenance"])),
    # No NAND chip has a dump: every "sfdp" is [] (SFDP_COUNT 0).
    Config(Selection.make("full", with_=["sfdp_dumps"], chips=ChipFilter(types=(FlashType.NAND,)))),
    # JSON without TEXT: the shared formatting helpers compiled for JSON alone.
    Config(Selection.make("write", with_=["json"])),
]


@parity
@pytest.mark.parametrize("config", CONFIGS, ids=name)
def test_json_matches_spiflash(tmp_path: Path, compilers: list[str], config: Config) -> None:
    db = snapshot(config).database

    def json_text(fam: int, data: bytes) -> str:
        return oracle.json_text(db, FAMILIES[fam], data, config.selection)

    check(tmp_path, compilers, config, {"J": json_text})
