from pathlib import Path


def test_help_menu_contains_info_action_and_dialog():
    root = Path(__file__).resolve().parents[1]
    src = (root / "src" / "heizlast" / "ui" / "build_mixin.py").read_text(encoding="utf-8")
    assert 'm_help = mbar.addMenu("&Hilfe")' in src
    assert '"Info…"' in src
    assert 'InfoDialog(self)' in src


def test_info_dialog_mentions_features_and_din_reference():
    root = Path(__file__).resolve().parents[1]
    src = (root / "src" / "heizlast" / "ui" / "dialogs" / "info_dialog.py").read_text(encoding="utf-8")
    assert 'Hauptfunktionen' in src
    assert 'DIN EN 12831' in src
    assert 'Interne Versionsnummer' in src


def test_project_settings_dialog_exposes_all_project_cfg_user_settings():
    root = Path(__file__).resolve().parents[1]
    src = (root / "src" / "heizlast" / "ui" / "dialogs" / "project_settings_dialog.py").read_text(encoding="utf-8")
    assert 'cb_t_out_source' in src
    assert 'cfg.t_out_source = self.cb_t_out_source.currentText()' in src
    for fragment in [
        'cfg.t_out_c = float(self.sp_t_out.value())',
        'cfg.t_keller_c = float(self.sp_t_keller.value())',
        'cfg.t_oben_c = float(self.sp_t_oben.value())',
        'cfg.thickness_mode = self.cb_thickness.currentText()',
        'cfg.area_shrink_factor = float(self.sp_shrink.value())',
        'cfg.floor_area_mode = self.cb_area_mode.currentText()',
        'cfg.wall_thickness_outer_m = float(self.sp_tw_out.value())',
        'cfg.wall_thickness_inner_m = float(self.sp_tw_in.value())',
        'cfg.c_air = float(self.sp_c_air.value())',
        'cfg.u_kellerdecke_w_m2k = float(self.sp_u_kd.value())',
        'cfg.u_eg_geschossdecke_w_m2k = float(self.sp_u_eg.value())',
        'cfg.u_dg_geschossdecke_w_m2k = float(self.sp_u_dg.value())',
        'cfg.tb.mode = self.cb_tb_mode.currentText()',
        'cfg.tb.delta_u_w_m2k = float(self.sp_tb_du.value())',
        'cfg.tb.psi_default_w_mk = float(self.sp_tb_psi.value())',
        'cfg.tb.percent_of_trans = float(self.sp_tb_p.value())',
        'cfg.tb.use_element_meta_psi = bool(self.cb_tb_meta.isChecked())',
        'cfg.tb.include_out = bool(self.cb_tb_out.isChecked())',
        'cfg.tb.include_keller = bool(self.cb_tb_k.isChecked())',
        'cfg.tb.include_oben = bool(self.cb_tb_o.isChecked())',
        'cfg.ground.mode = self.cb_ground_mode.currentText()',
        'cfg.ground.ground_temp_c = float(self.sp_ground_temp.value())',
        'cfg.ground.f_slab = float(self.sp_ground_f_slab.value())',
        'cfg.ground.f_wall = float(self.sp_ground_f_wall.value())',
        'cfg.ground.psi_perimeter_w_mk = float(self.sp_ground_psi.value())',
        'cfg.attic.enabled = bool(self.cb_attic_enabled.isChecked())',
        'cfg.attic.building_width_m = float(self.sp_attic_width.value())',
        'cfg.attic.building_length_m = float(self.sp_attic_length.value())',
        'cfg.attic.knee_wall_height_m = float(self.sp_attic_knee.value())',
        'cfg.attic.roof_pitch_deg = float(self.sp_attic_pitch.value())',
        'cfg.attic.u_roof_w_m2k = float(self.sp_attic_u_roof.value())',
        'cfg.attic.u_gable_w_m2k = float(self.sp_attic_u_gable.value())',
    ]:
        assert fragment in src
