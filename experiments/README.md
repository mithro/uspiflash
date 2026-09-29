# Experiments

The convention every research effort in this repository follows (spec §7.4,
`docs/superpowers/specs/2026-09-28-uspiflash-design.md`). Recording an
experiment this way means anyone — Tim, a reviewer, a later milestone — can
reproduce it and see whether its conclusion still holds as the database, the
compilers or the codecs change.

## Layout

Each experiment is a directory `experiments/YYYY-MM-DD-<slug>/` containing:

- `README.md`: **question**, **hypothesis**, **method**, **result** and
  **conclusion**, plus what changed in the code because of it. The date is
  when the experiment was first run, in the directory name and the title;
  the README is edited in place as the experiment is rerun, not copied.
- `run.py`: reproduces the experiment with one command,
  `uv run uspiflash research run <slug>`, with pinned inputs. It exposes
  `collect() -> dict[str, object]` (the measurement, importable and testable
  on its own) and, run as `__main__`, writes `results/*.json` from it.
- `results/`: the raw JSON `collect()` produced — including, where they
  apply, toolchain identity, host, the `spiflash` version and any random
  seeds — so a rerun's numbers can be diffed against the recorded ones.

## Running

```
uv run uspiflash research list                        # every experiment, oldest first
uv run uspiflash research run <slug>                   # reproduce one
```

Both work from anywhere inside a checkout: `uspiflash research` walks up
from the current directory to the nearest `experiments/`, the way `git`
finds the repository root.

## Adding an experiment

1. Write `run.py`'s `collect()` first, and a test that calls it directly
   (see `tests/test_research.py`'s statistics test) — it should not depend
   on the working directory, only the `__main__` block writes files.
2. `uv run uspiflash research run <slug>` to produce `results/`.
3. Fill in the README's **result** and **conclusion** from the real numbers
   in `results/*.json` — never commit a placeholder.
4. Ruff's INP001 (implicit namespace package) fires on a bare script
   directory with no `__init__.py`; add the directory to
   `namespace-packages` under `[tool.ruff]` in `pyproject.toml` (this is
   configuration, not a suppression — a `run.py` is a script location, never
   imported by name, so it is never a real package). Every experiment does
   this once, when it is added.
5. mypy checks each experiment's `run.py` on its own
   (`tests/test_research.py`), since every script has the same name; nothing
   to add.
6. The docs build picks the experiment up automatically: `docs/conf.py`
   generates `docs/_generated/experiments/<slug>.md` for every experiment at
   build time (see `docs/experiments.md`).

## Index

| Date | Slug | Question |
|---|---|---|
| 2026-09-28 | [`database-statistics`](2026-09-28-database-statistics/README.md) | What does the spiflash data look like, byte for byte, and what does the baseline layout cost at each detail level? |
| 2026-09-29 | [`sfdp-vs-database`](2026-09-29-sfdp-vs-database/README.md) | Where a chip's own SFDP and the database both describe it, do they agree, and which says more? |

## Rerunning everything

`uspiflash research rerun --all` (a later milestone) reruns every experiment
and reports which conclusions no longer hold — because of new chips, new
compilers or new codecs.
