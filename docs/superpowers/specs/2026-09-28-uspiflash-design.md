# uspiflash — design

Date: 2026-09-28. Status: draft for review.

## 1. What this is

`uspiflash` is a Python tool that reads the
[spiflash](https://github.com/mithro/spiflash) database and writes a **single C
file** that, on a device, detects which SPI flash chip is attached and reports
what it can do. The generated file is meant to be committed into other
projects (Zephyr, MicroPython, the LiteX BIOS, bare-metal firmware, Linux
tools), so it carries its own provenance and regeneration instructions.

The one optimisation target is **bytes on the device**: code and data,
flash and SRAM, counted together. Decode speed is recorded but never traded
against size: detection happens rarely, at human timescales.

### Goals

1. Carry *everything* spiflash knows (at the `full` detail level), in the
   fewest device bytes, with smaller presets and database subsets for tighter
   parts.
2. Build warning-free (`-Wall -Wextra -Wpedantic -Werror`) with every
   supported GCC, LLVM and SDCC version, need no libc functions, and never
   allocate memory.
3. Generate specialised output per CPU architecture and compiler, chosen by
   measurement, and prove every specialisation behaves identically to the
   portable one.
4. Record every size measurement and experiment so that any of it can be
   rerun and rechecked later, by anyone.
5. Demonstrate it in Zephyr (Renode), MicroPython (Renode), a custom LiteX
   BIOS (fpgas.online: Arty A7, TT FPGA demo board, Fomu) and a static Linux
   spidev tool (QEMU and a fpgas.online Raspberry Pi).

### Non-goals

- Reading, programming or erasing flash contents. The library only issues the
  commands needed to identify a chip (and, with SFDP enabled, to read its
  SFDP tables). It *reports* the read/program/erase commands a driver needs.
- MSVC / Windows.
- Building toolchains in the normal development flow (see §7.2).
- 8051/8052 optimisation (Phase 2, §11). SDCC builds for mcs51 are compiled
  and tested from the start so the portable core stays 8051-clean.

## 2. Decisions (from the question round, 2026-09-28)

| Topic | Decision |
|---|---|
| Name | `uspiflash`: repo `mithro/uspiflash`, PyPI `uspiflash`, module `uspiflash`, CLI `uspiflash`. The MicroPython module is also `uspiflash`. |
| Output file / C prefix | Chosen on the generator command line; defaults `uspiflash.h`, `usf_` / `USF_`. |
| Licences | Tool: Apache-2.0. Generated C file: Apache-2.0. |
| Detail levels | Presets (`read`, `write`, `full`, …) plus database subsetting; main effort goes into making `full` small, strings especially. |
| SFDP | Optional module in the output; a core part of the generator and its tests. |
| Objective | Size only (code + data, flash + SRAM). Instruction counts recorded, never optimised for. |
| Toolchains | Prebuilt only: existing Docker images and release tarballs. Separate, optional tooling may build and publish images to ghcr.io. |
| WCH | WCH's MounRiver GCC forks included, labelled "vendor fork". |
| LiteX hard CPUs | Size tracking only. |
| Zephyr | Module + sample + runtime-configured flash driver, in Renode. |
| MicroPython | `USER_C_MODULE` and a dynamic native `.mpy`, in Renode. |
| LiteX | Custom BIOS in this repo; Arty A7, TT FPGA demo board and a real Fomu, all on fpgas.online. Flash writes allowed. |
| Linux tool | QEMU (m25p80) in CI and a real fpgas.online Pi. |
| Debian | `python3-uspiflash` (all) and `uspiflash-linux` (the tool, per architecture; dynamically linked in the .deb: amendment 13). |
| Process | Worktrees under `.worktrees/`, small commits, a PR per milestone, self-merge after green CI and a subagent review; up to 2 subagents at a time. PRs to `mithro/spiflash` allowed when the C side needs data. |
| Sandboxing | Every heavy job runs in a resource-limited scope whose limits are set from the machine's current load (§7.5). |

## 3. The data, measured

From spiflash at commit `0556ad6` (2026-09-27), computed by a throwaway
script, recomputed and recorded properly as the first experiment in M1:

| Quantity | Value |
|---|---|
| Chip ids (`Flash` objects) | 778 (651 NOR, 127 NAND) |
| Id families | JEDEC 751, RES2 12, REMS 6, RES1 4, AT25F 4, ST95 1 |
| Id lengths (bytes, after continuation codes) | 3: 660, 2: 110, 1: 5, 5: 3 |
| JEP106 banks used | 0: 727, 1: 26, 6: 24, 7: 1 |
| Manufacturers | 37 (224 bytes of names) |
| Part names | 1,202 (11,238 bytes; 3,584 bytes zlib -9), up to 19 per id |
| Part-name alphabet | 40 characters: `)-.0-9A-Z_` |
| Distinct opcode sets / with source attribution | 215 / 314 (of 58 operations used) |
| Distinct feature sets | 126 |
| Distinct (size, page, sector, voltage) tuples | 163 |
| Ids whose sources conflict | 60 |
| Ids with extended-id variants | 21 (67 records) |

Almost every per-chip attribute is drawn from a small set of distinct values,
so the baseline encoding (§5.4) stores per-chip indices into small
deduplicated tables, and the research effort goes into the strings.

## 4. Architecture

```
spiflash (PyPI)  ──►  uspiflash.model    snapshot of the database as plain,
                                          immutable Python values (the "IR")
                        │
                        ▼
                      uspiflash.select   detail level + chip filters → the
                                          fields and chips that will be emitted
                        │
                        ▼
                      uspiflash.codecs   each codec = Python encoder + the C
                                          decoder it needs (tables, strings,
                                          bitfields, id search)
                        │
                        ▼
                      uspiflash.targets  Target class hierarchy: picks codecs
                                          and C idioms per architecture/compiler
                        │
                        ▼
                      uspiflash.emit     renders the single C file from
                                          templates, with provenance header
```

Beside the generator:

- `uspiflash.measure`: compiles a generated file with a given toolchain and
  target and returns section sizes, the linked-image difference, symbol
  sizes, stack use, and which libgcc/compiler-rt helpers were pulled in.
- `uspiflash.sim`: runs a test harness under an instruction-set simulator
  and returns its output and instruction count.
- `uspiflash.oracle`: the expected output for any id or bus transcript,
  computed with the Python spiflash package.

### 4.1 Approaches considered

1. **A fixed hand-written C file with `#if` switches, and Python emitting only
   data tables.** Simple, but every specialisation becomes more preprocessor
   branches in one file, and the data layout cannot change per target.
2. **Python emitting all code, e.g. lookup compiled to a decision tree of
   `if`/`switch`.** Code-as-data can win on some ISAs, but it is hard to review
   and hard to prove equivalent, and it bloats on others.
3. **Chosen: a template core plus pluggable codecs, specialised by a `Target`
   class hierarchy.** The core C (probe sequence, API, printer) is a readable
   template. Each data structure is produced by a *codec*: a Python encoder
   paired with its C decoder fragment. A `Target` subclass chooses codecs and
   idioms (integer widths, `__code` placement, how to avoid a multiply) for
   its architecture and compiler. Approach 2 survives as one more codec (a
   decision-tree id search) and is kept only where it measures smaller.

### 4.2 The `Target` hierarchy

```
Target                      portable C99; the reference every other target
 │                          is tested against
 ├── Target32               32-bit load/store CPUs: word-aligned tables
 │    ├── ArmThumb          Thumb-1 limits (M0/M0+/M23): no wide immediates
 │    │    └── ArmThumb2    M3/M4/M7/M33/M55/M85
 │    ├── RiscV32           rv32i/e with or without C/M/Zc*
 │    │    └── WchRiscV     rv32ec/rv32imac + XW with MounRiver GCC
 │    ├── OpenRisc          or1k, big-endian
 │    └── PowerPC64         microwatt (ppc64le)
 ├── Target64Host           Linux hosts (x86-64, aarch64, riscv64)
 └── Target8                8-bit: byte-wide everything
      └── Mcs51Sdcc         Phase 2
```

A target decides:

- which codec each structure gets
- integer types and loop idioms
- whether to avoid `*`, `/` and `%` (no hardware divide on rv32e, rv32i or M0)
- qualifiers such as SDCC's `__code`
- alignment

The choice for each target and compiler is **data, not code**: a table of
measured winners shipped with the package (`uspiflash/targets/best.toml`),
regenerated by `uspiflash research select`. Generating output never needs a
compiler installed. `--search` compiles every candidate with the local
toolchain and picks the smallest.

### 4.3 Detail levels and subsets

A detail level is a named set of *fields*; the command line can add or remove
single fields (`--level write --with voltage --without names`).

| Level | Contents (cumulative) |
|---|---|
| `id` | probe; identify the chip; manufacturer and chip index only |
| `read` | + size, 3/4-byte addressing, the fastest read of each width (opcode, protocol, address bytes, dummy clocks), NOR/NAND |
| `write` | + page size, every eraser with its block layout, program opcodes, write-enable/status/register operations, lock/OTP/no-erase flags |
| `describe` | + part names, manufacturer names, voltage, all features, all operations, and the text printer |
| `full` (default) | everything `spiflash id --opcodes --json` prints: + per-feature and per-operation source attribution, conflicting values, the source list, operation descriptions, extended-id narrowing |

Opt-in extras beyond `full`:

- `jep106-all`: every manufacturer name, not just those with flash chips
- `provenance`: upstream file and line, flags, notes

Subsets filter chips before encoding:

- `--manufacturer`
- `--id` (an explicit list, e.g. the chips on one board)
- `--type nor|nand` (default `nor`: amendment 12), `--family jedec`,
  `--min-size` / `--max-size`

A subset only shrinks the tables; the code shrinks when a level drops fields.

## 5. The generated C file

### 5.1 Shape

A single stb-style header, C99 restricted to what SDCC accepts, usable from
C++ (`extern "C"`):

```c
#include "uspiflash.h"             /* declarations only */

#define USF_IMPLEMENTATION         /* in exactly one .c file */
#include "uspiflash.h"
```

It begins with a comment block (§5.5) and has extensive inline
documentation: every public symbol, the encoding of every table, and why each
unusual idiom is there (with a link to the experiment that justified it).

Dependencies:

- **No libc functions** at all. The headers `<stdint.h>` and `<stddef.h>`
  are optional (they are freestanding headers; SDCC and very early boot code
  can define `USF_NO_STDINT` and supply the types).
- **No memory allocation, no writable static state.** All tables are `const`
  and live in flash (or `__code` on 8051). SRAM use is the caller's result
  struct plus stack. Peak stack is measured and published per target.
- **No compiler-generated calls.** Tests link with `-nostdlib` so that a
  compiler-generated `memcpy`, `memset` or `__udivsi3` fails the build rather
  than silently adding bytes.

### 5.2 API (sketch; names use the default prefix)

```c
/* Transport: the one thing a port must provide. Either define the macro
 * (zero overhead, inlined by the compiler) or leave it undefined and pass
 * a function pointer in usf_bus. */
#define USF_XFER(bus, tx, txlen, rx, rxlen)  my_spi_xfer(...)

typedef struct usf_chip usf_chip;   /* small; the caller owns it */

int  usf_probe(usf_bus *bus, usf_chip *out);           /* talk to the chip */
int  usf_lookup(const uint8_t *id, uint8_t len,
                usf_chip *out);                        /* id bytes → chip */
/* Accessors decode on demand from ROM; nothing is copied to RAM. */
uint32_t usf_size(const usf_chip *c);
uint16_t usf_page_size(const usf_chip *c);
int      usf_supports(const usf_chip *c, uint8_t op);  /* USF_OP_READ_1_1_4 */
int      usf_op(const usf_chip *c, uint8_t op, usf_op_info *out);
int      usf_eraser(const usf_chip *c, uint8_t i, usf_eraser_info *out);
void     usf_name(const usf_chip *c, uint8_t i,
                  void (*putc)(void *ctx, char ch), void *ctx);
/* `describe` and above: */
void     usf_print(const usf_chip *c, void (*putc)(void *, char), void *ctx);
void     usf_print_json(const usf_chip *c, void (*putc)(void *, char), void *ctx);
/* SFDP module (--with sfdp; USF_HAVE_SFDP is 1): */
uint8_t  usf_sfdp_read(usf_bus *bus, usf_sfdp *out);   /* --with sfdp */
```

Strings are *streamed* through a putc callback rather than copied into
buffers, so neither side needs a RAM buffer and packed strings can be
decoded one character at a time. The exact API is settled in M1 by writing
the Linux tool and the Zephyr driver against it (the two most demanding
users).

### 5.3 Probe sequence

The order is designed so that no step can change a chip's contents:

1. RES (`0xAB`): wakes a chip from deep power-down. Its response byte is kept
   as the legacy RES1 signature.
2. RDID (`0x9F`): reads up to 6 bytes, skips `0x7F` JEP106 continuation codes
   (counting the bank), and keeps extra bytes for extended-id narrowing.
3. If the RDID answer is all `0x00` or all `0xFF`: SPI NAND read-id (`0x9F`
   plus one dummy byte), then REMS (`0x90` + 3 address bytes), then RES2
   (`0xAB` with 3 dummy bytes, 2 bytes back), then AT25F (`0x15`) and ST95
   signatures.
4. The id is looked up in the family the command belongs to.
5. With SFDP enabled and requested, the SFDP header and the Basic Flash
   Parameter Table are read and merged (§5.6).

Every step is a transcript of bytes on the bus. The test harness replays
recorded and synthesised transcripts (§6.1).

### 5.4 Encoding (baseline, then research)

The baseline is chosen for obvious correctness; each later change must beat
it on the size ledger with an experiment write-up.

- **Id search:** one table per id family, sorted by (bank, id bytes) and
  searched linearly. Linear search is smaller code than binary search, and
  speed is not a target. Ids of different lengths are stored in separate
  tables so no length byte is needed per entry.
- **Per-chip record:** fixed-width indices into deduplicated tables:
  geometry (163), opcode set (215; 314 with attribution), feature set (126),
  manufacturer (37), name list. Index widths are computed from the table
  sizes and bit-packed only where a measurement shows the unpacking code
  costs less than the bytes saved.
- **Operation table:** the 58 operations in use, each as opcode, packed
  protocol, address bytes, dummy clocks, data direction, kind, and a
  description string reference.
- **Strings:**
  - baseline: NUL-separated ASCII
  - research: 6-bit packing of the 40-character alphabet; front coding within
    an id's name list (`W25Q128`, `W25Q128FV`, `W25Q128JV`) and across the
    sorted list; manufacturer-prefix stripping; a small shared-substring
    dictionary; and a tiny LZ77 variant whose decoder must be measured in
    bytes (zlib's 3,584-byte result is the reference to beat, decoder
    included)
- **Printer:** number formatting avoids division (repeated subtraction by a
  table of powers of ten), so no `__udivsi3` is linked on CPUs without a
  hardware divide.

### 5.5 Provenance header

Every generated file starts with a comment giving:

- uspiflash version and git description
- spiflash version, data format and each upstream's commit (`spiflash.sources()`)
- the full generator command line and the resolved configuration (level,
  fields, subset, target, compiler hint, prefix, codecs chosen), plus a hash
  of that configuration
- the exact regeneration command, e.g.
  `uvx --from 'uspiflash==X.Y' --with 'spiflash==A.B' uspiflash generate …`,
  and how to check a committed copy (`uspiflash check uspiflash.h`)
- the licence and the data provenance notice (from spiflash's
  `debian/copyright`)
- expected sizes for the reference targets

There are **no wall-clock timestamps**: the same inputs give byte-identical
output (checked in CI).

### 5.6 SFDP

The generator side is core:

- JESD216 parameter decoding, from `spiflash.sfdp`
- a comparison of BFPT fields with the same fields the database provides
  (the SFDP-versus-database experiment, amendment 11); no runtime mapping
  from one to the other is implemented (deferred)
- tests that the C decoder agrees with `spiflash.sfdp` on every shipped dump

Since the M1 part D replan, the Python side is spiflash's own
(`spiflash.sfdp`, amendment 9): uspiflash writes no JESD216 parser of its
own and fetches no fixtures of its own. spiflash's shipped SFDP dumps are
the fixtures.

The C side is optional (`--with sfdp`, which sets `USF_HAVE_SFDP`) and has
its own size ledger entries.
Fixtures currently come from QEMU's m25p80 SFDP tables (spiflash's 12
dumps, amendment 9); real chips on fpgas.online and published datasheet
tables may add more later, as spiflash data through PRs to
`mithro/spiflash`, each recorded with its origin.

## 6. Verification

### 6.1 Test oracle

For every id in the database (and every extended-id variant) the expected
answer comes from the Python spiflash package:

- `usf_print` must match `spiflash id <id> --opcodes` byte for byte
- `usf_print_json` must parse to the same object as `spiflash id <id>
  --opcodes --json`

This holds for each detail level: lower levels compare against the oracle
restricted to their fields. Transcript tests cover the probe sequence: a
fake bus answers like a given chip (including legacy-only, NAND, continuation
codes, silent bus and stuck-at-0xFF bus).

### 6.2 Layers

| Layer | What runs | Where |
|---|---|---|
| Python unit tests | encoders round-trip, level selection, provenance, determinism | pytest |
| Host C tests | the generated file compiled natively with gcc and clang, all ids + random non-ids + transcripts, under ASan/UBSan | pytest drives the compiler |
| Compiler matrix | every (compiler version × target × level × codec set): must build warning-free and link with `-nostdlib` | Docker images, CI |
| Simulator equivalence | the same test vectors run on the target ISA; the output must be byte-identical to the portable reference built for the host | Unicorn (ARM, RISC-V, PPC), QEMU user mode (or1k, ppc64le), ucsim (8051) |
| libc matrix | the example programs built against glibc, musl, uclibc-ng, dietlibc, picolibc, newlib, newlib-nano, Zephyr's libcs, LLVM-libc, the LiteX BIOS libc, SDCC's libc and MicroPython's | Docker images, CI |
| Demos | Zephyr and MicroPython in Renode; Linux tool in QEMU; LiteX on fpgas.online | CI (Renode, QEMU); hardware jobs run from this machine |

Simulator runs use every id in the database; random non-ids are sampled
(with a fixed, recorded seed) because full 24-bit sweeps are only affordable
natively.

## 7. Measurement and research

### 7.1 What is measured

For each (generated file, target, compiler, flags):

- flash: `.text` + `.rodata` + `.data` initialisers
- SRAM: `.data` + `.bss` + peak stack (from `-fstack-usage` where available,
  and from the simulator's lowest stack pointer)
- **the linked-image difference**: a minimal program that calls the API,
  linked with and without the library. This counts libgcc/compiler-rt
  helpers, literal pools and alignment padding that per-object sizes miss.
- per-symbol sizes, and the list of helper functions pulled in
- instruction count for lookup and print (recorded, not optimised)

### 7.2 Toolchains

Only prebuilt toolchains are used:

- existing Docker images where they exist (distribution GCC/LLVM across
  Debian, Ubuntu and Alpine releases; the Zephyr SDK image; SDCC)
- sha256-pinned release tarballs (xPack arm-none-eabi and riscv-none-elf, the
  Arm GNU Toolchain, LLVM releases, WCH's MounRiver GCC, or1k and ppc64le
  cross compilers)

`tools/images/` holds optional scripts that assemble images containing these
and publish them to `ghcr.io/mithro/uspiflash-*`; they are not part of the
normal flow.

The toolchain inventory (`toolchains.toml`) records, for each entry: name,
version, source URL or image digest, hash, targets it can build, and a
"vendor fork" flag. Target CPU flags are enumerated from primary sources (GCC
and LLVM `-mcpu` lists, `litex/soc/cores/cpu` at a pinned LiteX commit) and
recorded with that commit.

### 7.3 The size ledger

`sizes/` holds one JSON-lines file per (target, compiler) with a row per
measured commit: uspiflash commit, spiflash version, level, codec set, the
numbers in §7.1, and the toolchain identity. CI checks each PR's changes
against `main`, posts a size-difference comment on the PR (in this repo
only), and fails when the default configuration grows without a matching
ledger update. The docs render the ledger as tables and charts.

### 7.4 Experiments

Each experiment is a directory `experiments/YYYY-MM-DD-<slug>/` containing:

- `README.md`: question, hypothesis, method, result, conclusion, and what
  changed in the code because of it
- `run.py`: reproduces it with one command (`uv run uspiflash research run
  <slug>`), with pinned inputs
- `results/`: raw JSON, including toolchain identity, host, spiflash version
  and random seeds

The docs include every experiment. `uspiflash research rerun --all` reruns
them and reports which conclusions no longer hold (because of new chips,
new compilers or new codecs).

### 7.5 Sandboxing

Every compiler, simulator, Renode, QEMU and Docker job goes through one
runner (`uspiflash.sandbox`):

- **Local runs:** `systemd-run --user --scope` with `MemoryMax`,
  `MemorySwapMax=0`, `CPUQuota`, `TasksMax` and `nice`, plus a per-job
  timeout. Docker jobs get `--memory`, `--cpus` and `--pids-limit`.
- **Dynamic limits:** before each batch the runner reads `/proc/loadavg`,
  `/proc/meminfo` (MemAvailable) and `/proc/pressure/*`. It sizes the batch's
  memory limit and parallelism to the currently free headroom (leaving a
  fixed reserve for the desktop) and backs off when pressure stall
  information rises.
- **Pytest workers:** the same calculation sets the `pytest-xdist` worker
  count.
- **CI:** the same runner is used, with the runner machine's limits.

## 8. Demonstrations

- **Linux tool** (`examples/linux/`): a static C program for `/dev/spidevX.Y`
  (`SPI_IOC_MESSAGE`). Its output matches `spiflash id --opcodes` (and
  `--json`). Built against glibc and musl for amd64, arm64, armhf and
  riscv64. Tested in QEMU (a small Linux image with the m25p80 model behind
  a spidev node) and on a fpgas.online Raspberry Pi wired to an FPGA board's
  configuration flash. Packaged as `uspiflash-linux`, dynamically linked
  (amendment 13).
- **Zephyr** (`zephyr/`, a Zephyr module):
  - a sample that probes and prints
  - a flash driver (`uspiflash,spi-nor`) that configures size, page size,
    erase types and read mode at runtime from the probe result
  - tests on `litex_vexriscv` and one ARM board in Renode, against a new
    Renode SPI-flash peripheral model (`renode/`) that answers as any chip in
    the database
  - built against the latest Zephyr release and 3.7 LTS
- **MicroPython** (`micropython/`): the same `uspiflash` module built both as
  a `USER_C_MODULE` and as a dynamic native `.mpy`. Its API mirrors spiflash:
  `lookup(id)` returns an object with `.manufacturer`, `.names`, `.size`,
  `.page_size`, `.features`, `.opcodes`…, and `probe(spi, cs)` reads a real
  chip. Tested in Renode on an STM32 board with the Renode flash model.
- **LiteX BIOS** (`examples/litex/`): LiteX SoCs for the Arty A7, TT FPGA
  demo board and Fomu, whose BIOS adds a `spiflash` command printing the
  same output. Built with open toolchains (openXC7 for the Arty,
  yosys/nextpnr-ice40 for the iCE40UP5K) and run on fpgas.online hardware.
  The BIOS size difference is recorded in the ledger. The existing
  `fpgas.online-test-designs/designs/spi-flash-id` is reference material.

## 9. Python tool

- Python ≥ 3.11, `uv`-managed, hatch-vcs rolling versions (as spiflash).
- **Required dependency:** only `spiflash`. Optional extras enable more:
  - `uspiflash[measure]`: (no extra: amendment 14)
  - `uspiflash[sim]`: `unicorn`
  - `uspiflash[docs]`
  - `uspiflash[research]`: plotting
- `ruff` (spiflash's rule set) and `mypy --strict` clean, with no
  suppressions. Docstrings on every public module, class and function.
- CLI: `uspiflash generate`, `check`, `measure`, `sim`, `research run`,
  `research rerun`, `research select`, `toolchains list`.

## 10. Packaging, CI, docs

Mirrors spiflash, adapted:

- `.github/workflows/deb.yml` runs the gates (lint, types, tests, host C
  tests, a small compiler matrix), then builds `python3-uspiflash` and
  `uspiflash-linux` for bookworm, trixie, forky and sid with
  `mithro/apt-repo-action`, and publishes the signed apt repository to
  GitHub Pages (`https://mith.ro/uspiflash/`).
- `publish-pypi.yml` uploads to PyPI when that succeeds on `main` (trusted
  publishing).
- `matrix.yml` runs the full compiler/libc/simulator matrix nightly and on
  PRs that touch C or codecs, and updates the ledger.
- `renode.yml` runs the Zephyr and MicroPython demos.
- Docs: Sphinx, furo and MyST on Read the Docs. Pages cover the user guide,
  generated-file reference, per-target size tables and charts, every
  experiment, the toolchain inventory, and the Python API.
- Tim-only setup (listed in `RELEASING.md`): the PyPI pending publisher, the
  Read the Docs project import, and "Include Git LFS objects in archives". I
  create the apt signing key and set its secret myself.

## 11. Milestones

Each is one or more PRs of small commits, reviewed by a subagent before
merging.

1. **M1: core.** Python scaffolding, packaging, CI and docs skeleton; the
   IR and levels; baseline codecs; the portable template; the oracle; host C
   tests; SFDP decoder (Python and C); the Linux tool (QEMU test); the first
   experiment (§3 statistics).
2. **M2: measurement.** Sandbox runner; toolchain inventory and images;
   `measure`; the ledger; the compiler and libc matrix in CI.
3. **M3: simulators.** Unicorn, QEMU user mode and ucsim harnesses; the
   equivalence tests.
4. **M4: specialisation.** Target subclasses; string and table codec
   research; `best.toml`; experiments write-ups.
5. **M5: Zephyr** in Renode, with the Renode flash model.
6. **M6: MicroPython** in Renode.
7. **M7: LiteX BIOS** on fpgas.online; Linux tool on a real Pi.
8. **M8: docs polish** and release setup completed.
9. **Phase 2: 8051/8052.** A short question round first (which cores: WCH
   CH55x, Nuvoton N76E003, FPGA soft cores; memory model), then an
   `Mcs51Sdcc` target.

## 12. Risks

- **Parts sharing an id differ** (a W25Q128BV has no QPI, an FV does). The C
  side reports what the database reports (the union, with attribution at
  `full`), and the docs say so.
- **Byte-exact output parity** couples the printer to spiflash's CLI format.
  The oracle pins a spiflash version; format changes in spiflash become
  deliberate updates here.
- **WCH vendor compilers** may not have complete source or stable download
  URLs; they are pinned by hash and marked as vendor forks, and nothing
  depends on them.
- **Renode flash models**: if Renode's existing SPI flash models cannot be
  configured to answer as any chip in the database (checked at the start of
  M5), M5 writes one. It may be useful upstream later (only with Tim's
  approval).
- **fpgas.online availability**: hardware jobs are not a merge gate; their
  results are recorded with the date and board serial.

## 13. Amendments (M1 plan, 2026-09-28)

1. **`records` and `provenance` extras.**
   - `spiflash id --json` includes every upstream record (source, raw name,
     ext_id, `at`). The raw names alone are 19,329 bytes, more than every
     other string together.
   - So `full` covers everything the **text** output shows, plus the JSON
     *minus* `records`.
   - The extra `records` adds `records[]` without `at`; the extra
     `provenance` adds `at`.
   - JSON parity tests delete what the level leaves out from the oracle's
     JSON.
2. **Erasers with block layouts** are per-record data. spiflash's `Flash`
   exposes no consensus for them, so `write` gets erase *operations* (with
   `sector_size`), and eraser layouts wait for a spiflash change (a PR to
   `mithro/spiflash`, M4 or later).
3. **Stable operation ids.**
   - `USF_OP_<NAME>` is the operation's index in spiflash's full operation
     list (sorted by `spiflash.opcodes.sort_key`).
   - Ids therefore do not change when a subset drops an operation.
   - The generated table stores only the operations it needs, each with its
     stable id.
4. **`usf_lookup` returns up to two chips** (one NOR, one NAND), because
   spiflash's `lookup` does.
5. **The probe reads these exact transactions**, derived from spiflash's
   operation table (`RES` `0xAB`, 24 dummy clocks; `RDID_ATMEL` `0x15`;
   `RDID_M95` `0x83` with 2 address bytes and 3 data bytes; `REMS` `0x90`
   with 3 address bytes):

   | Step | TX | RX bytes | Family looked up |
   |---|---|---|---|
   | RES | `ab 00 00 00` | 2 | RES2 (2 bytes), RES1 (first byte) — after the JEDEC steps fail |
   | RDID | `9f` | `USF_RDID_LEN` | JEDEC |
   | NAND RDID | `9f 00` | `USF_RDID_LEN - 1` | JEDEC |
   | REMS | `90 00 00 00` | 2 | REMS |
   | AT25F | `15` | 2 | AT25F |
   | M95 | `83 00 00` | 3 | ST95 |

   `USF_RDID_LEN` is generated: the longest (continuation codes + id +
   extended id) over the selected chips, and at least 6. At spiflash
   0.0.post36 it is 10 (checked 2026-09-28): the ATXP032 sits in JEP106
   bank 7, so it sends seven `0x7f` codes before its 3-byte id `43a700`. A
   fixed 6-byte read could never identify it.

6. **Strings must be printable ASCII without `"` or `\`.** The generator
   checks this and refuses otherwise, so the C JSON writer needs no escaping.
   Every chip, record and operation string in spiflash 0.0.post36 passes.
   The one exception is datasheet titles and revisions (decision 7). They
   appear only in JSON, so they are stored already JSON-escaped: exactly
   what `json.dumps` writes, `×` and all.
7. **Datasheets are two extras, not part of `full`.** spiflash 0.0.post38
   (released during planning, 2026-09-28) added datasheets: 651 of them
   for 631 chip ids, with 52,464 bytes of URLs and 42,296 bytes of titles.
   That is several times all other strings together.
   - The text output prints the best one (`    datasheet: <url>`, after
     `from:`); the JSON lists all of them (`datasheets`, between
     `conflicts` and `records`).
   - The extra `datasheet` adds the best URL per chip (the text line).
   - The extra `datasheets` adds the full JSON list (url, title, revision,
     date, official, id_confirmed).
   - The oracle removes the line and the key when they aren't selected, as
     it does for `records`.
8. **The probe only sends legacy commands to a silent bus.**
   - The NAND read-id (`9f 00`) runs whenever the JEDEC lookup fails. It is
     the same read-id command, and a NAND chip answers plain `9f` with a
     non-blank dummy byte first.
   - REMS, RES2/RES1, AT25F and ST95 run only when the JEDEC answer was
     blank (all `0x00` or `0xFF`), as spec §5.3 says. A chip that answers
     read-id but isn't in the database is never sent anything else.
9. **SFDP comes from spiflash** (Part D replan, 2026-09-29). spiflash
   0.0.post74 added a JESD216 decoder (`spiflash.sfdp`) and per-record SFDP
   dumps (QEMU's 12 tables, for 11 chip ids). uspiflash has no SFDP parser
   of its own and fetches no fixtures: `spiflash.sfdp.parse` is the oracle
   for everything the C decodes, and spiflash's dumps are the fixtures.
   §5.6's other fixture sources (real chips, datasheets) arrive as spiflash
   data, through PRs to `mithro/spiflash`.
10. **Three SFDP fields.**
    - `sfdp_summary` (the text output's `sfdp:` lines for the database's
      dumps, +0.9 KB on Cortex-M0) is part of `describe` and `full`. Like
      conflicts, it is stored only with the text printer. `usf_print`
      matches `spiflash id` at those levels, `sfdp:` lines included.
    - `sfdp` compiles `usf_sfdp_read`, which reads and decodes the chip's
      own BFPT (+0.7 KB). It is an opt-in extra.
    - `sfdp_dumps` adds the JSON's `"sfdp"` list (+19.6 KB). It is an
      opt-in extra like `records`; without it the oracle strips the key.
11. **`usf_sfdp_read(usf_bus *, usf_sfdp *)`** fills its own struct (the
    BFPT fields a driver needs) instead of the §5.2 sketch's `usf_chip`,
    which holds only ROM indices. The probe does not merge SFDP into its
    answer (§5.3 step 5): the caller chooses. The SFDP-versus-database
    experiment found the database saying as much as SFDP, or more, for
    every shipped dump.
12. **`generate` defaults to SPI NOR; SPI NOR is the primary target**
    (maintainer decision, 2026-09-29). Without `--type`, `uspiflash
    generate` keeps only SPI NOR chips, as if given `--type nor`; `--type
    nor --type nand` keeps every type and `--type nand` only NAND.
    - Only the command line's default changes. The library's
      (`ChipFilter()`, `Selection.make`) still keeps every type, and the
      tests, the oracle and the size ledger name their types explicitly.
    - A generated file records its effective types: its regeneration
      command always gives `--type` (every type is `--type nor --type
      nand`), so `uspiflash check` regenerates it identically. A
      configuration with no types still means every type, as it always
      has.
13. **The `uspiflash-linux` .deb is dynamically linked** (Part E ruling
    R4). §2 said "static tool".
    - Debian policy asks a statically linked binary to declare
      `Built-Using` for the libraries it contains, and a dynamic one gets
      its libc dependency from `${shlibs:Depends}`.
    - The package is built for each suite, so it links against that
      suite's libc and installs wherever the suite does.
    - `debian/rules` builds it with dpkg-buildflags' flags (hardening
      included) and `-Werror`, from a header generated by the generator the
      same build made.
    - The static build stays the Makefile's default (`examples/linux/`),
      for use outside Debian: glibc now, musl in M2.

## 14. Amendments (M2 plan, 2026-09-30)

14. **The measurement reads ELF itself.**
    - `uspiflash.elf` (stdlib `struct`) reads sections, symbols and
      relocations of 32- and 64-bit, little- and big-endian objects.
    - It replaces `llvm-readobj`/`llvm-nm` and spec §9's `pyelftools`
      extra: the numbers no longer depend on an environment's LLVM, or on
      which targets that LLVM supports (bullseye's LLVM 11 has no JSON
      output). mypy --strict needs no override for an untyped library.
    - The reference ledger's `tools` then lists compilers and linkers
      (amendment 22), no size tools.
15. **Ledger history is git's** (§7.3 said JSON-lines with a row per
    commit).
    - `sizes/ledger.json` is the reference: the three M1 targets, every
      configuration, per-section and per-symbol sizes, stack, linked image.
    - `sizes/matrix/<environment>.json` has one entry per toolchain × CPU
      × matrix configuration.
    - Both hold only HEAD's numbers and are checked byte for byte; their
      history is `git log -p sizes/`.
    - The PR size-difference comment compares a pull request's committed
      files with its base branch's.
16. **Toolchains.**
    - Debian packages from snapshot.debian.org in digest-pinned
      `debian:{bullseye,bookworm,trixie,sid}` images, each at the snapshot
      its image was built from.
    - sha256-pinned release tarballs: xPack `arm-none-eabi-gcc` and
      `riscv-none-elf-gcc`; Bootlin uClibc-ng.
    - WCH MounRiver 1.92 (maintainer decision, 2026-10-01): pinned by
      sha256 from a third-party GitHub mirror (WCH's own URL answers 403),
      labelled "vendor fork, unofficial mirror", in an environment of its
      own (`wch`), so the mirror disappearing breaks only WCH's rows.
    - The inventory is `src/uspiflash/toolchains.toml`, in the package, so
      `uspiflash toolchains list` works from an install.
    - Images on ghcr.io are optional caches, built by `tools/images/` only.
17. **"Links nothing", per CPU** (controller ruling, 2026-10-01).
    - No undefined symbol, except a port's non-arithmetic runtime routines,
      each listed per CPU with the reason: SDCC's generic-pointer and
      calling-convention routines, and the ELFv2 TOC base.
    - Measured on SDCC 4.5.0 (Task 9's research, 2026-09-30):
      - mcs51: `__gptrget`, `__gptrput` (generic-pointer access);
      - hc08: `___SDCC_hc08_ret2`, `___SDCC_hc08_ret3` (return registers);
      - z80: `___sdcc_call_iy`, `___sdcc_enter_ix`;
      - mos6502: `REGTEMP`, `DPTR`, `__sdcc_indirect_jsr`,
        `___SDCC_m6502_ret2`, `___SDCC_m6502_ret3`.
    - ppc64le may need `.TOC.` (the ELFv2 TOC base, defined by the linker).
    - An arithmetic helper (multiply, divide, shift) is never allowed, nor
      a C library function (`memcpy`) or a switch-table dispatcher
      (`__gnu_thumb1_case_uqi`).
18. **Arithmetic without helpers** (per-CPU switches in the template now,
    with per-compiler defaults: controller ruling, 2026-10-01; M4's
    `Target` classes may take them over).
    - `USF_SOFT_MUL` (row offsets by shift-and-add) and `USF_SOFT_SHIFT`
      (no variable 32-bit shift) are 1 automatically where the CPU needs
      them, and can be overridden. An index times `USF_OFF_BYTES` is a
      shift when that is 2.
    - A constant multiply or shift chain is kept out of the optimiser's
      reach with `__attribute__((noinline))` under GNU C: GCC and clang
      fold both back into the helper call.
    - The SFDP reader reads each field from its own byte address, so it
      never shifts by a variable count on any CPU. `usf__dec2` no longer
      subtracts in a loop, which clang turns into `__udivsi3`.
    - Both switches are also tested on the host (parity with spiflash) with
      the switch forced on.
    - On Cortex-M0 with GCC, the JSON tree walker dispatches by range, not
      by a dense `switch` (a Thumb-1 jump table calls libgcc), and the
      NAND probe copies `usf_chip` member by member (a 2-byte-aligned
      struct copy called `memcpy`).
19. **SDCC.**
    - The callback typedefs carry `USF_REENTRANT`:
      - `__reentrant` on the non-reentrant ports (mcs51, ds390, hc08, s08,
        mos6502, mos65c02, pdk13–15);
      - empty elsewhere (stm8, z80 and the other ports reject the keyword).
    - The default memory model therefore works. A user's `putc`/`xfer`
      functions must be declared `USF_REENTRANT` too.
    - SDCC builds use `--std-c99 --opt-code-size --Werror --disable-warning
      110` (controller ruling, 2026-10-01). Warning 110 ("conditional flow
      changed by optimizer") reports the optimiser deleting a branch that a
      one-type header (`USF_LOOKUP_MAX` 1) makes constant. It is not about
      the source.
    - "No static data" is checked for real: a second compile with
      `--stack-auto` moves every local to the stack, and any writable area
      left is static data, refused. Only then are the default model's
      writable areas reported as static frames.
    - SDCC reports no stack use: stm8's and z80's stacks are not measured
      until M3.
    - A whole program on the 8051 needs `--model-large`: the small model's
      internal RAM cannot hold its locals.
20. **AVR is measured on avrxmega3 (ATmega4809)**, where flash is in the
    data address space, with avr-gcc only: clang 19's AVR backend still
    references `__do_copy_data` there.
    - Classic AVR (ATmega328P) copies `.rodata` to RAM
      (`__do_copy_data`).
    - The library would need every table and string literal in `__flash`
      there. That is M4's (controller ruling, 2026-10-01: AVR is not a
      stated target).
21. **libc matrix scope** (§6.2):
    - The generated library needs no libc.
    - The Linux tool is built against glibc (static and dynamic), musl,
      dietlibc and uClibc-ng.
    - The host tests run on glibc (Ubuntu, Debian) and musl (Alpine).
    - A bare-metal example links against newlib, newlib-nano, picolibc (Arm
      and RISC-V), avr-libc and SDCC's library.
    - Deferred:
      - Zephyr's, the LiteX BIOS's and MicroPython's libcs arrive with
        M5–M7;
      - LLVM-libc: Debian ships it only as an overlay on glibc.
22. **Stack, the linked image, and instruction counts.**
    - Each function's frame comes from `-fstack-usage`. GCC's
      `dynamic,bounded` (stack realignment, as on i386) counts its bound,
      and an unbounded `dynamic` frame is refused. A static peak is
      computed over the call graph, read from the object's relocations.
      Callbacks (`putc`, `xfer`) are excluded, because they are the
      caller's.
    - "Linked" is the implementation linked alone, every public function
      kept as an entry, with no C library or start-up code. §7.1 says "a
      minimal program that calls the API, linked with and without the
      library". The two agree on what they count (alignment, pools,
      veneers), and this one needs no per-target start-up code. The
      linkers' version lines are recorded beside the compilers'.
    - The simulator's measured peak and instruction counts are M3's.
23. **LiteX's hard CPUs are measured, for size tracking only.**
    - From `litex/soc/cores/cpu` at LiteX `8c01073afb71aa0a0709f02f8e24247589e8f5e4`
      (2026-09-30), the "hardcore" CPUs and LiteX's own compiler flags:
      - zynq7000 and cyclonev_hps: Cortex-A9 (`-mcpu=cortex-a9 -mfpu=vfpv3
        -mfloat-abi=hard`);
      - zynqmp and agilex_hps: Cortex-A53 (`aarch64-none-elf`);
      - eos_s3: Cortex-M4F;
      - gowin_emcu: Cortex-M3 (`-march=armv7-m -mthumb`);
      - gowin_ae350: RISC-V (`-march=rv32imafdc -mabi=ilp32`).
    - They are `measure.CPUS` entries (cortex-m3, cortex-m4, cortex-a9,
      cortex-a53, rv32imafdc) marked LiteX, with sections of their own in
      the size matrix.
24. **What M2 defers** (each recorded, none silent):
    - CPU flags enumerated from GCC's and LLVM's `-mcpu` lists (§7.2): M2
      takes each CPU's flags from the compilers' documented triples and,
      for LiteX, from LiteX's own sources (decision 23). The full
      enumeration is M4's, when the `Target` classes choose per CPU.
    - musl builds of the Linux tool for arm64, armhf and riscv64 (§8): M2
      builds musl, dietlibc and uClibc-ng for x86-64. Other architectures
      wait for M7's real Pi, with Bootlin's musl toolchains, pinned the
      same way.
    - A per-architecture parity job (arm64, i386) at the locked spiflash
      (issue #7): M8.
    - §7.3's charts of the ledger in the docs: M8. M2's docs render the
      ledgers as tables.
    - Classic AVR (decision 20): M4.
    - The simulator-measured stack and instruction counts (decision 22):
      M3.

## 15. Amendments (spiflash 0.0.post173 catch-up, 2026-10-01)

25. **Source masks follow the selection.** spiflash 0.0.post173 has eleven
    sources (Dediprog, Rockchip and IMSProg are new) and 0.0.post182
    twelve (MediaTek, SPI NAND only). SPI NOR chips alone cite eleven, so
    a one-byte mask (§5.4) cannot hold them.
    - One byte each while every mask the selection stores fits eight bits
      (`SRC_BYTES` 1): the old format, at no cost.
    - Past that, two bytes (`usf_srcmask` is `uint16_t`). An entry's mask
      is a one-byte index into a table of the distinct ones (`srcmasks`)
      when that is smaller than a second byte per entry. An operation's or
      a conflict value's mask is stored relative to its entry's (bit *j*
      for the entry's *j*-th source: one byte up to eight sources, two
      past that) when that saves more than its code (`layout.REL_CODE`).
    - Measured on the ledger's targets (`full:nor`, Cortex-M0, clang 19):
      two bytes for every mask 91,806 bytes; entry masks two bytes and
      the rest relative 85,748; entry-mask table and the rest two bytes
      90,978; table and relative (chosen) 84,976. For `full:nand` (a
      dozen operation and conflict masks) the relative code costs more
      than it saves, so the rule leaves them two bytes.
    - Sixteen sources fill two bytes: the generator refuses a 17th.
26. **A filtered build answers as the whole database does.** spiflash
    infers a chip's manufacturer from the other chips and folds a SPI NAND
    id into a longer one, so a database rebuilt from the kept chips'
    records could answer differently. `ChipFilter.apply` keeps the whole
    database's own chips (`levels.Kept`), narrowed by the whole database.
27. **Variants are what spiflash prints.** `Database.narrow` also re-infers
    the manufacturer and keeps only the remaining parts' datasheets, so
    two narrowings with the same records can print differently. The
    snapshot tells variants apart by spiflash's own JSON and verbose text
    (`model.printed`).
28. **0.0.post173's output.** A SPI NAND chip's shorter ids follow its own
    in `ids` as bare headers (bit 7), matched by `usf_lookup` and printed
    in the JSON's `"ids"`; inferred manufacturers follow the named ones in
    `mfrs` (`usf_manufacturer` returns 2 for one: `(inferred)` and
    `"manufacturer_inferred"`); the `parts differ on` lines are stored as
    text (`difflines`), about 1 KB at `describe:nor`. A SPI NOR-only build
    has no shorter ids and pays nothing for them.
