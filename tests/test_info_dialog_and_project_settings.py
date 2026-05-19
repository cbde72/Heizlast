from pathlib import Path


def test_help_menu_contains_info_action_and_dialog():
    root = Path(__file__).resolve().parents[1]
    build_src = (root / "src" / "heizlast" / "ui" / "build_mixin.py").read_text(encoding="utf-8")
    misc_src = (root / "src" / "heizlast" / "ui" / "misc_mixin.py").read_text(encoding="utf-8")
    assert 'm_help = mbar.addMenu("&Hilfe")' in build_src
    assert '"Info…"' in build_src
    assert 'InfoDialog(' in misc_src


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
        'cfg.wall_heat_transfer_coeff_inside_w_m2k = float(self.sp_wall_h_inside.value())',
        'cfg.wall_heat_transfer_coeff_outside_w_m2k = float(self.sp_wall_h_outside.value())',
        'cfg.c_air = float(self.sp_c_air.value())',
        'cfg.u_aussenwand_w_m2k = float(self.sp_u_aw.value())',
        'cfg.u_fenster_w_m2k = float(self.sp_u_window.value())',
        'cfg.u_tuer_w_m2k = float(self.sp_u_door.value())',
        'cfg.u_kellerdecke_w_m2k = float(self.sp_u_kd.value())',
        'cfg.u_eg_geschossdecke_w_m2k = float(self.sp_u_eg.value())',
        'cfg.u_dg_geschossdecke_w_m2k = float(self.sp_u_dg.value())',
        'cfg.u_bodenplatte_w_m2k = float(self.sp_u_bodenplatte.value())',
        'cfg.u_erdberuehrte_wand_w_m2k = float(self.sp_u_erdwand.value())',
        'cfg.u_value_source = self.ed_u_source.text().strip()',
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


def test_project_menu_exposes_direct_parameter_shortcuts_and_export_preflight():
    root = Path(__file__).resolve().parents[1]
    build_src = (root / "src" / "heizlast" / "ui" / "build_mixin.py").read_text(encoding="utf-8")
    settings_src = (root / "src" / "heizlast" / "ui" / "settings_mixin.py").read_text(encoding="utf-8")
    export_src = (root / "src" / "heizlast" / "ui" / "export_mixin.py").read_text(encoding="utf-8")

    for fragment in [
        "self.act_project_settings_norm",
        "self.act_project_settings_u_values",
        "self.act_project_settings_ventilation",
        "self.act_project_settings_ground",
    ]:
        assert fragment in build_src

    for fragment in [
        'self._open_project_settings_dialog("Normprüfung")',
        'self._open_project_settings_dialog("Auto-Decken")',
        'self._open_project_settings_dialog("Lüftung")',
        'self._open_project_settings_dialog("Erdreich")',
    ]:
        assert fragment in settings_src

    assert "def _confirm_export_din_preflight" in export_src
    assert "assess_din_status(" in export_src
    assert "Export trotzdem starten?" in export_src


def test_room_properties_expose_usage_presets_for_norm_room_data():
    root = Path(__file__).resolve().parents[1]
    build_src = (root / "src" / "heizlast" / "ui" / "build_mixin.py").read_text(encoding="utf-8")
    selection_src = (root / "src" / "heizlast" / "ui" / "selection_mixin.py").read_text(encoding="utf-8")

    assert "ROOM_USAGE_DEFAULTS" in build_src
    assert "self.cb_usage_type = QComboBox()" in build_src
    assert 'form.addRow("Nutzung", self.cb_usage_type)' in build_src
    assert "self.cb_usage_type.currentIndexChanged.connect(self._on_room_usage_preset_changed)" in build_src
    assert "def _on_room_usage_preset_changed" in selection_src
    assert "usage_defaults(usage)" in selection_src
    assert "r.usage_type = str(usage).strip() if usage else None" in selection_src


def test_project_dashboard_backup_room_status_and_export_options_are_wired():
    root = Path(__file__).resolve().parents[1]
    build_src = (root / "src" / "heizlast" / "ui" / "build_mixin.py").read_text(encoding="utf-8")
    comfort_src = (root / "src" / "heizlast" / "ui" / "comfort_mixin.py").read_text(encoding="utf-8")
    load_src = (root / "src" / "heizlast" / "ui" / "load_save_mixin.py").read_text(encoding="utf-8")
    selection_src = (root / "src" / "heizlast" / "ui" / "selection_mixin.py").read_text(encoding="utf-8")
    element_src = (root / "src" / "heizlast" / "ui" / "element_edit_mixin.py").read_text(encoding="utf-8")
    export_src = (root / "src" / "heizlast" / "ui" / "export_mixin.py").read_text(encoding="utf-8")
    report_src = (root / "src" / "heizlast" / "infrastructure" / "reporting.py").read_text(encoding="utf-8")

    for fragment in [
        'self.dock_dashboard = QDockWidget("Projekt-Dashboard", self)',
        'self.list_dashboard_workflow = QListWidget()',
        'self.list_dashboard_checks = QListWidget()',
        'self.tbl_room_norm_matrix = QTableWidget(0, 10)',
        'self.list_dashboard_heat_audit = QListWidget()',
        'self.btn_element_assistant = QPushButton("Bauteil-Assistent")',
        'self.act_project_dashboard = self._make_action(',
        'self.act_project_manager = self._make_action(',
        'self.list_dashboard_workflow.itemClicked.connect(self._on_dashboard_workflow_item_clicked)',
        'self.tbl_room_norm_matrix.cellClicked.connect(self._on_room_norm_matrix_cell_clicked)',
        'self.list_dashboard_heat_audit.itemClicked.connect(self._on_heat_audit_item_clicked)',
        'self.btn_element_assistant.clicked.connect(self._on_element_assistant)',
        'self.btn_dashboard_save_version.clicked.connect(self._on_save_version)',
        'def _show_project_dashboard(self):',
    ]:
        assert fragment in build_src

    assert "def _refresh_project_dashboard(self) -> None:" in comfort_src
    assert "assess_din_status(" in comfort_src
    assert "def _refresh_dashboard_workflow" in comfort_src
    assert "def _refresh_room_norm_matrix" in comfort_src
    assert "def _refresh_heatload_audit" in comfort_src
    assert "DG-Dachfläche" in comfort_src
    assert "Mögliche Doppelung" in comfort_src
    assert '"Projektparameter vollständig"' in comfort_src
    assert '"DIN-Report bereit"' in comfort_src
    assert '"thermal_bridge"' in comfort_src
    assert "def _write_project_backup(self, reason: str = \"backup\")" in load_src
    assert "def _on_save_version(self):" in load_src
    assert "def _on_project_manager(self) -> None:" in load_src
    assert '"Versionen", "Version"' in load_src
    assert '"_backups", "Backup"' in load_src
    assert "def _on_element_assistant(self) -> None:" in element_src
    assert '"Innenwand"' in element_src
    assert 'cb_boundary.setCurrentText("Nachbarzone/Interzone")' in element_src
    assert '"source_status": source_status' in element_src
    assert 'form.addRow("Quelle/Status", cb_source)' in element_src
    assert "def _refresh_selected_room_norm_status" in selection_src
    assert 'self.lbl_room_norm_status = QLabel("Raumstatus: —")' in build_src
    assert "def _show_export_options_dialog" in export_src
    assert 'QCheckBox("PDF-Report mit DIN-Prüfstatus")' in export_src
    assert 'self._write_project_backup("before_export")' in export_src
    assert "def _append_proof_overview_section(self) -> None:" in report_src
    assert "Nachweisübersicht für Prüfung und Übergabe" in report_src
    assert "Bauteilquellen und Annahmen" in report_src


def test_new_project_wizard_is_guided_and_versioned():
    root = Path(__file__).resolve().parents[1]
    build_src = (root / "src" / "heizlast" / "ui" / "build_mixin.py").read_text(encoding="utf-8")
    load_src = (root / "src" / "heizlast" / "ui" / "load_save_mixin.py").read_text(encoding="utf-8")
    dialog_src = (root / "src" / "heizlast" / "ui" / "dialogs" / "new_project_dialog.py").read_text(encoding="utf-8")
    init_src = (root / "src" / "heizlast" / "__init__.py").read_text(encoding="utf-8")
    version_src = (root / "src" / "heizlast" / "version.py").read_text(encoding="utf-8")

    assert "slot=self._on_new_project_wizard" in build_src
    assert "def _run_project_setup_wizard" in load_src
    assert 'return ["Normprüfung", "Auto-Decken", "Lüftung", "Erdreich"]' in load_src
    assert "self.chk_guided_setup = QCheckBox" in dialog_src
    assert "self.cb_setup_scope = QComboBox()" in dialog_src
    assert "'guided_setup': self.chk_guided_setup.isChecked()" in dialog_src
    assert '__version__ = "2.9.0"' in init_src
    assert '__internal_version__ = "Heizlast_V37-intern-01"' in init_src
    assert 'APP_INTERNAL_VERSION = "37.1.0"' in version_src
