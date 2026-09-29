"""The spiflash database as the generator sees it.

An :class:`Entry` is one answer the C library can give: a chip id's
:class:`~spiflash.Flash`, or that flash narrowed by the extended-id bytes a
chip sends after its id (:meth:`~spiflash.Flash.with_ext_id`). Narrowing
changes consensus values, so each distinct narrowing is its own entry.
Base entries come first, in the database's order; variants follow.

Which narrowing applies depends only on *which* of the chip's extended ids
agree with the bytes read (:func:`ext_mask`), so the C library computes that
bit mask and looks the variant up by it. :func:`reaching_probes` finds byte
strings that between them produce every mask any input can produce, which is
how every variant is found and tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from spiflash.db import Database, database
from spiflash.enums import FlashType, IdFamily
from spiflash.model import strip_continuation

if TYPE_CHECKING:
    from collections.abc import Sequence

    from spiflash.model import Flash

#: The id families, in the order of their C codes (``USF_FAMILY_*``).
FAMILIES: tuple[IdFamily, ...] = (
    IdFamily.JEDEC,
    IdFamily.REMS,
    IdFamily.RES1,
    IdFamily.RES2,
    IdFamily.AT25F,
    IdFamily.ST95,
)


def compatible(ext_id: bytes, probe: bytes) -> bool:
    """spiflash's rule: an extended id agrees with the bytes read when they
    are equal as far as both go."""
    return ext_id[: len(probe)] == probe[: len(ext_id)]


def ext_mask(ids: Sequence[bytes], probe: bytes) -> int:
    """Bit ``i`` set when ``ids[i]`` agrees with ``probe``."""
    return sum(1 << i for i, e in enumerate(ids) if compatible(e, probe))


def reaching_probes(ids: Sequence[bytes]) -> tuple[bytes, ...]:
    """Byte strings that reach every mask :func:`ext_mask` can produce.

    For any input, let ``d`` be the longest prefix of some id that is also a
    prefix of the input. The mask depends only on ``d`` and on whether the
    input *is* ``d``. So every prefix ``p`` of every id, and ``p`` followed
    by one byte that continues no id, reaches every mask; the empty prefix
    covers inputs that match nothing.
    """
    nodes = {e[:n] for e in ids for n in range(1, len(e) + 1)}
    out = set(nodes)
    for p in (*nodes, b""):
        children = {e[len(p)] for e in ids if len(e) > len(p) and e.startswith(p)}
        spare = next(b for b in range(256) if b not in children)
        out.add(p + bytes([spare]))
    return tuple(sorted(out))


@dataclass(frozen=True)
class Entry:
    """One answer: ``flash`` (possibly narrowed), the index of its chip id's
    base entry, and the extended-id mask that selects it (0 for a base)."""

    flash: Flash
    base: int
    ext_mask: int


@dataclass(frozen=True)
class Snapshot:
    """Every entry of a database, and how extended ids select variants."""

    database: Database
    entries: tuple[Entry, ...]
    #: Base entry index → the distinct extended ids of its records, sorted.
    ext: dict[int, tuple[bytes, ...]]
    #: Base entry index → {mask: entry index}, for masks whose narrowing
    #: differs from the base. Any other mask means the base entry.
    variants: dict[int, dict[int, int]]

    @classmethod
    def build(cls, db: Database | None = None) -> Snapshot:
        """The snapshot of ``db`` (the installed spiflash database by default)."""
        db = db or database()
        entries = [Entry(f, i, 0) for i, f in enumerate(db.flashes)]
        ext: dict[int, tuple[bytes, ...]] = {}
        variants: dict[int, dict[int, int]] = {}
        for i, f in enumerate(db.flashes):
            ids = tuple(sorted({r.ext_id for r in f.records if r.ext_id}))
            if not ids:
                continue
            ext[i] = ids
            by_records: dict[tuple[object, ...], int] = {}
            table: dict[int, int] = {}
            for probe in reaching_probes(ids):
                mask = ext_mask(ids, probe)
                narrowed = f.with_ext_id(probe)
                if mask in table or narrowed.records == f.records:
                    continue
                if narrowed.records not in by_records:
                    by_records[narrowed.records] = len(entries)
                    entries.append(Entry(narrowed, i, mask))
                table[mask] = by_records[narrowed.records]
            if table:
                variants[i] = table
        return cls(db, tuple(entries), ext, variants)

    @property
    def n_base(self) -> int:
        """How many entries are chip ids (the rest are variants)."""
        return len(self.database.flashes)

    def resolve(self, base: int, leftover: bytes) -> int:
        """The entry for chip id ``base`` given the bytes read after its id."""
        if not leftover or base not in self.variants:
            return base
        return self.variants[base].get(ext_mask(self.ext[base], leftover), base)

    def lookup(self, family: IdFamily, data: bytes) -> list[int]:
        """Entry indices answering ``data``, as :meth:`Database.lookup` would."""
        _bank, core = strip_continuation(data)
        best: dict[FlashType, int] = {}
        for i in range(self.n_base):
            f = self.entries[i].flash
            if f.family is not family or core[: len(f.id)] != f.id:
                continue
            if f.type not in best or len(f.id) > len(self.entries[best[f.type]].flash.id):
                best[f.type] = i
        order = sorted(best.items(), key=lambda kv: kv[0] is not FlashType.NOR)
        return [self.resolve(i, core[len(self.entries[i].flash.id) :]) for _, i in order]
