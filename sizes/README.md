# Sizes

<!-- Generated from ledger.json by `uspiflash measure --write`: do not edit. -->

What the generated library costs in flash, in bytes, for each configuration
and target. Each configuration's header is generated with the default prefix,
its implementation compiled on its own (`-c`), and the object read with
`llvm-size -A`. **text** is code (`.text*`), **rodata** is tables and strings
(`.rodata*`, `.srodata*`), and **total** is text + rodata + data. Every object
has no writable static data: data and bss are 0 (the measurement refuses
otherwise), so the library needs no RAM beyond its stack. Unwind tables
(`.ARM.exidx`, `.eh_frame`) are not counted, and linking can add compiler
helpers and alignment; `ledger.json` lists every section of every object.

Measured against spiflash 0.0.post39 (database format 2).
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

Debian clang version 19.1.7 (3+b1): `clang --target=thumbv6m-none-eabi -mcpu=cortex-m0 -mthumb -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id` | 874 | 3,823 | **4,697** |
| `read` | 1,424 | 10,681 | **12,105** |
| `write` | 1,532 | 15,393 | **16,925** |
| `describe` | 3,912 | 37,760 | **41,672** |
| `full` | 7,418 | 47,665 | **55,083** |
| `full+datasheet` | 7,618 | 94,990 | **102,608** |
| `full+datasheets` | 8,482 | 162,558 | **171,040** |
| `full+records+provenance+jep106` | 8,386 | 191,976 | **200,362** |
| `read:nor` | 1,272 | 9,351 | **10,623** |
| `read:nand` | 726 | 1,345 | **2,071** |
| `full:nor` | 7,266 | 43,145 | **50,411** |
| `full:nand` | 4,254 | 5,287 | **9,541** |

## rv32imc

Debian clang version 19.1.7 (3+b1): `clang --target=riscv32-unknown-elf -march=rv32imc -mabi=ilp32 -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id` | 1,052 | 3,823 | **4,875** |
| `read` | 1,760 | 10,681 | **12,441** |
| `write` | 1,906 | 15,393 | **17,299** |
| `describe` | 5,206 | 37,760 | **42,966** |
| `full` | 9,708 | 47,665 | **57,373** |
| `full+datasheet` | 10,070 | 94,990 | **105,060** |
| `full+datasheets` | 11,108 | 162,558 | **173,666** |
| `full+records+provenance+jep106` | 10,976 | 191,976 | **202,952** |
| `read:nor` | 1,598 | 9,351 | **10,949** |
| `read:nand` | 914 | 1,345 | **2,259** |
| `full:nor` | 9,548 | 43,145 | **52,693** |
| `full:nand` | 5,530 | 5,287 | **10,817** |

## x86_64

gcc (Debian 14.2.0-19) 14.2.0: `gcc -std=c99 -Os -ffreestanding -fno-common -ffunction-sections -fdata-sections -Wall -Wextra -Wpedantic -Wundef -Werror -c`

| Configuration | text | rodata | total |
|---|--:|--:|--:|
| `id` | 928 | 3,823 | **4,751** |
| `read` | 1,433 | 10,681 | **12,114** |
| `write` | 1,528 | 15,393 | **16,921** |
| `describe` | 3,637 | 37,760 | **41,397** |
| `full` | 6,875 | 47,665 | **54,540** |
| `full+datasheet` | 6,937 | 94,990 | **101,927** |
| `full+datasheets` | 7,594 | 162,558 | **170,152** |
| `full+records+provenance+jep106` | 7,447 | 191,976 | **199,423** |
| `read:nor` | 1,297 | 9,351 | **10,648** |
| `read:nand` | 700 | 1,345 | **2,045** |
| `full:nor` | 6,739 | 43,145 | **49,884** |
| `full:nand` | 3,830 | 5,287 | **9,117** |

## Regenerate

Tools:

- `clang`: Debian clang version 19.1.7 (3+b1)
- `gcc`: gcc (Debian 14.2.0-19) 14.2.0
- `llvm-size`: Debian LLVM version 19.1.7

These are Debian trixie's `clang-19`, `llvm-19` and `gcc`. Regenerate with
the same versions (CI's `sizes` job checks in a `debian:trixie` container):

```sh
uv run python -m uspiflash.sandbox -- uv run uspiflash measure --write
```

`uv run uspiflash measure --check` exits 1 when this ledger is stale, and 2
when the installed tools differ from the ones above.
