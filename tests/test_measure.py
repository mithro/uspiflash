"""Measuring a generated file's compiled size (uspiflash.measure)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from uspiflash import emit, ledger, measure
from uspiflash.cli import main
from uspiflash.levels import Selection
from uspiflash.measure import TARGETS, MeasureError, Sizes, Target
from uspiflash.provenance import Config

ID = Config(Selection.make("id"))


def available(target: Target) -> bool:
    """Whether ``target``'s compiler and the size tool are installed."""
    return all(measure.find_tool(t) for t in (target.compiler, measure.SIZE_TOOL))


@pytest.mark.parametrize("target", TARGETS, ids=lambda t: t.name)
def test_id_measures_code_and_tables_and_no_ram(tmp_path: Path, target: Target) -> None:
    if not available(target):
        pytest.skip(f"{target.compiler} or {measure.SIZE_TOOL} not installed")
    sizes = measure.measure(ID, target, tmp_path)
    assert sizes.text > 0
    assert sizes.rodata > 0
    assert (sizes.data, sizes.bss) == (0, 0)
    assert sizes.total == sizes.text + sizes.rodata
    assert sizes.sections[".text.usf_probe"] > 0


def test_sections_are_summed_by_kind() -> None:
    sizes = Sizes(
        {
            ".text": 0,
            ".text.f": 10,
            ".rodata.t": 5,
            ".srodata.cst4": 4,
            ".rodata": 1,
            ".sdata.x": 2,
            ".data": 3,
            ".bss.y": 7,
            ".sbss": 1,
            ".ARM.exidx.text.f": 8,
            ".eh_frame": 40,
            ".comment": 36,
            ".textual": 99,
        }
    )
    assert (sizes.text, sizes.rodata, sizes.data, sizes.bss) == (10, 10, 5, 8)
    assert sizes.total == 25
    assert sizes.to_json()["sections"] == sizes.sections


def test_find_tool_prefers_the_plain_name_then_the_newest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("llvm-size-9", "llvm-size-19", "llvm-size-x", "clang-19"):
        exe = tmp_path / name
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
    (tmp_path / "llvm-size-20").write_text("not executable")
    monkeypatch.setenv("PATH", f"{tmp_path / 'missing'}{os.pathsep}{tmp_path}")
    assert measure.find_tool("llvm-size") == str(tmp_path / "llvm-size-19")
    (tmp_path / "clang").write_text("#!/bin/sh\n")
    (tmp_path / "clang").chmod(0o755)
    assert measure.find_tool("clang") == str(tmp_path / "clang")
    assert measure.find_tool("gcc") is None


@pytest.mark.parametrize(("name", "package"), [("clang", "clang"), ("llvm-size", "llvm")])
def test_a_missing_tool_names_its_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, package: str
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(MeasureError, match=f"{name} not found on PATH \\(install {package}\\)"):
        measure.tool(name)


def test_version_is_the_line_naming_the_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = {
        "llvm-size": "llvm-size-19\nDebian LLVM version 19.1.7\n  Optimized build.\n",
        "gcc": "gcc (Debian 14.2.0-19) 14.2.0\nCopyright (C) 2024\n",
    }
    for name, text in fake.items():
        exe = tmp_path / name
        # PATH holds only tmp_path, so only shell builtins are available.
        exe.write_text("#!/bin/sh\n" + "".join(f"echo '{line}'\n" for line in text.splitlines()))
        exe.chmod(0o755)
    (tmp_path / "clang").write_text("#!/bin/sh\necho broken >&2\nexit 1\n")
    (tmp_path / "clang").chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert measure.version("llvm-size") == "Debian LLVM version 19.1.7"
    assert measure.version("gcc") == "gcc (Debian 14.2.0-19) 14.2.0"
    with pytest.raises(MeasureError, match="clang --version failed:\nbroken"):
        measure.version("clang")


def _host() -> Target:
    target = next(t for t in TARGETS if t.name == "x86_64")
    if not available(target):
        pytest.skip("gcc or llvm-size not installed")
    return target


def test_writable_static_data_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _host()
    monkeypatch.setattr(emit, "render", lambda _c: "int usf_counter = 1;\n")
    with pytest.raises(MeasureError, match=r"writable static data \(data 4, bss 0 bytes\)"):
        measure.measure(ID, target, tmp_path)


def test_a_compiler_diagnostic_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _host()
    monkeypatch.setattr(emit, "render", lambda _c: "static int unused;\n")
    with pytest.raises(MeasureError, match="unused"):
        measure.measure(ID, target, tmp_path)


def test_an_unreadable_object_is_an_error(tmp_path: Path) -> None:
    if measure.find_tool(measure.SIZE_TOOL) is None:
        pytest.skip("llvm-size not installed")
    (tmp_path / "junk.o").write_text("not an object")
    with pytest.raises(MeasureError, match="-A"):
        measure.section_sizes(tmp_path / "junk.o")


def test_config_names_are_unique() -> None:
    names = [n for n, _ in measure.CONFIGS]
    assert len(set(names)) == len(names)
    assert len({t.name for t in TARGETS}) == len(TARGETS)


# The ledger and ``uspiflash measure`` (uspiflash.ledger, uspiflash.cli).

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def small(monkeypatch: pytest.MonkeyPatch) -> list[Target]:
    """Measure only ``id``, on the targets whose tools are installed."""
    targets = [t for t in TARGETS if available(t)]
    if not targets:
        pytest.skip("no target's compiler and llvm-size installed")
    monkeypatch.setattr(measure, "CONFIGS", (("id", ID),))
    monkeypatch.setattr(measure, "TARGETS", tuple(targets))
    return targets


def test_the_ledger_is_deterministic(tmp_path: Path, small: list[Target]) -> None:
    first = ledger.dumps(ledger.build(tmp_path / "a"))
    second = ledger.dumps(ledger.build(tmp_path / "b"))
    assert first == second
    assert first.endswith("}\n")
    data = json.loads(first)
    assert [t["name"] for t in data["targets"]] == [t.name for t in small]
    assert set(data["tools"]) == {*(t.compiler for t in small), measure.SIZE_TOOL}
    assert data["configs"][0]["options"] == ["--level", "id"]
    assert data["configs"][0]["config"] == ID.to_json()


def test_write_then_check_passes(
    tmp_path: Path, small: list[Target], capsys: pytest.CaptureFixture[str]
) -> None:
    del small
    assert main(["measure", "--write", "--root", str(tmp_path)]) == 0
    text = (tmp_path / "sizes" / "ledger.json").read_text()
    assert main(["measure", "--write", "--root", str(tmp_path)]) == 0
    assert (tmp_path / "sizes" / "ledger.json").read_text() == text
    readme = (tmp_path / "sizes" / "README.md").read_text()
    assert readme == ledger.readme(json.loads(text))
    assert "| `id` |" in readme
    assert ledger.REGENERATE in readme
    capsys.readouterr()
    assert main(["measure", "--check", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "sizes/ledger.json is current\n"


def test_check_shows_a_changed_number(
    tmp_path: Path, small: list[Target], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["measure", "--write", "--root", str(tmp_path)]) == 0
    path = tmp_path / "sizes" / "ledger.json"
    data = json.loads(path.read_text())
    data["sizes"][small[0].name]["id"]["text"] += 1
    path.write_text(ledger.dumps(data))
    capsys.readouterr()
    assert main(["measure", "--check", "--root", str(tmp_path)]) == 1
    out, err = capsys.readouterr()
    assert "--- sizes/ledger.json (committed)" in out
    assert "+++ sizes/ledger.json (measured)" in out
    assert "the size ledger is stale" in err


def test_check_without_a_ledger_fails(
    tmp_path: Path, small: list[Target], capsys: pytest.CaptureFixture[str]
) -> None:
    del small
    assert main(["measure", "--check", "--root", str(tmp_path)]) == 1
    assert "+++ sizes/README.md (measured)" in capsys.readouterr().out


def test_check_refuses_other_tool_versions(
    tmp_path: Path, small: list[Target], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["measure", "--write", "--root", str(tmp_path)]) == 0
    path = tmp_path / "sizes" / "ledger.json"
    data = json.loads(path.read_text())
    data["tools"][small[0].compiler] = "clang version 1.0"
    path.write_text(ledger.dumps(data))
    capsys.readouterr()
    assert main(["measure", "--check", "--root", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert f"{small[0].compiler}: the ledger has 'clang version 1.0', installed is" in err
    assert "Regenerate the ledger with those tools" in err


def test_measure_prints_the_tables(small: list[Target], capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["measure"]) == 0
    out = capsys.readouterr().out
    for t in small:
        assert f"## {t.name}\n" in out
    assert "| `id` |" in out


def test_measure_without_tools_names_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    assert main(["measure"]) == 2
    assert "not found on PATH (install" in capsys.readouterr().err


def test_write_needs_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["measure", "--write"]) == 2
    assert "no experiments/ directory" in capsys.readouterr().err


def test_the_committed_files_match_the_committed_ledger() -> None:
    """Cheap and compiler-free: the generated files were not hand-edited.
    (CI's sizes job checks the numbers themselves.)"""
    data = ledger.committed(ROOT)
    assert data is not None
    for path, text in ledger.files(data).items():
        assert (ROOT / path).read_text(encoding="utf-8") == text, path
    assert [c["name"] for c in data["configs"]] == [n for n, _ in measure.CONFIGS]
    assert [t["name"] for t in data["targets"]] == [t.name for t in TARGETS]
