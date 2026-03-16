from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..core.attic_geometry import AtticGeometry


class AtticSketchWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._geom: AtticGeometry | None = None
        self.setMinimumHeight(220)
        self.setMinimumWidth(260)

    def set_geometry(self, geom: AtticGeometry | None) -> None:
        self._geom = geom
        self.update()

    def _cross_section_points(self, g: AtticGeometry) -> list[tuple[float, float]]:
        return g.cross_section_points()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(12, 12, -12, -12)
        painter.fillRect(self.rect(), self.palette().base())
        if self._geom is None:
            painter.setPen(QPen(self.palette().mid().color(), 1.2, Qt.DashLine))
            painter.drawRoundedRect(rect, 12, 12)
            painter.setPen(self.palette().text().color())
            painter.drawText(rect, Qt.AlignCenter, "Kein DG-Dachprofil aktiv")
            return

        g = self._geom
        draw = QRectF(rect.left(), rect.top() + 18, rect.width() * 0.70, rect.height() - 36)
        plan = QRectF(draw.right() + 10, rect.top() + 24, rect.right() - draw.right() - 10, max(90.0, rect.height() * 0.50))
        cross_span = float(g.cross_span_m)
        scale = min(draw.width() / max(cross_span, 1e-9), draw.height() / max(g.total_height_m, 1e-9))
        base_x = draw.left() + (draw.width() - cross_span * scale) / 2.0
        base_y = draw.bottom()

        def px(x_m: float, y_m: float) -> QPointF:
            return QPointF(base_x + x_m * scale, base_y - y_m * scale)

        pts = self._cross_section_points(g)
        path = QPainterPath()
        path.moveTo(px(*pts[0]))
        for x, y in pts[1:]:
            path.lineTo(px(x, y))
        path.closeSubpath()

        painter.setPen(QPen(QColor("#1f2937"), 2.0))
        painter.setBrush(QColor("#fff7ed"))
        painter.drawPath(path)

        roof_type = str(getattr(g, "roof_type", "satteldach") or "satteldach").strip().lower()
        painter.setPen(QPen(QColor("#b45309"), 2.5))
        roof_poly = g.cross_section_points()
        for (x0, y0), (x1, y1) in zip(roof_poly[1:-1], roof_poly[2:]):
            painter.drawLine(px(x0, y0), px(x1, y1))
        if roof_type == "walmdach":
            painter.setPen(QPen(QColor("#92400e"), 1.4, Qt.DashLine))
            painter.drawLine(px(g.ridge_pos_m, g.total_height_m), px(g.ridge_pos_m, max(0.0, g.knee_wall_height_m - 0.35)))

        painter.setPen(QPen(QColor("#2563eb"), 2.5))
        painter.drawLine(px(roof_poly[0][0], roof_poly[0][1]), px(roof_poly[1][0], roof_poly[1][1]))
        painter.drawLine(px(roof_poly[-1][0], roof_poly[-1][1]), px(roof_poly[-2][0], roof_poly[-2][1]))
        painter.setPen(QPen(QColor("#111827"), 2.2))
        painter.drawLine(px(0.0, 0.0), px(cross_span, 0.0))

        painter.setPen(QPen(QColor("#6b7280"), 1.1, Qt.DashLine))
        for hh, txt in ((1.0, "1.0 m"), (2.0, "2.0 m")):
            if hh >= g.total_height_m:
                continue
            x0 = g.slope_offset_x_m(hh)
            x1 = x0 + g.clear_width_at_height_m(hh)
            p0 = px(x0, hh)
            p1 = px(x1, hh)
            painter.drawLine(p0, p1)
            painter.drawText(p1 + QPointF(8, 4), txt)

        # Mini-Planansicht für Firstrichtung + Überstand
        painter.setPen(QPen(QColor("#9ca3af"), 1.0))
        painter.setBrush(QColor("#f9fafb"))
        painter.drawRoundedRect(plan, 10, 10)
        ov = float(getattr(g, "roof_overhang_m", 0.0) or 0.0)
        pw = max(10.0, plan.width() - 22.0)
        ph = max(10.0, plan.height() - 30.0)
        sx = pw / max(g.building_width_m + 2.0 * ov, 1e-9)
        sy = ph / max(g.building_length_m + 2.0 * ov, 1e-9)
        s = min(sx, sy)
        bx = plan.left() + (plan.width() - (g.building_width_m + 2.0 * ov) * s) / 2.0
        by = plan.bottom() - 10.0

        def pl(xm: float, ym: float) -> QPointF:
            return QPointF(bx + xm * s, by - ym * s)

        outer = QRectF(pl(0.0, g.building_length_m + 2.0 * ov), pl(g.building_width_m + 2.0 * ov, 0.0)).normalized()
        inner = QRectF(pl(ov, ov + g.building_length_m), pl(ov + g.building_width_m, ov)).normalized()
        painter.setBrush(QColor("#ede9fe"))
        painter.drawRoundedRect(outer, 8, 8)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#475569"), 1.3))
        painter.drawRoundedRect(inner, 6, 6)

        ridge_line = g.plan_ridge_or_slope_line()
        if len(ridge_line) == 2:
            painter.setPen(QPen(QColor("#dc2626"), 2.0, Qt.DashLine))
            painter.drawLine(pl(*ridge_line[0]), pl(*ridge_line[1]))
        hip_lines = g.plan_hip_lines()
        if hip_lines:
            painter.setPen(QPen(QColor("#92400e"), 1.4, Qt.DashLine))
            for line in hip_lines:
                if len(line) == 2:
                    painter.drawLine(pl(*line[0]), pl(*line[1]))

        painter.setPen(self.palette().text().color())
        f = QFont(self.font())
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(QRectF(rect.left(), rect.top() - 4, rect.width(), 18), Qt.AlignHCenter | Qt.AlignVCenter, "DG-/Giebel-Querschnitt / Dachvorschau")
        painter.setFont(QFont(self.font()))
        painter.drawText(plan.adjusted(8, 6, -8, -6), Qt.AlignTop | Qt.AlignHCenter, "Dachplan")


class AtticSketchPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self.info_label = QLabel("Kein Dachprofil aktiv")
        self.info_label.setWordWrap(True)
        self.sketch = AtticSketchWidget(self)
        lay.addWidget(self.info_label)
        lay.addWidget(self.sketch, 1)

    def set_geometry(self, geom: AtticGeometry | None) -> None:
        self.sketch.set_geometry(geom)
        if geom is None:
            self.info_label.setText("Kein DG-Dachprofil aktiv")
            return
        roof_type = str(getattr(geom, "roof_type", "satteldach") or "satteldach").strip().lower()
        roof_name = {"satteldach": "Satteldach", "pultdach": "Pultdach", "walmdach": "Walmdach", "flachdach": "Flachdach"}.get(roof_type, "Satteldach")
        ridge_dir = {"length": "längs", "width": "quer"}.get(str(getattr(geom, "ridge_orientation", "length") or "length").strip().lower(), "längs")
        pult_dir = {"left": "links ansteigend", "right": "rechts ansteigend"}.get(str(getattr(geom, "pult_rise_side", "right") or "right").strip().lower(), "rechts ansteigend")
        asym = float(getattr(geom, "ridge_offset_ratio", 0.0) or 0.0)
        self.info_label.setText(
            f"B={geom.building_width_m:.2f} m · L={geom.building_length_m:.2f} m · "
            f"Kniestock={geom.knee_wall_height_m:.2f} m · Dachform={roof_name} · α={geom.roof_pitch_deg:.1f}°\n"
            f"Firstrichtung={ridge_dir} · Überstand={float(getattr(geom, 'roof_overhang_m', 0.0) or 0.0):.2f} m"
            f"{' · asym. Firstversatz=' + f'{asym:.2f}' if roof_type in ('satteldach', 'walmdach') and abs(asym) > 1e-9 else ''}"
            f"{' · Pult=' + pult_dir if roof_type == 'pultdach' else ''}\n"
            f"Dachfläche={geom.roof_area_total_m2:.2f} m² · Giebel={geom.gable_area_total_m2:.2f} m² je Stirnseite · "
            f"gew. DG-Fläche={geom.weighted_floor_area_m2():.2f} m²"
        )
