from __future__ import annotations

import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QBrush, QPen, QPolygonF, QPainter, QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QPushButton,
    QVBoxLayout,
)


class _HouseSideView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)

    def wheelEvent(self, event):  # pragma: no cover - interactive UI
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)


class HouseSideDialog(QDialog):
    """Simple side elevation for cellar, ground floor, upper floor and roof."""

    _VIEWS = (
        ("front", "Frontansicht", "building_width_m"),
        ("right", "Seite rechts", "building_depth_m"),
        ("back", "Ansicht von hinten", "building_width_m"),
        ("left", "Seite links", "building_depth_m"),
    )

    def __init__(self, scene_data: dict, parent=None):
        super().__init__(parent)
        self.scene_data = dict(scene_data or {})
        self._view_index = 0
        self.setWindowTitle(str(self.scene_data.get("title", "Haus Seitenansicht")))
        self.resize(1120, 760)

        lay = QVBoxLayout(self)
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QColor("#f4f7fb"))
        self._view = _HouseSideView(self._scene, self)
        self._view.setObjectName("houseSideView")
        lay.addWidget(self._view, 1)

        self._build_scene()

        nav_lay = QHBoxLayout()
        self.btn_prev = QPushButton("←")
        self.btn_prev.setToolTip("Vorherige Gebäudeseite anzeigen")
        self.btn_prev.clicked.connect(lambda: self._switch_view(-1))
        self.btn_next = QPushButton("→")
        self.btn_next.setToolTip("Nächste Gebäudeseite anzeigen")
        self.btn_next.clicked.connect(lambda: self._switch_view(1))
        btn = QPushButton("Schließen")
        btn.clicked.connect(self.accept)
        nav_lay.addWidget(self.btn_prev)
        nav_lay.addWidget(self.btn_next)
        nav_lay.addStretch(1)
        nav_lay.addWidget(btn)
        lay.addLayout(nav_lay)

    def keyPressEvent(self, event):  # pragma: no cover - interactive UI
        if event.key() == Qt.Key_Left:
            self._switch_view(-1)
            event.accept()
            return
        if event.key() == Qt.Key_Right:
            self._switch_view(1)
            event.accept()
            return
        super().keyPressEvent(event)

    def _switch_view(self, step: int) -> None:
        self._view_index = (self._view_index + int(step)) % len(self._VIEWS)
        self._build_scene()

    def _current_view_def(self) -> tuple[str, str, str]:
        return self._VIEWS[self._view_index % len(self._VIEWS)]

    def _xy(self, x_m: float, z_m: float, scale: float) -> QPointF:
        return QPointF(float(x_m) * scale, -float(z_m) * scale)

    def _add_label(self, text: str, x: float, y: float, size: int = 10, bold: bool = False) -> None:
        item = QGraphicsSimpleTextItem(text)
        font = QFont()
        font.setPointSize(size)
        font.setBold(bold)
        item.setFont(font)
        item.setBrush(QBrush(QColor("#243040")))
        item.setPos(x, y)
        item.setZValue(10.0)
        self._scene.addItem(item)

    def _build_scene(self) -> None:
        self._scene.clear()
        scale = float(self.scene_data.get("px_per_m", 78.0) or 78.0)
        view_key, view_title, dimension_key = self._current_view_def()
        width_m = max(3.0, float(self.scene_data.get(dimension_key, self.scene_data.get("building_width_m", 10.0)) or 10.0))
        levels = list(self.scene_data.get("levels", []) or [])
        if not levels:
            return
        self.setWindowTitle(f"{self.scene_data.get('title', 'Haus Seitenansicht')} · {view_title}")

        x0 = 0.0
        x1 = width_m
        facade = QColor(str(self.scene_data.get("facade_color", "#d9ded6") or "#d9ded6"))
        cellar = QColor("#c9ced6")
        slab = QColor("#6d7480")
        edge = QPen(QColor("#3f4854"), 1.6)
        edge.setCosmetic(True)
        slab_pen = QPen(slab, 2.0)
        slab_pen.setCosmetic(True)

        all_points: list[QPointF] = []

        self._add_label(view_title, -0.8 * scale, -self._max_roof_z(levels) * scale - 58.0, 14, True)

        ground = QGraphicsLineItem(-0.8 * scale, 0.0, (width_m + 0.8) * scale, 0.0)
        ground_pen = QPen(QColor("#556b50"), 2.0, Qt.DashLine)
        ground_pen.setCosmetic(True)
        ground.setPen(ground_pen)
        ground.setZValue(0.0)
        self._scene.addItem(ground)
        self._add_label("Gelände", -0.8 * scale, 8.0, 9)

        for idx, level in enumerate(levels):
            label = str(level.get("label", "Geschoss") or "Geschoss")
            z0 = float(level.get("z0_m", 0.0) or 0.0)
            z1 = float(level.get("z1_m", z0 + 2.5) or (z0 + 2.5))
            if z1 <= z0:
                continue
            p_tl = self._xy(x0, z1, scale)
            p_br = self._xy(x1, z0, scale)
            rect = QRectF(p_tl, p_br).normalized()
            item = QGraphicsRectItem(rect)
            item.setPen(edge)
            item.setBrush(QBrush(cellar if z1 <= 0.01 else facade))
            item.setZValue(1.0)
            self._scene.addItem(item)
            all_points.extend([rect.topLeft(), rect.bottomRight()])

            y_slab = -z1 * scale
            slab_line = QGraphicsLineItem(x0 * scale, y_slab, x1 * scale, y_slab)
            slab_line.setPen(slab_pen)
            slab_line.setZValue(3.0)
            self._scene.addItem(slab_line)

            self._add_label(label, x1 * scale + 16.0, rect.center().y() - 10.0, 10, True)
            height_txt = f"{max(0.0, z1 - z0):.2f} m"
            self._add_label(height_txt, x1 * scale + 16.0, rect.center().y() + 9.0, 8)
            self._add_projection_edges(rect, level, view_key)
            self._add_windows(rect, idx, view_key, level)

        top_z = max(float(l.get("z1_m", 0.0) or 0.0) for l in levels)
        roof_points = self._roof_polygon(x0, x1, top_z)
        if roof_points:
            roof_poly = QPolygonF([self._xy(x, z, scale) for x, z in roof_points])
            roof_item = QGraphicsPolygonItem(roof_poly)
            roof_item.setPen(edge)
            roof_item.setBrush(QBrush(QColor(str(self.scene_data.get("roof_color", "#b24a3a") or "#b24a3a"))))
            roof_item.setZValue(2.0)
            self._scene.addItem(roof_item)
            for p in roof_poly:
                all_points.append(p)
            roof_name = str(self.scene_data.get("roof_name", "Dach") or "Dach")
            roof_rect = roof_poly.boundingRect()
            self._add_label(roof_name, roof_rect.center().x() - 34.0, roof_rect.top() - 28.0, 11, True)
            self._add_dormers(view_key, width_m, top_z, scale)

        if all_points:
            xs = [p.x() for p in all_points]
            ys = [p.y() for p in all_points]
            pad = 130.0
            rect = QRectF(min(xs) - pad, min(ys) - pad, (max(xs) - min(xs)) + 2.0 * pad + 120.0, (max(ys) - min(ys)) + 2.0 * pad)
            self._scene.setSceneRect(rect)
            self._view.fitInView(rect, Qt.KeepAspectRatio)

    def _max_roof_z(self, levels: list[dict]) -> float:
        top_z = max(float(l.get("z1_m", 0.0) or 0.0) for l in levels)
        return top_z + max(0.12, float(self.scene_data.get("roof_height_m", 1.2) or 1.2))

    def _visible_dormers_for_view(self, view_key: str) -> list[dict]:
        dormers = list(self.scene_data.get("dormers", []) or [])
        return [d for d in dormers if str(d.get("side", "") or "").strip().lower() == str(view_key).strip().lower()]

    def _roof_z_at_view_x(self, x_m: float, width_m: float, top_z: float) -> float:
        roof_type = str(self.scene_data.get("roof_type", "satteldach") or "satteldach").strip().lower()
        roof_h = max(0.12, float(self.scene_data.get("roof_height_m", 1.2) or 1.2))
        overhang = max(0.0, float(self.scene_data.get("roof_overhang_m", 0.30) or 0.0))
        a = -overhang
        b = width_m + overhang
        if roof_type == "flachdach":
            return top_z + min(0.25, roof_h)
        if roof_type == "pultdach":
            t = 0.0 if b <= a else max(0.0, min(1.0, (float(x_m) - a) / (b - a)))
            return top_z + max(0.12, roof_h * (0.12 + 0.88 * t))
        if roof_type in {"walmdach", "krueppelwalmdach"}:
            e = max(0.5, min((b - a) * 0.22, roof_h / max(math.tan(math.radians(25.0)), 0.1)))
            if x_m <= a + e:
                return top_z + roof_h * max(0.0, min(1.0, (x_m - a) / e))
            if x_m >= b - e:
                return top_z + roof_h * max(0.0, min(1.0, (b - x_m) / e))
            return top_z + roof_h
        mid = (a + b) * 0.5
        half = max(0.1, (b - a) * 0.5)
        return top_z + roof_h * max(0.0, 1.0 - abs(float(x_m) - mid) / half)

    def _add_dormers(self, view_key: str, width_m: float, top_z: float, scale: float) -> None:
        dormers = self._visible_dormers_for_view(view_key)
        if not dormers:
            return
        roof_color = QColor(str(self.scene_data.get("roof_color", "#b24a3a") or "#b24a3a"))
        wall = QColor("#f5e8d0")
        edge = QPen(QColor("#334155"), 1.3)
        edge.setCosmetic(True)
        roof_pen = QPen(roof_color.darker(120), 1.2)
        roof_pen.setCosmetic(True)
        for dormer in dormers:
            center = max(0.0, min(width_m, float(dormer.get("center_along_m", width_m * 0.5) or 0.0)))
            width = max(0.20, float(dormer.get("width_m", 1.60) or 1.60))
            height = max(0.20, float(dormer.get("front_height_m", 1.10) or 1.10))
            x_left = max(0.0, min(width_m - 0.15, center - width * 0.5))
            x_right = min(width_m, max(0.15, center + width * 0.5))
            if x_right <= x_left:
                continue
            base_z = min(self._roof_z_at_view_x(x_left, width_m, top_z), self._roof_z_at_view_x(x_right, width_m, top_z))
            base_z = max(top_z + 0.08, base_z - 0.04)
            dormer_type = str(dormer.get("type", "schleppgaube") or "schleppgaube").strip().lower()
            body_top = base_z + height

            body = QGraphicsRectItem(QRectF(self._xy(x_left, body_top, scale), self._xy(x_right, base_z, scale)).normalized())
            body.setPen(edge)
            body.setBrush(QBrush(wall))
            body.setZValue(5.0)
            self._scene.addItem(body)

            roof_pts = self._dormer_roof_points(dormer_type, x_left, x_right, base_z, body_top)
            if roof_pts:
                roof_item = QGraphicsPolygonItem(QPolygonF([self._xy(x, z, scale) for x, z in roof_pts]))
                roof_item.setPen(roof_pen)
                roof_item.setBrush(QBrush(roof_color.lighter(110)))
                roof_item.setZValue(6.0)
                self._scene.addItem(roof_item)

            self._add_dormer_windows(dormer, x_left, x_right, base_z, body_top, scale)
            label = str(dormer.get("id", "Gaube") or "Gaube")
            self._add_label(label, x_left * scale, -max(body_top, max((p[1] for p in roof_pts), default=body_top)) * scale - 18.0, 8)

    def _dormer_roof_points(self, dormer_type: str, x_left: float, x_right: float, base_z: float, body_top: float) -> list[tuple[float, float]]:
        width = max(0.1, x_right - x_left)
        if dormer_type in {"satteldachgaube", "gable"}:
            ridge_z = body_top + max(0.20, width * 0.28)
            mid = 0.5 * (x_left + x_right)
            return [(x_left - 0.08, body_top), (mid, ridge_z), (x_right + 0.08, body_top)]
        if dormer_type in {"spitzgaube", "pointed"}:
            ridge_z = body_top + max(0.35, width * 0.55)
            mid = 0.5 * (x_left + x_right)
            return [(x_left, base_z), (mid, ridge_z), (x_right, base_z)]
        if dormer_type in {"flachdachgaube", "flat"}:
            return [(x_left - 0.08, body_top), (x_right + 0.08, body_top), (x_right + 0.08, body_top + 0.12), (x_left - 0.08, body_top + 0.12)]
        return [(x_left - 0.08, body_top), (x_right + 0.08, body_top), (x_right + 0.08, body_top + 0.28), (x_left - 0.08, body_top + 0.12)]

    def _add_dormer_windows(self, dormer: dict, x_left: float, x_right: float, base_z: float, body_top: float, scale: float) -> None:
        count = max(0, int(dormer.get("window_count", 1) or 0))
        if count <= 0:
            return
        width_m = x_right - x_left
        win_w = min(max(0.25, float(dormer.get("window_width_m", 0.8) or 0.8)), max(0.25, width_m / max(1, count) * 0.72))
        win_h = min(max(0.25, float(dormer.get("window_height_m", 0.8) or 0.8)), max(0.25, (body_top - base_z) * 0.58))
        sill = min(max(0.12, float(dormer.get("sill_height_m", 0.5) or 0.5)), max(0.12, (body_top - base_z) - win_h - 0.08))
        total_w = count * win_w
        gap = max(0.08, (width_m - total_w) / (count + 1))
        y0 = base_z + sill
        for idx in range(count):
            wx0 = x_left + gap * (idx + 1) + win_w * idx
            wx1 = wx0 + win_w
            rect = QGraphicsRectItem(QRectF(self._xy(wx0, y0 + win_h, scale), self._xy(wx1, y0, scale)).normalized())
            rect.setPen(QPen(QColor("#1d4ed8"), 1.0))
            rect.setBrush(QBrush(QColor("#bae6fd")))
            rect.setZValue(7.0)
            self._scene.addItem(rect)

    def _add_projection_edges(self, floor_rect: QRectF, level: dict, view_key: str) -> None:
        floor = str(level.get("floor", "") or "").strip().upper()
        edges = [
            item for item in list(self.scene_data.get("projection_edges", []) or [])
            if str(item.get("view", "") or "") == view_key and str(item.get("floor", "") or "").strip().upper() == floor
        ]
        if not edges:
            return
        pen = QPen(QColor("#1f2937"), 1.2, Qt.DashLine)
        pen.setCosmetic(True)
        for edge in edges:
            pos_m = max(0.0, float(edge.get("pos_m", 0.0) or 0.0))
            x = floor_rect.left() + pos_m * float(self.scene_data.get("px_per_m", 78.0) or 78.0)
            if x <= floor_rect.left() + 2.0 or x >= floor_rect.right() - 2.0:
                continue
            line = QGraphicsLineItem(x, floor_rect.top(), x, floor_rect.bottom())
            line.setPen(pen)
            line.setZValue(4.2)
            self._scene.addItem(line)

    def _add_windows(self, floor_rect: QRectF, idx: int, view_key: str, level: dict) -> None:
        floor = str(level.get("floor", "") or "").strip().upper()
        windows = [
            item for item in list(self.scene_data.get("windows", []) or [])
            if str(item.get("view", "") or "") == view_key and str(item.get("floor", "") or "").strip().upper() == floor
        ]
        if not windows:
            return
        scale = float(self.scene_data.get("px_per_m", 78.0) or 78.0)
        win_pen = QPen(QColor("#1d4ed8"), 1.2)
        win_pen.setCosmetic(True)
        secondary_pen = QPen(QColor("#1d4ed8"), 1.2, Qt.DashLine)
        secondary_pen.setCosmetic(True)
        door_pen = QPen(QColor("#8b451c"), 1.3)
        door_pen.setCosmetic(True)
        secondary_door_pen = QPen(QColor("#8b451c"), 1.3, Qt.DashLine)
        secondary_door_pen.setCosmetic(True)
        for item in windows:
            is_door = str(item.get("opening_type", "") or "").strip().lower() == "door"
            center_m = float(item.get("center_m", 0.0) or 0.0)
            width_m = max(0.10, float(item.get("width_m", 0.8) or 0.8))
            sill_m = max(0.0, float(item.get("sill_m", 0.9) or 0.9))
            height_m = max(0.10, float(item.get("height_m", 1.0) or 1.0))
            w = max(12.0, width_m * scale)
            h = max(14.0, height_m * scale)
            x = floor_rect.left() + center_m * scale - w * 0.5
            y = floor_rect.bottom() - (sill_m + height_m) * scale
            rect = QGraphicsRectItem(QRectF(x, y, w, h))
            if is_door:
                rect.setPen(secondary_door_pen if bool(item.get("secondary_plane", False)) else door_pen)
                rect.setBrush(QBrush(QColor("#d7b089")))
            else:
                rect.setPen(secondary_pen if bool(item.get("secondary_plane", False)) else win_pen)
                rect.setBrush(QBrush(QColor("#9bd2f3")))
            rect.setZValue(5.0 + idx * 0.01)
            self._scene.addItem(rect)
            cross_pen = QPen(QColor("#7c2d12") if is_door else QColor("#2563eb"), 0.8)
            cross_pen.setCosmetic(True)
            line_v = QGraphicsLineItem(x + w * 0.5, y, x + w * 0.5, y + h)
            line_h = QGraphicsLineItem(x, y + h * 0.5, x + w, y + h * 0.5)
            line_v.setPen(cross_pen)
            line_h.setPen(cross_pen)
            line_v.setZValue(5.2 + idx * 0.01)
            line_h.setZValue(5.2 + idx * 0.01)
            self._scene.addItem(line_v)
            self._scene.addItem(line_h)

    def _roof_polygon(self, x0: float, x1: float, z0: float) -> list[tuple[float, float]]:
        roof_type = str(self.scene_data.get("roof_type", "satteldach") or "satteldach").strip().lower()
        roof_h = max(0.12, float(self.scene_data.get("roof_height_m", 1.2) or 1.2))
        overhang = max(0.0, float(self.scene_data.get("roof_overhang_m", 0.30) or 0.0))
        a = x0 - overhang
        b = x1 + overhang
        if roof_type == "flachdach":
            return [(a, z0), (b, z0), (b, z0 + min(0.25, roof_h)), (a, z0 + min(0.25, roof_h))]
        if roof_type == "pultdach":
            return [(a, z0), (b, z0), (b, z0 + roof_h), (a, z0 + max(0.12, roof_h * 0.12))]
        if roof_type in {"walmdach", "krueppelwalmdach"}:
            e = max(0.5, min((b - a) * 0.22, roof_h / max(math.tan(math.radians(25.0)), 0.1)))
            return [(a, z0), (b, z0), (b - e, z0 + roof_h), (a + e, z0 + roof_h)]
        mid = (a + b) * 0.5
        return [(a, z0), (b, z0), (mid, z0 + roof_h)]
