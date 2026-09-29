"""The baseline byte layout: the tables a generated file carries, byte by byte.

This docstring is the reference the C template implements;
:mod:`uspiflash.decode` reads the tables back the same way. The baseline is
chosen for obvious correctness, not size (M4 measures and improves it).

Conventions
-----------

- Every field is **one byte** unless marked ``u16`` (2 bytes), ``u32`` (4
  bytes), ``u24`` (3 bytes) or ``OFF``. Multi-byte integers are
  little-endian.
- ``OFF`` is an offset into ``str``, ``OFF_BYTES`` (2, or 3 once the pool
  reaches 0xFFFF bytes) wide.
- A **source mask** is one byte: bit *i* set for ``SOURCES[i]``
  (:data:`SOURCES`: flashrom, flashprog, linux, u-boot, openocd,
  openfpgaloader, spiflash's priority order).
- A **blob table** (``opsets``, ``namelists``, ``conflicts``, ``ext``,
  ``records``) is a run of variable-length blobs, each stored once however
  many entries share it; entries point at a blob by its ``u16`` offset.
- A table is present (a key of :attr:`Layout.tables`) exactly when the
  code compiled for the selection reads it: with the field(s) in parentheses
  after its name. So the C file never holds a table nothing uses (which
  ``-Wunused-const-variable`` would reject).
- **Counted tables.** ``sizes``, ``pages``, ``sectors``, ``volts``,
  ``mfrs``, ``ops`` (with ``opsets``), ``ext`` and ``conflicts`` can have no
  rows in a filtered snapshot (a ``--type nand`` one has no voltages,
  operations, extended ids or conflicts). The C code that indexes such a
  table is compiled only when it has rows (``<NAME>_COUNT``, below), so a
  table with none is left out: nothing reads it, and no compiler sees an
  index into an empty array. The C emitter still pads any 0-byte table to
  one unused byte (C99 has no zero-length arrays), but no reader relies on
  the pad.

Tables
------

``ids`` (always)
    Per base entry, in entry order: ``hdr`` = ``len`` (bits 0-2) | ``type``
    (bit 3: 0 NOR, 1 NAND) | ``family`` (bits 4-6: the index in
    :data:`~uspiflash.model.FAMILIES`), then ``len`` (1-7) id bytes, without
    continuation codes. Ends with a ``0`` byte (``len`` is never 0).
``entries`` (always)
    ``ENTRY_SIZE`` bytes per entry (base entries, then variants), the fields
    at offsets ``E_*`` (below).
``sizes`` (SIZE)
    ``u32`` per distinct size in bytes, sorted ascending.
``pages`` (PAGE_SIZE)
    ``u16`` per distinct page size in bytes, sorted ascending.
``sectors`` (SECTOR_SIZE)
    ``u32`` per distinct sector size in bytes, sorted ascending.
``volts`` (VOLTAGE)
    ``u16`` minimum, ``u16`` maximum (millivolts) per distinct range, sorted
    ascending by (minimum, maximum).
``featsets`` (FEATURES)
    ``u24`` per distinct feature set: bit *i* set for ``FEATURES[i]``
    (:data:`FEATURES`, sorted by value, as ``spiflash id`` prints them).
``ops`` (OPERATIONS)
    ``OP_SIZE`` bytes per stored operation, in stable-id order: stable id
    (the index in :data:`ALL_OPS`), opcode, kind (the index in
    :data:`KINDS`), protocol (the index in :data:`PROTOCOLS`), address bytes,
    dummy clocks (``0xFF`` = varies), data (0 none, 1 read, 2 write), data
    bytes (0 = unbounded); then, with DESCRIPTIONS, name ``OFF`` (at byte
    ``OP_NAME`` = 8) and description ``OFF``. ``OP_COUNT`` rows; only the
    operations some entry keeps are stored.
``opsets`` (OPERATIONS)
    Blobs: count, then per operation: its row index in ``ops``, and, with
    SOURCES, a source mask (who says the chip has it). Operations appear in
    stable-id order.
``namelists`` (NAMES)
    Blobs: count, then ``OFF`` per part name, most-cited first.
``mfrs`` (MANUFACTURER)
    ``OFF`` per distinct manufacturer name, sorted by name.
``conflicts`` (CONFLICTS)
    Blobs, one per distinct list of a chip's conflicts: repeated ``attr``,
    ``n``, ``n x (value index, source mask)``, then ``0xFF``. ``attr`` is the
    index in :data:`CONFLICT_ATTRS` (size, page_size, sector_size, voltage);
    the value index is into ``sizes``, ``pages``, ``sectors`` or ``volts``
    respectively. Attributes and values are in spiflash's order
    (:attr:`~spiflash.model.Flash.conflicts`).
``ext`` (EXT)
    Blobs, one per base entry whose records carry extended ids: ``k``, then
    ``k x (len, len bytes)``: the chip's distinct extended ids, sorted; then
    ``n``, ``n x (u16 mask, u16 entry index)`` in ascending mask order.
    ``k`` is at most 16.
``records`` (RECORDS)
    Blobs, one per entry: ``n``, then per upstream record: source (the index
    in :data:`SOURCES`), name ``OFF``, ext len (0 = no extended id), ext len
    bytes, and with PROVENANCE ``at`` ``OFF`` (the upstream ``file:line``).
``jep106`` (JEP106)
    ``JEP106_COUNT`` rows, sorted by (bank, id): bank, id (with its parity
    bit, as a chip sends it), name ``OFF``.
``str`` (whenever compiled code reads a string, :func:`reads_strings`)
    NUL-terminated printable-ASCII strings with no ``"`` or ``\\``, each
    stored once. The readers are MANUFACTURER (with ``mfrs``), NAMES,
    DESCRIPTIONS (with ``ops``), TEXT, JSON (so RECORDS and PROVENANCE) and
    JEP106.
Name arrays
    ``OFF`` arrays holding each member's value (``str(member)``: ``"nor"``,
    ``"u-boot"``, ``"erase_4k"``), for the printers (:func:`name_arrays`):
    ``featnames`` per :data:`FEATURES`, ``famnames`` per
    :data:`~uspiflash.model.FAMILIES` and ``typenames`` per :data:`TYPES`
    (TEXT or JSON); ``kindnames`` per :data:`KINDS` (JSON, with ``ops``);
    ``srcnames`` per :data:`SOURCES` (SOURCES, and TEXT or JSON);
    ``attrnames`` per :data:`CONFLICT_ATTRS` (CONFLICTS with ``conflicts``,
    and TEXT or JSON). No printer prints an operation's protocol, so there is
    no protocol name array; ``ops`` rows still hold the :data:`PROTOCOLS`
    index.

Entry fields
------------

Present only with their table, in this order, packed:

- ``E_BANK``: the JEP106 bank (continuation codes before the id). Always.
- ``E_SIZE``, ``E_PAGE``, ``E_SECTOR``, ``E_VOLT``, ``E_FEAT`` and ``E_MFR``:
  indices into ``sizes``, ``pages``, ``sectors``, ``volts``, ``featsets`` and
  ``mfrs``; ``0xFF`` = unknown (``E_FEAT`` is never ``0xFF``).
- ``E_SRCS``: a source mask (who has an entry for the chip).
- ``E_NAMES``, ``E_OPS``, ``E_CONF``, ``E_EXT`` and ``E_RECS``: ``u16``
  offsets into ``namelists``, ``opsets``, ``conflicts``, ``ext`` and
  ``records``; ``0xFFFF`` = none. ``E_CONF`` is none for a chip without
  conflicts, ``E_EXT`` for a chip without extended ids and for every variant;
  the others always point at a blob (an empty list is a blob with count 0).

The generator raises :exc:`ValueError` if any index exceeds 254, any offset
exceeds 0xFFFE, any value overflows its field, or ``entries`` or ``ops`` is
over 65,535 bytes (the C computes a row's offset as ``(uint16_t)(entry *
ENTRY_SIZE)``, and likewise with ``OP_SIZE``). M4 revisits widths with
measurements.

Lookup
------

``lookup(family, data)`` (C's ``usf_lookup``, :func:`uspiflash.decode.lookup`):

1. Skip leading ``0x7f`` continuation codes while more than one byte
   remains; the rest is ``core``. The bank is not compared (spiflash ignores
   it too, since many chips leave the codes out).
2. Walk ``ids``, counting entries. An id matches when its ``family`` is
   ``family``, its ``len`` is at most ``len(core)`` and its bytes equal the
   start of ``core``. Keep, per type, the first longest match.
3. The answer is the NOR match, then the NAND match, each narrowed:

Narrowing, with EXT only (without it, the base entry is the answer): let
``x`` be the bytes of ``core`` after the id. If ``x`` is empty, or the base
entry's ``E_EXT`` is ``0xFFFF``, the answer is the base entry. Otherwise form
a mask: bit *i* set when the *i*-th extended id ``e`` of its ``ext`` blob
agrees with ``x``, by spiflash's two-way prefix rule ``e[:len(x)] ==
x[:len(e)]`` (:func:`uspiflash.model.compatible`). The answer is the entry of
the pair whose mask equals it exactly, or the base entry if none does.

Defines
-------

Constants for the C template, in :attr:`Layout.defines`:

- ``ENTRY_COUNT``, ``BASE_COUNT``, ``ENTRY_SIZE`` and each present ``E_*``;
- ``OFF_BYTES``; ``OP_SIZE`` and (with DESCRIPTIONS) ``OP_NAME``;
  ``JEP106_COUNT`` (0 without JEP106);
- the row counts of the counted tables, 0 when the table is absent:
  ``SIZE_COUNT``, ``PAGE_COUNT``, ``SECTOR_COUNT``, ``VOLT_COUNT``,
  ``MFR_COUNT``, ``OP_COUNT`` (rows of ``ops``), ``EXT_COUNT`` and
  ``CONF_COUNT`` (blobs of ``ext`` and ``conflicts``);
- ``LOOKUP_MAX``: ``HAVE_NOR + HAVE_NAND``, the most answers a lookup can
  give (the size of ``usf_lookup``'s output array);
- ``RDID_LEN``: the bytes the probe reads for RDID: max(6, the longest bank +
  id length + longest extended id over the JEDEC-family base entries). Only
  JEDEC answers are looked up from RDID reads; the legacy probes read fixed
  lengths.
- ``HAVE_<FIELD>`` for **every** :class:`~uspiflash.levels.Field`: 1 if
  selected, else 0; ``HAVE_NOR`` and ``HAVE_NAND``: 1 if that chip type is
  among the base entries, else 0; ``HAVE_FAMILY_<NAME>`` for every id family
  in :data:`~uspiflash.model.FAMILIES`: 1 if among them, else 0. Every flag
  is defined, as 0 or 1, so the C's ``#if`` lines are well-defined under
  ``-Wundef``.
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from spiflash.enums import DataPhase, Feature, FlashType, OperationKind, Source
from spiflash.opcodes import OPERATIONS, sort_key

from .levels import Field
from .model import FAMILIES

if TYPE_CHECKING:
    from collections.abc import Iterable

    from spiflash.model import Flash

    from .levels import Selection
    from .model import Snapshot

#: Every operation name, in ``sort_key`` order; the index is the stable id.
ALL_OPS: tuple[str, ...] = tuple(sorted(OPERATIONS, key=sort_key))
#: Features by value, as ``spiflash id`` prints them; bit i of a feature set.
FEATURES: tuple[Feature, ...] = tuple(sorted(Feature))
#: Sources in priority order; bit i of a source mask.
SOURCES: tuple[Source, ...] = tuple(Source)
#: Operation kinds, in spiflash's order.
KINDS: tuple[OperationKind, ...] = tuple(OperationKind)
#: Every operation protocol (``"1-1-4"``), sorted.
PROTOCOLS: tuple[str, ...] = tuple(sorted({o.protocol for o in OPERATIONS.values()}))
#: The attributes whose conflicts are stored, as :attr:`Flash.conflicts` names them.
CONFLICT_ATTRS: tuple[str, ...] = ("size", "page_size", "sector_size", "voltage")
#: Chip types; bit 3 of an id header is the index.
TYPES: tuple[FlashType, ...] = (FlashType.NOR, FlashType.NAND)
NONE8 = 0xFF
NONE16 = 0xFFFF
_PRINTABLE = set(string.printable) - set('\t\n\r\x0b\x0c"\\')
_DATA = {None: 0, DataPhase.READ: 1, DataPhase.WRITE: 2}


class StringPool:
    """NUL-terminated strings, each stored once."""

    def __init__(self) -> None:
        self._data = bytearray()
        self._at: dict[str, int] = {}

    @staticmethod
    def check(s: str) -> None:
        """Refuse strings the C JSON writer would have to escape."""
        if not set(s) <= _PRINTABLE:
            msg = f"not printable ASCII without quotes or backslashes: {s!r}"
            raise ValueError(msg)

    def add(self, s: str) -> int:
        """The offset of ``s``, adding it if new."""
        if s not in self._at:
            self.check(s)
            self._at[s] = len(self._data)
            self._data += s.encode("ascii") + b"\0"
        return self._at[s]

    @property
    def data(self) -> bytes:
        """The pool's bytes."""
        return bytes(self._data)


@dataclass
class Layout:
    """The byte tables, and the constants the C template needs, for one
    selection of one snapshot."""

    selection: Selection
    snapshot: Snapshot
    off_bytes: int
    defines: dict[str, int] = field(default_factory=dict)
    tables: dict[str, bytes] = field(default_factory=dict)
    ops: tuple[str, ...] = ()
    values: dict[str, tuple[object, ...]] = field(default_factory=dict)


def _u16(v: int) -> bytes:
    if not 0 <= v <= NONE16:
        msg = f"{v} does not fit 16 bits"
        raise ValueError(msg)
    return v.to_bytes(2, "little")


def _u8(v: int) -> bytes:
    if not 0 <= v <= NONE8:
        msg = f"{v} does not fit 8 bits"
        raise ValueError(msg)
    return bytes([v])


def _uint(v: int, width: int, what: str) -> bytes:
    """``v`` as ``width`` little-endian bytes; ``ValueError`` if it doesn't fit."""
    if not 0 <= v < 1 << 8 * width:
        msg = f"{what} {v} does not fit {8 * width} bits"
        raise ValueError(msg)
    return v.to_bytes(width, "little")


def _idx(values: tuple[object, ...], v: object) -> int:
    if v is None:
        return NONE8
    i = values.index(v)
    if i >= NONE8:
        msg = f"more than 254 distinct values ({len(values)})"
        raise ValueError(msg)
    return i


def _row_table(name: str, data: bytes) -> bytes:
    """``data``, if every row offset into it fits the C's 16-bit arithmetic."""
    if len(data) > NONE16:
        msg = f"table {name} is {len(data)} bytes, over 65,535"
        raise ValueError(msg)
    return data


class _Blobs:
    """A table of deduplicated byte strings, addressed by u16 offsets."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.data = bytearray()
        self._at: dict[bytes, int] = {}

    def __len__(self) -> int:
        """How many distinct blobs the table holds."""
        return len(self._at)

    def add(self, blob: bytes) -> int:
        """The offset of ``blob``, adding it if new."""
        if blob not in self._at:
            if len(self.data) >= NONE16:
                msg = f"table {self.name} passes offset 0xFFFE ({len(self.data)} bytes)"
                raise ValueError(msg)
            self._at[blob] = len(self.data)
            self.data += blob
        return self._at[blob]


def reads_strings(sel: Selection, *, ops: bool, mfrs: bool) -> bool:
    """Whether C code compiled for ``sel`` reads ``str`` (the template's
    ``USF__NEED_OFF``): ``ops`` and ``mfrs`` say whether those tables have rows."""
    has = sel.has
    return (
        (has(Field.MANUFACTURER) and mfrs)
        or has(Field.NAMES)
        or (has(Field.DESCRIPTIONS) and ops)
        or has(Field.JEP106)
        or has(Field.TEXT)
        or has(Field.JSON)
    )


def name_arrays(
    sel: Selection, *, ops: bool = True, conflicts: bool = True
) -> dict[str, tuple[object, ...]]:
    """The name arrays the printers compiled for ``sel`` read, with their
    members. ``ops`` and ``conflicts`` say whether those tables have rows:
    ``kindnames`` and ``attrnames`` are read only by code indexing them."""
    has = sel.has
    printer = has(Field.TEXT) or has(Field.JSON)
    wanted: tuple[tuple[str, tuple[object, ...], bool], ...] = (
        ("featnames", FEATURES, printer),
        ("srcnames", SOURCES, printer and has(Field.SOURCES)),
        ("famnames", FAMILIES, printer),
        ("kindnames", KINDS, has(Field.JSON) and ops),
        ("attrnames", CONFLICT_ATTRS, printer and has(Field.CONFLICTS) and conflicts),
        ("typenames", TYPES, printer),
    )
    return {table: members for table, members, present in wanted if present}


def _strings(
    snap: Snapshot, sel: Selection, pool: StringPool, ops: tuple[str, ...], *, conflicts: bool
) -> None:
    """Pass 1: every string, so the pool's size (hence offset width) is known."""
    has = sel.has
    for members in name_arrays(sel, ops=bool(ops), conflicts=conflicts).values():
        for member in members:
            pool.add(str(member))
    if has(Field.DESCRIPTIONS):
        for name in ops:
            pool.add(name)
            pool.add(OPERATIONS[name].description)
    for e in snap.entries:
        f = e.flash
        if has(Field.MANUFACTURER) and f.manufacturer:
            pool.add(f.manufacturer)
        if has(Field.NAMES):
            for n in f.names:
                pool.add(n)
        if has(Field.RECORDS):
            for r in f.records:
                pool.add(r.name)
                if has(Field.PROVENANCE):
                    pool.add(r.url)
    if has(Field.JEP106):
        for m in snap.database.manufacturers:
            pool.add(m.name)


def _int_values(snap: Snapshot, attr: str) -> tuple[int, ...]:
    """Every value of integer attribute ``attr`` (size, page_size,
    sector_size) that any entry, or any conflict, mentions, sorted."""
    seen: set[int] = set()
    for e in snap.entries:
        v = getattr(e.flash, attr)
        if v is not None:
            seen.add(v)
        seen.update(e.flash.conflicts.get(attr, {}))
    return tuple(sorted(seen))


def _volt_values(snap: Snapshot) -> tuple[tuple[int, int], ...]:
    """Every voltage range any entry, or any conflict, mentions, sorted."""
    seen: set[tuple[int, int]] = set()
    for e in snap.entries:
        if e.flash.voltage is not None:
            seen.add((e.flash.voltage[0], e.flash.voltage[1]))
        seen.update((v[0], v[1]) for v in e.flash.conflicts.get("voltage", {}))
    return tuple(sorted(seen))


def _ops_of(f: Flash, sel: Selection) -> list[str]:
    """The operation names of ``f`` that ``sel``'s operation kinds keep."""
    return [n for n, o in f.opcodes.items() if o.operation.kind in sel.op_kinds]


def mask(sources: Iterable[Source]) -> int:
    """The source mask: bit i for ``SOURCES[i]``."""
    return sum(1 << SOURCES.index(s) for s in sources)


def _value(attr: str, v: object) -> object:
    """A conflict value as its value table holds it (voltages as plain pairs)."""
    if attr == "voltage" and isinstance(v, tuple):
        return (v[0], v[1])
    return v


#: Entry fields: name, width, the field that makes them present.
_ENTRY_FIELDS: tuple[tuple[str, int, Field], ...] = (
    ("BANK", 1, Field.IDENT),
    ("SIZE", 1, Field.SIZE),
    ("PAGE", 1, Field.PAGE_SIZE),
    ("SECTOR", 1, Field.SECTOR_SIZE),
    ("VOLT", 1, Field.VOLTAGE),
    ("FEAT", 1, Field.FEATURES),
    ("MFR", 1, Field.MANUFACTURER),
    ("SRCS", 1, Field.SOURCES),
    ("NAMES", 2, Field.NAMES),
    ("OPS", 2, Field.OPERATIONS),
    ("CONF", 2, Field.CONFLICTS),
    ("EXT", 2, Field.EXT),
    ("RECS", 2, Field.RECORDS),
)
#: Each conflict attribute's value table.
_ATTR_TABLE = {"size": "sizes", "page_size": "pages", "sector_size": "sectors", "voltage": "volts"}


def build(snap: Snapshot, sel: Selection) -> Layout:
    """The baseline tables for ``sel`` over ``snap``."""
    has = sel.has
    used = {n for e in snap.entries for n in _ops_of(e.flash, sel)}
    ops = tuple(n for n in ALL_OPS if has(Field.OPERATIONS) and n in used)
    any_conflicts = has(Field.CONFLICTS) and any(e.flash.conflicts for e in snap.entries)
    pool = StringPool()
    _strings(snap, sel, pool, ops, conflicts=any_conflicts)
    pool_size = len(pool.data)
    lay = Layout(sel, snap, off_bytes=2 if pool_size < NONE16 else 3, ops=ops)
    tables, defines, values = lay.tables, lay.defines, lay.values
    bases = [snap.entries[i].flash for i in range(snap.n_base)]

    def off(s: str) -> bytes:
        return pool.add(s).to_bytes(lay.off_bytes, "little")

    # ids
    ids = bytearray()
    for f in bases:
        if not 1 <= len(f.id) <= 7:
            msg = f"id {f.id.hex()} is not 1-7 bytes"
            raise ValueError(msg)
        typ = 8 if f.type is FlashType.NAND else 0
        ids += bytes([len(f.id) | typ | FAMILIES.index(f.family) << 4]) + f.id
    tables["ids"] = bytes(ids) + b"\0"

    # Value tables.
    widths = {"sizes": 4, "pages": 2, "sectors": 4}
    for table, attr, fld in (
        ("sizes", "size", Field.SIZE),
        ("pages", "page_size", Field.PAGE_SIZE),
        ("sectors", "sector_size", Field.SECTOR_SIZE),
    ):
        if has(fld):
            ints = _int_values(snap, attr)
            values[table] = ints
            tables[table] = b"".join(_uint(v, widths[table], attr) for v in ints)
    if has(Field.VOLTAGE):
        volts = _volt_values(snap)
        values["volts"] = volts
        tables["volts"] = b"".join(
            _uint(lo, 2, "voltage") + _uint(hi, 2, "voltage") for lo, hi in volts
        )

    # featsets
    featsets: dict[frozenset[Feature], int] = {}
    if has(Field.FEATURES):
        for e in snap.entries:
            featsets.setdefault(e.flash.features, len(featsets))
        tables["featsets"] = b"".join(
            _uint(sum(1 << FEATURES.index(x) for x in fs), 3, "feature set") for fs in featsets
        )

    # ops and opsets
    opsets = _Blobs("opsets")
    if has(Field.OPERATIONS):
        rows = bytearray()
        for name in ops:
            op = OPERATIONS[name]
            rows += bytes(
                [
                    ALL_OPS.index(name),
                    op.opcode,
                    KINDS.index(op.kind),
                    PROTOCOLS.index(op.protocol),
                    op.address_bytes,
                    NONE8 if op.dummy_clocks is None else op.dummy_clocks,
                    _DATA[op.data],
                ]
            ) + _u8(op.data_bytes or 0)
            if has(Field.DESCRIPTIONS):
                rows += off(name) + off(op.description)
        tables["ops"] = _row_table("ops", bytes(rows))
        defines["OP_SIZE"] = 8 + (2 * lay.off_bytes if has(Field.DESCRIPTIONS) else 0)
        if has(Field.DESCRIPTIONS):
            defines["OP_NAME"] = 8

    # Per-entry blobs.
    namelists = _Blobs("namelists")
    conflicts = _Blobs("conflicts")
    ext = _Blobs("ext")
    records = _Blobs("records")
    mfrs = tuple(sorted({m for e in snap.entries if (m := e.flash.manufacturer)}))
    if has(Field.MANUFACTURER):
        values["mfrs"] = mfrs
        tables["mfrs"] = b"".join(off(m) for m in mfrs)

    ext_at: dict[int, int] = {}
    if has(Field.EXT):
        for i, eids in snap.ext.items():
            if len(eids) > 16:
                msg = f"{len(eids)} extended ids do not fit a 16-bit mask"
                raise ValueError(msg)
            blob = _u8(len(eids)) + b"".join(_u8(len(x)) + x for x in eids)
            variants = snap.variants.get(i, {})
            blob += _u8(len(variants))
            blob += b"".join(_u16(m) + _u16(variants[m]) for m in sorted(variants))
            ext_at[i] = ext.add(blob)

    rows = bytearray()
    for i, e in enumerate(snap.entries):
        f = e.flash
        row = bytearray(_u8(f.bank))
        if has(Field.SIZE):
            row += _u8(_idx(values["sizes"], f.size))
        if has(Field.PAGE_SIZE):
            row += _u8(_idx(values["pages"], f.page_size))
        if has(Field.SECTOR_SIZE):
            row += _u8(_idx(values["sectors"], f.sector_size))
        if has(Field.VOLTAGE):
            row += _u8(_idx(values["volts"], _value("voltage", f.voltage)))
        if has(Field.FEATURES):
            row += _u8(_idx(tuple(featsets), f.features))
        if has(Field.MANUFACTURER):
            row += _u8(_idx(mfrs, f.manufacturer))
        if has(Field.SOURCES):
            row += _u8(mask(f.sources))
        if has(Field.NAMES):
            row += _u16(namelists.add(_u8(len(f.names)) + b"".join(off(n) for n in f.names)))
        if has(Field.OPERATIONS):
            kept = [o for o in f.opcodes.values() if o.operation.kind in sel.op_kinds]
            blob = _u8(len(kept)) + b"".join(
                _u8(_idx(ops, o.name)) + (_u8(mask(o.sources)) if has(Field.SOURCES) else b"")
                for o in kept
            )
            row += _u16(opsets.add(blob))
        if has(Field.CONFLICTS):
            conf = f.conflicts
            if conf:
                conf_blob = bytearray()
                for attr, vals in conf.items():
                    conf_blob += _u8(CONFLICT_ATTRS.index(attr)) + _u8(len(vals))
                    for v, srcs in vals.items():
                        vi = _idx(values[_ATTR_TABLE[attr]], _value(attr, v))
                        conf_blob += _u8(vi) + _u8(mask(srcs))
                row += _u16(conflicts.add(bytes(conf_blob) + bytes([NONE8])))
            else:
                row += _u16(NONE16)
        if has(Field.EXT):
            row += _u16(ext_at.get(i, NONE16))
        if has(Field.RECORDS):
            recs = bytearray(_u8(len(f.records)))
            for r in f.records:
                x = r.ext_id or b""
                recs += _u8(SOURCES.index(r.source)) + off(r.name) + _u8(len(x)) + x
                if has(Field.PROVENANCE):
                    recs += off(r.url)
            row += _u16(records.add(bytes(recs)))
        rows += row

    # Entry offsets.
    at = 0
    for name, width, fld in _ENTRY_FIELDS:
        if has(fld) or name == "BANK":
            defines[f"E_{name}"] = at
            at += width
    defines["ENTRY_SIZE"] = at
    if len(rows) != at * len(snap.entries):
        msg = "entry rows disagree with ENTRY_SIZE"
        raise AssertionError(msg)
    tables["entries"] = _row_table("entries", bytes(rows))
    for blobs, fld in (
        (namelists, Field.NAMES),
        (opsets, Field.OPERATIONS),
        (conflicts, Field.CONFLICTS),
        (ext, Field.EXT),
        (records, Field.RECORDS),
    ):
        if has(fld):
            tables[blobs.name] = bytes(blobs.data)

    # jep106
    jep = sorted(snap.database.manufacturers, key=lambda m: (m.bank, m.id))
    if has(Field.JEP106):
        tables["jep106"] = b"".join(_u8(m.bank) + _u8(m.id) + off(m.name) for m in jep)

    # Strings.
    for table, members in name_arrays(sel, ops=bool(ops), conflicts=any_conflicts).items():
        tables[table] = b"".join(off(str(n)) for n in members)
    if len(pool.data) != pool_size:
        msg = "a string was added after the offset width was chosen"
        raise AssertionError(msg)
    if reads_strings(sel, ops=bool(ops), mfrs=bool(mfrs)):
        tables["str"] = pool.data

    # Counted tables: their readers are compiled only when they have rows,
    # so one with none is left out (see "Counted tables" above).
    counts = {
        "SIZE_COUNT": ("sizes", len(values.get("sizes", ()))),
        "PAGE_COUNT": ("pages", len(values.get("pages", ()))),
        "SECTOR_COUNT": ("sectors", len(values.get("sectors", ()))),
        "VOLT_COUNT": ("volts", len(values.get("volts", ()))),
        "MFR_COUNT": ("mfrs", len(values.get("mfrs", ()))),
        "OP_COUNT": ("ops", len(ops)),
        "EXT_COUNT": ("ext", len(ext)),
        "CONF_COUNT": ("conflicts", len(conflicts)),
    }
    for name, (table, n) in counts.items():
        defines[name] = n
        if not n:
            tables.pop(table, None)
    if not ops:
        tables.pop("opsets", None)

    # Defines.
    defines["ENTRY_COUNT"] = len(snap.entries)
    defines["BASE_COUNT"] = snap.n_base
    defines["OFF_BYTES"] = lay.off_bytes
    defines["JEP106_COUNT"] = len(jep) if has(Field.JEP106) else 0
    for fld in Field:
        defines[f"HAVE_{fld.name}"] = int(has(fld))
    for flash_type in TYPES:
        defines[f"HAVE_{flash_type.name}"] = int(any(f.type is flash_type for f in bases))
    for fam in FAMILIES:
        defines[f"HAVE_FAMILY_{fam.name}"] = int(any(f.family is fam for f in bases))
    defines["LOOKUP_MAX"] = defines["HAVE_NOR"] + defines["HAVE_NAND"]
    longest = 0
    for i, f in enumerate(bases):
        if f.family is FAMILIES[0]:
            longest = max(longest, f.bank + len(f.id) + max(map(len, snap.ext.get(i, (b"",)))))
    defines["RDID_LEN"] = max(6, longest)
    return lay
