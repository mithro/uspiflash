# The generated file

`uspiflash generate` writes one C header (`uspiflash.h` by default;
`--prefix` renames every `usf_`/`USF_` symbol). Include it wherever you
need the declarations; in exactly one C file, define `USF_IMPLEMENTATION`
before that include. This page is the reference for what that header
declares: every public function, struct and macro, the level or extra
that provides it, and worked examples. See [Usage](usage.md) for the
`generate` command itself and the [Levels](usage.md#levels) and
[Extras](usage.md#extras) tables.

Every guard below is `USF_HAVE_<FIELD>`, generated 1 or 0 for the field
that provides it (the template tests them with `#if`, so a header built
without a field simply has no such declaration to warn about).

## Types

| Type | Provided by | What it is |
|---|---|---|
| `usf_chip` | `id` | One answer: which entry (a chip id, or an extended-id variant of it) and the chip id it belongs to. Filled by `usf_lookup()` and `usf_probe()`; four bytes of RAM. |
| `usf_putc_fn` | `id` | A character sink: every string the library writes leaves through one of these, one character at a time, so no buffer is ever needed. |
| `usf_srcmask` | `id` | A source mask: bit `USF_SOURCE_*` set for each upstream that vouches (`usf_sources()`, `usf_op.sources`). `uint8_t` when the file has no `sources` field (below `full`) or every source its chips cite is among the first eight, else `uint16_t` (`USF_SRC_BYTES`). |
| `usf_op` | `read` (`USF_HAVE_OPERATIONS`) | One operation the chip supports and the transaction it is on the bus: `id`, `opcode`, `kind`, `protocol`, `address_bytes`, `dummy_clocks`, `data`, `data_bytes`, `sources`. |
| `usf_bus`, `usf_xfer_fn` | `id` (`USF_HAVE_PROBE`) | The transport. By default `struct usf_bus` is a function pointer (`usf_xfer_fn`) and a context pointer; when you define `USF_XFER` yourself, neither that definition nor `usf_xfer_fn` exists, and `struct usf_bus` is yours to define (see [Macros](#macros)). The `usf_bus` typedef (of `struct usf_bus`) always exists. |
| `usf_probe_result` | `id` (`USF_HAVE_PROBE`) | What `usf_probe()` found: which command answered (`family`), the raw bytes (`id[USF_RDID_LEN]`), and up to `USF_LOOKUP_MAX` looked-up `usf_chip` answers (`chip[]`, `count` of them). |
| `usf_sfdp` | `sfdp` extra (`USF_HAVE_SFDP`) | The chip's own SFDP (JESD216) Basic Flash Parameter Table, decoded as `spiflash.sfdp` decodes it: size, page size, revision, erase types and opcodes, fast-read modes, 4-byte addressing entry/exit ways, and more. |

## Functions

| Function | Provided by | What it does |
|---|---|---|
| `usf_lookup` | `id` | Looks up the bytes a chip answered to an id command of `family` (`USF_FAMILY_JEDEC` for `0x9F`, or a legacy family). Strips leading `0x7f` continuation codes; narrows by any bytes after the id (the extended id). Writes up to `USF_LOOKUP_MAX` answers (a NOR chip, then a NAND chip) to `out` and returns how many; 0 means unknown. Exactly what spiflash's `lookup(data, method=family)` returns. |
| `usf_family`, `usf_type`, `usf_bank` | `id` | The chip's id family (`USF_FAMILY_*`), type (`USF_TYPE_*`) and JEP106 bank (how many `0x7f` codes precede its manufacturer byte). |
| `usf_id` | `id` | Writes the chip's id bytes (without continuation codes) to `buf`, which must hold `USF_ID_MAX` bytes; returns how many. |
| `usf_size` | `read` | Size in bytes; 0 when unknown. |
| `usf_page_size` | `write` | Program page size in bytes; 0 when unknown. |
| `usf_sector_size` | `write` | Sector (usually 64 KiB erase block) size in bytes; 0 when unknown. |
| `usf_voltage` | `describe` | Supply range in millivolts; returns 0 (writing nothing) when unknown. |
| `usf_has_feature` | `read` | Whether any source claims `feature` (`USF_FEATURE_*`) for the chip; 0 for a number past the last feature. |
| `usf_op_count`, `usf_op_get`, `usf_op_find` | `read` (`operations`) | How many operations the chip has (spiflash's order: id, read, program, erase, register, mode); the i-th one; the operation with a given `USF_OP_*` id. Each returns 0 when there is no such operation. |
| `usf_op_name`, `usf_op_description` | `describe` (`descriptions`) | Write the name (e.g. `"READ_1_1_4"`) or the description of operation `op_id` (`USF_OP_*`); return 0 (writing nothing) if no chip in this file has it. |
| `usf_manufacturer` | `describe` | Writes the manufacturer's name; returns 0 (writing nothing) if unknown, 1 if a source names it, 2 if no source does and spiflash infers it from other chips with the same manufacturer byte and part names (the text output's `(inferred)`). |
| `usf_name_count`, `usf_name` | `describe` | How many part names the chip id has, most-cited first; and the i-th (returns 0 when out of range). |
| `usf_sources` | `full` | A `usf_srcmask`: bit `USF_SOURCE_*` set for each upstream describing the chip. |
| `usf_jep106` | `jep106` extra | Writes the JEP106 name of manufacturer byte `id` in `bank`; 0 if none. |
| `usf_print` | `describe` (`text`) | Prints what `spiflash id` (with `USF_PRINT_OPCODES`, `spiflash id --opcodes`) prints for `n` answers, byte for byte, less what this file was generated without: the `from:` line and each opcode's `[sources]` without `sources`, the `sources disagree` lines without `conflicts`, the `datasheet:` line without `datasheet`, and the `sfdp:` lines without `sfdp_summary`. |
| `usf_print_json` | `full` (`json`) | Prints what `spiflash id --json` prints, byte for byte, less what this file was generated without: `"datasheets"` without `datasheets`, `"records"` without `records`, each record's `"at"` without `provenance`, and `"sfdp"` without `sfdp_dumps`. |
| `usf_probe` | `id` (`probe`) | Identifies the chip; returns `r->count`. Sends only id commands (RES, RDID, REMS, AT25F RDID, M95 RDID), and only those some chip in this file answers, so it cannot change the chip. |
| `usf_sfdp_read` | `sfdp` extra | Reads the chip's SFDP header, parameter headers and BFPT into `out` and returns 1; returns 0 (`out` untouched) when there is no `"SFDP"` signature or no BFPT. Sends only RDSFDP (`0x5A`), so it cannot change the chip. Call it after `usf_probe()`, whose RES wakes the chip. |

## Macros

| Macro | Provided by | What it is |
|---|---|---|
| `USF_ROM` | every level | Where the tables live; empty by default. Define it as `__code` for SDCC on the 8051, or as a flash address space (avr-gcc's `__flash`) on AVR, before plain `const` data would otherwise be copied to RAM at startup. |
| `USF_ID_MAX` | every level | The longest id `usf_id()` writes (after `0x7f` continuation codes). |
| `USF_PRINT_OPCODES` | `describe` (`text`) | A flag to `usf_print()`: also list the operations, as `spiflash id --opcodes`. |
| `USF_XFER(bus, tx, txlen, rx, rxlen)` | `id` (`probe`) | How the library talks to the chip: send `txlen` bytes, then clock in `rxlen` bytes, chip select held for the whole transaction. Define it yourself to inline your own SPI driver (see [Example: a custom transport](#example-a-custom-transport)); otherwise the library defines it in terms of a `usf_bus` holding a `usf_xfer_fn`. |
| `USF_DELAY_US(us)` | `id` (`probe`) | The probe's delay hook: after RES (`0xAB`, which wakes a chip from deep power-down), it calls `USF_DELAY_US(30)` and waits for the chip's tRES1. Left undefined, it does nothing (`((void)0)`); define it as your delay, or make the transport itself allow 30 us after the first transaction. |
| `USF_SFDP_DTR` | `sfdp` extra | A `usf_sfdp.flags` bit: DTR (double transfer rate) clocking (BFPT DW1[19]). |
| `USF_SFDP_READ_1_1_2`, `_1_2_2`, `_1_1_4`, `_1_4_4`, `_2_2_2`, `_4_4_4` | `sfdp` extra | The BFPT's fast-read modes, in `usf_sfdp` order: bits of `reads`, and indices of `read_opcode`/`read_clocks`. |

Whatever you define (`USF_XFER`, `USF_DELAY_US`, `USF_ROM`, `USF_NO_STDINT`)
must be the same in every file that includes this one.

Beyond these, the header's provenance comment (`@@CONFIG@@` in the
template) generates one `USF_HAVE_<FIELD>` per field in the
[Levels](usage.md#levels) and [Extras](usage.md#extras) tables, the
table sizes and row counts, and a name for every family, type, feature,
source, operation kind, protocol and operation the selected chips use
(`USF_FAMILY_*`, `USF_TYPE_*`, `USF_FEATURE_*`, `USF_SOURCE_*`,
`USF_KIND_*`, `USF_PROTO_*`, `USF_OP_*`). Which of these exist, and how
many, depends on the selection (`--level`, `--with`/`--without`, the chip
filters): they are not fixed macros to enumerate here. Their values can
change between spiflash versions (a new source or operation renumbers the
ones after it: spiflash 0.0.post173 moved `USF_SOURCE_OPENOCD` from 4 to
6, 0.0.post182 to 7), so use the names, and regenerate every file a
program includes together.

## Example: probing with a function-pointer bus

The default transport is a function pointer (`usf_xfer_fn`) wrapped in a
`usf_bus`:

```c {.compile}
#include "uspiflash.h"

/* Your SPI driver, wired through usf_xfer_fn. Real code drives chip
 * select and clocks tx out / rx in over SPI. */
static void my_xfer(void *ctx, const uint8_t *tx, uint8_t txlen, uint8_t *rx, uint8_t rxlen)
{
    (void)ctx;
    (void)tx;
    (void)txlen;
    (void)rx;
    (void)rxlen;
}

void probe_flash(void)
{
    usf_bus bus = { my_xfer, 0 };
    usf_probe_result r;

    if (usf_probe(&bus, &r) > 0) {
        uint32_t size = usf_size(&r.chip[0]);
        (void)size;
    }
}
```

## Example: a custom transport

Define `USF_XFER` (and, if you need one, `USF_DELAY_US`) before including
the header, and `usf_bus` is yours to shape:

```c {.compile}
#include <stdint.h>

struct usf_bus {
    int cs_gpio;
};

extern void my_xfer(struct usf_bus *bus, const uint8_t *tx, uint8_t txlen,
                     uint8_t *rx, uint8_t rxlen);
extern void my_delay_us(unsigned us);

#define USF_XFER(bus, tx, txlen, rx, rxlen) my_xfer((bus), (tx), (txlen), (rx), (rxlen))
#define USF_DELAY_US(us) my_delay_us(us)

#include "uspiflash.h"

void probe_with_custom_bus(struct usf_bus *bus)
{
    usf_probe_result r;
    (void)usf_probe(bus, &r);
}
```

## Example: printing

`usf_print` and `usf_print_json` write through a `usf_putc_fn` sink, one
character at a time, so no buffer is ever needed:

```c {.compile}
#include <stdio.h>
#include "uspiflash.h"

static void putc_stdout(void *ctx, char ch)
{
    (void)ctx;
    (void)putchar((unsigned char)ch);
}

void print_chips(const usf_chip *chips, uint8_t n)
{
    usf_print(chips, n, USF_PRINT_OPCODES, putc_stdout, 0);
#if USF_HAVE_JSON
    usf_print_json(chips, n, putc_stdout, 0);
#endif
}
```

## SDCC and CPUs without a multiplier

The generated file builds with SDCC (`--std-c99 --Werror`) on the 8051,
68HC08/S08, STM8, Z80 and 6502 ports, and with GCC and clang on CPUs that
have no multiply instruction or barrel shifter. On every CPU and compiler
in the size matrix it calls no arithmetic helper and no C library
function: no multiply, divide or shift routine, no `memcpy`, no
jump-table dispatcher. The matrix checks this, and
[its README](https://github.com/mithro/uspiflash/blob/main/sizes/matrix/README.md)
lists the only symbols a port may still need: its calling-convention
runtime.

- **Callbacks on SDCC's non-reentrant ports** (8051, 68HC08/S08, 6502,
  Padauk) must be declared reentrant. Write `USF_REENTRANT` after the
  parameter list:

  ```c
  static void my_putc(void *ctx, char ch) USF_REENTRANT { /* ... */ }
  ```

  It is `__reentrant` there and empty everywhere else.
- **Tables in program memory on the 8051:** define `USF_ROM` as `__code`.
- **Memory model on the 8051:** the default (small) model keeps each
  function's locals in the 128 bytes of internal RAM. A whole program with
  the text printer does not fit there, so use `--model-large`.
- **`USF_SOFT_MUL` and `USF_SOFT_SHIFT`** are set automatically:
  - where a multiply by a table's row size would call a helper, table row
    offsets are computed by shift and add: on rv32i/rv32e without M,
    msp430, and SDCC's 8051, 68HC08/S08, 6502, Padauk, STM8 and f8 ports.
    The STM8 and the f8 have a multiplier, but SDCC calls its `_mulint`
    helper for some row sizes there. SDCC's Z80-family ports multiply
    inline, and shift and add would be larger;
  - on msp430 and SDCC, sizes are printed without a shift by a variable
    count: msp430 calls a helper for one, and SDCC's inline shift loop is
    larger.

  Define either as 0 or 1 to override. The generated file behaves
  identically either way (the tests run both).
- **What an SDCC port still links:** its own calling-convention runtime,
  such as the 8051's generic-pointer routines (`__gptrget`). The size
  matrix lists them per port (`sizes/matrix/README.md`).
