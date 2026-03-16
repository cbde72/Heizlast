from pathlib import Path


def test_roof_profile_quick_select_sources_present():
    build = Path("src/heizlast/ui/build_mixin.py").read_text(encoding="utf-8")
    settings = Path("src/heizlast/ui/settings_mixin.py").read_text(encoding="utf-8")

    assert "Dachprofil wählen" in build
    assert "cb_roof_profile_quick" in build
    assert "_set_attic_roof_type" in settings
    assert "_sync_roof_profile_widgets" in settings
