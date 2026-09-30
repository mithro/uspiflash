# Developing

## Setup

```console
uv sync --group dev --group docs
```

The `dev` group brings in `pytest`, `ruff`, `mypy` and friends; `docs`
brings in Sphinx and its extensions, so both mypy (it checks
`docs/conf.py` too) and the documentation build work locally.

## Gates

The same four gates run in CI (`.github/workflows/deb.yml`, job `test`)
and must all be green before a commit lands:

```console
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```

`pytest` carries a coverage gate (`--cov-fail-under=85`); a change that
drops coverage below that fails the same way CI does.

## Heavy test runs

Anything heavier than the default suite (parallel workers, the full C
matrix once it exists, etc.) goes through the sandbox
(`uspiflash.sandbox`), which sizes memory and CPU limits from the
machine's current load rather than assuming a dedicated CI runner:

```console
uv run python -m uspiflash.sandbox -- uv run pytest -n {jobs}
```

Leave `{jobs}` literally; the sandbox replaces it with the CPU count the
current limits allow.

Nothing is written to `/tmp`: pytest keeps its temporary directories in the
git-ignored `tmp/pytest` (and points `TMPDIR` there for the compilers it
runs), `uspiflash measure` works in `tmp/`, and the sandbox sets `TMPDIR` to
`./tmp` for the command it runs.

## The size ledger

`sizes/ledger.json` records what the generated library costs, compiled for
each target, and `sizes/README.md` and the README's two headline figures
are generated from it. A change that alters the generated C changes those
numbers; regenerate them in the same commit, with the tool versions the
ledger names (Debian trixie's `clang-19` and `gcc`):

```console
uv run python -m uspiflash.sandbox -- uv run uspiflash measure --write
```

CI's `sizes` job runs `uspiflash measure --check` in a `debian:trixie`
container pinned by digest: it exits 1 with a diff when the committed files
are stale, and 2 when the tools' versions differ from the ledger's.
[RELEASING.md](https://github.com/mithro/uspiflash/blob/main/RELEASING.md#the-size-ledgers-image)
says how to move the pin.

## Workflow

- Feature work happens in a git worktree under `.worktrees/`, not in the
  main checkout, so several tasks can be worked on in isolation at once.
- Commits are small, one logical change each.
- Branches land on `main` through merge commits, never a rebase or a
  squash, so the branch's own commit history is kept.
