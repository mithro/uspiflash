"""The spiflash database as the generator sees it.

An :class:`Entry` is one answer the C library can give: a chip id's
:class:`~spiflash.Flash`, or that flash narrowed by the extended-id bytes a
chip sends after its id (:meth:`Database.narrow <spiflash.db.Database.narrow>`).
Narrowing changes consensus values, the manufacturer and the datasheets, so
each distinct narrowing (as spiflash prints it, :func:`printed`) is its own
entry. Base entries come first, in the database's order; variants follow.

A SPI NAND chip can also answer to shorter ids (:attr:`Flash.ids
<spiflash.model.Flash.ids>`: sources that match fewer of its id bytes),
each the start of its id.

Which narrowing applies depends only on *which* of the chip's extended ids
agree with the bytes read (:func:`ext_mask`), so the C library computes that
bit mask and looks the variant up by it. :func:`reaching_probes` finds byte
strings that between them produce every mask any input can produce, which is
how every variant is found and tested.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from spiflash.cli import describe
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


def printed(f: Flash) -> str:
    """Everything spiflash prints about ``f`` (``spiflash id --json``, and
    ``-v --opcodes``): two narrowings that print alike are one entry."""
    return json.dumps(f.to_json(), default=str) + describe(f, verbose=True, opcodes=True)


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
            if len(f.ids) > 1:
                # The C narrows only after a chip's whole id.
                msg = f"chip {f.key} has both shorter ids and extended ids"
                raise ValueError(msg)
            base = printed(f)
            by_output: dict[str, int] = {}
            table: dict[int, int] = {}
            for probe in reaching_probes(ids):
                mask = ext_mask(ids, probe)
                narrowed = db.narrow(f, probe)
                out = printed(narrowed)
                if mask in table or out == base:
                    continue
                if out not in by_output:
                    by_output[out] = len(entries)
                    entries.append(Entry(narrowed, i, mask))
                table[mask] = by_output[out]
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
        """Entry indices answering ``data``, as :meth:`Database.lookup` would:
        per type, the chip with the longest of its ids that starts ``data``,
        narrowed by the bytes after its whole id."""
        _bank, core = strip_continuation(data)
        best: dict[FlashType, tuple[int, int]] = {}
        for i in range(self.n_base):
            f = self.entries[i].flash
            fits = next((len(x) for x in f.ids if core[: len(x)] == x), 0)
            if f.family is not family or not fits:
                continue
            if f.type not in best or fits > best[f.type][0]:
                best[f.type] = (fits, i)
        order = sorted(best.items(), key=lambda kv: kv[0] is not FlashType.NOR)
        return [self.resolve(i, core[len(self.entries[i].flash.id) :]) for _, (_n, i) in order]
