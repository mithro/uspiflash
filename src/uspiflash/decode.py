"""Read a :class:`~uspiflash.layout.Layout`'s bytes back, the way the C
template does. The tests compare this with spiflash (so the tables are right)
and the C output with spiflash (so the C is right); the two meet in the
middle."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .layout import (
    ALL_OPS,
    CONFLICT_ATTRS,
    FEATURES,
    ID_ALIAS,
    NONE8,
    NONE16,
    SOURCES,
    T_DICT,
    T_DICT_END,
    T_END,
    T_FALSE,
    T_INT,
    T_ITEM,
    T_KEY,
    T_LIST,
    T_LIST_END,
    T_NULL,
    T_STR,
    T_TRUE,
    rel_bytes,
)

if TYPE_CHECKING:
    from spiflash.enums import Source

    from .layout import Layout

#: Each conflict attribute's value table.
_ATTR_TABLE = {"size": "sizes", "page_size": "pages", "sector_size": "sectors", "voltage": "volts"}


def _u16(b: bytes, at: int) -> int:
    return b[at] | b[at + 1] << 8


def _off(lay: Layout, b: bytes, at: int) -> int:
    return int.from_bytes(b[at : at + lay.off_bytes], "little")


def string(lay: Layout, offset: int) -> str:
    """The NUL-terminated string at ``offset`` in the pool."""
    pool = lay.tables["str"]
    return pool[offset : pool.index(b"\0", offset)].decode("ascii")


def _sources(mask: int) -> list[Source]:
    return [s for i, s in enumerate(SOURCES) if mask >> i & 1]


def lookup(lay: Layout, family: int, data: bytes) -> list[int]:
    """Entry indices answering ``data`` (C's ``usf_lookup``)."""
    skip = 0
    while skip + 1 < len(data) and data[skip] == 0x7F:
        skip += 1
    core = data[skip:]
    ids = lay.tables["ids"]
    best_len = [0, 0]
    best = [0, 0]
    at, e, own = 0, -1, 0
    while ids[at]:
        hdr = ids[at]
        n, t = hdr & 7, hdr >> 3 & 1
        if not hdr & ID_ALIAS:  # a chip's own id; a shorter one starts it
            own, e = at + 1, e + 1
        if (
            hdr >> 4 & 7 == family
            and n <= len(core)
            and n > best_len[t]
            and ids[own : own + n] == core[:n]
        ):
            best_len[t], best[t] = n, e
        at += 1 if hdr & ID_ALIAS else 1 + n
    return [_narrow(lay, best[t], core[best_len[t] :]) for t in (0, 1) if best_len[t]]


def ids(lay: Layout, base: int) -> list[bytes]:
    """Chip id ``base``'s ids, its own then the shorter ones (JSON's ``ids``)."""
    b, at = lay.tables["ids"], 0
    for _ in range(base):
        at += 1 + (b[at] & 7)
        while b[at] & ID_ALIAS:
            at += 1
    own = b[at + 1 : at + 1 + (b[at] & 7)]
    out, at = [own], at + 1 + len(own)
    while b[at] & ID_ALIAS:
        out.append(own[: b[at] & 7])
        at += 1
    return out


def _narrow(lay: Layout, base: int, x: bytes) -> int:
    """The entry for ``base`` given the bytes read after its id (C's
    ``usf__narrow``): the mask of agreeing extended ids selects a variant."""
    d = lay.defines
    if not x or not d["HAVE_EXT"]:
        return base
    offset = _u16(lay.tables["entries"], base * d["ENTRY_SIZE"] + d["E_EXT"])
    if offset == NONE16:
        return base
    b = lay.tables["ext"]
    k, at, mask = b[offset], offset + 1, 0
    for i in range(k):
        n = b[at]
        ext = b[at + 1 : at + 1 + n]
        if ext[: len(x)] == x[:n]:
            mask |= 1 << i
        at += 1 + n
    count = b[at]
    at += 1
    for _ in range(count):
        if _u16(b, at) == mask:
            return _u16(b, at + 2)
        at += 4
    return base


#: Each value table's row width in bytes.
_WIDTH = {"sizes": 4, "pages": 2, "sectors": 4, "volts": 4}


def _value(lay: Layout, table: str, i: int) -> object:
    """Row ``i`` of value table ``table``, read from its bytes; ``None`` for 0xFF."""
    if i == NONE8:
        return None
    w = _WIDTH[table]
    row = lay.tables[table][i * w : (i + 1) * w]
    if table == "volts":
        return (_u16(row, 0), _u16(row, 2))
    return int.from_bytes(row, "little")


def entry_mask(lay: Layout, row: bytes) -> int:
    """An entry row's source mask (C's ``usf_sources``): ``E_SRCS`` itself,
    or an index into ``srcmasks``."""
    d = lay.defines
    at = d["E_SRCS"]
    if d["SRCMASK_COUNT"]:
        return _u16(lay.tables["srcmasks"], 2 * row[at])
    return int.from_bytes(row[at : at + d["SRC_BYTES"]], "little")


def _item_bytes(lay: Layout, full: int) -> int:
    """The width of an operation's or a conflict value's mask, in an entry
    whose mask is ``full``."""
    return rel_bytes(full) if lay.defines["SRC_REL"] else lay.defines["SRC_BYTES"]


def _item_mask(lay: Layout, b: bytes, at: int, full: int) -> int:
    """The operation's or conflict value's mask stored at ``b[at]`` (C's
    ``USF__SRC``), as an absolute mask."""
    stored = int.from_bytes(b[at : at + _item_bytes(lay, full)], "little")
    if not lay.defines["SRC_REL"]:
        return stored
    bits = [i for i in range(full.bit_length()) if full >> i & 1]
    return sum(1 << i for j, i in enumerate(bits) if stored >> j & 1)


def _operations(lay: Layout, offset: int, full: int) -> list[tuple[str, list[Source] | None]]:
    if not lay.defines["OP_COUNT"]:  # no operation stored: no opsets either
        return []
    b, ops = lay.tables["opsets"], lay.tables["ops"]
    with_sources = bool(lay.defines["HAVE_SOURCES"])
    step = 1 + (_item_bytes(lay, full) if with_sources else 0)
    out: list[tuple[str, list[Source] | None]] = []
    for j in range(b[offset]):
        at = offset + 1 + j * step
        stable = ops[b[at] * lay.defines["OP_SIZE"]]
        srcs = _sources(_item_mask(lay, b, at + 1, full)) if with_sources else None
        out.append((ALL_OPS[stable], srcs))
    return out


def _conflicts(lay: Layout, offset: int, full: int) -> dict[str, list[tuple[object, list[Source]]]]:
    out: dict[str, list[tuple[object, list[Source]]]] = {}
    if offset == NONE16:
        return out
    b, at = lay.tables["conflicts"], offset
    step = 1 + _item_bytes(lay, full)
    while b[at] != NONE8:
        attr, n = CONFLICT_ATTRS[b[at]], b[at + 1]
        at += 2
        out[attr] = [
            (
                _value(lay, _ATTR_TABLE[attr], b[at + step * j]),
                _sources(_item_mask(lay, b, at + step * j + 1, full)),
            )
            for j in range(n)
        ]
        at += step * n
    return out


def entry(lay: Layout, index: int) -> dict[str, object]:
    """Entry ``index``'s fields, as the tables hold them."""
    d = lay.defines
    row = lay.tables["entries"][index * d["ENTRY_SIZE"] : (index + 1) * d["ENTRY_SIZE"]]
    out: dict[str, object] = {"bank": row[d["E_BANK"]]}
    for key, name, table in (
        ("size", "E_SIZE", "sizes"),
        ("page_size", "E_PAGE", "pages"),
        ("sector_size", "E_SECTOR", "sectors"),
        ("voltage", "E_VOLT", "volts"),
    ):
        if name in d:
            out[key] = _value(lay, table, row[d[name]])
    if "E_FEAT" in d:
        bits = int.from_bytes(lay.tables["featsets"][3 * row[d["E_FEAT"]] :][:3], "little")
        out["features"] = [f for i, f in enumerate(FEATURES) if bits >> i & 1]
    if "E_MFR" in d:
        i = row[d["E_MFR"]]
        mfr = None if i == NONE8 else string(lay, _off(lay, lay.tables["mfrs"], i * lay.off_bytes))
        out["manufacturer"] = mfr
        out["manufacturer_inferred"] = i != NONE8 and i >= d["MFR_INFERRED"]
    if "E_NAMES" in d:
        b, at = lay.tables["namelists"], _u16(row, d["E_NAMES"])
        out["names"] = [string(lay, _off(lay, b, at + 1 + j * lay.off_bytes)) for j in range(b[at])]
    full = entry_mask(lay, row) if "E_SRCS" in d else 0
    if "E_SRCS" in d:
        out["sources"] = _sources(full)
    if "E_OPS" in d:
        out["operations"] = _operations(lay, _u16(row, d["E_OPS"]), full)
    if "E_CONF" in d:
        out["conflicts"] = _conflicts(lay, _u16(row, d["E_CONF"]), full)
    if "E_DS" in d:
        out["datasheets"] = _datasheets(lay, _u16(row, d["E_DS"]))
    return out


def _datasheets(lay: Layout, offset: int) -> list[tuple[str, bool | None]]:
    """A ``dslists`` blob: (URL, id confirmed, or ``None`` without DATASHEETS)."""
    d = lay.defines
    if not d["DS_COUNT"]:  # no chip has a datasheet: no dslists either
        return []
    b, rows, step = lay.tables["dslists"], lay.tables["dsrows"], d["DS_ITEM"]
    out: list[tuple[str, bool | None]] = []
    for j in range(b[offset]):
        at = offset + 1 + j * step
        url = string(lay, _off(lay, rows, _u16(b, at) * d["DS_ROW"]))
        out.append((url, bool(b[at + 2]) if d["HAVE_DATASHEETS"] else None))
    return out


def records(lay: Layout, index: int) -> list[tuple[Source, str, bytes | None, str | None]]:
    """Entry ``index``'s records: (source, name, extended id, ``at`` or ``None``)."""
    d, ob = lay.defines, lay.off_bytes
    b = lay.tables["records"]
    at = _u16(lay.tables["entries"], index * d["ENTRY_SIZE"] + d["E_RECS"])
    out: list[tuple[Source, str, bytes | None, str | None]] = []
    count, at = b[at], at + 1
    for _ in range(count):
        source, name = SOURCES[b[at]], string(lay, _off(lay, b, at + 1))
        at += 1 + ob
        n = b[at]
        ext = b[at + 1 : at + 1 + n] or None
        at += 1 + n
        url = None
        if d["HAVE_PROVENANCE"]:
            url = string(lay, _off(lay, b, at))
            at += ob
        out.append((source, name, ext, url))
    return out


def jep106(lay: Layout) -> list[tuple[int, int, str]]:
    """Every (bank, id, name) in the ``jep106`` table, in table order."""
    b, step = lay.tables["jep106"], 2 + lay.off_bytes
    return [(b[at], b[at + 1], string(lay, _off(lay, b, at + 2))) for at in range(0, len(b), step)]


def _sfdp_row(lay: Layout, index: int) -> int | None:
    """The byte offset of entry ``index``'s ``sfdprows`` row (C's
    ``usf__sfdprow``), or ``None`` when it has no SFDP dump."""
    rows, size = lay.tables.get("sfdprows", b""), lay.defines.get("SFDP_ROW", 2)
    return next((at for at in range(0, len(rows), size) if _u16(rows, at) == index), None)


def diff_lines(lay: Layout, index: int) -> list[str]:
    """Entry ``index``'s ``parts differ on`` lines, without their prefix."""
    b, step = lay.tables.get("difflines", b""), 2 + lay.off_bytes
    return [
        string(lay, _off(lay, b, at + 2)) for at in range(0, len(b), step) if _u16(b, at) == index
    ]


def sfdp_lines(lay: Layout, index: int) -> list[str]:
    """Entry ``index``'s ``sfdp:`` lines, without their ``"    sfdp: "``."""
    at = _sfdp_row(lay, index)
    if at is None:
        return []
    b = lay.tables["sfdplines"]
    p = _u16(lay.tables["sfdprows"], at + lay.defines["SFDP_LINES"])
    return [string(lay, _off(lay, b, p + 1 + k * lay.off_bytes)) for k in range(b[p])]


def sfdp_json(lay: Layout, index: int) -> list[Any]:
    """Entry ``index``'s JSON ``"sfdp"`` value, read back token by token as
    the C's ``usf__jtree`` walks it."""
    at = _sfdp_row(lay, index)
    if at is None:
        return []
    b, ob = lay.tables["sfdptree"], lay.off_bytes
    p = _u16(lay.tables["sfdprows"], at + lay.defines["SFDP_TREE"])
    holder: list[Any] = []
    stack: list[Any] = [holder]
    key = ""
    while (t := b[p]) != T_END:
        p += 1
        kind, top = t & ~T_ITEM, stack[-1]
        if kind in (T_LIST_END, T_DICT_END):
            stack.pop()
            continue
        if kind == T_KEY:
            key = json.loads(f'"{string(lay, _off(lay, b, p))}"')
            p += ob
            continue
        if bool(t & T_ITEM) != (isinstance(top, list) and top is not holder):
            msg = f"sfdptree token 0x{t:02x} at {p - 1}: item flag disagrees with its parent"
            raise ValueError(msg)
        value: Any
        if kind == T_INT:
            value, p = int.from_bytes(b[p : p + 4], "little"), p + 4
        elif kind == T_STR:
            value, p = json.loads(f'"{string(lay, _off(lay, b, p))}"'), p + ob
        elif kind in (T_NULL, T_FALSE, T_TRUE):
            value = {T_NULL: None, T_FALSE: False, T_TRUE: True}[kind]
        elif kind in (T_LIST, T_DICT):
            value = [] if kind == T_LIST else {}
        else:
            msg = f"sfdptree token 0x{t:02x} at {p - 1}"
            raise ValueError(msg)
        if isinstance(top, list):
            top.append(value)
        else:
            top[key] = value
        if kind in (T_LIST, T_DICT):
            stack.append(value)
    root: list[Any] = holder[0]
    return root
