from pathlib import Path


def test_facade_material_quick_select_sources_present():
    build = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    settings = Path("src/heizlast/ui/settings_mixin.py").read_text(encoding="utf-8")

    assert "3D-Material wählen" in build
    assert "cb_facade_material_quick" in build
    assert "_set_facade_material" in settings
    assert "_sync_facade_material_widgets" in settings
