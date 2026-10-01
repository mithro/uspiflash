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

**Result.** From `results/stats.json`, against `spiflash` **0.0.post182**.
Spec §3 recorded its table from spiflash at commit `0556ad6` (2026-09-27)
with a throwaway script. **Every §3 number reproduced exactly** from the
live package at spiflash 0.0.post39 (this experiment's first run, commit
`bf516da`). spiflash 0.0.post74 added two sources, QEMU and Zephyr, and
spells out flashrom's suffix-group part names (`S25FL032(A/P)` is
`S25FL032A` and `S25FL032P`), which moves the counts. The catch-ups to
0.0.post92 and 0.0.post108 moved none of them. 0.0.post173 and
0.0.post182 add four sources (Dediprog's and IMSProg's programmer
tables, and Rockchip's and MediaTek's drivers), infer the manufacturer
of a chip no source names one for, and fold a SPI NAND id into the
longer id of the same part; the database grows by over two thirds:

| Quantity | §3 (0.0.post39) | 0.0.post74 | 0.0.post182 | `stats.json` key(s) |
|---|---|---|---|---|
| Chip ids (`Flash` objects) | 778 (651 NOR, 127 NAND) | 787 (660 NOR, 127 NAND) | 1,347 (1,056 NOR, 291 NAND) | `chip_ids`, `types` |
| Id families | JEDEC 751, RES2 12, REMS 6, RES1 4, AT25F 4, ST95 1 | JEDEC 760, others unchanged | JEDEC 1,312, REMS 12, RES2 13, RES1 5, AT25F 4, ST95 1 | `families` |
| Id lengths (bytes, after continuation codes) | 3: 660, 2: 110, 1: 5, 5: 3 | 3: 669, others unchanged | 3: 1,075, 2: 263, 1: 6, 5: 3 | `id_lengths` |
| JEP106 banks used | 0: 727, 1: 26, 6: 24, 7: 1 | 0: 736, others unchanged | 0: 1,279, 1: 43, 6: 24, 7: 1 | `banks` |
| Manufacturers | 37 (224 bytes of names) | 38 (233 bytes) | 64 (428 bytes) | `manufacturers`, `manufacturer_name_bytes` |
| Part names, counted per id | 1,202 (11,238 bytes; 3,584 bytes zlib -9), up to 19 per id | 1,252 (11,755 bytes; 3,766 zlib -9), up to 19 | 2,877 (27,664 bytes; 8,555 zlib -9), up to 28 | `names_per_id`, `name_bytes_per_id`, `name_bytes_per_id_zlib9`, `max_names_per_id` |
| Part-name alphabet | 40 characters: `)-.0-9A-Z_` | 39: `-.0-9A-Z_` (no suffix groups left) | 39, unchanged | `name_alphabet` |
| Distinct opcode sets / with source attribution | 215 / 314 (of 58 operations used) | 229 / 337 (of 60) | 261 / 434 (of 61) | `opcode_sets`, `opcode_sets_with_sources`, `operations_used` |
| Distinct feature sets | 126 | 141 | 159 | `feature_sets` |
| Distinct (size, page, sector, voltage) tuples | 163 | 169 | 192 | `geometry_tuples` |
| Ids whose sources conflict | 60 | 66 | 92 | `conflicting_ids` |
| Ids with extended-id variants | 21 (67 records) | 27 (92 records) | 29 (96 records) | `ext_ids`, `ext_records` |

§3's part-name figures count names per chip id (`sum(len(f.names))`: a
name two ids share counts twice) and compress them NUL-separated in
database order. Deduplicated, as the layout's string pool stores them,
there are **2,774** distinct part names in **26,743** bytes (7,866 bytes
zlib -9, sorted and newline-separated): `names`, `name_bytes`,
`name_bytes_zlib9`.

The extra facts the M1 index calls out, over every upstream `Record`:

| Quantity | Bytes, per record | Distinct strings (bytes) |
|---|---|---|
| Record names (`Record.name`, before parsing into part numbers) | 50,057 | 3,026 (32,388) |
| Opcode "via" strings (why a source claims an operation) | 655,670 | not stored at any level |
| Upstream notes (`Record.notes`) | 290,110 | not stored at any level |
| Record locations (`Record.url`: `file:line`, despite the name) | 138,555 | 4,954 (138,555) |
| JEP106 manufacturer names (`Database.manufacturers`, one row per bank/id) | 47,526 | 2,283 (46,970) |

Baseline layout size (`uspiflash.layout.build`, sum of `Layout.tables`),
and its biggest tables (`layout_tables` has every table at every level):

| Level | Bytes | Largest tables |
|---|---|---|
| `id` | 6,562 | `ids` 5,148, `entries` 1,414 |
| `read` | 17,590 | `entries` 9,898, `ids` 5,148, `opsets` 1,197 |
| `write` | 24,172 | `entries` 12,726, `ids` 5,148, `opsets` 4,665 |
| `describe` | 72,506 | `str` 34,187, `entries` 18,382, `namelists` 7,854, `ids` 5,148, `opsets` 4,665 |
| `full` | 88,833 | `str` 34,360, `entries` 22,624, `opsets` 15,174, `namelists` 7,854, `ids` 5,148 |
| `full` + `records` + `provenance` + `jep106` | 353,895 | `str` 233,721, `records` 47,834, `entries` 25,452, `opsets` 15,174, `jep106` 11,530 |
| `full` + `datasheet` | 141,715 | `str` 77,736, `entries` 25,452, `opsets` 15,174, `namelists` 11,093, `ids` 5,148, `dslists` 1,585, `dsrows` 1,584 |
| `full` + `datasheets` | 206,757 | `str` 134,211, `entries` 25,452, `opsets` 15,174, `namelists` 11,093, `dsrows` 9,114, `ids` 5,148 |

**Conclusion.** The shape of the data has not moved since spec §3 was
written: every number in its table reproduced at spiflash 0.0.post39;
0.0.post74's new sources grew the counts by a few percent, and
0.0.post173's and 0.0.post182's by over two thirds, without changing where the bytes are.

The hypothesis holds for part names at the default levels, but not for
record names:

- At `describe` and `full` the string pool, `str`, is the largest table
  (34,187 and 34,360 bytes), and part names are most of it: the 2,774
  distinct names take 26,743 bytes plus 2,774 NULs (29,517 bytes); the rest
  is manufacturer names, operation names and descriptions, the 12 `sfdp:`
  lines' text (646 bytes; with `sfdprows` and `sfdplines` the SFDP summary
  costs 733), the 12 distinct `parts differ on` lines' text (971 bytes;
  1,023 with `difflines`) and the printers' name arrays. With `namelists`
  (7,854 bytes of offsets pointing at them), part names cost about 37,400
  of `describe`'s 72,506 bytes, the largest single cost. It is not the
  whole story, though: `entries`, the fixed-width per-entry rows of
  indices and offsets, is nearly as big (18,382 at `describe`, 22,624 at
  `full`), and at `full` the per-operation source masks make `opsets`
  15,174 bytes (each mask relative to its chip's sources, one byte, or two
  past eight sources: see the layout's "source mask"). The per-chip
  attribute values are shareable (the value tables total a few hundred
  bytes at every level), but the
  baseline's one-byte-per-field rows and per-chip operation lists are
  where M4 should look next after the strings.
- With `records` + `provenance` + `jep106` the file quadruples (353,895
  bytes), and `str` grows to 233,721 bytes. Record names are deduplicated
  in the pool (3,026 distinct, 32,388 bytes), so they are not what grows
  it: every record's location is distinct (4,954 locations, 138,555 bytes)
  and so is nearly every JEP106 name (2,283 distinct, 46,970 bytes). Those
  two, not record names, dominate the extras; the tables that point at
  them (`records` 47,834, `jep106` 11,530) add about a third as much
  again. They are opt-in extras for that reason.
- Datasheets (spiflash 0.0.post38 and later) cost more than half of `full`
  itself, and since 0.0.post173 either extra takes the pool past 64 KiB,
  so every offset in the file widens to 3 bytes, which alone costs 3,509
  bytes (3,239 of them in `namelists`, the rest in `ops`, `mfrs`,
  `sfdplines`, `difflines` and the name arrays). The `datasheet` extra
  adds 52,882 bytes (to 141,715): the URLs of the 528 distinct best
  datasheets are 43,376 bytes of `str`, and `dsrows`, `dslists` and the
  2-byte `E_DS` per entry add 5,997. The `datasheets` extra more than
  doubles it (+117,924, to 206,757): every one of the 651 datasheets' URL,
  title and revision (99,851 bytes of `str`), 14-byte `dsrows` rows
  (9,114), `dslists` (2,622) and `E_DS` (2,828). They are opt-in extras
  for that reason.
- The two facts the layout never stores at any level, `via` (655,670
  bytes) and upstream `notes` (290,110 bytes), are bigger than everything
  above combined. They exist only in spiflash's own JSON, and uspiflash has
  no field for them (`levels.Field` has none): this experiment measures them
  only to confirm that keeping them out is the right call.

No code changed because of this experiment (it establishes the convention
and the baseline measurement M4 will compare against).
