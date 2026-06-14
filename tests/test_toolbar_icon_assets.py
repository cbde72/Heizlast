from pathlib import Path


def test_icon_asset_set_is_present_and_build_mixin_references_auto_walls_icon():
    root = Path(__file__).resolve().parents[1]
    icons_dir = root / "src" / "heizlast" / "assets" / "icons"
    expected = {
        "select", "draw_floorplan", "rect_room", "l_room", "polygon_room",
        "split_room", "merge_rooms", "subtract_rooms", "window_insert", "door_insert",
        "auto_walls", "auto_keller", "project_settings", "view_3d",
        "regen", "delete_selection",
    }
    existing = {p.stem for p in icons_dir.glob("*.svg")}
    assert expected.issubset(existing)

    build_mixin = (root / "src" / "heizlast" / "ui" / "build_mixin.py").read_text(encoding="utf-8")
    assert 'icon=self._toolbar_icon("auto_walls")' in build_mixin
    assert 'def _load_asset_icon' in build_mixin
