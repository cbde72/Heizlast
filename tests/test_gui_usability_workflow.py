from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_dashboard_exposes_next_step_and_room_inspector():
    build = _src("src/heizlast/ui/build_mixin.py")
    comfort = _src("src/heizlast/ui/comfort_mixin.py")
    assert "self.lbl_dashboard_next_step" in build
    assert "self.btn_dashboard_next_step" in build
    assert "self.lbl_dashboard_room_inspector_text" in build
    assert "def _refresh_dashboard_next_step" in comfort
    assert "def _refresh_dashboard_room_inspector" in comfort


def test_workspace_switcher_controls_main_dock_sets():
    build = _src("src/heizlast/ui/build_mixin.py")
    assert "def _create_workspace_switcher" in build
    assert "def _set_workspace" in build
    assert '"planning": ("properties", "elements")' in build
    assert '"proof": ("dashboard", "plausibility")' in build
    assert '"roof": ("attic", "dashboard")' in build
    assert '"export": ("dashboard", "plausibility")' in build


def test_room_warning_status_is_shared_by_matrix_and_plan_items():
    comfort = _src("src/heizlast/ui/comfort_mixin.py")
    redraw = _src("src/heizlast/ui/redraw_mixin.py")
    graphics = _src("src/heizlast/ui/graphics.py")
    assert "def _room_status_summary" in comfort
    assert "def _refresh_room_visual_warnings" in comfort
    assert "_refresh_room_visual_warnings(list(self.rooms.values()), list(self.elements))" in redraw
    assert "def set_warning_status" in graphics
    assert 'warning_status == "error"' in graphics
