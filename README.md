# uspiflash

A generator of tiny, single-file C libraries that detect SPI flash chips and
report their capabilities, built from the
[spiflash](https://github.com/mithro/spiflash) database, for early-boot and
embedded code: Zephyr, MicroPython, the LiteX BIOS, bare-metal Cortex-M and
RISC-V (down to WCH's CH32V003), and Linux spidev.

Every byte the library puts on a device is measured, across a wide range of
GCC, LLVM and SDCC versions.

## Quick start

```sh
pip install uspiflash
uspiflash generate -o uspiflash.h --level full
```

Include the header wherever you need it; in exactly one C file, define
`USF_IMPLEMENTATION` first, so that file holds the library's code:

```c
#define USF_IMPLEMENTATION
#include "uspiflash.h"

/* Yours, defined elsewhere: an SPI transaction (chip select held: send
 * txlen bytes, then read rxlen), and a console that takes one character. */
void my_xfer(void *ctx, const uint8_t *tx, uint8_t txlen, uint8_t *rx, uint8_t rxlen);
void my_putc(void *ctx, char ch);

void show_flash(void)
{
    usf_bus bus = { my_xfer, 0 };
    usf_probe_result r;

    usf_probe(&bus, &r);
    usf_print(r.chip, r.count, USF_PRINT_OPCODES, my_putc, 0);
}
```

The full C API, with a worked example of each step above:
[`docs/generated-file.md`](https://github.com/mithro/uspiflash/blob/main/docs/generated-file.md)
(also at <https://uspiflash.readthedocs.io/>).
Already on Linux with a spidev device: skip the generator and use
[`uspiflash-linux`](https://github.com/mithro/uspiflash/blob/main/examples/linux/README.md)
instead, built from source or `sudo apt install uspiflash-linux` from the
apt repository below.

## Size

<!-- sizes: generated from sizes/ledger.json by `uspiflash measure --write` -->
For SPI NOR flash (`--type nor`, the default), compiled for `cortex-m0` with
Debian clang version 19.1.7 (3+b1) at `-Os`, the `read` level costs
**15,877 bytes** of flash and `full` **84,971 bytes**, code and tables
together, with no static RAM. Every configuration (all chip types, and
NAND), every target, and how they are measured:
[`sizes/README.md`](https://github.com/mithro/uspiflash/blob/main/sizes/README.md).
<!-- sizes: end -->

## Output

A generated file's `usf_print()` and `usf_print_json()` print exactly what
`spiflash id` and `spiflash id --json` print, byte for byte, less what the
file was generated without: the `from:` line and per-opcode sources without
`sources`, conflicts without `conflicts`, the datasheet line without
`datasheet`, the JSON `datasheets`, `records` and records' `at` without
`datasheets`, `records` and `provenance`, the `sfdp:` lines without
`sfdp_summary`, and the JSON `sfdp` without `sfdp_dumps`. The tests check
this against spiflash 0.0.post182 (`uspiflash.VERIFIED_SPIFLASH`).
`--with sfdp` adds `usf_sfdp_read()`, which reads and decodes the chip's own
SFDP tables (JESD216).

SPI NOR is the primary target: `uspiflash generate` keeps only SPI NOR chips
unless told otherwise (`--type nor --type nand` keeps every chip, NAND
included; `--type nand` only NAND).

On 16-bit targets (AVR, msp430, the 8051) the levels `id` to `full` fit, if
the part has the flash (`full` is about 59 KB of code and tables); the
`datasheet`, `datasheets`, `records`, `provenance` and `jep106` extras do
not, as their tables pass the 64 KiB a 16-bit pointer can address. On AVR,
define `USF_ROM` as a flash address space (avr-gcc's `__flash`) to keep the
tables in flash rather than copied to RAM.

## Install

```sh
pip install uspiflash          # or: uv tool install uspiflash
```

Or, as Debian packages, from the signed apt repository at
<https://mith.ro/uspiflash/>. There is one per suite (bookworm, trixie, forky
and sid), with two packages:

- `python3-uspiflash`, the generator (the `uspiflash` command). It is
  `Architecture: all`, so it installs on any architecture, and it depends
  on `python3-spiflash`, which is not in this repository: add spiflash's
  own apt repository first, then uspiflash's.
- `uspiflash-linux`, the spidev tool. It depends only on libc, so it needs
  only uspiflash's repository. It is built for amd64, i386, arm64, armhf
  and riscv64 (riscv64 from trixie on). The armhf package is Debian's armhf
  (ARMv7 and later): Raspberry Pi OS 32-bit on an ARMv6 board (Pi 1, Zero)
  cannot run it; a 64-bit Pi uses the arm64 package.

Put your suite's name in place of `trixie` below (Raspberry Pi OS uses
Debian's codenames). For the generator, spiflash's repository:

```sh
sudo install -d -m0755 /etc/apt/keyrings
curl -fsSL https://mith.ro/spiflash/spiflash.gpg | sudo tee /etc/apt/keyrings/spiflash.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/spiflash.gpg] https://mith.ro/spiflash/trixie/ ./" \
  | sudo tee /etc/apt/sources.list.d/spiflash.list
```

spiflash's repository's signing key is
`B528 6C61 A99A 9E6A 5B8A  8E5B 6B2D 7683 DE01 081D`
(`gpg --show-keys /etc/apt/keyrings/spiflash.gpg` shows it).

For either package, uspiflash's repository:

```sh
sudo install -d -m0755 /etc/apt/keyrings
curl -fsSL https://mith.ro/uspiflash/uspiflash.gpg | sudo tee /etc/apt/keyrings/uspiflash.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/uspiflash.gpg] https://mith.ro/uspiflash/trixie/ ./" \
  | sudo tee /etc/apt/sources.list.d/uspiflash.list
```

uspiflash's repository's signing key is
`2E19 5D58 706D 44E8 5704  1566 04FA D17C 2A3B 8344`
(`gpg --show-keys /etc/apt/keyrings/uspiflash.gpg` shows it).

```sh
sudo apt update
sudo apt install python3-uspiflash      # provides the uspiflash command
sudo apt install uspiflash-linux        # the spidev tool
```

Work in progress: the design is in
[`docs/superpowers/specs/`](https://github.com/mithro/uspiflash/tree/main/docs/superpowers/specs/).

## License

Apache-2.0; see [LICENSE](https://github.com/mithro/uspiflash/blob/main/LICENSE).
