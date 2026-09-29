"""uspiflash: generate tiny single-file C libraries that detect SPI flash
chips and report their capabilities, from the spiflash database.

See https://uspiflash.readthedocs.io/ and the design in
docs/superpowers/specs/2026-09-28-uspiflash-design.md."""

from __future__ import annotations

from ._version import __version__

__all__ = ["__version__"]
