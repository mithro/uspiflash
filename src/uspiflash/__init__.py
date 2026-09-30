"""uspiflash: generate tiny single-file C libraries that detect SPI flash
chips and report their capabilities, from the spiflash database.

See https://uspiflash.readthedocs.io/ and the design in
docs/superpowers/specs/2026-09-28-uspiflash-design.md."""

from __future__ import annotations

from ._version import __version__

#: The spiflash version the generated C's output is verified byte-identical
#: to (the parity tests run in full against it; uv.lock pins it).
VERIFIED_SPIFLASH = "0.0.post108"

__all__ = ["VERIFIED_SPIFLASH", "__version__"]
