"""Experiments: ``experiments/YYYY-MM-DD-<slug>/`` directories, each with a
README (question, hypothesis, method, result, conclusion), a ``run.py`` that
reproduces it with one command, and ``results/`` holding what it measured.
See ``experiments/README.md``."""

from __future__ import annotations

import os
import runpy
from pathlib import Path


def find_root(start: Path) -> Path:
    """The nearest directory at or above ``start`` holding ``experiments/``."""
    for d in (start.resolve(), *start.resolve().parents):
        if (d / "experiments").is_dir():
            return d
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
