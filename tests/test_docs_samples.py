"""Every ``{.compile}``-tagged C sample in docs/generated-file.md compiles
against a generated header, with the same strict flags the C tests use."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from harness import compile_c, generate
from uspiflash.levels import Selection
from uspiflash.provenance import Config

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "generated-file.md"
#: A fenced ```c {.compile} ... ``` block (MyST block attributes).
_BLOCK_RE = re.compile(r"```c \{\.compile\}\n(.*?)\n```", re.DOTALL)

#: One header, full enough for every sample: usf_probe, usf_size, usf_print
#: (with USF_PRINT_OPCODES) and usf_print_json all need to exist.
_CONFIG = Config(Selection.make("full", with_=["sfdp"]))


def _samples() -> list[str]:
    text = DOC.read_text(encoding="utf-8")
    samples = _BLOCK_RE.findall(text)
    assert samples, f"no {{.compile}} blocks found in {DOC}"
    return samples


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not installed")
@pytest.mark.parametrize(("i", "sample"), list(enumerate(_samples())))
def test_sample_compiles(tmp_path: Path, i: int, sample: str) -> None:
    header = generate(tmp_path, _CONFIG)
    src = tmp_path / f"sample_{i}.c"
    src.write_text(sample, encoding="utf-8")
    obj = tmp_path / f"sample_{i}.o"
    compile_c("gcc", [src], obj, ["-c", f"-I{header.parent}"])
