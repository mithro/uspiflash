# SFDP versus the database (2026-09-29)

**Question.** A chip's own SFDP tables and the database's consensus both
describe it. How often do they agree, and where they differ, which says
more? That decides what a driver should trust (spec §13, amendment 11).

**Why.** uspiflash can now read a chip's SFDP over the bus
(`usf_sfdp_read`, the `sfdp` extra) and also carries the database's answer
for every chip it knows. A driver that has both needs to know which to
prefer, and whether either catches the other's mistakes.

**Hypothesis.** The database, merged from several independent sources,
says at least as much as SFDP does, and agrees with it on geometry. Where
they differ, the database says more (things SFDP cannot express or an old
JESD216 revision leaves out), rather than contradicting the chip.

**Method.** `uv run uspiflash research run 2026-09-29-sfdp-vs-database`
takes every SFDP dump spiflash ships (`Flash.sfdp_dumps`, all from QEMU),
decodes it with `spiflash.sfdp`, and compares it field by field with the
`Flash` it belongs to. See `run.py`'s `collect()`:

- **size**: the BFPT's density against `Flash.size`;
- **page size**: the BFPT's page size, where the revision has one
  (JESD216A and later), against `Flash.page_size`;
- **sector size**: whether `Flash.sector_size` is one of the BFPT's erase
  sizes;
- **features**: only the 14 SFDP can express (`SFDP_FEATURES`), both ways;
  for each feature only the database claims, which sources claim it;
- **operations**: the operations SFDP names (reads and sized erases)
  against the database's reads and erases, leaving out chip and die erases,
  which a BFPT never lists; for each operation only the database has, which
  sources claim it.

Each row also keeps the dump's raw erase types (`sfdp_erases`, size and
opcode), the chip's records (`records`), the operations spiflash's decoder
could not name (`unnamed_operations`) and its warnings.
`results/comparison.json` records the `spiflash` version. Two runs give
byte-identical results.

**Result.** From `results/comparison.json`, against `spiflash`
**0.0.post92**.

- **12 dumps over 11 chip ids** (`c22019` has two: MX25L25635E and
  MX25L25635F). Revisions: JESD216 ×4, JESD216A ×1, JESD216B ×7.
- **Size agrees 12/12.**
- **Page size agrees 12/12:** the 8 dumps that give one (JESD216A and
  later) say 256 B, as the database does. The 4 JESD216 1.0 dumps
  (`20ba19`, both `c22019`, `ef4019`) give none.
- **Sector size agrees 12/12:** the database's sector size is always among
  SFDP's erase sizes.
- **Features agree 5/12.** SFDP never claims a feature the database lacks
  (`features_only_sfdp` is empty in all 12). The database claims more in
  7/12:

  | Chip id | Dump | Only the database claims | Claimed by |
  |---|---|---|---|
  | `20ba19` | N25Q256A13, N25Q256A | `4byte_opcodes` | flashrom, flashprog, linux, u-boot |
  | | | `erase_32k` | flashrom, flashprog |
  | `2c5b1b` | MT35XU01G | `erase_64k` | linux |
  | | | `octal_read` | u-boot |
  | `2c5b1c` | MT35XU02GBBA | `octal_read` | linux, u-boot |
  | `9d7019` | IS25WP256 | `quad_pp` | linux |
  | `c22019` | MX25L25635E | `4byte_opcodes` | flashrom, flashprog |
  | | | `qpi` | flashprog, qemu |
  | `c22019` | MX25L25635F | `4byte_opcodes` | flashrom, flashprog |
  | `ef4019` | W25Q256 | `4byte_opcodes` | flashrom, flashprog |

  `4byte_opcodes` is missing from SFDP exactly where the dump is JESD216
  1.0, which has no 4-byte address instruction table (4BAIT).
- **Operations agree 5/12.** SFDP names no operation the database lacks.
  The database has more in the same 7/12: the 4-byte forms on the four
  JESD216 1.0 dumps and on `9d7019` (`SE_4B`, `BE_4K_4B`,
  `READ_1_1_1_4B`, ...), `READ_1_1_8` and `READ_1_1_8_4B` on the MT35X
  parts (`2c5b1b`, `2c5b1c`), and `BE_32K` (`0x52`) with `BE_32K_4B` on
  `20ba19`. Of the operations SFDP describes, 13 across 8 dumps have no
  name in spiflash (0 to 5 per dump; 5 on `c2201b`), and 6 dumps carry a
  decoder warning.

**Two findings.** In two places the database claims an erase size the
chip's own SFDP does not list. These are findings only: nothing has been
reported upstream, and whether to report them is the maintainer's
decision.

- **`20ba19`, a 32 KiB erase.** QEMU's dump, for N25Q256A13 and N25Q256A,
  gives two erase types: 4 KiB (`0x20`) and 64 KiB (`0xd8`). The database
  claims `erase_32k` and `BE_32K` (`0x52`, with `BE_32K_4B`, `0x5c`). Only
  flashrom and flashprog claim them. Each has two records for this id,
  `MT25QL256` and `N25Q256..3E`, and only the `MT25QL256` records claim the
  32 KiB erase (`block_erasers (1024 x 32768)`); their `N25Q256..3E`
  records do not. Linux and U-Boot name the id `N25Q256A` and `MT25QL256A`,
  and claim no 32 KiB erase. The id is shared by an N25Q and an MT25Q part,
  and the dump is an N25Q's. So the claim may be right for the MT25QL256
  and wrong for the N25Q256A. This experiment cannot tell which part a chip
  with this id is, and does not decide it.
- **`2c5b1b`, a 64 KiB erase.** QEMU's MT35XU01G dump gives three erase
  types: 4 KiB (`0x20`), 32 KiB (`0x52`) and 128 KiB (`0xd8`). The
  database's sector size is 128 KiB, but it also claims `erase_64k`, from
  Linux alone. Linux's record, `MT35XU01GBBA`, gives a 64 KiB sector size
  and only the features `erase_64k` and `sfdp`; QEMU and U-Boot give
  128 KiB. The database's erase operations are the SFDP's opcodes: `SE`
  (`0xd8`, "usually 64 KiB", claimed by U-Boot and QEMU) is the 128 KiB
  erase on this part, as QEMU's own claim says ("SFDP BFPT erase type 2:
  131072 B"). No operation in the database erases 64 KiB on this chip.

**Conclusion.** The hypothesis holds. For every chip with a shipped dump,
the database says as much as SFDP or more, and never contradicts it on
size, page size or sector size. SFDP adds no feature and no named operation
the database lacks. What SFDP lacks is mostly what JESD216 1.0 cannot say
(4-byte opcodes), plus what these dumps leave undeclared although SFDP
could express it (octal reads, quad page program, QPI). SFDP's value here
is as a check: it is what exposes the two suspect erase claims above. A driver should prefer the database's answer,
and use `usf_sfdp_read` for chips the database does not know.

**What changed because of it.** Nothing in the generator: `sfdp` (the
on-chip reader) stays an opt-in extra, for chips the database lacks.

The caveat is the sample: 12 dumps, all from QEMU, all SPI NOR, under five
JEDEC manufacturer ids (`0x20`, `0x2c`, `0x9d`, `0xc2`, `0xef`), all
256 Mbit or larger but one 8 Mbit Winbond.
More dumps (read from real chips, or from datasheets) should come in as
spiflash data, and a rerun will show whether the conclusion still holds.
