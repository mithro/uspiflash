"""The uspiflash command's top level."""

from __future__ import annotations

import pytest
import spiflash

import uspiflash
from uspiflash.cli import main


def test_version_names_both_packages(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert out == f"uspiflash {uspiflash.__version__} (spiflash {spiflash.__version__})\n"


def test_no_subcommand_prints_help_and_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "usage: uspiflash" in capsys.readouterr().out
