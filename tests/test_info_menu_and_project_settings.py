import pytest

pytest.importorskip("PySide6")

from heizlast import __internal_version__, PROJECT_SCHEMA_VERSION
from heizlast.configs.project_config import ProjectCfg
from heizlast.ui.dialogs.project_settings_dialog import ProjectSettingsDialog
from heizlast.ui.main_window import MainWindow


def test_project_settings_dialog_exposes_all_project_cfg_fields(qapp):
    cfg = ProjectCfg()
    dlg = ProjectSettingsDialog(None, cfg)

    dlg.ed_internal_project_version.setText("INT-2026-03")
    dlg.cb_t_out_source.setCurrentText("din12831")
    dlg.sp_t_out.setValue(-12.5)
    dlg.sp_ground_temp.setValue(9.5)
    dlg.cb_attic_enabled.setChecked(True)

    dlg.apply_to_cfg(cfg)

    assert cfg.internal_project_version == "INT-2026-03"
    assert cfg.t_out_source == "din12831"
    assert cfg.t_out_c == -12.5
    assert cfg.ground.ground_temp_c == 9.5
    assert cfg.attic.enabled is True
    assert cfg.cfg_version == PROJECT_SCHEMA_VERSION


def test_main_window_has_info_action_without_toolbar_changes(qapp):
    win = MainWindow()
    assert hasattr(win, "act_info_dialog")
    assert win.act_info_dialog.text() == "Info…"
    assert win.windowTitle().endswith(__internal_version__)
