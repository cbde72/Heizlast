from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..core.attic_geometry import AtticGeometry


class AtticSketchWidget(QWidget):
    planClicked = Signal(dict)
    dormerDrawFinished = Signal(dict)
    dormerDragStarted = Signal(dict)
    dormerDragMoved = Signal(dict)
    dormerDragFinished = Signal(dict)
    dormerResizeStarted = Signal(dict)
    dormerResizeMoved = Signal(dict)
    dormerResizeFinished = Signal(dict)
    roofProfileChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._geom: AtticGeometry | None = None
        self._last_plan_meta: dict | None = None
        self._last_cross_meta: dict | None = None
        self._profile_adjust_mode_active = False
        self._profile_drag_active = False
        self._profile_drag_kind = "pitch"
        self._placement_mode_active = False
        self._draw_mode_active = False
        self._draw_start_payload: dict | None = None
        self._draw_current_payload: dict | None = None
        self._placement_has_selection = False
        self._placement_dormer_width_m = 1.80
        self._placement_min_edge_clearance_m = 0.40
        self._hover_plan_payload: dict | None = None
        self._selected_dormer_payload: dict | None = None
        self._selected_roof_side_payload: dict | None = None
        self._drag_active = False
        self._drag_started = False
        self._drag_payload: dict | None = None
        self._drag_press_pos: QPointF | None = None
        self._resize_active = False
        self._resize_started = False
        self._resize_mode: str | None = None
        self._resize_payload: dict | None = None
        self._resize_press_pos: QPointF | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(220)
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_dormer_preview_state(self, active: bool, *, has_selection: bool = False, dormer_width_m: float = 1.80, min_edge_clearance_m: float = 0.40, draw_mode: bool = False) -> None:
        self._placement_mode_active = bool(active)
        self._draw_mode_active = bool(draw_mode)
        self._placement_has_selection = bool(has_selection)
        self._placement_dormer_width_m = max(0.30, float(dormer_width_m or 1.80))
        self._placement_min_edge_clearance_m = max(0.0, float(min_edge_clearance_m or 0.0))
        if not self._placement_mode_active:
            self._hover_plan_payload = None
        if not self._draw_mode_active:
            self._draw_start_payload = None
            self._draw_current_payload = None
        self.update()

    def set_selected_dormer_state(self, payload: dict | None) -> None:
        self._selected_dormer_payload = dict(payload or {}) if payload else None
        if not self._selected_dormer_payload:
            self._drag_active = False
            self._drag_started = False
            self._drag_payload = None
            self._drag_press_pos = None
            self._resize_active = False
            self._resize_started = False
            self._resize_mode = None
            self._resize_payload = None
            self._resize_press_pos = None
        self.update()

    def set_selected_roof_side_state(self, payload: dict | None) -> None:
        self._selected_roof_side_payload = dict(payload or {}) if payload else None
        self.update()

    def set_roof_profile_adjust_state(self, active: bool) -> None:
        self._profile_adjust_mode_active = bool(active)
        if not self._profile_adjust_mode_active:
            self._profile_drag_active = False
        self.update()

    def set_geometry(self, geom: AtticGeometry | None) -> None:
        self._geom = geom
        self.update()

    def _cross_section_points(self, g: AtticGeometry) -> list[tuple[float, float]]:
        return g.cross_section_points()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(12, 12, -12, -12)
        if rect.width() <= 0 or rect.height() <= 0:
            return
        painter.fillRect(self.rect(), self.palette().base())

        if self._geom is None:
            self._last_plan_meta = None
            painter.setPen(QPen(self.palette().mid().color(), 1.2, Qt.DashLine))
            painter.drawRoundedRect(rect, 12, 12)
            painter.setPen(self.palette().text().color())
            painter.drawText(rect, Qt.AlignCenter, "Kein DG-Dachprofil aktiv")
            return

        g = self._geom
        if rect.width() < 720:
            header_h = 18.0
            gap = 12.0
            available_h = max(120.0, rect.height() - header_h - gap)
            plan_h = max(80.0, available_h * 0.42)
            draw_h = max(80.0, available_h - plan_h)
            draw = QRectF(rect.left(), rect.top() + header_h, rect.width(), draw_h)
            plan = QRectF(rect.left(), draw.bottom() + gap, rect.width(), max(80.0, rect.bottom() - draw.bottom() - gap))
        else:
            draw_w = max(320.0, rect.width() * 0.62)
            draw = QRectF(rect.left(), rect.top() + 18, draw_w, rect.height() - 36)
            plan = QRectF(draw.right() + 12, rect.top() + 24, max(180.0, rect.right() - draw.right() - 12), max(120.0, rect.height() * 0.56))
        cross_span = float(g.cross_span_m)
        scale = min(draw.width() / max(cross_span, 1e-9), draw.height() / max(g.total_height_m, 1e-9))
        base_x = draw.left() + (draw.width() - cross_span * scale) / 2.0
        base_y = draw.bottom()
        self._last_cross_meta = {
            "draw_rect": QRectF(draw),
            "base_x": float(base_x),
            "base_y": float(base_y),
            "scale": float(scale),
            "cross_span_m": float(cross_span),
        }

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

        if self._profile_adjust_mode_active:
            painter.setPen(QPen(QColor("#0f766e"), 1.8, Qt.DashLine))
            painter.setBrush(QColor(20, 184, 166, 34))
            painter.drawRoundedRect(draw.adjusted(2.0, 2.0, -2.0, -2.0), 10, 10)
            ridge_handle = px(float(getattr(g, "ridge_pos_m", cross_span / 2.0)), float(getattr(g, "total_height_m", 0.0)))
            left_knee = px(0.0, float(getattr(g, "knee_wall_height_m", 0.0)))
            right_knee = px(cross_span, float(getattr(g, "knee_wall_height_m", 0.0)))
            painter.setPen(QPen(QColor("#047857"), 1.6))
            painter.setBrush(QColor("#d1fae5"))
            for handle in (ridge_handle, left_knee, right_knee):
                painter.drawEllipse(handle, 6.0, 6.0)
            painter.setPen(QPen(QColor("#064e3b"), 1.0))
            painter.drawText(draw.adjusted(8.0, 8.0, -8.0, -8.0), Qt.AlignTop | Qt.AlignLeft, "Schrägen-Modus: First ziehen = Neigung, Kniestockpunkte ziehen = Kniestock")

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

        outer_rect = g.plan_outer_rect()
        inner_rect = g.plan_inner_rect()
        outer = QRectF(pl(outer_rect[0], outer_rect[3]), pl(outer_rect[2], outer_rect[1])).normalized()
        inner = QRectF(pl(inner_rect[0], inner_rect[3]), pl(inner_rect[2], inner_rect[1])).normalized()
        self._last_plan_meta = {
            "plan_rect": QRectF(plan),
            "inner_rect": tuple(float(v) for v in inner_rect),
            "outer_rect": tuple(float(v) for v in outer_rect),
            "bx": float(bx),
            "by": float(by),
            "scale": float(s),
            "ridge_orientation": str(getattr(g, "ridge_orientation", "length") or "length").strip().lower(),
            "building_width_m": float(getattr(g, "building_width_m", 0.0) or 0.0),
            "building_length_m": float(getattr(g, "building_length_m", 0.0) or 0.0),
        }

        painter.setBrush(QColor("#ede9fe"))
        painter.drawRoundedRect(outer, 8, 8)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#475569"), 1.3))
        painter.drawRoundedRect(inner, 6, 6)
        self._draw_plan_measurements(painter, plan, inner_rect, pl, g)

        facets = g.roof_facets()
        if facets:
            painter.setPen(QPen(QColor("#cbd5e1"), 1.0))
            for idx, facet in enumerate(facets):
                facet_path = QPainterPath()
                facet_pts = list(getattr(facet, "polygon_m", ()) or ())
                if len(facet_pts) < 3:
                    continue
                facet_path.moveTo(pl(*facet_pts[0]))
                for pt in facet_pts[1:]:
                    facet_path.lineTo(pl(*pt))
                facet_path.closeSubpath()
                painter.setBrush(QColor("#e0e7ff" if idx % 2 == 0 else "#ede9fe"))
                painter.drawPath(facet_path)

        ridge_line = g.plan_ridge_or_slope_line()
        if ridge_line:
            painter.setPen(QPen(QColor("#7c3aed"), 1.8, Qt.DashLine))
            try:
                # expected format: ((x0, y0), (x1, y1))
                (x0, y0), (x1, y1) = ridge_line
                painter.drawLine(pl(float(x0), float(y0)), pl(float(x1), float(y1)))
            except Exception:
                # fallback for flat sequence format [x0, y0, x1, y1]
                try:
                    x0, y0, x1, y1 = ridge_line
                    painter.drawLine(pl(float(x0), float(y0)), pl(float(x1), float(y1)))
                except Exception:
                    pass

        selected_rect = self._build_selected_dormer_rect()
        if selected_rect is not None:
            painter.setPen(QPen(QColor("#1d4ed8"), 2.0))
            painter.setBrush(QColor(59, 130, 246, 48))
            painter.drawRoundedRect(selected_rect, 5, 5)
            for key, handle_rect in self._build_selected_dormer_handle_rects().items():
                painter.setPen(QPen(QColor("#1e3a8a"), 1.2))
                painter.setBrush(QColor("#ffffff"))
                painter.drawRect(handle_rect)

        selected_side_rect = None
        if self._selected_roof_side_payload:
            selected_side_rect = self._build_hover_side_highlight_rect(self._selected_roof_side_payload)
        if selected_side_rect is not None:
            painter.setPen(QPen(QColor("#2563eb"), 1.8, Qt.DashLine))
            painter.setBrush(QColor(37, 99, 235, 34))
            painter.drawRoundedRect(selected_side_rect, 6, 6)

        hover_payload = self._drag_payload if self._drag_active and self._drag_payload is not None else self._hover_plan_payload
        if (self._placement_mode_active or self._drag_active) and hover_payload is not None:
            preview = self._build_hover_preview_rect(hover_payload)
            side_rect = self._build_hover_side_highlight_rect(hover_payload)
            if side_rect is not None:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(14, 165, 233, 28))
                painter.drawRoundedRect(side_rect, 6, 6)
            if preview is not None:
                painter.setPen(QPen(QColor("#0f766e"), 2.0, Qt.DashLine))
                painter.setBrush(QColor(20, 184, 166, 70))
                painter.drawRoundedRect(preview, 5, 5)
            hp = pl(float(hover_payload.get("x_m", 0.0) or 0.0), float(hover_payload.get("y_m", 0.0) or 0.0))
            painter.setPen(QPen(QColor("#0284c7"), 1.6, Qt.DashLine))
            painter.drawLine(QPointF(plan.left() + 8.0, hp.y()), QPointF(plan.right() - 8.0, hp.y()))
            painter.drawLine(QPointF(hp.x(), plan.top() + 18.0), QPointF(hp.x(), plan.bottom() - 8.0))
            painter.setPen(QPen(QColor("#0369a1"), 1.6))
            painter.setBrush(QColor("#e0f2fe"))
            painter.drawEllipse(hp, 4.0, 4.0)
            badge = QRectF(plan.left() + 10.0, plan.bottom() - 28.0, min(240.0, plan.width() - 20.0), 20.0)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 220))
            painter.drawRoundedRect(badge, 8, 8)
            painter.setPen(QPen(QColor("#0f172a"), 1.0))
            label = "Gaube ziehen" if self._drag_active else ("Gaube verschieben" if self._placement_has_selection else "Gaube einfügen")
            painter.drawText(
                badge.adjusted(8, 0, -8, 0),
                Qt.AlignVCenter | Qt.AlignLeft,
                f"{label}: {str(hover_payload.get('side', '–'))} · {float(hover_payload.get('along_m', 0.0) or 0.0):.2f} m",
            )
        elif self._placement_mode_active:
            painter.setPen(QPen(QColor("#0284c7"), 1.2, Qt.DashLine))
            painter.drawRoundedRect(inner.adjusted(-2.0, -2.0, 2.0, 2.0), 8, 8)
            painter.setPen(QPen(QColor("#075985"), 1.0))
            painter.drawText(
                QRectF(plan.left() + 8.0, plan.bottom() - 28.0, plan.width() - 16.0, 20.0),
                Qt.AlignLeft | Qt.AlignVCenter,
                "Platzierungsmodus: Maus im Dachplan bewegen und klicken",
            )

        painter.setPen(self.palette().text().color())
        f = QFont(self.font())
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(QRectF(rect.left(), rect.top() - 4, rect.width(), 18), Qt.AlignHCenter | Qt.AlignVCenter, "DG-/Giebel-Querschnitt / Dachvorschau")
        painter.setFont(QFont(self.font()))
        painter.drawText(plan.adjusted(8, 6, -8, -6), Qt.AlignTop | Qt.AlignHCenter, "Dachplan")

    def _draw_plan_measurements(self, painter: QPainter, plan: QRectF, inner_rect_m: tuple[float, float, float, float], pl, g: AtticGeometry) -> None:
        x0, y0, x1, y1 = (float(v) for v in inner_rect_m)
        p_bl = pl(x0, y0)
        p_br = pl(x1, y0)
        p_tl = pl(x0, y1)
        painter.save()
        painter.setPen(QPen(QColor("#64748b"), 1.0, Qt.DashLine))
        font = QFont(self.font())
        font.setPointSize(max(7, font.pointSize() - 1))
        painter.setFont(font)

        y_dim = min(plan.bottom() - 34.0, p_bl.y() + 16.0)
        x_dim = max(plan.left() + 8.0, p_tl.x() - 18.0)
        painter.drawLine(QPointF(p_bl.x(), y_dim), QPointF(p_br.x(), y_dim))
        painter.drawLine(QPointF(p_bl.x(), y_dim - 4.0), QPointF(p_bl.x(), y_dim + 4.0))
        painter.drawLine(QPointF(p_br.x(), y_dim - 4.0), QPointF(p_br.x(), y_dim + 4.0))
        painter.drawText(QRectF(p_bl.x(), y_dim + 2.0, max(20.0, p_br.x() - p_bl.x()), 14.0), Qt.AlignCenter, f"B {float(getattr(g, 'building_width_m', x1 - x0) or (x1 - x0)):.2f} m")

        painter.drawLine(QPointF(x_dim, p_tl.y()), QPointF(x_dim, p_bl.y()))
        painter.drawLine(QPointF(x_dim - 4.0, p_tl.y()), QPointF(x_dim + 4.0, p_tl.y()))
        painter.drawLine(QPointF(x_dim - 4.0, p_bl.y()), QPointF(x_dim + 4.0, p_bl.y()))
        painter.drawText(QRectF(x_dim - 58.0, (p_tl.y() + p_bl.y()) * 0.5 - 8.0, 52.0, 16.0), Qt.AlignRight | Qt.AlignVCenter, f"L {float(getattr(g, 'building_length_m', y1 - y0) or (y1 - y0)):.2f} m")

        ov = float(getattr(g, "roof_overhang_m", 0.0) or 0.0)
        if ov > 0.0:
            painter.setPen(QPen(QColor("#94a3b8"), 1.0, Qt.DotLine))
            painter.drawText(QRectF(plan.left() + 8.0, plan.top() + 22.0, min(150.0, plan.width() - 16.0), 16.0), Qt.AlignLeft | Qt.AlignVCenter, f"Überstand {ov:.2f} m")

        dormer_rect = self._build_selected_dormer_rect()
        if dormer_rect is not None and self._selected_dormer_payload:
            painter.setPen(QPen(QColor("#1d4ed8"), 1.0, Qt.DashLine))
            payload = self._selected_dormer_payload
            width_m = float(payload.get("width_m", 0.0) or 0.0)
            depth_m = float(payload.get("depth_m", 0.0) or 0.0)
            painter.drawLine(QPointF(dormer_rect.left(), dormer_rect.top() - 8.0), QPointF(dormer_rect.right(), dormer_rect.top() - 8.0))
            painter.drawText(QRectF(dormer_rect.left(), dormer_rect.top() - 24.0, max(34.0, dormer_rect.width()), 14.0), Qt.AlignCenter, f"{width_m:.2f} m")
            painter.drawLine(QPointF(dormer_rect.right() + 8.0, dormer_rect.top()), QPointF(dormer_rect.right() + 8.0, dormer_rect.bottom()))
            painter.drawText(QRectF(dormer_rect.right() + 10.0, dormer_rect.center().y() - 8.0, 54.0, 16.0), Qt.AlignLeft | Qt.AlignVCenter, f"T {depth_m:.2f} m")
        painter.restore()

    def _build_hover_preview_rect(self, payload: dict) -> QRectF | None:
        meta = self._last_plan_meta or {}
        scale = float(meta.get("scale", 0.0) or 0.0)
        if scale <= 1e-9:
            return None
        inner_rect = tuple(meta.get("inner_rect", (0.0, 0.0, 0.0, 0.0)))
        if len(inner_rect) != 4:
            return None
        x0, y0, x1, y1 = (float(v) for v in inner_rect)
        ridge_orientation = str(meta.get("ridge_orientation", "length") or "length").strip().lower()
        side = str((payload or {}).get("side", "right") or "right").strip().lower()
        along = float((payload or {}).get("along_m", 0.0) or 0.0)
        width_m = max(0.30, float((payload or {}).get("width_m", self._placement_dormer_width_m) or self._placement_dormer_width_m or 1.80))
        depth_m = max(0.20, float((payload or {}).get("depth_m", 0.85) or 0.85))
        min_clearance = max(0.0, float((payload or {}).get("min_edge_clearance_m", self._placement_min_edge_clearance_m) or self._placement_min_edge_clearance_m or 0.0))
        span = (x1 - x0) if ridge_orientation == "width" else (y1 - y0)
        half = min(width_m / 2.0, max(0.10, span / 2.0))
        lo = min_clearance + half
        hi = max(lo, span - min_clearance - half)
        along = max(lo, min(hi, along))

        bx = float(meta.get("bx", 0.0) or 0.0)
        by = float(meta.get("by", 0.0) or 0.0)

        def pl(xm: float, ym: float) -> QPointF:
            return QPointF(bx + xm * scale, by - ym * scale)

        max_band = max(0.35, min(x1 - x0, y1 - y0) * 0.45)
        band = max(0.20, min(max_band, depth_m))
        if ridge_orientation == "width":
            yy0 = y0 + max(0.0, along - half)
            yy1 = y0 + min(span, along + half)
            if side == "front":
                xx0, xx1 = x0 + 0.55, min(x1, x0 + 0.55 + band)
            else:
                xx0, xx1 = max(x0, x1 - 0.55 - band), x1 - 0.55
        else:
            xx0 = x0 + max(0.0, along - half)
            xx1 = x0 + min(span, along + half)
            if side == "left":
                yy0, yy1 = y0 + 0.55, min(y1, y0 + 0.55 + band)
            else:
                yy0, yy1 = max(y0, y1 - 0.55 - band), y1 - 0.55
        return QRectF(pl(xx0, yy1), pl(xx1, yy0)).normalized()

    def _build_hover_side_highlight_rect(self, payload: dict) -> QRectF | None:
        meta = self._last_plan_meta or {}
        scale = float(meta.get("scale", 0.0) or 0.0)
        if scale <= 1e-9:
            return None
        inner_rect = tuple(meta.get("inner_rect", (0.0, 0.0, 0.0, 0.0)))
        if len(inner_rect) != 4:
            return None
        x0, y0, x1, y1 = (float(v) for v in inner_rect)
        ridge_orientation = str(meta.get("ridge_orientation", "length") or "length").strip().lower()
        side = str((payload or {}).get("side", "right") or "right").strip().lower()
        bx = float(meta.get("bx", 0.0) or 0.0)
        by = float(meta.get("by", 0.0) or 0.0)

        def pl(xm: float, ym: float) -> QPointF:
            return QPointF(bx + xm * scale, by - ym * scale)

        if ridge_orientation == "width":
            midx = (x0 + x1) / 2.0
            if side == "front":
                return QRectF(pl(x0, y1), pl(midx, y0)).normalized()
            return QRectF(pl(midx, y1), pl(x1, y0)).normalized()
        midy = (y0 + y1) / 2.0
        if side == "left":
            return QRectF(pl(x0, midy), pl(x1, y0)).normalized()
        return QRectF(pl(x0, y1), pl(x1, midy)).normalized()

    def _build_selected_dormer_rect(self) -> QRectF | None:
        payload = self._selected_dormer_payload
        if not payload:
            return None
        previous_width = self._placement_dormer_width_m
        previous_clearance = self._placement_min_edge_clearance_m
        try:
            self._placement_dormer_width_m = max(0.30, float(payload.get("width_m", previous_width) or previous_width))
            self._placement_min_edge_clearance_m = max(0.0, float(payload.get("min_edge_clearance_m", previous_clearance) or previous_clearance))
            return self._build_hover_preview_rect(payload)
        finally:
            self._placement_dormer_width_m = previous_width
            self._placement_min_edge_clearance_m = previous_clearance


    def _build_selected_dormer_handle_rects(self) -> dict[str, QRectF]:
        rect = self._build_selected_dormer_rect()
        if rect is None:
            return {}
        size = 10.0
        half = size / 2.0
        cy = rect.center().y()
        cx = rect.center().x()
        return {
            "left": QRectF(rect.left() - half, cy - half, size, size),
            "right": QRectF(rect.right() - half, cy - half, size, size),
            "top": QRectF(cx - half, rect.top() - half, size, size),
            "bottom": QRectF(cx - half, rect.bottom() - half, size, size),
        }

    def _hit_selected_dormer_resize_handle(self, payload: dict | None) -> str | None:
        if not payload or not self._selected_dormer_payload:
            return None
        meta = self._last_plan_meta or {}
        scale = float(meta.get("scale", 0.0) or 0.0)
        bx = float(meta.get("bx", 0.0) or 0.0)
        by = float(meta.get("by", 0.0) or 0.0)
        if scale <= 1e-9:
            return None
        pt = QPointF(bx + float(payload.get("x_m", 0.0) or 0.0) * scale, by - float(payload.get("y_m", 0.0) or 0.0) * scale)
        for key, rect in self._build_selected_dormer_handle_rects().items():
            if rect.adjusted(-3.0, -3.0, 3.0, 3.0).contains(pt):
                return key
        return None

    def _build_resize_payload(self, payload: dict | None) -> dict | None:
        base = dict(self._selected_dormer_payload or {})
        if not base or not payload:
            return None
        meta = self._last_plan_meta or {}
        inner_rect = tuple(meta.get("inner_rect", (0.0, 0.0, 0.0, 0.0)))
        if len(inner_rect) != 4:
            return None
        x0, y0, x1, y1 = (float(v) for v in inner_rect)
        ridge_orientation = str((payload or {}).get("ridge_orientation", base.get("ridge_orientation", "length")) or "length").strip().lower()
        side = str(base.get("side", payload.get("side", "right")) or payload.get("side", "right")).strip().lower()
        along = float(base.get("along_m", payload.get("along_m", 0.0)) or 0.0)
        width_m = max(0.30, float(base.get("width_m", 1.80) or 1.80))
        depth_m = max(0.20, float(base.get("depth_m", 1.40) or 1.40))
        x_m = float(payload.get("x_m", 0.0) or 0.0)
        y_m = float(payload.get("y_m", 0.0) or 0.0)
        mode = str(self._resize_mode or "").strip().lower()
        eave_offset = 0.55

        if ridge_orientation == "width":
            left_edge = along - width_m / 2.0
            right_edge = along + width_m / 2.0
            if mode == "top":
                new_left = max(y0, min(y1, y_m))
                new_right = right_edge
                base.update({"along_m": 0.5 * (new_left + new_right), "width_m": max(0.30, new_right - new_left)})
            elif mode == "bottom":
                new_left = left_edge
                new_right = max(y0, min(y1, y_m))
                base.update({"along_m": 0.5 * (new_left + new_right), "width_m": max(0.30, new_right - new_left)})
            elif mode in ("left", "right"):
                if side == "front":
                    outer_x = x0 + eave_offset
                    new_depth = max(0.20, x_m - outer_x)
                else:
                    outer_x = x1 - eave_offset
                    new_depth = max(0.20, outer_x - x_m)
                max_depth = max(0.20, (x1 - x0) * 0.48)
                base.update({"depth_m": min(max_depth, new_depth)})
        else:
            left_edge = along - width_m / 2.0
            right_edge = along + width_m / 2.0
            if mode == "left":
                new_left = max(x0, min(x1, x_m))
                new_right = right_edge
                base.update({"along_m": 0.5 * (new_left + new_right), "width_m": max(0.30, new_right - new_left)})
            elif mode == "right":
                new_left = left_edge
                new_right = max(x0, min(x1, x_m))
                base.update({"along_m": 0.5 * (new_left + new_right), "width_m": max(0.30, new_right - new_left)})
            elif mode in ("top", "bottom"):
                if side == "left":
                    outer_y = y0 + eave_offset
                    new_depth = max(0.20, y_m - outer_y)
                else:
                    outer_y = y1 - eave_offset
                    new_depth = max(0.20, outer_y - y_m)
                max_depth = max(0.20, (y1 - y0) * 0.48)
                base.update({"depth_m": min(max_depth, new_depth)})
        base.update({"side": side, "depth_m": max(0.20, float(base.get("depth_m", depth_m) or depth_m))})
        return base


    def _build_draw_preview_rect(self, start_payload: dict | None, current_payload: dict | None) -> QRectF | None:
        if not start_payload or not current_payload:
            return None
        meta = self._last_plan_meta or {}
        scale = float(meta.get("scale", 0.0) or 0.0)
        bx = float(meta.get("bx", 0.0) or 0.0)
        by = float(meta.get("by", 0.0) or 0.0)
        if scale <= 1e-9:
            return None
        x0 = float(start_payload.get("x_m", 0.0) or 0.0)
        y0 = float(start_payload.get("y_m", 0.0) or 0.0)
        x1 = float(current_payload.get("x_m", x0) or x0)
        y1 = float(current_payload.get("y_m", y0) or y0)
        if abs(x1 - x0) < 0.20:
            x1 = x0 + (0.20 if x1 >= x0 else -0.20)
        if abs(y1 - y0) < 0.20:
            y1 = y0 + (0.20 if y1 >= y0 else -0.20)
        return QRectF(QPointF(bx + x0 * scale, by - y0 * scale), QPointF(bx + x1 * scale, by - y1 * scale)).normalized()

    def _payload_hits_selected_dormer(self, payload: dict | None) -> bool:
        if not payload or not self._selected_dormer_payload:
            return False
        preview = self._build_selected_dormer_rect()
        if preview is None:
            return False
        meta = self._last_plan_meta or {}
        scale = float(meta.get("scale", 0.0) or 0.0)
        bx = float(meta.get("bx", 0.0) or 0.0)
        by = float(meta.get("by", 0.0) or 0.0)
        if scale <= 1e-9:
            return False
        pt = QPointF(bx + float(payload.get("x_m", 0.0) or 0.0) * scale, by - float(payload.get("y_m", 0.0) or 0.0) * scale)
        return preview.adjusted(-6.0, -6.0, 6.0, 6.0).contains(pt)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._profile_adjust_mode_active and self._geom is not None and isinstance(self._last_cross_meta, dict):
            draw_rect = self._last_cross_meta.get("draw_rect")
            if isinstance(draw_rect, QRectF) and draw_rect.contains(event.position()):
                self._profile_drag_active = True
                payload = self._build_profile_payload(event.position())
                if payload is not None:
                    self._profile_drag_kind = str(payload.get("kind", "pitch") or "pitch")
                    self.roofProfileChanged.emit(payload)
                event.accept()
                return
        if event.button() == Qt.LeftButton and self._geom is not None and isinstance(self._last_plan_meta, dict):
            meta = self._last_plan_meta
            plan_rect = meta.get("plan_rect")
            if isinstance(plan_rect, QRectF) and plan_rect.contains(event.position()):
                payload = self._build_plan_click_payload(event.position().x(), event.position().y())
                if payload is not None:
                    self._drag_press_pos = QPointF(event.position())
                    if self._draw_mode_active:
                        self._draw_start_payload = payload
                        self._draw_current_payload = payload
                        self.update()
                        event.accept()
                        return
                    resize_mode = self._hit_selected_dormer_resize_handle(payload)
                    if resize_mode is not None:
                        self._resize_active = True
                        self._resize_started = False
                        self._resize_mode = resize_mode
                        self._resize_payload = payload
                        self._resize_press_pos = QPointF(event.position())
                        event.accept()
                        return
                    if self._payload_hits_selected_dormer(payload):
                        self._drag_active = True
                        self._drag_started = False
                        self._drag_payload = payload
                        event.accept()
                        return
                    self.planClicked.emit(payload)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._profile_drag_active and self._profile_adjust_mode_active:
            payload = self._build_profile_payload(event.position(), forced_kind=self._profile_drag_kind)
            if payload is not None:
                self.roofProfileChanged.emit(payload)
                self.update()
            event.accept()
            return
        if self._geom is not None and isinstance(self._last_plan_meta, dict):
            payload = self._build_plan_click_payload(event.position().x(), event.position().y())
            if self._draw_mode_active and self._draw_start_payload is not None:
                if payload is not None:
                    self._draw_current_payload = payload
                    self.update()
                event.accept()
                return
            if self._resize_active:
                if payload is not None:
                    self._resize_payload = payload
                    resized = self._build_resize_payload(payload)
                    moved = self._resize_press_pos is None or (event.position() - self._resize_press_pos).manhattanLength() >= 4.0
                    if moved and resized is not None and not self._resize_started:
                        self._resize_started = True
                        self.dormerResizeStarted.emit(resized)
                    if moved and resized is not None:
                        self.dormerResizeMoved.emit(resized)
                    self.update()
                event.accept()
                return
            if self._drag_active:
                if payload is not None:
                    self._drag_payload = payload
                    moved = self._drag_press_pos is None or (event.position() - self._drag_press_pos).manhattanLength() >= 4.0
                    if moved and not self._drag_started:
                        self._drag_started = True
                        self.dormerDragStarted.emit(payload)
                    if moved:
                        self.dormerDragMoved.emit(payload)
                    self.update()
                event.accept()
                return
            if self._placement_mode_active and payload != self._hover_plan_payload:
                self._hover_plan_payload = payload
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._profile_drag_active:
            payload = self._build_profile_payload(event.position(), forced_kind=self._profile_drag_kind)
            self._profile_drag_active = False
            if payload is not None:
                self.roofProfileChanged.emit(payload)
                self.update()
                event.accept()
                return
        if event.button() == Qt.LeftButton and self._draw_mode_active and self._draw_start_payload is not None:
            payload = self._build_plan_click_payload(event.position().x(), event.position().y()) or self._draw_current_payload
            start_payload = self._draw_start_payload
            self._draw_start_payload = None
            self._draw_current_payload = None
            if payload is not None and start_payload is not None:
                out = dict(payload)
                out["draw_start_along_m"] = float(start_payload.get("along_m", 0.0) or 0.0)
                out["draw_start_x_m"] = float(start_payload.get("x_m", 0.0) or 0.0)
                out["draw_start_y_m"] = float(start_payload.get("y_m", 0.0) or 0.0)
                out["draw_side"] = str(start_payload.get("side", payload.get("side", "left")) or payload.get("side", "left"))
                self.dormerDrawFinished.emit(out)
                self.update()
                event.accept()
                return
            self.update()
        if event.button() == Qt.LeftButton and self._resize_active:
            payload = self._resize_payload or self._build_plan_click_payload(event.position().x(), event.position().y())
            resized = self._build_resize_payload(payload) if payload is not None else None
            started = self._resize_started
            self._resize_active = False
            self._resize_started = False
            self._resize_mode = None
            self._resize_press_pos = None
            self._resize_payload = None
            if started and resized is not None:
                self.dormerResizeFinished.emit(resized)
                self.update()
                event.accept()
                return
            self.update()
        if event.button() == Qt.LeftButton and self._drag_active:
            payload = self._drag_payload or self._build_plan_click_payload(event.position().x(), event.position().y())
            started = self._drag_started
            self._drag_active = False
            self._drag_started = False
            self._drag_press_pos = None
            self._drag_payload = None
            if started and payload is not None:
                self.dormerDragFinished.emit(payload)
                self.update()
                event.accept()
                return
            if payload is not None:
                self.planClicked.emit(payload)
                self.update()
                event.accept()
                return
            self.update()
        super().mouseReleaseEvent(event)

    def _build_profile_payload(self, pos: QPointF, forced_kind: str | None = None) -> dict | None:
        g = self._geom
        meta = self._last_cross_meta or {}
        if g is None:
            return None
        scale = float(meta.get("scale", 0.0) or 0.0)
        if scale <= 1e-9:
            return None
        cross_span = max(0.50, float(meta.get("cross_span_m", getattr(g, "cross_span_m", 0.0)) or 0.0))
        base_x = float(meta.get("base_x", 0.0) or 0.0)
        base_y = float(meta.get("base_y", 0.0) or 0.0)
        x_m = max(0.0, min(cross_span, (float(pos.x()) - base_x) / scale))
        y_m = max(0.0, (base_y - float(pos.y())) / scale)
        knee_current = max(0.0, float(getattr(g, "knee_wall_height_m", 0.0) or 0.0))
        kind = forced_kind or ("knee" if y_m <= knee_current + 0.45 and (x_m < cross_span * 0.18 or x_m > cross_span * 0.82) else "pitch")
        if kind == "knee":
            return {"kind": "knee", "knee_wall_height_m": max(0.0, min(5.0, y_m))}
        run = max(0.25, min(max(x_m, cross_span - x_m), cross_span * 0.5))
        rise = max(0.05, y_m - knee_current)
        pitch = math.degrees(math.atan(rise / run))
        return {"kind": "pitch", "roof_pitch_deg": max(0.0, min(85.0, pitch))}

    def leaveEvent(self, event):
        changed = False
        if self._hover_plan_payload is not None:
            self._hover_plan_payload = None
            changed = True
        if not self._drag_active and self._drag_payload is not None:
            self._drag_payload = None
            changed = True
        if not self._resize_active and self._resize_payload is not None:
            self._resize_payload = None
            changed = True
        if changed:
            self.update()
        super().leaveEvent(event)

    def _build_plan_click_payload(self, px: float, py: float) -> dict | None:
        meta = self._last_plan_meta or {}
        scale = float(meta.get("scale", 0.0) or 0.0)
        if scale <= 1e-9:
            return None
        bx = float(meta.get("bx", 0.0) or 0.0)
        by = float(meta.get("by", 0.0) or 0.0)
        xm = (float(px) - bx) / scale
        ym = (by - float(py)) / scale
        inner_rect = tuple(meta.get("inner_rect", (0.0, 0.0, 0.0, 0.0)))
        if len(inner_rect) != 4:
            return None
        x0, y0, x1, y1 = (float(v) for v in inner_rect)
        if not (x0 <= xm <= x1 and y0 <= ym <= y1):
            return None
        ridge_orientation = str(meta.get("ridge_orientation", "length") or "length").strip().lower()
        if ridge_orientation == "width":
            along_m = max(0.0, min(float(meta.get("building_width_m", x1 - x0) or (x1 - x0)), ym - y0))
            side = "front" if xm <= (x0 + x1) / 2.0 else "back"
        else:
            along_m = max(0.0, min(float(meta.get("building_length_m", y1 - y0) or (y1 - y0)), xm - x0))
            side = "left" if ym <= (y0 + y1) / 2.0 else "right"
        return {
            "along_m": along_m,
            "side": side,
            "x_m": xm,
            "y_m": ym,
            "ridge_orientation": ridge_orientation,
        }


class AtticSketchPanel(QWidget):
    planClicked = Signal(dict)
    dormerDrawFinished = Signal(dict)
    dormerDragStarted = Signal(dict)
    dormerDragMoved = Signal(dict)
    dormerDragFinished = Signal(dict)
    dormerResizeStarted = Signal(dict)
    dormerResizeMoved = Signal(dict)
    dormerResizeFinished = Signal(dict)
    roofProfileChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self.info_label = QLabel("Kein Dachprofil aktiv")
        self.info_label.setWordWrap(True)
        self.sketch = AtticSketchWidget(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.sketch.planClicked.connect(self.planClicked)
        self.sketch.dormerDrawFinished.connect(self.dormerDrawFinished)
        self.sketch.dormerDragStarted.connect(self.dormerDragStarted)
        self.sketch.dormerDragMoved.connect(self.dormerDragMoved)
        self.sketch.dormerDragFinished.connect(self.dormerDragFinished)
        self.sketch.dormerResizeStarted.connect(self.dormerResizeStarted)
        self.sketch.dormerResizeMoved.connect(self.dormerResizeMoved)
        self.sketch.dormerResizeFinished.connect(self.dormerResizeFinished)
        self.sketch.roofProfileChanged.connect(self.roofProfileChanged)
        lay.addWidget(self.info_label)
        lay.addWidget(self.sketch, 1)

    def set_dormer_preview_state(self, active: bool, *, has_selection: bool = False, dormer_width_m: float = 1.80, min_edge_clearance_m: float = 0.40, draw_mode: bool = False) -> None:
        self.sketch.set_dormer_preview_state(
            active,
            has_selection=has_selection,
            dormer_width_m=dormer_width_m,
            min_edge_clearance_m=min_edge_clearance_m,
            draw_mode=draw_mode,
        )

    def set_selected_dormer_state(self, payload: dict | None) -> None:
        self.sketch.set_selected_dormer_state(payload)

    def set_selected_roof_side_state(self, payload: dict | None) -> None:
        self.sketch.set_selected_roof_side_state(payload)

    def set_roof_profile_adjust_state(self, active: bool) -> None:
        self.sketch.set_roof_profile_adjust_state(active)

    def set_geometry(self, geom: AtticGeometry | None) -> None:
        self.sketch.set_geometry(geom)
        if geom is None:
            self.info_label.setText("Kein DG-Dachprofil aktiv")
            return
        roof_type = str(getattr(geom, "roof_type", "satteldach") or "satteldach").strip().lower()
        roof_name = {
            "satteldach": "Satteldach",
            "pultdach": "Pultdach",
            "walmdach": "Walmdach",
            "krueppelwalmdach": "Krüppelwalmdach",
            "flachdach": "Flachdach",
            "winkeldach": "Winkel-/Kehldach",
        }.get(roof_type, "Satteldach")
        ridge_dir = {"length": "längs", "width": "quer"}.get(str(getattr(geom, "ridge_orientation", "length") or "length").strip().lower(), "längs")
        pult_dir = {"left": "links ansteigend", "right": "rechts ansteigend"}.get(str(getattr(geom, "pult_rise_side", "right") or "right").strip().lower(), "rechts ansteigend")
        asym = float(getattr(geom, "ridge_offset_ratio", 0.0) or 0.0)
        eave_ov = float(getattr(geom, "effective_eave_overhang_m", getattr(geom, "roof_overhang_m", 0.0)) or 0.0)
        gable_ov = float(getattr(geom, "effective_gable_overhang_m", getattr(geom, "roof_overhang_m", 0.0)) or 0.0)
        dormer_txt = "" if str(getattr(geom, "dormer_type", "none")).lower() == "none" else f" · Gaube={str(getattr(geom, 'dormer_type', 'none')).replace('gaube', '-gaube')}"
        rw_cnt = int(getattr(geom, "roof_window_count", 0) or 0)
        rw_txt = "" if rw_cnt <= 0 else f" · Dachfenster={rw_cnt}x"
        custom_cnt = len(getattr(geom, "roof_lines", []) or [])
        facet_cnt = len(geom.roof_facets())
        facet_txt = (" · Dachlinien=" + str(custom_cnt)) if custom_cnt > 0 else ""
        metric_txt = (" · Facetten=" + str(facet_cnt)) if facet_cnt > 0 else ""
        asym_txt = ""
        if roof_type in ("satteldach", "walmdach", "krueppelwalmdach") and abs(asym) > 1e-9:
            asym_txt = f" · asym. Firstversatz={asym:.2f}"
        pult_txt = f" · Pult={pult_dir}" if roof_type == "pultdach" else ""
        hip_txt = f" · Krüppelwalm={float(getattr(geom, 'half_hip_ratio', 0.0) or 0.0):.2f}" if roof_type == "krueppelwalmdach" else ""
        self.info_label.setText(
            f"B={geom.building_width_m:.2f} m · L={geom.building_length_m:.2f} m · "
            f"Kniestock={geom.knee_wall_height_m:.2f} m · Dachform={roof_name} · α={geom.roof_pitch_deg:.1f}°\n"
            f"Firstrichtung={ridge_dir} · Überstand Traufe={eave_ov:.2f} m · Giebel={gable_ov:.2f} m"
            f"{asym_txt}{pult_txt}{hip_txt}{dormer_txt}{rw_txt}{facet_txt}{metric_txt}\n"
            f"Dachfläche={geom.roof_area_total_m2:.2f} m² · Giebel={geom.gable_area_total_m2:.2f} m² je Stirnseite · "
            f"gew. DG-Fläche={geom.weighted_floor_area_m2():.2f} m²"
        )
