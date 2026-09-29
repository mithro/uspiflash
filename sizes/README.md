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
stack. Linking can add compiler helpers and alignment. `ledger.json` lists
every allocated section of every object.

Measured against spiflash 0.0.post74 (database format 3).
These are compiled objects; the
[database-statistics experiment](https://github.com/mithro/uspiflash/blob/main/experiments/2026-09-28-database-statistics/README.md)
counts the raw table bytes before compiling.

## Configurations

SPI NOR is the primary target: its builds (`--type nor`, the `:nor` rows)
come first, and the default (all types) and NAND builds are listed for
comparison.

| Configuration | `uspiflash generate` options |
|---|---|
| `id:nor` | `--level id --type nor` |
| `read:nor` | `--level read --type nor` |
| `write:nor` | `--level write --type nor` |
| `describe:nor` | `--level describe --type nor` |
| `full:nor` | `--level full --type nor` |
| `id` | `--level id` |
| `read` | `--level read` |
| `write` | `--level write` |
| `describe` | `--level describe` |
| `full` | `--level full` |
| `full+datasheet` | `--level full --with datasheet` |
| `full+datasheets` | `--level full --with datasheets` |
| `full+records+provenance+jep106` | `--level full --with jep106 --with provenance --with records` |
| `read:nand` | `--level read --type nand` |
| `full:nand` | `--level full --type nand` |

## cortex-m0

Debian clang version 19.1.7 (3+b1): `clang --target=thumbv6m-none-eabi -mcpu=cortex-m0 -mthumb -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id:nor` | 754 | 3,388 | **4,142** |
| `read:nor` | 1,272 | 10,003 | **11,275** |
| `write:nor` | 1,380 | 14,820 | **16,200** |
| `describe:nor` | 3,760 | 35,683 | **39,443** |
| `full:nor` | 7,266 | 46,436 | **53,702** |
| `id` | 922 | 3,944 | **4,866** |
| `read` | 1,472 | 11,333 | **12,805** |
| `write` | 1,580 | 16,406 | **17,986** |
| `describe` | 3,960 | 39,820 | **43,780** |
| `full` | 7,466 | 50,954 | **58,420** |
| `full+datasheet` | 7,666 | 98,337 | **106,003** |
| `full+datasheets` | 8,530 | 166,019 | **174,549** |
| `full+records+provenance+jep106` | 8,434 | 201,522 | **209,956** |
| `read:nand` | 724 | 1,441 | **2,165** |
| `full:nand` | 4,252 | 5,543 | **9,795** |

## rv32imc

Debian clang version 19.1.7 (3+b1): `clang --target=riscv32-unknown-elf -march=rv32imc -mabi=ilp32 -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id:nor` | 910 | 3,332 | **4,242** |
| `read:nor` | 1,598 | 9,907 | **11,505** |
| `write:nor` | 1,744 | 14,708 | **16,452** |
| `describe:nor` | 5,040 | 35,475 | **40,515** |
| `full:nor` | 9,548 | 46,140 | **55,688** |
| `id` | 1,126 | 3,888 | **5,014** |
| `read` | 1,834 | 11,237 | **13,071** |
| `write` | 1,980 | 16,294 | **18,274** |
| `describe` | 5,280 | 39,612 | **44,892** |
| `full` | 9,782 | 50,658 | **60,440** |
| `full+datasheet` | 10,144 | 98,041 | **108,185** |
| `full+datasheets` | 11,182 | 165,723 | **176,905** |
| `full+records+provenance+jep106` | 11,050 | 201,218 | **212,268** |
| `read:nand` | 914 | 1,345 | **2,259** |
| `full:nand` | 5,530 | 5,303 | **10,833** |

## x86_64

gcc (Debian 14.2.0-19) 14.2.0: `gcc -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id:nor` | 845 | 3,332 | **4,177** |
| `read:nor` | 1,297 | 9,907 | **11,204** |
| `write:nor` | 1,392 | 14,708 | **16,100** |
| `describe:nor` | 3,501 | 35,475 | **38,976** |
| `full:nor` | 6,739 | 46,140 | **52,879** |
| `id` | 969 | 3,888 | **4,857** |
| `read` | 1,474 | 11,237 | **12,711** |
| `write` | 1,569 | 16,294 | **17,863** |
| `describe` | 3,678 | 39,612 | **43,290** |
| `full` | 6,916 | 50,658 | **57,574** |
| `full+datasheet` | 6,978 | 98,041 | **105,019** |
| `full+datasheets` | 7,635 | 165,723 | **173,358** |
| `full+records+provenance+jep106` | 7,488 | 201,218 | **208,706** |
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
