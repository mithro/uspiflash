"""What the generated C must print, computed from the spiflash package: the
tests' single source of truth. Every function is spiflash's own output with
only the fields the selection leaves out removed."""

from __future__ import annotations

from typing import TYPE_CHECKING

from spiflash.cli import describe
from spiflash.enums import DataPhase

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
