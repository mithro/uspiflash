"""The documentation builds with warnings as errors."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from uspiflash.levels import Field

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(
    shutil.which("sphinx-build") is None, reason="docs group not installed"
)


@dataclass(frozen=True)
class Build:
    """One Sphinx HTML build: its result, and where its HTML went."""

    result: subprocess.CompletedProcess[str]
    html: Path


@pytest.fixture(scope="module")
def build(tmp_path_factory: pytest.TempPathFactory) -> Build:
    """The docs, built once for every test here."""
    html = tmp_path_factory.mktemp("docs") / "html"
    sphinx = [sys.executable, "-m", "sphinx", "-W", "--keep-going", "-q", "-b", "html"]
    result = subprocess.run(
        [*sphinx, str(ROOT / "docs"), str(html)],
        capture_output=True,
        text=True,
        check=False,
    )
    return Build(result, html)


def test_docs_build_without_warnings(build: Build) -> None:
    assert build.result.returncode == 0, build.result.stderr


def test_fields_table_lists_every_field(build: Build) -> None:
    """The ``{fields}`` directive's tables (docs/usage.md, built from
    ``uspiflash.levels`` by ``docs/_ext/fields_table.py``) name every
    ``Field``, so the generated Levels and Extras tables cannot silently
    drop one."""
    assert build.result.returncode == 0, build.result.stderr
    html = (build.html / "usage.html").read_text(encoding="utf-8")
    missing = [f for f in Field if f'<span class="pre">{f.value}</span>' not in html]
    assert not missing, f"usage.html's fields tables are missing: {missing}"
