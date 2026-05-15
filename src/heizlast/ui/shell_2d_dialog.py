from __future__ import annotations

import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QBrush, QPen, QPolygonF, QPainter
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QGraphicsView, QGraphicsScene, QGraphicsPolygonItem, QGraphicsLineItem


class _Shell2DView(QGraphicsView):
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


class Shell2DDialog(QDialog):
    """2D renderer for the shell with real wall thickness, openings and roof plan lines."""

    def __init__(self, scene_data: dict, parent=None):
        super().__init__(parent)
        self.scene_data = dict(scene_data or {})
        self.setWindowTitle(str(self.scene_data.get("title", "2D Gebäudehülle")))
        self.resize(1180, 860)
        lay = QVBoxLayout(self)
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QColor("#f6f8fb"))
        self._view = _Shell2DView(self._scene, self)
        self._view.setObjectName("shell2DView")
        lay.addWidget(self._view, 1)
        self._build_scene()
        btn = QPushButton("Schließen")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)

    def _build_scene(self) -> None:
        scale = float(self.scene_data.get("px_per_m", 140.0) or 140.0)
        all_pts = []
        for item in list(self.scene_data.get("walls", []) or []):
            all_pts.extend(self._add_wall(item, scale))
        for line in list(self.scene_data.get("roof_plan_lines", []) or []):
            all_pts.extend(self._add_roof_line(line, scale))
        if all_pts:
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            pad = 120.0
            rect = QRectF(min(xs) - pad, min(ys) - pad, (max(xs) - min(xs)) + 2 * pad, (max(ys) - min(ys)) + 2 * pad)
            self._scene.setSceneRect(rect)
            self._view.fitInView(rect, Qt.KeepAspectRatio)

    def _xy(self, p, scale: float):
        return float(p[0]) * scale, -float(p[1]) * scale

    def _segment_points(self, p0, p1, s0: float, s1: float):
        dx = float(p1[0]) - float(p0[0])
        dy = float(p1[1]) - float(p0[1])
        L = max(1e-9, math.hypot(dx, dy))
        t0 = s0 / L
        t1 = s1 / L
        a = (float(p0[0]) + dx * t0, float(p0[1]) + dy * t0)
        b = (float(p0[0]) + dx * t1, float(p0[1]) + dy * t1)
        return a, b

    def _wall_polygon(self, p0, p1, thickness: float, poly_sign: float, scale: float):
        dx = float(p1[0]) - float(p0[0])
        dy = float(p1[1]) - float(p0[1])
        L = math.hypot(dx, dy)
        if L <= 1e-9:
            return None, 0.0, 0.0
        if poly_sign >= 0.0:
            nx, ny = dy / L, -dx / L
        else:
            nx, ny = -dy / L, dx / L
        ox = nx * thickness
        oy = ny * thickness
        a_in = self._xy(p0, scale)
        b_in = self._xy(p1, scale)
        a_out = self._xy((float(p0[0]) + ox, float(p0[1]) + oy), scale)
        b_out = self._xy((float(p1[0]) + ox, float(p1[1]) + oy), scale)
        poly = QPolygonF([QPointF(*a_in), QPointF(*b_in), QPointF(*b_out), QPointF(*a_out)])
        return poly, nx, ny

    def _add_wall(self, item: dict, scale: float):
        pts = []
        p0 = item.get("p0")
        p1 = item.get("p1")
        if not p0 or not p1:
            return pts
        thickness = float(item.get("thickness_m", 0.30) or 0.30)
        poly_sign = float(item.get("poly_sign", 1.0) or 1.0)
        wall_poly, nx, ny = self._wall_polygon(p0, p1, thickness, poly_sign, scale)
        if wall_poly is None:
            return pts
        wall_color = QColor("#d9dde3")
        wall_edge = QColor("#4c5561")
        wall_item = QGraphicsPolygonItem(wall_poly)
        wall_item.setPen(QPen(wall_edge, 1.4))
        wall_item.setBrush(QBrush(wall_color))
        wall_item.setZValue(1.0)
        self._scene.addItem(wall_item)
        for pt in wall_poly:
            pts.append((pt.x(), pt.y()))
        dx = float(p1[0]) - float(p0[0])
        dy = float(p1[1]) - float(p0[1])
        L = math.hypot(dx, dy)
        if L <= 1e-9:
            return pts
        openings = sorted(list(item.get("openings", []) or []), key=lambda o: (float(o.get("start", 0.0) or 0.0), float(o.get("end", 0.0) or 0.0)))
        for op in openings:
            start = max(0.0, min(L, float(op.get("start", 0.0) or 0.0)))
            end = max(0.0, min(L, float(op.get("end", 0.0) or 0.0)))
            if end <= start + 1e-6:
                continue
            a2, b2 = self._segment_points(p0, p1, start, end)
            opening_poly, _, _ = self._wall_polygon(a2, b2, thickness, poly_sign, scale)
            if opening_poly is None:
                continue
            opening_type = str(op.get("type", "window") or "window").lower()
            if opening_type == "door":
                fill = QColor("#8e6b48")
                edge = QColor("#5a4029")
            else:
                fill = QColor("#8dc8ff")
                fill.setAlpha(150)
                edge = QColor("#2c6ebd")
            op_item = QGraphicsPolygonItem(opening_poly)
            op_item.setPen(QPen(edge, 1.4, Qt.SolidLine))
            op_item.setBrush(QBrush(fill))
            op_item.setZValue(3.0)
            self._scene.addItem(op_item)
            for pt in opening_poly:
                pts.append((pt.x(), pt.y()))
            self._add_opening_reveals(a2, b2, nx, ny, thickness, scale, edge)
        return pts

    def _add_opening_reveals(self, a2, b2, nx: float, ny: float, thickness: float, scale: float, edge: QColor):
        ax, ay = self._xy(a2, scale)
        bx, by = self._xy(b2, scale)
        aox, aoy = self._xy((a2[0] + nx * thickness, a2[1] + ny * thickness), scale)
        box, boy = self._xy((b2[0] + nx * thickness, b2[1] + ny * thickness), scale)
        pen = QPen(edge, 1.6)
        pen.setCosmetic(True)
        for p1, p2 in [((ax, ay), (aox, aoy)), ((bx, by), (box, boy)), ((ax, ay), (bx, by)), ((aox, aoy), (box, boy))]:
            ln = QGraphicsLineItem(p1[0], p1[1], p2[0], p2[1])
            ln.setPen(pen)
            ln.setZValue(4.0)
            self._scene.addItem(ln)

    def _add_roof_line(self, line: dict, scale: float):
        p1 = line.get("p1")
        p2 = line.get("p2")
        if not p1 or not p2:
            return []
        x1, y1 = self._xy(p1, scale)
        x2, y2 = self._xy(p2, scale)
        kind = str(line.get("kind", "line") or "line").lower()
        color = QColor("#2d3440") if kind == "first" else QColor("#8d4f2f") if kind == "grat" else QColor("#2b5f9e")
        pen = QPen(color, 2.2 if kind == "first" else 1.7)
        pen.setCosmetic(True)
        if kind != "first":
            pen.setStyle(Qt.DashLine)
        item = QGraphicsLineItem(x1, y1, x2, y2)
        item.setPen(pen)
        item.setZValue(5.0)
        self._scene.addItem(item)
        return [(x1, y1), (x2, y2)]
