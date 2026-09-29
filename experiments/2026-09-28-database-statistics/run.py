"""Database statistics (2026-09-28): every count in spec §3 ("The data,
measured"), the M1 index's extra byte facts, and the baseline layout size
(``uspiflash.layout``) at each detail level. See ``README.md`` for the
question and the conclusion, and ``experiments/README.md`` for the
convention this directory follows."""

from __future__ import annotations

import json
import zlib
from collections import Counter
from pathlib import Path

import spiflash
from spiflash.db import database

from uspiflash import layout as layout_module
from uspiflash.levels import LEVELS, Selection
from uspiflash.model import Snapshot


def collect() -> dict[str, object]:
    """Every statistic spec §3 lists, the extra byte facts the M1 index
    calls out, and the baseline layout size at each detail level."""
    db = database()
    bases = db.flashes
    snap = Snapshot.build(db)

    types = Counter(f.type.value for f in bases)
    families = Counter(f.family.value for f in bases)
    id_lengths = Counter(len(f.id) for f in bases)
    banks = Counter(f.bank for f in bases)

    manufacturers = {m for f in bases if (m := f.manufacturer)}
    names = {n for f in bases for n in f.names}
    name_bytes = sum(len(n) for n in names)
    name_alphabet = "".join(sorted({c for n in names for c in n}))

    opcode_sets = {frozenset(f.opcodes) for f in bases}
    opcode_sets_with_sources = {
        frozenset((name, op.sources) for name, op in f.opcodes.items()) for f in bases
    }
    feature_sets = {f.features for f in bases}
    geometry_tuples = {(f.size, f.page_size, f.sector_size, f.voltage) for f in bases}
    conflicting_ids = sum(1 for f in bases if f.conflicts)
    ext_ids = sum(1 for f in bases if any(r.ext_id for r in f.records))
    ext_records = sum(1 for r in db.records if r.ext_id)

    # The M1 index's extra facts (bytes, since every other per-string fact
    # measured here is a byte count too): raw record names (a record's name
    # before it is split into part numbers), the "via" strings that justify
    # each opcode claim, upstream notes, each record's "at" location (the
    # ``Record.url`` property: ``file:line``, despite the name), and the
    # JEP106 manufacturer table.
    record_name_bytes = sum(len(r.name) for r in db.records)
    via_bytes = sum(len(use.via) for r in db.records for use in r.opcodes)
    notes_bytes = sum(len(n) for r in db.records for n in r.notes)
    record_url_bytes = sum(len(r.url) for r in db.records)
    jep106_bytes = sum(len(m.name) for m in db.manufacturers)

    layout_bytes = {
        level: sum(len(t) for t in layout_module.build(snap, Selection.make(level)).tables.values())
        for level in LEVELS
    }
    layout_bytes["full+records+provenance+jep106"] = sum(
        len(t)
        for t in layout_module.build(
            snap, Selection.make("full", with_=("records", "provenance", "jep106"))
        ).tables.values()
    )

    return {
        "chip_ids": len(bases),
        "types": dict(sorted(types.items())),
        "families": dict(sorted(families.items())),
        "id_lengths": {str(k): v for k, v in sorted(id_lengths.items())},
        "banks": {str(k): v for k, v in sorted(banks.items())},
        "manufacturers": len(manufacturers),
        "names": len(names),
        "name_bytes": name_bytes,
        "name_bytes_zlib9": len(zlib.compress("\n".join(sorted(names)).encode("ascii"), 9)),
        "name_alphabet": name_alphabet,
        "opcode_sets": len(opcode_sets),
        "opcode_sets_with_sources": len(opcode_sets_with_sources),
        "feature_sets": len(feature_sets),
        "geometry_tuples": len(geometry_tuples),
        "conflicting_ids": conflicting_ids,
        "ext_ids": ext_ids,
        "ext_records": ext_records,
        "record_name_bytes": record_name_bytes,
        "via_bytes": via_bytes,
        "notes_bytes": notes_bytes,
        "record_url_bytes": record_url_bytes,
        "jep106_bytes": jep106_bytes,
        "layout_bytes": layout_bytes,
        "spiflash_version": spiflash.__version__,
        "sources_commits": {name: info.commit for name, info in spiflash.sources().items()},
    }


if __name__ == "__main__":
    Path("results").mkdir(exist_ok=True)
    text = json.dumps(collect(), sort_keys=True, indent=1)
    Path("results/stats.json").write_text(text + "\n")
