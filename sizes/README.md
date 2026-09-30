# Sizes

<!-- Generated from ledger.json by `uspiflash measure --write`: do not edit. -->

What the generated library costs in flash, in bytes, for each configuration
and target. Each configuration's header is generated with the default prefix,
its implementation compiled on its own (`-c`, no unwind tables), and the
object's sections read with `llvm-readobj --sections`. Sections count by
their ELF flags, not their names: **text** is every allocated, executable
section (code); **rodata** is every other allocated, read-only one (tables
and strings, plus anything else that lands in flash, such as the
`.ARM.exidx` entries clang emits for Arm even without unwind tables); and
**total** is text + rodata, everything the object puts in flash. Every
object has no allocated writable section (data and bss are 0; the
measurement refuses otherwise), so the library needs no RAM beyond its
stack; and no object has an undefined symbol (`llvm-nm -u` is empty, or
the measurement fails), so it calls no libc function and no compiler
helper. Linking can add alignment. `ledger.json` lists every allocated
section of every object.

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

Debian clang version 19.1.7 (3+b1): `clang --target=thumbv6m-none-eabi -mcpu=cortex-m0 -mthumb -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id:nor` | 754 | 3,388 | **4,142** |
| `read:nor` | 1,272 | 10,003 | **11,275** |
| `write:nor` | 1,380 | 14,820 | **16,200** |
| `describe:nor` | 3,884 | 36,428 | **40,312** |
| `full:nor` | 7,366 | 47,181 | **54,547** |
| `id+sfdp:nor` | 1,430 | 3,422 | **4,852** |
| `read+sfdp:nor` | 1,948 | 10,037 | **11,985** |
| `full-sfdp_summary:nor` | 7,226 | 46,436 | **53,662** |
| `full+sfdp_dumps:nor` | 7,966 | 66,159 | **74,125** |
| `id` | 922 | 3,944 | **4,866** |
| `read` | 1,472 | 11,333 | **12,805** |
| `write` | 1,580 | 16,406 | **17,986** |
| `describe` | 4,084 | 40,565 | **44,649** |
| `full` | 7,566 | 51,699 | **59,265** |
| `full+datasheet` | 7,766 | 99,082 | **106,848** |
| `full+datasheets` | 8,638 | 166,776 | **175,414** |
| `full+records+provenance+jep106` | 8,542 | 202,279 | **210,821** |
| `full+sfdp+sfdp_dumps` | 8,842 | 70,711 | **79,553** |
| `read:nand` | 724 | 1,441 | **2,165** |
| `full:nand` | 4,252 | 5,543 | **9,795** |

## rv32imc

Debian clang version 19.1.7 (3+b1): `clang --target=riscv32-unknown-elf -march=rv32imc -mabi=ilp32 -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id:nor` | 910 | 3,332 | **4,242** |
| `read:nor` | 1,598 | 9,907 | **11,505** |
| `write:nor` | 1,744 | 14,708 | **16,452** |
| `describe:nor` | 5,166 | 36,220 | **41,386** |
| `full:nor` | 9,692 | 46,885 | **56,577** |
| `id+sfdp:nor` | 1,720 | 3,350 | **5,070** |
| `read+sfdp:nor` | 2,408 | 9,925 | **12,333** |
| `full-sfdp_summary:nor` | 9,498 | 46,140 | **55,638** |
| `full+sfdp_dumps:nor` | 10,502 | 65,899 | **76,401** |
| `id` | 1,126 | 3,888 | **5,014** |
| `read` | 1,834 | 11,237 | **13,071** |
| `write` | 1,980 | 16,294 | **18,274** |
| `describe` | 5,406 | 40,357 | **45,763** |
| `full` | 9,926 | 51,403 | **61,329** |
| `full+datasheet` | 10,276 | 98,786 | **109,062** |
| `full+datasheets` | 11,340 | 166,480 | **177,820** |
| `full+records+provenance+jep106` | 11,208 | 201,975 | **213,183** |
| `full+sfdp+sfdp_dumps` | 11,546 | 70,435 | **81,981** |
| `read:nand` | 914 | 1,345 | **2,259** |
| `full:nand` | 5,530 | 5,303 | **10,833** |

## x86_64

gcc (Debian 14.2.0-19) 14.2.0: `gcc -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id:nor` | 845 | 3,332 | **4,177** |
| `read:nor` | 1,297 | 9,907 | **11,204** |
| `write:nor` | 1,392 | 14,708 | **16,100** |
| `describe:nor` | 3,630 | 36,220 | **39,850** |
| `full:nor` | 6,831 | 46,885 | **53,716** |
| `id+sfdp:nor` | 1,623 | 3,350 | **4,973** |
| `read+sfdp:nor` | 2,075 | 9,925 | **12,000** |
| `full-sfdp_summary:nor` | 6,756 | 46,140 | **52,896** |
| `full+sfdp_dumps:nor` | 7,366 | 65,899 | **73,265** |
| `id` | 969 | 3,888 | **4,857** |
| `read` | 1,474 | 11,237 | **12,711** |
| `write` | 1,569 | 16,294 | **17,863** |
| `describe` | 3,807 | 40,357 | **44,164** |
| `full` | 7,008 | 51,403 | **58,411** |
| `full+datasheet` | 7,063 | 98,786 | **105,849** |
| `full+datasheets` | 7,737 | 166,480 | **174,217** |
| `full+records+provenance+jep106` | 7,590 | 201,975 | **209,565** |
| `full+sfdp+sfdp_dumps` | 8,321 | 70,435 | **78,756** |
| `read:nand` | 701 | 1,345 | **2,046** |
| `full:nand` | 3,831 | 5,303 | **9,134** |

## Regenerate

Tools:

- `clang`: Debian clang version 19.1.7 (3+b1)
- `gcc`: gcc (Debian 14.2.0-19) 14.2.0
- `llvm-readobj`: Debian LLVM version 19.1.7

These are the Debian packages `clang-19`, `llvm-19`, `gcc`, `libc6-dev`
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
