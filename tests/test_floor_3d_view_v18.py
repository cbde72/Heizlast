from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_MIXIN = ROOT / "src" / "heizlast" / "ui" / "build_mixin.py"
MISC_MIXIN = ROOT / "src" / "heizlast" / "ui" / "misc_mixin.py"


def test_project_menu_and_toolbar_expose_floor_3d_action():
    src = BUILD_MIXIN.read_text(encoding="utf-8")
    assert 'self.act_show_3d_floor = self._make_action(' in src
    assert '"3D Geschoss"' in src
    assert 'menu.addAction(self.act_show_3d_floor)' in src
    assert 'self.act_show_3d_floor,' in src


def test_plan_info_bar_does_not_contain_floor_3d_button():
    src = BUILD_MIXIN.read_text(encoding="utf-8")
    assert 'self.btn_show_current_floor_3d = QPushButton("3D Geschoss")' not in src
    assert 'self.btn_show_current_floor_3d.clicked.connect(self._on_show_3d_floor)' not in src


def test_misc_mixin_contains_floor_3d_helpers():
    src = MISC_MIXIN.read_text(encoding="utf-8")
    assert 'def _collect_room_polygons_by_floor(self) -> dict:' in src
    assert 'def _current_floor_key(self) -> str:' in src
    assert 'def _plot_3d_floor_detail(self, ax, floor: str, poly_by_floor: dict, heights: dict) -> None:' in src
    assert 'def _on_show_3d_floor(self) -> None:' in src


def test_floor_3d_helpers_cover_openings_on_wall_segments():
    src = MISC_MIXIN.read_text(encoding="utf-8")
    assert 'def _wall_segment_key(self, p0, p1, ndigits: int = 6) -> tuple:' in src
    assert 'def _wall_elements_for_floor(self, floor: str) -> dict:' in src
    assert 'def _combined_wall_openings(self, walls: list, wall_length_m: float) -> list[dict]:' in src
    assert 'def _render_wall_with_openings(self, ax, p0, p1, z0: float, z1: float, wall_entry: dict, material_style: dict) -> tuple[int, int]:' in src
    assert 'self._add_opening_panel(ax, pa, pb, sill, top, opening_type=op_here["type"])' in src
    assert 'Fenster: {total_windows} · Türen: {total_doors}' in src
