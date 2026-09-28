# M1 part A: scaffold, CI, release pipeline (Tasks 1–3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Read [the M1 index](2026-09-28-m1-core.md) (global constraints) and the
spec first. Branch and worktree: `m1a` in `.worktrees/m1a`, from
`origin/main`.

The reference for everything in this part is spiflash's own setup at
`~/github/mithro/spiflash` (commit `0556ad6`): `pyproject.toml`,
`.github/workflows/{deb,publish-pypi,docs}.yml`, `.github/apt-packaging.toml`,
`debian/`, `packaging/`, `.readthedocs.yaml`, `RELEASING.md`. When in doubt,
copy what spiflash does and change only the names.

---

### Task 1: Python project skeleton, sandbox runner, spec amendments

**Files:**
- Create: `pyproject.toml`, `src/uspiflash/__init__.py`,
  `src/uspiflash/py.typed`, `src/uspiflash/cli.py`,
  `src/uspiflash/sandbox.py`, `tests/test_cli.py`, `tests/test_sandbox.py`,
  `uv.lock` (by `uv lock`)
- Modify: `.gitignore` (add `src/uspiflash/_version.py`, `docs/_build/`,
  `docs/_generated/`, `docs/_autosummary/`)
- Modify: `docs/superpowers/specs/2026-09-28-uspiflash-design.md` (append
  "Amendments (M1 plan)", the numbered decisions from the M1 index, verbatim)

**Interfaces:**
- Produces:
  - `uspiflash.__version__: str`
  - `uspiflash.cli.main(argv: Sequence[str] | None = None) -> int`
  - `uspiflash.sandbox.Limits(memory_bytes: int, cpus: int, tasks: int = 1024)`
  - `uspiflash.sandbox.compute_limits(meminfo: str, loadavg: str, pressure: str, ncpu: int) -> Limits`
  - `uspiflash.sandbox.current_limits() -> Limits`
  - `uspiflash.sandbox.wrap(argv: Sequence[str], limits: Limits, timeout: int) -> list[str]`
  - `python -m uspiflash.sandbox [--timeout S] [--print-limits] -- CMD...`,
    which replaces any `{jobs}` argument with `limits.cpus`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[project]
name = "uspiflash"
dynamic = ["version"]
description = "Generates tiny single-file C libraries that detect SPI flash chips and report their capabilities, from the spiflash database."
readme = "README.md"
requires-python = ">=3.11"
# PEP 621 table form: Debian bookworm's hatchling 1.12 rejects PEP 639's
# `license = "Apache-2.0"` + `license-files` (as in spiflash).
license = { text = "Apache-2.0" }
authors = [{ name = "Tim Ansell", email = "me@mith.ro" }]
keywords = ["spi", "flash", "spi-nor", "spi-nand", "jedec", "sfdp", "embedded", "zephyr",
            "micropython", "litex", "code-generator"]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: C",
    "License :: OSI Approved :: Apache Software License",
    "Topic :: System :: Hardware",
    "Topic :: Software Development :: Embedded Systems",
    "Topic :: Software Development :: Code Generators",
]
# The one runtime dependency: the database. Everything else is optional.
# 0.0.post38 added datasheets (Flash.datasheets, the `datasheet:` line and
# the JSON `datasheets` list), which the generator and its oracle rely on.
dependencies = ["spiflash>=0.0.post38"]

[project.urls]
Homepage = "https://github.com/mithro/uspiflash"
Documentation = "https://uspiflash.readthedocs.io/"
Issues = "https://github.com/mithro/uspiflash/issues"

[project.scripts]
uspiflash = "uspiflash.cli:main"

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.6", "mypy>=1.11", "pytest-cov>=5.0", "pytest-xdist>=3.6"]
docs = ["sphinx>=8", "furo>=2024.8", "myst-parser>=4", "sphinx-copybutton>=0.5",
        "types-docutils"]

# Rolling release, exactly as spiflash: X.Y at a vX.Y tag, X.Y.postN after.
[tool.hatch.version]
source = "vcs"

[tool.hatch.version.raw-options]
version_scheme = "post-release"
local_scheme = "no-local-version"

[tool.hatch.build.hooks.vcs]
version-file = "src/uspiflash/_version.py"

[tool.hatch.build.targets.wheel]
packages = ["src/uspiflash"]

[tool.hatch.build.targets.sdist]
include = ["src/", "tests/", "tools/", "examples/", "experiments/", "docs/", "README.md",
           "LICENSE"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --cov=uspiflash --cov-report=term-missing --cov-fail-under=85"

[tool.ruff]
target-version = "py311"
src = ["src", "tests", "tools", "docs", "experiments"]
line-length = 100
extend-exclude = ["src/uspiflash/_version.py"]

[tool.ruff.format]
exclude = ["*.md"]

[tool.ruff.lint]
# spiflash's rule set, unchanged (see its pyproject.toml for the reasons).
select = [
    "E", "W", "F", "I", "UP", "B", "SIM", "RUF", "PT", "TC", "C4", "PIE", "RET", "N", "A",
    "ARG", "ISC", "PERF", "FURB", "PGH", "PTH", "ERA", "EM", "FBT", "SLF", "PLC", "PLE", "PLW",
    "T10", "YTT", "RSE", "G", "LOG", "BLE", "DTZ", "ICN", "INP", "TID", "FLY",
]

[tool.mypy]
files = ["src/uspiflash", "tests", "tools", "docs/conf.py"]
mypy_path = ["src"]
strict = true

[[tool.mypy.overrides]]
module = "uspiflash._version"
ignore_errors = true
```

(`tools/` and `docs/conf.py` don't exist until later tasks. If mypy
complains about missing paths, list only the existing ones now and add each
path in the task that creates it.)

- [ ] **Step 2: Write the failing tests**

`tests/test_cli.py`:

```python
"""The uspiflash command's top level."""

from __future__ import annotations

import pytest
import spiflash

import uspiflash
from uspiflash.cli import main


def test_version_names_both_packages(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert out == f"uspiflash {uspiflash.__version__} (spiflash {spiflash.__version__})\n"


def test_no_subcommand_prints_help_and_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "usage: uspiflash" in capsys.readouterr().out
```

`tests/test_sandbox.py`:

```python
"""Resource limits sized from the machine's load."""

from __future__ import annotations

from uspiflash.sandbox import GIB, Limits, compute_limits, wrap

MEMINFO = "MemTotal:       32000000 kB\nMemAvailable:   20000000 kB\n"
CALM = "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
STALLING = "some avg10=25.00 avg60=5.00 avg300=1.00 total=9\n"


def test_memory_leaves_a_reserve_and_is_capped() -> None:
    lim = compute_limits(MEMINFO, "0.50 0.40 0.30 1/100 5", CALM, 12)
    reserve = max(4 * GIB, 32000000 * 1024 * 15 // 100)
    assert lim.memory_bytes == min(20000000 * 1024 - reserve, 16 * GIB)


def test_cpus_leave_room_for_load_and_the_desktop() -> None:
    assert compute_limits(MEMINFO, "3.20 1 1 1/1 1", CALM, 12).cpus == 12 - 4 - 2


def test_never_below_one_cpu_or_one_gib() -> None:
    lim = compute_limits("MemTotal: 4000000 kB\nMemAvailable: 100 kB\n", "99 1 1 1/1 1", CALM, 4)
    assert lim == Limits(GIB, 1)


def test_memory_pressure_halves_the_limits() -> None:
    calm = compute_limits(MEMINFO, "0 0 0 1/1 1", CALM, 12)
    busy = compute_limits(MEMINFO, "0 0 0 1/1 1", STALLING, 12)
    assert busy.memory_bytes == max(calm.memory_bytes // 2, GIB)
    assert busy.cpus == max(1, calm.cpus // 2)


def test_wrap_runs_in_a_limited_scope_with_a_timeout() -> None:
    argv = wrap(["make", "-j", "{jobs}"], Limits(2 * GIB, 3), 60)
    assert argv[:4] == ["systemd-run", "--user", "--scope", "--quiet"]
    assert f"-pMemoryMax={2 * GIB}" in argv
    assert "-pMemorySwapMax=0" in argv
    assert "-pCPUQuota=300%" in argv
    assert argv[-6:] == ["timeout", "--kill-after=30", "60", "make", "-j", "3"]
```

- [ ] **Step 3: Run them and see them fail**

Run: `uv sync --group dev && uv run pytest tests -q -o addopts=`
Expected: collection errors, `ModuleNotFoundError: No module named 'uspiflash'`.

- [ ] **Step 4: Implement**

`src/uspiflash/__init__.py`:

```python
"""uspiflash: generate tiny single-file C libraries that detect SPI flash
chips and report their capabilities, from the spiflash database.

See https://uspiflash.readthedocs.io/ and the design in
docs/superpowers/specs/2026-09-28-uspiflash-design.md."""

from __future__ import annotations

from ._version import __version__

__all__ = ["__version__"]
```

`src/uspiflash/cli.py`:

```python
"""The ``uspiflash`` command. Subcommands are added by later modules:
``generate`` and ``check`` (the C file), and ``research`` (experiments)."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import spiflash

from . import __version__

if TYPE_CHECKING:
    from collections.abc import Sequence


def parser() -> argparse.ArgumentParser:
    """The command line; each subcommand registers itself here."""
    ap = argparse.ArgumentParser(
        prog="uspiflash",
        description="Generate a single-file C library that detects SPI flash chips.",
    )
    ap.add_argument(
        "--version",
        action="version",
        version=f"uspiflash {__version__} (spiflash {spiflash.__version__})",
    )
    ap.add_subparsers(dest="command")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; the return value is the exit status."""
    args = parser().parse_args(argv)
    if args.command is None:
        parser().print_help()
        return 2
    return 0
```

`src/uspiflash/sandbox.py`:

```python
"""Run a command in a resource-limited systemd scope, with limits sized from
the machine's *current* load, so test suites cannot exhaust memory or make
the desktop unresponsive.

Memory: what is available now, less a reserve for everything else (4 GiB or
15 % of RAM, whichever is larger), clamped to 1–16 GiB. CPUs: all of them,
less the current one-minute load and two for the desktop, at least one. When
the kernel reports memory pressure (PSI ``some avg10`` above 10 %), both are
halved. Swap is disallowed, so a runaway job is killed rather than thrashing.

Usage::

    uv run python -m uspiflash.sandbox -- uv run pytest -n {jobs}

``{jobs}`` becomes the CPU count the limits allow.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

GIB = 1 << 30


@dataclass(frozen=True)
class Limits:
    """How much of the machine one sandboxed command may use."""

    memory_bytes: int
    cpus: int
    tasks: int = 1024

    def properties(self) -> list[str]:
        """The systemd resource-control properties for these limits."""
        return [
            f"MemoryMax={self.memory_bytes}",
            "MemorySwapMax=0",
            f"CPUQuota={self.cpus * 100}%",
            f"TasksMax={self.tasks}",
        ]


def _meminfo(text: str) -> dict[str, int]:
    """``/proc/meminfo`` as bytes by field name."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        fields = rest.split()
        if fields:
            out[key.strip()] = int(fields[0]) * 1024
    return out


def _pressure(text: str) -> float:
    """PSI's ``some avg10`` percentage, 0 when unavailable."""
    for line in text.splitlines():
        if line.startswith("some"):
            for part in line.split():
                if part.startswith("avg10="):
                    return float(part.removeprefix("avg10="))
    return 0.0


def compute_limits(meminfo: str, loadavg: str, pressure: str, ncpu: int) -> Limits:
    """Limits from the text of ``/proc/meminfo``, ``/proc/loadavg`` and
    ``/proc/pressure/memory`` and the CPU count."""
    mem = _meminfo(meminfo)
    reserve = max(4 * GIB, mem["MemTotal"] * 15 // 100)
    memory = min(max(mem["MemAvailable"] - reserve, GIB), 16 * GIB)
    cpus = max(1, ncpu - math.ceil(float(loadavg.split()[0])) - 2)
    if _pressure(pressure) > 10.0:
        memory = max(memory // 2, GIB)
        cpus = max(1, cpus // 2)
    return Limits(memory, cpus)


def current_limits() -> Limits:
    """Limits for this machine, right now."""
    psi = Path("/proc/pressure/memory")
    return compute_limits(
        Path("/proc/meminfo").read_text(encoding="ascii"),
        Path("/proc/loadavg").read_text(encoding="ascii"),
        psi.read_text(encoding="ascii") if psi.exists() else "",
        os.cpu_count() or 1,
    )


def wrap(argv: Sequence[str], limits: Limits, timeout: int) -> list[str]:
    """``argv`` run in a transient systemd user scope with ``limits``, at low
    priority, killed after ``timeout`` seconds. ``{jobs}`` arguments become
    the CPU count."""
    inner = [str(limits.cpus) if a == "{jobs}" else a for a in argv]
    return [
        "systemd-run", "--user", "--scope", "--quiet", "--collect",
        *(f"-p{p}" for p in limits.properties()),
        "nice", "-n", "10",
        "timeout", "--kill-after=30", str(timeout),
        *inner,
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m uspiflash.sandbox [--timeout S] [--print-limits] -- CMD...``"""
    ap = argparse.ArgumentParser(prog="python -m uspiflash.sandbox")
    ap.add_argument("--timeout", type=int, default=3600, help="seconds (default 3600)")
    ap.add_argument("--print-limits", action="store_true")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    limits = current_limits()
    if args.print_limits:
        print(f"memory {limits.memory_bytes // (1 << 20)} MiB, cpus {limits.cpus}")
    cmd = [a for a in args.command if a != "--"]
    if not cmd:
        return 0
    if shutil.which("systemd-run") is None:
        msg = "systemd-run is not available: refusing to run unsandboxed"
        raise SystemExit(msg)
    return subprocess.run(wrap(cmd, limits, args.timeout), check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Lock, run the gates and see them pass**

Run:
```
uv lock
uv sync --group dev
uv run ruff check && uv run ruff format --check && uv run mypy
uv run pytest -q
```
Expected: all pass (coverage ≥ 85 %; add a test for
`main(["--print-limits"])` and for `main([])`, exit 2, if the coverage gate
fails).

Then smoke-test the sandbox itself: `uv run python -m uspiflash.sandbox
--print-limits -- true` prints the limits and exits 0.

- [ ] **Step 6: Amend the spec**

Append to the spec a section `## 13. Amendments (M1 plan, 2026-09-28)`
containing the numbered decisions from the M1 index, verbatim.

- [ ] **Step 7: Commit (three commits)**

1. `pyproject, package skeleton and --version` (pyproject.toml, uv.lock,
   `__init__.py`, py.typed, cli.py, test_cli.py, .gitignore)
2. `sandbox: resource limits sized from the machine's load` (sandbox.py,
   test_sandbox.py)
3. `spec: amendments from the M1 plan` (the spec)

---

### Task 2: CI test job and the documentation skeleton

**Files:**
- Create: `.github/workflows/deb.yml` (test job only, for now),
  `.github/workflows/docs.yml`, `.readthedocs.yaml`, `docs/conf.py`,
  `docs/index.md`, `docs/design.md`, `docs/developing.md`, `docs/api.md`,
  `docs/_static/.gitkeep`, `tests/test_docs.py`
- Modify: `pyproject.toml` (mypy `files` += `docs/conf.py`)

**Interfaces:**
- Produces: `uv run sphinx-build -W --keep-going -b html docs docs/_build/html`
  succeeds; later tasks add pages under `docs/`.

- [ ] **Step 1: Write `deb.yml` with the test job**

The workflow must be named `Debian packages` from the start:
`publish-pypi.yml` (Task 3) triggers on that name. Copy spiflash's
`deb.yml` header comment, `on:`, `permissions:`, `concurrency:` and `test:`
job verbatim, then change:
- `spiflash` → `uspiflash` in comments;
- the sync step to `uv sync --group dev --group docs --python ${{ matrix.python-version }}`;
- add, before the tests, a step that prints the C compilers the host C tests
  (Part C) use:

```yaml
      - name: C compilers
        run: gcc --version && clang --version
```

Leave out `build-deb` and `publish-apt` for now (Task 3).

- [ ] **Step 2: Write the docs skeleton**

`docs/conf.py`:

```python
"""Sphinx configuration for https://uspiflash.readthedocs.io/."""

from __future__ import annotations

import uspiflash

project = "uspiflash"
author = "Tim Ansell"
project_copyright = "2026, Tim Ansell"
release = uspiflash.__version__
version = release

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
exclude_patterns = ["_build", "superpowers", "Thumbs.db", ".DS_Store"]
myst_enable_extensions = ["colon_fence", "deflist", "attrs_inline"]
myst_heading_anchors = 3
autosummary_generate = True
autodoc_default_options = {"members": True, "undoc-members": True, "member-order": "bysource"}
autodoc_typehints = "description"
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
html_theme = "furo"
html_title = "uspiflash"
html_static_path = ["_static"]
html_theme_options = {
    "source_repository": "https://github.com/mithro/uspiflash/",
    "source_branch": "main",
    "source_directory": "docs/",
}
```

`docs/index.md`:

````markdown
# uspiflash

```{include} ../README.md
:start-line: 1
```

```{toctree}
:maxdepth: 2

design
developing
api
```
````

`docs/design.md`:

````markdown
# Design

```{include} superpowers/specs/2026-09-28-uspiflash-design.md
:start-line: 1
```
````

(`exclude_patterns` keeps `superpowers/` from being built as pages of its
own; `{include}` still reads the spec.)

`docs/developing.md` covers how to work on uspiflash:
- `uv sync --group dev --group docs`
- the gates (`uv run ruff check`, `uv run ruff format --check`,
  `uv run mypy`, `uv run pytest`)
- running heavy suites through the sandbox, with the exact command:
  `uv run python -m uspiflash.sandbox -- uv run pytest -n {jobs}`
- worktrees under `.worktrees/`, small commits, merge commits only

`docs/api.md`:

````markdown
# Python API

```{eval-rst}
.. autosummary::
   :toctree: _autosummary
   :recursive:

   uspiflash
```
````

`.readthedocs.yaml`: copy spiflash's, changing only the comment's URL.

`.github/workflows/docs.yml`: copy spiflash's `docs.yml`. Keep only the
checkout, uv, `uv sync --group docs` and `sphinx-build -W` steps and the
artifact upload. Drop the link-check and chip-page steps: uspiflash has no
such pages.

- [ ] **Step 3: Write the docs build test**

`tests/test_docs.py`:

```python
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
        [sys.executable, "-m", "sphinx", "-W", "--keep-going", "-q", "-b", "html",
         str(ROOT / "docs"), str(tmp_path / "html")],
        capture_output=True, text=True, check=False,
    )
    assert out.returncode == 0, out.stderr
```

- [ ] **Step 4: Run it**

Run: `uv sync --group dev --group docs && uv run pytest tests/test_docs.py -q -o addopts=`
Expected: PASS. If `{include}` of `../README.md` warns about relative links,
switch to `:relative-docs: docs/` and `:relative-images:` as MyST
documents.

- [ ] **Step 5: Commit (two commits)**

1. `ci: the test job (ruff, mypy, pytest) as "Debian packages"`
2. `docs: Sphinx skeleton, Read the Docs config and docs.yml`

---

### Task 3: Debian packaging, apt and PyPI publishing, release setup

**Files:**
- Create: `debian/control`, `debian/rules`, `debian/copyright`,
  `debian/source/format`, `packaging/install-test.sh`,
  `packaging/apt-intro.html`, `.github/apt-packaging.toml`,
  `.github/workflows/publish-pypi.yml`, `RELEASING.md`
- Modify: `.github/workflows/deb.yml` (add `build-deb` and `publish-apt`),
  `README.md` (install section)

**Interfaces:**
- Consumes: the `pypi` GitHub environment (exists) and the PyPI pending
  publisher (registered by Tim on 2026-09-28: project `uspiflash`, owner
  `mithro`, repo `uspiflash`, workflow `publish-pypi.yml`, environment
  `pypi`).
- Produces:
  - `python3-uspiflash` (`Architecture: all`), depending on
    `python3-spiflash` from `mithro/spiflash`'s apt repository
  - the apt repository at `https://mith.ro/uspiflash/<suite>/`

- [ ] **Step 1: Debian files**

`debian/control`:

```
Source: uspiflash
Section: python
Priority: optional
Maintainer: Tim 'mithro' Ansell <me@mith.ro>
Build-Depends: debhelper-compat (= 13),
               dh-python,
               pybuild-plugin-pyproject,
               python3-all,
               python3-hatchling,
               python3-hatch-vcs,
               python3-setuptools-scm,
               python3-spiflash (>= 0.0.post38~),
               python3-pytest <!nocheck>,
               gcc <!nocheck>,
Standards-Version: 4.7.0
Homepage: https://github.com/mithro/uspiflash
Vcs-Git: https://github.com/mithro/uspiflash.git
Vcs-Browser: https://github.com/mithro/uspiflash
Rules-Requires-Root: no

Package: python3-uspiflash
Architecture: all
Depends: python3 (>= 3.11),
         python3-spiflash (>= 0.0.post38~),
         ${python3:Depends},
         ${misc:Depends}
Provides: uspiflash
Description: generator of tiny C libraries that detect SPI flash chips
 uspiflash writes a single C header that, on an embedded device, identifies
 the SPI flash chip attached (JEDEC read-id, legacy ids, SFDP) and reports its
 size, geometry, voltages, capabilities and supported commands, from the
 spiflash database. The output needs no libc functions and no allocation, and
 is measured byte for byte across GCC, LLVM and SDCC.
 .
 This package provides the uspiflash Python module and the uspiflash command.
```

The trailing `~` in `(>= 0.0.post38~)` matters. spiflash's debs are
versioned `0.0.post38~deb13` (bookworm `~deb12`, and so on), and `~`
sorts before everything in dpkg. So `0.0.post38~deb13` is *lower* than
`0.0.post38` and would not satisfy `>= 0.0.post38`. The same applies to
`Build-Depends`: write `python3-spiflash (>= 0.0.post38~)` there too.

`debian/rules`: copy spiflash's. Set `PYBUILD_NAME = uspiflash`, keep the
`SETUPTOOLS_SCM_PRETEND_VERSION` line, and set:

```make
export PYBUILD_TEST_ARGS = cd {dir} && PYTHONPATH={build_dir} {interpreter} -m pytest -q -p no:cacheprovider -o addopts= tests --ignore=tests/test_docs.py
```

`debian/copyright`: DEP-5. `Files: *`, copyright 2026 Tim Ansell,
Apache-2.0, with a `Comment:` saying the generated C files carry data from
spiflash (Apache-2.0), itself extracted from the upstreams listed in
spiflash's `debian/copyright`.

`debian/source/format`: `3.0 (native)`.

`packaging/install-test.sh`:

```sh
#!/bin/sh
# Run by deb.yml's "Install test" in a clean debian:<suite> container after
# installing the built python3-uspiflash (and python3-spiflash from its repo).
set -eu
uspiflash --version
uspiflash --version | grep -q '(spiflash '
python3 -c 'import uspiflash, spiflash; print(uspiflash.__version__, spiflash.__version__)'
```

(Part C extends this to generate a header and compile it. The container
then needs `gcc`: add it to the `apt-get install` line in `deb.yml` at
that point, not now.)

`packaging/apt-intro.html`: one paragraph, as spiflash's: install
`python3-uspiflash`, which provides the `uspiflash` command.

`.github/apt-packaging.toml`:

```toml
# How this repository is packaged, and why it differs from the defaults.
# See https://github.com/mithro/apt-repo-action/blob/main/docs/packaging.md
kind = "B"
architectures = "all"       # until uspiflash-linux (M1 part E) adds per-arch packages
suites = ["bookworm", "trixie", "forky", "sid"]

[exceptions]
PKG-SUITES = "fpgas.online uses it: its Pis run bookworm, and uspiflash-linux runs there"

[[depends]]
repo = "mithro/spiflash"
reason = "python3-spiflash (the database) is not in Debian"
```

- [ ] **Step 2: Add `build-deb` and `publish-apt` to `deb.yml`**

Copy spiflash's two jobs verbatim, then:
- set `description: "uspiflash: tiny C libraries that detect SPI flash chips"`;
- add the dependency repository to the install test. The `Build` step's
  `apt-sources` output is already mounted and `install.sh` run; that is how
  `python3-spiflash` gets installed. Verify this in the first CI run's log.

- [ ] **Step 3: `publish-pypi.yml` and `RELEASING.md`**

`publish-pypi.yml`: copy spiflash's verbatim. The trigger name
`Debian packages`, environment `pypi` and `skip-existing` all stay.

`RELEASING.md`: spiflash's, with names and URLs changed and these facts:
- PyPI pending publisher registered 2026-09-28 (no action left).
- The apt key's fingerprint (from Step 4).
- Pages: build type `workflow`.
- Read the Docs: Tim imports `mithro/uspiflash` at
  <https://app.readthedocs.org/dashboard/import/>, project slug
  `uspiflash`, default branch `main`.
- "Include Git LFS objects in archives": UI only, Tim.

- [ ] **Step 4: Create the apt signing key and secret; enable Pages**

(Tim authorised this on 2026-09-28.)

```sh
gpg --batch --passphrase '' --quick-gen-key 'uspiflash apt repository <me@mith.ro>' rsa4096 sign never
gpg --list-keys --with-colons 'uspiflash apt repository' | grep '^fpr' | head -1
gpg --armor --export-secret-keys 'uspiflash apt repository' | gh secret set APT_GPG_PRIVATE_KEY --repo mithro/uspiflash
gh secret list --repo mithro/uspiflash
gh api repos/mithro/uspiflash/pages -X POST -f build_type=workflow
gh api repos/mithro/uspiflash/pages --jq '.html_url,.build_type'
```

Expected:
- `gh secret list` shows `APT_GPG_PRIVATE_KEY`.
- Pages reports `build_type: workflow` and an `html_url` under `mith.ro`,
  because `mithro.github.io` carries the `mith.ro` domain. If it doesn't,
  record the actual URL in `RELEASING.md` and the README.

Write the fingerprint, grouped in fours like spiflash's, into `RELEASING.md`
and the README's install section.

- [ ] **Step 5: README install section**

Add the `pip install uspiflash` / `uv tool install uspiflash` lines, the apt
instructions (copy spiflash's block with `uspiflash` names and the new
fingerprint), and a line saying the apt repo also needs spiflash's repo for
`python3-spiflash`, with the three commands for that.

- [ ] **Step 6: Commit (three commits), open PR M1a, review, merge**

1. `debian: python3-uspiflash, built and install-tested per suite`
2. `ci: publish the apt repository and PyPI from green main`
3. `RELEASING, README: how releases happen and how to install`

```sh
git push -u origin m1a
gh pr create --title "M1a: scaffold, CI and release pipeline" --body "<summary + test evidence>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE"
gh pr checks --watch
```

Expected: `test` (4 Pythons), `build-deb` (4 suites) and `sphinx` all green
on the PR. Then run the whole-part code review, fix findings, and merge:
`gh pr merge --merge`.

After the merge, watch `main`:
- `publish-apt` publishes;
- "Publish to PyPI" uploads `uspiflash 0.0.postN`;
- `curl -fsS https://mith.ro/uspiflash/uspiflash.gpg | gpg --show-keys`
  shows the fingerprint.

Report any failure with its log. Tell Tim the Read the Docs import is now
possible.
