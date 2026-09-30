"""The linked-image cost: the implementation linked on its own, every
public function kept, no C library."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from uspiflash import measure
from uspiflash.levels import Selection
from uspiflash.measure import TARGETS, MeasureError, Target
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

FULL = Config(Selection.make("full"))


def _usable(target: Target) -> None:
    if not measure.usable(target):
        pytest.skip(f"{target.name} cannot be measured here")


def _script(path: Path, output: str) -> str:
    path.write_text(f"#!/bin/sh\necho {output}\n")
    path.chmod(0o755)
    return str(path)


def test_can_link_asks_the_compiler_for_lld(tmp_path: Path) -> None:
    # What clang prints when it finds no ld.lld: the bare name.
    fake = _script(tmp_path / "clang", "ld.lld")
    assert not measure.can_link(Target("m0", fake, link_flags=("-fuse-ld=lld",)))
    assert measure.can_link(Target("x", fake, link_flags=None))
    assert measure.can_link(Target("x", fake, link_flags=("-no-pie",)))


def test_can_link_finds_an_installed_lld(tmp_path: Path) -> None:
    lld = _script(tmp_path / "ld.lld", "LLD 19.1.7")
    fake = _script(tmp_path / "clang", lld)
    assert measure.can_link(Target("m0", fake, link_flags=("-fuse-ld=lld",)))


def test_a_default_cpu_target_needs_that_default(tmp_path: Path) -> None:
    fake = _script(tmp_path / "gcc", "i686-linux-gnu")  # Debian's i386 gcc
    assert not measure.usable(Target("x86_64", fake, link_flags=("-no-pie",)))
    assert measure.default_machine(fake) == "i686"
    native = _script(tmp_path / "cc", "x86_64-linux-gnu")
    assert measure.usable(Target("x86_64", native, link_flags=("-no-pie",)))
    # A target that selects its CPU does not depend on the default.
    assert measure.usable(Target("m", fake, ("-m64",), link_flags=("-no-pie",)))


def test_default_machine_is_empty_when_the_compiler_cannot_say(tmp_path: Path) -> None:
    broken = tmp_path / "gcc"
    broken.write_text("#!/bin/sh\necho no >&2\nexit 1\n")
    broken.chmod(0o755)
    assert measure.default_machine(str(broken)) == ""


def test_a_missing_compiler_is_not_usable() -> None:
    assert not measure.usable(Target("x86_64", "no-such-compiler-uspiflash"))


def test_linker_names_the_linker(tmp_path: Path) -> None:
    fake = _script(tmp_path / "gcc", "/usr/lib/gcc-cross/bin/ld")
    assert measure.linker(Target("x", fake, link_flags=None)) is None
    assert measure.linker(Target("x", fake, link_flags=("-fuse-ld=lld",))) == "ld.lld"
    assert measure.linker(Target("x", fake, link_flags=("-no-pie",))) == (
        "/usr/lib/gcc-cross/bin/ld"
    )
    assert measure.linker(Target("x", _script(tmp_path / "cc", "''"))) == "ld"


@pytest.mark.parametrize("target", TARGETS, ids=lambda t: t.name)
def test_the_linked_image_is_close_to_the_object(tmp_path: Path, target: Target) -> None:
    _usable(target)
    sizes = measure.measure(FULL, target, tmp_path)
    assert sizes.linked is not None
    # Padding and pools add a little; merged strings and unwind entries
    # take a little away (clang's Arm image is smaller than its object).
    assert abs(sizes.linked - sizes.total) < sizes.total // 50
    assert sizes.to_json()["linked"] == sizes.linked


def test_no_linker_means_no_number(tmp_path: Path) -> None:
    target = replace(TARGETS[-1], link_flags=None)
    _usable(target)
    assert measure.measure(Config(Selection.make("id")), target, tmp_path).linked is None


def test_a_failed_link_is_an_error(tmp_path: Path) -> None:
    target = replace(TARGETS[-1], link_flags=("-Wl,--no-such-option",))
    _usable(target)
    with pytest.raises(MeasureError, match="no-such-option"):
        measure.measure(Config(Selection.make("id")), target, tmp_path)


def test_writable_data_in_the_image_is_refused(tmp_path: Path) -> None:
    target = TARGETS[-1]
    _usable(target)
    source = tmp_path / "data.c"
    source.write_text(
        "int usf_counter = 1;\nint usf_f(void);\nint usf_f(void) { return usf_counter; }\n"
    )
    obj = tmp_path / "data.o"
    subprocess.run(measure.compile_command(target, source, obj), check=True, cwd=tmp_path)
    with pytest.raises(
        MeasureError, match=r"x86_64: the linked image has writable data \(4 bytes\)"
    ):
        measure.linked(target, obj)
