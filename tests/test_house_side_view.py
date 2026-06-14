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
    assert 'def _collect_house_side_dormers(self, attic) -> list[dict]:' in src
    assert 'def _collect_house_side_windows(' in src
    assert '"opening_type": "door" if is_door else "window"' in src
    assert 'def _collect_house_side_projection_edges(' in src
    assert '"windows": self._collect_house_side_windows(' in src
    assert '"projection_edges": self._collect_house_side_projection_edges(' in src
    assert '"dormers": self._collect_house_side_dormers(attic)' in src
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
    assert 'def _add_dormers(' in src
    assert 'def _visible_dormers_for_view(' in src
    assert 'def _add_dormer_windows(' in src
    assert 'def _add_projection_edges(' in src
    assert 'def _add_windows(self, floor_rect: QRectF, idx: int, view_key: str, level: dict)' in src
    assert 'door_pen = QPen(QColor("#8b451c"), 1.3)' in src
    assert 'Qt.DashLine' in src
    assert 'Gelände' in src
    assert 'QGraphicsRectItem' in src
