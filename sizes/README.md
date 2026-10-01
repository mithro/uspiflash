# Sizes

<!-- Generated from ledger.json by `uspiflash measure --write`: do not edit. -->

What the generated library costs in flash, in bytes, for each configuration
and target. Each configuration's header is generated with the default prefix,
its implementation compiled on its own (`-c`, no unwind tables), and the
object's sections read by uspiflash's own ELF reader (`uspiflash.elf`).
Sections count by their ELF flags, not their names: **text** is every
allocated, executable section (code); **rodata** is every other allocated,
read-only one (tables and strings, plus anything else that lands in flash,
such as the `.ARM.exidx` entries clang emits for Arm even without unwind
tables); and **total** is text + rodata, everything the object puts in flash.
Every object has no allocated writable section (data and bss are 0; the
measurement refuses otherwise), so the library needs no RAM beyond its stack;
and no object has an undefined symbol (the object's undefined symbols are
none, or the measurement fails), so it calls no libc function and no compiler
helper. **linked** is the implementation linked on its own (every public
function kept, no C library): it adds alignment, pools and veneers, and
merges duplicate strings, so it can come out smaller. `ledger.json` lists
every allocated section of every object.

**stack** is the deepest path through the library's call graph, in
bytes: each function's frame as the compiler reports it
(`-fstack-usage`), added along the calls its relocations show,
from any public function. Your `putc` and `xfer` callbacks' own
frames come on top. `ledger.json` has every frame, the peak's path,
and every function's and table's size.

Measured against spiflash 0.0.post173 (database format 3).
These are compiled objects; the
[database-statistics experiment](https://github.com/mithro/uspiflash/blob/main/experiments/2026-09-28-database-statistics/README.md)
counts the raw table bytes before compiling.

## Configurations

SPI NOR is the primary target and `uspiflash generate`'s default: its
builds (`--type nor`, the `:nor` rows) come first, and the all-types
(`--type nor --type nand`) and NAND builds are listed for comparison.

| Configuration | `uspiflash generate` options |
|---|---|
| `id:nor` | `--level id --type nor` |
| `read:nor` | `--level read --type nor` |
| `write:nor` | `--level write --type nor` |
| `describe:nor` | `--level describe --type nor` |
| `full:nor` | `--level full --type nor` |
| `id+sfdp:nor` | `--level id --with sfdp --type nor` |
| `read+sfdp:nor` | `--level read --with sfdp --type nor` |
| `full-sfdp_summary:nor` | `--level full --without sfdp_summary --type nor` |
| `full+sfdp_dumps:nor` | `--level full --with sfdp_dumps --type nor` |
| `id` | `--level id --type nor --type nand` |
| `read` | `--level read --type nor --type nand` |
| `write` | `--level write --type nor --type nand` |
| `describe` | `--level describe --type nor --type nand` |
| `full` | `--level full --type nor --type nand` |
| `full+datasheet` | `--level full --with datasheet --type nor --type nand` |
| `full+datasheets` | `--level full --with datasheets --type nor --type nand` |
| `full+records+provenance+jep106` | `--level full --with jep106 --with provenance --with records --type nor --type nand` |
| `full+sfdp+sfdp_dumps` | `--level full --with sfdp --with sfdp_dumps --type nor --type nand` |
| `read:nand` | `--level read --type nand` |
| `full:nand` | `--level full --type nand` |

## cortex-m0

Debian clang version 19.1.7 (3+b1): `clang --target=thumbv6m-none-eabi -mcpu=cortex-m0 -mthumb -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -fstack-usage -c`

| Configuration | text | rodata | total | linked | stack |
|---|--:|--:|--:|--:|--:|
| `id:nor` | 754 | 5,340 | **6,094** | 6,054 | 156 |
| `read:nor` | 1,272 | 14,605 | **15,877** | 15,799 | 160 |
| `write:nor` | 1,380 | 20,613 | **21,993** | 21,899 | 160 |
| `describe:nor` | 4,060 | 61,105 | **65,165** | 64,980 | 160 |
| `full:nor` | 8,156 | 76,804 | **84,960** | 84,670 | 160 |
| `id+sfdp:nor` | 1,430 | 5,374 | **6,804** | 6,750 | 156 |
| `read+sfdp:nor` | 1,948 | 14,639 | **16,587** | 16,495 | 160 |
| `full-sfdp_summary:nor` | 8,016 | 76,059 | **84,075** | 83,786 | 160 |
| `full+sfdp_dumps:nor` | 8,764 | 95,773 | **104,537** | 104,245 | 160 |
| `id` | 1,022 | 6,531 | **7,553** | 7,513 | 184 |
| `read` | 1,576 | 17,467 | **19,043** | 18,965 | 216 |
| `write` | 1,684 | 24,023 | **25,707** | 25,613 | 212 |
| `describe` | 4,372 | 71,850 | **76,222** | 76,036 | 212 |
| `full` | 8,716 | 88,416 | **97,132** | 96,842 | 212 |
| `full+datasheet` | 9,196 | 141,216 | **150,412** | 150,120 | 212 |
| `full+datasheets` | 9,820 | 206,298 | **216,118** | 215,827 | 212 |
| `full+records+provenance+jep106` | 9,728 | 348,951 | **358,679** | 358,380 | 212 |
| `full+sfdp+sfdp_dumps` | 10,004 | 107,419 | **117,423** | 117,117 | 212 |
| `read:nand` | 1,182 | 2,984 | **4,166** | 4,086 | 136 |
| `full:nand` | 7,298 | 13,056 | **20,354** | 20,102 | 168 |

## rv32imc

Debian clang version 19.1.7 (3+b1): `clang --target=riscv32-unknown-elf -march=rv32imc -mabi=ilp32 -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -fstack-usage -c`

| Configuration | text | rodata | total | linked | stack |
|---|--:|--:|--:|--:|--:|
| `id:nor` | 910 | 5,284 | **6,194** | 6,152 | 80 |
| `read:nor` | 1,598 | 14,509 | **16,107** | 16,059 | 96 |
| `write:nor` | 1,744 | 20,501 | **22,245** | 22,197 | 96 |
| `describe:nor` | 5,374 | 60,897 | **66,271** | 66,148 | 224 |
| `full:nor` | 10,916 | 76,492 | **87,408** | 86,942 | 256 |
| `id+sfdp:nor` | 1,720 | 5,302 | **7,022** | 6,908 | 80 |
| `read+sfdp:nor` | 2,408 | 14,527 | **16,935** | 16,815 | 96 |
| `full-sfdp_summary:nor` | 10,716 | 75,747 | **86,463** | 85,998 | 256 |
| `full+sfdp_dumps:nor` | 11,608 | 95,497 | **107,105** | 106,621 | 256 |
| `id` | 1,164 | 6,475 | **7,639** | 7,591 | 112 |
| `read` | 1,864 | 17,371 | **19,235** | 19,181 | 144 |
| `write` | 2,010 | 23,911 | **25,921** | 25,867 | 144 |
| `describe` | 5,666 | 71,642 | **77,308** | 77,188 | 224 |
| `full` | 11,408 | 88,104 | **99,512** | 99,042 | 256 |
| `full+datasheet` | 11,976 | 140,904 | **152,880** | 152,388 | 272 |
| `full+datasheets` | 12,754 | 205,986 | **218,740** | 218,207 | 256 |
| `full+records+provenance+jep106` | 12,592 | 348,631 | **361,223** | 360,702 | 256 |
| `full+sfdp+sfdp_dumps` | 12,920 | 107,127 | **120,047** | 119,499 | 256 |
| `read:nand` | 1,442 | 2,888 | **4,330** | 4,306 | 64 |
| `full:nand` | 9,442 | 12,784 | **22,226** | 21,868 | 240 |

## x86_64

gcc (Debian 14.2.0-19) 14.2.0: `gcc -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -fstack-usage -c`

| Configuration | text | rodata | total | linked | stack |
|---|--:|--:|--:|--:|--:|
| `id:nor` | 845 | 5,284 | **6,129** | 6,157 | 160 |
| `read:nor` | 1,297 | 14,509 | **15,806** | 15,921 | 168 |
| `write:nor` | 1,392 | 20,501 | **21,893** | 22,032 | 168 |
| `describe:nor` | 3,731 | 60,897 | **64,628** | 64,899 | 224 |
| `full:nor` | 7,307 | 76,492 | **83,799** | 84,107 | 304 |
| `id+sfdp:nor` | 1,623 | 5,302 | **6,925** | 6,967 | 160 |
| `read+sfdp:nor` | 2,075 | 14,527 | **16,602** | 16,731 | 168 |
| `full-sfdp_summary:nor` | 7,240 | 75,747 | **82,987** | 83,272 | 304 |
| `full+sfdp_dumps:nor` | 7,840 | 95,497 | **103,337** | 103,680 | 304 |
| `id` | 1,000 | 6,475 | **7,475** | 7,481 | 160 |
| `read` | 1,499 | 17,371 | **18,870** | 18,930 | 184 |
| `write` | 1,594 | 23,911 | **25,505** | 25,587 | 184 |
| `describe` | 3,933 | 71,642 | **75,575** | 75,793 | 224 |
| `full` | 7,643 | 88,104 | **95,747** | 96,035 | 304 |
| `full+datasheet` | 7,882 | 140,904 | **148,786** | 149,174 | 304 |
| `full+datasheets` | 8,343 | 205,986 | **214,329** | 214,691 | 304 |
| `full+records+provenance+jep106` | 8,298 | 348,631 | **356,929** | 357,302 | 320 |
| `full+sfdp+sfdp_dumps` | 8,951 | 107,127 | **116,078** | 116,383 | 304 |
| `read:nand` | 1,058 | 2,888 | **3,946** | 3,993 | 152 |
| `full:nand` | 6,156 | 12,784 | **18,940** | 19,140 | 304 |

## Regenerate

Tools:

- `clang`: Debian clang version 19.1.7 (3+b1)
- `gcc`: gcc (Debian 14.2.0-19) 14.2.0
- `ld`: GNU ld (GNU Binutils for Debian) 2.44
- `ld.lld`: Debian LLD 19.1.7 (compatible with GNU linkers)

These are the Debian packages `clang-19`, `lld-19`, `gcc`, `libc6-dev`
from snapshot.debian.org at `20260918T000000Z`, in `debian:trixie@sha256:d5ce19d4736f0ebbacd686d1040271a5aeb0cc920f5990c1bfae1717627f0674`, the
image CI's `sizes` job checks the ledger in. On a machine with the same
versions, regenerate with:

```sh
uv run python -m uspiflash.sandbox -- uv run uspiflash measure --write
```

`uv run uspiflash measure --check` exits 1 when this ledger is stale, and 2
when the installed tools differ from the ones above. The image changes only
deliberately: a new digest and a ledger regenerated in it, in one commit
(see [RELEASING.md](https://github.com/mithro/uspiflash/blob/main/RELEASING.md#the-size-ledgers-image)).
