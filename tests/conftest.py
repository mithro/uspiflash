"""Shared fixtures. Plain helpers (compiling, generating, the harness) live
in tests/harness.py, which tests import by name."""

from __future__ import annotations

import shutil

import pytest


@pytest.fixture(scope="session")
def compilers() -> list[str]:
    """Those of ``gcc`` and ``clang`` on ``PATH``; skips the test if neither is."""
    found = [cc for cc in ("gcc", "clang") if shutil.which(cc)]
    if not found:
        pytest.skip("no C compiler")
    return found
