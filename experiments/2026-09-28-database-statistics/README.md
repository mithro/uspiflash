# Database statistics (2026-09-28)

**Question.** What does the spiflash data look like, byte for byte, and
what does the baseline layout cost at each detail level?

**Why.** The encoding research (M4) needs to know where the bytes are; the
spec's claim that per-chip data is highly shareable needs a number.

**Hypothesis.** Part names and record names dominate: the strings, not the
per-chip attributes, are where the bytes are (the M1 plan's expectation,
from spec §3's 1,202 part names in 11,238 bytes and about 19 KB of record
names).

**Method.** `uv run uspiflash research run 2026-09-28-database-statistics`
counts the database through `uspiflash.model.Snapshot` and builds the
baseline `uspiflash.layout` at every level, recording each table's size.
See `run.py`'s `collect()`. `results/stats.json` also records the
`spiflash` version, each upstream's commit, and the Python version,
implementation, OS and machine it ran on. Two runs on the same inputs give
byte-identical results.

**Result.** From `results/stats.json`, against `spiflash` **0.0.post74**.
Spec §3 recorded its table from spiflash at commit `0556ad6` (2026-09-27)
with a throwaway script. **Every §3 number reproduced exactly** from the
live package at spiflash 0.0.post39 (this experiment's first run, commit
`bf516da`). spiflash 0.0.post74 added two sources, QEMU and Zephyr, and
spells out flashrom's suffix-group part names (`S25FL032(A/P)` is
`S25FL032A` and `S25FL032P`), which moves the counts:

| Quantity | §3 (0.0.post39) | 0.0.post74 | `stats.json` key(s) |
|---|---|---|---|
| Chip ids (`Flash` objects) | 778 (651 NOR, 127 NAND) | 787 (660 NOR, 127 NAND) | `chip_ids`, `types` |
| Id families | JEDEC 751, RES2 12, REMS 6, RES1 4, AT25F 4, ST95 1 | JEDEC 760, others unchanged | `families` |
| Id lengths (bytes, after continuation codes) | 3: 660, 2: 110, 1: 5, 5: 3 | 3: 669, others unchanged | `id_lengths` |
| JEP106 banks used | 0: 727, 1: 26, 6: 24, 7: 1 | 0: 736, others unchanged | `banks` |
| Manufacturers | 37 (224 bytes of names) | 38 (233 bytes) | `manufacturers`, `manufacturer_name_bytes` |
| Part names, counted per id | 1,202 (11,238 bytes; 3,584 bytes zlib -9), up to 19 per id | 1,252 (11,755 bytes; 3,766 zlib -9), up to 19 | `names_per_id`, `name_bytes_per_id`, `name_bytes_per_id_zlib9`, `max_names_per_id` |
| Part-name alphabet | 40 characters: `)-.0-9A-Z_` | 39: `-.0-9A-Z_` (no suffix groups left) | `name_alphabet` |
| Distinct opcode sets / with source attribution | 215 / 314 (of 58 operations used) | 229 / 337 (of 60) | `opcode_sets`, `opcode_sets_with_sources`, `operations_used` |
| Distinct feature sets | 126 | 141 | `feature_sets` |
| Distinct (size, page, sector, voltage) tuples | 163 | 169 | `geometry_tuples` |
| Ids whose sources conflict | 60 | 66 | `conflicting_ids` |
| Ids with extended-id variants | 21 (67 records) | 27 (92 records) | `ext_ids`, `ext_records` |

§3's part-name figures count names per chip id (`sum(len(f.names))`: a
name two ids share counts twice) and compress them NUL-separated in
database order. Deduplicated, as the layout's string pool stores them,
there are **1,209** distinct part names in **11,363** bytes (3,454 bytes
zlib -9, sorted and newline-separated): `names`, `name_bytes`,
`name_bytes_zlib9`.

The extra facts the M1 index calls out, over every upstream `Record`:

| Quantity | Bytes, per record | Distinct strings (bytes) |
|---|---|---|
| Record names (`Record.name`, before parsing into part numbers) | 21,673 | 1,206 (12,711) |
| Opcode "via" strings (why a source claims an operation) | 437,685 | not stored at any level |
| Upstream notes (`Record.notes`) | 174,480 | not stored at any level |
| Record locations (`Record.url`: `file:line`, despite the name) | 57,759 | 2,182 (57,759) |
| JEP106 manufacturer names (`Database.manufacturers`, one row per bank/id) | 47,526 | 2,283 (46,970) |

Baseline layout size (`uspiflash.layout.build`, sum of `Layout.tables`),
and its biggest tables (`layout_tables` has every table at every level):

| Level | Bytes | Largest tables |
|---|---|---|
| `id` | 3,888 | `ids` 3,035, `entries` 853 |
| `read` | 11,237 | `entries` 5,971, `ids` 3,035, `opsets` 959 |
| `write` | 16,294 | `entries` 7,677, `opsets` 4,032, `ids` 3,035 |
| `describe` | 39,392 | `str` 15,354, `entries` 11,089, `opsets` 4,032, `namelists` 3,912, `ids` 3,035 |
| `full` | 50,229 | `str` 15,492, `entries` 13,648, `opsets` 11,522, `namelists` 3,912, `ids` 3,035 |
| `full` + `records` + `provenance` + `jep106` | 200,759 | `str` 126,600, `records` 24,440, `entries` 15,354, `jep106` 11,530, `opsets` 11,522 |
| `full` + `datasheet` | 97,595 | `str` 58,526, `entries` 15,354, `opsets` 11,522, `namelists` 3,912, `ids` 3,035, `dslists` 1,576, `dsrows` 1,050 |
| `full` + `datasheets` | 165,226 | `str` 115,343, `entries` 15,354, `opsets` 11,522, `dsrows` 9,114, `namelists` 5,456, `dslists` 2,580 |

**Conclusion.** The shape of the data has not moved since spec §3 was
written: every number in its table reproduced at spiflash 0.0.post39, and
0.0.post74's new sources grow the counts by a few percent without changing
where the bytes are.

The hypothesis holds for part names at the default levels, but not for
record names:

- At `describe` and `full` the string pool, `str`, is the largest table
  (15,354 and 15,492 bytes), and part names are most of it: the 1,209
  distinct names take 11,363 bytes plus 1,209 NULs (12,572 bytes); the rest
  is manufacturer names, operation names and descriptions and the printers'
  name arrays. With `namelists` (3,912 bytes of offsets pointing at them),
  part names cost about 16,500 of `describe`'s 39,392 bytes, the largest
  single cost. It is not the whole story, though: `entries`, the fixed-width
  per-entry rows of indices and offsets, is nearly as big (11,089 at
  `describe`, 13,648 at `full`), and at `full` the per-operation source
  masks make `opsets` 11,522 bytes. The per-chip attribute values are
  shareable (the value tables total a few hundred bytes at every level), but
  the baseline's one-byte-per-field rows and per-chip operation lists are
  where M4 should look next after the strings.
- With `records` + `provenance` + `jep106` the file quadruples (200,759
  bytes), and `str` grows to 126,600 bytes. Record names are deduplicated
  in the pool (1,206 distinct, 12,711 bytes), so they are not what grows
  it: every record's location is distinct (2,182 locations, 57,759 bytes)
  and so is nearly every JEP106 name (2,283 distinct, 46,970 bytes). Those
  two, not record names, dominate the extras; the tables that point at
  them (`records` 24,440, `jep106` 11,530) add about a third as much
  again. They are opt-in extras for that reason.
- Datasheets (spiflash 0.0.post38 and later) cost more than `full`
  itself. The `datasheet` extra nearly doubles the file (+47,366 bytes, to
  97,595): the URLs of the 525 distinct best datasheets are 43,034 bytes of
  `str`, and `dsrows`, `dslists` and the 2-byte `E_DS` per entry add 4,332.
  The `datasheets` extra more than triples it (+114,997, to 165,226):
  every one of the 651 datasheets' URL, title and revision (99,851 bytes
  of `str`), 14-byte `dsrows` rows (9,114), `dslists` (2,580) and `E_DS`
  (1,706); and because the pool passes 64 KiB, every offset in the file
  widens to 3 bytes, which alone costs 1,746 bytes in `namelists`, `ops`,
  `mfrs` and the name arrays. They are opt-in extras for that reason.
- The two facts the layout never stores at any level, `via` (437,685
  bytes) and upstream `notes` (174,480 bytes), are bigger than everything
  above combined. They exist only in spiflash's own JSON, and uspiflash has
  no field for them (`levels.Field` has none): this experiment measures them
  only to confirm that keeping them out is the right call.

No code changed because of this experiment (it establishes the convention
and the baseline measurement M4 will compare against).
