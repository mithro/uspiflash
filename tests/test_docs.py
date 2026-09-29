"""The documentation builds with warnings as errors."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from uspiflash.levels import Field

ROOT = Path(__file__).resolve().parent.parent
_SKIP = pytest.mark.skipif(shutil.which("sphinx-build") is None, reason="docs group not installed")


def _build(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-W",
            "--keep-going",
            "-q",
            "-b",
            "html",
            str(ROOT / "docs"),
            str(tmp_path / "html"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@_SKIP
def test_docs_build_without_warnings(tmp_path: Path) -> None:
    out = _build(tmp_path)
    assert out.returncode == 0, out.stderr


@_SKIP
def test_fields_table_lists_every_field(tmp_path: Path) -> None:
    """The ``{fields}`` directive's tables (docs/usage.md, built from
    ``uspiflash.levels`` by ``docs/_ext/fields_table.py``) name every
    ``Field``, so the generated Levels and Extras tables cannot silently
    drop one."""
    out = _build(tmp_path)
    assert out.returncode == 0, out.stderr
    html = (tmp_path / "html" / "usage.html").read_text(encoding="utf-8")
    missing = [f for f in Field if f'<span class="pre">{f.value}</span>' not in html]
    assert not missing, f"usage.html's fields tables are missing: {missing}"
