"""What goes into a generated file: fields (a detail level plus extras) and chips.

========== =========================================================================
Level      Adds
========== =========================================================================
id         probe the bus; which chip (ids, family, type, JEP106 bank)
read       size, features, id/read/mode operations, extended-id narrowing
write      page and sector size, every operation (program, erase, registers)
describe   voltage, manufacturer and part names, operation names/descriptions,
           the text printer (``usf_print``)
full       which sources say what, where they disagree, the JSON printer
========== =========================================================================

Extras (``--with``): ``records`` (each upstream entry's source, raw name and
extended id), ``provenance`` (each entry's upstream file:line), ``datasheet``
(the best datasheet's URL, the text output's ``datasheet:`` line),
``datasheets`` (every datasheet, as the JSON lists them), ``jep106`` (every
JEP106 manufacturer name), ``sfdp`` (read and decode SFDP on the chip).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from spiflash.db import Database
from spiflash.enums import FlashType, IdFamily, OperationKind
from spiflash.vendors import canonical

if TYPE_CHECKING:
    from collections.abc import Iterable

    from spiflash.model import Flash


class Field(StrEnum):
    """A piece of data or code the generated file can include."""

    IDENT = "ident"
    PROBE = "probe"
    EXT = "ext"
    SIZE = "size"
    FEATURES = "features"
    OPERATIONS = "operations"
    PAGE_SIZE = "page_size"
    SECTOR_SIZE = "sector_size"
    VOLTAGE = "voltage"
    MANUFACTURER = "manufacturer"
    NAMES = "names"
    DESCRIPTIONS = "descriptions"
    TEXT = "text"
    SOURCES = "sources"
    CONFLICTS = "conflicts"
    JSON = "json"
    RECORDS = "records"
    PROVENANCE = "provenance"
    DATASHEET = "datasheet"
    DATASHEETS = "datasheets"
    JEP106 = "jep106"
    SFDP = "sfdp"


F = Field
_ID = frozenset({F.IDENT, F.PROBE})
_READ = _ID | {F.EXT, F.SIZE, F.FEATURES, F.OPERATIONS}
_WRITE = _READ | {F.PAGE_SIZE, F.SECTOR_SIZE}
_DESCRIBE = _WRITE | {F.VOLTAGE, F.MANUFACTURER, F.NAMES, F.DESCRIPTIONS, F.TEXT}
_FULL = _DESCRIBE | {F.SOURCES, F.CONFLICTS, F.JSON}

#: Each level's fields.
LEVELS: dict[str, frozenset[Field]] = {
    "id": _ID,
    "read": _READ,
    "write": _WRITE,
    "describe": _DESCRIBE,
    "full": _FULL,
}
#: Each level's operation kinds (``read`` keeps only what reading needs).
LEVEL_OP_KINDS: dict[str, frozenset[OperationKind]] = {
    "id": frozenset(),
    "read": frozenset({OperationKind.ID, OperationKind.READ, OperationKind.MODE}),
    "write": frozenset(OperationKind),
    "describe": frozenset(OperationKind),
    "full": frozenset(OperationKind),
}
_TEXT_NEEDS = frozenset(
    {
        F.IDENT,
        F.SIZE,
        F.PAGE_SIZE,
        F.SECTOR_SIZE,
        F.VOLTAGE,
        F.FEATURES,
        F.MANUFACTURER,
        F.NAMES,
        F.OPERATIONS,
        F.DESCRIPTIONS,
    }
)
#: What each field needs present to work.
REQUIRES: dict[Field, frozenset[Field]] = {
    F.PROBE: frozenset({F.IDENT}),
    F.EXT: frozenset({F.IDENT}),
    F.DESCRIPTIONS: frozenset({F.OPERATIONS}),
    F.TEXT: _TEXT_NEEDS,
    F.CONFLICTS: frozenset({F.SIZE, F.PAGE_SIZE, F.SECTOR_SIZE, F.VOLTAGE}),
    F.JSON: _TEXT_NEEDS | {F.SOURCES, F.CONFLICTS, F.EXT},
    F.RECORDS: frozenset({F.JSON}),
    F.PROVENANCE: frozenset({F.RECORDS}),
    F.DATASHEET: frozenset({F.TEXT}),
    F.DATASHEETS: frozenset({F.JSON}),
    F.SFDP: frozenset({F.PROBE}),
}


def _close(fields: set[Field]) -> set[Field]:
    todo = list(fields)
    while todo:
        for need in REQUIRES.get(todo.pop(), frozenset()):
            if need not in fields:
                fields.add(need)
                todo.append(need)
    return fields


@dataclass(frozen=True)
class ChipFilter:
    """Which chips to keep; an empty criterion keeps everything."""

    manufacturers: tuple[str, ...] = ()
    ids: tuple[bytes, ...] = ()
    types: tuple[FlashType, ...] = ()
    families: tuple[IdFamily, ...] = ()
    min_size: int | None = None
    max_size: int | None = None

    def keeps(self, f: Flash) -> bool:
        """Whether chip id ``f`` stays."""
        if self.manufacturers:
            wanted = {(canonical(m) or m).lower() for m in self.manufacturers}
            if (f.manufacturer or "").lower() not in wanted:
                return False
        if self.ids and f.id not in self.ids:
            return False
        if self.types and f.type not in self.types:
            return False
        if self.families and f.family not in self.families:
            return False
        if self.min_size is not None and (f.size is None or f.size < self.min_size):
            return False
        return not (self.max_size is not None and (f.size is None or f.size > self.max_size))

    def apply(self, db: Database) -> Database:
        """A database of the kept chips' records (same manufacturers, sources
        and datasheets, so kept chips keep theirs)."""
        records = [r for f in db.flashes if self.keeps(f) for r in f.records]
        return Database(records, db.manufacturers, db.sources, db.datasheets)

    def to_json(self) -> dict[str, Any]:
        """Plain JSON, for the provenance header."""
        return {
            "manufacturers": list(self.manufacturers),
            "ids": [i.hex() for i in self.ids],
            "types": [t.value for t in self.types],
            "families": [f.value for f in self.families],
            "min_size": self.min_size,
            "max_size": self.max_size,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> ChipFilter:
        """The inverse of :meth:`to_json`."""
        return cls(
            tuple(d["manufacturers"]),
            tuple(bytes.fromhex(i) for i in d["ids"]),
            tuple(FlashType(t) for t in d["types"]),
            tuple(IdFamily(f) for f in d["families"]),
            d["min_size"],
            d["max_size"],
        )


@dataclass(frozen=True)
class Selection:
    """The fields and chips one generated file carries."""

    level: str
    fields: frozenset[Field]
    op_kinds: frozenset[OperationKind]
    chips: ChipFilter = field(default_factory=ChipFilter)

    @classmethod
    def make(
        cls,
        level: str = "full",
        with_: Iterable[str] = (),
        without: Iterable[str] = (),
        chips: ChipFilter | None = None,
    ) -> Selection:
        """``level`` plus ``with_`` (and whatever they need), minus ``without``.

        Removing a field another selected field needs is an error, rather than
        silently removing both."""
        if level not in LEVELS:
            msg = f"unknown level {level!r}: one of {', '.join(LEVELS)}"
            raise ValueError(msg)
        fields = _close(set(LEVELS[level]) | {Field(w) for w in with_})
        for name in without:
            drop = Field(name)
            fields.discard(drop)
            for f in (x for x in Field if x in fields):  # declaration order
                if drop in REQUIRES.get(f, frozenset()):
                    msg = f"{f} needs {drop}"
                    raise ValueError(msg)
        kinds = LEVEL_OP_KINDS[level]
        if Field.OPERATIONS in fields and not kinds:
            kinds = frozenset(OperationKind)
        return cls(level, frozenset(fields), kinds, chips or ChipFilter())

    def has(self, f: Field) -> bool:
        """Whether field ``f`` is selected."""
        return f in self.fields

    def to_json(self) -> dict[str, Any]:
        """Plain JSON, for the provenance header and ``uspiflash check``."""
        return {
            "level": self.level,
            "fields": sorted(self.fields),
            "op_kinds": sorted(self.op_kinds),
            "chips": self.chips.to_json(),
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Selection:
        """The inverse of :meth:`to_json`."""
        return cls(
            d["level"],
            frozenset(Field(f) for f in d["fields"]),
            frozenset(OperationKind(k) for k in d["op_kinds"]),
            ChipFilter.from_json(d["chips"]),
        )
