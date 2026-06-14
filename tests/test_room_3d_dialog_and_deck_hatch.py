from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_MIXIN = ROOT / "src" / "heizlast" / "ui" / "build_mixin.py"
SELECTION_MIXIN = ROOT / "src" / "heizlast" / "ui" / "selection_mixin.py"
MISC_MIXIN = ROOT / "src" / "heizlast" / "ui" / "misc_mixin.py"
ROOM_3D_DIALOG = ROOT / "src" / "heizlast" / "ui" / "room_3d_dialog.py"


def test_room_3d_action_is_exposed_as_non_modal_view():
    build_src = BUILD_MIXIN.read_text(encoding="utf-8")
    misc_src = MISC_MIXIN.read_text(encoding="utf-8")
    dialog_src = ROOM_3D_DIALOG.read_text(encoding="utf-8")

    assert 'self.act_show_3d_room = self._make_action(' in build_src
    assert '"3D Raum"' in build_src
    assert "menu.addAction(self.act_show_3d_room)" in build_src
    assert "self.act_show_3d_room," in build_src
    assert "def _on_show_3d_room(self) -> None:" in misc_src
    assert "class Room3DDialog(QDialog):" in dialog_src
    assert "self.setWindowModality(Qt.NonModal)" in dialog_src
    assert "self._view = gl.GLViewWidget(self)" in dialog_src


def test_room_3d_dialog_updates_on_plan_room_selection():
    selection_src = SELECTION_MIXIN.read_text(encoding="utf-8")

    assert "self._update_room_3d_dialog_selection()" in selection_src
    assert "def _update_room_3d_dialog_selection(self) -> None:" in selection_src
    assert "dlg.set_room(room, elements)" in selection_src


def test_deck_selection_hatches_room_footprint():
    selection_src = SELECTION_MIXIN.read_text(encoding="utf-8")

    assert "deck_kind_for_element" in selection_src
    assert "def _show_deck_hatch(self, element: ElementModel) -> None:" in selection_src
    assert "QGraphicsPathItem(path)" in selection_src
    assert "Qt.BDiagPattern" in selection_src
    assert "self._deck_hatch_item = hatch" in selection_src


def test_toolbar_contains_yellow_roof_gable_zero_toggle():
    build_src = BUILD_MIXIN.read_text(encoding="utf-8")
    misc_src = MISC_MIXIN.read_text(encoding="utf-8")

    assert "self.act_zero_roof_gable_transfer = self._make_action(" in build_src
    assert '"Dach/Giebel 0"' in build_src
    assert "checkable=True" in build_src
    assert "self.act_zero_roof_gable_transfer," in build_src
    assert "def _on_toggle_zero_roof_gable_transfer(self, checked: bool) -> None:" in misc_src
    assert "#facc15" in misc_src
    assert 'action.setText("0W" if enabled else "Dach/Giebel 0")' in misc_src
    assert "btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if enabled else Qt.ToolButtonIconOnly)" in misc_src
    assert "zero_roof_gable_transmission" in misc_src


def test_roof_gable_zero_toggle_refreshes_visible_views_immediately():
    misc_src = MISC_MIXIN.read_text(encoding="utf-8")

    assert "def _refresh_views_after_zero_roof_gable_transfer(self) -> None:" in misc_src
    assert "self._refresh_attic_preview()" in misc_src
    assert "self._update_room_3d_dialog_selection()" in misc_src
    assert "view.viewport().update()" in misc_src
    assert "self._refresh_views_after_zero_roof_gable_transfer()" in misc_src
