from pathlib import Path


def test_roof_material_quick_select_sources_present():
    build = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    settings = Path("src/heizlast/ui/settings_mixin.py").read_text(encoding="utf-8")
    dialog = Path("src/heizlast/ui/dialogs/project_settings_dialog.py").read_text(encoding="utf-8")
    assert "Dachmaterial wählen" in build
    assert "cb_roof_material_quick" in build
    assert "_set_roof_material" in settings
    assert "_sync_roof_material_widgets" in settings
    assert "Dachmaterial" in dialog
