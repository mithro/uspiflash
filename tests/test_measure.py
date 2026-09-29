"""Measuring a generated file's compiled size (uspiflash.measure)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from uspiflash import emit, measure
from uspiflash.levels import Selection
from uspiflash.measure import TARGETS, MeasureError, Sizes, Target
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

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
