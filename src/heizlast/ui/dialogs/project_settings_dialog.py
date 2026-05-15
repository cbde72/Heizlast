from __future__ import annotations
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush
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
    QPushButton,
    QMessageBox,
    QSpinBox,
)
from ... import PROJECT_SCHEMA_VERSION
from ...configs.project_config import ProjectCfg, DormerCfgDTO, RoofLineCfgDTO


class _SettingsNavList(QListWidget):
    def tabText(self, index: int) -> str:
        item = self.item(index)
        return item.text() if item is not None else ""

    def setCurrentIndex(self, index: int) -> None:
        self.setCurrentRow(index)

    def currentIndex(self) -> int:
        return self.currentRow()


class RoofLineEditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("roofLineEditorWidget")
        self.setMinimumHeight(280)
        self._lines: list[RoofLineCfgDTO] = []
        self._current_kind: str = "first"
        self._draft_start: tuple[float, float] | None = None
        self._selected_index: int = -1
        self.on_lines_changed = None

    def set_current_kind(self, kind: str) -> None:
        self._current_kind = str(kind or "first").strip().lower()
        self.update()

    def set_lines(self, lines: list[RoofLineCfgDTO]) -> None:
        self._lines = [RoofLineCfgDTO(**{k: getattr(line, k) for k in RoofLineCfgDTO.__dataclass_fields__.keys()}) for line in list(lines or [])]
        if self._selected_index >= len(self._lines):
            self._selected_index = len(self._lines) - 1
        self.update()

    def current_lines(self) -> list[RoofLineCfgDTO]:
        return [RoofLineCfgDTO(**{k: getattr(line, k) for k in RoofLineCfgDTO.__dataclass_fields__.keys()}) for line in self._lines]

    def selected_index(self) -> int:
        return self._selected_index

    def delete_selected_line(self) -> None:
        if 0 <= self._selected_index < len(self._lines):
            del self._lines[self._selected_index]
            if self._selected_index >= len(self._lines):
                self._selected_index = len(self._lines) - 1
            self._emit_lines_changed()
            self.update()

    def clear_all(self) -> None:
        self._lines = []
        self._selected_index = -1
        self._draft_start = None
        self._emit_lines_changed()
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        ratio = self._event_to_ratio(event.position().x(), event.position().y())
        hit = self._hit_test_line(*ratio)
        if hit >= 0 and self._draft_start is None:
            self._selected_index = hit
            self.update()
            self._emit_lines_changed()
            return
        if self._draft_start is None:
            self._draft_start = ratio
            self._selected_index = -1
        else:
            x1, y1 = self._draft_start
            x2, y2 = ratio
            if abs(x2 - x1) > 1e-4 or abs(y2 - y1) > 1e-4:
                self._lines.append(RoofLineCfgDTO(kind=self._current_kind, x1_ratio=x1, y1_ratio=y1, x2_ratio=x2, y2_ratio=y2))
                self._selected_index = len(self._lines) - 1
                self._emit_lines_changed()
            self._draft_start = None
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        outer = self.rect().adjusted(10, 10, -10, -10)
        p.fillRect(self.rect(), QColor("#fafbfc"))
        p.setPen(QPen(QColor("#d9e0e6"), 1))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawRoundedRect(outer, 8, 8)
        roof = QRectF(outer.left() + 26, outer.top() + 24, max(40.0, outer.width() - 52), max(40.0, outer.height() - 48))
        p.setPen(QPen(QColor("#202a34"), 2))
        p.setBrush(QBrush(QColor("#f6f8fa")))
        p.drawRect(roof)
        p.setPen(QPen(QColor("#d0d7de"), 1, Qt.DashLine))
        for i in range(1, 4):
            x = roof.left() + i * roof.width() / 4.0
            y = roof.top() + i * roof.height() / 4.0
            p.drawLine(QPointF(x, roof.top()), QPointF(x, roof.bottom()))
            p.drawLine(QPointF(roof.left(), y), QPointF(roof.right(), y))
        p.setPen(QPen(QColor("#57606a"), 1))
        p.drawText(roof.adjusted(8, 6, -8, -6), Qt.AlignTop | Qt.AlignLeft, "Draufsicht – 1. Klick Start, 2. Klick Ende")
        p.drawText(roof.adjusted(8, 6, -8, -6), Qt.AlignTop | Qt.AlignRight, "Typ: " + self._kind_label(self._current_kind))
        for idx, line in enumerate(self._lines):
            color = self._line_color(getattr(line, 'kind', 'first'))
            width = 4 if idx == self._selected_index else 3
            p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(self._ratio_to_point(roof, line.x1_ratio, line.y1_ratio), self._ratio_to_point(roof, line.x2_ratio, line.y2_ratio))
        if self._draft_start is not None:
            pt = self._ratio_to_point(roof, *self._draft_start)
            p.setPen(QPen(QColor("#1f6feb"), 2, Qt.DashLine))
            p.setBrush(QBrush(QColor("#1f6feb")))
            p.drawEllipse(pt, 4, 4)

    def _ratio_to_point(self, roof: QRectF, x_ratio: float, y_ratio: float) -> QPointF:
        xr = min(1.0, max(0.0, float(x_ratio)))
        yr = min(1.0, max(0.0, float(y_ratio)))
        return QPointF(roof.left() + xr * roof.width(), roof.top() + yr * roof.height())

    def _event_to_ratio(self, x_px: float, y_px: float) -> tuple[float, float]:
        outer = self.rect().adjusted(10, 10, -10, -10)
        roof = QRectF(outer.left() + 26, outer.top() + 24, max(40.0, outer.width() - 52), max(40.0, outer.height() - 48))
        xr = 0.0 if roof.width() <= 0 else (float(x_px) - roof.left()) / roof.width()
        yr = 0.0 if roof.height() <= 0 else (float(y_px) - roof.top()) / roof.height()
        return (min(1.0, max(0.0, xr)), min(1.0, max(0.0, yr)))

    def _hit_test_line(self, x_ratio: float, y_ratio: float) -> int:
        best_idx = -1
        best_dist = 0.04
        for idx, line in enumerate(self._lines):
            dist = self._point_line_distance(x_ratio, y_ratio, line.x1_ratio, line.y1_ratio, line.x2_ratio, line.y2_ratio)
            if dist <= best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx

    def _point_line_distance(self, px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        vx = x2 - x1
        vy = y2 - y1
        wx = px - x1
        wy = py - y1
        vv = vx * vx + vy * vy
        if vv <= 1e-12:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0.0, min(1.0, (wx * vx + wy * vy) / vv))
        qx = x1 + t * vx
        qy = y1 + t * vy
        return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5

    def _kind_label(self, kind: str) -> str:
        return {"first": "First", "grat": "Grat", "kehle": "Kehle"}.get(str(kind or "").lower(), str(kind))

    def _line_color(self, kind: str) -> QColor:
        mapping = {"first": QColor("#1f6feb"), "grat": QColor("#d1242f"), "kehle": QColor("#8250df")}
        return mapping.get(str(kind or "").lower(), QColor("#57606a"))

    def _emit_lines_changed(self) -> None:
        if callable(self.on_lines_changed):
            self.on_lines_changed()


class DormerEditDialog(QDialog):
    def __init__(self, parent, dormer: DormerCfgDTO | None = None, *, active_sides: tuple[str, ...] = ("left", "right")):
        super().__init__(parent)
        self.setWindowTitle("Gaube bearbeiten" if dormer else "Gaube hinzufügen")
        self.resize(520, 420)
        self._dormer = dormer or DormerCfgDTO()

        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setContentsMargins(8, 8, 8, 8)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)

        self.ed_id = QLineEdit(str(getattr(self._dormer, "id", "dormer_1") or "dormer_1"))
        self.cb_type = QComboBox(); self.cb_type.addItems(["Schleppgaube", "Satteldachgaube", "Flachdachgaube"])
        self.cb_type.setCurrentText({"schleppgaube": "Schleppgaube", "satteldachgaube": "Satteldachgaube", "flachdachgaube": "Flachdachgaube"}.get(str(getattr(self._dormer, "dormer_type", "schleppgaube") or "schleppgaube").strip().lower(), "Schleppgaube"))
        self.cb_side = QComboBox(); self.set_active_sides(active_sides, selected=str(getattr(self._dormer, "roof_side", "right") or "right"))

        self.sp_center = QDoubleSpinBox(); self.sp_center.setRange(0.0, 999.0); self.sp_center.setDecimals(2); self.sp_center.setValue(float(getattr(self._dormer, "center_along_m", 0.0)))
        self.sp_width = QDoubleSpinBox(); self.sp_width.setRange(0.3, 20.0); self.sp_width.setDecimals(2); self.sp_width.setValue(float(getattr(self._dormer, "width_m", 1.80)))
        self.sp_depth = QDoubleSpinBox(); self.sp_depth.setRange(0.2, 20.0); self.sp_depth.setDecimals(2); self.sp_depth.setValue(float(getattr(self._dormer, "depth_m", 1.40)))
        self.sp_front_height = QDoubleSpinBox(); self.sp_front_height.setRange(0.2, 10.0); self.sp_front_height.setDecimals(2); self.sp_front_height.setValue(float(getattr(self._dormer, "front_height_m", 1.20)))
        self.sp_window_count = QSpinBox(); self.sp_window_count.setRange(0, 8); self.sp_window_count.setValue(int(getattr(self._dormer, "window_count", 1) or 0))
        self.sp_window_width = QDoubleSpinBox(); self.sp_window_width.setRange(0.2, 5.0); self.sp_window_width.setDecimals(2); self.sp_window_width.setValue(float(getattr(self._dormer, "window_width_m", 1.20)))
        self.sp_window_height = QDoubleSpinBox(); self.sp_window_height.setRange(0.2, 5.0); self.sp_window_height.setDecimals(2); self.sp_window_height.setValue(float(getattr(self._dormer, "window_height_m", 1.20)))
        self.sp_sill = QDoubleSpinBox(); self.sp_sill.setRange(0.0, 3.0); self.sp_sill.setDecimals(2); self.sp_sill.setValue(float(getattr(self._dormer, "sill_height_m", 0.90)))
        self.cb_has_pitch = QCheckBox("eigene Gaubendach-Neigung verwenden")
        pitch = getattr(self._dormer, "roof_pitch_deg", None)
        self.cb_has_pitch.setChecked(pitch is not None)
        self.sp_pitch = QDoubleSpinBox(); self.sp_pitch.setRange(0.0, 85.0); self.sp_pitch.setDecimals(1); self.sp_pitch.setValue(float(15.0 if pitch is None else pitch))
        self.sp_edge_clearance = QDoubleSpinBox(); self.sp_edge_clearance.setRange(0.0, 5.0); self.sp_edge_clearance.setDecimals(2); self.sp_edge_clearance.setValue(float(getattr(self._dormer, "min_edge_clearance_m", 0.40)))

        form.addRow("ID", self.ed_id)
        form.addRow("Gaubentyp", self.cb_type)
        form.addRow("Dachseite", self.cb_side)
        form.addRow("Position entlang Dach [m]", self.sp_center)
        form.addRow("Breite [m]", self.sp_width)
        form.addRow("Tiefe [m]", self.sp_depth)
        form.addRow("Front-Höhe [m]", self.sp_front_height)
        form.addRow("Fensteranzahl", self.sp_window_count)
        form.addRow("Fensterbreite [m]", self.sp_window_width)
        form.addRow("Fensterhöhe [m]", self.sp_window_height)
        form.addRow("Brüstungshöhe [m]", self.sp_sill)
        form.addRow(self.cb_has_pitch)
        form.addRow("Gaubendach-Neigung [°]", self.sp_pitch)
        form.addRow("Mindestabstand Dachrand [m]", self.sp_edge_clearance)
        lay.addLayout(form)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.cb_has_pitch.toggled.connect(self.sp_pitch.setEnabled)
        self.sp_pitch.setEnabled(self.cb_has_pitch.isChecked())

    def set_active_sides(self, active_sides: tuple[str, ...], selected: str | None = None) -> None:
        labels = {"left": "links", "right": "rechts", "front": "vorne", "back": "hinten"}
        current = selected or self.cb_side.currentData() or "right"
        self.cb_side.blockSignals(True)
        self.cb_side.clear()
        for side in active_sides:
            self.cb_side.addItem(labels.get(side, side), side)
        idx = max(0, self.cb_side.findData(current))
        self.cb_side.setCurrentIndex(idx)
        self.cb_side.blockSignals(False)

    def to_dto(self) -> DormerCfgDTO:
        dtype = {"Schleppgaube": "schleppgaube", "Satteldachgaube": "satteldachgaube", "Flachdachgaube": "flachdachgaube"}.get(self.cb_type.currentText(), "schleppgaube")
        return DormerCfgDTO(
            id=self.ed_id.text().strip() or "dormer_1",
            dormer_type=dtype,
            roof_side=str(self.cb_side.currentData() or "right"),
            center_along_m=float(self.sp_center.value()),
            width_m=float(self.sp_width.value()),
            depth_m=float(self.sp_depth.value()),
            front_height_m=float(self.sp_front_height.value()),
            window_count=int(self.sp_window_count.value()),
            window_width_m=float(self.sp_window_width.value()),
            window_height_m=float(self.sp_window_height.value()),
            sill_height_m=float(self.sp_sill.value()),
            roof_pitch_deg=float(self.sp_pitch.value()) if self.cb_has_pitch.isChecked() else None,
            min_edge_clearance_m=float(self.sp_edge_clearance.value()),
        )


class ProjectSettingsDialog(QDialog):
    def __init__(self, parent, cfg: ProjectCfg, initial_tab: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Projektparameter – Heizlast")
        self.resize(860, 720)
        self._cfg = cfg
        self._dormers = [DormerCfgDTO(**d) if isinstance(d, dict) else DormerCfgDTO(**{k: getattr(d, k) for k in DormerCfgDTO.__dataclass_fields__.keys()}) for d in list(getattr(getattr(cfg, "attic", None), "dormers", []) or [])]
        self._roof_lines = [RoofLineCfgDTO(**d) if isinstance(d, dict) else RoofLineCfgDTO(**{k: getattr(d, k) for k in RoofLineCfgDTO.__dataclass_fields__.keys()}) for d in list(getattr(getattr(cfg, "attic", None), "roof_lines", []) or [])]
        if not self._dormers and str(getattr(getattr(cfg, "attic", None), "dormer_type", "none") or "none").strip().lower() != "none":
            self._dormers = [DormerCfgDTO(
                id="gaube_1",
                dormer_type=str(getattr(cfg.attic, "dormer_type", "schleppgaube") or "schleppgaube").strip().lower(),
                roof_side="right" if str(getattr(cfg.attic, "ridge_orientation", "length") or "length").strip().lower() == "length" else "back",
                center_along_m=float(getattr(cfg.attic, "building_length_m", 10.0)) / 2.0,
                width_m=float(getattr(cfg.attic, "dormer_width_m", 1.80)),
                depth_m=1.40,
                front_height_m=float(getattr(cfg.attic, "dormer_height_m", 1.20)),
                window_count=1,
                window_width_m=1.20,
                window_height_m=1.20,
                sill_height_m=0.90,
                roof_pitch_deg=float(getattr(cfg.attic, "roof_pitch_deg", 35.0)),
                min_edge_clearance_m=0.40,
            )]
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
        self.ed_internal_project_version = QLineEdit(str(getattr(cfg, "internal_project_version", "V30-intern-01")))
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
        self.cb_attic_roof_type = QComboBox(); self.cb_attic_roof_type.addItems(["Satteldach", "Pultdach", "Walmdach", "Krüppelwalmdach", "Flachdach", "Winkel-/Kehldach"])
        _roof_type_raw = str(getattr(cfg.attic, "roof_type", "satteldach") or "satteldach").strip().lower()
        _roof_type_map = {"satteldach": "Satteldach", "pultdach": "Pultdach", "walmdach": "Walmdach", "krueppelwalmdach": "Krüppelwalmdach", "flachdach": "Flachdach", "winkeldach": "Winkel-/Kehldach"}
        self.cb_attic_roof_type.setCurrentText(_roof_type_map.get(_roof_type_raw, "Satteldach"))
        self.cb_attic_ridge_orientation = QComboBox(); self.cb_attic_ridge_orientation.addItems(["längs", "quer"]); self.cb_attic_ridge_orientation.setCurrentText("quer" if str(getattr(cfg.attic, "ridge_orientation", "length") or "length").strip().lower() == "width" else "längs")
        self.sp_attic_overhang = QDoubleSpinBox(); self.sp_attic_overhang.setRange(0.0, 3.0); self.sp_attic_overhang.setDecimals(2); self.sp_attic_overhang.setSingleStep(0.05); self.sp_attic_overhang.setValue(float(getattr(cfg.attic, "roof_overhang_m", 0.30)))
        self.sp_attic_eave_overhang = QDoubleSpinBox(); self.sp_attic_eave_overhang.setRange(0.0, 3.0); self.sp_attic_eave_overhang.setDecimals(2); self.sp_attic_eave_overhang.setSingleStep(0.05); self.sp_attic_eave_overhang.setValue(float(getattr(cfg.attic, "eave_overhang_m", getattr(cfg.attic, "roof_overhang_m", 0.30))))
        self.sp_attic_gable_overhang = QDoubleSpinBox(); self.sp_attic_gable_overhang.setRange(0.0, 3.0); self.sp_attic_gable_overhang.setDecimals(2); self.sp_attic_gable_overhang.setSingleStep(0.05); self.sp_attic_gable_overhang.setValue(float(getattr(cfg.attic, "gable_overhang_m", getattr(cfg.attic, "roof_overhang_m", 0.30))))
        self.sp_attic_ridge_offset = QDoubleSpinBox(); self.sp_attic_ridge_offset.setRange(-0.80, 0.80); self.sp_attic_ridge_offset.setDecimals(2); self.sp_attic_ridge_offset.setSingleStep(0.05); self.sp_attic_ridge_offset.setValue(float(getattr(cfg.attic, "ridge_offset_ratio", 0.0)))
        self.cb_attic_pult_side = QComboBox(); self.cb_attic_pult_side.addItems(["links ansteigend", "rechts ansteigend"]); self.cb_attic_pult_side.setCurrentText("links ansteigend" if str(getattr(cfg.attic, "pult_rise_side", "right") or "right").strip().lower() == "left" else "rechts ansteigend")
        self.sp_attic_half_hip = QDoubleSpinBox(); self.sp_attic_half_hip.setRange(0.05, 0.95); self.sp_attic_half_hip.setDecimals(2); self.sp_attic_half_hip.setSingleStep(0.05); self.sp_attic_half_hip.setValue(float(getattr(cfg.attic, "half_hip_ratio", 0.45)))
        self.cb_attic_dormer_type = QComboBox(); self.cb_attic_dormer_type.addItems(["keine", "Schleppgaube", "Satteldachgaube", "Flachdachgaube"]); self.cb_attic_dormer_type.setCurrentText({"none":"keine","schleppgaube":"Schleppgaube","satteldachgaube":"Satteldachgaube","flachdachgaube":"Flachdachgaube"}.get(str(getattr(cfg.attic, "dormer_type", "none") or "none").strip().lower(), "keine"))
        self.sp_attic_dormer_width = QDoubleSpinBox(); self.sp_attic_dormer_width.setRange(0.5, 8.0); self.sp_attic_dormer_width.setDecimals(2); self.sp_attic_dormer_width.setValue(float(getattr(cfg.attic, "dormer_width_m", 1.80)))
        self.sp_attic_dormer_height = QDoubleSpinBox(); self.sp_attic_dormer_height.setRange(0.3, 4.0); self.sp_attic_dormer_height.setDecimals(2); self.sp_attic_dormer_height.setValue(float(getattr(cfg.attic, "dormer_height_m", 1.20)))
        self.sp_attic_dormer_offset = QDoubleSpinBox(); self.sp_attic_dormer_offset.setRange(-0.80, 0.80); self.sp_attic_dormer_offset.setDecimals(2); self.sp_attic_dormer_offset.setSingleStep(0.05); self.sp_attic_dormer_offset.setValue(float(getattr(cfg.attic, "dormer_offset_ratio", 0.0)))
        self.sp_attic_roof_window_count = QDoubleSpinBox(); self.sp_attic_roof_window_count.setRange(0, 8); self.sp_attic_roof_window_count.setDecimals(0); self.sp_attic_roof_window_count.setValue(float(getattr(cfg.attic, "roof_window_count", 0)))
        self.sp_attic_roof_window_width = QDoubleSpinBox(); self.sp_attic_roof_window_width.setRange(0.3, 2.5); self.sp_attic_roof_window_width.setDecimals(2); self.sp_attic_roof_window_width.setValue(float(getattr(cfg.attic, "roof_window_width_m", 0.78)))
        self.sp_attic_roof_window_height = QDoubleSpinBox(); self.sp_attic_roof_window_height.setRange(0.4, 2.5); self.sp_attic_roof_window_height.setDecimals(2); self.sp_attic_roof_window_height.setValue(float(getattr(cfg.attic, "roof_window_height_m", 1.18)))
        self.cb_attic_roof_window_side = QComboBox(); self.cb_attic_roof_window_side.addItems(["links", "rechts", "beidseitig"]); self.cb_attic_roof_window_side.setCurrentText({"left":"links","right":"rechts","both":"beidseitig"}.get(str(getattr(cfg.attic, "roof_window_side", "right") or "right").strip().lower(), "rechts"))
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
            "Firstrichtung, getrennte Überstände, Firstversatz, Krüppelwalm, Gauben und Dachfenster wirken auf Auto-DG, Vorschau und 3D-Ansicht."
        )
        self.lb_attic_hint.setWordWrap(True)
        self.gb_attic_activation = self._group("Aktivierung", self._make_form([(None, self.cb_attic_enabled)]), "Schaltet die Ableitung für DG-/Dachflächen ein oder aus.")
        self.gb_attic_geometry = self._group("Gebäude- und Dachgeometrie", self._make_form([
            ("Gebäudebreite / Giebelbreite [m]", self.sp_attic_width),
            ("Gebäudelänge in Firstrichtung [m]", self.sp_attic_length),
            ("Kniestockhöhe [m]", self.sp_attic_knee),
            ("Dachform", self.cb_attic_roof_type),
            ("Firstrichtung", self.cb_attic_ridge_orientation),
            ("Dachüberstand gesamt [m]", self.sp_attic_overhang),
            ("Traufüberstand [m]", self.sp_attic_eave_overhang),
            ("Giebelüberstand [m]", self.sp_attic_gable_overhang),
            ("Asymmetrie / Firstversatz [-1..1]", self.sp_attic_ridge_offset),
            ("Pultdach Neigungsrichtung", self.cb_attic_pult_side),
            ("Krüppelwalm-Anteil [0..1]", self.sp_attic_half_hip),
            ("Gaubentyp (Legacy)", self.cb_attic_dormer_type),
            ("Gaubenbreite (Legacy) [m]", self.sp_attic_dormer_width),
            ("Gaubenhöhe (Legacy) [m]", self.sp_attic_dormer_height),
            ("Gaubenlage (Legacy) [-1..1]", self.sp_attic_dormer_offset),
            ("Dachfenster Anzahl", self.sp_attic_roof_window_count),
            ("Dachfenster Breite [m]", self.sp_attic_roof_window_width),
            ("Dachfenster Höhe [m]", self.sp_attic_roof_window_height),
            ("Dachfenster Seite", self.cb_attic_roof_window_side),
            ("Dachneigung [°]", self.sp_attic_pitch),
        ]), "Geometrische Parameter für Vorschau, 3D-Modell und Auto-DG-Ableitung.")
        self.lst_dormers = QListWidget(); self.lst_dormers.setObjectName("dormerListWidget")
        self.btn_dormer_add = QPushButton("Hinzufügen")
        self.btn_dormer_edit = QPushButton("Bearbeiten")
        self.btn_dormer_delete = QPushButton("Löschen")
        dormer_btns = QWidget(); dormer_btns_lay = QHBoxLayout(dormer_btns); dormer_btns_lay.setContentsMargins(0, 0, 0, 0); dormer_btns_lay.setSpacing(8); dormer_btns_lay.addWidget(self.btn_dormer_add); dormer_btns_lay.addWidget(self.btn_dormer_edit); dormer_btns_lay.addWidget(self.btn_dormer_delete); dormer_btns_lay.addStretch(1)
        dormer_body = QWidget(); dormer_body_lay = QVBoxLayout(dormer_body); dormer_body_lay.setContentsMargins(6, 6, 6, 6); dormer_body_lay.setSpacing(8); dormer_body_lay.addWidget(self.lst_dormers); dormer_body_lay.addWidget(dormer_btns)
        self.gb_attic_dormers = self._group("Gaubenliste", dormer_body, "Mehrere Gauben direkt im Projekt verwalten. Add/Edit/Delete öffnet einen parametrischen Gauben-Dialog.")
        self.cb_roof_line_kind = QComboBox(); self.cb_roof_line_kind.addItems(["First", "Grat", "Kehle"])
        self.roof_line_editor = RoofLineEditorWidget(self)
        self.roof_line_editor.set_lines(self._roof_lines)
        self.lst_roof_lines = QListWidget(); self.lst_roof_lines.setObjectName("roofLineListWidget")
        self.btn_roof_line_delete = QPushButton("Ausgewählte Linie löschen")
        self.btn_roof_line_clear = QPushButton("Alle Linien löschen")
        roof_line_btns = QWidget(); roof_line_btns_lay = QHBoxLayout(roof_line_btns); roof_line_btns_lay.setContentsMargins(0, 0, 0, 0); roof_line_btns_lay.setSpacing(8); roof_line_btns_lay.addWidget(self.btn_roof_line_delete); roof_line_btns_lay.addWidget(self.btn_roof_line_clear); roof_line_btns_lay.addStretch(1)
        roof_line_body = QWidget(); roof_line_body_lay = QVBoxLayout(roof_line_body); roof_line_body_lay.setContentsMargins(6, 6, 6, 6); roof_line_body_lay.setSpacing(8); roof_line_body_lay.addWidget(self._make_form([("Linientyp", self.cb_roof_line_kind)]))
        roof_line_body_lay.addWidget(self.roof_line_editor)
        roof_line_body_lay.addWidget(self.lst_roof_lines)
        roof_line_body_lay.addWidget(roof_line_btns)
        self.gb_attic_roof_lines = self._group("Dachlinien-Editor", roof_line_body, "First-, Grat- und Kehllinien per Klick direkt in der Draufsicht setzen. Klick 1 = Start, Klick 2 = Ende.")
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
            self.gb_attic_dormers,
            self.gb_attic_roof_lines,
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
        self.cb_attic_dormer_type.currentTextChanged.connect(self._sync_attic_roof_type)
        self.cb_attic_ridge_orientation.currentTextChanged.connect(lambda _=None: (self._refresh_dormer_actions(), self._refresh_roof_line_actions()))
        self.btn_dormer_add.clicked.connect(self._add_dormer)
        self.btn_dormer_edit.clicked.connect(self._edit_selected_dormer)
        self.btn_dormer_delete.clicked.connect(self._delete_selected_dormer)
        self.lst_dormers.itemDoubleClicked.connect(lambda _item: self._edit_selected_dormer())
        self.lst_dormers.currentRowChanged.connect(lambda _row: self._refresh_dormer_actions())
        self.cb_roof_line_kind.currentTextChanged.connect(self._sync_roof_line_kind)
        self.lst_roof_lines.currentRowChanged.connect(self._on_roof_line_list_row_changed)
        self.btn_roof_line_delete.clicked.connect(self._delete_selected_roof_line)
        self.btn_roof_line_clear.clicked.connect(self._clear_roof_lines)
        self.roof_line_editor.on_lines_changed = self._on_roof_lines_changed

        if self.tabs.count():
            self.tabs.setCurrentRow(self.tabs.currentRow() if self.tabs.currentRow() >= 0 else 0)
        self._sync_tb_mode(self.cb_tb_mode.currentText())
        self._sync_ground_mode(self.cb_ground_mode.currentText())
        self._sync_attic_enabled(bool(self.cb_attic_enabled.isChecked()))
        self._sync_attic_roof_type(self.cb_attic_roof_type.currentText())
        self._reload_dormer_list()
        self._sync_roof_line_kind(self.cb_roof_line_kind.currentText())
        self._reload_roof_line_list()
        self._refresh_dormer_actions()
        self._refresh_roof_line_actions()

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
        self.gb_attic_dormers.setEnabled(bool(enabled))
        self.gb_attic_materials.setEnabled(bool(enabled))
        self.gb_attic_u.setEnabled(bool(enabled))
        self._set_widgets_enabled([
            self.sp_attic_width,
            self.sp_attic_length,
            self.sp_attic_knee,
            self.cb_attic_roof_type,
            self.cb_attic_ridge_orientation,
            self.sp_attic_overhang,
            self.sp_attic_eave_overhang,
            self.sp_attic_gable_overhang,
            self.sp_attic_ridge_offset,
            self.cb_attic_pult_side,
            self.sp_attic_half_hip,
            self.cb_attic_dormer_type,
            self.sp_attic_dormer_width,
            self.sp_attic_dormer_height,
            self.sp_attic_dormer_offset,
            self.sp_attic_roof_window_count,
            self.sp_attic_roof_window_width,
            self.sp_attic_roof_window_height,
            self.cb_attic_roof_window_side,
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
        is_half_hip = roof_type == "Krüppelwalmdach"
        is_flat = roof_type == "Flachdach"
        is_winkel = roof_type == "Winkel-/Kehldach"
        dormer_enabled = enabled and not is_flat and self.cb_attic_dormer_type.currentText() != "keine"
        roof_window_enabled = enabled and not is_flat
        self.cb_attic_ridge_orientation.setEnabled(enabled and roof_type != "Flachdach")
        self.sp_attic_ridge_offset.setEnabled(enabled and (is_saddle or is_half_hip))
        self.cb_attic_pult_side.setEnabled(enabled and is_pult)
        self.sp_attic_half_hip.setEnabled(enabled and is_half_hip)
        self.sp_attic_pitch.setEnabled(enabled and not is_flat)
        self.sp_attic_dormer_width.setEnabled(dormer_enabled)
        self.sp_attic_dormer_height.setEnabled(dormer_enabled)
        self.sp_attic_dormer_offset.setEnabled(dormer_enabled)
        self.sp_attic_roof_window_count.setEnabled(roof_window_enabled)
        self.sp_attic_roof_window_width.setEnabled(roof_window_enabled)
        self.sp_attic_roof_window_height.setEnabled(roof_window_enabled)
        self.cb_attic_roof_window_side.setEnabled(roof_window_enabled)
        self._refresh_dormer_actions()
        self._refresh_roof_line_actions()

    def _active_dormer_sides(self) -> tuple[str, ...]:
        return ("front", "back") if self.cb_attic_ridge_orientation.currentText() == "quer" else ("left", "right")

    def _friendly_dormer_label(self, dormer: DormerCfgDTO) -> str:
        tmap = {"schleppgaube": "Schleppgaube", "satteldachgaube": "Satteldachgaube", "flachdachgaube": "Flachdachgaube"}
        smap = {"left": "links", "right": "rechts", "front": "vorne", "back": "hinten"}
        pitch = "auto" if dormer.roof_pitch_deg is None else f"{float(dormer.roof_pitch_deg):.1f}°"
        return (
            f"{dormer.id} · {tmap.get(str(dormer.dormer_type), str(dormer.dormer_type))} · {smap.get(str(dormer.roof_side), str(dormer.roof_side))} · "
            f"Pos {float(dormer.center_along_m):.2f} m · B {float(dormer.width_m):.2f} m · T {float(dormer.depth_m):.2f} m · Dach {pitch}"
        )

    def _reload_dormer_list(self) -> None:
        self.lst_dormers.clear()
        for dormer in self._dormers:
            self.lst_dormers.addItem(self._friendly_dormer_label(dormer))
        if self._dormers and self.lst_dormers.currentRow() < 0:
            self.lst_dormers.setCurrentRow(0)

    def _refresh_dormer_actions(self) -> None:
        enabled = bool(self.cb_attic_enabled.isChecked()) and self.cb_attic_roof_type.currentText() != "Flachdach"
        self.gb_attic_dormers.setEnabled(enabled)
        has_selection = self.lst_dormers.currentRow() >= 0
        self.btn_dormer_add.setEnabled(enabled)
        self.btn_dormer_edit.setEnabled(enabled and has_selection)
        self.btn_dormer_delete.setEnabled(enabled and has_selection)

    def _make_default_dormer(self) -> DormerCfgDTO:
        idx = len(self._dormers) + 1
        side = self._active_dormer_sides()[-1]
        return DormerCfgDTO(
            id=f"gaube_{idx}",
            dormer_type={"Schleppgaube": "schleppgaube", "Satteldachgaube": "satteldachgaube", "Flachdachgaube": "flachdachgaube"}.get(self.cb_attic_dormer_type.currentText(), "schleppgaube"),
            roof_side=side,
            center_along_m=max(0.0, float(self.sp_attic_length.value()) / 2.0),
            width_m=float(self.sp_attic_dormer_width.value()),
            depth_m=1.40,
            front_height_m=float(self.sp_attic_dormer_height.value()),
            window_count=1,
            window_width_m=1.20,
            window_height_m=1.20,
            sill_height_m=0.90,
            roof_pitch_deg=float(self.sp_attic_pitch.value()),
            min_edge_clearance_m=0.40,
        )

    def _add_dormer(self) -> None:
        dlg = DormerEditDialog(self, self._make_default_dormer(), active_sides=self._active_dormer_sides())
        if dlg.exec() == QDialog.Accepted:
            self._dormers.append(dlg.to_dto())
            self._reload_dormer_list()
            self.lst_dormers.setCurrentRow(len(self._dormers) - 1)
            self._refresh_dormer_actions()

    def _edit_selected_dormer(self) -> None:
        row = self.lst_dormers.currentRow()
        if row < 0 or row >= len(self._dormers):
            return
        dlg = DormerEditDialog(self, self._dormers[row], active_sides=self._active_dormer_sides())
        if dlg.exec() == QDialog.Accepted:
            self._dormers[row] = dlg.to_dto()
            self._reload_dormer_list()
            self.lst_dormers.setCurrentRow(row)
            self._refresh_dormer_actions()

    def _delete_selected_dormer(self) -> None:
        row = self.lst_dormers.currentRow()
        if row < 0 or row >= len(self._dormers):
            return
        dormer = self._dormers[row]
        if QMessageBox.question(self, "Gaube löschen", f"Soll die Gaube '{dormer.id}' gelöscht werden?") != QMessageBox.Yes:
            return
        del self._dormers[row]
        self._reload_dormer_list()
        if self._dormers:
            self.lst_dormers.setCurrentRow(min(row, len(self._dormers) - 1))
        self._refresh_dormer_actions()

    def _friendly_roof_line_label(self, line: RoofLineCfgDTO) -> str:
        kind = {"first": "First", "grat": "Grat", "kehle": "Kehle"}.get(str(getattr(line, "kind", "first") or "first").strip().lower(), str(getattr(line, "kind", "first")))
        return f"{kind} · ({float(line.x1_ratio):.2f}, {float(line.y1_ratio):.2f}) → ({float(line.x2_ratio):.2f}, {float(line.y2_ratio):.2f})"

    def _reload_roof_line_list(self) -> None:
        self._roof_lines = self.roof_line_editor.current_lines()
        self.lst_roof_lines.clear()
        for line in self._roof_lines:
            self.lst_roof_lines.addItem(self._friendly_roof_line_label(line))
        current = self.roof_line_editor.selected_index()
        if 0 <= current < self.lst_roof_lines.count():
            self.lst_roof_lines.setCurrentRow(current)
        elif self.lst_roof_lines.count() > 0 and self.lst_roof_lines.currentRow() < 0:
            self.lst_roof_lines.setCurrentRow(self.lst_roof_lines.count() - 1)

    def _refresh_roof_line_actions(self) -> None:
        enabled = bool(self.cb_attic_enabled.isChecked()) and self.cb_attic_roof_type.currentText() == "Winkel-/Kehldach"
        self.gb_attic_roof_lines.setEnabled(enabled)
        has_selection = self.lst_roof_lines.currentRow() >= 0
        self.btn_roof_line_delete.setEnabled(enabled and has_selection)
        self.btn_roof_line_clear.setEnabled(enabled and self.lst_roof_lines.count() > 0)
        self.cb_roof_line_kind.setEnabled(enabled)
        self.roof_line_editor.setEnabled(enabled)

    def _sync_roof_line_kind(self, label: str) -> None:
        mapping = {"First": "first", "Grat": "grat", "Kehle": "kehle"}
        self.roof_line_editor.set_current_kind(mapping.get(str(label), "first"))
        self._refresh_roof_line_actions()

    def _on_roof_lines_changed(self) -> None:
        self._reload_roof_line_list()
        self._refresh_roof_line_actions()

    def _on_roof_line_list_row_changed(self, row: int) -> None:
        self.roof_line_editor._selected_index = row
        self.roof_line_editor.update()
        self._refresh_roof_line_actions()

    def _delete_selected_roof_line(self) -> None:
        self.roof_line_editor.delete_selected_line()
        self._reload_roof_line_list()
        self._refresh_roof_line_actions()

    def _clear_roof_lines(self) -> None:
        if self.lst_roof_lines.count() <= 0:
            return
        if QMessageBox.question(self, "Dachlinien löschen", "Sollen alle Dachlinien gelöscht werden?") != QMessageBox.Yes:
            return
        self.roof_line_editor.clear_all()
        self._reload_roof_line_list()
        self._refresh_roof_line_actions()

    def apply_to_cfg(self, cfg: ProjectCfg) -> None:
        cfg.cfg_version = PROJECT_SCHEMA_VERSION
        cfg.internal_project_version = self.ed_internal_project_version.text().strip() or "V30-intern-01"

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
        _roof_rev = {"Satteldach": "satteldach", "Pultdach": "pultdach", "Walmdach": "walmdach", "Krüppelwalmdach": "krueppelwalmdach", "Flachdach": "flachdach", "Winkel-/Kehldach": "winkeldach"}
        cfg.attic.roof_type = _roof_rev.get(self.cb_attic_roof_type.currentText(), "satteldach")
        cfg.attic.ridge_orientation = "width" if self.cb_attic_ridge_orientation.currentText() == "quer" else "length"
        cfg.attic.roof_overhang_m = float(self.sp_attic_overhang.value())
        cfg.attic.eave_overhang_m = float(self.sp_attic_eave_overhang.value())
        cfg.attic.gable_overhang_m = float(self.sp_attic_gable_overhang.value())
        cfg.attic.ridge_offset_ratio = float(self.sp_attic_ridge_offset.value())
        cfg.attic.pult_rise_side = "left" if self.cb_attic_pult_side.currentText() == "links ansteigend" else "right"
        cfg.attic.half_hip_ratio = float(self.sp_attic_half_hip.value())
        _dormer_rev = {"keine": "none", "Schleppgaube": "schleppgaube", "Satteldachgaube": "satteldachgaube", "Flachdachgaube": "flachdachgaube"}
        cfg.attic.dormer_type = _dormer_rev.get(self.cb_attic_dormer_type.currentText(), "none")
        cfg.attic.dormer_width_m = float(self.sp_attic_dormer_width.value())
        cfg.attic.dormer_height_m = float(self.sp_attic_dormer_height.value())
        cfg.attic.dormer_offset_ratio = float(self.sp_attic_dormer_offset.value())
        cfg.attic.dormers = [DormerCfgDTO(**{k: getattr(d, k) for k in DormerCfgDTO.__dataclass_fields__.keys()}) for d in self._dormers]
        cfg.attic.roof_lines = [RoofLineCfgDTO(**{k: getattr(line, k) for k in RoofLineCfgDTO.__dataclass_fields__.keys()}) for line in self.roof_line_editor.current_lines()]
        if cfg.attic.dormers:
            first = cfg.attic.dormers[0]
            cfg.attic.dormer_type = str(first.dormer_type)
            cfg.attic.dormer_width_m = float(first.width_m)
            cfg.attic.dormer_height_m = float(first.front_height_m)
        elif cfg.attic.dormer_type != "none":
            cfg.attic.dormer_type = _dormer_rev.get(self.cb_attic_dormer_type.currentText(), "none")
        cfg.attic.roof_window_count = int(round(float(self.sp_attic_roof_window_count.value())))
        cfg.attic.roof_window_width_m = float(self.sp_attic_roof_window_width.value())
        cfg.attic.roof_window_height_m = float(self.sp_attic_roof_window_height.value())
        cfg.attic.roof_window_side = {"links": "left", "rechts": "right", "beidseitig": "both"}.get(self.cb_attic_roof_window_side.currentText(), "right")
        cfg.attic.roof_pitch_deg = float(self.sp_attic_pitch.value())
        _facade_rev = {"Klinker": "klinker", "Putz": "putz", "Holz": "holz", "Beton": "beton"}
        cfg.attic.facade_material = _facade_rev.get(self.cb_attic_facade_material.currentText(), "klinker")
        _roof_material_rev = {"Ziegel": "ziegel"}
        cfg.attic.roof_material = _roof_material_rev.get(self.cb_attic_roof_material.currentText(), "ziegel")
        cfg.attic.u_roof_w_m2k = float(self.sp_attic_u_roof.value())
        cfg.attic.u_gable_w_m2k = float(self.sp_attic_u_gable.value())
