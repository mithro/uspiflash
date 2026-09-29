"""Shared fixtures. Plain helpers (compiling, generating, the harness) live
in tests/harness.py, which tests import by name."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from uspiflash import research

if TYPE_CHECKING:
    from collections.abc import Iterator


def pytest_configure(config: pytest.Config) -> None:
    """Create ``--basetemp``'s parent (pyproject's ``tmp/pytest``): pytest
    makes the base temporary directory without parents, and ``tmp/`` is
    git-ignored, so a fresh checkout has none. A relative basetemp is
    resolved as pytest resolves it, against the invocation directory."""
    basetemp = config.option.basetemp
    if basetemp:
        path = Path(basetemp)
        if not path.is_absolute():
            path = config.invocation_params.dir / path
        path.parent.mkdir(parents=True, exist_ok=True)


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


@pytest.fixture(scope="session", autouse=True)
def _no_repository_above_basetemp(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """While the tests run, :func:`uspiflash.research.find_root` looks no
    higher than the base temporary directory for a start inside it. The
    basetemp is inside the repository (tmp/pytest), so without this a test
    working in its tmp_path could find the real checkout, and ``measure
    --write`` rewrite the committed ledger."""
    basetemp = tmp_path_factory.getbasetemp().resolve()
    find_root = research.find_root

    def guarded(start: Path, ceiling: Path | None = None) -> Path:
        if ceiling is None and start.resolve().is_relative_to(basetemp):
            ceiling = basetemp
        return find_root(start, ceiling)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(research, "find_root", guarded)
        yield
