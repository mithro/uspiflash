"""The probe finds every chip the database knows, through the commands it
answers, and never sends anything but id commands; a single-type header
sends only the steps its chips answer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from spiflash.enums import FlashType, IdFamily

from harness import Harness, snapshot
from uspiflash.levels import ChipFilter, Selection
from uspiflash.provenance import Config

if TYPE_CHECKING:
    from spiflash.model import Flash

ID_COMMANDS = {"ab", "9f", "90", "15", "83"}
_LEGACY = {
    IdFamily.REMS: "90/4={}",  # REMS: 3 address bytes, then the id
    IdFamily.RES2: "ab/4={}",  # RES: 3 dummy bytes, then 2 id bytes
    IdFamily.RES1: "ab/4={}00",  # ...of which RES1 is the first; 00 keeps RES2 from matching
    IdFamily.AT25F: "15/1={}",
    IdFamily.ST95: "83/3={}00",  # M95: 2 address bytes, then 3 bytes
}
PROBES = {
    "all": Config(Selection.make("full")),
    "nor": Config(Selection.make("full", chips=ChipFilter(types=(FlashType.NOR,)))),
    "nand": Config(Selection.make("full", chips=ChipFilter(types=(FlashType.NAND,)))),
}


def spec_for(f: Flash, *, nand_dummy: bool) -> str:
    """A simulated chip answering the way ``f`` does. SPI NAND chips answer
    read-id after one dummy byte, or (a few) straight away: ``nand_dummy``
    picks which."""
    ident = f.id.hex()
    if f.family is not IdFamily.JEDEC:
        reply = _LEGACY[f.family].format(ident)
    elif f.type is FlashType.NAND:
        reply = f"9f/{2 if nand_dummy else 1}={ident}"
    else:
        reply = f"9f/1={'7f' * f.bank}{ident}"
    return f"{reply} fill=ff"


@pytest.fixture(scope="module")
def harnesses(tmp_path_factory: pytest.TempPathFactory, compilers: list[str]) -> dict[str, Harness]:
    """One harness per probe config, built with the first compiler found."""
    return {
        k: Harness.build(tmp_path_factory.mktemp(k), c, compilers[0]) for k, c in PROBES.items()
    }


def sent(out: str) -> list[str]:
    """The transactions a probe sent, as hex, in order."""
    return [line.split()[1] for line in out.splitlines() if line.startswith("> ")]


@pytest.mark.parametrize("which", list(PROBES))
@pytest.mark.parametrize("nand_dummy", [True, False])
def test_every_chip_is_found(
    harnesses: dict[str, Harness], which: str, *, nand_dummy: bool
) -> None:
    snap = snapshot(PROBES[which])
    chips = [snap.entries[i].flash for i in range(snap.n_base)]
    outs = harnesses[which].run([f"P {spec_for(f, nand_dummy=nand_dummy)}" for f in chips])
    for f, out in zip(chips, outs, strict=True):
        lines = out.splitlines()
        bases = [int(line.split()[2]) for line in lines if line.startswith("chip ")]
        assert any(snap.entries[b].flash.id == f.id for b in bases), (
            f"{f.family}:{f.id_hex} not found\n{out}"
        )
        assert {tx[:2] for tx in sent(out)} <= ID_COMMANDS


@pytest.mark.parametrize(
    ("which", "steps"),
    [
        ("all", ["ab000000", "9f", "9f00", "90000000", "15", "830000"]),
        ("nor", ["ab000000", "9f", "90000000", "15", "830000"]),
        # Plain 9f too: three GD5F NAND chips answer read-id without a dummy byte.
        ("nand", ["9f", "9f00"]),
    ],
)
def test_a_blank_bus_gets_each_compiled_step_once(
    harnesses: dict[str, Harness], which: str, steps: list[str]
) -> None:
    (out,) = harnesses[which].run(["P fill=ff"])
    assert sent(out) == steps
    assert "len=0" in out
    assert "count=0" in out


def test_unknown_jedec_id_is_reported(harnesses: dict[str, Harness]) -> None:
    (out,) = harnesses["all"].run(["P 9f/1=ee7777ee7777 fill=ff"])
    status = next(line for line in out.splitlines() if line.startswith("family="))
    assert status.startswith("family=jedec ")
    assert " id=ee7777ee7777" in status
    assert status.endswith(" count=0")


def test_unknown_chip_gets_only_read_id(harnesses: dict[str, Harness]) -> None:
    # A chip that answers read-id but isn't in the database must not be sent
    # REMS, AT25F or M95 commands (spec §5.3; M1 index decision 8).
    (out,) = harnesses["all"].run(["P 9f/1=ee7777ee7777 fill=ff"])
    assert {tx[:2] for tx in sent(out)} == {"ab", "9f"}


def test_res_wakes_before_rdid(harnesses: dict[str, Harness]) -> None:
    (out,) = harnesses["all"].run(["P 9f/1=ef4018 fill=ff"])
    assert sent(out)[0] == "ab000000"
