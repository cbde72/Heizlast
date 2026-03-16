from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIALOG = ROOT / "src" / "heizlast" / "ui" / "dialogs" / "project_settings_dialog.py"


def test_project_settings_uses_left_navigation_sidebar_and_stacked_pages():
    src = PROJECT_DIALOG.read_text(encoding="utf-8")
    assert 'class _SettingsNavList(QListWidget):' in src
    assert 'self.pages = QStackedWidget()' in src
    assert 'self.tabs = sidebar' in src
    assert 'self.tabs.currentRowChanged.connect(self.pages.setCurrentIndex)' in src
    assert 'sidebar.setObjectName("projectSettingsNav")' in src
    assert 'self._add_nav_page("DG Dach"' in src
    assert 'self.tabs.setCurrentRow(idx)' in src
