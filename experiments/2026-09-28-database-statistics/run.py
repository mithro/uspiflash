"""Database statistics (2026-09-28): every count in spec §3 ("The data,
measured"), the M1 index's extra byte facts, and the baseline layout size
(``uspiflash.layout``) at each detail level. See ``README.md`` for the
question and the conclusion, and ``experiments/README.md`` for the
convention this directory follows."""

from __future__ import annotations

import json
import platform
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
    # Spec §3 counts part names per chip id (a name two ids share counts
    # twice); the string pool stores each distinct name once.
    names = {n for f in bases for n in f.names}
    name_bytes = sum(len(n) for n in names)
    names_per_id = sum(len(f.names) for f in bases)
    name_bytes_per_id = sum(len(n) for f in bases for n in f.names)
    # NUL-separated in database order, as the spec's §3 figure (3,584) was taken.
    per_id_text = "\0".join(n for f in bases for n in f.names).encode("ascii")
    name_alphabet = "".join(sorted({c for n in names for c in n}))
    operations_used = {name for f in bases for name in f.opcodes}

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
    record_names = {r.name for r in db.records}
    via_bytes = sum(len(use.via) for r in db.records for use in r.opcodes)
    notes_bytes = sum(len(n) for r in db.records for n in r.notes)
    record_url_bytes = sum(len(r.url) for r in db.records)
    record_urls = {r.url for r in db.records}
    jep106_bytes = sum(len(m.name) for m in db.manufacturers)
    jep106_names = {m.name for m in db.manufacturers}

    selections = {level: Selection.make(level) for level in LEVELS}
    selections["full+records+provenance+jep106"] = Selection.make(
        "full", with_=("records", "provenance", "jep106")
    )
    layout_tables = {
        name: {t: len(b) for t, b in sorted(layout_module.build(snap, sel).tables.items())}
        for name, sel in selections.items()
    }
    layout_bytes = {name: sum(tables.values()) for name, tables in layout_tables.items()}

    return {
        "chip_ids": len(bases),
        "types": dict(sorted(types.items())),
        "families": dict(sorted(families.items())),
        "id_lengths": {str(k): v for k, v in sorted(id_lengths.items())},
        "banks": {str(k): v for k, v in sorted(banks.items())},
        "manufacturers": len(manufacturers),
        "manufacturer_name_bytes": sum(len(m) for m in manufacturers),
        "names": len(names),
        "name_bytes": name_bytes,
        "name_bytes_zlib9": len(zlib.compress("\n".join(sorted(names)).encode("ascii"), 9)),
        "names_per_id": names_per_id,
        "name_bytes_per_id": name_bytes_per_id,
        "name_bytes_per_id_zlib9": len(zlib.compress(per_id_text, 9)),
        "max_names_per_id": max(len(f.names) for f in bases),
        "name_alphabet": name_alphabet,
        "operations_used": len(operations_used),
        "opcode_sets": len(opcode_sets),
        "opcode_sets_with_sources": len(opcode_sets_with_sources),
        "feature_sets": len(feature_sets),
        "geometry_tuples": len(geometry_tuples),
        "conflicting_ids": conflicting_ids,
        "ext_ids": ext_ids,
        "ext_records": ext_records,
        "record_name_bytes": record_name_bytes,
        "record_names_unique": len(record_names),
        "record_name_bytes_unique": sum(len(n) for n in record_names),
        "via_bytes": via_bytes,
        "notes_bytes": notes_bytes,
        "record_url_bytes": record_url_bytes,
        "record_urls_unique": len(record_urls),
        "record_url_bytes_unique": sum(len(u) for u in record_urls),
        "jep106_bytes": jep106_bytes,
        "jep106_names_unique": len(jep106_names),
        "jep106_name_bytes_unique": sum(len(n) for n in jep106_names),
        "layout_bytes": layout_bytes,
        "layout_tables": layout_tables,
        "host": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "spiflash_version": spiflash.__version__,
        "sources_commits": {name: info.commit for name, info in spiflash.sources().items()},
    }


if __name__ == "__main__":
    Path("results").mkdir(exist_ok=True)
    text = json.dumps(collect(), sort_keys=True, indent=1)
    Path("results/stats.json").write_text(text + "\n")
