from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_MIXIN = ROOT / "src" / "heizlast" / "ui" / "build_mixin.py"
MISC_MIXIN = ROOT / "src" / "heizlast" / "ui" / "misc_mixin.py"
DIALOG = ROOT / "src" / "heizlast" / "ui" / "house_side_dialog.py"


def test_project_toolbar_and_menu_expose_house_side_view():
    src = BUILD_MIXIN.read_text(encoding="utf-8")
    assert 'self.act_show_house_side = self._make_action(' in src
    assert '"Haus Seitenansicht"' in src
    assert 'menu.addAction(self.act_show_house_side)' in src
    assert 'self.act_show_house_side,' in src


def test_misc_mixin_collects_and_launches_house_side_view():
    src = MISC_MIXIN.read_text(encoding="utf-8")
    assert 'from .house_side_dialog import HouseSideDialog' in src
    assert 'def _collect_house_side_scene_data(self) -> dict:' in src
    assert '"building_depth_m": building_depth' in src
    assert '"Keller"' in src
    assert '"Erdgeschoss"' in src
    assert '"Obergeschoss"' in src
    assert 'def _on_show_house_side_view(self) -> None:' in src


def test_house_side_dialog_draws_levels_and_roof():
    src = DIALOG.read_text(encoding="utf-8")
    assert 'class HouseSideDialog(QDialog):' in src
    assert '"Frontansicht"' in src
    assert '"Seite rechts"' in src
    assert '"Ansicht von hinten"' in src
    assert '"Seite links"' in src
    assert 'def keyPressEvent(self, event):' in src
    assert 'Qt.Key_Left' in src
    assert 'Qt.Key_Right' in src
    assert 'self._view = _HouseSideView(self._scene, self)' in src
    assert 'def _roof_polygon(' in src
    assert 'Gelände' in src
    assert 'QGraphicsRectItem' in src
