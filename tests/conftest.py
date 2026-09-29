"""Shared fixtures. Plain helpers (compiling, generating, the harness) live
in tests/harness.py, which tests import by name."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(scope="session")
def compilers() -> list[str]:
    """Those of ``gcc`` and ``clang`` on ``PATH``; skips the test if neither is."""
    found = [cc for cc in ("gcc", "clang") if shutil.which(cc)]
    if not found:
        pytest.skip("no C compiler")
    return found


@pytest.fixture(scope="session", autouse=True)
def _tmpdir_under_basetemp(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point ``TMPDIR`` into pytest's base temporary directory (the
    repository's tmp/pytest, set in pyproject), so the compilers and tools
    the tests run write nothing to /tmp either."""
    scratch = tmp_path_factory.mktemp("tmpdir")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TMPDIR", str(scratch))
        yield
