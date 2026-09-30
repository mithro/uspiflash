# uspiflash-linux under QEMU

`tests/test_qemu.py` runs `uspiflash-linux` (`examples/linux/`) on a real
Linux kernel, against a SPI flash chip that answers over a real SPI
controller driver and spidev, and checks that it prints what `spiflash id
9d7019 --opcodes` prints, followed by the chip's own SFDP table decoded as
`uspiflash.oracle.sfdp_fields` decodes spiflash's copy of it.

The machine is QEMU's `sifive_u` (a SiFive HiFive Unleashed), whose first
SPI controller has an emulated `is25wp256` (id `9d7019`) with an SFDP
table. The guest is Debian trixie's riscv64 kernel with an initramfs of
busybox, the controller's module, the tool and `init`.

```sh
USPIFLASH_QEMU=1 uv run python -m uspiflash.sandbox -- \
    uv run pytest tests/test_qemu.py -o addopts="--basetemp=tmp/pytest"
uv run tools/qemu/run.py            # just the guest tool's output
uv run tools/qemu/run.py --verbose  # and the whole console, on stderr
```

The host needs only docker. The test is skipped unless `USPIFLASH_QEMU=1`
is set and `docker` is on `PATH`. CI runs it in `.github/workflows/qemu.yml`.

## The files

- `Dockerfile`: the image everything runs in. It is `uspiflash.ledger.IMAGE`
  (Debian trixie, pinned by digest) with its packages from
  snapshot.debian.org at `uspiflash.ledger.SNAPSHOT`, as the size ledger's
  image: `qemu-system-riscv` and `opensbi` (QEMU's `-bios default`), the
  riscv64 cross compiler, `cpio`, `xz-utils`, `kmod` and `python3`. The
  riscv64 kernel and busybox packages are downloaded by version and
  unpacked under `/opt/riscv`, not installed.
- `build_image.py`: run in that image as the calling user, builds the
  guest: the kernel `Image` and `initramfs.cpio.gz`, into `tmp/qemu/`.
- `init`: the guest's `/init` (busybox sh).
- `run.py`: generates the tool's header on the host (the Makefile's
  `GENERATE` options), builds the image, builds the guest, boots it with a
  300 s timeout, and prints the tool's output from between the markers
  `init` prints. It exits with the tool's exit code, or 3 if the markers
  never appear; then the console's last 200 lines and docker's exit code go
  to stderr. Every `docker run` gets `--rm` and the memory and CPU limits
  `uspiflash.sandbox.current_limits()` gives, and `--pids-limit 512`; a
  hung one is killed. The image is tagged `uspiflash-qemu:<hash>`, a hash
  of the Dockerfile and its build arguments, and kept as a cache (about
  720 MB): an image of that tag is used as it is. When the pins change, a
  new tag is built, and `docker rmi` removes the old one. The Dockerfile
  checks the kernel's and busybox's .deb sha256s against run.py's.

The tool is cross-compiled with `riscv64-linux-gnu-gcc -static -Os`, the
Makefile's `CFLAGS` (read from `examples/linux/Makefile`) and
`-DUSPIFLASH_LINUX_VERSION` set to `uspiflash --version`'s line, as `make`
builds it.

## The guest

`init` mounts devtmpfs, proc and sysfs, makes busybox's applet links (the
riscv64 busybox cannot run on the build host to list them), and `insmod`s
the modules `build_image.py` listed in `/modules`: `spi-sifive` (its
`modinfo -F depends` is empty), decompressed from `.ko.xz`. `spi-nor` and
`mtd` are never in the initramfs: the flash must be free for spidev.

It finds the flash as the SPI device whose device tree node's
`compatible` has `jedec,spi-nor`, writes `spidev` to its `driver_override`
and binds it (`/sys/bus/spi/drivers/spidev/bind`). The device node is
`/dev/spidev<bus>.<cs>`. It runs `uspiflash-linux -D <node> --opcodes
--sfdp` between `=== uspiflash-linux ===` and `=== exit <code> ===`,
`=== end ===`, and then `reboot -f`: `sifive_u` has no power-off device
(OpenSBI reports `Platform Shutdown Device : ---` and `Platform Reboot
Device : gpio-restart`), so `poweroff -f` only halts the CPU, while a reboot
makes QEMU, run with `-no-reboot`, exit.

The kernel's command line has `quiet loglevel=0`, so kernel messages do not
interleave with the tool's output on the one serial console. `--verbose`
drops them, and `init` then shows what it found in the kernel log.

## Pins

From snapshot.debian.org at `20260918T000000Z` (riscv64):

| package | version | .deb sha256 |
| --- | --- | --- |
| `linux-image-6.12.107+deb13-riscv64` | `6.12.107-1` | `abe9f65d74b434692149482b031db7a2aaf832921e09f69f775293c0e0c5799c` |
| `busybox-static` | `1:1.37.0-6+b9` | `4add476d2b185c5b487c285b38d790f0881a7e4a8e2ddde835f917e770eb8633` |

and (amd64) `qemu-system-riscv` `1:10.0.13+ds-0+deb13u1`, `opensbi` `1.6-1`,
`gcc-riscv64-linux-gnu` `4:14.2.0-1` (gcc 14.2.0-19),
`libc6-dev-riscv64-cross` `2.41-11cross1`.

The kernel is the snapshot's, 6.12.107: the live mirror's 6.12.111 came
later. To list the versions a snapshot has, in the image:

```sh
apt-get update && apt-cache policy linux-image-riscv64:riscv64 busybox-static:riscv64
apt-cache search --names-only '^linux-image-6.*riscv64$'
```

## Evidence

Checked on 2026-09-30 against the QEMU sources at `81ce3a87` (the commit
spiflash's QEMU dumps come from) and in this image.

1. `sifive_u` attaches an `is25wp256` to SPI0 (`hw/riscv/sifive_u.c:597-605`).
   Its device tree node is `/soc/spi@10040000/flash@0`, `compatible =
   "jedec,spi-nor"` (`:325-333`). SPI2 (`spi@10050000`) has an
   `mmc-spi-slot` at `mmc@0`. `hw/block/m25p80.c:229` gives the
   `is25wp256` an SFDP table (`m25p80_sfdp_is25wp256`); RDSFDP takes the
   address and a dummy byte (`:1573-1580`), as the library sends.
2. RDID (`m25p80.c:1419-1431`) answers the 3 id bytes, then zeros to 6
   bytes; then the flash is idle and each further byte (spidev clocks
   `0x00`) decodes as a NOP and reads `0x00`. The tool's 10-byte RDID reads
   `9d7019` and seven `0x00`, so the test's oracle input is that.
3. The kernel's config: `CONFIG_SPI_SIFIVE=m`, `CONFIG_SPI_SPIDEV=y`,
   `CONFIG_MTD_SPI_NOR=m`, `CONFIG_RD_GZIP=y`, `CONFIG_DEVTMPFS=y` (not
   mounted automatically). `/boot/vmlinux-*` is the RISC-V `Image` that
   `-kernel` takes. The initramfs has no `/dev/console` (it is built
   without root), so `init` redirects to it once devtmpfs is mounted.
4. The flash is on bus 0: the two controllers probe as `spi0` and `spi1`,
   and `spidev` binds through `driver_override`. From `run.py --verbose`:

   ```text
   Platform Reboot Device      : gpio-restart
   Platform Shutdown Device    : ---
   [    0.000000] Linux version 6.12.107+deb13-riscv64 (debian-kernel@lists.debian.org) (riscv64-linux-gnu-gcc-14 (Debian 14.2.0-19) 14.2.0, GNU ld (GNU Binutils for Debian) 2.44) #1 SMP Debian 6.12.107-1 (2026-08-29)
   [    0.000000] Machine model: SiFive HiFive Unleashed A00
   [    1.930926] Run /init as init process
   [    2.365193] sifive_spi 10040000.spi: mapped; irq=33, cs=1
   [    2.371429] sifive_spi 10050000.spi: mapped; irq=34, cs=1
   [    2.467048] init: spi0.0 /sys/firmware/devicetree/base/soc/spi@10040000/flash@0 driver=spidev
   [    2.487503] init: spi1.0 /sys/firmware/devicetree/base/soc/spi@10050000/mmc@0 driver=
   [    2.489520] init: flash node /dev/spidev0.0
   === uspiflash-linux ===
   9d7019  ISSI  IS25WP256, IS25WP256D  (nor)
       size 32 MiB, page 256 B, sector 64 KiB, 1.65-1.95 V
   ...
   sfdp=1.6 dwords=16 addr=0 erase4k=0x20 dtr=1 size=33554432 page=256 qe=2 en4b=0x29 ex4b=0xe8
   erase 1:12:0x20 2:15:0x52 3:16:0xd8
   read 1-1-2:0x3b:0+8 1-2-2:0xbb:4+0 1-1-4:0x6b:0+8 1-4-4:0xeb:2+4 4-4-4:0xeb:2+4
   === exit 0 ===
   === end ===
   [    2.624842] reboot: Restarting system
   ```

   The tool's first 39 lines are byte for byte `spiflash id 9d7019
   --opcodes` (spiflash 0.0.post108); the last three are Debian's QEMU
   10.0.13's SFDP table, equal to spiflash's copy of it from `81ce3a87`.
   The guest takes under 3 s from power-on; the whole run, with the
   image cached, about 15 s.
