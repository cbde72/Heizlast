from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = ROOT / "src" / "heizlast" / "ui" / "main_window.py"
LOAD_SAVE = ROOT / "src" / "heizlast" / "ui" / "load_save_mixin.py"


def test_main_window_schedules_last_project_load_on_startup():
    src = MAIN_WINDOW.read_text(encoding="utf-8")

    assert "QTimer.singleShot(0, self._load_last_project_on_startup)" in src


def test_load_save_mixin_persists_and_loads_last_project_quietly():
    src = LOAD_SAVE.read_text(encoding="utf-8")

    assert 'self._settings.setValue("last_project_file", str(rooms_path))' in src
    assert "def _startup_project_candidates(self) -> list[Path]:" in src
    assert "def _load_last_project_on_startup(self) -> None:" in src
    assert "self._load_project_from_path(rooms_path, quiet=True)" in src
    assert "def _load_project_from_path(self, rooms_path: Path, *, quiet: bool = False) -> bool:" in src
    assert "def _fit_loaded_plan_views() -> None:" in src
    assert "QTimer.singleShot(0, _fit_loaded_plan_views)" in src
    assert "view.fit_content()" in src
    assert "if not quiet:" in src
