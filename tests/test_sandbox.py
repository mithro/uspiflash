"""Resource limits sized from the machine's load."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from typing import TYPE_CHECKING

import pytest

from uspiflash import sandbox
from uspiflash.sandbox import GIB, Limits, compute_limits, current_limits, main, wrap

if TYPE_CHECKING:
    from pathlib import Path

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
    argv = wrap(["make", "-j", "{jobs}"], Limits(2 * GIB, 3), 60, "uspiflash-sandbox-123")
    assert argv[:4] == ["systemd-run", "--user", "--scope", "--quiet"]
    assert "--unit=uspiflash-sandbox-123" in argv
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


class _FakePopen:
    """A stand-in for ``subprocess.Popen``: records the argv it was started
    with and the signals sent to it; ``wait()`` returns a canned code, or
    raises once to simulate Ctrl-C landing during the real wait."""

    def __init__(
        self,
        argv: list[str],
        *,
        returncode: int = 0,
        raise_on_first_wait: BaseException | None = None,
    ) -> None:
        self.argv = argv
        self.returncode = returncode
        self._raise_on_first_wait = raise_on_first_wait
        self.signals: list[int] = []

    def wait(self) -> int:
        if self._raise_on_first_wait is not None:
            exc, self._raise_on_first_wait = self._raise_on_first_wait, None
            raise exc
        return self.returncode

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)


def test_main_runs_the_wrapped_command_without_starting_it_via_the_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limits = Limits(2 * GIB, 3)
    calls: list[list[str]] = []

    def fake_popen(argv: list[str], env: dict[str, str]) -> _FakePopen:
        del env
        calls.append(list(argv))
        return _FakePopen(argv, returncode=42)

    monkeypatch.setattr(sandbox, "current_limits", lambda: limits)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/systemd-run")
    monkeypatch.setattr(os, "getpid", lambda: 123)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    assert main(["--timeout", "10", "--", "make", "-j", "{jobs}"]) == 42
    assert calls == [wrap(["make", "-j", "{jobs}"], limits, 10, "uspiflash-sandbox-123")]


def test_main_keeps_an_inner_double_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only a *leading* ``--`` (argparse's own separator) is dropped; one
    inside the wrapped command (e.g. ``git diff -- path``) survives."""
    limits = Limits(2 * GIB, 3)
    calls: list[list[str]] = []

    def fake_popen(argv: list[str], env: dict[str, str]) -> _FakePopen:
        del env
        calls.append(list(argv))
        return _FakePopen(argv, returncode=0)

    monkeypatch.setattr(sandbox, "current_limits", lambda: limits)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/systemd-run")
    monkeypatch.setattr(os, "getpid", lambda: 1)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    assert main(["--", "printf", "[%s]", "a", "--", "b"]) == 0
    expected = wrap(["printf", "[%s]", "a", "--", "b"], limits, 3600, "uspiflash-sandbox-1")
    assert calls == [expected]
    assert expected[-5:] == ["printf", "[%s]", "a", "--", "b"]


def test_main_forwards_ctrl_c_as_sigterm_and_returns_130(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limits = Limits(2 * GIB, 3)
    fake = _FakePopen(["irrelevant"], raise_on_first_wait=KeyboardInterrupt())

    monkeypatch.setattr(sandbox, "current_limits", lambda: limits)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/systemd-run")
    monkeypatch.setattr(subprocess, "Popen", lambda _argv, **_kwargs: fake)

    assert main(["--", "sleep", "4242"]) == 130
    assert fake.signals == [signal.SIGTERM]


def test_main_points_tmpdir_at_the_current_directorys_tmp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No /tmp: the command's temporary files go in ./tmp, made if missing."""
    envs: list[dict[str, str]] = []

    def fake_popen(argv: list[str], env: dict[str, str]) -> _FakePopen:
        envs.append(env)
        return _FakePopen(argv)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USPIFLASH_SANDBOX_TEST", "kept")
    monkeypatch.setattr(sandbox, "current_limits", lambda: Limits(GIB, 1))
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/systemd-run")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    assert main(["--", "true"]) == 0
    (env,) = envs
    assert env["TMPDIR"] == str(tmp_path / "tmp")
    assert (tmp_path / "tmp").is_dir()
    assert env["USPIFLASH_SANDBOX_TEST"] == "kept"


def test_main_refuses_to_run_unsandboxed_when_systemd_run_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sandbox, "current_limits", lambda: Limits(GIB, 1))
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(SystemExit):
        main(["--", "true"])
