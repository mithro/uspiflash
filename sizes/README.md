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

| Configuration | `uspiflash generate` options |
|---|---|
| `id` | `--level id` |
| `read` | `--level read` |
| `write` | `--level write` |
| `describe` | `--level describe` |
| `full` | `--level full` |
| `full+datasheet` | `--level full --with datasheet` |
| `full+datasheets` | `--level full --with datasheets` |
| `full+records+provenance+jep106` | `--level full --with jep106 --with provenance --with records` |
| `read:nor` | `--level read --type nor` |
| `read:nand` | `--level read --type nand` |
| `full:nor` | `--level full --type nor` |
| `full:nand` | `--level full --type nand` |

## cortex-m0

Debian clang version 19.1.7 (3+b1): `clang --target=thumbv6m-none-eabi -mcpu=cortex-m0 -mthumb -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id` | 874 | 3,944 | **4,818** |
| `read` | 1,424 | 11,333 | **12,757** |
| `write` | 1,532 | 16,406 | **17,938** |
| `describe` | 3,912 | 39,820 | **43,732** |
| `full` | 7,418 | 50,954 | **58,372** |
| `full+datasheet` | 7,618 | 98,337 | **105,955** |
| `full+datasheets` | 8,482 | 166,019 | **174,501** |
| `full+records+provenance+jep106` | 8,386 | 201,522 | **209,908** |
| `read:nor` | 1,272 | 10,003 | **11,275** |
| `read:nand` | 726 | 1,441 | **2,167** |
| `full:nor` | 7,266 | 46,436 | **53,702** |
| `full:nand` | 4,254 | 5,543 | **9,797** |

## rv32imc

Debian clang version 19.1.7 (3+b1): `clang --target=riscv32-unknown-elf -march=rv32imc -mabi=ilp32 -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id` | 1,052 | 3,888 | **4,940** |
| `read` | 1,760 | 11,237 | **12,997** |
| `write` | 1,906 | 16,294 | **18,200** |
| `describe` | 5,206 | 39,612 | **44,818** |
| `full` | 9,708 | 50,658 | **60,366** |
| `full+datasheet` | 10,070 | 98,041 | **108,111** |
| `full+datasheets` | 11,108 | 165,723 | **176,831** |
| `full+records+provenance+jep106` | 10,976 | 201,218 | **212,194** |
| `read:nor` | 1,598 | 9,907 | **11,505** |
| `read:nand` | 914 | 1,345 | **2,259** |
| `full:nor` | 9,548 | 46,140 | **55,688** |
| `full:nand` | 5,530 | 5,303 | **10,833** |

## x86_64

gcc (Debian 14.2.0-19) 14.2.0: `gcc -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id` | 928 | 3,888 | **4,816** |
| `read` | 1,433 | 11,237 | **12,670** |
| `write` | 1,528 | 16,294 | **17,822** |
| `describe` | 3,637 | 39,612 | **43,249** |
| `full` | 6,875 | 50,658 | **57,533** |
| `full+datasheet` | 6,937 | 98,041 | **104,978** |
| `full+datasheets` | 7,594 | 165,723 | **173,317** |
| `full+records+provenance+jep106` | 7,447 | 201,218 | **208,665** |
| `read:nor` | 1,297 | 9,907 | **11,204** |
| `read:nand` | 700 | 1,345 | **2,045** |
| `full:nor` | 6,739 | 46,140 | **52,879** |
| `full:nand` | 3,830 | 5,303 | **9,133** |

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
