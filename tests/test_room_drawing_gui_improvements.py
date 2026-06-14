from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_properties_dock_exposes_point_editor_and_drawing_template():
    src = _src("src/heizlast/ui/build_mixin.py")
    assert "self.tbl_room_points = QTableWidget(0, 2)" in src
    assert "self.tbl_room_points.itemChanged.connect(self._on_room_points_table_changed)" in src
    assert "self.cb_new_room_usage" in src
    assert "self.sp_new_room_height" in src
    assert "self.lbl_drawing_snap_hint" in src


def test_selection_mixin_applies_numeric_polygon_points_and_warnings():
    src = _src("src/heizlast/ui/selection_mixin.py")
    assert "def _on_room_points_table_changed" in src
    assert "validate_orthogonal_polygon(pts)" in src
    assert "room.set_polygon_points(pts)" in src
    assert "def _room_geometry_warnings" in src
    assert "BBox-Überlappung" in src


def test_drawing_preview_template_snap_and_background_are_wired():
    src = _src("src/heizlast/ui/misc_mixin.py")
    assert "def _preview_measure_text" in src
    assert "Fanglinie: vertikale Raumkante" in src
    assert "def _apply_new_room_template" in src
    assert "usage_defaults(usage)" in src
    assert "def _on_load_floorplan_background" in src
    assert "fitz.open(path)" in src


def test_plan_view_and_opening_insert_support_new_drawing_workflow():
    graphics = _src("src/heizlast/ui/graphics.py")
    opening = _src("src/heizlast/ui/window_insert_mixin.py")
    misc = _src("src/heizlast/ui/misc_mixin.py")
    assert "def set_background_pixmap" in graphics
    assert "QGraphicsPixmapItem" in graphics
    assert "unbeheizt" in graphics and "DashLine" in graphics
    assert "max_dist=1.2" in opening
    assert "view.mapToScene(event.position().toPoint())" in misc
    assert "self._add_opening_at(floor, p, opening_kind=opening_kind)" in misc
