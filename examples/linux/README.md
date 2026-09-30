# uspiflash-linux

`uspiflash-linux` identifies the SPI flash chip on a Linux `spidev` device
and describes it exactly as `spiflash id` does: the same text (with
`--opcodes`, the operation list too) or the same JSON, byte for byte. It
is the first real user of a uspiflash-generated header: it probes with
`usf_probe`, prints with `usf_print` / `usf_print_json`, and with `--sfdp`
also reads the chip's own SFDP table with `usf_sfdp_read`.

It can also look an id up offline, like `spiflash id HEX`, with no device.

## Building

```sh
make                 # build/uspiflash-linux, statically linked
make LDFLAGS=        # dynamically linked
make CC=clang        # any C99 compiler with the Linux headers
make USPIFLASH=uspiflash   # an installed uspiflash, not `uv run uspiflash`
```

`make` first generates `build/uspiflash.h` with uspiflash (by default
through `uv run`):

```sh
uspiflash generate -o build/uspiflash.h --level full --type nor --type nand \
    --with sfdp --with sfdp_dumps --with datasheet --with datasheets \
    --with records --with provenance
```

That is every chip type (`generate` alone keeps only SPI NOR) and every
extra that changes what `spiflash id` prints, so the tool has the whole
database. It has no size budget: the static binary is about 1 MiB on
x86-64 with glibc, the dynamic one about 300 KiB. `uspiflash-linux
--version` names the uspiflash (and spiflash) that generated its header.
`make` remakes the header, and so the tool, whenever that version changes
(it keeps it in `build/version`).

A static glibc build needs `libc.a` (Debian: `libc6-dev`). musl builds are
for a later milestone: `musl-gcc` has no `linux/spi/spidev.h`.

## Running

```text
uspiflash-linux [-D DEVICE] [-s HZ] [--json | --sfdp] [--opcodes]
uspiflash-linux id HEX [--method FAMILY] [--json] [--opcodes]
uspiflash-linux --version | -h | --help
```

- `-D DEVICE`: the spidev device, default `/dev/spidev0.0`.
- `-s HZ`: the clock, default 1000000 (1 MHz): decimal, optionally with
  `k` (x1000) or `M` (x1000000), so `-s 400k` or `-s 1M`; 1 Hz to
  4294967295 Hz. Probing is a few bytes, so a slow clock costs nothing and
  survives long wires.
- `--json`: `spiflash id --json`'s output.
- `--opcodes`: the operation list, as `spiflash id --opcodes`.
- `--sfdp`: after the description, the chip's own SFDP basic parameter
  table as the chip answers it (or `sfdp=none`). Text only: `--json
  --sfdp` is a usage error.
- `id HEX`: no device; `HEX` is read as `spiflash id` reads it (`ef4018`,
  `0xEF4018`, `ef 40 18`, `ef:40:18`). `--method` is one of `jedec`,
  `rems`, `res1`, `res2`, `at25f`, `st95` (default `jedec`).
- `-h`, `--help`: the usage, on standard output.

What differs from `spiflash id`:

- No `-v`/`--verbose` (every upstream entry) and no `--type`: the tool's
  header has both chip types, and it prints every answer, as `spiflash id`
  does without `--type`.
- `--method` takes exactly spiflash's id families, `st95` included
  (spiflash accepts it too, though its `--help` lists only `rems`, `res1`,
  `res2` and `at25f`).
- In `id HEX`, only ASCII whitespace separates bytes; spiflash also takes
  Unicode whitespace (a no-break space, say), which the tool refuses.
- An id longer than 255 bytes is a usage error (`usf_lookup` takes up to
  255); spiflash looks it up.

Each transaction is one `SPI_IOC_MESSAGE(2)` with chip select held: the
command bytes, then the answer. The probe sends RES (`ab`, which also wakes
a chip from deep power-down), waits for it, then the read-id commands.

Exit codes:

| code | probing a device                                   | `id HEX`            |
|------|----------------------------------------------------|---------------------|
| 0    | a chip was found and described                     | found               |
| 1    | a chip answered but is not in the database; its id family and the bytes read are printed | not found (an empty line, as spiflash) |
| 2    | nothing answered (the bus reads all `00` or all `ff`), the device could not be opened or configured, or a usage error | a usage error (e.g. not a hex id) |

A usage error also prints the usage on standard error. Output that cannot
be written (a full disk, a closed standard output) is exit 2 too.

## Binding spidev to a flash chip

The chip must be on a spidev device. On a board whose device tree already
describes the flash, the kernel's `spi-nor` driver usually owns it; unbind
it first, then hand the device to `spidev` through `driver_override`. For
the device `spi0.0`:

```sh
cd /sys/bus/spi/devices/spi0.0
[ -e driver ] && echo spi0.0 > driver/unbind   # e.g. spi-nor
echo spidev > driver_override
echo spi0.0 > /sys/bus/spi/drivers/spidev/bind
ls /dev/spidev0.0
```

(`modprobe spidev` first if it is a module.) To give the chip back to
`spi-nor`, unbind it from `spidev`, write an empty line to
`driver_override`, and bind it to `spi-nor`.

On a Raspberry Pi, `dtparam=spi=on` in `config.txt` gives `/dev/spidev0.0`
and `/dev/spidev0.1` directly.
