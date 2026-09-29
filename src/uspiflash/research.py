"""Experiments: ``experiments/YYYY-MM-DD-<slug>/`` directories, each with a
README (question, hypothesis, method, result, conclusion), a ``run.py`` that
reproduces it with one command, and ``results/`` holding what it measured.
See ``experiments/README.md``."""

from __future__ import annotations

import os
import runpy
from pathlib import Path


def find_root(start: Path, ceiling: Path | None = None) -> Path:
    """The nearest directory at or above ``start`` holding ``experiments/``,
    looking no higher than ``ceiling`` (default: the filesystem root). The
    tests' scratch directories are inside the repository (``tmp/``), so a
    test for "no repository here" sets the ceiling to its own directory."""
    here = start.resolve()
    top = ceiling.resolve() if ceiling is not None else None
    for d in (here, *here.parents):
        if (d / "experiments").is_dir():
            return d
        if d == top:
            break
    msg = f"no experiments/ directory at or above {start}"
    raise FileNotFoundError(msg)


def slugs(root: Path) -> list[str]:
    """Every experiment, oldest first."""
    return sorted(p.parent.name for p in (root / "experiments").glob("*/run.py"))


def run(slug: str, root: Path) -> int:
    """Run one experiment's ``run.py`` in its own directory."""
    here = root / "experiments" / slug
    script = here / "run.py"
    if not script.is_file():
        msg = f"no experiment {slug!r} (known: {', '.join(slugs(root))})"
        raise FileNotFoundError(msg)
    cwd = Path.cwd()
    os.chdir(here)
    try:
        runpy.run_path(str(script), run_name="__main__")
    finally:
        os.chdir(cwd)
    return 0
