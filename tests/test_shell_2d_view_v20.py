from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_MIXIN = ROOT / "src" / "heizlast" / "ui" / "build_mixin.py"
MISC_MIXIN = ROOT / "src" / "heizlast" / "ui" / "misc_mixin.py"
DIALOG = ROOT / "src" / "heizlast" / "ui" / "shell_2d_dialog.py"


def test_project_menu_and_plan_bar_expose_shell_2d_action():
    src = BUILD_MIXIN.read_text(encoding="utf-8")
    assert 'self.act_show_2d_shell = self._make_action(' in src
    assert '"2D Gebäudehülle+"' in src
    assert 'menu.addAction(self.act_show_2d_shell)' in src
    assert 'self.btn_show_shell_2d = QPushButton("2D Hülle+")' in src
    assert 'self.btn_show_shell_2d.clicked.connect(self._on_show_2d_shell)' in src


def test_misc_mixin_contains_shell_2d_scene_builder_and_launcher():
    src = MISC_MIXIN.read_text(encoding="utf-8")
    assert 'from .shell_2d_dialog import Shell2DDialog' in src
    assert 'def _collect_shell_2d_scene_data(self) -> dict:' in src
    assert 'def _on_show_2d_shell(self) -> None:' in src
    assert 'scene_data["roof_plan_lines"] = roof_plan_lines' in src
    assert 'scene_data["px_per_m"] = 140.0' in src


def test_shell_2d_dialog_contains_wall_thickness_openings_and_roof_lines():
    src = DIALOG.read_text(encoding="utf-8")
    assert 'class Shell2DDialog(QDialog):' in src
    assert 'self._view = _Shell2DView(self._scene, self)' in src
    assert 'def _add_wall(' in src
    assert 'def _add_opening_reveals(' in src
    assert 'def _add_roof_line(' in src
