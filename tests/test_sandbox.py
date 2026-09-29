"""Resource limits sized from the machine's load."""

from __future__ import annotations

from typing import TYPE_CHECKING

from uspiflash.sandbox import GIB, Limits, compute_limits, current_limits, main, wrap

if TYPE_CHECKING:
    import pytest

MEMINFO = "MemTotal:       32000000 kB\nMemAvailable:   20000000 kB\n"
CALM = "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
STALLING = "some avg10=25.00 avg60=5.00 avg300=1.00 total=9\n"


def test_memory_leaves_a_reserve_and_is_capped() -> None:
    lim = compute_limits(MEMINFO, "0.50 0.40 0.30 1/100 5", CALM, 12)
    reserve = max(4 * GIB, 32000000 * 1024 * 15 // 100)
    assert lim.memory_bytes == min(20000000 * 1024 - reserve, 16 * GIB)


def test_cpus_leave_room_for_load_and_the_desktop() -> None:
    assert compute_limits(MEMINFO, "3.20 1 1 1/1 1", CALM, 12).cpus == 12 - 4 - 2


def test_never_below_one_cpu_or_one_gib() -> None:
    lim = compute_limits("MemTotal: 4000000 kB\nMemAvailable: 100 kB\n", "99 1 1 1/1 1", CALM, 4)
    assert lim == Limits(GIB, 1)


def test_memory_pressure_halves_the_limits() -> None:
    calm = compute_limits(MEMINFO, "0 0 0 1/1 1", CALM, 12)
    busy = compute_limits(MEMINFO, "0 0 0 1/1 1", STALLING, 12)
    assert busy.memory_bytes == max(calm.memory_bytes // 2, GIB)
    assert busy.cpus == max(1, calm.cpus // 2)


def test_wrap_runs_in_a_limited_scope_with_a_timeout() -> None:
    argv = wrap(["make", "-j", "{jobs}"], Limits(2 * GIB, 3), 60)
    assert argv[:4] == ["systemd-run", "--user", "--scope", "--quiet"]
    assert f"-pMemoryMax={2 * GIB}" in argv
    assert "-pMemorySwapMax=0" in argv
    assert "-pCPUQuota=300%" in argv
    assert argv[-6:] == ["timeout", "--kill-after=30", "60", "make", "-j", "3"]


def test_current_limits_reads_the_real_machine() -> None:
    lim = current_limits()
    assert lim.cpus >= 1
    assert lim.memory_bytes >= GIB


def test_main_print_limits_reports_memory_and_cpus(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--print-limits"]) == 0
    out = capsys.readouterr().out
    assert "memory" in out
    assert "cpus" in out


def test_main_with_no_command_does_not_run_anything() -> None:
    assert main([]) == 0


def test_main_runs_a_wrapped_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--timeout", "10", "--", "true"]) == 0
    capsys.readouterr()
