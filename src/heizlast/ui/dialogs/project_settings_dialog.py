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
    QTabWidget,
)
from ... import PROJECT_SCHEMA_VERSION
from ...configs.project_config import ProjectCfg, DormerCfgDTO, RoofLineCfgDTO, AtticCfgDTO
from ...core.attic_geometry import AtticGeometry
from ...core.dormer_auto_elements import build_dormer_results_from_attic_cfg, dormer_cutout_area_total


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
        if not p.isActive():
            return
        p.setRenderHint(QPainter.Antialiasing, True)
        outer = self.rect().adjusted(10, 10, -10, -10)
        if outer.width() <= 0 or outer.height() <= 0:
            p.end()
            return
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
        self.cb_type = QComboBox(); self.cb_type.addItems(["Schleppgaube", "Satteldachgaube", "Flachdachgaube", "Spitzgaube"])
        self.cb_type.setCurrentText({"schleppgaube": "Schleppgaube", "satteldachgaube": "Satteldachgaube", "flachdachgaube": "Flachdachgaube", "spitzgaube": "Spitzgaube"}.get(str(getattr(self._dormer, "dormer_type", "schleppgaube") or "schleppgaube").strip().lower(), "Schleppgaube"))
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
        dtype = {"Schleppgaube": "schleppgaube", "Satteldachgaube": "satteldachgaube", "Flachdachgaube": "flachdachgaube", "Spitzgaube": "spitzgaube"}.get(self.cb_type.currentText(), "schleppgaube")
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
        self.ed_norm_edition = QLineEdit(str(getattr(cfg, "norm_edition", "DIN EN 12831-1:2017-09 / DIN/TS 12831-1:2020-04")))
        self.ed_reviewer_note = QLineEdit(str(getattr(cfg, "reviewer_note", "")))
        self.ed_reviewer_note.setPlaceholderText("Bearbeiter/Prüfvermerk, optional")
        self.cb_proof_export = QCheckBox("DIN-Prüffassung nur bei grünen Tool-Gates freigeben")
        self.cb_proof_export.setChecked(bool(getattr(cfg, "proof_export_enabled", False)))
        self.ed_change_log_note = QLineEdit(str(getattr(cfg, "change_log_note", "")))
        self.ed_change_log_note.setPlaceholderText("Kurzprotokoll geänderter Nachweiswerte, optional")
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
            ("Normausgabe", self.ed_norm_edition),
            ("Bearbeiter/Prüfvermerk", self.ed_reviewer_note),
            ("Prüffassung", self.cb_proof_export),
            ("Änderungsprotokoll", self.ed_change_log_note),
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
        self.ed_t_out_source_detail = QLineEdit(str(getattr(cfg, "t_out_source_detail", "")))
        self.ed_t_out_source_detail.setPlaceholderText("z.B. Klimatabelle, PLZ, Höhenkorrektur")
        self.ed_climate_station = QLineEdit(str(getattr(cfg, "climate_station", "")))
        self.ed_climate_altitude = QLineEdit(str(getattr(cfg, "climate_altitude_correction", "")))
        self.lb_t_source_hint = QLabel("manual = feste Eingabe, din12831 = Normquelle, custom = projektspezifischer Wert")
        self.lb_t_source_hint.setWordWrap(True)
        f1a = self._make_form([
            ("Norm-Außentemp. t_out [°C]", self.sp_t_out),
            ("Keller temp. t_keller [°C]", self.sp_t_keller),
            ("Oben temp. t_oben [°C]", self.sp_t_oben),
        ])
        f1b = self._make_form([
            ("Quelle Außentemperatur", self.cb_t_out_source),
            ("Quellendetail", self.ed_t_out_source_detail),
            ("Klimastation/Region", self.ed_climate_station),
            ("Höhenkorrektur", self.ed_climate_altitude),
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
        self.sp_wall_h_inside = QDoubleSpinBox(); self.sp_wall_h_inside.setRange(0.1, 100.0); self.sp_wall_h_inside.setDecimals(2); self.sp_wall_h_inside.setSingleStep(0.1); self.sp_wall_h_inside.setValue(float(getattr(cfg, "wall_heat_transfer_coeff_inside_w_m2k", 7.69)))
        self.sp_wall_h_outside = QDoubleSpinBox(); self.sp_wall_h_outside.setRange(0.1, 100.0); self.sp_wall_h_outside.setDecimals(2); self.sp_wall_h_outside.setSingleStep(0.1); self.sp_wall_h_outside.setValue(float(getattr(cfg, "wall_heat_transfer_coeff_outside_w_m2k", 25.0)))
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
            ("α innen Außenwand [W/m²K]", self.sp_wall_h_inside),
            ("α außen Außenwand [W/m²K]", self.sp_wall_h_outside),
            ("Hinweis", self.lb_geo_hint),
        ])
        self._add_nav_page("Geometrie", self._build_tab([
            self._group("Flächenmodell", f2a, "Steuert die geometrische Bezugslogik der Flächen- und Volumenableitung."),
            self._group("Wandstärken", f2b, "Material- und Referenzdicken für Innen- und Außenwände."),
        ]))

        # --- Tab: Lüftung ---
        self.sp_c_air = QDoubleSpinBox(); self.sp_c_air.setRange(0.0, 5.0); self.sp_c_air.setDecimals(3); self.sp_c_air.setValue(cfg.c_air)
        self.cb_vent_mode = QComboBox(); self.cb_vent_mode.addItems(["natural", "mechanical"]); self.cb_vent_mode.setCurrentText(str(getattr(cfg, "ventilation_mode", "natural") or "natural"))
        self.sp_min_air_change = QDoubleSpinBox(); self.sp_min_air_change.setRange(0.0, 5.0); self.sp_min_air_change.setDecimals(3); self.sp_min_air_change.setSingleStep(0.05); self.sp_min_air_change.setValue(float(getattr(cfg, "min_air_change_1ph", 0.0)))
        self.sp_infiltration_air_change = QDoubleSpinBox(); self.sp_infiltration_air_change.setRange(0.0, 5.0); self.sp_infiltration_air_change.setDecimals(3); self.sp_infiltration_air_change.setSingleStep(0.05); self.sp_infiltration_air_change.setValue(float(getattr(cfg, "infiltration_air_change_1ph", 0.0)))
        self.sp_mech_supply = QDoubleSpinBox(); self.sp_mech_supply.setRange(0.0, 10000.0); self.sp_mech_supply.setDecimals(1); self.sp_mech_supply.setValue(float(getattr(cfg, "mech_supply_m3h", 0.0)))
        self.sp_mech_exhaust = QDoubleSpinBox(); self.sp_mech_exhaust.setRange(0.0, 10000.0); self.sp_mech_exhaust.setDecimals(1); self.sp_mech_exhaust.setValue(float(getattr(cfg, "mech_exhaust_m3h", 0.0)))
        self.sp_hrv = QDoubleSpinBox(); self.sp_hrv.setRange(0.0, 1.0); self.sp_hrv.setDecimals(3); self.sp_hrv.setSingleStep(0.05); self.sp_hrv.setValue(float(getattr(cfg, "heat_recovery_efficiency", 0.0)))
        self.ed_vent_source = QLineEdit(str(getattr(cfg, "ventilation_source", "")))
        self.ed_vent_source.setPlaceholderText("Quelle Volumenstrom/WRG, optional")
        self.cb_reheat_enabled = QCheckBox("Aufheizzuschlag ansetzen"); self.cb_reheat_enabled.setChecked(bool(getattr(cfg, "reheat_enabled", False)))
        self.sp_reheat = QDoubleSpinBox(); self.sp_reheat.setRange(0.0, 500.0); self.sp_reheat.setDecimals(2); self.sp_reheat.setValue(float(getattr(cfg, "reheat_power_w_m2", 0.0)))
        self.sp_reheat_duration = QDoubleSpinBox(); self.sp_reheat_duration.setRange(0.0, 48.0); self.sp_reheat_duration.setDecimals(2); self.sp_reheat_duration.setValue(float(getattr(cfg, "reheat_duration_h", 2.0)))
        self.sp_reheat_drop = QDoubleSpinBox(); self.sp_reheat_drop.setRange(0.0, 30.0); self.sp_reheat_drop.setDecimals(2); self.sp_reheat_drop.setValue(float(getattr(cfg, "reheat_temp_drop_k", 0.0)))
        self.sp_reheat_capacity = QDoubleSpinBox(); self.sp_reheat_capacity.setRange(0.0, 500.0); self.sp_reheat_capacity.setDecimals(2); self.sp_reheat_capacity.setValue(float(getattr(cfg, "reheat_capacity_wh_m2k", 20.0)))
        self.ed_reheat_source = QLineEdit(str(getattr(cfg, "reheat_source", "")))
        self.ed_reheat_source.setPlaceholderText("Quelle Aufheizzuschlag, optional")
        self.ed_reheat_norm_basis = QLineEdit(str(getattr(cfg, "reheat_norm_basis", "")))
        self.ed_reheat_norm_basis.setPlaceholderText("Nutzung/Gebäudeschwere/Wiederaufheizzeit/Tabellenbezug")
        self.lb_air_hint = QLabel("c_air ist der globale Luftwärmekoeffizient für die Lüftungsverluste der Räume.")
        self.lb_air_hint.setWordWrap(True)
        f3 = self._make_form([
            ("Lüftungsart", self.cb_vent_mode),
            ("c_air [Wh/(m³·K)]", self.sp_c_air),
            ("Mindestluftwechsel n_min [1/h]", self.sp_min_air_change),
            ("Infiltration n_inf [1/h]", self.sp_infiltration_air_change),
            ("Zuluft Volumenstrom [m³/h]", self.sp_mech_supply),
            ("Abluft Volumenstrom [m³/h]", self.sp_mech_exhaust),
            ("WRG-Wirkungsgrad [-]", self.sp_hrv),
            ("Quelle Lüftung/WRG", self.ed_vent_source),
            ("Aufheizzuschlag", self.cb_reheat_enabled),
            ("q_hu [W/m²]", self.sp_reheat),
            ("Wiederaufheizzeit [h]", self.sp_reheat_duration),
            ("Temperaturabsenkung [K]", self.sp_reheat_drop),
            ("Speicherkennwert [Wh/m²K]", self.sp_reheat_capacity),
            ("Quelle Aufheizzuschlag", self.ed_reheat_source),
            ("Norm-/Tabellenbasis", self.ed_reheat_norm_basis),
            ("Hinweis", self.lb_air_hint),
        ])
        self._add_nav_page("Lüftung", self._build_tab([
            self._group("Lüftungsmodell", f3, "Globale Einstellungen für die Lüftungsverluste der Räume."),
        ]))

        # --- Tab: Auto-Decken U-Werte ---
        self.sp_u_aw = QDoubleSpinBox(); self.sp_u_aw.setRange(0.0, 5.0); self.sp_u_aw.setDecimals(3); self.sp_u_aw.setValue(float(getattr(cfg, "u_aussenwand_w_m2k", 0.45)))
        self.sp_u_window = QDoubleSpinBox(); self.sp_u_window.setRange(0.0, 5.0); self.sp_u_window.setDecimals(3); self.sp_u_window.setValue(float(getattr(cfg, "u_fenster_w_m2k", 2.80)))
        self.sp_u_door = QDoubleSpinBox(); self.sp_u_door.setRange(0.0, 5.0); self.sp_u_door.setDecimals(3); self.sp_u_door.setValue(float(getattr(cfg, "u_tuer_w_m2k", 1.80)))
        self.sp_u_kd = QDoubleSpinBox(); self.sp_u_kd.setRange(0.0, 5.0); self.sp_u_kd.setDecimals(3); self.sp_u_kd.setValue(cfg.u_kellerdecke_w_m2k)
        self.sp_u_eg = QDoubleSpinBox(); self.sp_u_eg.setRange(0.0, 5.0); self.sp_u_eg.setDecimals(3); self.sp_u_eg.setValue(cfg.u_eg_geschossdecke_w_m2k)
        self.sp_u_dg = QDoubleSpinBox(); self.sp_u_dg.setRange(0.0, 5.0); self.sp_u_dg.setDecimals(3); self.sp_u_dg.setValue(cfg.u_dg_geschossdecke_w_m2k)
        self.sp_u_bodenplatte = QDoubleSpinBox(); self.sp_u_bodenplatte.setRange(0.0, 5.0); self.sp_u_bodenplatte.setDecimals(3); self.sp_u_bodenplatte.setValue(float(getattr(cfg, "u_bodenplatte_w_m2k", 0.40)))
        self.sp_u_erdwand = QDoubleSpinBox(); self.sp_u_erdwand.setRange(0.0, 5.0); self.sp_u_erdwand.setDecimals(3); self.sp_u_erdwand.setValue(float(getattr(cfg, "u_erdberuehrte_wand_w_m2k", 0.60)))
        self.ed_u_source = QLineEdit(str(getattr(cfg, "u_value_source", "")))
        self.ed_u_source.setPlaceholderText("Quelle U-Werte, z.B. Energieausweis, Bauteilkatalog, Herstellerdaten")
        self.cb_auto_deck_confirmed = QCheckBox("Auto-Decken-Annahmen fachlich geprüft")
        self.cb_auto_deck_confirmed.setChecked(bool(getattr(cfg, "auto_deck_assumptions_confirmed", False)))
        self.ed_auto_deck_boundary_source = QLineEdit(str(getattr(cfg, "auto_deck_boundary_source", "")))
        self.ed_auto_deck_boundary_source.setPlaceholderText("Quelle Randbedingungen, z.B. Bestandsaufnahme, Plan, Bauteilnachweis")
        self.cb_auto_deck_eg_keller = QCheckBox("EG: Kellerdecke automatisch erzeugen")
        self.cb_auto_deck_eg_keller.setChecked(bool(getattr(cfg, "auto_deck_create_eg_kellerdecke", True)))
        self.cb_auto_deck_eg_deck = QCheckBox("EG: Geschossdecke zu DG automatisch erzeugen")
        self.cb_auto_deck_eg_deck.setChecked(bool(getattr(cfg, "auto_deck_create_eg_geschossdecke", True)))
        self.cb_auto_deck_dg_attic = QCheckBox("DG: Speicherdecke automatisch erzeugen")
        self.cb_auto_deck_dg_attic.setChecked(bool(getattr(cfg, "auto_deck_create_dg_speicherdecke", True)))
        self.cb_norm_profile = QComboBox()
        self.cb_norm_profile.addItems(["Individuell", "Altbau unsaniert", "Teilsaniert", "Neubau"])
        self.btn_apply_norm_profile = QPushButton("Profil anwenden")
        profile_actions = QWidget()
        profile_actions_lay = QHBoxLayout(profile_actions)
        profile_actions_lay.setContentsMargins(0, 0, 0, 0)
        profile_actions_lay.setSpacing(8)
        profile_actions_lay.addWidget(self.cb_norm_profile, 1)
        profile_actions_lay.addWidget(self.btn_apply_norm_profile, 0)
        f4_profile = self._make_form([
            ("Schnellprofil", profile_actions),
        ])
        f4 = self._make_form([
            ("U Außenwand [W/m²K]", self.sp_u_aw),
            ("U Fenster [W/m²K]", self.sp_u_window),
            ("U Tür [W/m²K]", self.sp_u_door),
            ("U Kellerdecke [W/m²K]", self.sp_u_kd),
            ("U EG-Geschossdecke [W/m²K]", self.sp_u_eg),
            ("U DG-Geschossdecke [W/m²K]", self.sp_u_dg),
            ("U Bodenplatte [W/m²K]", self.sp_u_bodenplatte),
            ("U erdberührte Wand [W/m²K]", self.sp_u_erdwand),
            ("Quelle U-Werte", self.ed_u_source),
        ])
        f4_decks = self._make_form([
            ("Annahmen bestätigt", self.cb_auto_deck_confirmed),
            ("Quelle Randbedingungen", self.ed_auto_deck_boundary_source),
            ("Kellerdecke", self.cb_auto_deck_eg_keller),
            ("EG-Geschossdecke", self.cb_auto_deck_eg_deck),
            ("DG-Speicherdecke", self.cb_auto_deck_dg_attic),
        ])
        self._add_nav_page("Auto-Decken", self._build_tab([
            self._group("Schnellprofil", f4_profile, "Setzt plausible Startwerte für typische Sanierungsstände. Die Werte bleiben Projektannahmen und sollten über die Quelle U-Werte dokumentiert werden."),
            self._group("Projekt-U-Werte", f4, "U-Werte für automatisch abgeleitete Außenwände und Decken sowie Fallbackwerte für erdberührte Bauteile ohne eigenen U-Wert."),
            self._group("Automatische Decken", f4_decks, "Steuert, welche Decken aus dem Geschossmodell erzeugt werden und ob die daraus folgenden Nachbarzonen als geprüft gelten."),
        ]))

        # --- Tab: Wärmebrücken ---
        self.cb_tb_mode = QComboBox(); self.cb_tb_mode.addItems(["none", "delta_u", "psi", "percent"]); self.cb_tb_mode.setCurrentText(cfg.tb.mode)
        self.sp_tb_du = QDoubleSpinBox(); self.sp_tb_du.setRange(0.0, 1.0); self.sp_tb_du.setDecimals(3); self.sp_tb_du.setValue(cfg.tb.delta_u_w_m2k)
        self.sp_tb_psi = QDoubleSpinBox(); self.sp_tb_psi.setRange(0.0, 5.0); self.sp_tb_psi.setDecimals(3); self.sp_tb_psi.setValue(cfg.tb.psi_default_w_mk)
        self.sp_tb_p = QDoubleSpinBox(); self.sp_tb_p.setRange(0.0, 2.0); self.sp_tb_p.setDecimals(3); self.sp_tb_p.setValue(cfg.tb.percent_of_trans)
        self.cb_tb_meta = QCheckBox("ψ aus Element-meta nutzen (psi_w_mk / psi_L_m)"); self.cb_tb_meta.setChecked(bool(cfg.tb.use_element_meta_psi))
        self.ed_tb_source = QLineEdit(str(getattr(cfg, "thermal_bridge_source", "")))
        self.ed_tb_source.setPlaceholderText("Quelle ΔU/ψ, z.B. Anschlusskatalog")
        self.cb_tb_out = QCheckBox("WB für Außen"); self.cb_tb_out.setChecked(bool(cfg.tb.include_out))
        self.cb_tb_k = QCheckBox("WB für Keller"); self.cb_tb_k.setChecked(bool(cfg.tb.include_keller))
        self.cb_tb_o = QCheckBox("WB für Oben"); self.cb_tb_o.setChecked(bool(cfg.tb.include_oben))
        f5a = self._make_form([
            ("Modus", self.cb_tb_mode),
            ("ΔU [W/m²K] (delta_u)", self.sp_tb_du),
            ("ψ default [W/mK] (psi)", self.sp_tb_psi),
            ("p (percent)", self.sp_tb_p),
            ("Quelle Wärmebrücken", self.ed_tb_source),
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
        self.cb_ground_mode = QComboBox(); self.cb_ground_mode.addItems(["none", "simplified", "perimeter", "din_ts"]); self.cb_ground_mode.setCurrentText(getattr(cfg.ground, "mode", "simplified"))
        self.sp_ground_temp = QDoubleSpinBox(); self.sp_ground_temp.setRange(-20.0, 30.0); self.sp_ground_temp.setDecimals(2); self.sp_ground_temp.setValue(float(getattr(cfg.ground, "ground_temp_c", 10.0)))
        self.sp_ground_f_slab = QDoubleSpinBox(); self.sp_ground_f_slab.setRange(0.0, 1.0); self.sp_ground_f_slab.setDecimals(3); self.sp_ground_f_slab.setSingleStep(0.05); self.sp_ground_f_slab.setValue(float(getattr(cfg.ground, "f_slab", 0.40)))
        self.sp_ground_f_wall = QDoubleSpinBox(); self.sp_ground_f_wall.setRange(0.0, 1.0); self.sp_ground_f_wall.setDecimals(3); self.sp_ground_f_wall.setSingleStep(0.05); self.sp_ground_f_wall.setValue(float(getattr(cfg.ground, "f_wall", 0.60)))
        self.sp_ground_psi = QDoubleSpinBox(); self.sp_ground_psi.setRange(0.0, 5.0); self.sp_ground_psi.setDecimals(3); self.sp_ground_psi.setSingleStep(0.01); self.sp_ground_psi.setValue(float(getattr(cfg.ground, "psi_perimeter_w_mk", 0.0)))
        self.sp_ground_din_f_slab = QDoubleSpinBox(); self.sp_ground_din_f_slab.setRange(0.0, 1.0); self.sp_ground_din_f_slab.setDecimals(3); self.sp_ground_din_f_slab.setSingleStep(0.05); self.sp_ground_din_f_slab.setValue(float(getattr(cfg.ground, "din_ts_f_slab", 0.35)))
        self.sp_ground_din_f_wall = QDoubleSpinBox(); self.sp_ground_din_f_wall.setRange(0.0, 1.0); self.sp_ground_din_f_wall.setDecimals(3); self.sp_ground_din_f_wall.setSingleStep(0.05); self.sp_ground_din_f_wall.setValue(float(getattr(cfg.ground, "din_ts_f_wall", 0.50)))
        self.ed_ground_source = QLineEdit(str(getattr(cfg, "ground_source", "")))
        self.ed_ground_source.setPlaceholderText("Quelle Erdreichansatz, optional")
        self.ed_ground_din_source = QLineEdit(str(getattr(cfg.ground, "din_ts_source", "")))
        self.ed_ground_din_source.setPlaceholderText("Quelle DIN/TS-Ersatzfaktoren, optional")
        self.ed_ground_norm_inputs = QLineEdit(str(getattr(cfg, "ground_norm_inputs", "")))
        self.ed_ground_norm_inputs.setPlaceholderText("Bodenleitfähigkeit, Perimeter/B', Einbindetiefe, Randdämmung")
        f6a = self._make_form([
            ("Modell", self.cb_ground_mode),
            ("Feste Erdtemperatur [°C]", self.sp_ground_temp),
            ("Quelle Erdreich", self.ed_ground_source),
        ])
        f6b = self._make_form([
            ("f_ground Bodenplatte", self.sp_ground_f_slab),
            ("f_ground Kellerwand", self.sp_ground_f_wall),
            ("ψ Perimeter [W/mK]", self.sp_ground_psi),
            ("DIN/TS f Bodenplatte", self.sp_ground_din_f_slab),
            ("DIN/TS f Kellerwand", self.sp_ground_din_f_wall),
            ("Quelle DIN/TS-Faktoren", self.ed_ground_din_source),
            ("DIN/TS-Zwischenwerte", self.ed_ground_norm_inputs),
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
        self.sp_attic_ridge_height = QDoubleSpinBox(); self.sp_attic_ridge_height.setRange(0.0, 50.0); self.sp_attic_ridge_height.setDecimals(2); self.sp_attic_ridge_height.setSpecialValueText("auto"); self.sp_attic_ridge_height.setValue(float(getattr(cfg.attic, "ridge_height_m", 0.0) or 0.0))
        self.cb_attic_pult_side = QComboBox(); self.cb_attic_pult_side.addItems(["links ansteigend", "rechts ansteigend"]); self.cb_attic_pult_side.setCurrentText("links ansteigend" if str(getattr(cfg.attic, "pult_rise_side", "right") or "right").strip().lower() == "left" else "rechts ansteigend")
        self.sp_attic_half_hip = QDoubleSpinBox(); self.sp_attic_half_hip.setRange(0.05, 0.95); self.sp_attic_half_hip.setDecimals(2); self.sp_attic_half_hip.setSingleStep(0.05); self.sp_attic_half_hip.setValue(float(getattr(cfg.attic, "half_hip_ratio", 0.45)))
        self.cb_attic_dormer_type = QComboBox(); self.cb_attic_dormer_type.addItems(["keine", "Schleppgaube", "Satteldachgaube", "Flachdachgaube", "Spitzgaube"]); self.cb_attic_dormer_type.setCurrentText({"none":"keine","schleppgaube":"Schleppgaube","satteldachgaube":"Satteldachgaube","flachdachgaube":"Flachdachgaube","spitzgaube":"Spitzgaube"}.get(str(getattr(cfg.attic, "dormer_type", "none") or "none").strip().lower(), "keine"))
        self.sp_attic_dormer_width = QDoubleSpinBox(); self.sp_attic_dormer_width.setRange(0.5, 8.0); self.sp_attic_dormer_width.setDecimals(2); self.sp_attic_dormer_width.setValue(float(getattr(cfg.attic, "dormer_width_m", 1.80)))
        self.sp_attic_dormer_height = QDoubleSpinBox(); self.sp_attic_dormer_height.setRange(0.3, 4.0); self.sp_attic_dormer_height.setDecimals(2); self.sp_attic_dormer_height.setValue(float(getattr(cfg.attic, "dormer_height_m", 1.20)))
        self.sp_attic_dormer_offset = QDoubleSpinBox(); self.sp_attic_dormer_offset.setRange(-0.80, 0.80); self.sp_attic_dormer_offset.setDecimals(2); self.sp_attic_dormer_offset.setSingleStep(0.05); self.sp_attic_dormer_offset.setValue(float(getattr(cfg.attic, "dormer_offset_ratio", 0.0)))
        self.sp_attic_roof_window_count = QDoubleSpinBox(); self.sp_attic_roof_window_count.setRange(0, 8); self.sp_attic_roof_window_count.setDecimals(0); self.sp_attic_roof_window_count.setValue(float(getattr(cfg.attic, "roof_window_count", 0)))
        self.sp_attic_roof_window_width = QDoubleSpinBox(); self.sp_attic_roof_window_width.setRange(0.3, 2.5); self.sp_attic_roof_window_width.setDecimals(2); self.sp_attic_roof_window_width.setValue(float(getattr(cfg.attic, "roof_window_width_m", 0.78)))
        self.sp_attic_roof_window_height = QDoubleSpinBox(); self.sp_attic_roof_window_height.setRange(0.4, 2.5); self.sp_attic_roof_window_height.setDecimals(2); self.sp_attic_roof_window_height.setValue(float(getattr(cfg.attic, "roof_window_height_m", 1.18)))
        self.cb_attic_roof_window_side = QComboBox(); self.cb_attic_roof_window_side.addItems(["links", "rechts", "beidseitig"]); self.cb_attic_roof_window_side.setCurrentText({"left":"links","right":"rechts","both":"beidseitig"}.get(str(getattr(cfg.attic, "roof_window_side", "right") or "right").strip().lower(), "rechts"))
        self.sp_attic_pitch = QDoubleSpinBox(); self.sp_attic_pitch.setRange(0.0, 85.0); self.sp_attic_pitch.setDecimals(1); self.sp_attic_pitch.setValue(float(getattr(cfg.attic, "roof_pitch_deg", 35.0)))
        self.cb_attic_roof_boundary = QComboBox(); self.cb_attic_roof_boundary.addItems(["Außenluft", "Dachboden/Abseite unbeheizt"]); self.cb_attic_roof_boundary.setCurrentText("Dachboden/Abseite unbeheizt" if str(getattr(cfg.attic, "roof_boundary", "outside") or "outside").strip().lower() == "unheated_attic" else "Außenluft")
        self.sp_attic_roof_unheated_factor = QDoubleSpinBox(); self.sp_attic_roof_unheated_factor.setRange(0.0, 1.0); self.sp_attic_roof_unheated_factor.setDecimals(2); self.sp_attic_roof_unheated_factor.setSingleStep(0.05); self.sp_attic_roof_unheated_factor.setValue(float(getattr(cfg.attic, "roof_unheated_factor", 0.80)))
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
            ("Firsthöhe gesamt [m]", self.sp_attic_ridge_height),
            ("Pultdach Neigungsrichtung", self.cb_attic_pult_side),
            ("Krüppelwalm-Anteil [0..1]", self.sp_attic_half_hip),
            ("Dachfenster Anzahl", self.sp_attic_roof_window_count),
            ("Dachfenster Breite [m]", self.sp_attic_roof_window_width),
            ("Dachfenster Höhe [m]", self.sp_attic_roof_window_height),
            ("Dachfenster Seite", self.cb_attic_roof_window_side),
            ("Dachneigung [°]", self.sp_attic_pitch),
            ("Dach grenzt an", self.cb_attic_roof_boundary),
            ("Faktor unbeheizt [-]", self.sp_attic_roof_unheated_factor),
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
        self.lbl_attic_balance = QLabel("–")
        self.lbl_attic_balance.setWordWrap(True)
        self.lbl_attic_validation = QLabel("–")
        self.lbl_attic_validation.setWordWrap(True)
        self.gb_attic_live = self._group("Live-Bilanz & Prüfung", self._make_form([
            ("Flächenbilanz", self.lbl_attic_balance),
            ("Status", self.lbl_attic_validation),
        ]), "Brutto-/Öffnungsflächen und Plausibilitätsprüfung der DIN-nahen Dach-/Giebelparameter.")
        self.attic_tabs = QTabWidget()
        self.attic_tabs.setObjectName("atticProjectSettingsTabs")
        self.attic_tabs.addTab(self._build_tab([self.gb_attic_geometry]), "Geometrie")
        self.attic_tabs.addTab(self._build_tab([self.gb_attic_dormers]), "Öffnungen")
        self.attic_tabs.addTab(self._build_tab([self.gb_attic_roof_lines]), "Dachlinien")
        self.attic_tabs.addTab(self._build_tab([self.gb_attic_u, self.gb_attic_live]), "Thermik/DIN")
        self.attic_tabs.addTab(self._build_tab([self.gb_attic_materials]), "Darstellung")
        self._add_nav_page("DG Dach", self._build_tab([
            self.gb_attic_activation,
            self.attic_tabs,
        ]))

        self.lbl_norm_check_summary = QLabel("–")
        self.lbl_norm_check_summary.setWordWrap(True)
        self.lst_norm_check = QListWidget()
        self.lst_norm_check.setObjectName("normGuidanceChecklist")
        self.lst_norm_check.setUniformItemSizes(False)
        norm_body = QWidget()
        norm_body_lay = QVBoxLayout(norm_body)
        norm_body_lay.setContentsMargins(6, 6, 6, 6)
        norm_body_lay.setSpacing(8)
        norm_body_lay.addWidget(self.lbl_norm_check_summary)
        norm_body_lay.addWidget(self.lst_norm_check)
        self._add_nav_page("Normprüfung", self._build_tab([
            self._group("DIN-Nachweisführung", norm_body, "Projektweite Prüfliste für Quellen, Annahmen und die wichtigsten DIN-nahen Eingaben vor dem Reporting."),
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
            "Normprüfung": 8,
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
        self.cb_attic_roof_boundary.currentTextChanged.connect(lambda _=None: self._sync_attic_roof_type(self.cb_attic_roof_type.currentText()))
        self.cb_attic_ridge_orientation.currentTextChanged.connect(lambda _=None: (self._refresh_dormer_actions(), self._refresh_roof_line_actions()))
        self._connect_attic_live_updates()
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
        self.btn_apply_norm_profile.clicked.connect(self._apply_norm_profile)
        self._connect_norm_guidance_updates()

        if self.tabs.count():
            self.tabs.setCurrentRow(self.tabs.currentRow() if self.tabs.currentRow() >= 0 else 0)
        self._sync_tb_mode(self.cb_tb_mode.currentText())
        self._sync_ground_mode(self.cb_ground_mode.currentText())
        self._sync_attic_enabled(bool(self.cb_attic_enabled.isChecked()))
        self._refresh_attic_live_status()
        self._sync_attic_roof_type(self.cb_attic_roof_type.currentText())
        self._reload_dormer_list()
        self._sync_roof_line_kind(self.cb_roof_line_kind.currentText())
        self._reload_roof_line_list()
        self._refresh_dormer_actions()
        self._refresh_roof_line_actions()
        self._sync_norm_checklist()

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
        simplified_or_perimeter = mode in {"simplified", "perimeter", "din_ts"}
        self.sp_ground_f_slab.setEnabled(simplified_or_perimeter)
        self.sp_ground_f_wall.setEnabled(simplified_or_perimeter)
        self.sp_ground_psi.setEnabled(mode == "perimeter")
        self.sp_ground_din_f_slab.setEnabled(mode == "din_ts")
        self.sp_ground_din_f_wall.setEnabled(mode == "din_ts")
        self.ed_ground_din_source.setEnabled(mode == "din_ts")
        self._sync_norm_checklist()

    def _apply_norm_profile(self) -> None:
        profile = self.cb_norm_profile.currentText()
        values = {
            "Altbau unsaniert": {
                "aw": 1.400,
                "window": 2.800,
                "door": 2.500,
                "kd": 1.000,
                "eg": 0.800,
                "dg": 0.800,
                "bodenplatte": 1.200,
                "erdwand": 1.200,
                "roof": 1.000,
                "gable": 1.400,
            },
            "Teilsaniert": {
                "aw": 0.600,
                "window": 1.600,
                "door": 1.800,
                "kd": 0.450,
                "eg": 0.350,
                "dg": 0.300,
                "bodenplatte": 0.500,
                "erdwand": 0.600,
                "roof": 0.350,
                "gable": 0.600,
            },
            "Neubau": {
                "aw": 0.240,
                "window": 0.950,
                "door": 1.300,
                "kd": 0.250,
                "eg": 0.220,
                "dg": 0.180,
                "bodenplatte": 0.300,
                "erdwand": 0.350,
                "roof": 0.180,
                "gable": 0.240,
            },
        }.get(profile)
        if not values:
            return
        self.sp_u_aw.setValue(values["aw"])
        self.sp_u_window.setValue(values["window"])
        self.sp_u_door.setValue(values["door"])
        self.sp_u_kd.setValue(values["kd"])
        self.sp_u_eg.setValue(values["eg"])
        self.sp_u_dg.setValue(values["dg"])
        self.sp_u_bodenplatte.setValue(values["bodenplatte"])
        self.sp_u_erdwand.setValue(values["erdwand"])
        self.sp_attic_u_roof.setValue(values["roof"])
        self.sp_attic_u_gable.setValue(values["gable"])
        if not self.ed_u_source.text().strip():
            self.ed_u_source.setText(f"Schnellprofil {profile} (Projektannahme, Nachweis nachtragen)")
        self._sync_norm_checklist()

    def _connect_norm_guidance_updates(self) -> None:
        for widget in [
            self.sp_t_out,
            self.sp_c_air,
            self.sp_min_air_change,
            self.sp_infiltration_air_change,
            self.sp_mech_supply,
            self.sp_mech_exhaust,
            self.sp_hrv,
            self.sp_reheat,
            self.sp_u_aw,
            self.sp_u_window,
            self.sp_u_door,
            self.sp_u_kd,
            self.sp_u_eg,
            self.sp_u_dg,
            self.sp_u_bodenplatte,
            self.sp_u_erdwand,
            self.sp_tb_du,
            self.sp_tb_psi,
            self.sp_tb_p,
            self.sp_ground_f_slab,
            self.sp_ground_f_wall,
            self.sp_ground_din_f_slab,
            self.sp_ground_din_f_wall,
            self.sp_attic_u_roof,
            self.sp_attic_u_gable,
        ]:
            widget.valueChanged.connect(lambda _=None: self._sync_norm_checklist())
        for combo in [
            self.cb_t_out_source,
            self.cb_vent_mode,
            self.cb_tb_mode,
            self.cb_ground_mode,
            self.cb_attic_roof_boundary,
        ]:
            combo.currentTextChanged.connect(lambda _=None: self._sync_norm_checklist())
        for edit in [
            self.ed_norm_edition,
            self.ed_t_out_source_detail,
            self.ed_climate_station,
            self.ed_vent_source,
            self.ed_reheat_source,
            self.ed_reheat_norm_basis,
            self.ed_u_source,
            self.ed_tb_source,
            self.ed_ground_source,
            self.ed_ground_din_source,
            self.ed_ground_norm_inputs,
            self.ed_reviewer_note,
            self.ed_change_log_note,
        ]:
            edit.textChanged.connect(lambda _=None: self._sync_norm_checklist())
        self.cb_reheat_enabled.toggled.connect(lambda _=None: self._sync_norm_checklist())
        self.cb_attic_enabled.toggled.connect(lambda _=None: self._sync_norm_checklist())
        self.cb_proof_export.toggled.connect(lambda _=None: self._sync_norm_checklist())

    def _sync_norm_checklist(self) -> None:
        if not hasattr(self, "lst_norm_check"):
            return

        def has_text(widget: QLineEdit) -> bool:
            return bool(widget.text().strip())

        rows: list[tuple[str, str]] = []

        def add(status: str, label: str, detail: str) -> None:
            rows.append((status, f"[{status}] {label}: {detail}"))

        climate_source_ok = (
            self.cb_t_out_source.currentText() == "din12831"
            or has_text(self.ed_t_out_source_detail)
            or has_text(self.ed_climate_station)
        )
        add(
            "OK" if self.ed_norm_edition.text().strip() and climate_source_ok else "FEHLT",
            "Normausgabe und Außentemperatur",
            "Quelle/Region dokumentiert." if climate_source_ok else "Normausgabe, Klimaregion oder Quellendetail ergänzen.",
        )

        u_values = [
            self.sp_u_aw.value(),
            self.sp_u_window.value(),
            self.sp_u_door.value(),
            self.sp_u_kd.value(),
            self.sp_u_eg.value(),
            self.sp_u_dg.value(),
            self.sp_u_bodenplatte.value(),
            self.sp_u_erdwand.value(),
        ]
        u_ok = all(float(value) > 0.0 for value in u_values)
        if u_ok and has_text(self.ed_u_source):
            add("OK", "U-Werte Außenwand/Fenster/Tür/Decken/Boden", "Kennwerte und Quelle liegen vor.")
        elif u_ok:
            add("FEHLT", "U-Werte Außenwand/Fenster/Tür/Decken/Boden", "Kennwerte vorhanden, Quelle U-Werte fehlt.")
        else:
            add("FEHLT", "U-Werte Außenwand/Fenster/Tür/Decken/Boden", "Alle angesetzten U-Werte müssen größer 0 sein.")

        ground_mode = self.cb_ground_mode.currentText()
        if ground_mode == "din_ts":
            ground_doc_ok = (has_text(self.ed_ground_din_source) or has_text(self.ed_ground_source)) and has_text(self.ed_ground_norm_inputs)
            add(
                "OK" if ground_doc_ok else "FEHLT",
                "Erdreichansatz",
                "DIN/TS-Faktoren und Zwischenwerte sind dokumentiert." if ground_doc_ok else "Quelle und Zwischenwerte wie Bodenleitfähigkeit, Perimeter/B', Einbindetiefe oder Randdämmung ergänzen.",
            )
        elif ground_mode == "none":
            add("PRÜFEN", "Erdreichansatz", "Erdreichverluste sind deaktiviert.")
        else:
            add(
                "OK" if has_text(self.ed_ground_source) else "PRÜFEN",
                "Erdreichansatz",
                "Vereinfachter Ansatz mit Quelle." if has_text(self.ed_ground_source) else "Vereinfachten Ansatz im Report begründen.",
            )

        vent_needs_source = self.cb_vent_mode.currentText() == "mechanical" or self.sp_min_air_change.value() > 0.0 or self.sp_infiltration_air_change.value() > 0.0
        add(
            "OK" if not vent_needs_source or has_text(self.ed_vent_source) else "FEHLT",
            "Lüftung und Infiltration",
            "Volumenstrom-/WRG-Quelle dokumentiert." if has_text(self.ed_vent_source) else "Bei mechanischer Lüftung, WRG oder Mindestluftwechsel Quelle ergänzen.",
        )

        tb_mode = self.cb_tb_mode.currentText()
        if tb_mode == "none":
            add("PRÜFEN", "Wärmebrücken", "Kein Wärmebrückenansatz aktiv; für DIN-Nachweis bewusst begründen.")
        else:
            add(
                "OK" if has_text(self.ed_tb_source) else "FEHLT",
                "Wärmebrücken",
                "Ansatz und Quelle dokumentiert." if has_text(self.ed_tb_source) else "Quelle für ΔU/ψ/Prozentansatz ergänzen.",
            )

        if self.cb_reheat_enabled.isChecked():
            reheat_doc_ok = has_text(self.ed_reheat_source) and has_text(self.ed_reheat_norm_basis)
            add(
                "OK" if reheat_doc_ok else "FEHLT",
                "Aufheizzuschlag",
                "Wiederaufheizansatz mit Norm-/Tabellenbasis dokumentiert." if reheat_doc_ok else "Quelle und Tabellenbasis/Gebäudeschwere/Nutzung ergänzen.",
            )
        else:
            add("OK", "Aufheizzuschlag", "Nicht angesetzt.")

        roof_ok = self.sp_attic_u_roof.value() > 0.0 and self.sp_attic_u_gable.value() > 0.0
        if self.cb_attic_enabled.isChecked():
            add(
                "OK" if roof_ok else "FEHLT",
                "Dach und Giebel",
                "Dach-/Giebel-U-Werte gesetzt; Live-Bilanz prüfen." if roof_ok else "Dach-/Giebel-U-Werte müssen größer 0 sein.",
            )
        else:
            add("PRÜFEN", "Dach und Giebel", "DG-Dachprofil deaktiviert; Dachflächen ggf. manuell prüfen.")

        add(
            "OK" if has_text(self.ed_reviewer_note) else "PRÜFEN",
            "Reporting",
            "Bearbeiter-/Prüfvermerk vorhanden." if has_text(self.ed_reviewer_note) else "Prüfvermerk vor Abgabe ergänzen.",
        )
        add(
            "OK" if has_text(self.ed_change_log_note) else "PRÜFEN",
            "Änderungsprotokoll",
            "Nachweiswert-Änderungen dokumentiert." if has_text(self.ed_change_log_note) else "Änderungen an U-Werten, Klima, Lüftung, Erdreich und Wärmebrücken kurz protokollieren.",
        )
        if self.cb_proof_export.isChecked():
            add("PRÜFEN", "DIN-Prüffassung", "Export wird später nur freigegeben, wenn alle zentralen Tool-Gates grün sind.")

        self.lst_norm_check.clear()
        for _status, text in rows:
            self.lst_norm_check.addItem(text)
        missing = sum(1 for status, _text in rows if status == "FEHLT")
        check = sum(1 for status, _text in rows if status == "PRÜFEN")
        if missing:
            self.lbl_norm_check_summary.setText(f"{missing} fehlende Nachweise, {check} Prüfpunkte. Vor normnahem Reporting bitte ergänzen.")
        elif check:
            self.lbl_norm_check_summary.setText(f"Keine fehlenden Nachweise, {check} Prüfpunkte bleiben fachlich zu bestätigen.")
        else:
            self.lbl_norm_check_summary.setText("Alle projektweiten DIN-Prüfpunkte sind für das Reporting dokumentiert.")

    def _sync_attic_enabled(self, enabled: bool) -> None:
        self.gb_attic_geometry.setEnabled(bool(enabled))
        self.gb_attic_dormers.setEnabled(bool(enabled))
        self.gb_attic_live.setEnabled(bool(enabled))
        self.attic_tabs.setEnabled(bool(enabled))
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
            self.sp_attic_ridge_height,
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
            self.cb_attic_roof_boundary,
            self.sp_attic_roof_unheated_factor,
            self.cb_attic_facade_material,
            self.cb_attic_roof_material,
            self.sp_attic_u_roof,
            self.sp_attic_u_gable,
        ], bool(enabled))
        self._sync_attic_roof_type(self.cb_attic_roof_type.currentText())
        self._refresh_attic_live_status()
        self._sync_norm_checklist()

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
        self.sp_attic_roof_unheated_factor.setEnabled(enabled and self.cb_attic_roof_boundary.currentText() != "Außenluft")
        self._refresh_dormer_actions()
        self._refresh_roof_line_actions()
        self._refresh_attic_live_status()

    def _connect_attic_live_updates(self) -> None:
        widgets = [
            self.sp_attic_width,
            self.sp_attic_length,
            self.sp_attic_knee,
            self.sp_attic_overhang,
            self.sp_attic_eave_overhang,
            self.sp_attic_gable_overhang,
            self.sp_attic_ridge_offset,
            self.sp_attic_ridge_height,
            self.sp_attic_half_hip,
            self.sp_attic_dormer_width,
            self.sp_attic_dormer_height,
            self.sp_attic_dormer_offset,
            self.sp_attic_roof_window_count,
            self.sp_attic_roof_window_width,
            self.sp_attic_roof_window_height,
            self.sp_attic_pitch,
            self.sp_attic_roof_unheated_factor,
        ]
        for widget in widgets:
            widget.valueChanged.connect(lambda _=None: self._refresh_attic_live_status())
        for combo in [
            self.cb_attic_roof_type,
            self.cb_attic_ridge_orientation,
            self.cb_attic_pult_side,
            self.cb_attic_dormer_type,
            self.cb_attic_roof_window_side,
            self.cb_attic_roof_boundary,
        ]:
            combo.currentTextChanged.connect(lambda _=None: self._refresh_attic_live_status())

    def _attic_cfg_from_widgets(self) -> AtticCfgDTO:
        _roof_rev = {"Satteldach": "satteldach", "Pultdach": "pultdach", "Walmdach": "walmdach", "Krüppelwalmdach": "krueppelwalmdach", "Flachdach": "flachdach", "Winkel-/Kehldach": "winkeldach"}
        _dormer_rev = {"keine": "none", "Schleppgaube": "schleppgaube", "Satteldachgaube": "satteldachgaube", "Flachdachgaube": "flachdachgaube", "Spitzgaube": "spitzgaube"}
        return AtticCfgDTO(
            enabled=bool(self.cb_attic_enabled.isChecked()),
            building_width_m=float(self.sp_attic_width.value()),
            building_length_m=float(self.sp_attic_length.value()),
            knee_wall_height_m=float(self.sp_attic_knee.value()),
            roof_type=_roof_rev.get(self.cb_attic_roof_type.currentText(), "satteldach"),
            ridge_orientation="width" if self.cb_attic_ridge_orientation.currentText() == "quer" else "length",
            roof_overhang_m=float(self.sp_attic_overhang.value()),
            eave_overhang_m=float(self.sp_attic_eave_overhang.value()),
            gable_overhang_m=float(self.sp_attic_gable_overhang.value()),
            ridge_offset_ratio=float(self.sp_attic_ridge_offset.value()),
            ridge_height_m=float(self.sp_attic_ridge_height.value()) if float(self.sp_attic_ridge_height.value()) > 0.0 else None,
            pult_rise_side="left" if self.cb_attic_pult_side.currentText() == "links ansteigend" else "right",
            half_hip_ratio=float(self.sp_attic_half_hip.value()),
            dormer_type=_dormer_rev.get(self.cb_attic_dormer_type.currentText(), "none"),
            dormer_width_m=float(self.sp_attic_dormer_width.value()),
            dormer_height_m=float(self.sp_attic_dormer_height.value()),
            dormer_offset_ratio=float(self.sp_attic_dormer_offset.value()),
            dormers=[DormerCfgDTO(**{k: getattr(d, k) for k in DormerCfgDTO.__dataclass_fields__.keys()}) for d in self._dormers],
            roof_window_count=int(round(float(self.sp_attic_roof_window_count.value()))),
            roof_window_width_m=float(self.sp_attic_roof_window_width.value()),
            roof_window_height_m=float(self.sp_attic_roof_window_height.value()),
            roof_window_side={"links": "left", "rechts": "right", "beidseitig": "both"}.get(self.cb_attic_roof_window_side.currentText(), "right"),
            roof_pitch_deg=float(self.sp_attic_pitch.value()),
            roof_boundary="unheated_attic" if self.cb_attic_roof_boundary.currentText() != "Außenluft" else "outside",
            roof_unheated_factor=float(self.sp_attic_roof_unheated_factor.value()),
            roof_lines=[RoofLineCfgDTO(**{k: getattr(line, k) for k in RoofLineCfgDTO.__dataclass_fields__.keys()}) for line in self.roof_line_editor.current_lines()],
        )

    def _refresh_attic_live_status(self) -> None:
        if not hasattr(self, "lbl_attic_balance"):
            return
        if not bool(self.cb_attic_enabled.isChecked()):
            self.lbl_attic_balance.setText("DG-Dachprofil deaktiviert.")
            self.lbl_attic_validation.setText("○ Keine automatische Dach-/Giebelbilanz.")
            return
        try:
            cfg = self._attic_cfg_from_widgets()
            geom = AtticGeometry(
                building_width_m=cfg.building_width_m,
                building_length_m=cfg.building_length_m,
                knee_wall_height_m=cfg.knee_wall_height_m,
                roof_pitch_deg=cfg.roof_pitch_deg,
                ridge_height_m=cfg.ridge_height_m,
                roof_type=cfg.roof_type,
                ridge_orientation=cfg.ridge_orientation,
                roof_overhang_m=cfg.roof_overhang_m,
                eave_overhang_m=cfg.eave_overhang_m,
                gable_overhang_m=cfg.gable_overhang_m,
                ridge_offset_ratio=cfg.ridge_offset_ratio,
                pult_rise_side=cfg.pult_rise_side,
                half_hip_ratio=cfg.half_hip_ratio,
                dormer_type=cfg.dormer_type,
                dormer_width_m=cfg.dormer_width_m,
                dormer_height_m=cfg.dormer_height_m,
                dormer_offset_ratio=cfg.dormer_offset_ratio,
                roof_window_count=cfg.roof_window_count,
                roof_window_width_m=cfg.roof_window_width_m,
                roof_window_height_m=cfg.roof_window_height_m,
                roof_window_side=cfg.roof_window_side,
                roof_lines=tuple((line.kind, line.x1_ratio, line.y1_ratio, line.x2_ratio, line.y2_ratio) for line in cfg.roof_lines),
            )
            roof_window_area = cfg.roof_window_count * cfg.roof_window_width_m * cfg.roof_window_height_m
            try:
                dormer_cutout = dormer_cutout_area_total(build_dormer_results_from_attic_cfg(cfg))
            except Exception:
                dormer_cutout = 0.0
            effective = max(0.0, geom.roof_area_total_m2 - roof_window_area - dormer_cutout)
            self.lbl_attic_balance.setText(
                f"Dach brutto {geom.roof_area_total_m2:.2f} m² · Öffnungen -{roof_window_area + dormer_cutout:.2f} m² · wirksam ca. {effective:.2f} m²"
            )
            warnings: list[str] = []
            if abs(cfg.ridge_offset_ratio) > 1e-9 and cfg.ridge_height_m is None:
                warnings.append("Firstversatz ohne explizite Firsthöhe")
            if cfg.roof_boundary == "unheated_attic":
                warnings.append("Dachboden/Abseite: Faktor prüfen")
            if cfg.roof_window_count > 0 and cfg.roof_window_width_m * cfg.roof_window_height_m <= 0.0:
                warnings.append("Dachfenstermaße prüfen")
            self.lbl_attic_validation.setText("● Hinweis: " + "; ".join(warnings) if warnings else "● Eingaben vollständig für DIN-nahe Dach-/Giebelbilanz.")
        except Exception as exc:
            self.lbl_attic_balance.setText("Bilanz derzeit nicht berechenbar.")
            self.lbl_attic_validation.setText(f"● Prüfen: {exc}")

    def _active_dormer_sides(self) -> tuple[str, ...]:
        return ("front", "back") if self.cb_attic_ridge_orientation.currentText() == "quer" else ("left", "right")

    def _friendly_dormer_label(self, dormer: DormerCfgDTO) -> str:
        tmap = {"schleppgaube": "Schleppgaube", "satteldachgaube": "Satteldachgaube", "flachdachgaube": "Flachdachgaube", "spitzgaube": "Spitzgaube"}
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
        self._refresh_attic_live_status()

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
            dormer_type={"Schleppgaube": "schleppgaube", "Satteldachgaube": "satteldachgaube", "Flachdachgaube": "flachdachgaube", "Spitzgaube": "spitzgaube"}.get(self.cb_attic_dormer_type.currentText(), "schleppgaube"),
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
        self._refresh_attic_live_status()

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
        cfg.norm_edition = self.ed_norm_edition.text().strip()
        cfg.reviewer_note = self.ed_reviewer_note.text().strip()
        cfg.proof_export_enabled = bool(self.cb_proof_export.isChecked())
        cfg.change_log_note = self.ed_change_log_note.text().strip()

        cfg.t_out_c = float(self.sp_t_out.value())
        cfg.t_keller_c = float(self.sp_t_keller.value())
        cfg.t_oben_c = float(self.sp_t_oben.value())
        cfg.t_out_source = self.cb_t_out_source.currentText()
        cfg.t_out_source_detail = self.ed_t_out_source_detail.text().strip()
        cfg.climate_station = self.ed_climate_station.text().strip()
        cfg.climate_altitude_correction = self.ed_climate_altitude.text().strip()

        cfg.thickness_mode = self.cb_thickness.currentText()
        cfg.area_shrink_factor = float(self.sp_shrink.value())
        cfg.floor_area_mode = self.cb_area_mode.currentText()

        cfg.wall_thickness_outer_m = float(self.sp_tw_out.value())
        cfg.wall_thickness_inner_m = float(self.sp_tw_in.value())
        cfg.wall_heat_transfer_coeff_inside_w_m2k = float(self.sp_wall_h_inside.value())
        cfg.wall_heat_transfer_coeff_outside_w_m2k = float(self.sp_wall_h_outside.value())

        cfg.c_air = float(self.sp_c_air.value())
        cfg.ventilation_mode = self.cb_vent_mode.currentText()
        cfg.min_air_change_1ph = float(self.sp_min_air_change.value())
        cfg.infiltration_air_change_1ph = float(self.sp_infiltration_air_change.value())
        cfg.mech_supply_m3h = float(self.sp_mech_supply.value())
        cfg.mech_exhaust_m3h = float(self.sp_mech_exhaust.value())
        cfg.heat_recovery_efficiency = float(self.sp_hrv.value())
        cfg.ventilation_source = self.ed_vent_source.text().strip()
        cfg.reheat_enabled = bool(self.cb_reheat_enabled.isChecked())
        cfg.reheat_power_w_m2 = float(self.sp_reheat.value())
        cfg.reheat_duration_h = float(self.sp_reheat_duration.value())
        cfg.reheat_temp_drop_k = float(self.sp_reheat_drop.value())
        cfg.reheat_capacity_wh_m2k = float(self.sp_reheat_capacity.value())
        cfg.reheat_source = self.ed_reheat_source.text().strip()
        cfg.reheat_norm_basis = self.ed_reheat_norm_basis.text().strip()

        cfg.u_aussenwand_w_m2k = float(self.sp_u_aw.value())
        cfg.u_fenster_w_m2k = float(self.sp_u_window.value())
        cfg.u_tuer_w_m2k = float(self.sp_u_door.value())
        cfg.u_kellerdecke_w_m2k = float(self.sp_u_kd.value())
        cfg.u_eg_geschossdecke_w_m2k = float(self.sp_u_eg.value())
        cfg.u_dg_geschossdecke_w_m2k = float(self.sp_u_dg.value())
        cfg.u_bodenplatte_w_m2k = float(self.sp_u_bodenplatte.value())
        cfg.u_erdberuehrte_wand_w_m2k = float(self.sp_u_erdwand.value())
        cfg.u_value_source = self.ed_u_source.text().strip()
        cfg.auto_deck_assumptions_confirmed = bool(self.cb_auto_deck_confirmed.isChecked())
        cfg.auto_deck_boundary_source = self.ed_auto_deck_boundary_source.text().strip()
        cfg.auto_deck_create_eg_kellerdecke = bool(self.cb_auto_deck_eg_keller.isChecked())
        cfg.auto_deck_create_eg_geschossdecke = bool(self.cb_auto_deck_eg_deck.isChecked())
        cfg.auto_deck_create_dg_speicherdecke = bool(self.cb_auto_deck_dg_attic.isChecked())

        cfg.tb.mode = self.cb_tb_mode.currentText()
        cfg.tb.delta_u_w_m2k = float(self.sp_tb_du.value())
        cfg.tb.psi_default_w_mk = float(self.sp_tb_psi.value())
        cfg.tb.percent_of_trans = float(self.sp_tb_p.value())
        cfg.tb.use_element_meta_psi = bool(self.cb_tb_meta.isChecked())
        cfg.tb.include_out = bool(self.cb_tb_out.isChecked())
        cfg.tb.include_keller = bool(self.cb_tb_k.isChecked())
        cfg.tb.include_oben = bool(self.cb_tb_o.isChecked())
        cfg.thermal_bridge_source = self.ed_tb_source.text().strip()

        cfg.ground.mode = self.cb_ground_mode.currentText()
        cfg.ground.ground_temp_c = float(self.sp_ground_temp.value())
        cfg.ground.f_slab = float(self.sp_ground_f_slab.value())
        cfg.ground.f_wall = float(self.sp_ground_f_wall.value())
        cfg.ground.psi_perimeter_w_mk = float(self.sp_ground_psi.value())
        cfg.ground.din_ts_f_slab = float(self.sp_ground_din_f_slab.value())
        cfg.ground.din_ts_f_wall = float(self.sp_ground_din_f_wall.value())
        cfg.ground.din_ts_source = self.ed_ground_din_source.text().strip()
        cfg.ground_source = self.ed_ground_source.text().strip()
        cfg.ground_norm_inputs = self.ed_ground_norm_inputs.text().strip()

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
        cfg.attic.ridge_height_m = float(self.sp_attic_ridge_height.value()) if float(self.sp_attic_ridge_height.value()) > 0.0 else None
        cfg.attic.pult_rise_side = "left" if self.cb_attic_pult_side.currentText() == "links ansteigend" else "right"
        cfg.attic.half_hip_ratio = float(self.sp_attic_half_hip.value())
        _dormer_rev = {"keine": "none", "Schleppgaube": "schleppgaube", "Satteldachgaube": "satteldachgaube", "Flachdachgaube": "flachdachgaube", "Spitzgaube": "spitzgaube"}
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
        cfg.attic.roof_boundary = "unheated_attic" if self.cb_attic_roof_boundary.currentText() != "Außenluft" else "outside"
        cfg.attic.roof_unheated_factor = float(self.sp_attic_roof_unheated_factor.value())
        _facade_rev = {"Klinker": "klinker", "Putz": "putz", "Holz": "holz", "Beton": "beton"}
        cfg.attic.facade_material = _facade_rev.get(self.cb_attic_facade_material.currentText(), "klinker")
        _roof_material_rev = {"Ziegel": "ziegel"}
        cfg.attic.roof_material = _roof_material_rev.get(self.cb_attic_roof_material.currentText(), "ziegel")
        cfg.attic.u_roof_w_m2k = float(self.sp_attic_u_roof.value())
        cfg.attic.u_gable_w_m2k = float(self.sp_attic_u_gable.value())
