# uspiflash

A generator of tiny, single-file C libraries that detect SPI flash chips and
report their capabilities, built from the
[spiflash](https://github.com/mithro/spiflash) database, for early-boot and
embedded code: Zephyr, MicroPython, the LiteX BIOS, bare-metal Cortex-M and
RISC-V (down to WCH's CH32V003), and Linux spidev.

Every byte the library puts on a device is measured, across a wide range of
GCC, LLVM and SDCC versions.

Work in progress: the design is in
[`docs/superpowers/specs/`](docs/superpowers/specs/).

## License

Apache-2.0; see [LICENSE](LICENSE).
