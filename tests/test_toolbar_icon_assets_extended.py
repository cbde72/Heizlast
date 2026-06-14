from pathlib import Path


def test_extended_toolbar_icon_asset_set_is_present():
    root = Path(__file__).resolve().parents[1]
    icons_dir = root / "src" / "heizlast" / "assets" / "icons"
    expected = {
        "new", "new_with_settings", "open", "save", "save_as", "export", "quit",
        "project_settings", "auto_walls", "auto_keller", "view_3d", "delete_selection",
        "delete_windows", "undo", "redo", "select", "draw_floorplan", "rect_room",
        "l_room", "polygon_room", "split_room", "merge_rooms", "subtract_rooms",
        "delete_room", "regen", "fit_view", "label_outer", "label_windows",
        "label_inner", "debug_overlay", "attic_markers", "area_ref_outer", "heatmap",
        "window_insert", "door_insert", "roof_settings", "go_dg", "roof_profile",
    }
    existing = {p.stem for p in icons_dir.glob("*.svg")}
    assert expected.issubset(existing)


def test_build_mixin_uses_new_toolbar_icons_for_secondary_actions():
    root = Path(__file__).resolve().parents[1]
    build_mixin = (root / "src" / "heizlast" / "ui" / "build_mixin.py").read_text(encoding="utf-8")
    for fragment in [
        '_toolbar_icon("new_with_settings")',
        '_toolbar_icon("delete_windows")',
        '_toolbar_icon("undo")',
        '_toolbar_icon("redo")',
        '_toolbar_icon("delete_room")',
        '_toolbar_icon("label_outer")',
        '_toolbar_icon("label_windows")',
        '_toolbar_icon("label_inner")',
        '_toolbar_icon("debug_overlay")',
        '_toolbar_icon("area_ref_outer")',
        '_toolbar_icon("heatmap")',
        '_toolbar_icon("door_insert")',
    ]:
        assert fragment in build_mixin
