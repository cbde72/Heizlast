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
