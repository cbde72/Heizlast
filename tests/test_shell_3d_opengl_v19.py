from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_MIXIN = ROOT / "src" / "heizlast" / "ui" / "build_mixin.py"
MISC_MIXIN = ROOT / "src" / "heizlast" / "ui" / "misc_mixin.py"
GL_DIALOG = ROOT / "src" / "heizlast" / "ui" / "gl_3d_shell_dialog.py"


def test_project_menu_and_plan_bar_expose_shell_gl_action():
    src = BUILD_MIXIN.read_text(encoding="utf-8")
    assert 'self.act_show_3d_shell_gl = self._make_action(' in src
    assert '"3D Gebäudehülle+"' in src
    assert 'menu.addAction(self.act_show_3d_shell_gl)' in src
    assert 'self.btn_show_shell_3d_gl = QPushButton("3D Hülle+")' in src
    assert 'self.btn_show_shell_3d_gl.clicked.connect(self._on_show_3d_shell_gl)' in src


def test_misc_mixin_contains_shell_gl_scene_builder_and_launcher():
    src = MISC_MIXIN.read_text(encoding="utf-8")
    assert 'from .gl_3d_shell_dialog import Shell3DDialog' in src
    assert 'def _collect_shell_3d_scene_data(self) -> dict:' in src
    assert 'def _on_show_3d_shell_gl(self) -> None:' in src
    assert '"thickness_m": self._shell_wall_thickness_m(),' in src
    assert '"roof_faces": roof_faces,' in src
    assert '"roof_lines": roof_lines,' in src


def test_gl_dialog_contains_opening_reveals_and_wall_boxes():
    src = GL_DIALOG.read_text(encoding="utf-8")
    assert 'class Shell3DDialog(QDialog):' in src
    assert 'self._view = gl.GLViewWidget(self)' in src
    assert 'def _add_wall_box(' in src
    assert 'def _add_opening_reveals(' in src
    assert 'def _add_roof_face(' in src
