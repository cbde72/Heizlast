from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from ..domain.models import RoomModel

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    import pyqtgraph.opengl as gl
except Exception:  # pragma: no cover
    gl = None


class Room3DDialog(QDialog):
    """Non-modal 3D preview for the currently selected room."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("3D Raum")
        self.setWindowModality(Qt.NonModal)
        self.resize(760, 560)
        self._items = []
        self._view = None

        layout = QVBoxLayout(self)
        self._title = QLabel("Kein Raum ausgewählt")
        self._title.setObjectName("room3DTitle")
        layout.addWidget(self._title)

        if gl is None or np is None:
            self._fallback = QLabel("3D-Ansicht nicht verfügbar: pyqtgraph.opengl oder numpy fehlt.")
            self._fallback.setAlignment(Qt.AlignCenter)
            layout.addWidget(self._fallback, 1)
        else:
            self._view = gl.GLViewWidget(self)
            self._view.setObjectName("room3DOpenGLView")
            self._view.opts["distance"] = 10.0
            self._view.opts["elevation"] = 22
            self._view.opts["azimuth"] = -42
            layout.addWidget(self._view, 1)

    @staticmethod
    def is_available() -> bool:
        return gl is not None and np is not None

    def set_room(self, room: RoomModel | None, elements=None) -> None:
        self._clear_scene()
        if room is None:
            self._title.setText("Kein Raum ausgewählt")
            return
        self._title.setText(f"{getattr(room, 'name', '') or getattr(room, 'id', 'Raum')} · {getattr(room, 'floor', '')}")
        if self._view is None:
            return
        pts = self._room_points(room)
        if len(pts) < 3:
            return
        height = max(0.1, float(getattr(room, "height_m", 2.5) or 2.5))
        self._add_grid(pts)
        self._add_floor_and_ceiling(pts, height)
        self._add_walls(pts, height)
        self._add_element_markers(list(elements or []), height)
        self._frame_camera(pts, height)

    def _clear_scene(self) -> None:
        if self._view is None:
            return
        for item in list(self._items):
            try:
                self._view.removeItem(item)
            except Exception:
                pass
        self._items.clear()

    def _room_points(self, room: RoomModel) -> list[tuple[float, float]]:
        try:
            room.ensure_polygon()
            pts = [(float(x), float(y)) for x, y in room.polygon_points()]
        except Exception:
            pts = []
        if len(pts) >= 3:
            return pts
        x = float(getattr(room, "x_m", 0.0) or 0.0)
        y = float(getattr(room, "y_m", 0.0) or 0.0)
        w = max(0.1, float(getattr(room, "w_m", 0.0) or 0.0))
        h = max(0.1, float(getattr(room, "h_m", 0.0) or 0.0))
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]

    def _add_grid(self, pts: list[tuple[float, float]]) -> None:
        grid = gl.GLGridItem()
        span = max(
            max(x for x, _ in pts) - min(x for x, _ in pts),
            max(y for _, y in pts) - min(y for _, y in pts),
            2.0,
        )
        grid.setSize(x=span + 4.0, y=span + 4.0)
        grid.setSpacing(x=0.5, y=0.5)
        self._view.addItem(grid)
        self._items.append(grid)

    def _add_floor_and_ceiling(self, pts: list[tuple[float, float]], height: float) -> None:
        floor_color = (0.38, 0.46, 0.52, 0.32)
        ceiling_color = (0.78, 0.82, 0.86, 0.18)
        self._add_polygon_mesh([(x, y, 0.0) for x, y in pts], floor_color, (0.16, 0.20, 0.24, 1.0))
        self._add_polygon_mesh([(x, y, height) for x, y in pts], ceiling_color, (0.42, 0.46, 0.50, 1.0))

    def _add_walls(self, pts: list[tuple[float, float]], height: float) -> None:
        for i, (x0, y0) in enumerate(pts):
            x1, y1 = pts[(i + 1) % len(pts)]
            verts = [(x0, y0, 0.0), (x1, y1, 0.0), (x1, y1, height), (x0, y0, height)]
            self._add_polygon_mesh(verts, (0.72, 0.75, 0.76, 0.50), (0.22, 0.24, 0.26, 1.0))

    def _add_element_markers(self, elements: list, height: float) -> None:
        for e in elements:
            if None in (getattr(e, "x0_m", None), getattr(e, "y0_m", None), getattr(e, "x1_m", None), getattr(e, "y1_m", None)):
                continue
            z = min(height * 0.55, max(0.15, float(getattr(e, "height_m", 1.0) or 1.0)))
            color = (0.06, 0.55, 0.82, 1.0) if str(getattr(e, "element_type", "")).lower() == "fenster" else (0.86, 0.45, 0.18, 1.0)
            self._add_line((float(e.x0_m), float(e.y0_m), z), (float(e.x1_m), float(e.y1_m), z), color=color, width=4.0)

    def _add_polygon_mesh(self, pts3: list[tuple[float, float, float]], color, edge) -> None:
        if len(pts3) < 3:
            return
        verts = np.array(pts3, dtype=float)
        faces = np.array([(0, i, i + 1) for i in range(1, len(pts3) - 1)], dtype=int)
        mesh = gl.MeshData(vertexes=verts, faces=faces)
        item = gl.GLMeshItem(meshdata=mesh, smooth=False, shader="shaded", drawEdges=True, edgeColor=edge, color=color)
        self._view.addItem(item)
        self._items.append(item)

    def _add_line(self, p1, p2, *, color=(0.2, 0.2, 0.2, 1.0), width=2.0) -> None:
        arr = np.array([[float(v) for v in p1], [float(v) for v in p2]], dtype=float)
        item = gl.GLLinePlotItem(pos=arr, color=color, width=width, antialias=True, mode="lines")
        self._view.addItem(item)
        self._items.append(item)

    def _frame_camera(self, pts: list[tuple[float, float]], height: float) -> None:
        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        cx = 0.5 * (min(xs) + max(xs))
        cy = 0.5 * (min(ys) + max(ys))
        span = max(max(xs) - min(xs), max(ys) - min(ys), height, 1.0)
        self._view.pan(cx, cy, height * 0.45)
        self._view.opts["distance"] = max(4.0, span * 2.4)
