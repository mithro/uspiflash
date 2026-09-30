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

Measured against spiflash 0.0.post108 (database format 3).
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
| `id:nor` | 754 | 3,388 | **4,142** | 4,102 | 156 |
| `read:nor` | 1,272 | 10,003 | **11,275** | 11,197 | 160 |
| `write:nor` | 1,380 | 14,820 | **16,200** | 16,106 | 160 |
| `describe:nor` | 3,884 | 36,428 | **40,312** | 40,124 | 160 |
| `full:nor` | 7,366 | 47,181 | **54,547** | 54,276 | 160 |
| `id+sfdp:nor` | 1,382 | 3,422 | **4,804** | 4,750 | 156 |
| `read+sfdp:nor` | 1,900 | 10,037 | **11,937** | 11,845 | 160 |
| `full-sfdp_summary:nor` | 7,226 | 46,436 | **53,662** | 53,388 | 160 |
| `full+sfdp_dumps:nor` | 7,946 | 66,159 | **74,105** | 73,833 | 160 |
| `id` | 918 | 3,944 | **4,862** | 4,822 | 176 |
| `read` | 1,468 | 11,333 | **12,801** | 12,723 | 212 |
| `write` | 1,576 | 16,406 | **17,982** | 17,888 | 208 |
| `describe` | 4,080 | 40,565 | **44,645** | 44,460 | 208 |
| `full` | 7,562 | 51,699 | **59,261** | 58,988 | 208 |
| `full+datasheet` | 7,762 | 99,082 | **106,844** | 106,570 | 208 |
| `full+datasheets` | 8,586 | 166,776 | **175,362** | 175,088 | 208 |
| `full+records+provenance+jep106` | 8,538 | 202,279 | **210,817** | 210,538 | 208 |
| `full+sfdp+sfdp_dumps` | 8,770 | 70,711 | **79,481** | 79,193 | 208 |
| `read:nand` | 724 | 1,441 | **2,165** | 2,085 | 132 |
| `full:nand` | 4,252 | 5,543 | **9,795** | 9,572 | 144 |

## rv32imc

Debian clang version 19.1.7 (3+b1): `clang --target=riscv32-unknown-elf -march=rv32imc -mabi=ilp32 -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -fstack-usage -c`

| Configuration | text | rodata | total | linked | stack |
|---|--:|--:|--:|--:|--:|
| `id:nor` | 910 | 3,332 | **4,242** | 4,200 | 80 |
| `read:nor` | 1,598 | 9,907 | **11,505** | 11,457 | 96 |
| `write:nor` | 1,744 | 14,708 | **16,452** | 16,404 | 96 |
| `describe:nor` | 5,166 | 36,220 | **41,386** | 41,258 | 208 |
| `full:nor` | 9,692 | 46,885 | **56,577** | 56,160 | 240 |
| `id+sfdp:nor` | 1,672 | 3,350 | **5,022** | 4,908 | 80 |
| `read+sfdp:nor` | 2,360 | 9,925 | **12,285** | 12,165 | 96 |
| `full-sfdp_summary:nor` | 9,498 | 46,140 | **55,638** | 55,218 | 240 |
| `full+sfdp_dumps:nor` | 10,346 | 65,863 | **76,209** | 75,771 | 240 |
| `id` | 1,126 | 3,888 | **5,014** | 4,966 | 112 |
| `read` | 1,834 | 11,237 | **13,071** | 13,017 | 144 |
| `write` | 1,980 | 16,294 | **18,274** | 18,220 | 144 |
| `describe` | 5,406 | 40,357 | **45,763** | 45,634 | 208 |
| `full` | 9,926 | 51,403 | **61,329** | 60,910 | 240 |
| `full+datasheet` | 10,276 | 98,786 | **109,062** | 108,646 | 240 |
| `full+datasheets` | 11,316 | 166,480 | **177,796** | 177,306 | 240 |
| `full+records+provenance+jep106` | 11,208 | 201,975 | **213,183** | 212,722 | 240 |
| `full+sfdp+sfdp_dumps` | 11,342 | 70,399 | **81,741** | 81,243 | 240 |
| `read:nand` | 914 | 1,345 | **2,259** | 2,241 | 48 |
| `full:nand` | 5,530 | 5,303 | **10,833** | 10,590 | 192 |

## x86_64

gcc (Debian 14.2.0-19) 14.2.0: `gcc -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -fstack-usage -c`

| Configuration | text | rodata | total | linked | stack |
|---|--:|--:|--:|--:|--:|
| `id:nor` | 845 | 3,332 | **4,177** | 4,195 | 160 |
| `read:nor` | 1,297 | 9,907 | **11,204** | 11,275 | 168 |
| `write:nor` | 1,392 | 14,708 | **16,100** | 16,182 | 168 |
| `describe:nor` | 3,630 | 36,220 | **39,850** | 40,108 | 224 |
| `full:nor` | 6,831 | 46,885 | **53,716** | 54,015 | 288 |
| `id+sfdp:nor` | 1,584 | 3,350 | **4,934** | 4,966 | 160 |
| `read+sfdp:nor` | 2,036 | 9,925 | **11,961** | 12,046 | 168 |
| `full-sfdp_summary:nor` | 6,756 | 46,140 | **52,896** | 53,140 | 288 |
| `full+sfdp_dumps:nor` | 7,324 | 65,863 | **73,187** | 73,484 | 288 |
| `id` | 969 | 3,888 | **4,857** | 4,862 | 152 |
| `read` | 1,474 | 11,237 | **12,711** | 12,757 | 184 |
| `write` | 1,569 | 16,294 | **17,863** | 17,918 | 184 |
| `describe` | 3,807 | 40,357 | **44,164** | 44,400 | 224 |
| `full` | 7,008 | 51,403 | **58,411** | 58,672 | 288 |
| `full+datasheet` | 7,063 | 98,786 | **105,849** | 106,119 | 288 |
| `full+datasheets` | 7,728 | 166,480 | **174,208** | 174,500 | 288 |
| `full+records+provenance+jep106` | 7,590 | 201,975 | **209,565** | 209,882 | 288 |
| `full+sfdp+sfdp_dumps` | 8,240 | 70,399 | **78,639** | 78,944 | 288 |
| `read:nand` | 701 | 1,345 | **2,046** | 2,070 | 144 |
| `full:nand` | 3,831 | 5,303 | **9,134** | 9,223 | 256 |

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
