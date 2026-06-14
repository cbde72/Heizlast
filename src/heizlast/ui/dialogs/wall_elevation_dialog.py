from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget


@dataclass
class WallOpeningViewModel:
    offset_m: float
    width_m: float
    sill_m: float
    height_m: float
    label: str = "Fenster"
    opening_type: str = "window"


class WallElevationWidget(QWidget):
    def __init__(self, wall_width_m: float, wall_height_m: float, openings: List[WallOpeningViewModel], parent=None):
        super().__init__(parent)
        self.wall_width_m = max(0.10, float(wall_width_m))
        self.wall_height_m = max(0.10, float(wall_height_m))
        self.openings = list(openings or [])
        self.setMinimumSize(760, 440)

    def _px(self, x_m: float, y_m: float, rect: QRectF):
        sx = rect.left() + (float(x_m) / self.wall_width_m) * rect.width()
        sy = rect.bottom() - (float(y_m) / self.wall_height_m) * rect.height()
        return sx, sy

    def paintEvent(self, event):
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self.width() <= 0 or self.height() <= 0:
            return
        painter.fillRect(self.rect(), QColor(248, 250, 252))

        margin_l = 80
        margin_r = 36
        margin_t = 30
        margin_b = 64
        rect = QRectF(margin_l, margin_t, max(80, self.width() - margin_l - margin_r), max(80, self.height() - margin_t - margin_b))

        # wall face
        painter.setPen(QPen(QColor(88, 100, 114), 2))
        painter.setBrush(QColor(229, 231, 235))
        painter.drawRect(rect)

        # brick-like vertical joints, technical not photorealistic
        painter.setPen(QPen(QColor(190, 120, 100), 1))
        n_cols = max(4, int(round(self.wall_width_m / 0.25)))
        for i in range(1, n_cols):
            x = rect.left() + rect.width() * i / n_cols
            painter.drawLine(x, rect.top(), x, rect.bottom())
        n_rows = max(3, int(round(self.wall_height_m / 0.08)))
        for i in range(1, n_rows):
            y = rect.top() + rect.height() * i / n_rows
            painter.drawLine(rect.left(), y, rect.right(), y)

        # openings
        font_small = QFont()
        font_small.setPointSize(9)
        painter.setFont(font_small)
        for op in self.openings:
            is_door = str(getattr(op, "opening_type", "window") or "window").lower() == "door"
            if is_door:
                painter.setPen(QPen(QColor(120, 53, 15), 2))
                painter.setBrush(QColor(254, 215, 170))
            else:
                painter.setPen(QPen(QColor(37, 99, 235), 2))
                painter.setBrush(QColor(219, 234, 254))
            x0, y0 = self._px(op.offset_m, op.sill_m, rect)
            x1, y1 = self._px(op.offset_m + op.width_m, op.sill_m + op.height_m, rect)
            r = QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            painter.drawRect(r)
            if is_door:
                painter.drawLine(r.left(), r.top(), r.right(), r.bottom())
                painter.drawArc(QRectF(r.left() + 8, r.top() + 8, max(10.0, r.width() - 16), max(10.0, r.width() - 16)), 0, 90 * 16)
            else:
                painter.drawLine(r.left(), r.top(), r.right(), r.bottom())
                painter.drawLine(r.left(), r.bottom(), r.right(), r.top())
            painter.drawText(r.adjusted(4, 4, -4, -4), Qt.AlignTop | Qt.AlignHCenter, f"{op.label}\n{op.width_m:.2f} × {op.height_m:.2f} m")

        # axes / dimensions
        dim_pen = QPen(QColor(51, 65, 85), 1)
        painter.setPen(dim_pen)
        base_y = rect.bottom() + 24
        painter.drawLine(rect.left(), base_y, rect.right(), base_y)
        painter.drawLine(rect.left(), base_y - 6, rect.left(), base_y + 6)
        painter.drawLine(rect.right(), base_y - 6, rect.right(), base_y + 6)
        painter.drawText(QRectF(rect.left(), base_y + 6, rect.width(), 20), Qt.AlignHCenter | Qt.AlignTop, f"Breite = {self.wall_width_m:.2f} m")

        left_x = rect.left() - 28
        painter.drawLine(left_x, rect.top(), left_x, rect.bottom())
        painter.drawLine(left_x - 6, rect.top(), left_x + 6, rect.top())
        painter.drawLine(left_x - 6, rect.bottom(), left_x + 6, rect.bottom())
        painter.save()
        painter.translate(left_x - 28, rect.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-80, -12, 160, 24), Qt.AlignCenter, f"Höhe = {self.wall_height_m:.2f} m")
        painter.restore()

        # opening dimensions: left/right distances, width, sill, height
        painter.setPen(QPen(QColor(71, 85, 105), 1, Qt.DashLine))
        dim_row_h = 18
        for idx, op in enumerate(self.openings):
            x0, _ = self._px(op.offset_m, 0.0, rect)
            x1, _ = self._px(op.offset_m + op.width_m, 0.0, rect)
            painter.drawLine(x0, rect.bottom(), x0, base_y - 2)
            painter.drawLine(x1, rect.bottom(), x1, base_y - 2)
            row_y = base_y - 2 - idx * dim_row_h
            painter.drawLine(rect.left(), row_y, rect.right(), row_y)
            painter.drawText(QRectF(rect.left(), row_y - 16, max(36, x0 - rect.left()), 14), Qt.AlignHCenter | Qt.AlignBottom, f"L = {op.offset_m:.2f} m")
            painter.drawText(QRectF(x0, row_y - 16, max(36, x1 - x0), 14), Qt.AlignHCenter | Qt.AlignBottom, f"B = {op.width_m:.2f} m")
            right_gap = max(0.0, self.wall_width_m - op.offset_m - op.width_m)
            painter.drawText(QRectF(x1, row_y - 16, max(36, rect.right() - x1), 14), Qt.AlignHCenter | Qt.AlignBottom, f"R = {right_gap:.2f} m")

            yb = self._px(0.0, op.sill_m, rect)[1]
            yt = self._px(0.0, op.sill_m + op.height_m, rect)[1]
            dim_x = rect.right() + 16 + idx * 22
            painter.drawLine(dim_x, yb, dim_x, yt)
            painter.drawLine(dim_x - 5, yb, dim_x + 5, yb)
            painter.drawLine(dim_x - 5, yt, dim_x + 5, yt)
            painter.save()
            painter.translate(dim_x + 16, 0.5 * (yb + yt))
            painter.rotate(-90)
            painter.drawText(QRectF(-72, -12, 144, 24), Qt.AlignCenter, f"h = {op.height_m:.2f} m")
            painter.restore()
            if op.sill_m > 1e-9:
                dim_x2 = dim_x + 12
                painter.drawLine(dim_x2, rect.bottom(), dim_x2, yb)
                painter.drawLine(dim_x2 - 4, rect.bottom(), dim_x2 + 4, rect.bottom())
                painter.drawLine(dim_x2 - 4, yb, dim_x2 + 4, yb)
                painter.save()
                painter.translate(dim_x2 + 16, 0.5 * (rect.bottom() + yb))
                painter.rotate(-90)
                painter.drawText(QRectF(-72, -12, 144, 24), Qt.AlignCenter, f"BRH = {op.sill_m:.2f} m")
                painter.restore()


class WallElevationDialog(QDialog):
    def __init__(self, *, title: str, wall_width_m: float, wall_height_m: float, openings: List[WallOpeningViewModel], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(920, 620)

        root = QVBoxLayout(self)
        n_doors = sum(1 for o in openings if str(getattr(o, "opening_type", "window") or "window").lower() == "door")
        n_windows = len(openings) - n_doors
        info = QLabel(f"2D-Wandansicht · Breite {wall_width_m:.2f} m · Höhe {wall_height_m:.2f} m · Fenster {n_windows} · Türen {n_doors}")
        info.setStyleSheet("font-weight: 600; color: #0f172a; padding: 4px 2px;")
        root.addWidget(info)

        canvas = WallElevationWidget(wall_width_m=wall_width_m, wall_height_m=wall_height_m, openings=openings, parent=self)
        root.addWidget(canvas, 1)

        foot = QHBoxLayout()
        foot.addWidget(QLabel(f"Öffnungen gesamt: {len(openings)}"))
        foot.addStretch(1)
        root.addLayout(foot)
