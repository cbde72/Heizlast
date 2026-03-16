from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QDialogButtonBox,
    QDoubleSpinBox,
    QComboBox,
    QListWidget,
    QStackedWidget,
    QWidget,
    QCheckBox,
    QLineEdit,
    QLabel,
    QGroupBox,
    QScrollArea,
    QHBoxLayout,
    QFrame,
)
from ... import PROJECT_SCHEMA_VERSION
from ...configs.project_config import ProjectCfg


class _SettingsNavList(QListWidget):
    def tabText(self, index: int) -> str:
        item = self.item(index)
        return item.text() if item is not None else ""

    def setCurrentIndex(self, index: int) -> None:
        self.setCurrentRow(index)

    def currentIndex(self) -> int:
        return self.currentRow()


class ProjectSettingsDialog(QDialog):
    def __init__(self, parent, cfg: ProjectCfg, initial_tab: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Projektparameter – Heizlast")
        self.resize(860, 720)
        self._cfg = cfg
        self._apply_dialog_style()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        self.lb_intro = QLabel(
            "Vollständige Projektparameter für Randbedingungen, Geometrie, Lüftung, "
            "Auto-Decken, Wärmebrücken, Erdreich und DG-/Dachmodell."
        )
        self.lb_intro.setWordWrap(True)
        self.lb_intro.setObjectName("projectSettingsIntro")
        lay.addWidget(self._wrap_intro_card(self.lb_intro))

        nav_host = QWidget()
        nav_layout = QHBoxLayout(nav_host)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(12)

        sidebar = _SettingsNavList()
        sidebar.setObjectName("projectSettingsNav")
        sidebar.setMinimumWidth(210)
        sidebar.setMaximumWidth(260)
        sidebar.setUniformItemSizes(True)
        self.tabs = sidebar
        self.pages = QStackedWidget()

        nav_layout.addWidget(sidebar, 0)
        nav_layout.addWidget(self.pages, 1)
        lay.addWidget(nav_host, 1)

        # --- Tab: Projektinfo ---
        self.ed_internal_project_version = QLineEdit(str(getattr(cfg, "internal_project_version", "V22-intern-01")))
        self.lb_cfg_schema = QLabel(str(PROJECT_SCHEMA_VERSION))
        self.lb_cfg_schema.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lb_info = QLabel(
            "Die interne Projektversionsnummer wird projektbezogen gespeichert. "
            "Die Schema-Version folgt der aktuellen Anwendungsversion."
        )
        self.lb_info.setWordWrap(True)
        f0 = self._make_form([
            ("Interne Projektversionsnummer", self.ed_internal_project_version),
            ("Projekt-Schema-Version", self.lb_cfg_schema),
            ("Hinweis", self.lb_info),
        ])
        self._add_nav_page("Projektinfo", self._build_tab([
            self._group("Projektidentifikation", f0, "Versionierung und Projekt-Metadaten für den aktuellen Stand."),
        ]))

        # --- Tab: Randbedingungen ---
        self.sp_t_out = QDoubleSpinBox(); self.sp_t_out.setRange(-50, 50); self.sp_t_out.setDecimals(1); self.sp_t_out.setValue(cfg.t_out_c)
        self.sp_t_keller = QDoubleSpinBox(); self.sp_t_keller.setRange(-50, 50); self.sp_t_keller.setDecimals(1); self.sp_t_keller.setValue(cfg.t_keller_c)
        self.sp_t_oben = QDoubleSpinBox(); self.sp_t_oben.setRange(-50, 50); self.sp_t_oben.setDecimals(1); self.sp_t_oben.setValue(cfg.t_oben_c)
        self.cb_t_out_source = QComboBox(); self.cb_t_out_source.addItems(["manual", "din12831", "custom"]); self.cb_t_out_source.setCurrentText(getattr(cfg, "t_out_source", "manual"))
        self.lb_t_source_hint = QLabel("manual = feste Eingabe, din12831 = Normquelle, custom = projektspezifischer Wert")
        self.lb_t_source_hint.setWordWrap(True)
        f1a = self._make_form([
            ("Norm-Außentemp. t_out [°C]", self.sp_t_out),
            ("Keller temp. t_keller [°C]", self.sp_t_keller),
            ("Oben temp. t_oben [°C]", self.sp_t_oben),
        ])
        f1b = self._make_form([
            ("Quelle Außentemperatur", self.cb_t_out_source),
            ("Hinweis", self.lb_t_source_hint),
        ])
        self._add_nav_page("Randbedingungen", self._build_tab([
            self._group("Temperaturen", f1a, "Auslegungs- und Randtemperaturen für Außen, Keller und obere Zone."),
            self._group("Norm-/Quellbezug", f1b, "Legt fest, aus welcher Quelle die Außentemperatur stammt."),
        ]))

        # --- Tab: Geometrie ---
        self.cb_thickness = QComboBox(); self.cb_thickness.addItems(["full", "half"]); self.cb_thickness.setCurrentText(cfg.thickness_mode)
        self.sp_shrink = QDoubleSpinBox(); self.sp_shrink.setRange(0.50, 1.00); self.sp_shrink.setDecimals(3); self.sp_shrink.setSingleStep(0.005); self.sp_shrink.setValue(cfg.area_shrink_factor)
        self.cb_area_mode = QComboBox(); self.cb_area_mode.addItems(["inner", "outer"]); self.cb_area_mode.setCurrentText(cfg.floor_area_mode)
        self.sp_tw_out = QDoubleSpinBox(); self.sp_tw_out.setRange(0.01, 2.0); self.sp_tw_out.setDecimals(3); self.sp_tw_out.setValue(cfg.wall_thickness_outer_m)
        self.sp_tw_in = QDoubleSpinBox(); self.sp_tw_in.setRange(0.01, 2.0); self.sp_tw_in.setDecimals(3); self.sp_tw_in.setValue(cfg.wall_thickness_inner_m)
        self.lb_geo_hint = QLabel("full/half steuert die Wanddickenreferenz der Flächen- und Raumgeometrie.")
        self.lb_geo_hint.setWordWrap(True)
        f2a = self._make_form([
            ("Wanddicken-Modus", self.cb_thickness),
            ("Bezugs-/Flächenmodus", self.cb_area_mode),
            ("Flächen-Faktor (shrink)", self.sp_shrink),
        ])
        f2b = self._make_form([
            ("Außenwanddicke [m]", self.sp_tw_out),
            ("Innenwanddicke [m]", self.sp_tw_in),
            ("Hinweis", self.lb_geo_hint),
        ])
        self._add_nav_page("Geometrie", self._build_tab([
            self._group("Flächenmodell", f2a, "Steuert die geometrische Bezugslogik der Flächen- und Volumenableitung."),
            self._group("Wandstärken", f2b, "Material- und Referenzdicken für Innen- und Außenwände."),
        ]))

        # --- Tab: Lüftung ---
        self.sp_c_air = QDoubleSpinBox(); self.sp_c_air.setRange(0.0, 5.0); self.sp_c_air.setDecimals(3); self.sp_c_air.setValue(cfg.c_air)
        self.lb_air_hint = QLabel("c_air ist der globale Luftwärmekoeffizient für die Lüftungsverluste der Räume.")
        self.lb_air_hint.setWordWrap(True)
        f3 = self._make_form([
            ("c_air [Wh/(m³·K)]", self.sp_c_air),
            ("Hinweis", self.lb_air_hint),
        ])
        self._add_nav_page("Lüftung", self._build_tab([
            self._group("Lüftungsmodell", f3, "Globale Einstellungen für die Lüftungsverluste der Räume."),
        ]))

        # --- Tab: Auto-Decken U-Werte ---
        self.sp_u_kd = QDoubleSpinBox(); self.sp_u_kd.setRange(0.0, 5.0); self.sp_u_kd.setDecimals(3); self.sp_u_kd.setValue(cfg.u_kellerdecke_w_m2k)
        self.sp_u_eg = QDoubleSpinBox(); self.sp_u_eg.setRange(0.0, 5.0); self.sp_u_eg.setDecimals(3); self.sp_u_eg.setValue(cfg.u_eg_geschossdecke_w_m2k)
        self.sp_u_dg = QDoubleSpinBox(); self.sp_u_dg.setRange(0.0, 5.0); self.sp_u_dg.setDecimals(3); self.sp_u_dg.setValue(cfg.u_dg_geschossdecke_w_m2k)
        f4 = self._make_form([
            ("U Kellerdecke [W/m²K]", self.sp_u_kd),
            ("U EG-Geschossdecke [W/m²K]", self.sp_u_eg),
            ("U DG-Geschossdecke [W/m²K]", self.sp_u_dg),
        ])
        self._add_nav_page("Auto-Decken", self._build_tab([
            self._group("Automatisch erzeugte Decken", f4, "U-Werte für automatisch abgeleitete Decken- und Geschossflächen."),
        ]))

        # --- Tab: Wärmebrücken ---
        self.cb_tb_mode = QComboBox(); self.cb_tb_mode.addItems(["none", "delta_u", "psi", "percent"]); self.cb_tb_mode.setCurrentText(cfg.tb.mode)
        self.sp_tb_du = QDoubleSpinBox(); self.sp_tb_du.setRange(0.0, 1.0); self.sp_tb_du.setDecimals(3); self.sp_tb_du.setValue(cfg.tb.delta_u_w_m2k)
        self.sp_tb_psi = QDoubleSpinBox(); self.sp_tb_psi.setRange(0.0, 5.0); self.sp_tb_psi.setDecimals(3); self.sp_tb_psi.setValue(cfg.tb.psi_default_w_mk)
        self.sp_tb_p = QDoubleSpinBox(); self.sp_tb_p.setRange(0.0, 2.0); self.sp_tb_p.setDecimals(3); self.sp_tb_p.setValue(cfg.tb.percent_of_trans)
        self.cb_tb_meta = QCheckBox("ψ aus Element-meta nutzen (psi_w_mk / psi_L_m)"); self.cb_tb_meta.setChecked(bool(cfg.tb.use_element_meta_psi))
        self.cb_tb_out = QCheckBox("WB für Außen"); self.cb_tb_out.setChecked(bool(cfg.tb.include_out))
        self.cb_tb_k = QCheckBox("WB für Keller"); self.cb_tb_k.setChecked(bool(cfg.tb.include_keller))
        self.cb_tb_o = QCheckBox("WB für Oben"); self.cb_tb_o.setChecked(bool(cfg.tb.include_oben))
        f5a = self._make_form([
            ("Modus", self.cb_tb_mode),
            ("ΔU [W/m²K] (delta_u)", self.sp_tb_du),
            ("ψ default [W/mK] (psi)", self.sp_tb_psi),
            ("p (percent)", self.sp_tb_p),
        ])
        f5b = self._make_form([
            ("Element-Metadaten", self.cb_tb_meta),
            ("Außen", self.cb_tb_out),
            ("Keller", self.cb_tb_k),
            ("Oben", self.cb_tb_o),
        ])
        self._add_nav_page("Wärmebrücken", self._build_tab([
            self._group("Ansatz", f5a, "Wahl des Wärmebrückenmodells und der zugehörigen Kennwerte."),
            self._group("Geltungsbereich", f5b, "Legt fest, auf welche Hüllflächen der Wärmebrückenansatz angewendet wird."),
        ]))

        # --- Tab: Erdreich ---
        self.cb_ground_mode = QComboBox(); self.cb_ground_mode.addItems(["none", "simplified", "perimeter"]); self.cb_ground_mode.setCurrentText(getattr(cfg.ground, "mode", "simplified"))
        self.sp_ground_temp = QDoubleSpinBox(); self.sp_ground_temp.setRange(-20.0, 30.0); self.sp_ground_temp.setDecimals(2); self.sp_ground_temp.setValue(float(getattr(cfg.ground, "ground_temp_c", 10.0)))
        self.sp_ground_f_slab = QDoubleSpinBox(); self.sp_ground_f_slab.setRange(0.0, 1.0); self.sp_ground_f_slab.setDecimals(3); self.sp_ground_f_slab.setSingleStep(0.05); self.sp_ground_f_slab.setValue(float(getattr(cfg.ground, "f_slab", 0.40)))
        self.sp_ground_f_wall = QDoubleSpinBox(); self.sp_ground_f_wall.setRange(0.0, 1.0); self.sp_ground_f_wall.setDecimals(3); self.sp_ground_f_wall.setSingleStep(0.05); self.sp_ground_f_wall.setValue(float(getattr(cfg.ground, "f_wall", 0.60)))
        self.sp_ground_psi = QDoubleSpinBox(); self.sp_ground_psi.setRange(0.0, 5.0); self.sp_ground_psi.setDecimals(3); self.sp_ground_psi.setSingleStep(0.01); self.sp_ground_psi.setValue(float(getattr(cfg.ground, "psi_perimeter_w_mk", 0.0)))
        f6a = self._make_form([
            ("Modell", self.cb_ground_mode),
            ("Feste Erdtemperatur [°C]", self.sp_ground_temp),
        ])
        f6b = self._make_form([
            ("f_ground Bodenplatte", self.sp_ground_f_slab),
            ("f_ground Kellerwand", self.sp_ground_f_wall),
            ("ψ Perimeter [W/mK]", self.sp_ground_psi),
        ])
        self._add_nav_page("Erdreich", self._build_tab([
            self._group("Grundmodell", f6a, "Allgemeine Erdreichrandbedingungen für Bodenplatte und erdberührte Bauteile."),
            self._group("Zusatzparameter", f6b, "Vereinfachte bzw. perimeterbasierte Korrekturparameter."),
        ]))

        # --- Tab: DG Dach / Giebel ---
        self.cb_attic_enabled = QCheckBox("DG-Dachprofil aktivieren")
        self.cb_attic_enabled.setChecked(bool(getattr(cfg.attic, "enabled", False)))
        self.sp_attic_width = QDoubleSpinBox(); self.sp_attic_width.setRange(0.5, 200.0); self.sp_attic_width.setDecimals(2); self.sp_attic_width.setValue(float(getattr(cfg.attic, "building_width_m", 8.0)))
        self.sp_attic_length = QDoubleSpinBox(); self.sp_attic_length.setRange(0.5, 200.0); self.sp_attic_length.setDecimals(2); self.sp_attic_length.setValue(float(getattr(cfg.attic, "building_length_m", 10.0)))
        self.sp_attic_knee = QDoubleSpinBox(); self.sp_attic_knee.setRange(0.0, 10.0); self.sp_attic_knee.setDecimals(2); self.sp_attic_knee.setValue(float(getattr(cfg.attic, "knee_wall_height_m", 1.0)))
        self.cb_attic_roof_type = QComboBox(); self.cb_attic_roof_type.addItems(["Satteldach", "Pultdach", "Walmdach", "Flachdach"])
        _roof_type_raw = str(getattr(cfg.attic, "roof_type", "satteldach") or "satteldach").strip().lower()
        _roof_type_map = {"satteldach": "Satteldach", "pultdach": "Pultdach", "walmdach": "Walmdach", "flachdach": "Flachdach"}
        self.cb_attic_roof_type.setCurrentText(_roof_type_map.get(_roof_type_raw, "Satteldach"))
        self.cb_attic_ridge_orientation = QComboBox(); self.cb_attic_ridge_orientation.addItems(["längs", "quer"]); self.cb_attic_ridge_orientation.setCurrentText("quer" if str(getattr(cfg.attic, "ridge_orientation", "length") or "length").strip().lower() == "width" else "längs")
        self.sp_attic_overhang = QDoubleSpinBox(); self.sp_attic_overhang.setRange(0.0, 3.0); self.sp_attic_overhang.setDecimals(2); self.sp_attic_overhang.setSingleStep(0.05); self.sp_attic_overhang.setValue(float(getattr(cfg.attic, "roof_overhang_m", 0.30)))
        self.sp_attic_ridge_offset = QDoubleSpinBox(); self.sp_attic_ridge_offset.setRange(-0.80, 0.80); self.sp_attic_ridge_offset.setDecimals(2); self.sp_attic_ridge_offset.setSingleStep(0.05); self.sp_attic_ridge_offset.setValue(float(getattr(cfg.attic, "ridge_offset_ratio", 0.0)))
        self.cb_attic_pult_side = QComboBox(); self.cb_attic_pult_side.addItems(["links ansteigend", "rechts ansteigend"]); self.cb_attic_pult_side.setCurrentText("links ansteigend" if str(getattr(cfg.attic, "pult_rise_side", "right") or "right").strip().lower() == "left" else "rechts ansteigend")
        self.sp_attic_pitch = QDoubleSpinBox(); self.sp_attic_pitch.setRange(0.0, 85.0); self.sp_attic_pitch.setDecimals(1); self.sp_attic_pitch.setValue(float(getattr(cfg.attic, "roof_pitch_deg", 35.0)))
        self.cb_attic_facade_material = QComboBox(); self.cb_attic_facade_material.addItems(["Klinker", "Putz", "Holz", "Beton"])
        self.cb_attic_roof_material = QComboBox(); self.cb_attic_roof_material.addItems(["Ziegel"])
        _facade_raw = str(getattr(cfg.attic, "facade_material", "klinker") or "klinker").strip().lower()
        _facade_map = {"klinker": "Klinker", "putz": "Putz", "holz": "Holz", "beton": "Beton"}
        self.cb_attic_facade_material.setCurrentText(_facade_map.get(_facade_raw, "Klinker"))
        _roof_material_raw = str(getattr(cfg.attic, "roof_material", "ziegel") or "ziegel").strip().lower()
        _roof_material_map = {"ziegel": "Ziegel"}
        self.cb_attic_roof_material.setCurrentText(_roof_material_map.get(_roof_material_raw, "Ziegel"))
        self.sp_attic_u_roof = QDoubleSpinBox(); self.sp_attic_u_roof.setRange(0.0, 5.0); self.sp_attic_u_roof.setDecimals(3); self.sp_attic_u_roof.setValue(float(getattr(cfg.attic, "u_roof_w_m2k", 0.30)))
        self.sp_attic_u_gable = QDoubleSpinBox(); self.sp_attic_u_gable.setRange(0.0, 5.0); self.sp_attic_u_gable.setDecimals(3); self.sp_attic_u_gable.setValue(float(getattr(cfg.attic, "u_gable_w_m2k", 0.45)))
        self.lb_attic_hint = QLabel(
            "Firstrichtung, Überstand, Firstversatz und Pult-Anstiegsrichtung wirken auf Auto-DG, Vorschau und 3D-Ansicht."
        )
        self.lb_attic_hint.setWordWrap(True)
        self.gb_attic_activation = self._group("Aktivierung", self._make_form([(None, self.cb_attic_enabled)]), "Schaltet die Ableitung für DG-/Dachflächen ein oder aus.")
        self.gb_attic_geometry = self._group("Gebäude- und Dachgeometrie", self._make_form([
            ("Gebäudebreite / Giebelbreite [m]", self.sp_attic_width),
            ("Gebäudelänge in Firstrichtung [m]", self.sp_attic_length),
            ("Kniestockhöhe [m]", self.sp_attic_knee),
            ("Dachform", self.cb_attic_roof_type),
            ("Firstrichtung", self.cb_attic_ridge_orientation),
            ("Dachüberstand [m]", self.sp_attic_overhang),
            ("Asymmetrie / Firstversatz [-1..1]", self.sp_attic_ridge_offset),
            ("Pultdach Neigungsrichtung", self.cb_attic_pult_side),
            ("Dachneigung [°]", self.sp_attic_pitch),
        ]), "Geometrische Parameter für Vorschau, 3D-Modell und Auto-DG-Ableitung.")
        self.gb_attic_materials = self._group("Darstellung und Materialien", self._make_form([
            ("3D-Fassadenmaterial", self.cb_attic_facade_material),
            ("Dachmaterial", self.cb_attic_roof_material),
            ("Hinweis", self.lb_attic_hint),
        ]), "Visuelle Materialwahl für Fassade und Dach in der 3D-Ansicht.")
        self.gb_attic_u = self._group("Thermische Kennwerte", self._make_form([
            ("U Dach [W/m²K]", self.sp_attic_u_roof),
            ("U Giebelwand [W/m²K]", self.sp_attic_u_gable),
        ]), "Wärmeschutzwerte für Dach- und Giebelansätze.")
        self._add_nav_page("DG Dach", self._build_tab([
            self.gb_attic_activation,
            self.gb_attic_geometry,
            self.gb_attic_materials,
            self.gb_attic_u,
        ]))

        self._tab_index_map = {
            "Projektinfo": 0,
            "Randbedingungen": 1,
            "Geometrie": 2,
            "Lüftung": 3,
            "Auto-Decken": 4,
            "Wärmebrücken": 5,
            "Erdreich": 6,
            "DG Dach": 7,
        }
        if initial_tab:
            idx = self._tab_index_map.get(str(initial_tab), None)
            if idx is not None:
                self.tabs.setCurrentRow(idx)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        self.tabs.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.cb_tb_mode.currentTextChanged.connect(self._sync_tb_mode)
        self.cb_ground_mode.currentTextChanged.connect(self._sync_ground_mode)
        self.cb_attic_enabled.toggled.connect(self._sync_attic_enabled)
        self.cb_attic_roof_type.currentTextChanged.connect(self._sync_attic_roof_type)

        if self.tabs.count():
            self.tabs.setCurrentRow(self.tabs.currentRow() if self.tabs.currentRow() >= 0 else 0)
        self._sync_tb_mode(self.cb_tb_mode.currentText())
        self._sync_ground_mode(self.cb_ground_mode.currentText())
        self._sync_attic_enabled(bool(self.cb_attic_enabled.isChecked()))
        self._sync_attic_roof_type(self.cb_attic_roof_type.currentText())

    def _apply_dialog_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background: #f5f7fb; }
            QLabel#projectSettingsIntro {
                color: #233244;
                font-size: 13px;
            }
            QFrame#introCard {
                background: white;
                border: 1px solid #d7dfeb;
                border-radius: 10px;
            }
            QListWidget#projectSettingsNav {
                background: #eef3fa;
                border: 1px solid #d7dfeb;
                border-radius: 12px;
                outline: none;
                padding: 8px;
            }
            QListWidget#projectSettingsNav::item {
                background: transparent;
                color: #28405b;
                border: 1px solid transparent;
                border-radius: 9px;
                padding: 10px 12px;
                margin: 2px 0;
            }
            QListWidget#projectSettingsNav::item:selected {
                background: white;
                color: #17324d;
                border: 1px solid #d7dfeb;
                font-weight: 600;
            }
            QListWidget#projectSettingsNav::item:hover {
                background: #f8fbff;
            }
            QStackedWidget {
                background: white;
                border: 1px solid #d7dfeb;
                border-radius: 12px;
            }
            QGroupBox {
                background: white;
                border: 1px solid #d7dfeb;
                border-radius: 10px;
                margin-top: 14px;
                font-weight: 600;
                color: #1f2d3d;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLineEdit, QDoubleSpinBox, QComboBox {
                min-height: 30px;
                border: 1px solid #c8d3e1;
                border-radius: 7px;
                padding: 2px 8px;
                background: #fcfdff;
            }
            QScrollArea { border: none; background: transparent; }
            """
        )

    def _wrap_intro_card(self, label: QLabel) -> QWidget:
        frame = QFrame()
        frame.setObjectName("introCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(label)
        return frame

    def _make_form(self, rows: list[tuple[str | None, QWidget]]) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setContentsMargins(6, 6, 6, 6)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        for label, field in rows:
            if label is None:
                form.addRow(field)
            else:
                form.addRow(label, field)
        return widget

    def _group(self, title: str, body: QWidget, description: str | None = None) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)
        if description:
            lb = QLabel(description)
            lb.setWordWrap(True)
            lb.setStyleSheet("color: #5a6b7f; font-weight: 400;")
            layout.addWidget(lb)
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("color: #e3e9f2;")
            layout.addWidget(line)
        layout.addWidget(body)
        return box


    def _add_nav_page(self, title: str, page: QWidget) -> None:
        self.pages.addWidget(page)
        self.tabs.addItem(title)

    def _build_tab(self, groups: list[QWidget]) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        for group in groups:
            layout.addWidget(group)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer = QWidget()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.addWidget(scroll)
        return outer

    def _set_widgets_enabled(self, widgets, enabled: bool) -> None:
        for widget in widgets:
            try:
                widget.setEnabled(bool(enabled))
            except Exception:
                pass

    def _sync_tb_mode(self, mode: str) -> None:
        mode = str(mode or "none").strip().lower()
        self.sp_tb_du.setEnabled(mode == "delta_u")
        self.sp_tb_psi.setEnabled(mode == "psi")
        self.sp_tb_p.setEnabled(mode == "percent")
        self.cb_tb_meta.setEnabled(mode == "psi")
        enabled = mode != "none"
        self.cb_tb_out.setEnabled(enabled)
        self.cb_tb_k.setEnabled(enabled)
        self.cb_tb_o.setEnabled(enabled)

    def _sync_ground_mode(self, mode: str) -> None:
        mode = str(mode or "simplified").strip().lower()
        self.sp_ground_temp.setEnabled(mode != "none")
        simplified_or_perimeter = mode in {"simplified", "perimeter"}
        self.sp_ground_f_slab.setEnabled(simplified_or_perimeter)
        self.sp_ground_f_wall.setEnabled(simplified_or_perimeter)
        self.sp_ground_psi.setEnabled(mode == "perimeter")

    def _sync_attic_enabled(self, enabled: bool) -> None:
        self.gb_attic_geometry.setEnabled(bool(enabled))
        self.gb_attic_materials.setEnabled(bool(enabled))
        self.gb_attic_u.setEnabled(bool(enabled))
        self._set_widgets_enabled([
            self.sp_attic_width,
            self.sp_attic_length,
            self.sp_attic_knee,
            self.cb_attic_roof_type,
            self.cb_attic_ridge_orientation,
            self.sp_attic_overhang,
            self.sp_attic_ridge_offset,
            self.cb_attic_pult_side,
            self.sp_attic_pitch,
            self.cb_attic_facade_material,
            self.cb_attic_roof_material,
            self.sp_attic_u_roof,
            self.sp_attic_u_gable,
        ], bool(enabled))
        self._sync_attic_roof_type(self.cb_attic_roof_type.currentText())

    def _sync_attic_roof_type(self, roof_type_label: str) -> None:
        enabled = bool(self.cb_attic_enabled.isChecked())
        roof_type = str(roof_type_label or "Satteldach").strip()
        is_saddle = roof_type == "Satteldach"
        is_pult = roof_type == "Pultdach"
        is_flat = roof_type == "Flachdach"
        self.cb_attic_ridge_orientation.setEnabled(enabled and roof_type != "Flachdach")
        self.sp_attic_ridge_offset.setEnabled(enabled and is_saddle)
        self.cb_attic_pult_side.setEnabled(enabled and is_pult)
        self.sp_attic_pitch.setEnabled(enabled and not is_flat)

    def apply_to_cfg(self, cfg: ProjectCfg) -> None:
        cfg.cfg_version = PROJECT_SCHEMA_VERSION
        cfg.internal_project_version = self.ed_internal_project_version.text().strip() or "V22-intern-01"

        cfg.t_out_c = float(self.sp_t_out.value())
        cfg.t_keller_c = float(self.sp_t_keller.value())
        cfg.t_oben_c = float(self.sp_t_oben.value())
        cfg.t_out_source = self.cb_t_out_source.currentText()

        cfg.thickness_mode = self.cb_thickness.currentText()
        cfg.area_shrink_factor = float(self.sp_shrink.value())
        cfg.floor_area_mode = self.cb_area_mode.currentText()

        cfg.wall_thickness_outer_m = float(self.sp_tw_out.value())
        cfg.wall_thickness_inner_m = float(self.sp_tw_in.value())

        cfg.c_air = float(self.sp_c_air.value())

        cfg.u_kellerdecke_w_m2k = float(self.sp_u_kd.value())
        cfg.u_eg_geschossdecke_w_m2k = float(self.sp_u_eg.value())
        cfg.u_dg_geschossdecke_w_m2k = float(self.sp_u_dg.value())

        cfg.tb.mode = self.cb_tb_mode.currentText()
        cfg.tb.delta_u_w_m2k = float(self.sp_tb_du.value())
        cfg.tb.psi_default_w_mk = float(self.sp_tb_psi.value())
        cfg.tb.percent_of_trans = float(self.sp_tb_p.value())
        cfg.tb.use_element_meta_psi = bool(self.cb_tb_meta.isChecked())
        cfg.tb.include_out = bool(self.cb_tb_out.isChecked())
        cfg.tb.include_keller = bool(self.cb_tb_k.isChecked())
        cfg.tb.include_oben = bool(self.cb_tb_o.isChecked())

        cfg.ground.mode = self.cb_ground_mode.currentText()
        cfg.ground.ground_temp_c = float(self.sp_ground_temp.value())
        cfg.ground.f_slab = float(self.sp_ground_f_slab.value())
        cfg.ground.f_wall = float(self.sp_ground_f_wall.value())
        cfg.ground.psi_perimeter_w_mk = float(self.sp_ground_psi.value())

        cfg.attic.enabled = bool(self.cb_attic_enabled.isChecked())
        cfg.attic.building_width_m = float(self.sp_attic_width.value())
        cfg.attic.building_length_m = float(self.sp_attic_length.value())
        cfg.attic.knee_wall_height_m = float(self.sp_attic_knee.value())
        _roof_rev = {"Satteldach": "satteldach", "Pultdach": "pultdach", "Walmdach": "walmdach", "Flachdach": "flachdach"}
        cfg.attic.roof_type = _roof_rev.get(self.cb_attic_roof_type.currentText(), "satteldach")
        cfg.attic.ridge_orientation = "width" if self.cb_attic_ridge_orientation.currentText() == "quer" else "length"
        cfg.attic.roof_overhang_m = float(self.sp_attic_overhang.value())
        cfg.attic.ridge_offset_ratio = float(self.sp_attic_ridge_offset.value())
        cfg.attic.pult_rise_side = "left" if self.cb_attic_pult_side.currentText() == "links ansteigend" else "right"
        cfg.attic.roof_pitch_deg = float(self.sp_attic_pitch.value())
        _facade_rev = {"Klinker": "klinker", "Putz": "putz", "Holz": "holz", "Beton": "beton"}
        cfg.attic.facade_material = _facade_rev.get(self.cb_attic_facade_material.currentText(), "klinker")
        _roof_material_rev = {"Ziegel": "ziegel"}
        cfg.attic.roof_material = _roof_material_rev.get(self.cb_attic_roof_material.currentText(), "ziegel")
        cfg.attic.u_roof_w_m2k = float(self.sp_attic_u_roof.value())
        cfg.attic.u_gable_w_m2k = float(self.sp_attic_u_gable.value())
