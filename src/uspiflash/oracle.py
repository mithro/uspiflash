"""What the generated C must print, computed from the spiflash package: the
tests' single source of truth. Every function is spiflash's own output with
only the fields the selection leaves out removed.

:func:`sfdp_fields` is the oracle for ``usf_sfdp_read``, which decodes a
chip's own SFDP tables: :func:`spiflash.sfdp.parse`, in the fields the C
fills."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from spiflash.cli import describe
from spiflash.enums import DataPhase
from spiflash.sfdp import AddressBytes, FourByteMethod
from spiflash.sfdp import parse as parse_sfdp

from . import layout
from .levels import Field

if TYPE_CHECKING:
    from spiflash.db import Database
    from spiflash.enums import IdFamily
    from spiflash.model import Flash

    from .levels import Selection

_DATA = {None: "none", DataPhase.READ: "read", DataPhase.WRITE: "write"}


def accessors(flash: Flash, sel: Selection) -> str:
    """The harness's ``A`` dump for one answer."""
    has = sel.has
    out = [f"family={flash.family} type={flash.type} bank={flash.bank} id={flash.id_hex}"]
    if has(Field.SIZE):
        out.append(f"size={flash.size or 0}")
    if has(Field.PAGE_SIZE):
        out.append(f"page={flash.page_size or 0}")
    if has(Field.SECTOR_SIZE):
        out.append(f"sector={flash.sector_size or 0}")
    if has(Field.VOLTAGE):
        v = flash.voltage
        out.append(f"volt={v[0]}-{v[1]}" if v else "volt=none")
    if has(Field.FEATURES):
        out.append("features=" + " ".join(f for f in layout.FEATURES if f in flash.features))
    if has(Field.MANUFACTURER):
        out.append(f"mfr={flash.manufacturer or '?'}")
    if has(Field.NAMES):
        out.append("names=" + ",".join(flash.names))
    if has(Field.SOURCES):
        out.append("sources=" + ",".join(flash.sources))
    if has(Field.OPERATIONS):
        for o in flash.opcodes.values():
            op = o.operation
            if op.kind not in sel.op_kinds:
                continue
            dummy = "var" if op.dummy_clocks is None else str(op.dummy_clocks)
            src = ",".join(o.sources) if has(Field.SOURCES) else ""
            desc = f" desc={op.description}" if has(Field.DESCRIPTIONS) else ""
            out.append(
                f"op={op.name} 0x{op.opcode:02x} kind={op.kind} proto={op.protocol} "
                f"addr={op.address_bytes} dummy={dummy} data={_DATA[op.data]} "
                f"bytes={op.data_bytes or 0} src={src}{desc}"
            )
    return "\n".join(out) + "\n"


def text(db: Database, family: IdFamily, data: bytes, sel: Selection, *, opcodes: bool) -> str:
    """What `spiflash id <data> --method <family> [--opcodes]` prints, less
    what ``sel`` leaves out."""
    blocks = []
    for f in db.lookup(data, method=family):
        lines = []
        for line in describe(f, opcodes=opcodes).split("\n"):
            if line.startswith("    from: ") and not sel.has(Field.SOURCES):
                continue
            if line.startswith("    sfdp: ") and not sel.has(Field.SFDP_SUMMARY):
                continue
            if line.startswith("    sources disagree on ") and not sel.has(Field.CONFLICTS):
                continue
            if line.startswith("    datasheet: ") and not sel.has(Field.DATASHEET):
                continue
            kept = line
            if line.startswith("    0x") and not sel.has(Field.SOURCES):
                kept = line[: line.rindex("  [")]
            lines.append(kept)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def json_text(db: Database, family: IdFamily, data: bytes, sel: Selection) -> str:
    """What `spiflash id --json` prints, less what ``sel`` leaves out."""
    objs = [f.to_json() for f in db.lookup(data, method=family)]
    for o in objs:
        if not sel.has(Field.SFDP_DUMPS):
            del o["sfdp"]
        if not sel.has(Field.DATASHEETS):
            del o["datasheets"]
        if not sel.has(Field.RECORDS):
            del o["records"]
        elif not sel.has(Field.PROVENANCE):
            for r in o["records"]:
                del r["at"]
    return json.dumps(objs, indent=1) + "\n"


#: usf_sfdp.address_bytes: DW1[18:17] (spiflash gives None for the reserved 3).
_ADDRESS = {AddressBytes.THREE: 0, AddressBytes.THREE_OR_FOUR: 1, AddressBytes.FOUR: 2, None: 3}
#: usf_sfdp.enter_4b and exit_4b: bit i is the method at index i (DW16[30:24]
#: and DW16[21:14], in JESD216's bit order).
_ENTER_4B = (
    FourByteMethod.EN4B,
    FourByteMethod.WREN_EN4B,
    FourByteMethod.WREAR,
    FourByteMethod.BRWR,
    FourByteMethod.NV_CR,
    FourByteMethod.OPCODES_4B,
    FourByteMethod.ALWAYS_4B,
)
_EXIT_4B = (
    FourByteMethod.EN4B,
    FourByteMethod.WREN_EN4B,
    FourByteMethod.WREAR,
    FourByteMethod.BRWR,
    FourByteMethod.NV_CR,
    FourByteMethod.HW_RESET,
    FourByteMethod.SW_RESET,
    FourByteMethod.POWER_CYCLE,
)


def sfdp_space(image: bytes) -> bytes:
    """``image`` as a chip whose SFDP space holds it answers: followed by
    0xFF (an idle bus), as far as the header, every parameter header and
    every BFPT they point at reach. A dump file ends where its tables do;
    the chip's space never ends, so this is what ``usf_sfdp_read`` sees.
    A table pointer near 0xFFFFFF makes it about 16 MiB long."""
    space = image.ljust(8, b"\xff")
    headers = space[6] + 1
    space = space.ljust(8 + 8 * headers, b"\xff")
    end = len(space)
    for i in range(headers):
        h = space[8 + 8 * i : 16 + 8 * i]
        if h[0] == 0x00 and h[7] == 0xFF:  # a BFPT (id 0xff00)
            end = max(end, int.from_bytes(h[4:7], "little") + 4 * h[3])
    return space.ljust(end, b"\xff")


def sfdp_fields(image: bytes) -> str:
    """What the harness's ``S`` command (and ``uspiflash-linux --sfdp``)
    prints for a chip whose SFDP space holds ``image``: spiflash's decoding
    of its BFPT, in the fields ``usf_sfdp`` has; ``sfdp=none`` without one."""
    try:
        b = parse_sfdp(sfdp_space(image)).bfpt
    except ValueError:  # no "SFDP" signature
        b = None
    if b is None:
        return "sfdp=none\n"
    size = b.size if b.size is not None and b.size < 1 << 32 else 0
    qe = "none" if b.quad_enable is None else str(b.quad_enable)
    en4b = sum(1 << i for i, m in enumerate(_ENTER_4B) if m in b.four_byte_enter)
    ex4b = sum(1 << i for i, m in enumerate(_EXIT_4B) if m in b.four_byte_exit)
    e4k = 0xFF if b.erase_4k_opcode is None else b.erase_4k_opcode
    head = (
        f"sfdp={b.major}.{b.minor} dwords={b.length} addr={_ADDRESS[b.address_bytes]} "
        f"erase4k=0x{e4k:02x} dtr={int(b.dtr)} size={size} page={b.page_size or 0} "
        f"qe={qe} en4b=0x{en4b:02x} ex4b=0x{ex4b:02x}"
    )
    erase = "".join(f" {e.index}:{e.size.bit_length() - 1}:0x{e.opcode:02x}" for e in b.erase_types)
    reads = "".join(
        f" {r.protocol}:0x{r.opcode:02x}:{r.mode_clocks}+{r.wait_states}" for r in b.reads
    )
    return f"{head}\nerase{erase}\nread{reads}\n"
