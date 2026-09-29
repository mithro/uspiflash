"""The generated file: deterministic, self-describing, renamable."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import spiflash
from spiflash.db import FORMAT, database
from spiflash.enums import FlashType

import uspiflash
from harness import FORCE_PARITY
from uspiflash import emit, layout
from uspiflash.cli import config_from_args, main
from uspiflash.levels import ChipFilter, Selection
from uspiflash.model import Snapshot
from uspiflash.provenance import CONFIG_RE, Config

FULL = Config(Selection.make("full"), "usf", "uspiflash.h")


def _generate_in_subprocess(seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    cmd = [sys.executable, "-m", "uspiflash.cli", "generate", "-o", "-", "--level", "full"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
    return res.stdout


def test_output_is_byte_identical_across_processes() -> None:
    # Two interpreters with different hash seeds: set or dict ordering that
    # leaked into the output would show here, not within one process.
    assert _generate_in_subprocess("1") == _generate_in_subprocess("2")


def test_header_carries_versions_config_and_regeneration() -> None:
    text = emit.render(FULL)
    head = text[: text.index("*/")]
    assert f"uspiflash {uspiflash.__version__}" in head
    assert f"spiflash {spiflash.__version__}" in head
    assert f"(database format {FORMAT})" in head
    for name, info in spiflash.sources().items():
        assert f"{name} {info.commit}" in head
    assert "uvx --from 'uspiflash==" in head
    assert "uspiflash check uspiflash.h" in head
    assert "Apache-2.0" in head
    m = CONFIG_RE.search(text)
    assert m is not None
    assert Config.from_json(json.loads(m.group(1))) == FULL


def test_no_wall_clock_in_output(monkeypatch: pytest.MonkeyPatch) -> None:
    before = emit.render(FULL)
    monkeypatch.setenv("TZ", "Pacific/Chatham")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1")
    assert emit.render(FULL) == before


def test_prefix_renames_every_symbol() -> None:
    text = emit.render(Config(Selection.make("full"), "fl", "flashid.h"))
    code = text[text.index("*/") :]
    assert "usf_" not in code
    assert "USF_" not in code
    assert "fl_lookup(" in code
    assert "fl__ids[]" in code
    assert "FL_IMPLEMENTATION" in code
    assert "#ifndef FL_FLASHID_H\n" in code


def test_prefix_leaves_the_provenance_alone() -> None:
    # The rename runs before the provenance goes in, so a file name holding
    # "usf_" survives in the embedded config.
    cfg = Config(Selection.make("id"), "fl", "usf_x.h")
    m = CONFIG_RE.search(emit.render(cfg))
    assert m is not None
    assert Config.from_json(json.loads(m.group(1))) == cfg


@pytest.mark.parametrize(
    ("filename", "guard"),
    [("uspiflash.h", "USF_USPIFLASH_H"), ("9x.h", "USF_9X_H"), ("a-b.h", "USF_A_B_H")],
)
def test_include_guard_is_never_reserved(filename: str, guard: str) -> None:
    text = emit.render(Config(Selection.make("id"), "usf", filename))
    assert f"#ifndef {guard}\n#define {guard}\n" in text


def test_bad_prefix_is_refused() -> None:
    with pytest.raises(ValueError, match="C identifier"):
        emit.render(Config(Selection.make("full"), "9x", "a.h"))


def test_constants_are_unique_and_clash_with_no_layout_define() -> None:
    consts = emit.constants()
    assert all(k.isidentifier() for k in consts)
    assert consts["FEATURE_COUNT"] == len(layout.FEATURES)
    assert consts["TYPE_NOR"] == 0
    assert consts["TYPE_NAND"] == 1
    assert consts["FAMILY_JEDEC"] == 0
    assert consts["OP_RDID"] == layout.ALL_OPS.index("RDID")
    assert consts["PROTO_8D_8D_8D"] == layout.PROTOCOLS.index("8D-8D-8D")
    sel = Selection.make("full", with_=["records", "provenance", "jep106"])
    nand = Snapshot.build(ChipFilter(types=(FlashType.NAND,)).apply(database()))
    for snap in (Snapshot.build(), nand):
        assert not consts.keys() & layout.build(snap, sel).defines.keys()


def test_args_regenerate_the_same_config() -> None:
    cfg = Config(
        Selection.make(
            "write",
            with_=["sfdp"],
            without=["ext"],
            chips=ChipFilter(manufacturers=("Winbond",), types=(FlashType.NOR,)),
        ),
        "usf",
        "w.h",
    )
    # Parsing the canonical arguments back must give the same config.
    assert config_from_args(cfg.args()) == cfg


def test_the_file_name_is_the_outputs_own_name(tmp_path: Path) -> None:
    assert config_from_args(["-o", str(tmp_path / "x.h")]).filename == "x.h"
    assert config_from_args(["-o", "-"]).filename == "uspiflash.h"


def test_generate_writes_the_file(tmp_path: Path) -> None:
    out = tmp_path / "x.h"
    assert main(["generate", "-o", str(out), "--level", "id"]) == 0
    text = out.read_text(encoding="ascii")
    assert text.startswith("/*")
    assert "usf_lookup(" in text
    m = CONFIG_RE.search(text)
    assert m is not None
    assert Config.from_json(json.loads(m.group(1))).filename == "x.h"


def test_generate_warns_when_spiflash_is_not_the_verified_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "x.h"
    monkeypatch.setattr(spiflash, "__version__", uspiflash.VERIFIED_SPIFLASH)
    assert main(["generate", "-o", str(out), "--level", "id"]) == 0
    assert capsys.readouterr().err == ""
    out.unlink()
    monkeypatch.setattr(spiflash, "__version__", "9.9.post9")
    assert main(["generate", "-o", str(out), "--level", "id"]) == 0
    assert capsys.readouterr().err == (
        f"uspiflash: warning: output is verified byte-identical to spiflash "
        f"{uspiflash.VERIFIED_SPIFLASH}; spiflash 9.9.post9 is installed\n"
    )
    assert out.is_file()


def test_the_lock_pins_the_verified_spiflash() -> None:
    """So every normal CI job runs the parity tests in full."""
    lock = Path(__file__).resolve().parent.parent / "uv.lock"
    if not lock.is_file():
        pytest.skip("no uv.lock (an sdist or a Debian build)")
    packages = tomllib.loads(lock.read_text(encoding="utf-8"))["package"]
    (pinned,) = (p["version"] for p in packages if p["name"] == "spiflash")
    assert pinned == uspiflash.VERIFIED_SPIFLASH


def test_a_daily_job_runs_parity_against_the_newest_spiflash() -> None:
    """The drift alarm: scheduled, never on a pull request, parity forced."""
    workflow = Path(__file__).resolve().parent.parent / ".github/workflows/spiflash-latest.yml"
    if not workflow.is_file():
        pytest.skip("no .github/ (an sdist or a Debian build)")
    text = workflow.read_text(encoding="utf-8")
    assert "  schedule:\n" in text
    assert "pull_request" not in text
    assert "uv pip install --upgrade spiflash" in text
    assert f'{FORCE_PARITY}: "1"' in text
    assert "uv run --no-sync pytest" in text


def test_generate_refuses_a_broken_selection(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["generate", "-o", "-", "--without", "names"]) == 2
    assert "text needs names" in capsys.readouterr().err


def test_generate_refuses_a_filter_that_keeps_no_chips(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "x.h"
    assert main(["generate", "-o", str(out), "--min-size", "2", "--max-size", "1"]) == 2
    assert "uspiflash: the chip filter keeps no chips" in capsys.readouterr().err
    assert not out.exists()


def test_stdint_is_included_outside_extern_c() -> None:
    text = emit.render(FULL)
    assert text.index("#include <stdint.h>") < text.index('extern "C" {')
