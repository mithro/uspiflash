"""SFDP versus the database (2026-09-29): for every SFDP dump spiflash ships,
what the chip's own tables say (decoded by :mod:`spiflash.sfdp`) against
what the database's consensus says for the same chip id. See ``README.md``
for the question and the conclusion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import spiflash
from spiflash.db import database
from spiflash.enums import Feature, OperationKind

#: The features SFDP can express (:meth:`spiflash.sfdp.Sfdp.features`):
#: only these are compared, since SFDP says nothing about the others.
SFDP_FEATURES = frozenset(
    {
        Feature.SFDP,
        Feature.FAST_READ,
        Feature.ERASE_4K,
        Feature.ERASE_32K,
        Feature.ERASE_64K,
        Feature.DUAL_READ,
        Feature.QUAD_READ,
        Feature.QPI,
        Feature.OCTAL_READ,
        Feature.OCTAL_DTR_READ,
        Feature.OCTAL_DTR_PP,
        Feature.FOUR_BYTE_ADDR,
        Feature.FOUR_BYTE_OPCODES,
        Feature.QUAD_PP,
    }
)

#: Erases a BFPT never lists: the whole chip, or a die.
NOT_IN_SFDP = frozenset({"CHIP_ERASE", "CHIP_ERASE_ALT", "CHIP_ERASE_ATMEL", "DIE_ERASE"})
#: The operation kinds SFDP describes (fast reads, and erases by size).
SFDP_KINDS = frozenset({OperationKind.READ, OperationKind.ERASE})


def compare() -> list[dict[str, Any]]:
    """One row per (chip id, dump): each field SFDP and the database both
    give, and where they differ."""
    rows: list[dict[str, Any]] = []
    for f in database().flashes:
        for d in f.sfdp_dumps:
            s = d.tables
            named = {o.name for o in s.operations() if o.name is not None}
            sfdp_features = s.features()
            erase_sizes = sorted({e.size for e in s.erase_types})
            rows.append(
                {
                    "chip": f.key,
                    "names": list(f.names),
                    "dump": {"source": str(d.source), "parts": list(d.parts)},
                    "revision": s.revision_name,
                    "size": {"sfdp": s.size, "database": f.size},
                    "page_size": {"sfdp": s.page_size, "database": f.page_size},
                    "sector_size": {"sfdp_erase_sizes": erase_sizes, "database": f.sector_size},
                    "sfdp_erases": [[e.size, e.opcode] for e in s.erase_types],
                    "records": [f"{r.source}: {r.name}" for r in f.records],
                    "features_only_sfdp": sorted(sfdp_features - f.features),
                    # Evidence for each claim SFDP does not make: who makes it.
                    "features_only_database": {
                        str(x): [str(src) for src in f.feature_sources(x)]
                        for x in sorted((f.features & SFDP_FEATURES) - sfdp_features)
                    },
                    "operations_only_sfdp": sorted(named - set(f.opcodes)),
                    "operations_only_database": {
                        n: [str(src) for src in o.sources]
                        for n, o in sorted(f.opcodes.items())
                        if n not in named
                        and n not in NOT_IN_SFDP
                        and o.operation.kind in SFDP_KINDS
                    },
                    "unnamed_operations": sum(1 for o in s.operations() if o.name is None),
                    "warnings": list(s.warnings),
                }
            )
    return rows


def collect() -> dict[str, object]:
    """The comparison, and a summary: how many dumps agree on each field."""
    rows = compare()
    agree = {
        "size": sum(r["size"]["sfdp"] == r["size"]["database"] for r in rows),
        "page_size": sum(
            r["page_size"]["sfdp"] in (None, r["page_size"]["database"]) for r in rows
        ),
        "sector_size": sum(
            r["sector_size"]["database"] in r["sector_size"]["sfdp_erase_sizes"] for r in rows
        ),
        "features": sum(
            not r["features_only_sfdp"] and not r["features_only_database"] for r in rows
        ),
        "operations": sum(
            not r["operations_only_sfdp"] and not r["operations_only_database"] for r in rows
        ),
    }
    return {
        "dumps": len(rows),
        "chip_ids": len({r["chip"] for r in rows}),
        "agree": agree,
        "rows": rows,
        "spiflash_version": spiflash.__version__,
    }


if __name__ == "__main__":
    Path("results").mkdir(exist_ok=True)
    text = json.dumps(collect(), sort_keys=True, indent=1)
    Path("results/comparison.json").write_text(text + "\n")
