# Usage

The `uspiflash` command has four subcommands: `generate` (write a header),
`check` (is a committed header current?), `measure` (the size ledger) and
`research` (reproduce an experiment).

## `uspiflash generate`

Write a generated C file:

```console
uv run uspiflash generate -o uspiflash.h --level read
```

SPI NOR is the primary target, so without `--type` the file keeps only SPI
NOR chips (as if given `--type nor`). For every chip in the database, NAND
included, give both types:

```console
uv run uspiflash generate -o uspiflash.h --level read --type nor --type nand
```

The file's regeneration command and embedded configuration record the
types either way, so `uspiflash check` regenerates it identically.

Options:

| Option | Meaning |
|---|---|
| `-o`, `--output PATH` | the file to write, or `-` for standard output (default: `uspiflash.h`) |
| `--prefix NAME` | the C symbol prefix, so symbols are `name_*` / `NAME_*` (default: `usf`) |
| `--level LEVEL` | one of the levels below (default: `full`) |
| `--with FIELD` | add a field or extra beyond the level |
| `--without FIELD` | leave a field the level would include out |
| `--manufacturer NAME` | keep only this manufacturer's chips (repeatable) |
| `--id HEX` | keep only this chip id, after stripping `0x7f` continuation codes (repeatable) |
| `--type TYPE` | keep only chips of this type, `nor` or `nand` (repeatable; default: `nor`, SPI NOR only; `--type nor --type nand` keeps every type) |
| `--family FAMILY` | keep only chips of this id family, the command that reads the id: `jedec`, `rems`, `res1`, `res2`, `at25f` or `st95` (repeatable) |
| `--min-size BYTES` | keep only chips at least this big |
| `--max-size BYTES` | keep only chips at most this big |

### Levels

Each level is a fixed set of fields, from bus probing up to the full JSON
printer. This table (and the Extras one below) is generated straight from
`uspiflash.levels` (the `{fields}` Sphinx directive, `docs/_ext/fields_table.py`),
so it cannot drift from the code:

```{fields} levels
```

Without `--type`, `generate` keeps only SPI NOR chips (as if given
`--type nor`); `--type nor --type nand` keeps every chip, NAND included
(amendment 12). This holds at every level, from `id` up.

### Extras

Beyond a level, `--with FIELD` adds one of these:

```{fields} extras
```

`conflicts` and `sfdp_summary` (in the Levels table above) are only ever
printed, so selecting either without a printer (`text` or `json`) adds
nothing to the file. Two extras cost the most: on `cortex-m0` at `-Os`
(clang), `sfdp` adds about 710 bytes to `id` or `read`, and `sfdp_dumps`
about 19.5 KB to `full`, for SPI NOR (from `sizes/README.md`: `id:nor`
6,094 and `id+sfdp:nor` 6,804 bytes; `full:nor` 84,855 and
`full+sfdp_dumps:nor` 104,404). The exact costs of every configuration,
on every measured target, are in [Sizes](sizes.md).

### Chip filters and `--prefix`

`--manufacturer`, `--id`, `--type`, `--family`, `--min-size` and
`--max-size` are repeatable and combine as an AND of ORs: repeating one
widens it (any of the given manufacturers), giving several different ones
narrows it (this manufacturer *and* this type). An empty filter keeps
every chip, except that no `--type` means `--type nor`.

`--prefix` renames every `usf_`/`USF_` symbol; it must be a C identifier
and must not start with `_` (C reserves those). This is the only way to
put more than one generated file's symbols in the same program.

### Size lines

The generated file's provenance comment also states its measured size for
the reference targets, quoted from the committed size ledger, when the
ledger measured this exact selection with the spiflash version installed
now (for example `Size (full:nor in sizes/ledger.json, spiflash 1.2.3):
cortex-m0 84,855, rv32imc ..., x86_64 ... bytes of flash for code and
tables at -Os, and no static RAM.`). When the selection is not one the
ledger measures, it says so instead of claiming a size (`uspiflash
measure` only sizes the ledger's own selections, not arbitrary ones); when
it is in the ledger but was measured with a different spiflash than the
one installed now, it says that instead.

## `uspiflash check`

Every generated file's provenance comment embeds the exact configuration
that made it, as a JSON `uspiflash-config` line. `check` re-runs that
configuration with the installed uspiflash and spiflash and compares the
result with the file on disk, so a committed copy can be verified without
keeping the command that generated it around:

```console
uv run uspiflash check src/uspiflash.h
```

Exit status:
- **0** when every named file is byte-identical to what the installed
  tools generate from its embedded configuration ("up to date");
- **1** when at least one file is out of date. For each such file, `check`
  prints the uspiflash and spiflash versions that generated it, the
  installed ones, and the first 40 lines of a unified diff between the
  file and a fresh regeneration;
- **2** when a file cannot be read, has no `uspiflash-config` line (it was
  not generated by uspiflash, or the line was removed), its
  `Configuration (sha256 ...)` tag does not match the JSON below it (the
  file was hand-edited, or otherwise damaged, rather than merely stale),
  or its configuration cannot be regenerated (for example a level or
  field this version of uspiflash no longer knows, or a value of the
  wrong JSON type). This status wins over 1: a single `check` run of
  several files always reports every file, but exits 2 if any of them
  errored this way.

Like `generate`, `check` warns on standard error, once per run (not once
per file), when the installed spiflash is not the one its output is
verified byte-identical to (`uspiflash.VERIFIED_SPIFLASH`) — so a report
of "out of date" is not mistaken for real drift when it is really just an
unverified spiflash.

A CI job can pin the exact versions the file was committed with, so it
never reports drift when only *its* environment differs:

```console
uvx --from 'uspiflash==<version>' --with 'spiflash==<version>' \
    uspiflash check src/uspiflash.h
```

## `uspiflash measure`

Compile every measured configuration for every target and print its size,
or write or check the committed ledger (`sizes/ledger.json`,
`sizes/README.md` and the README's size figures):

```console
uv run python -m uspiflash.sandbox -- uv run uspiflash measure --write
uv run uspiflash measure --check
```

With neither `--write` nor `--check`, `measure` prints the tables to
standard output without touching the repository. `--write` rewrites the
committed ledger and its generated Markdown; heavy runs go through the
sandbox (`uspiflash.sandbox`), which sizes memory and CPU limits from the
machine's current load. `--check` exits 1 with a diff when the committed
ledger is stale, and 2 when the installed compilers differ from the ones
that produced it (regenerate it with the tools named in
`sizes/README.md`, or run `--check` there instead). See
[Sizes](sizes.md) for what is measured and how.

## `uspiflash research`

Reproduce one of the project's recorded experiments, or list them:

```console
uv run uspiflash research list
uv run uspiflash research run 2026-09-28-database-statistics
```

`list` prints every experiment's slug, oldest first; `run SLUG` runs the
one experiment at `experiments/SLUG/`. See [Experiments](experiments.md)
for what each one asked and found.
