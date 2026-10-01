"""Measuring a generated file's compiled size (uspiflash.measure)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from spiflash.enums import FlashType

from uspiflash import emit, ledger, measure, research
from uspiflash.cli import main
from uspiflash.levels import LEVELS, Selection
from uspiflash.measure import TARGETS, MeasureError, Sizes, Target
from uspiflash.provenance import Config

ID = Config(Selection.make("id"))


def available(target: Target) -> bool:
    """Whether ``target`` can be measured here (:func:`uspiflash.measure.usable`)."""
    return measure.usable(target)


@pytest.mark.parametrize("target", TARGETS, ids=lambda t: t.name)
def test_id_measures_code_and_tables_and_no_ram(tmp_path: Path, target: Target) -> None:
    if not available(target):
        pytest.skip(f"{target.name} cannot be measured here")
    sizes = measure.measure(ID, target, tmp_path)
    assert sizes.text > 0
    assert sizes.rodata > 0
    assert (sizes.data, sizes.bss) == (0, 0)
    assert sizes.total == sizes.text + sizes.rodata
    assert sizes.sections["text"][".text.usf_probe"] > 0
    names = {n for kind in sizes.sections.values() for n in kind}
    # Not allocated: not recorded. No unwind tables but Arm's index.
    assert not names & {".comment", ".symtab", ".strtab", ".eh_frame"}


def test_sections_are_classified_by_flags() -> None:
    w, a, x = 0x1, 0x2, 0x4
    progbits, nobits, exidx = 1, 8, 0x70000001
    assert measure.kind(a | x, progbits) == "text"
    assert measure.kind(a, progbits) == "rodata"
    assert measure.kind(a | 0x80, exidx) == "rodata"  # .ARM.exidx: SHF_LINK_ORDER
    assert measure.kind(a | w, progbits) == "data"
    assert measure.kind(a | w, nobits) == "bss"
    assert measure.kind(0x30, progbits) is None  # .comment: merge, strings
    assert measure.kind(0, 2) is None  # .symtab


def test_sizes_sum_each_kind() -> None:
    sizes = Sizes(
        {
            "text": {".text": 0, ".text.f": 10},
            "rodata": {".rodata.t": 5, ".ARM.exidx.text.f": 8, ".flashy": 3},
            "data": {},
            "bss": {".bss.y": 7},
        }
    )
    assert (sizes.text, sizes.rodata, sizes.data, sizes.bss) == (10, 16, 0, 7)
    assert sizes.total == 26
    assert sizes.to_json()["sections"] == {
        "text": {".text": 0, ".text.f": 10},
        "rodata": {".rodata.t": 5, ".ARM.exidx.text.f": 8, ".flashy": 3},
        "bss": {".bss.y": 7},
    }


#: A table in a section of its own name: counted because it is allocated and
#: read-only, whatever it is called.
FLASHY = (
    'const char usf_t[7] __attribute__((section(".flashy"))) = "abcdef";\n'
    "int usf_f(int i);\n"
    "int usf_f(int i) { return usf_t[i]; }\n"
)


@pytest.mark.parametrize("target", TARGETS, ids=lambda t: t.name)
def test_every_allocated_read_only_section_is_in_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: Target
) -> None:
    if not available(target):
        pytest.skip(f"{target.name} cannot be measured here")
    monkeypatch.setattr(emit, "render", lambda _c: FLASHY)
    sizes = measure.measure(ID, target, tmp_path)
    assert sizes.sections["rodata"][".flashy"] == 7
    read_only = [*sizes.sections["text"].values(), *sizes.sections["rodata"].values()]
    assert sizes.total == sum(read_only)
    assert sizes.total > 7
    if target.name == "cortex-m0":
        # clang emits Arm's unwind index even with -fno-unwind-tables.
        assert sizes.sections["rodata"][".ARM.exidx.text.usf_f"] == 8


def test_find_tool_prefers_the_plain_name_then_the_newest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("llvm-readobj-9", "llvm-readobj-19", "llvm-readobj-x", "clang-19"):
        exe = tmp_path / name
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
    (tmp_path / "llvm-readobj-20").write_text("not executable")
    monkeypatch.setenv("PATH", f"{tmp_path / 'missing'}{os.pathsep}{tmp_path}")
    assert measure.find_tool("llvm-readobj") == str(tmp_path / "llvm-readobj-19")
    (tmp_path / "clang").write_text("#!/bin/sh\n")
    (tmp_path / "clang").chmod(0o755)
    assert measure.find_tool("clang") == str(tmp_path / "clang")
    assert measure.find_tool("gcc") is None


@pytest.mark.parametrize(
    ("name", "package"),
    [("clang", "clang"), ("gcc", "gcc"), ("ld.lld", "lld"), ("ld", "binutils")],
)
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
        "llvm-readobj": "llvm-readobj-19\nDebian LLVM version 19.1.7\n  Optimized build.\n",
        "gcc": "gcc (Debian 14.2.0-19) 14.2.0\nCopyright (C) 2024\n",
        "ld": (
            "GNU ld (GNU Binutils for Debian) 2.44\nCopyright (C) 2025\n"
            "the GNU General Public License version 3 or later.\n"
        ),
    }
    for name, text in fake.items():
        exe = tmp_path / name
        # PATH holds only tmp_path, so only shell builtins are available.
        exe.write_text("#!/bin/sh\n" + "".join(f"echo '{line}'\n" for line in text.splitlines()))
        exe.chmod(0o755)
    (tmp_path / "clang").write_text("#!/bin/sh\necho broken >&2\nexit 1\n")
    (tmp_path / "clang").chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert measure.version("llvm-readobj") == "Debian LLVM version 19.1.7"
    assert measure.version("gcc") == "gcc (Debian 14.2.0-19) 14.2.0"
    assert measure.version("ld") == "GNU ld (GNU Binutils for Debian) 2.44"
    with pytest.raises(MeasureError, match="clang --version failed:\nbroken"):
        measure.version("clang")


def _host() -> Target:
    target = next(t for t in TARGETS if t.name == "x86_64")
    if not available(target):
        pytest.skip("x86_64 cannot be measured here")
    return target


def test_writable_static_data_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _host()
    monkeypatch.setattr(emit, "render", lambda _c: "int usf_counter = 1;\nint usf_zero;\n")
    with pytest.raises(MeasureError, match=r"writable static data \(data 4, bss 4 bytes\)"):
        measure.measure(ID, target, tmp_path)


@pytest.mark.parametrize("target", TARGETS, ids=lambda t: t.name)
def test_an_undefined_symbol_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: Target
) -> None:
    """Links nothing: a call out of the library fails measuring, on every
    target."""
    if not available(target):
        pytest.skip(f"{target.name} cannot be measured here")
    code = "int usf_ext(int x);\nint usf_f(int x);\nint usf_f(int x) { return usf_ext(x); }\n"
    monkeypatch.setattr(emit, "render", lambda _c: code)
    with pytest.raises(MeasureError, match=f"{target.name}: .* from elsewhere: usf_ext"):
        measure.measure(ID, target, tmp_path)


def test_a_compiler_helper_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = next(t for t in TARGETS if t.name == "cortex-m0")
    if not available(target):
        pytest.skip("cortex-m0 cannot be measured here")
    code = (
        "unsigned usf_div(unsigned a, unsigned b);\n"
        "unsigned usf_div(unsigned a, unsigned b) { return a / b; }\n"
    )
    monkeypatch.setattr(emit, "render", lambda _c: code)
    with pytest.raises(MeasureError, match="from elsewhere: __aeabi_uidiv"):
        measure.measure(ID, target, tmp_path)


def test_a_compiler_diagnostic_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _host()
    monkeypatch.setattr(emit, "render", lambda _c: "static int unused;\n")
    with pytest.raises(MeasureError, match="unused"):
        measure.measure(ID, target, tmp_path)


def test_config_names_are_unique() -> None:
    names = [n for n, _ in measure.CONFIGS]
    assert len(set(names)) == len(names)
    assert len({t.name for t in TARGETS}) == len(TARGETS)


def test_spi_nor_is_measured_first_at_every_level() -> None:
    """SPI NOR is the primary target: a NOR-only build of every level leads
    the ledger, and the README's headline figures are NOR-only."""
    nor = [f"{level}:nor" for level in LEVELS]
    assert [n for n, _ in measure.CONFIGS[: len(nor)]] == nor
    for name, config in measure.CONFIGS[: len(nor)]:
        assert config.selection.chips.types == (FlashType.NOR,), name
    assert set(ledger.HEADLINE) <= set(nor)
    names = [n for n, _ in measure.CONFIGS]
    assert {*LEVELS, "read:nand", "full:nand"} <= set(names)


# The ledger and ``uspiflash measure`` (uspiflash.ledger, uspiflash.cli).

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def small(monkeypatch: pytest.MonkeyPatch) -> list[Target]:
    """Measure only ``id``, on the targets whose tools are installed."""
    targets = [t for t in TARGETS if available(t)]
    if not targets:
        pytest.skip("no target can be measured here")
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
    assert set(data["tools"]) == set(ledger.tools(small))
    # Every type (the library's default) is spelt out: ``generate`` alone keeps SPI NOR.
    assert data["configs"][0]["options"] == ["--level", "id", "--type", "nor", "--type", "nand"]
    assert data["configs"][0]["config"] == ID.to_json()


def test_a_native_target_refuses_a_wrong_default_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A target with no ``target_flags`` (a compiler's default CPU) must be
    what its compiler actually builds for by default here, else ``build``
    would silently measure host-CPU code under the wrong target name (as
    happens for the ``x86_64`` target on an i386 or arm64 host)."""
    target = Target("x86_64", "gcc", link_flags=("-no-pie",))
    monkeypatch.setattr(measure, "default_machine", lambda _compiler: "i686")
    with pytest.raises(MeasureError, match="gcc builds for i686 by default"):
        ledger.build(tmp_path, configs=(("id", ID),), targets=(target,))


def test_a_native_target_accepts_a_right_default_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ppc64le's gcc target also has no ``target_flags`` (``CPUS["ppc64le"].gcc``
    is ``()``): the check above must accept it when the compiler's default
    machine actually matches, not only refuse a mismatch. The same stubbed
    ``default_machine`` must still refuse a genuinely wrong native target
    (``x86_64``), so the acceptance is not just a check that was skipped."""
    monkeypatch.setattr(measure, "default_machine", lambda _compiler: "powerpc64le")
    monkeypatch.setattr(measure, "version", lambda _name: "stub 1.0")
    monkeypatch.setattr(measure, "linker", lambda _target: None)
    monkeypatch.setattr(measure, "measure", lambda _config, _target, _workdir: Sizes({}))

    ppc = measure.target("ppc64le", "gcc")
    result = ledger.build(tmp_path, configs=(("id", ID),), targets=(ppc,))
    assert result["targets"][0]["name"] == "ppc64le"

    x86 = Target("x86_64", "gcc", link_flags=("-no-pie",))
    with pytest.raises(MeasureError, match="gcc builds for powerpc64le by default"):
        ledger.build(tmp_path, configs=(("id", ID),), targets=(x86,))


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


def test_scratch_files_go_in_the_roots_tmp_and_are_removed(
    tmp_path: Path, small: list[Target]
) -> None:
    del small
    data = ledger.measure_fresh(tmp_path)
    assert data["configs"][0]["name"] == "id"
    assert (tmp_path / "tmp").is_dir()
    assert list((tmp_path / "tmp").iterdir()) == []


def test_measure_outside_a_repository_uses_the_current_directorys_tmp(
    tmp_path: Path,
    small: list[Target],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del small
    monkeypatch.chdir(tmp_path)
    find_root = research.find_root
    monkeypatch.setattr(research, "find_root", lambda d: find_root(d, ceiling=tmp_path))
    assert main(["measure"]) == 0
    assert "| `id` |" in capsys.readouterr().out
    assert list((tmp_path / "tmp").iterdir()) == []


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
    # tmp_path is inside the repository (tmp/): look no higher than it.
    find_root = research.find_root
    monkeypatch.setattr(research, "find_root", lambda d: find_root(d, ceiling=tmp_path))
    assert main(["measure", "--write"]) == 2
    assert "no experiments/ directory" in capsys.readouterr().err


def test_the_committed_files_match_the_committed_ledger() -> None:
    """Cheap and compiler-free: the generated files were not hand-edited.
    (CI's sizes job checks the numbers themselves.)"""
    data = ledger.committed(ROOT)
    assert data is not None
    files = ledger.files(data, ROOT)
    assert ledger.TOP_README in files
    assert ledger.REFERENCE in files
    for path, text in files.items():
        assert (ROOT / path).read_text(encoding="utf-8") == text, path
    assert [c["name"] for c in data["configs"]] == [n for n, _ in measure.CONFIGS]
    assert [t["name"] for t in data["targets"]] == [t.name for t in TARGETS]
    assert data["environment"] == {
        "image": ledger.IMAGE,
        "packages": list(ledger.PACKAGES),
        "snapshot": ledger.SNAPSHOT,
    }


def test_ci_checks_the_ledger_in_the_pinned_image() -> None:
    path = ROOT / ".github" / "workflows" / "deb.yml"
    if not path.is_file():
        pytest.skip("no .github/ (an sdist)")
    workflow = path.read_text(encoding="utf-8")
    job = workflow[workflow.index("\n  sizes:\n") :].split("\n  build-deb:\n")[0]
    assert f"    container: {ledger.IMAGE}\n" in job
    install = job[job.index("apt-get install") :].split("\n\n")[0].split()
    assert set(ledger.PACKAGES) <= set(install)
    _assert_snapshot_install(job)


def _assert_snapshot_install(script: str) -> None:
    """``script`` installs from the pinned snapshot only: the default
    sources removed, the snapshot line in their place, and apt told that a
    snapshot's expired Release file is expected."""
    assert "rm -f /etc/apt/sources.list.d/debian.sources" in script
    assert f'echo "{ledger.APT_SOURCE}" > /etc/apt/sources.list' in script
    assert "Acquire::Check-Valid-Until" in script
    first = script.index("rm -f /etc/apt/sources.list.d/debian.sources")
    assert first < script.index("apt-get update")


def test_releasing_regenerates_from_the_same_snapshot() -> None:
    releasing = ROOT / "RELEASING.md"
    if not releasing.is_file():
        pytest.skip("no RELEASING.md (an sdist)")
    text = releasing.read_text(encoding="utf-8")
    command = text[text.index("## The size ledger's image") :]
    command = command[command.index("```sh\n   IMAGE=") :].split("   ```\n")[0]
    _assert_snapshot_install(command)


def test_write_updates_the_readme_figures(
    tmp_path: Path,
    small: list[Target],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(measure, "CONFIGS", tuple((name, ID) for name in ledger.HEADLINE))
    top = tmp_path / "README.md"
    top.write_text(f"# x\n\n{ledger.BEGIN}\nstale\n{ledger.END}\n\nmore\n")
    assert main(["measure", "--write", "--root", str(tmp_path)]) == 0
    text = top.read_text()
    data = json.loads((tmp_path / "sizes" / "ledger.json").read_text())
    assert text == f"# x\n\n{ledger.BEGIN}\n{ledger.summary(data)}\n{ledger.END}\n\nmore\n"
    total = data["sizes"][small[0].name]["full:nor"]["total"]
    assert f"**{total:,} bytes**" in text
    top.write_text(text.replace(f"{total:,}", "1"))
    capsys.readouterr()
    assert main(["measure", "--check", "--root", str(tmp_path)]) == 1
    assert "--- README.md (committed)" in capsys.readouterr().out
    top.write_text("# no markers\n")
    assert main(["measure", "--write", "--root", str(tmp_path)]) == 2
    assert "README.md has no <!-- sizes:" in capsys.readouterr().err


def test_the_sfdp_extras_are_measured_nor_first() -> None:
    names = [n for n, _ in measure.CONFIGS]
    nor = ["id+sfdp:nor", "read+sfdp:nor", "full-sfdp_summary:nor", "full+sfdp_dumps:nor"]
    assert names[len(LEVELS) : len(LEVELS) + len(nor)] == nor
    assert "full+sfdp+sfdp_dumps" in names
