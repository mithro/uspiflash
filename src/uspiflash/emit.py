"""Render the C template with a layout's tables and a provenance header."""

from __future__ import annotations

import re
from importlib import resources
from typing import TYPE_CHECKING

from spiflash.db import database

from . import layout
from .cgen import byte_array, defines
from .levels import Field
from .model import FAMILIES, Snapshot
from .provenance import header

if TYPE_CHECKING:
    from .provenance import Config

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def constants() -> dict[str, int]:
    """The C names of spiflash's vocabularies (``USF_`` is added by
    :func:`~uspiflash.cgen.defines`), generated from the tuples the layout
    indexes, so the names can never drift from the data. Enum *member*
    names throughout (``FEATURE_FOUR_BYTE_ADDR``, ``SOURCE_UBOOT``); a
    protocol's ``-`` becomes ``_`` (``PROTO_1_1_4``, ``PROTO_8D_8D_8D``)."""
    pairs = [
        *((f"FAMILY_{f.name}", i) for i, f in enumerate(FAMILIES)),
        *((f"TYPE_{t.name}", i) for i, t in enumerate(layout.TYPES)),
        *((f"FEATURE_{f.name}", i) for i, f in enumerate(layout.FEATURES)),
        ("FEATURE_COUNT", len(layout.FEATURES)),
        *((f"SOURCE_{s.name}", i) for i, s in enumerate(layout.SOURCES)),
        *((f"KIND_{k.name}", i) for i, k in enumerate(layout.KINDS)),
        *((f"PROTO_{p.replace('-', '_')}", i) for i, p in enumerate(layout.PROTOCOLS)),
        *((f"OP_{name}", i) for i, name in enumerate(layout.ALL_OPS)),
    ]
    out = dict(pairs)
    if len(out) != len(pairs):
        msg = "two constants share a name"
        raise ValueError(msg)
    return out


def _guard(filename: str) -> str:
    """The include guard: ``uspiflash.h`` gives ``USF_USPIFLASH_H``, which the
    prefix rename then makes the user's own (never a reserved identifier)."""
    return "USF_" + re.sub(r"[^A-Za-z0-9]", "_", filename).upper()


def render(config: Config, snapshot: Snapshot | None = None) -> str:
    """The generated file for ``config``."""
    if not _IDENT.fullmatch(config.prefix):
        msg = f"prefix {config.prefix!r} is not a C identifier"
        raise ValueError(msg)
    if config.prefix.startswith("_"):
        msg = (
            f"prefix {config.prefix!r} starts with an underscore: C reserves "
            "identifiers that do (at file scope, and _ with a capital everywhere)"
        )
        raise ValueError(msg)
    if config.selection.has(Field.SFDP):
        msg = "sfdp is not available yet (the SFDP milestone adds it)"
        raise ValueError(msg)
    snap = snapshot or Snapshot.build(config.selection.chips.apply(database()))
    if not snap.entries:
        msg = "the chip filter keeps no chips"
        raise ValueError(msg)
    lay = layout.build(snap, config.selection)
    template = resources.files("uspiflash").joinpath("templates/uspiflash.h.in").read_text("ascii")
    code = (
        template.replace("@@GUARD@@", _guard(config.filename))
        .replace("@@CONFIG@@", defines(lay.defines) + defines(constants()))
        .replace("@@TABLES@@", "".join(byte_array(n, d) for n, d in sorted(lay.tables.items())))
    )
    if config.prefix != "usf":
        code = re.sub(r"\busf_", config.prefix + "_", code)
        code = re.sub(r"\bUSF_", config.prefix.upper() + "_", code)
    # Last, so the rename never touches the embedded configuration.
    return code.replace("@@PROVENANCE@@", header(config))
