import pytest

pytest.importorskip("PySide6")

from heizlast import PROJECT_SCHEMA_VERSION
from heizlast.configs.project_config import ProjectCfg
from heizlast.ui.dialogs.project_settings_dialog import ProjectSettingsDialog


def test_project_settings_dialog_has_all_tabs_and_sets_schema(qapp):
    cfg = ProjectCfg()
    dlg = ProjectSettingsDialog(None, cfg)
    labels = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
    assert labels == [
        "Projektinfo",
        "Randbedingungen",
        "Geometrie",
        "Lüftung",
        "Auto-Decken",
        "Wärmebrücken",
        "Erdreich",
        "DG Dach",
        "Normprüfung",
    ]
    dlg.apply_to_cfg(cfg)
    assert cfg.cfg_version == PROJECT_SCHEMA_VERSION


def test_project_settings_dynamic_enabling_for_roof_and_modes(qapp):
    cfg = ProjectCfg()
    dlg = ProjectSettingsDialog(None, cfg)

    dlg.cb_tb_mode.setCurrentText("none")
    assert not dlg.sp_tb_du.isEnabled()
    dlg.cb_tb_mode.setCurrentText("delta_u")
    assert dlg.sp_tb_du.isEnabled()
    assert not dlg.sp_tb_psi.isEnabled()

    dlg.cb_ground_mode.setCurrentText("perimeter")
    assert dlg.sp_ground_psi.isEnabled()
    dlg.cb_ground_mode.setCurrentText("none")
    assert not dlg.sp_ground_temp.isEnabled()

    dlg.cb_attic_enabled.setChecked(True)
    dlg.cb_attic_roof_type.setCurrentText("Satteldach")
    assert dlg.sp_attic_ridge_offset.isEnabled()
    assert not dlg.cb_attic_pult_side.isEnabled()

    dlg.cb_attic_roof_type.setCurrentText("Pultdach")
    assert dlg.cb_attic_pult_side.isEnabled()
    assert not dlg.sp_attic_ridge_offset.isEnabled()

    dlg.cb_attic_roof_type.setCurrentText("Flachdach")
    assert not dlg.sp_attic_pitch.isEnabled()


def test_project_settings_norm_guidance_and_quick_profiles(qapp):
    cfg = ProjectCfg()
    dlg = ProjectSettingsDialog(None, cfg)

    assert hasattr(dlg, "lst_norm_check")
    assert dlg.lst_norm_check.count() >= 7
    assert "fehlende Nachweise" in dlg.lbl_norm_check_summary.text()

    dlg.cb_norm_profile.setCurrentText("Neubau")
    dlg._apply_norm_profile()

    assert dlg.sp_u_aw.value() == pytest.approx(0.240)
    assert dlg.sp_u_window.value() == pytest.approx(0.950)
    assert dlg.sp_u_bodenplatte.value() == pytest.approx(0.300)
    assert dlg.sp_attic_u_roof.value() == pytest.approx(0.180)
    assert "Schnellprofil Neubau" in dlg.ed_u_source.text()

    rows = [dlg.lst_norm_check.item(i).text() for i in range(dlg.lst_norm_check.count())]
    assert any("U-Werte Außenwand/Fenster/Tür/Decken/Boden" in row and "[OK]" in row for row in rows)
