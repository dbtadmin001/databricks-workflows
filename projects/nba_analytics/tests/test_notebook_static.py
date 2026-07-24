from pathlib import Path

import pytest


@pytest.mark.local_fast
def test_databricks_notebooks_do_not_depend_on_dunder_file():
    notebook_dir = Path(__file__).resolve().parents[1] / "src" / "notebooks"
    offenders = [
        path.relative_to(notebook_dir).as_posix()
        for path in sorted(notebook_dir.glob("*.py"))
        if "__file__" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


@pytest.mark.local_fast
def test_bundled_raw_dataset_contains_required_csvs():
    dataset_dir = Path(__file__).resolve().parents[1] / "dataset"
    expected = {
        "teams.csv",
        "players.csv",
        "roster_season1.csv",
        "roster_season2.csv",
        "games.csv",
        "player_game_stats.csv",
    }

    assert {path.name for path in dataset_dir.glob("*.csv")} >= expected


@pytest.mark.local_fast
def test_unity_catalog_bound_code_does_not_use_input_file_name():
    source_dir = Path(__file__).resolve().parents[1] / "src"
    offenders = [
        path.relative_to(source_dir).as_posix()
        for path in sorted(source_dir.rglob("*.py"))
        if "input_file_name" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
