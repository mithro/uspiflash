# M2 (measurement) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every size uspiflash reports is measured reproducibly: the reference
ledger records code, tables, stack and the linked image, and a committed matrix
ledger shows the generated library building warning-free, linking nothing, on
every CPU with many GCC, LLVM and SDCC versions (and WCH's vendor fork, and
LiteX's hard CPUs for size tracking), while
the Linux tool, the host tests and a bare-metal example are built against every
popular libc.

**Architecture:**
- **ELF reader:** `uspiflash.elf` reads compiled objects with the standard
  library, so every environment measures the same way, whatever binutils or
  LLVM it has. SDCC's `.rel` objects are read too.
- **CPUs:** `measure.CPUS` says how each compiler family selects each CPU
  and which calling-convention runtime symbols that port may need.
  `measure.Target` is a compiler plus a CPU.
- **Inventory:** `src/uspiflash/toolchains.toml` lists every toolchain:
  Debian packages from snapshot.debian.org, in digest-pinned Debian images,
  or sha256-pinned release tarballs. `uspiflash toolchains` lists them, sets
  an environment up inside its container, and runs a command there under the
  sandbox's limits.
- **Ledgers:** `sizes/ledger.json` stays the reference: three targets, the
  README's headline. `sizes/matrix/<environment>.json` holds every
  toolchain × CPU × configuration: all of them on 32- and 64-bit CPUs,
  the SPI NOR ones on 16-bit CPUs. Both are regenerated and checked
  byte for byte, and CI checks them.
- **Portability fixes:** the matrix finds compiler-helper calls, which are
  fixed in the template: no multiply, divide or variable shift reaches a
  helper on any CPU, and neither does a struct copy or a switch on
  Cortex-M0 with GCC. SDCC's non-reentrant ports get `__reentrant`
  callbacks.
- **libc matrix:**
  - the Linux tool is built against glibc, musl, dietlibc and uClibc-ng;
  - the host tests run on glibc and on musl (Alpine);
  - a bare-metal example links against newlib, newlib-nano, picolibc,
    avr-libc and SDCC's library.

**Tech Stack:** Python ≥ 3.11 (stdlib `struct`, `tomllib`,
`concurrent.futures`), pytest, ruff, mypy --strict; GCC, clang/LLVM and SDCC
from Debian bullseye, bookworm, trixie and sid at snapshot.debian.org; xPack
and WCH MounRiver tarballs; Bootlin uClibc-ng; Docker; GitHub Actions.

**Spec:** [`docs/superpowers/specs/2026-09-28-uspiflash-design.md`](../specs/2026-09-28-uspiflash-design.md)
(§7, §11 "M2", §12, §13). Read it and [the M1 index](2026-09-28-m1-core.md)
first: the M1 index's global constraints and notes sections still bind.

## Parts

| Part | Tasks | Ends with PR |
|---|---|---|
| [A: catch-up, the ELF reader, stack, linked image, sizes in the header](2026-09-30-m2-a-reference.md) | 1–5 | "M2a" |
| [B: CPUs, SDCC, arithmetic without helpers](2026-09-30-m2-b-portability.md) | 6–9 (and 8b) | "M2b" |
| [C: the inventory, the runner, the matrix ledger, CI, images](2026-09-30-m2-c-matrix.md) | 10–14 | "M2c" |
| [D: the libc matrix, experiments, docs, wrap-up](2026-09-30-m2-d-libc.md) | 15–19 | "M2d" |

Why four part files: the plan carries every step's code (about 7,000 lines
across the parts), as M1's did. The parts are also reviewable and
mergeable on their own:
- Part A changes only the reference ledger.
- Part B fixes the C before any matrix exists to fail.
- Part C adds the matrix.
- Part D adds the libc builds on top of the matrix's environments.

Each part is its own branch and worktree (`.worktrees/m2a`, …), made from
`origin/main` after the previous part merged. Review checkpoints and merging
are exactly the M1 index's:
- a `feature-dev:code-reviewer` subagent reviews every task's commits;
- a whole-part review runs before each merge;
- merge only with CI green, with `gh pr merge <n> --merge`.

## Global Constraints

The maintainer's binding decisions, verbatim (controller brief, 2026-09-30):

- "Size is the only optimisation target: measure code + data; record instruction counts at most, never optimise for them."
- "Toolchains are never built in the normal development flow. Use prebuilt or existing Docker containers; scripts/tooling that build and publish images to ghcr are fine as separate tooling, but not part of the normal flow."
- "Open-source compilers only: GCC, LLVM/clang and SDCC, many versions each. WCH's MounRiver GCC forks are included but labelled "vendor fork". LiteX's hard CPUs are for size tracking only. No Windows/MSVC."
- "Test against all popular libcs (glibc, musl, newlib, picolibc, …) — decide which apply where (the generated library needs no libc; the Linux tool and the host tests do)."
- "Heavy runs go through the sandbox (`uv run python -m uspiflash.sandbox -- …`), sized from the machine's current load; never write to /tmp on the host; Docker runs get sandbox-derived limits."
- "SPI NOR is the primary target; ledger and reports lead with NOR-only configurations."
- "Numbers quoted in status reports and docs must come from what the repo documents (the ledger), never computed ad hoc."
- "A new spiflash release, or a flaky/slow job, must never block publishing; the committed ledger must not go stale silently."
- "Commits small and logical with the two trailer lines; ruff (spiflash's rule set), mypy --strict, no noqa/type: ignore; C99 SDCC subset, -Werror everywhere, nm -u empty."

And, carried from the spec and M1 (exact values):

- **Python:** `requires-python = ">=3.11"`; the one runtime dependency is
  `spiflash`. M2 adds no dependency: the ELF reader is stdlib only (decision
  14 below replaces spec §9's `pyelftools` extra).
- **Style:** ruff with spiflash's rule set (`line-length = 100`), `ruff
  format`, `mypy --strict`; no `noqa`, `type: ignore` or mypy overrides for
  untyped modules. A docstring on every module and on every public class
  and function.
- **Generated C:**
  - compiles with `-std=c99 -Wall -Wextra -Wpedantic -Wundef -Werror` under
    gcc and clang; SDCC gets `--std-c99 --Werror` (decision 19);
  - no libc and no allocation; no writable static data;
  - the implementation object has no undefined symbol, except a port's
    listed non-arithmetic runtime routine (decision 17, the controller's
    ruling of 2026-10-01).
- **Output is deterministic:** the same inputs give byte-identical generated
  files, ledgers and READMEs.
- **Housekeeping:**
  - temporary files go in the worktree's `tmp/` (git-ignored), never
    `/tmp` on the host;
  - never redirect stderr to `/dev/null`;
  - use `uv run` for every Python command;
  - no inline `python -c`: write a script file under `tmp/` instead;
  - dates are ISO 8601.
- **Sandbox:**
  - Heavy local runs go through
    `uv run python -m uspiflash.sandbox -- <command>`, e.g. the full test
    suite, and `uspiflash toolchains run`.
  - Docker containers run outside the caller's systemd scope, so every
    `docker run` passes `sandbox.docker_limits(current_limits())`
    (Task 11).
- **Commits:** small, one logical change each, ending with:
  ```
  Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01TYQmVKazwZhRmGrFbrL7TE
  ```
  Never `git push --force`.
- **Publishing is never blocked by M2's new jobs:**
  - `publish-pypi.yml` follows `deb.yml` only.
  - The matrix, libc and musl jobs live in a new `matrix.yml`, never in
    `deb.yml`.
  - `deb.yml` keeps only its `sizes` job (the reference ledger, about a
    minute, fully pinned) and gains the cheap host-clang portability test
    inside the existing pytest run.
- **Numbers in docs and reports** are generated from the ledgers (the
  README splice, `sizes/README.md`, `sizes/matrix/README.md`, the generated
  header's size lines) or quoted from them; never computed by hand.

## Decisions this plan adds to the spec (amendments 14–24)

All of these are decided. The maintainer decided WCH's source; the
controller ruled on the runtime symbols, SDCC's warning 110, classic AVR
and the per-CPU switches (2026-10-01).

Task 1 records these in the spec as "## 14. Amendments (M2 plan,
2026-09-30)", as M1's Task 1 did.

14. **The measurement reads ELF itself.**
    - `uspiflash.elf` (stdlib `struct`) reads sections, symbols and
      relocations of 32- and 64-bit, little- and big-endian objects.
    - It replaces `llvm-readobj`/`llvm-nm` and spec §9's `pyelftools`
      extra: the numbers no longer depend on an environment's LLVM, or on
      which targets that LLVM supports (bullseye's LLVM 11 has no JSON
      output). mypy --strict needs no override for an untyped library.
    - The reference ledger's `tools` then lists compilers only.
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

## The toolchain inventory (researched 2026-09-30)

Each version below was read with `apt-cache policy` in the pinned image at
its snapshot:
- bullseye at `20260824T000000Z`, the snapshot its image names;
- bookworm, trixie and sid at `20260918T000000Z`, the snapshot all three
  images name.

The research also compiled a generated header with most of these:
- trixie's clang 17/19/22, gcc 12/13/14, arm-none-eabi, riscv64-unknown-elf,
  avr, or1k and SDCC 4.5.0;
- the host's clang 19 and arm-none-eabi-gcc 14.2.1;
- in the review (2026-10-01), every `measure.CONFIGS` entry with
  arm-none-eabi-gcc for Cortex-M0, M3 and A9, and clang for M3, A9 and
  A53. That found the two Cortex-M0 helpers Task 8b removes.

| Environment | Image | Compilers (Debian version) |
|---|---|---|
| bullseye | `debian:bullseye@sha256:c0a2ad73611131275b0e9a2e7544cfe3725f4268d4085d8c6f61fdd55aef7917` | gcc-9 9.3.0-22, gcc-10 10.2.1-6, clang-9 1:9.0.1-16.1, clang-11 1:11.0.1-2, gcc-arm-none-eabi 15:8-2019-q3-1+b1, gcc-riscv64-unknown-elf 8.3.0.2019.08+dfsg-1, sdcc 4.0.0+dfsg-2 |
| bookworm | `debian:bookworm@sha256:704583dbf243593da87cf949fc0543ffeca24a28d36c2760dc9545410cb8ed02` | gcc-11 11.3.0-12, gcc-12 12.2.0-14+deb12u1, clang-13 1:13.0.1-11+b2, clang-14 1:14.0.6-12, clang-15 1:15.0.6-4+b1, clang-16 1:16.0.6-15~deb12u1, gcc-arm-none-eabi 15:12.2.rel1-1, gcc-riscv64-unknown-elf 12.2.0-14+deb12u1+11+b2, sdcc 4.2.0+dfsg-1 |
| trixie | `debian:trixie@sha256:d5ce19d4736f0ebbacd686d1040271a5aeb0cc920f5990c1bfae1717627f0674` (= `ledger.IMAGE`) | gcc-12 12.4.0-5, gcc-13 13.3.0-16, gcc-14 14.2.0-19, clang-17 1:17.0.6-22+b2, clang-18 1:18.1.8-18+b1, clang-19 1:19.1.7-3+b1, clang-22 1:22.1.8-1~deb13u4, gcc-arm-none-eabi 15:14.2.rel1-1, gcc-riscv64-unknown-elf 14.2.0+19, gcc-avr 1:14.2.0-2, gcc-or1k-elf 14.2.0-19+1.0.10+b1, gcc-aarch64-linux-gnu 4:14.2.0-1, gcc-powerpc64le-linux-gnu 4:14.2.0-1, sdcc 4.5.0+dfsg-1 |
| sid | `debian:sid@sha256:e6650c18f362b11157a1043a83fbf4f3f603a4ff0aa259da900ffb287d3e6dbd` | gcc-15 15.3.0-3, gcc-16 16.2.0-2, clang-21 1:21.1.8-12, clang-23 1:23.1.1-2, gcc-arm-none-eabi 15:15.3.rel1-2, gcc-riscv64-unknown-elf 15.3.0-24 |
| tarballs (trixie image) | as trixie | xPack arm-none-eabi-gcc 13.3.1-1.1 and 14.2.1-1.1; xPack riscv-none-elf-gcc 13.4.0-1 and 14.2.0-3 |
| wch (trixie image) | as trixie | WCH MounRiver toolchain 1.92 (riscv-none-embed-gcc 8, riscv-none-elf-gcc 12): vendor fork, unofficial mirror |
| libc (trixie image) | as trixie | musl-tools 1.2.5-3.1~deb13u1, dietlibc-dev 0.34~cvs20160606-18, libnewlib-arm-none-eabi 4.5.0.20241231-1, picolibc-arm-none-eabi and picolibc-riscv64-unknown-elf 1.8.10-2, avr-libc 1:2.2.1-1, sdcc-libraries 4.5.0+dfsg-1; Bootlin `x86-64--uclibc--stable-2026.08-1` |

That is:
- GCC 9, 10, 11, 12, 13, 14, 15 and 16 on the host, and 8–15 for Arm and
  RISC-V across Debian and xPack;
- clang 9, 11, 13, 14, 15, 16, 17, 18, 19, 21, 22 and 23;
- SDCC 4.0.0, 4.2.0 and 4.5.0.

Not in Debian:
- msp430-gcc (clang covers msp430);
- SDCC 4.3/4.4: SourceForge tarballs, a candidate for later.

The tarballs' sha256s:

| Tarball | sha256 | Source |
|---|---|---|
| `xpack-arm-none-eabi-gcc-13.3.1-1.1-linux-x64.tar.gz` | `006c89337eced277fdf4c1c3bf3aebe55c85e8d52cba8d412009717fb781b959` | the release's `.sha` file |
| `xpack-arm-none-eabi-gcc-14.2.1-1.1-linux-x64.tar.gz` | `ed8c7d207a85d00da22b90cf80ab3b0b2c7600509afadf6b7149644e9d4790a6` | the release's `.sha` file |
| `xpack-riscv-none-elf-gcc-13.4.0-1-linux-x64.tar.gz` | `2f669492e131906f21641de3ed5cb808d17eff2716b551c73651fe6650565a5f` | the release's `.sha` file |
| `xpack-riscv-none-elf-gcc-14.2.0-3-linux-x64.tar.gz` | `f574415b63f12b09bdd3475223ab492a465d23810646c90c13a4c3b676c83503` | the release's `.sha` file |
| `MRS_Toolchain_Linux_x64_V1.92.tar.xz` (330,007,712 bytes) | `33e0dd7581a2eea25bc5d1aa2c31f5c8b316e543b954d84f9e1ffc5999e93fea` | downloaded and hashed 2026-09-30, from the unofficial GitHub mirror `ch32-riscv-ug/MounRiver_Studio_Community_miror` (maintainer decision) |
| `x86-64--uclibc--stable-2026.08-1.tar.xz` (89,077,704 bytes) | `744dabae2230e8c13fdf338717d9e48201c844a00792e0eed18bb406c4cf149b` | Bootlin's `.sha256` file |

## CI: what runs where

| Workflow | Job | When | Blocks publishing | Wall time |
|---|---|---|---|---|
| `deb.yml` | `test` (pytest, now with the host-clang portability test) | every push and PR | yes (as today) | about 5–9 min, as today, plus seconds |
| `deb.yml` | `sizes` (the reference ledger, pinned trixie) | every push and PR | yes (as today) | about 1 min |
| `matrix.yml` | `measure` × bullseye, bookworm, trixie, sid | PRs touching C, generator, sizes or toolchains; main; nightly | no | about 4 min of `apt-get install` (measured: 221 s for trixie's cross toolchains) + 5–20 min measuring (20 configurations per 32/64-bit build, 4 vCPUs) |
| `matrix.yml` | `measure` × tarballs, wch | main, nightly, dispatch, and PRs touching the C template or the inventory | no | about 10–20 min each (1.3 GB of tarballs; cached by sha256) |
| `matrix.yml` | `libc`, `host-musl` | as `measure` | no | about 5 min each |
| `matrix.yml` | `size-diff` (PR comment) | PRs from this repository | no | under 1 min |
| `matrix.yml` | `stale` (opens/updates an issue) | nightly, when a check failed | no | seconds |
| `images.yml` | `build` (ghcr, optional) | `workflow_dispatch` only | no | as long as the installs |

A PR's added cost is about 60–90 runner-minutes. The repository is public,
so standard runners are free. They are not unlimited, though:
- a public repository's workflows share 20 concurrent standard runners;
- `deb.yml` alone starts 25 jobs on a push (4 test, 1 sizes, 20
  build-deb).

So on a busy push the matrix jobs queue behind `deb.yml`'s. Expect them
to finish 10–30 minutes after it. Nothing waits on them: publishing
follows `deb.yml` only.

The ledgers cannot go stale silently:
- a PR that changes the generator or a toolchain is checked by
  `matrix.yml`, in every environment when it touches the C template or the
  inventory;
- main is checked on every push and nightly;
- a nightly failure of `measure`, `libc` or `host-musl` opens (or
  comments on) an issue labelled `size-matrix`, and a failed `measure`
  uploads the regenerated files as an artifact.

A new spiflash release changes nothing until a catch-up commit moves
`uv.lock`:
- the ledgers are measured with the locked spiflash;
- `spiflash-latest.yml` stays the daily drift alarm.

## File structure (end of M2)

```
src/uspiflash/
  elf.py               NEW  stdlib ELF reader (sections, symbols, relocations)
  measure.py           Cpu/CPUS (LiteX's hard CPUs too), target(), Target (family, runtime,
                            link flags), usable(), linker(), SDCC .rel sizes and the
                            --stack-auto data check, -fstack-usage frames and peak, linked
                            image, SMALL_CONFIGS and configs_for()
  ledger.py            reference ledger: + stack, linked, symbols; reference_sizes.json; compare
  matrix.py            NEW  the matrix ledger: sizes/matrix/<env>.json and README
  toolchains.py        NEW  inventory loader, setup script, docker runner, CI matrix
  toolchains.toml      NEW  the inventory (environments, toolchains, libcs)
  reference_sizes.json NEW  generated by `measure --write`: sizes the header quotes
  provenance.py        the header quotes reference_sizes.json
  sandbox.py           + docker_limits(), --docker-args
  research.py          + environment() for experiment results
  cli.py               + measure --matrix/--compare, toolchains list/script/run/ci-matrix
  templates/uspiflash.h.in   USF_SOFT_MUL, USF_SOFT_SHIFT, USF__NOINLINE, USF__OFFS,
                             USF_REENTRANT, byte-addressed SFDP fields, usf__dec2,
                             usf__jtree by ranges, the NAND probe's member copy
sizes/ledger.json, sizes/README.md
sizes/matrix/{bullseye,bookworm,trixie,sid,tarballs,wch}.json, sizes/matrix/README.md   NEW
examples/linux/Makefile       LIBC=glibc|musl|dietlibc|uclibc-ng
examples/baremetal/{lookup.c,README.md}   NEW
tools/images/{build_images.py,README.md}  NEW (optional ghcr images)
.github/workflows/matrix.yml              NEW
.github/workflows/images.yml              NEW (workflow_dispatch)
tests/test_elf.py, test_stack.py, test_linked.py, test_reference_sizes.py, test_cpus.py,
tests/test_portability.py, test_soft_arith.py, test_human.py, test_sdcc.py,
tests/test_toolchains.py, test_matrix.py, test_images.py, test_libc.py, test_harness.py   NEW
docs/toolchains.md, docs/_ext/toolchains_table.py, docs/_ext/doc_tables.py   NEW
```

## Rulings (2026-10-01)

None of the first draft's open questions remain. Each ruling is written
into the decisions above:
1. Runtime symbols (decision 17): SDCC's non-arithmetic runtime routines
   (e.g. `__gptrget` on mcs51) and `.TOC.` on ppc64le are allowed, listed
   per CPU with a reason; an arithmetic helper never is. Controller
   ruling.
2. WCH MounRiver (decision 16): pinned by sha256 from the unofficial GitHub
   mirror, labelled "vendor fork, unofficial mirror", in its own `wch`
   environment. Maintainer decision.
3. SDCC warning 110 is disabled in SDCC builds (decision 19). Controller
   ruling.
4. Classic AVR `__flash` placement is M4's (decision 20). Controller
   ruling.
5. The per-CPU switches `USF_SOFT_MUL` and `USF_SOFT_SHIFT` go in the
   template now, with per-compiler defaults (decision 18). Controller
   ruling.

## Self-review (2026-09-30; revised 2026-10-01)

- **Spec coverage:** every item in §11's M2 line has a task:
  - sandbox runner: Task 11 (`docker_limits`, the `toolchains run`
    runner);
  - toolchain inventory and images: Tasks 10, 11 and 14;
  - `measure`: Tasks 2–6 and 12;
  - the ledger: Tasks 3–5 and 12;
  - the compiler and libc matrix in CI: Tasks 13, 15, 16 and 17.

  §7.1 (flash, SRAM, stack, linked image, per-symbol sizes, helpers):
  Tasks 2–4 and 6; instruction counts are M3's (decision 22). §7.2's
  LiteX CPUs: Task 6 (decision 23). §7.4's results fields: Task 18. §5.5's
  expected sizes: Task 5. What M2 does not do is listed in decision 24.
  Issue #7's M2 items:
  - SDCC acceptance and `__reentrant`: Task 9;
  - 16×16 multiplies: Task 7;
  - msp430 shifts: Task 8;
  - "links nothing" on more targets: Tasks 6–9, 8b and 12;
  - the musl build: Task 15;
  - experiment environment records: Task 18;
  - the spiflash catch-up: Task 1.
- **Placeholders:** none. Where a value depends on the day the task runs
  (the newest spiflash, a regenerated ledger's numbers), the step gives the
  command that produces it and the check that it is right.
- **Names:** these are defined once and used with the same signatures in
  every part:
  - `elf.read`, `measure.Cpu`, `measure.CPUS`, `measure.target()`,
    `measure.usable()`, `measure.linker()`, `measure.SMALL_CONFIGS`,
    `measure.configs_for()`, `Target.family`, `Sizes.frames`, `Stack`;
  - `toolchains.load()`, `Inventory`, `Inventory.label()`,
    `matrix.build()`, `sandbox.docker_limits()`,
    `research.environment()`.
- **Revision (2026-10-01):** the review's findings (C1, I2–I8 and the
  minor ones) are fixed in place. The changed code was extracted and run
  again (see the report).
