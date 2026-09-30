"""The Linux tool prints what `spiflash id` prints, offline and through a
(simulated) spidev device."""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from spiflash.db import database
from spiflash.enums import IdFamily
from spiflash.model import parse_id

from harness import CFLAGS, parity
from uspiflash import __version__, oracle
from uspiflash.cli import main
from uspiflash.levels import Selection

ROOT = Path(__file__).resolve().parent.parent
#: The tool's header: full, both chip types, every extra that changes the output.
EXTRAS = ["sfdp", "sfdp_dumps", "datasheet", "datasheets", "records", "provenance"]
FULL = Selection.make("full", with_=EXTRAS)
pytestmark = [
    pytest.mark.skipif(sys.platform != "linux", reason="spidev is Linux-only"),
    pytest.mark.skipif(shutil.which("gcc") is None, reason="needs gcc"),
]


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """The tool (dynamic, for LD_PRELOAD), the shim, and a static build."""
    out = tmp_path_factory.mktemp("linux")
    extras = [a for e in EXTRAS for a in ("--with", e)]
    args = ["generate", "-o", str(out / "uspiflash.h"), "--level", "full"]
    assert main([*args, "--type", "nor", "--type", "nand", *extras]) == 0
    tool = out / "uspiflash-linux"
    version = f'-DUSPIFLASH_LINUX_VERSION="uspiflash {__version__}"'
    src = str(ROOT / "examples/linux/uspiflash-linux.c")
    common = [*CFLAGS, "-D_DEFAULT_SOURCE", version, f"-I{out}", src]
    subprocess.run(["gcc", "-Os", *common, "-o", str(tool)], check=True)
    shim = out / "fake_spidev.so"
    subprocess.run(
        [
            "gcc",
            *CFLAGS,
            "-shared",
            "-fPIC",
            "-O1",
            f"-I{ROOT / 'tests/c'}",
            str(ROOT / "tests/linux/fake_spidev.c"),
            "-o",
            str(shim),
            "-ldl",
        ],
        check=True,
    )
    static = out / "uspiflash-linux-static"
    res = subprocess.run(
        ["gcc", "-Os", "-static", *common, "-o", str(static)],
        capture_output=True,
        text=True,
        check=False,
    )
    return {"tool": tool, "shim": shim, **({"static": static} if res.returncode == 0 else {})}


def run(
    tool: Path, *args: str, spec: str | None = None, shim: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run ``tool``; with ``spec``, /dev/spidev-fake answers as that chip."""
    env = dict(os.environ)
    if spec is not None and shim is not None:
        env |= {
            "LD_PRELOAD": str(shim),
            "FAKE_SPIDEV": "/dev/spidev-fake",
            "FAKE_SPIDEV_SPEC": spec,
        }
    return subprocess.run([str(tool), *args], capture_output=True, text=True, env=env, check=False)


@parity
def test_offline_id_matches_spiflash(built: dict[str, Path]) -> None:
    db = database()
    rng = random.Random(9)
    for f in rng.sample(list(db.flashes), 150):
        res = run(built["tool"], "id", f.id.hex(), "--method", f.family.value, "--opcodes")
        assert res.returncode == 0, res.stderr
        assert res.stdout == oracle.text(db, f.family, f.id, FULL, opcodes=True)


@parity
def test_offline_json_matches_spiflash(built: dict[str, Path]) -> None:
    res = run(built["tool"], "id", "ef4018", "--json")
    assert res.returncode == 0, res.stderr
    want = oracle.json_text(database(), IdFamily.JEDEC, bytes.fromhex("ef4018"), FULL)
    assert res.stdout == want


def test_offline_unknown_id_exits_1(built: dict[str, Path]) -> None:
    res = run(built["tool"], "id", "ee7777")
    assert res.returncode == 1
    assert res.stdout == "\n"


#: Ids `spiflash id` refuses (exit 2), and spellings of ef4018 it takes.
BAD_IDS = ("ef401", "zz", "", " ", "0x", "0x0xef4018", "ef4g18", "0xef401", "x0ef4018", "ef,40")
EF4018 = ("0xEF4018", "ef:40:18", "EF-40_18", "ef4 018", " ef4018\t", "0X ef 40 18", "0 x ef4018")


def test_offline_bad_hex_is_a_usage_error(built: dict[str, Path]) -> None:
    for bad in BAD_IDS:
        res = run(built["tool"], "id", bad)
        assert res.returncode == 2, bad
        assert res.stdout == ""


def test_offline_id_too_long_is_a_usage_error(built: dict[str, Path]) -> None:
    """usf_lookup takes up to 255 bytes."""
    assert run(built["tool"], "id", "ef4018" + "ff" * 252).returncode == 0
    assert run(built["tool"], "id", "ef4018" + "ff" * 253).returncode == 2


@parity
def test_offline_id_spellings_match_spiflash(built: dict[str, Path]) -> None:
    """The tool reads an id as spiflash does (``spiflash.model.parse_id``)."""
    for bad in BAD_IDS:
        with pytest.raises(ValueError, match="not a hex id"):
            parse_id(bad)
    want = oracle.text(database(), IdFamily.JEDEC, bytes.fromhex("ef4018"), FULL, opcodes=False)
    for spelling in EF4018:
        assert parse_id(spelling) == bytes.fromhex("ef4018")
        res = run(built["tool"], "id", spelling)
        assert res.returncode == 0, spelling
        assert res.stdout == want


def test_json_with_sfdp_is_a_usage_error(built: dict[str, Path]) -> None:
    """The --sfdp lines are text: there is no JSON for them."""
    res = run(built["tool"], "-D", "/dev/spidev-fake", "--json", "--sfdp")
    assert res.returncode == 2
    assert res.stdout == ""
    assert res.stderr.startswith("usage: ")


#: Clocks ``-s`` takes (``k`` is x1000, ``M`` x1000000), and what it refuses:
#: empty, not decimal, trailing junk, 0, and past UINT32_MAX.
GOOD_HZ = ("1", "1000000", "400k", "1M", "50M", "4294967295", "4294967k", "4294M")
BAD_HZ = (
    "",
    " 1",
    "-1",
    "+1",
    "0x10",
    "1MHz",
    "1m",
    "1K",
    "1 ",
    "M",
    "0",
    "0k",
    "4294967296",
    "4294968k",
    "4295M",
    "99999999999999999999999",
)


def test_clock_is_validated(built: dict[str, Path]) -> None:
    for hz in GOOD_HZ:
        args = ("-D", "/dev/spidev-fake", "-s", hz)
        res = run(built["tool"], *args, spec="9f/1=ef4018 fill=ff", shim=built["shim"])
        assert res.returncode == 0, (hz, res.stderr)
        assert res.stdout.startswith("ef4018  Winbond"), hz
    for hz in BAD_HZ:
        res = run(built["tool"], "-D", "/dev/spidev-fake", "-s", hz)
        assert res.returncode == 2, hz
        assert res.stdout == "", hz
        assert res.stderr.startswith("uspiflash-linux: -s: not a clock in Hz"), hz
        assert "\nusage: " in res.stderr, hz


def test_help_is_on_stdout(built: dict[str, Path]) -> None:
    """Asked for, the usage is output (exit 0); a usage error stays an error."""
    for flag in ("-h", "--help"):
        res = run(built["tool"], flag)
        assert res.returncode == 0, flag
        assert res.stdout.startswith("usage: uspiflash-linux ")
        assert res.stderr == ""
    res = run(built["tool"], "--no-such-flag")
    assert res.returncode == 2
    assert res.stdout == ""
    assert res.stderr.startswith("usage: uspiflash-linux ")


@pytest.mark.skipif(not Path("/dev/full").exists(), reason="needs /dev/full")
def test_output_write_error_exits_2(built: dict[str, Path]) -> None:
    """Output that cannot be written (a full disk, here /dev/full) is an error,
    not a silent success."""
    with Path("/dev/full").open("w") as full:
        res = subprocess.run(
            [str(built["tool"]), "id", "ef4018"],
            stdout=full,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    assert res.returncode == 2
    assert res.stderr.startswith("uspiflash-linux: writing the output: ")


def test_closed_stdout_exits_2(built: dict[str, Path]) -> None:
    """With stdout closed, the same."""
    res = subprocess.run(
        ["sh", "-c", 'exec "$0" id ef4018 >&-', str(built["tool"])],
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert res.returncode == 2
    assert res.stderr.startswith("uspiflash-linux: writing the output: ")


def test_missing_device_exits_2(built: dict[str, Path], tmp_path: Path) -> None:
    res = run(built["tool"], "-D", str(tmp_path / "spidev9.9"))
    assert res.returncode == 2
    assert res.stdout == ""
    assert "spidev9.9" in res.stderr


@parity
def test_probe_through_spidev(built: dict[str, Path]) -> None:
    res = run(
        built["tool"],
        "-D",
        "/dev/spidev-fake",
        "--opcodes",
        spec="9f/1=ef4018 fill=ff",
        shim=built["shim"],
    )
    assert res.returncode == 0, res.stderr
    rdid = bytes.fromhex("ef4018") + b"\xff" * 7
    assert res.stdout == oracle.text(database(), IdFamily.JEDEC, rdid, FULL, opcodes=True)


def is25wp256_sfdp() -> bytes:
    """The IS25WP256's SFDP area as spiflash ships it (QEMU's table)."""
    (f,) = database().lookup("9d7019")
    assert f.sfdp is not None
    return f.sfdp.data


@parity
def test_sfdp_through_spidev(built: dict[str, Path]) -> None:
    dump = is25wp256_sfdp()
    res = run(
        built["tool"],
        "-D",
        "/dev/spidev-fake",
        "--sfdp",
        spec=f"9f/1=9d7019 sfdp={dump.hex()} fill=ff",
        shim=built["shim"],
    )
    assert res.returncode == 0, res.stderr
    rdid = bytes.fromhex("9d7019") + b"\xff" * 7
    text = oracle.text(database(), IdFamily.JEDEC, rdid, FULL, opcodes=False)
    assert res.stdout == text + oracle.sfdp_fields(dump)


def test_blank_bus_exits_2(built: dict[str, Path]) -> None:
    res = run(built["tool"], "-D", "/dev/spidev-fake", spec="fill=ff", shim=built["shim"])
    assert res.returncode == 2
    assert "no answer" in res.stdout


def test_unknown_chip_exits_1(built: dict[str, Path]) -> None:
    res = run(
        built["tool"], "-D", "/dev/spidev-fake", spec="9f/1=ee7777 fill=ff", shim=built["shim"]
    )
    assert res.returncode == 1
    assert "jedec ee7777" in res.stdout


def test_version(built: dict[str, Path]) -> None:
    res = run(built["tool"], "--version")
    assert res.returncode == 0
    assert res.stdout == f"uspiflash-linux: uspiflash {__version__}\n"


def test_static_build_runs(built: dict[str, Path]) -> None:
    if "static" not in built:
        pytest.skip("no static libc (libc6-dev's libc.a) to link against")
    res = run(built["static"], "id", "ef4018")
    assert res.returncode == 0
    assert res.stdout.startswith("ef4018  Winbond")
    if shutil.which("file"):
        kind = subprocess.run(
            ["file", str(built["static"])], capture_output=True, text=True, check=True
        )
        assert "statically linked" in kind.stdout


@parity
def test_nand_probe_through_spidev(built: dict[str, Path]) -> None:
    """A SPI NAND chip (W25N01GV) sends a dummy byte before its id to plain
    9f, and its id to 9f 00: the tool's header has NAND chips too."""
    res = run(
        built["tool"],
        "-D",
        "/dev/spidev-fake",
        spec="9f/1=00efaa21 9f/2=efaa21 fill=ff",
        shim=built["shim"],
    )
    assert res.returncode == 0, res.stderr
    rdid = bytes.fromhex("efaa21") + b"\xff" * 6
    assert res.stdout == oracle.text(database(), IdFamily.JEDEC, rdid, FULL, opcodes=False)
    assert "(nand)" in res.stdout
