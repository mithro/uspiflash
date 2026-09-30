"""A generated header quotes its measured size, from the committed ledger,
when its selection is one the ledger measures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import spiflash
from spiflash.enums import FlashType

from uspiflash import ledger, provenance
from uspiflash.levels import ChipFilter, Selection
from uspiflash.provenance import Config

ROOT = Path(__file__).resolve().parent.parent
FULL_NOR = Selection.make("full", chips=ChipFilter(types=(FlashType.NOR,)))


def committed() -> dict[str, Any]:
    data = ledger.committed(ROOT)
    if data is None:
        pytest.skip("no committed ledger (an sdist without sizes/)")
    return data


def test_a_measured_selection_quotes_the_ledger() -> None:
    data = committed()
    if data["spiflash"]["version"] != spiflash.__version__:
        pytest.skip("the ledger was measured against another spiflash")
    text = " ".join(provenance.size_lines(Config(FULL_NOR)))
    for target in data["targets"]:
        total = data["sizes"][target["name"]]["full:nor"]["total"]
        assert f"{target['name']} {total:,}" in text
    assert "full:nor" in text


def test_the_prefix_and_file_name_do_not_matter() -> None:
    committed()
    assert provenance.size_lines(Config(FULL_NOR, "fl", "flash.h")) == provenance.size_lines(
        Config(FULL_NOR)
    )


def test_an_unmeasured_selection_says_so() -> None:
    lines = provenance.size_lines(Config(Selection.make("id", with_=["jep106"])))
    assert "not in the size ledger" in " ".join(lines)


def test_another_spiflash_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spiflash, "__version__", "0.0.0")
    assert "not in the size ledger" in " ".join(provenance.size_lines(Config(FULL_NOR)))


def test_the_header_has_the_lines() -> None:
    config = Config(FULL_NOR)
    header = provenance.header(config)
    for line in provenance.size_lines(config):
        assert f" * {line}\n" in header


def test_the_packaged_file_is_generated_from_the_ledger() -> None:
    data = committed()
    packaged = json.loads((ROOT / ledger.REFERENCE).read_text(encoding="utf-8"))
    assert packaged == ledger.reference_sizes(data)
