"""Tests for per-user data paths and filename sanitizing."""

from macroengine import paths


def test_app_data_and_routines_dir_created(tmp_path, monkeypatch):
    # Redirect HOME/APPDATA so the test never touches the real profile.
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path / "home"))

    rdir = paths.routines_dir()
    assert rdir.exists() and rdir.is_dir()
    assert rdir.parent == paths.app_data_dir()
    assert rdir.name == "routines"

    mdir = paths.macros_dir()
    assert mdir.exists() and mdir.is_dir()
    assert mdir.parent == paths.app_data_dir()
    assert mdir.name == "macros"


def test_safe_filename():
    assert paths.safe_filename("Daily quest") == "Daily quest"
    assert paths.safe_filename("boss/run:2") == "boss_run_2"
    assert paths.safe_filename("") == "routine"
    assert paths.safe_filename("   ") == "routine"
    assert paths.safe_filename("a*b?c") == "a_b_c"


def test_unique_name_increments_on_collision(tmp_path):
    # First save keeps the name.
    assert paths.unique_name(tmp_path, "routine") == "routine"
    (tmp_path / "routine.json").write_text("{}")
    # Next one bumps to (1), then (2)…
    assert paths.unique_name(tmp_path, "routine") == "routine(1)"
    (tmp_path / "routine(1).json").write_text("{}")
    assert paths.unique_name(tmp_path, "routine") == "routine(2)"


def test_unique_name_excludes_own_path(tmp_path):
    # Re-saving the file we already own keeps its name (no bump).
    own = tmp_path / "routine.json"
    own.write_text("{}")
    assert paths.unique_name(tmp_path, "routine", exclude=own) == "routine"
