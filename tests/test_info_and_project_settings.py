from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_MIXIN = ROOT / "src" / "heizlast" / "ui" / "build_mixin.py"
SETTINGS_MIXIN = ROOT / "src" / "heizlast" / "ui" / "settings_mixin.py"
INFO_DIALOG = ROOT / "src" / "heizlast" / "ui" / "dialogs" / "info_dialog.py"
PROJECT_DIALOG = ROOT / "src" / "heizlast" / "ui" / "dialogs" / "project_settings_dialog.py"
INIT_FILE = ROOT / "src" / "heizlast" / "__init__.py"


def test_help_menu_and_info_action_are_present():
    src = BUILD_MIXIN.read_text(encoding="utf-8")
    assert 'm_help = mbar.addMenu("&Hilfe")' in src
    assert 'def _create_help_menu' in src
    assert '"Info…"' in src


def test_info_dialog_mentions_features_and_din_conformity():
    src = INFO_DIALOG.read_text(encoding="utf-8")
    assert 'Interne Versionsnummer' in src
    assert 'Hauptfunktionen' in src
    assert 'DIN EN 12831' in src


def test_internal_version_constant_is_defined():
    src = INIT_FILE.read_text(encoding="utf-8")
    assert '__internal_version__' in src


def test_project_settings_dialog_exposes_all_project_fields_including_t_out_source():
    src = PROJECT_DIALOG.read_text(encoding="utf-8")
    assert 'self.cb_t_out_source = QComboBox()' in src
    assert 'cfg.t_out_source = self.cb_t_out_source.currentText()' in src
    assert 'self.ed_norm_edition = QLineEdit' in src
    assert 'cfg.norm_edition = self.ed_norm_edition.text().strip()' in src
    assert 'self.cb_vent_mode = QComboBox()' in src
    assert 'cfg.ventilation_mode = self.cb_vent_mode.currentText()' in src
    assert 'self.cb_reheat_enabled = QCheckBox("Aufheizzuschlag ansetzen")' in src
    assert 'cfg.reheat_power_w_m2 = float(self.sp_reheat.value())' in src
    assert 'cfg.reheat_duration_h = float(self.sp_reheat_duration.value())' in src
    assert 'cfg.climate_station = self.ed_climate_station.text().strip()' in src
    assert 'cfg.ground.din_ts_f_slab = float(self.sp_ground_din_f_slab.value())' in src
    assert 'cfg.attic.u_gable_w_m2k = float(self.sp_attic_u_gable.value())' in src
    assert 'cfg.ground.psi_perimeter_w_mk = float(self.sp_ground_psi.value())' in src
    assert 'cfg.tb.include_oben = bool(self.cb_tb_o.isChecked())' in src
