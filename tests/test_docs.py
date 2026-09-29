"""The documentation builds with warnings as errors."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("sphinx-build") is None, reason="docs group not installed")
def test_docs_build_without_warnings(tmp_path: Path) -> None:
    out = subprocess.run(
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
    assert out.returncode == 0, out.stderr
