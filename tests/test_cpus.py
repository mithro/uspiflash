"""Each CPU, how each compiler family selects it, SDCC's objects, and the
runtime symbols a port may need (spec amendment 17)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from spiflash.enums import FlashType

from uspiflash import emit, measure
from uspiflash.levels import ChipFilter, Selection
from uspiflash.measure import CPUS, TARGETS, MeasureError
from uspiflash.provenance import Config

#: SDCC 4.5.0's object for the mcs51 id:nor implementation (areas and
#: symbols only; 2026-09-30).
MCS51_REL = """\
XH3
H 1B areas E global symbols
M s
O -mmcs51 --model-small
S __gptrput Ref000000
S .__.ABS. Def000000
S __gptrget Ref000000
A _CODE size 0 flags 0 addr 0
A REG_BANK_0 size 8 flags 4 addr 0
A DSEG size 39 flags 0 addr 0
S _usf_probe_PARM_2 Def000015
A OSEG size 13 flags 4 addr 0
S _usf_lookup_PARM_2 Def000000
A BSEG size 1 flags 80 addr 0
A CSEG size 742 flags 20 addr 0
S _usf_lookup Def000000
A CONST size D04 flags 20 addr 0
"""


#: SDCC 4.5.0's object for the z80 id:nor implementation, as
#: `sdcc -mz80 --std-c99 --opt-code-size --Werror --disable-warning 110 -c`
#: wrote it (2026-10-01, pinned trixie image): its areas' names start with
#: `_`, and the tables are in _CODE with the code. Areas and symbols only.
Z80_REL = """\
XL4
H 9 areas 9 global symbols
M z
O -mz80 sdcccall(1)
S ___sdcc_call_iy Ref00000000
S ___sdcc_enter_ix Ref00000000
A _CODE size 1211 flags 0 addr 0
S _usf_lookup Def00000000
A _DATA size 0 flags 0 addr 0
A _INITIALIZED size 0 flags 0 addr 0
A _DABS size 0 flags 8 addr 0
A _HOME size 0 flags 0 addr 0
A _GSINIT size 0 flags 0 addr 0
A _GSFINAL size 0 flags 0 addr 0
A _INITIALIZER size 0 flags 0 addr 0
A _CABS size 0 flags 8 addr 0
"""


def test_an_sdcc_object_is_read() -> None:
    sizes, undefined = measure.rel_contents(MCS51_REL)
    assert sizes.text == 0x742
    assert sizes.rodata == 0xD04
    # Writable areas are bss until the check compile shows they are frames.
    assert sizes.bss == 0x39 + 0x13 + 1
    assert (sizes.data, sizes.frames) == (0, 0)
    assert sizes.total == 0x742 + 0xD04
    assert undefined == ["__gptrget", "__gptrput"]


def test_a_z80_object_is_read() -> None:
    sizes, undefined = measure.rel_contents(Z80_REL)
    assert sizes.sections["text"] == {"CODE": 0x1211}
    assert (sizes.rodata, sizes.data, sizes.bss) == (0, 0, 0)
    assert undefined == ["___sdcc_call_iy", "___sdcc_enter_ix"]


def test_decimal_sdcc_objects_are_read() -> None:
    sizes, _ = measure.rel_contents("DL2\nA CSEG size 100 flags 0 addr 0\n")
    assert sizes.text == 100


def test_an_unknown_sdcc_area_is_refused() -> None:
    with pytest.raises(MeasureError, match="unknown SDCC area WEIRD"):
        measure.rel_contents("XH3\nA _WEIRD size 4 flags 0 addr 0\n")


def test_sdcc_static_data_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A writable static survives --stack-auto (locals do not): refused."""
    if measure.find_tool("sdcc") is None:
        pytest.skip("sdcc not installed")
    code = "unsigned char usf_counter;\nvoid usf_f(void);\nvoid usf_f(void) { usf_counter++; }\n"
    monkeypatch.setattr(emit, "render", lambda _c: code)
    with pytest.raises(MeasureError, match="mcs51: the library has writable static data"):
        measure.measure(Config(Selection.make("id")), measure.target("mcs51", "sdcc"), tmp_path)


def test_the_reference_targets_are_cpus() -> None:
    assert [t.name for t in TARGETS] == ["cortex-m0", "rv32imc", "x86_64"]
    assert TARGETS[0] == measure.target("cortex-m0", "clang")
    assert TARGETS[0].link_flags == ("-fuse-ld=lld",)
    assert TARGETS[2].link_flags == ("-no-pie",)


def test_families() -> None:
    assert measure.family_of("clang-19") == "clang"
    assert measure.family_of("/opt/toolchains/x/bin/riscv-none-elf-gcc") == "gcc"
    assert measure.family_of("sdcc") == "sdcc"
    assert measure.target("mcs51", "sdcc").family == "sdcc"


def test_sdcc_targets_are_unlinked_and_list_their_runtime() -> None:
    t = measure.target("mcs51", "sdcc")
    assert t.link_flags is None
    assert not t.stack
    assert t.runtime == {"__gptrget", "__gptrput"}
    assert "--Werror" in t.flags
    assert "-fstack-usage" not in t.flags


def test_a_family_that_cannot_build_a_cpu_is_refused() -> None:
    with pytest.raises(ValueError, match="gcc cannot build for msp430"):
        measure.target("msp430", "gcc")


def test_every_cpu_is_buildable_and_explains_its_runtime() -> None:
    for cpu in CPUS.values():
        assert (cpu.clang, cpu.gcc, cpu.sdcc) != (None, None, None), cpu.name
        for symbol, why in cpu.runtime:
            assert symbol
            assert len(why) > 20, (cpu.name, symbol)
        if cpu.sdcc is not None:
            assert not cpu.link, cpu.name
            assert cpu.small, cpu.name


def test_litex_hard_cpus_are_size_tracking() -> None:
    """LiteX's hard CPUs (litex/soc/cores/cpu at 8c01073, "hardcore"):
    size tracking only, and labelled so."""
    for name in ("cortex-m3", "cortex-m4", "cortex-a9", "cortex-a53", "rv32imafdc"):
        assert "LiteX" in CPUS[name].note, name


def test_a_listed_runtime_symbol_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = replace(TARGETS[-1], runtime=frozenset({"usf_ext"}), link_flags=None)
    if not measure.usable(target):
        pytest.skip("the x86_64 target cannot be measured here")
    code = "int usf_ext(int x);\nint usf_f(int x);\nint usf_f(int x) { return usf_ext(x); }\n"
    monkeypatch.setattr(emit, "render", lambda _c: code)
    measure.measure(Config(Selection.make("id")), target, tmp_path)  # no MeasureError


def test_sdcc_measures_stm8(tmp_path: Path) -> None:
    if measure.find_tool("sdcc") is None:
        pytest.skip("sdcc not installed")
    config = Config(Selection.make("id", chips=ChipFilter(types=(FlashType.NOR,))))
    sizes = measure.measure(config, measure.target("stm8", "sdcc"), tmp_path)
    assert sizes.text > 0
    assert sizes.rodata > 0
    assert sizes.stack is None
    assert sizes.linked is None


def _fake_sdcc(tmp_path: Path, plain: str, stack_auto: str) -> str:
    """An ``sdcc`` that writes ``plain`` as its object, or ``stack_auto``
    under ``--stack-auto``: the SDCC path, without SDCC."""
    (tmp_path / "plain.rel").write_text(plain)
    (tmp_path / "auto.rel").write_text(stack_auto)
    sdcc = tmp_path / "bin" / "sdcc"
    sdcc.parent.mkdir()
    sdcc.write_text(
        "#!/bin/sh\n"
        f"src={tmp_path}/plain.rel\n"
        "for a; do\n"
        f'  [ "$a" = --stack-auto ] && src={tmp_path}/auto.rel\n'
        '  [ "$prev" = -o ] && out="$a"\n'
        '  prev="$a"\n'
        "done\n"
        'cp "$src" "$out"\n'
    )
    sdcc.chmod(0o755)
    return str(sdcc)


def test_sdcc_writable_areas_are_frames_without_static_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdcc = _fake_sdcc(tmp_path, MCS51_REL, "XH3\nA CSEG size 800 flags 20 addr 0\n")
    monkeypatch.setattr(emit, "render", lambda _c: "")
    target = replace(measure.target("mcs51", "sdcc"), compiler=sdcc)
    sizes = measure.measure(Config(Selection.make("id")), target, tmp_path / "w")
    assert sizes.frames == 0x39 + 0x13 + 1
    assert (sizes.bss, sizes.text, sizes.rodata) == (0, 0x742, 0xD04)
    assert sizes.to_json()["frames"] == sizes.frames
    assert (sizes.stack, sizes.linked) == (None, None)


def test_sdcc_static_data_is_refused_by_the_check_compile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdcc = _fake_sdcc(tmp_path, MCS51_REL, "XH3\nA DSEG size 2 flags 0 addr 0\n")
    monkeypatch.setattr(emit, "render", lambda _c: "")
    target = replace(measure.target("mcs51", "sdcc"), compiler=sdcc)
    with pytest.raises(MeasureError, match=r"mcs51: .*writable static data \(data 0, bss 2"):
        measure.measure(Config(Selection.make("id")), target, tmp_path / "w")


def test_an_unlisted_sdcc_runtime_symbol_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdcc = _fake_sdcc(tmp_path, MCS51_REL, "XH3\n")
    monkeypatch.setattr(emit, "render", lambda _c: "")
    target = replace(measure.target("stm8", "sdcc"), compiler=sdcc)
    with pytest.raises(MeasureError, match="needs symbols from elsewhere: __gptrget, __gptrput"):
        measure.measure(Config(Selection.make("id")), target, tmp_path / "w")


def test_a_failed_sdcc_check_compile_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdcc = _fake_sdcc(tmp_path, MCS51_REL, "")
    script = Path(sdcc)
    script.write_text(script.read_text().replace('cp "$src"', '[ -s "$src" ] || exit 1\ncp "$src"'))
    monkeypatch.setattr(emit, "render", lambda _c: "")
    target = replace(measure.target("mcs51", "sdcc"), compiler=sdcc)
    with pytest.raises(MeasureError, match=r"--stack-auto -c .* failed"):
        measure.measure(Config(Selection.make("id")), target, tmp_path / "w")
