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

**Result.** From `results/stats.json`, against `spiflash` **0.0.post39**.
Spec §3 recorded its table from spiflash at commit `0556ad6` (2026-09-27)
with a throwaway script. **Every §3 number reproduces exactly** from the
live package:

| Quantity | Value | `stats.json` key(s) |
|---|---|---|
| Chip ids (`Flash` objects) | 778 (651 NOR, 127 NAND) | `chip_ids`, `types` |
| Id families | JEDEC 751, RES2 12, REMS 6, RES1 4, AT25F 4, ST95 1 | `families` |
| Id lengths (bytes, after continuation codes) | 3: 660, 2: 110, 1: 5, 5: 3 | `id_lengths` |
| JEP106 banks used | 0: 727, 1: 26, 6: 24, 7: 1 | `banks` |
| Manufacturers | 37 (224 bytes of names) | `manufacturers`, `manufacturer_name_bytes` |
| Part names, counted per id | 1,202 (11,238 bytes; 3,584 bytes zlib -9), up to 19 per id | `names_per_id`, `name_bytes_per_id`, `name_bytes_per_id_zlib9`, `max_names_per_id` |
| Part-name alphabet | 40 characters: `)-.0-9A-Z_` | `name_alphabet` |
| Distinct opcode sets / with source attribution | 215 / 314 (of 58 operations used) | `opcode_sets`, `opcode_sets_with_sources`, `operations_used` |
| Distinct feature sets | 126 | `feature_sets` |
| Distinct (size, page, sector, voltage) tuples | 163 | `geometry_tuples` |
| Ids whose sources conflict | 60 | `conflicting_ids` |
| Ids with extended-id variants | 21 (67 records) | `ext_ids`, `ext_records` |

§3's part-name figures count names per chip id (`sum(len(f.names))`: a
name two ids share counts twice) and compress them NUL-separated in
database order. Deduplicated, as the layout's string pool stores them,
there are **1,165** distinct part names in **10,909** bytes (3,339 bytes
zlib -9, sorted and newline-separated): `names`, `name_bytes`,
`name_bytes_zlib9`.

The extra facts the M1 index calls out, over every upstream `Record`:

| Quantity | Bytes, per record | Distinct strings (bytes) |
|---|---|---|
| Record names (`Record.name`, before parsing into part numbers) | 19,519 | 1,324 (13,626) |
| Opcode "via" strings (why a source claims an operation) | 400,398 | not stored at any level |
| Upstream notes (`Record.notes`) | 164,813 | not stored at any level |
| Record locations (`Record.url`: `file:line`, despite the name) | 49,702 | 1,946 (49,702) |
| JEP106 manufacturer names (`Database.manufacturers`, one row per bank/id) | 47,526 | 2,283 (46,970) |

Baseline layout size (`uspiflash.layout.build`, sum of `Layout.tables`),
and its biggest tables (`layout_tables` has every table at every level):

| Level | Bytes | Largest tables |
|---|---|---|
| `id` | 3,823 | `ids` 2,999, `entries` 824 |
| `read` | 10,681 | `entries` 5,768, `ids` 2,999, `opsets` 841 |
| `write` | 15,393 | `entries` 7,416, `opsets` 3,635, `ids` 2,999 |
| `describe` | 37,540 | `str` 14,766, `entries` 10,712, `namelists` 3,675, `opsets` 3,635, `ids` 2,999 |
| `full` | 47,236 | `str` 14,892, `entries` 13,184, `opsets` 10,143, `namelists` 3,675, `ids` 2,999 |
| `full` + `records` + `provenance` + `jep106` | 191,517 | `str` 123,505, `records` 20,858, `entries` 14,832, `jep106` 11,530, `opsets` 10,143 |
| `full` + `datasheet` | 94,544 | `str` 57,926, `entries` 14,832, `opsets` 10,143, `namelists` 3,675, `ids` 2,999, `dslists` 1,576, `dsrows` 1,050 |
| `full` + `datasheets` | 162,061 | `str` 114,743, `entries` 14,832, `opsets` 10,143, `dsrows` 9,114, `namelists` 5,112, `dslists` 2,580 |

**Conclusion.** The shape of the data has not moved since spec §3 was
written: every number in its table reproduces.

The hypothesis holds for part names at the default levels, but not for
record names:

- At `describe` and `full` the string pool, `str`, is the largest table
  (14,766 and 14,892 bytes), and part names are most of it: the 1,165
  distinct names take 10,909 bytes plus 1,165 NULs (12,074 bytes); the rest
  is manufacturer names, operation names and descriptions and the printers'
  name arrays. With `namelists` (3,675 bytes of offsets pointing at them),
  part names cost about 15,700 of `describe`'s 37,540 bytes, the largest
  single cost. It is not the whole story, though: `entries`, the fixed-width
  per-entry rows of indices and offsets, is nearly as big (10,712 at
  `describe`, 13,184 at `full`), and at `full` the per-operation source
  masks make `opsets` 10,143 bytes. The per-chip attribute values are
  shareable (the value tables total a few hundred bytes at every level), but
  the baseline's one-byte-per-field rows and per-chip operation lists are
  where M4 should look next after the strings.
- With `records` + `provenance` + `jep106` the file quadruples (191,517
  bytes), and `str` grows to 123,505 bytes. Record names are deduplicated
  in the pool (1,324 distinct, 13,626 bytes), so they are not what grows
  it: every record's location is distinct (1,946 locations, 49,702 bytes)
  and so is nearly every JEP106 name (2,283 distinct, 46,970 bytes). Those
  two, not record names, dominate the extras; the tables that point at
  them (`records` 20,858, `jep106` 11,530) add about a quarter as much
  again. They are opt-in extras for that reason.
- Datasheets (spiflash 0.0.post38 and later) cost more than `full`
  itself. The `datasheet` extra doubles the file (+47,308 bytes, to
  94,544): the URLs of the 525 distinct best datasheets are 43,034 bytes of
  `str`, and `dsrows`, `dslists` and the 2-byte `E_DS` per entry add 4,274.
  The `datasheets` extra more than triples it (+114,825, to 162,061):
  every one of the 651 datasheets' URL, title and revision (99,851 bytes
  of `str`), 14-byte `dsrows` rows (9,114), `dslists` (2,580) and `E_DS`
  (1,648); and because the pool passes 64 KiB, every offset in the file
  widens to 3 bytes, which alone costs 1,632 bytes in `namelists`, `ops`,
  `mfrs` and the name arrays. They are opt-in extras for that reason.
- The two facts the layout never stores at any level, `via` (400,398
  bytes) and upstream `notes` (164,813 bytes), are bigger than everything
  above combined. They exist only in spiflash's own JSON, and uspiflash has
  no field for them (`levels.Field` has none): this experiment measures them
  only to confirm that keeping them out is the right call.

No code changed because of this experiment (it establishes the convention
and the baseline measurement M4 will compare against).
