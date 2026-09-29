"""Experiments run with one command, from anywhere in the repository."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from spiflash.db import database

from uspiflash import research
from uspiflash.cli import main

EXPERIMENT = (
    '"""A toy experiment."""\n'
    "import json\nfrom pathlib import Path\n\n"
    "def collect():\n    return {'answer': 42}\n\n"
    "if __name__ == '__main__':\n"
    "    Path('results').mkdir(exist_ok=True)\n"
    "    Path('results/out.json').write_text(json.dumps(collect()))\n"
)


def make(tmp_path: Path) -> Path:
    d = tmp_path / "experiments" / "2026-01-01-toy"
    d.mkdir(parents=True)
    (d / "run.py").write_text(EXPERIMENT)
    return tmp_path


def test_find_root_walks_up(tmp_path: Path) -> None:
    root = make(tmp_path)
    deep = root / "a" / "b"
    deep.mkdir(parents=True)
    assert research.find_root(deep) == root


def test_find_root_missing_raises(tmp_path: Path) -> None:
    deep = tmp_path / "a"
    deep.mkdir()
    with pytest.raises(FileNotFoundError, match="no experiments/"):
        research.find_root(deep, ceiling=tmp_path)


def test_find_root_looks_no_higher_than_the_ceiling(tmp_path: Path) -> None:
    root = make(tmp_path)
    deep = root / "a" / "b"
    deep.mkdir(parents=True)
    assert research.find_root(deep, ceiling=root) == root
    with pytest.raises(FileNotFoundError, match="no experiments/"):
        research.find_root(deep, ceiling=root / "a")


def test_run_writes_results_in_the_experiment(tmp_path: Path) -> None:
    root = make(tmp_path)
    assert research.run("2026-01-01-toy", root) == 0
    out = root / "experiments" / "2026-01-01-toy" / "results" / "out.json"
    assert json.loads(out.read_text()) == {"answer": 42}


def test_run_unknown_slug_names_known_slugs(tmp_path: Path) -> None:
    root = make(tmp_path)
    with pytest.raises(FileNotFoundError, match="2026-01-01-toy"):
        research.run("no-such-experiment", root)


def test_run_restores_cwd_even_on_error(tmp_path: Path) -> None:
    root = make(tmp_path)
    (root / "experiments" / "2026-01-01-toy" / "run.py").write_text("raise ValueError('boom')\n")
    start = Path.cwd()
    with pytest.raises(ValueError, match="boom"):
        research.run("2026-01-01-toy", root)
    assert Path.cwd() == start


def test_cli_lists_experiments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(make(tmp_path))
    assert main(["research", "list"]) == 0
    assert capsys.readouterr().out == "2026-01-01-toy\n"


def test_cli_runs_an_experiment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(make(tmp_path))
    assert main(["research", "run", "2026-01-01-toy"]) == 0
    out = tmp_path / "experiments" / "2026-01-01-toy" / "results" / "out.json"
    assert json.loads(out.read_text()) == {"answer": 42}


def test_cli_unknown_experiment_is_an_error_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(make(tmp_path))
    assert main(["research", "run", "no-such-experiment"]) == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "uspiflash: no experiment 'no-such-experiment' (known: 2026-01-01-toy)\n"


def test_cli_research_with_no_subcommand_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(make(tmp_path))
    assert main(["research"]) == 2


def test_the_statistics_experiment_counts_the_database() -> None:
    root = research.find_root(Path(__file__).parent)
    ns = runpy.run_path(str(root / "experiments/2026-09-28-database-statistics/run.py"))
    stats = ns["collect"]()
    assert stats["chip_ids"] == len(database().flashes)
    assert stats["layout_bytes"]["full"] > stats["layout_bytes"]["id"]
    # The per-table sizes add up to each selection's total.
    assert stats["layout_bytes"] == {
        sel: sum(tables.values()) for sel, tables in stats["layout_tables"].items()
    }
    # Per id, a shared name counts again; deduplicated, it does not.
    assert stats["names_per_id"] >= stats["names"]
    assert stats["max_names_per_id"] >= 1
    assert set(stats["host"]) == {"python", "python_implementation", "system", "machine"}


def test_tests_cannot_find_the_real_repository_from_their_tmp_path(tmp_path: Path) -> None:
    """conftest.py stops find_root at pytest's basetemp, which is inside the
    repository: no test can reach (and rewrite) the committed files."""
    with pytest.raises(FileNotFoundError, match="no experiments/"):
        research.find_root(tmp_path)


EXPERIMENTS = sorted(research.find_root(Path(__file__).parent).glob("experiments/*/run.py"))


@pytest.mark.parametrize("script", EXPERIMENTS, ids=lambda p: p.parent.name)
def test_every_experiment_type_checks(script: Path) -> None:
    """mypy --strict on each experiment's script on its own: every one is
    run.py, and mypy refuses two modules of one name in one run."""
    pytest.importorskip("mypy")
    root = script.parent.parent.parent
    res = subprocess.run(
        [sys.executable, "-m", "mypy", str(script.relative_to(root))],
        capture_output=True,
        text=True,
        check=False,
        cwd=root,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def test_the_sfdp_experiment_compares_every_dump() -> None:
    root = research.find_root(Path(__file__).parent)
    ns = runpy.run_path(str(root / "experiments/2026-09-29-sfdp-vs-database/run.py"))
    result = ns["collect"]()
    dumps = [d for f in database().flashes for d in f.sfdp_dumps]
    assert result["dumps"] == len(dumps) == len(result["rows"])
    assert result["chip_ids"] == sum(1 for f in database().flashes if f.sfdp_dumps)
    assert set(result["agree"]) == {"size", "page_size", "sector_size", "features", "operations"}
    assert all(0 <= n <= result["dumps"] for n in result["agree"].values())
