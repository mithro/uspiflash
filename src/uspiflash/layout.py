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
- A **source mask** has bit *i* set for ``SOURCES[i]`` (:data:`SOURCES`:
  flashrom, flashprog, linux, u-boot, dediprog, rockchip, openocd,
  openfpgaloader, imsprog, qemu, zephyr, spiflash's priority order). How a
  selection stores masks is chosen per selection (:class:`SourceMasks`),
  the smallest of:

  - one byte each (``SRC_BYTES`` 1), while every mask fits eight bits;
  - otherwise two bytes (``SRC_BYTES`` 2), with ``E_SRCS`` a one-byte index
    into ``srcmasks`` (``SRCMASK_COUNT`` rows) when that table is smaller
    than a second byte in every entry; and an operation's or a conflict
    value's mask stored **relative** to its entry's (``SRC_REL``) when that
    saves more than the code reading it costs (:data:`REL_CODE`): bit *j*
    stands for the entry mask's *j*-th set bit (:func:`relative`), in one
    byte, or two when the entry has more than eight sources
    (:func:`rel_bytes`). A mask item below (in ``opsets`` and
    ``conflicts``) is that relative mask, or the mask itself, ``SRC_BYTES``
    wide.

  Two bytes hold sixteen sources: :func:`build` refuses a 17th
  (:func:`check_sources`).
- A **blob table** (``opsets``, ``namelists``, ``conflicts``, ``ext``,
  ``records``, ``dslists``) is a run of variable-length blobs, each stored
  once however many entries share it; entries point at a blob by its
  ``u16`` offset.
- A table is present (a key of :attr:`Layout.tables`) exactly when the
  code compiled for the selection reads it: with the field(s) in parentheses
  after its name. So the C file never holds a table nothing uses (which
  ``-Wunused-const-variable`` would reject).
- **Counted tables.** ``sizes``, ``pages``, ``sectors``, ``volts``,
  ``mfrs``, ``ops`` (with ``opsets``), ``ext``, ``conflicts``, ``dsrows``
  (with ``dslists``) and ``sfdprows`` (with ``sfdplines`` and ``sfdptree``)
  can have no rows in a filtered snapshot (a ``--type nand`` one has no
  voltages or SFDP dumps; a chip may have no datasheet). The C code that
  indexes such a
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
    continuation codes; then a header with ``ID_ALIAS`` (bit 7) set and no
    bytes for each of the chip's shorter ids (a SPI NAND chip's, from
    sources matching fewer of its bytes: :attr:`Flash.ids
    <spiflash.model.Flash.ids>`), longest first: each is the first ``len``
    bytes of the chip's id. Ends with a ``0`` byte (``len`` is never 0).
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
    SOURCES, a mask item (who says the chip has it). Operations appear in
    stable-id order.
``namelists`` (NAMES)
    Blobs: count, then ``OFF`` per part name, most-cited first.
``mfrs`` (MANUFACTURER)
    ``OFF`` per distinct manufacturer name that a source gives, sorted by
    name; then (from row ``MFR_INFERRED``) per distinct one spiflash infers
    for a chip no source names one for
    (:attr:`~spiflash.model.Flash.manufacturer_inferred`), sorted.
``conflicts`` (CONFLICTS, and TEXT or JSON: :func:`stores_conflicts`)
    Blobs, one per distinct list of a chip's conflicts: repeated ``attr``,
    ``n``, ``n x (value index, mask item)``, then ``0xFF``. ``attr`` is the
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
``dsrows`` (DATASHEET or DATASHEETS)
    ``DS_ROW`` bytes per stored datasheet, sorted by URL: URL ``OFF``; then,
    with DATASHEETS, title ``OFF``, revision ``OFF`` (``NONE_OFF`` = none),
    ``u16`` year, month and day (all three 0 = no date; a year is 1000 or
    later, as the C prints it without zero padding), and official (0 or 1).
    Title and revision are stored JSON-escaped (below). ``DS_COUNT`` rows: with
    DATASHEETS every datasheet of a chip, with DATASHEET alone only each
    chip's best (the one the text line prints).
``dslists`` (DATASHEET or DATASHEETS)
    Blobs: ``n``, then ``n x`` (``u16`` row index in ``dsrows``, and with
    DATASHEETS id confirmed, 0 or 1: whether the document gives the chip's
    id), best first as spiflash ranks them. With DATASHEET alone ``n`` is at
    most 1.
``sfdprows`` (SFDP_SUMMARY with TEXT, or SFDP_DUMPS)
    ``SFDP_ROW`` bytes per entry whose records carry an SFDP dump, in entry
    order: ``u16`` entry index; with ``sfdplines``, at ``SFDP_LINES``, a
    ``u16`` offset into ``sfdplines``; with SFDP_DUMPS, at ``SFDP_TREE``, a
    ``u16`` offset into ``sfdptree``. ``SFDP_COUNT`` rows (13 at spiflash
    0.0.post173: 11 chip ids and 2 extended-id variants). An entry without a
    row has no dump; the C finds a row by scanning (no ``E_*`` field: two
    bytes per entry would cost more than the rows).
``sfdplines`` (SFDP_SUMMARY with TEXT: :func:`stores_sfdp_lines`)
    Blobs: ``n``, then ``n x OFF``: the text after ``"    sfdp: "`` of each of
    the entry's ``sfdp:`` lines, as ``spiflash id`` prints them
    (``<summary>  [<source>: <parts>]``, :func:`sfdp_lines`).
``sfdptree`` (SFDP_DUMPS)
    Blobs, one per distinct JSON ``"sfdp"`` value (:func:`sfdp_json`): the
    value as a flat run of tokens in document order, ending with ``T_END``
    (0). A token is one byte, its kind in bits 0-6 and ``T_ITEM`` (bit 7)
    set on a value that is an array element; then ``T_INT``: ``u32``;
    ``T_STR`` and ``T_KEY`` (an object member's name; its value follows):
    ``OFF``, stored JSON-escaped; ``T_NULL``, ``T_FALSE``, ``T_TRUE``,
    ``T_LIST``, ``T_DICT``, ``T_LIST_END`` and ``T_DICT_END``: nothing. A
    ``T_KEY`` always starts a member, so the reader writes the member
    separator before it unasked; ``T_ITEM`` is never set on ``T_KEY``,
    ``T_LIST_END`` or ``T_DICT_END``. Flat, so the C walks it in one loop,
    without recursion.
``srcmasks`` (SOURCES, when ``SRCMASK_COUNT`` is not 0)
    ``u16`` per distinct entry source mask, sorted ascending.
``difflines`` (TEXT)
    ``2 + OFF_BYTES`` bytes per ``parts differ on`` line (where parts that
    extended ids tell apart differ, :meth:`~spiflash.model.Flash.by_ext_id`),
    in entry order: ``u16`` entry index, then ``OFF`` of the text after
    ``"    parts differ on "`` (:func:`diff_lines`). ``DIFF_COUNT`` rows;
    the C prints every row of the entry, by scanning.
``str`` (whenever compiled code reads a string, :func:`reads_strings`)
    NUL-terminated printable-ASCII strings with no ``"`` or ``\\``, each
    stored once. The readers are MANUFACTURER (with ``mfrs``), NAMES,
    DESCRIPTIONS (with ``ops``), TEXT (so DATASHEET), JSON (so RECORDS,
    PROVENANCE, DATASHEETS and SFDP_DUMPS) and JEP106. The one exception to
    the character rule: datasheet titles and revisions and every
    ``sfdptree`` string, which only JSON prints, are stored as
    ``json.dumps`` writes them between the quotes (ASCII, with
    ``\\u00d7``-style escapes; :meth:`StringPool.add_json`). URLs,
    ``sfdp:`` lines and ``parts differ on`` lines follow the rule.
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
- ``E_SRCS``: the entry's source mask (who has an entry for the chip),
  ``SRC_BYTES`` wide, or with ``SRCMASK_COUNT`` its index in ``srcmasks``.
- ``E_NAMES``, ``E_OPS``, ``E_CONF``, ``E_EXT``, ``E_RECS`` and ``E_DS``:
  ``u16`` offsets into ``namelists``, ``opsets``, ``conflicts``, ``ext``,
  ``records`` and ``dslists``; ``0xFFFF`` = none. ``E_DS`` is present with
  DATASHEET or DATASHEETS (even when ``DS_COUNT`` is 0 and nothing reads
  it, as ``E_OPS`` is when ``OP_COUNT`` is). ``E_CONF`` is present exactly
  when the ``conflicts`` table is: conflicts are only ever printed, so
  selecting CONFLICTS without a printer adds nothing. It is none for a chip
  without conflicts, ``E_EXT`` for a chip without extended ids and for every
  variant; the others always point at a blob (an empty list is a blob with
  count 0).

The generator raises :exc:`ValueError` if any index exceeds 254, any value
overflows its field, a blob table's ``u16`` offsets would pass 0xFFFE, the
string pool reaches ``NONE_OFF`` bytes (so no ``OFF``, 2 or 3 bytes wide, is
ever ``NONE_OFF``), two datasheets share a URL, a datasheet is dated before
the year 1000, or ``entries``, ``ops`` or ``dsrows`` is over 65,535 bytes
(the C computes a row's offset as ``(uint16_t)(entry * ENTRY_SIZE)``, and
likewise with ``OP_SIZE`` and ``DS_ROW``). M4 revisits widths with
measurements.

Lookup
------

``lookup(family, data)`` (C's ``usf_lookup``, :func:`uspiflash.decode.lookup`):

1. Skip leading ``0x7f`` continuation codes while more than one byte
   remains; the rest is ``core``. The bank is not compared (spiflash ignores
   it too, since many chips leave the codes out).
2. Walk ``ids``, counting entries (a shorter id is its chip's). An id
   matches when its ``family`` is ``family``, its ``len`` is at most
   ``len(core)`` and its bytes equal the start of ``core``. Keep, per type,
   the first longest match.
3. The answer is the NOR match, then the NAND match, each narrowed:

Narrowing, with EXT only (without it, the base entry is the answer): let
``x`` be the bytes of ``core`` after the id that matched (a chip with
shorter ids has no extended ids: :meth:`Snapshot.build
<uspiflash.model.Snapshot.build>` refuses one). If ``x`` is empty, or the base
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
- ``SRC_BYTES``, ``SRC_REL`` and ``SRCMASK_COUNT``: how source masks are
  stored (above; 1, 0 and 0 without SOURCES);
- the row counts of the counted tables, 0 when the table is absent:
  ``SIZE_COUNT``, ``PAGE_COUNT``, ``SECTOR_COUNT``, ``VOLT_COUNT``,
  ``MFR_COUNT``, ``OP_COUNT`` (rows of ``ops``), ``EXT_COUNT`` and
  ``CONF_COUNT`` (blobs of ``ext`` and ``conflicts``), ``DS_COUNT``
  (rows of ``dsrows``), ``SFDP_COUNT`` (rows of ``sfdprows``) and
  ``DIFF_COUNT`` (rows of ``difflines``);
- ``ALIAS_COUNT``: the shorter ids in ``ids``;
- ``MFR_INFERRED``: the first inferred manufacturer's row in ``mfrs``
  (``MFR_COUNT`` when none is; 0 without MANUFACTURER);
- with DATASHEET or DATASHEETS: ``DS_ROW`` (the ``dsrows`` row size),
  ``DS_ITEM`` (a ``dslists`` item's size: 2, or 3 with DATASHEETS) and
  ``NONE_OFF`` (``2 ** (8 * OFF_BYTES) - 1``, which no real offset
  reaches: the generator refuses a pool that large);
- with ``sfdprows``: ``SFDP_ROW`` (the ``sfdprows`` row size), and
  ``SFDP_LINES`` and ``SFDP_TREE`` (offsets in a row) with their fields;
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

import json
import string
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from spiflash.cli import describe
from spiflash.enums import DataPhase, Feature, FlashType, IdFamily, OperationKind, Source
from spiflash.opcodes import OPERATIONS, sort_key

from .levels import Field
from .model import FAMILIES

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from spiflash.model import Datasheet, Flash

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
#: ``sfdptree`` token kinds (bits 0-6 of a token's first byte).
T_END, T_NULL, T_FALSE, T_TRUE, T_INT, T_STR, T_KEY = 0, 1, 2, 3, 4, 5, 6
T_LIST, T_DICT, T_LIST_END, T_DICT_END = 7, 8, 9, 10
#: Set on a token whose value is an array element: the C writes the separator.
T_ITEM = 0x80
#: Set on an ``ids`` header that is a shorter id of the chip before it.
ID_ALIAS = 0x80
_SFDP_LINE = "    sfdp: "
_DIFF_LINE = "    parts differ on "
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
        """The offset of ``s``, adding it if new. Checked every time, so an
        escaped string :meth:`add_json` stored is never handed out as raw text."""
        self.check(s)
        return self._store(s)

    def add_json(self, s: str) -> int:
        """The offset of ``s`` as a JSON string's body (``json.dumps(s)``
        without its quotes: ASCII, already escaped), adding it if new. For
        strings that only ever appear inside JSON quotes; plain printable
        ASCII is its own body, so it shares :meth:`add`'s copy."""
        return self._store(json.dumps(s)[1:-1])

    def _store(self, s: str) -> int:
        if s not in self._at:
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


def stores_conflicts(sel: Selection) -> bool:
    """Whether ``sel`` stores conflicts (the ``conflicts`` table and
    ``E_CONF``): CONFLICTS and a printer (TEXT or JSON), the only readers."""
    return sel.has(Field.CONFLICTS) and (sel.has(Field.TEXT) or sel.has(Field.JSON))


def stores_sfdp_lines(sel: Selection) -> bool:
    """Whether ``sel`` stores the ``sfdp:`` lines (``sfdplines``):
    SFDP_SUMMARY and TEXT, their only printer."""
    return sel.has(Field.SFDP_SUMMARY) and sel.has(Field.TEXT)


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
        ("attrnames", CONFLICT_ATTRS, stores_conflicts(sel) and conflicts),
        ("typenames", TYPES, printer),
    )
    return {table: members for table, members, present in wanted if present}


def _strings(
    snap: Snapshot,
    sel: Selection,
    pool: StringPool,
    ops: tuple[str, ...],
    sheets: tuple[Datasheet, ...],
    *,
    conflicts: bool,
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
        if stores_sfdp_lines(sel):
            for line in sfdp_lines(f):
                pool.add(line)
        if has(Field.TEXT):
            for line in diff_lines(f):
                pool.add(line)
        if has(Field.SFDP_DUMPS):
            for s in _json_strings(sfdp_json(f)):
                pool.add_json(s)
    if has(Field.JEP106):
        for m in snap.database.manufacturers:
            pool.add(m.name)
    for d in sheets:
        pool.add(d.url)
        if has(Field.DATASHEETS):
            pool.add_json(d.title)
            if d.revision is not None:
                pool.add_json(d.revision)


def sfdp_lines(f: Flash) -> list[str]:
    """What follows ``"    sfdp: "`` on each of ``f``'s ``sfdp:`` lines, taken
    from ``spiflash id``'s own text so the two cannot differ."""
    if not f.sfdp_dumps:
        return []
    lines = describe(f).split("\n")
    return [line[len(_SFDP_LINE) :] for line in lines if line.startswith(_SFDP_LINE)]


def diff_lines(f: Flash) -> list[str]:
    """What follows ``"    parts differ on "`` on each of ``f``'s lines
    giving the values that parts its extended ids tell apart differ on
    (:meth:`~spiflash.model.Flash.by_ext_id`), taken from ``spiflash id``'s
    own text."""
    if not any(r.ext_id for r in f.records):
        return []
    lines = describe(f).split("\n")
    return [line[len(_DIFF_LINE) :] for line in lines if line.startswith(_DIFF_LINE)]


def _maker(f: Flash) -> tuple[str, bool] | None:
    """``f``'s manufacturer, and whether it is inferred; ``None`` if unknown."""
    return (f.manufacturer, f.manufacturer_inferred) if f.manufacturer else None


def sfdp_json(f: Flash) -> list[Any]:
    """``f``'s JSON ``"sfdp"`` value (spiflash's own :meth:`Flash.to_json`),
    as plain JSON types: its enums become the strings ``json.dumps`` writes."""
    if not f.sfdp_dumps:
        return []
    value: list[Any] = json.loads(json.dumps(f.to_json()["sfdp"]))
    return value


def _json_strings(v: object) -> Iterator[str]:
    """Every member name and string value in JSON value ``v``."""
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from _json_strings(x)
    elif isinstance(v, dict):
        for k, x in v.items():
            yield str(k)
            yield from _json_strings(x)


def sfdp_tree(v: object, off: Callable[[str], bytes], *, item: bool = False) -> bytes:
    """JSON value ``v`` as ``sfdptree`` tokens, without the final ``T_END``;
    ``off`` gives a string's ``OFF``."""
    flag = T_ITEM if item else 0
    if v is None:
        return _u8(T_NULL | flag)
    if isinstance(v, bool):
        return _u8((T_TRUE if v else T_FALSE) | flag)
    if isinstance(v, int):
        return _u8(T_INT | flag) + _uint(v, 4, "SFDP JSON integer")
    if isinstance(v, str):
        return _u8(T_STR | flag) + off(v)
    if isinstance(v, list):
        body = b"".join(sfdp_tree(x, off, item=True) for x in v)
        return _u8(T_LIST | flag) + body + _u8(T_LIST_END)
    if isinstance(v, dict):
        body = b"".join(_u8(T_KEY) + off(str(k)) + sfdp_tree(x, off) for k, x in v.items())
        return _u8(T_DICT | flag) + body + _u8(T_DICT_END)
    msg = f"no sfdptree token for {v!r}"
    raise ValueError(msg)


def _datasheets(f: Flash, sel: Selection) -> tuple[Datasheet, ...]:
    """The datasheets of ``f`` that ``sel`` stores: all of them with
    DATASHEETS, the best alone with DATASHEET (the text line), else none."""
    if sel.has(Field.DATASHEETS):
        return f.datasheets
    return f.datasheets[:1] if sel.has(Field.DATASHEET) else ()


def _sheets(snap: Snapshot, sel: Selection) -> tuple[Datasheet, ...]:
    """The ``dsrows`` rows: each distinct stored datasheet, sorted by URL."""
    by_url: dict[str, Datasheet] = {}
    for e in snap.entries:
        for d in _datasheets(e.flash, sel):
            if by_url.setdefault(d.url, d) != d:
                msg = f"two datasheets share the URL {d.url}"
                raise ValueError(msg)
    return tuple(by_url[u] for u in sorted(by_url))


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


def check_sources(sources: tuple[Source, ...] = SOURCES) -> None:
    """Refuse more sources than a two-byte source mask holds."""
    if len(sources) > 16:
        names = ", ".join(sources)
        msg = (
            f"spiflash has {len(sources)} sources ({names}), but a source mask is at "
            "most two bytes: widen the mask (layout, template and decode) for the 17th"
        )
        raise ValueError(msg)


def mask(sources: Iterable[Source]) -> int:
    """The source mask: bit i for ``SOURCES[i]``."""
    return sum(1 << SOURCES.index(s) for s in sources)


def relative(sub: int, full: int) -> int:
    """Source mask ``sub`` relative to ``full``, which holds every bit of it:
    bit j set when ``full``'s j-th set bit (counting from bit 0) is set in
    ``sub``."""
    if sub & ~full:
        msg = f"source mask {sub:#x} is not within {full:#x}"
        raise ValueError(msg)
    out = j = 0
    for i in range(full.bit_length()):
        if full >> i & 1:
            out |= (sub >> i & 1) << j
            j += 1
    return out


#: About what reading relative source masks (``usf__srcw``, ``usf__srcmask``)
#: costs in code, in bytes, on the ledger's targets: 250 to 500.
REL_CODE = 512


def rel_bytes(full: int) -> int:
    """The bytes of a mask relative to ``full``: 1, or 2 past eight sources."""
    return 1 if full.bit_count() <= 8 else 2


@dataclass(frozen=True)
class SourceMasks:
    """How a selection stores its source masks (``SRC_BYTES``, ``SRC_REL``
    and ``SRCMASK_COUNT``; see "Source masks" above)."""

    #: ``SRC_BYTES``: an absolute mask's width; 1 while every mask fits 8 bits.
    width: int
    #: ``SRC_REL``: operations' and conflicts' masks are relative to the entry's.
    rel: bool
    #: ``srcmasks``: the distinct entry masks, sorted, when ``E_SRCS`` is an
    #: index into them; empty when ``E_SRCS`` holds the mask itself.
    table: tuple[int, ...]

    @classmethod
    def choose(cls, snap: Snapshot, sel: Selection) -> SourceMasks:
        """The smallest storage for ``snap``'s masks: one byte each while
        every mask fits. Past that, entry masks as indices into a table of
        the distinct ones, when that is smaller than two bytes per entry; and
        operations' and conflicts' masks relative to their entry's, when the
        bytes that saves (one per mask in an entry of at most eight sources)
        are more than the code reading them costs (:data:`REL_CODE`). Without
        SOURCES there are none: one byte, which nothing reads."""
        if not sel.has(Field.SOURCES):
            return cls(1, rel=False, table=())
        widest = saved = 0
        entries: set[int] = set()
        for e in snap.entries:
            f = e.flash
            full = mask(f.sources)
            entries.add(full)
            widest |= full
            if full.bit_count() <= 8:
                saved += len(_ops_of(f, sel)) if sel.has(Field.OPERATIONS) else 0
                saved += sum(map(len, f.conflicts.values())) if stores_conflicts(sel) else 0
        if widest < 1 << 8:
            return cls(1, rel=False, table=())
        small = len(entries) < NONE8 and 2 * len(entries) < len(snap.entries)
        table = tuple(sorted(entries)) if small else ()
        return cls(2, rel=saved > REL_CODE, table=table)

    @property
    def entry_bytes(self) -> int:
        """``E_SRCS``'s width."""
        return 1 if self.table else self.width

    def entry(self, full: int) -> bytes:
        """``E_SRCS`` for entry mask ``full``."""
        if self.table:
            return _u8(self.table.index(full))
        return _uint(full, self.width, "source mask")

    def item(self, sub: int, full: int) -> bytes:
        """The stored form of an operation's or a conflict value's mask
        ``sub``, in an entry whose mask is ``full``."""
        if self.rel:
            return _uint(relative(sub, full), rel_bytes(full), "relative source mask")
        return _uint(sub, self.width, "source mask")


def _value(attr: str, v: object) -> object:
    """A conflict value as its value table holds it (voltages as plain pairs)."""
    if attr == "voltage" and isinstance(v, tuple):
        return (v[0], v[1])
    return v


#: Entry fields: name, width, the fields that make them present (any of them).
_ENTRY_FIELDS: tuple[tuple[str, int, frozenset[Field]], ...] = (
    ("BANK", 1, frozenset({Field.IDENT})),
    ("SIZE", 1, frozenset({Field.SIZE})),
    ("PAGE", 1, frozenset({Field.PAGE_SIZE})),
    ("SECTOR", 1, frozenset({Field.SECTOR_SIZE})),
    ("VOLT", 1, frozenset({Field.VOLTAGE})),
    ("FEAT", 1, frozenset({Field.FEATURES})),
    ("MFR", 1, frozenset({Field.MANUFACTURER})),
    ("SRCS", 1, frozenset({Field.SOURCES})),
    ("NAMES", 2, frozenset({Field.NAMES})),
    ("OPS", 2, frozenset({Field.OPERATIONS})),
    ("CONF", 2, frozenset({Field.CONFLICTS})),  # only with a printer: stores_conflicts()
    ("EXT", 2, frozenset({Field.EXT})),
    ("RECS", 2, frozenset({Field.RECORDS})),
    ("DS", 2, frozenset({Field.DATASHEET, Field.DATASHEETS})),
)
#: Each conflict attribute's value table.
_ATTR_TABLE = {"size": "sizes", "page_size": "pages", "sector_size": "sectors", "voltage": "volts"}


def build(snap: Snapshot, sel: Selection) -> Layout:
    """The baseline tables for ``sel`` over ``snap``."""
    check_sources()
    has = sel.has
    used = {n for e in snap.entries for n in _ops_of(e.flash, sel)}
    ops = tuple(n for n in ALL_OPS if has(Field.OPERATIONS) and n in used)
    with_conflicts = stores_conflicts(sel)
    any_conflicts = with_conflicts and any(e.flash.conflicts for e in snap.entries)
    with_ds = has(Field.DATASHEET) or has(Field.DATASHEETS)
    sheets = _sheets(snap, sel)
    pool = StringPool()
    _strings(snap, sel, pool, ops, sheets, conflicts=any_conflicts)
    pool_size = len(pool.data)
    lay = Layout(sel, snap, off_bytes=2 if pool_size < NONE16 else 3, ops=ops)
    none_off = (1 << 8 * lay.off_bytes) - 1
    if pool_size >= none_off:
        msg = f"the string pool is {pool_size} bytes, over {none_off - 1}"
        raise ValueError(msg)
    tables, defines, values = lay.tables, lay.defines, lay.values
    bases = [snap.entries[i].flash for i in range(snap.n_base)]
    srcm = SourceMasks.choose(snap, sel)

    def off(s: str) -> bytes:
        return pool.add(s).to_bytes(lay.off_bytes, "little")

    def off_json(s: str | None) -> bytes:
        at = none_off if s is None else pool.add_json(s)
        return at.to_bytes(lay.off_bytes, "little")

    # ids
    ids = bytearray()
    seen: set[tuple[FlashType, IdFamily, bytes]] = set()
    aliases = 0
    for f in bases:
        if not 1 <= len(f.id) <= 7:
            msg = f"id {f.id.hex()} is not 1-7 bytes"
            raise ValueError(msg)
        if f.ids[0] != f.id or any(not f.id.startswith(x) for x in f.ids):
            msg = f"chip {f.key}'s ids {[x.hex() for x in f.ids]} do not all start its id"
            raise ValueError(msg)
        for x in f.ids:
            if (f.type, f.family, x) in seen:
                msg = f"two {f.type} chips answer to id {x.hex()}"
                raise ValueError(msg)
            seen.add((f.type, f.family, x))
        hdr = (8 if f.type is FlashType.NAND else 0) | FAMILIES.index(f.family) << 4
        ids += bytes([len(f.id) | hdr]) + f.id
        ids += bytes(ID_ALIAS | len(x) | hdr for x in f.ids[1:])
        aliases += len(f.ids) - 1
    tables["ids"] = bytes(ids) + b"\0"
    defines["ALIAS_COUNT"] = aliases

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
    named = sorted({m for e in snap.entries if (m := _maker(e.flash)) and not m[1]})
    inferred = sorted({m for e in snap.entries if (m := _maker(e.flash)) and m[1]})
    mfrs = (*named, *inferred)
    if has(Field.MANUFACTURER):
        values["mfrs"] = mfrs
        tables["mfrs"] = b"".join(off(m) for m, _inferred in mfrs)
    defines["MFR_INFERRED"] = len(named) if has(Field.MANUFACTURER) else 0

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

    # dsrows (and dslists, per entry below)
    dslists = _Blobs("dslists")
    sheet_row = {d.url: i for i, d in enumerate(sheets)}
    if with_ds:
        ds_rows = bytearray()
        for d in sheets:
            ds_rows += off(d.url)
            if has(Field.DATASHEETS):
                if d.date and d.date.year < 1000:
                    msg = (
                        f"datasheet {d.url} is dated {d.date}: the C prints years "
                        "without zero padding, so none before 1000"
                    )
                    raise ValueError(msg)
                ds_rows += off_json(d.title) + off_json(d.revision)
                ds_rows += _uint(d.date.year if d.date else 0, 2, "year")
                ds_rows += bytes([d.date.month, d.date.day]) if d.date else b"\0\0"
                ds_rows += _u8(int(d.official))
        tables["dsrows"] = _row_table("dsrows", bytes(ds_rows))
        # url; with DATASHEETS title, revision, year u16, month, day, official
        defines["DS_ROW"] = (3 * lay.off_bytes + 5) if has(Field.DATASHEETS) else lay.off_bytes
        defines["DS_ITEM"] = 3 if has(Field.DATASHEETS) else 2
        defines["NONE_OFF"] = none_off

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
            row += _u8(_idx(mfrs, _maker(f)))
        full = mask(f.sources)
        if has(Field.SOURCES):
            row += srcm.entry(full)
        if has(Field.NAMES):
            row += _u16(namelists.add(_u8(len(f.names)) + b"".join(off(n) for n in f.names)))
        if has(Field.OPERATIONS):
            kept = [o for o in f.opcodes.values() if o.operation.kind in sel.op_kinds]
            blob = _u8(len(kept)) + b"".join(
                _u8(_idx(ops, o.name))
                + (srcm.item(mask(o.sources), full) if has(Field.SOURCES) else b"")
                for o in kept
            )
            row += _u16(opsets.add(blob))
        if with_conflicts:
            conf = f.conflicts
            if conf:
                conf_blob = bytearray()
                for attr, vals in conf.items():
                    conf_blob += _u8(CONFLICT_ATTRS.index(attr)) + _u8(len(vals))
                    for v, srcs in vals.items():
                        vi = _idx(values[_ATTR_TABLE[attr]], _value(attr, v))
                        conf_blob += _u8(vi) + srcm.item(mask(srcs), full)
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
        if with_ds:
            ds = _datasheets(f, sel)
            row += _u16(
                dslists.add(
                    _u8(len(ds))
                    + b"".join(
                        _u16(sheet_row[d.url])
                        + (_u8(f.confirms(d)) if has(Field.DATASHEETS) else b"")
                        for d in ds
                    )
                )
            )
        rows += row

    # Entry offsets.
    at = 0
    for name, width, flds in _ENTRY_FIELDS:
        if (sel.fields & flds and (name != "CONF" or with_conflicts)) or name == "BANK":
            defines[f"E_{name}"] = at
            at += srcm.entry_bytes if name == "SRCS" else width
    defines["ENTRY_SIZE"] = at
    if len(rows) != at * len(snap.entries):
        msg = "entry rows disagree with ENTRY_SIZE"
        raise AssertionError(msg)
    tables["entries"] = _row_table("entries", bytes(rows))
    for blobs, present in (
        (namelists, has(Field.NAMES)),
        (opsets, has(Field.OPERATIONS)),
        (conflicts, with_conflicts),
        (ext, has(Field.EXT)),
        (records, has(Field.RECORDS)),
        (dslists, with_ds),
    ):
        if present:
            tables[blobs.name] = bytes(blobs.data)

    # jep106
    jep = sorted(snap.database.manufacturers, key=lambda m: (m.bank, m.id))
    if has(Field.JEP106):
        tables["jep106"] = b"".join(_u8(m.bank) + _u8(m.id) + off(m.name) for m in jep)

    # sfdprows, sfdplines, sfdptree
    sfdplines = _Blobs("sfdplines")
    sfdptree = _Blobs("sfdptree")
    sfdp_count = 0
    with_lines = stores_sfdp_lines(sel)
    if with_lines or has(Field.SFDP_DUMPS):
        sfdp_rows = bytearray()
        for i, e in enumerate(snap.entries):
            if not e.flash.sfdp_dumps:
                continue
            sfdp_count += 1
            sfdp_rows += _u16(i)
            if with_lines:
                lines = sfdp_lines(e.flash)
                sfdp_rows += _u16(sfdplines.add(_u8(len(lines)) + b"".join(map(off, lines))))
            if has(Field.SFDP_DUMPS):
                tree = sfdp_tree(sfdp_json(e.flash), off_json) + _u8(T_END)
                sfdp_rows += _u16(sfdptree.add(tree))
        tables["sfdprows"] = _row_table("sfdprows", bytes(sfdp_rows))
        defines["SFDP_ROW"] = 2
        if with_lines:
            tables["sfdplines"] = bytes(sfdplines.data)
            defines["SFDP_LINES"] = defines["SFDP_ROW"]
            defines["SFDP_ROW"] += 2
        if has(Field.SFDP_DUMPS):
            tables["sfdptree"] = bytes(sfdptree.data)
            defines["SFDP_TREE"] = defines["SFDP_ROW"]
            defines["SFDP_ROW"] += 2

    # difflines
    diff_count = 0
    if has(Field.TEXT):
        diff_rows = bytearray()
        for i, e in enumerate(snap.entries):
            for line in diff_lines(e.flash):
                diff_count += 1
                diff_rows += _u16(i) + off(line)
        tables["difflines"] = _row_table("difflines", bytes(diff_rows))

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
        "DS_COUNT": ("dsrows", len(sheets)),
        "SFDP_COUNT": ("sfdprows", sfdp_count),
        "DIFF_COUNT": ("difflines", diff_count),
    }
    for name, (table, n) in counts.items():
        defines[name] = n
        if not n:
            tables.pop(table, None)
    if not ops:
        tables.pop("opsets", None)
    if not sheets:
        tables.pop("dslists", None)
    if not sfdp_count:
        tables.pop("sfdplines", None)
        tables.pop("sfdptree", None)

    # Defines.
    defines["ENTRY_COUNT"] = len(snap.entries)
    defines["BASE_COUNT"] = snap.n_base
    defines["OFF_BYTES"] = lay.off_bytes
    defines["SRC_BYTES"] = srcm.width
    defines["SRC_REL"] = int(srcm.rel)
    defines["SRCMASK_COUNT"] = len(srcm.table)
    if srcm.table:
        tables["srcmasks"] = b"".join(_u16(m) for m in srcm.table)
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
