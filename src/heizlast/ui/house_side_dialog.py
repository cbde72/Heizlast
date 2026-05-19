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
            if label != "Keller":
                self._add_windows(rect, idx, view_key)

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

    def _add_windows(self, floor_rect: QRectF, idx: int, view_key: str) -> None:
        count_by_view = {"front": 3, "back": 3, "right": 2, "left": 2}
        count = count_by_view.get(view_key, 3)
        w = min(54.0, max(34.0, floor_rect.width() / 11.0))
        h = min(62.0, max(38.0, floor_rect.height() * 0.34))
        gap = floor_rect.width() / (count + 1)
        y = floor_rect.center().y() - h * 0.5
        for n in range(count):
            x = floor_rect.left() + gap * (n + 1) - w * 0.5
            rect = QGraphicsRectItem(QRectF(x, y, w, h))
            rect.setPen(QPen(QColor("#2d6f9f"), 1.2))
            rect.setBrush(QBrush(QColor("#9bd2f3")))
            rect.setZValue(4.0 + idx * 0.01)
            self._scene.addItem(rect)

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
