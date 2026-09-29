"""Read a :class:`~uspiflash.layout.Layout`'s bytes back, the way the C
template does. The tests compare this with spiflash (so the tables are right)
and the C output with spiflash (so the C is right); the two meet in the
middle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .layout import ALL_OPS, CONFLICT_ATTRS, FEATURES, NONE8, NONE16, SOURCES

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
    at, e = 0, 0
    while ids[at]:
        hdr = ids[at]
        n, t = hdr & 7, hdr >> 3 & 1
        if (
            hdr >> 4 == family
            and n <= len(core)
            and n > best_len[t]
            and ids[at + 1 : at + 1 + n] == core[:n]
        ):
            best_len[t], best[t] = n, e
        at += 1 + n
        e += 1
    return [_narrow(lay, best[t], core[best_len[t] :]) for t in (0, 1) if best_len[t]]


def _narrow(lay: Layout, base: int, x: bytes) -> int:
    """The entry for ``base`` given the bytes read after its id (C's
    ``usf__narrow``): the mask of agreeing extended ids selects a variant."""
    d = lay.defines
    if not x or not d.get("HAVE_EXT"):
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


def _operations(lay: Layout, offset: int) -> list[tuple[str, list[Source] | None]]:
    b, ops = lay.tables["opsets"], lay.tables["ops"]
    with_sources = "HAVE_SOURCES" in lay.defines
    step = 2 if with_sources else 1
    out: list[tuple[str, list[Source] | None]] = []
    for j in range(b[offset]):
        at = offset + 1 + j * step
        stable = ops[b[at] * lay.defines["OP_SIZE"]]
        out.append((ALL_OPS[stable], _sources(b[at + 1]) if with_sources else None))
    return out


def _conflicts(lay: Layout, offset: int) -> dict[str, list[tuple[object, list[Source]]]]:
    out: dict[str, list[tuple[object, list[Source]]]] = {}
    if offset == NONE16:
        return out
    b, at = lay.tables["conflicts"], offset
    while b[at] != NONE8:
        attr, n = CONFLICT_ATTRS[b[at]], b[at + 1]
        at += 2
        out[attr] = [
            (_value(lay, _ATTR_TABLE[attr], b[at + 2 * j]), _sources(b[at + 2 * j + 1]))
            for j in range(n)
        ]
        at += 2 * n
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
    if "E_NAMES" in d:
        b, at = lay.tables["namelists"], _u16(row, d["E_NAMES"])
        out["names"] = [string(lay, _off(lay, b, at + 1 + j * lay.off_bytes)) for j in range(b[at])]
    if "E_SRCS" in d:
        out["sources"] = _sources(row[d["E_SRCS"]])
    if "E_OPS" in d:
        out["operations"] = _operations(lay, _u16(row, d["E_OPS"]))
    if "E_CONF" in d:
        out["conflicts"] = _conflicts(lay, _u16(row, d["E_CONF"]))
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
        if "HAVE_PROVENANCE" in d:
            url = string(lay, _off(lay, b, at))
            at += ob
        out.append((source, name, ext, url))
    return out


def jep106(lay: Layout) -> list[tuple[int, int, str]]:
    """Every (bank, id, name) in the ``jep106`` table, in table order."""
    b, step = lay.tables["jep106"], 2 + lay.off_bytes
    return [(b[at], b[at + 1], string(lay, _off(lay, b, at + 2))) for at in range(0, len(b), step)]
