# uspiflash

A generator of tiny, single-file C libraries that detect SPI flash chips and
report their capabilities, built from the
[spiflash](https://github.com/mithro/spiflash) database, for early-boot and
embedded code: Zephyr, MicroPython, the LiteX BIOS, bare-metal Cortex-M and
RISC-V (down to WCH's CH32V003), and Linux spidev.

Every byte the library puts on a device is measured, across a wide range of
GCC, LLVM and SDCC versions.

## Size

<!-- sizes: generated from sizes/ledger.json by `uspiflash measure --write` -->
Compiled for `cortex-m0` with Debian clang version 19.1.7 (3+b1) at `-Os`,
the `read` level costs **12,105 bytes** of flash and `full`
**55,083 bytes**, code and tables together, with no static RAM.
Every configuration and target, and how they are measured:
[`sizes/README.md`](https://github.com/mithro/uspiflash/blob/main/sizes/README.md).
<!-- sizes: end -->

## Install

```sh
pip install uspiflash          # or: uv tool install uspiflash
```

Or, as a Debian package, from the signed apt repository at
<https://mith.ro/uspiflash/>. There is one per suite (bookworm, trixie, forky
and sid), and the package is `Architecture: all`, so it installs on any
architecture. `python3-uspiflash` depends on `python3-spiflash`, which is not
in this repository, so add spiflash's own apt repository first, then
uspiflash's. Put your suite's name in place of `trixie` below (Raspberry Pi
OS uses Debian's codenames):

```sh
sudo install -d -m0755 /etc/apt/keyrings
curl -fsSL https://mith.ro/spiflash/spiflash.gpg | sudo tee /etc/apt/keyrings/spiflash.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/spiflash.gpg] https://mith.ro/spiflash/trixie/ ./" \
  | sudo tee /etc/apt/sources.list.d/spiflash.list
```

spiflash's repository's signing key is
`B528 6C61 A99A 9E6A 5B8A  8E5B 6B2D 7683 DE01 081D`
(`gpg --show-keys /etc/apt/keyrings/spiflash.gpg` shows it).

```sh
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
```

Work in progress: the design is in
[`docs/superpowers/specs/`](https://github.com/mithro/uspiflash/tree/main/docs/superpowers/specs/).

## License

Apache-2.0; see [LICENSE](https://github.com/mithro/uspiflash/blob/main/LICENSE).
