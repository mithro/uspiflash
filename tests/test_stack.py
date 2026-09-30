"""The stack a library call can use: each function's frame from
-fstack-usage, and the deepest path through the call graph."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from uspiflash import measure
from uspiflash.levels import Selection
from uspiflash.measure import TARGETS, MeasureError, Target
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from pathlib import Path

GCC_SU = "uspiflash.h:765:15:usf__idrec\t8\tstatic\nuspiflash.h:812:9:usf_lookup\t32\tstatic\n"
CLANG_SU = "./uspiflash.h:812:usf_lookup\t44\tstatic\n./uspiflash.h:860:usf_id\t16\tstatic\n"


def test_frames_from_gcc_and_clang() -> None:
    assert measure.stack_frames(GCC_SU) == {"usf__idrec": 8, "usf_lookup": 32}
    assert measure.stack_frames(CLANG_SU) == {"usf_lookup": 44, "usf_id": 16}


#: gcc 14 for i386 (Debian's i386 package build runs these tests): stack
#: realignment makes a frame "dynamic,bounded", the size an upper bound.
I386_SU = (
    "uspiflash.h:812:9:usf_lookup\t44\tdynamic,bounded\nuspiflash.h:860:9:usf_id\t20\tstatic\n"
)


def test_a_bounded_dynamic_frame_counts_its_bound() -> None:
    assert measure.stack_frames(I386_SU) == {"usf_lookup": 44, "usf_id": 20}


def test_an_unbounded_frame_is_refused() -> None:
    with pytest.raises(MeasureError, match="usf_f has an unbounded stack frame"):
        measure.stack_frames("x.h:1:2:usf_f\t16\tdynamic\n")


def test_peak_is_the_deepest_path() -> None:
    graph = {"a": {"b", "c"}, "b": {"d"}, "c": set(), "d": set(), "e": {"c"}}
    frames = {"a": 10, "b": 20, "c": 50, "d": 5, "e": 1}
    assert measure.stack_peak(graph, frames, ["a", "e"]) == (60, ("a", "c"))


def test_a_clone_takes_its_functions_frame() -> None:
    graph = {"a": {"b.constprop.0"}, "b.constprop.0": set()}
    assert measure.stack_peak(graph, {"a": 8, "b": 16}, ["a"]) == (24, ("a", "b.constprop.0"))
    # GCC's .su file names the clone b.isra for the symbol b.isra.0 (gcc 14).
    graph = {"a": {"b.isra.0"}, "b.isra.0": set()}
    frames = {"a": 8, "b.isra": 12, "b": 99}
    assert measure.stack_peak(graph, frames, ["a"]) == (20, ("a", "b.isra.0"))


def test_recursion_is_refused() -> None:
    graph = {"a": {"b"}, "b": {"a"}}
    with pytest.raises(MeasureError, match="recursion: a -> b -> a"):
        measure.stack_peak(graph, {"a": 1, "b": 1}, ["a"])


def test_a_function_without_a_frame_is_refused() -> None:
    with pytest.raises(MeasureError, match="no -fstack-usage entry for b"):
        measure.stack_peak({"a": {"b"}, "b": set()}, {"a": 1}, ["a"])


@pytest.mark.parametrize("target", TARGETS, ids=lambda t: t.name)
def test_measured_objects_have_a_stack_and_symbols(tmp_path: Path, target: Target) -> None:
    if measure.find_tool(target.compiler) is None:
        pytest.skip(f"{target.compiler} not installed")
    sizes = measure.measure(Config(Selection.make("id")), target, tmp_path)
    assert sizes.stack is not None
    assert sizes.stack.path[0] in {"usf_probe", "usf_lookup", "usf_id"}
    assert sizes.stack.peak == sum(measure.frame(sizes.stack.frames, f) for f in sizes.stack.path)
    assert sizes.symbols["usf_probe"] > 0
    assert "usf__ids" in sizes.symbols
    assert sizes.to_json()["stack"] == sizes.stack.to_json()
