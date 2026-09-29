# Database statistics (2026-09-28)

**Question.** What does the spiflash data look like, byte for byte, and
what does the baseline layout cost at each detail level?

**Why.** The encoding research (M4) needs to know where the bytes are; the
spec's claim that per-chip data is highly shareable needs a number.

**Method.** `uv run uspiflash research run 2026-09-28-database-statistics`
counts the database through `uspiflash.model.Snapshot` and builds the
baseline `uspiflash.layout` at every level. See `run.py`'s `collect()`.

**Result.** From `results/stats.json`, against `spiflash` **0.0.post39**
(spec §3's table was recorded at 0.0.post36 by a throwaway script; every
count below is from the live package, not that recorded table).

Counts (spec §3):

| Quantity | Value |
|---|---|
| Chip ids (`Flash` objects) | 778 (651 NOR, 127 NAND) |
| Id families | JEDEC 751, RES2 12, REMS 6, RES1 4, AT25F 4, ST95 1 |
| Id lengths (bytes, after continuation codes) | 3: 660, 2: 110, 1: 5, 5: 3 |
| JEP106 banks used | 0: 727, 1: 26, 6: 24, 7: 1 |
| Manufacturers | 37 |
| Part names (deduplicated across the database) | 1,165 (10,909 bytes; 3,339 bytes zlib -9) |
| Part-name alphabet | 40 characters: `)-.0-9A-Z_` |
| Distinct opcode sets / with source attribution | 215 / 314 |
| Distinct feature sets | 126 |
| Distinct (size, page, sector, voltage) tuples | 163 |
| Ids whose sources conflict | 60 |
| Ids with extended-id variants | 21 (67 records) |

The extra facts the M1 index calls out, over every upstream `Record` (not
deduplicated — these are raw upstream strings, one instance per record, and
none of them are stored by the baseline layout at any level):

| Quantity | Bytes |
|---|---|
| Record names (`Record.name`, before parsing into part numbers) | 19,519 |
| Opcode "via" strings (why a source claims an operation) | 400,398 |
| Upstream notes (`Record.notes`) | 164,813 |
| Record locations (`Record.url`: `file:line`, despite the name) | 49,702 |
| JEP106 manufacturer names (`Database.manufacturers`, one row per bank/id) | 47,526 |

Baseline layout size (`uspiflash.layout.build`, sum of `Layout.tables`),
bytes, by level:

| Level | Bytes |
|---|---|
| `id` | 3,823 |
| `read` | 10,681 |
| `write` | 15,393 |
| `describe` | 37,813 |
| `full` | 47,351 |
| `full` + `records` + `provenance` + `jep106` | 191,646 |

**Conclusion.** `chip_ids`, the id families, id lengths and JEP106 banks
match spec §3's table exactly (778 chip ids, the same family and length
breakdowns) — the shape of *which* chips exist has not moved between
0.0.post36 and 0.0.post39. What has moved slightly is the part-name count
(1,165 here vs. 1,202 in the spec's table) and its byte totals (10,909 vs.
11,238; 3,339 vs. 3,584 bytes zlib -9): three point releases of upstream
data changed a handful of part names, as expected — this experiment reports
the live package on every rerun, not a frozen snapshot, so future reruns
are expected to drift the same way.

The layout numbers answer "where are the bytes" directly:

- Going from `id` (3,823 bytes — just enough to probe the bus and identify
  a chip) to `full` (47,351 bytes — everything the text and JSON output
  need) is a 12× jump. Most of that growth lands between `write` and
  `describe` (15,393 → 37,813 bytes, +22,420): that step adds the
  deduplicated part-name pool (10,909 bytes) and operation descriptions
  alongside voltage and manufacturer data — confirming the spec's
  expectation that **part names are the largest single string cost in the
  baseline `full` build**.
- Turning on `records` + `provenance` + `jep106` more than quadruples that
  again, to 191,646 bytes (+144,295 over `full`). Those extras store, per
  record rather than per deduplicated part name: the raw record name
  (19,519 bytes, almost twice `full`'s deduplicated 10,909-byte name pool,
  because it is per-*record*, unparsed, and not deduplicated across
  upstreams the way part names are), each record's `file:line` location
  (49,702 bytes) and the full JEP106 table (47,526 bytes, one row per
  bank/id pair rather than the ~37 names `describe`'s `manufacturer` field
  already carries). **Record-level provenance, not part names, is where M4
  should look first if `records`/`provenance`/`jep106` are ever selected
  together** — they are optional extras precisely because this experiment
  shows they roughly quadruple the file.
- The two facts the layout never stores at any level — `via` (400,398
  bytes) and upstream `notes` (164,813 bytes) — are bigger than everything
  else in this table combined. They exist only in spiflash's own JSON, and
  uspiflash deliberately has no field for them (levels.py's `Field` enum has
  none): this experiment measures them only to confirm that decision is
  cheap to keep. If a future milestone ever needs to expose *why* an
  upstream claims an operation, this is the number it would have to budget
  for.

No code changed because of this experiment (it establishes the convention
and the baseline measurement M4 will compare against).
