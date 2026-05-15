from __future__ import annotations

import math
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QMessageBox

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    import pyqtgraph.opengl as gl
except Exception:  # pragma: no cover
    gl = None


class Shell3DDialog(QDialog):
    """OpenGL shell viewer for exterior walls, openings and roof facets."""

    def __init__(self, scene_data: dict, parent=None):
        super().__init__(parent)
        self.scene_data = dict(scene_data or {})
        self.setWindowTitle(str(self.scene_data.get("title", "3D Gebäudehülle")))
        self.resize(1280, 860)
        lay = QVBoxLayout(self)
        if gl is None or np is None:
            QMessageBox.warning(self, "3D Gebäudehülle", "pyqtgraph.opengl / numpy ist nicht verfügbar.")
            self._view = None
        else:
            self._view = gl.GLViewWidget(self)
            self._view.setObjectName("shell3DOpenGLView")
            self._view.opts["distance"] = float(self.scene_data.get("camera_distance", 24.0) or 24.0)
            self._view.opts["elevation"] = 18
            self._view.opts["azimuth"] = -52
            lay.addWidget(self._view, 1)
            self._build_scene()
        btn = QPushButton("Schließen")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)

    @staticmethod
    def is_available() -> bool:
        return gl is not None and np is not None

    def _build_scene(self) -> None:
        if self._view is None:
            return
        grid = gl.GLGridItem()
        grid.setSize(x=40, y=40)
        grid.setSpacing(x=1.0, y=1.0)
        self._view.addItem(grid)
        all_pts = []
        for item in list(self.scene_data.get("walls", []) or []):
            all_pts.extend(self._add_wall_segments(item))
        for face in list(self.scene_data.get("roof_faces", []) or []):
            all_pts.extend(self._add_roof_face(face))
        for line in list(self.scene_data.get("roof_lines", []) or []):
            self._add_line(line.get("p1"), line.get("p2"), width=float(line.get("width", 2.0) or 2.0), color=tuple(line.get("color", (0.18, 0.18, 0.18, 1.0))))
            if line.get("p1"):
                all_pts.append(tuple(float(v) for v in line["p1"]))
            if line.get("p2"):
                all_pts.append(tuple(float(v) for v in line["p2"]))
        if all_pts:
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            zs = [p[2] for p in all_pts]
            cx = 0.5 * (min(xs) + max(xs))
            cy = 0.5 * (min(ys) + max(ys))
            cz = 0.5 * (min(zs) + max(zs))
            span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0)
            self._view.pan(cx, cy, cz)
            self._view.opts["distance"] = max(float(self._view.opts.get("distance", 24.0)), span * 2.2)

    def _add_wall_segments(self, item: dict):
        pts = []
        p0 = item.get("p0")
        p1 = item.get("p1")
        thickness = float(item.get("thickness_m", 0.30) or 0.30)
        color = tuple(item.get("color", (0.83, 0.84, 0.86, 1.0)))
        edge = tuple(item.get("edge", (0.35, 0.36, 0.38, 1.0)))
        poly_sign = float(item.get("poly_sign", 1.0) or 1.0)
        z0 = float(item.get("z0", 0.0) or 0.0)
        z1 = float(item.get("z1", 2.5) or 2.5)
        if not p0 or not p1 or z1 <= z0 + 1e-9:
            return pts
        dx = float(p1[0]) - float(p0[0])
        dy = float(p1[1]) - float(p0[1])
        L = math.hypot(dx, dy)
        if L <= 1e-9:
            return pts
        if poly_sign >= 0.0:
            nx, ny = dy / L, -dx / L
        else:
            nx, ny = -dy / L, dx / L
        openings = sorted(list(item.get("openings", []) or []), key=lambda o: (float(o.get("start", 0.0) or 0.0), float(o.get("end", 0.0) or 0.0)))
        cuts = [0.0, L]
        for op in openings:
            cuts.extend([max(0.0, min(L, float(op.get("start", 0.0) or 0.0))), max(0.0, min(L, float(op.get("end", 0.0) or 0.0)))])
        cuts = sorted({round(v, 6) for v in cuts})
        spans = [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1) if cuts[i + 1] - cuts[i] > 1e-6]
        for a, b in spans:
            mid = 0.5 * (a + b)
            active = None
            for op in openings:
                if float(op.get("start", 0.0) or 0.0) - 1e-6 <= mid <= float(op.get("end", 0.0) or 0.0) + 1e-6:
                    active = op
                    break
            if active is None:
                pts.extend(self._add_wall_box(p0, p1, a, b, z0, z1, thickness, nx, ny, color, edge))
                continue
            sill = max(z0, min(z1, float(active.get("sill", 0.0) or 0.0)))
            top = max(z0, min(z1, float(active.get("top", z1) or z1)))
            if sill > z0 + 1e-6:
                pts.extend(self._add_wall_box(p0, p1, a, b, z0, sill, thickness, nx, ny, color, edge))
            if top < z1 - 1e-6:
                pts.extend(self._add_wall_box(p0, p1, a, b, top, z1, thickness, nx, ny, color, edge))
            reveal_color = (0.58, 0.80, 0.98, 0.42) if str(active.get("type", "window")).lower() != "door" else (0.66, 0.48, 0.28, 0.92)
            pts.extend(self._add_opening_reveals(p0, p1, a, b, sill, top, thickness, nx, ny, reveal_color))
        return pts

    def _segment_points(self, p0, p1, s0: float, s1: float):
        dx = float(p1[0]) - float(p0[0])
        dy = float(p1[1]) - float(p0[1])
        L = max(1e-9, math.hypot(dx, dy))
        t0 = s0 / L
        t1 = s1 / L
        a = (float(p0[0]) + dx * t0, float(p0[1]) + dy * t0)
        b = (float(p0[0]) + dx * t1, float(p0[1]) + dy * t1)
        return a, b

    def _box_vertices(self, a2, b2, z0: float, z1: float, th: float, nx: float, ny: float):
        ox, oy = nx * th, ny * th
        a_in = (a2[0], a2[1])
        b_in = (b2[0], b2[1])
        a_out = (a2[0] + ox, a2[1] + oy)
        b_out = (b2[0] + ox, b2[1] + oy)
        return [
            (a_in[0], a_in[1], z0), (b_in[0], b_in[1], z0), (b_in[0], b_in[1], z1), (a_in[0], a_in[1], z1),
            (a_out[0], a_out[1], z0), (b_out[0], b_out[1], z0), (b_out[0], b_out[1], z1), (a_out[0], a_out[1], z1),
        ]

    def _faces_for_box(self):
        return [
            (0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
            (0, 4, 7), (0, 7, 3), (1, 5, 6), (1, 6, 2),
            (3, 2, 6), (3, 6, 7), (0, 1, 5), (0, 5, 4),
        ]

    def _add_wall_box(self, p0, p1, s0: float, s1: float, z0: float, z1: float, thickness: float, nx: float, ny: float, color, edge):
        a2, b2 = self._segment_points(p0, p1, s0, s1)
        verts = self._box_vertices(a2, b2, z0, z1, thickness, nx, ny)
        self._add_mesh(verts, self._faces_for_box(), color, edge)
        return verts

    def _add_opening_reveals(self, p0, p1, s0: float, s1: float, z0: float, z1: float, thickness: float, nx: float, ny: float, color):
        a2, b2 = self._segment_points(p0, p1, s0, s1)
        self._add_line((a2[0], a2[1], z0), (a2[0], a2[1], z1), color=color, width=2.0)
        self._add_line((b2[0], b2[1], z0), (b2[0], b2[1], z1), color=color, width=2.0)
        self._add_line((a2[0] + nx * thickness, a2[1] + ny * thickness, z0), (a2[0] + nx * thickness, a2[1] + ny * thickness, z1), color=color, width=2.0)
        self._add_line((b2[0] + nx * thickness, b2[1] + ny * thickness, z0), (b2[0] + nx * thickness, b2[1] + ny * thickness, z1), color=color, width=2.0)
        self._add_line((a2[0], a2[1], z0), (b2[0], b2[1], z0), color=color, width=2.0)
        self._add_line((a2[0], a2[1], z1), (b2[0], b2[1], z1), color=color, width=2.0)
        self._add_line((a2[0] + nx * thickness, a2[1] + ny * thickness, z0), (b2[0] + nx * thickness, b2[1] + ny * thickness, z0), color=color, width=2.0)
        self._add_line((a2[0] + nx * thickness, a2[1] + ny * thickness, z1), (b2[0] + nx * thickness, b2[1] + ny * thickness, z1), color=color, width=2.0)
        return [
            (a2[0], a2[1], z0), (a2[0], a2[1], z1), (b2[0], b2[1], z0), (b2[0], b2[1], z1),
            (a2[0] + nx * thickness, a2[1] + ny * thickness, z0), (a2[0] + nx * thickness, a2[1] + ny * thickness, z1),
            (b2[0] + nx * thickness, b2[1] + ny * thickness, z0), (b2[0] + nx * thickness, b2[1] + ny * thickness, z1),
        ]

    def _add_roof_face(self, face: dict):
        pts = [tuple(float(v) for v in p) for p in list(face.get("points", []) or [])]
        if len(pts) < 3:
            return []
        verts = np.array(pts, dtype=float)
        faces = [(0, i, i + 1) for i in range(1, len(pts) - 1)]
        self._add_mesh(verts, faces, tuple(face.get("color", (0.74, 0.24, 0.15, 1.0))), tuple(face.get("edge", (0.30, 0.10, 0.08, 1.0))))
        return pts

    def _add_mesh(self, vertices, faces, color, edge):
        if self._view is None or gl is None or np is None:
            return
        verts = np.array(vertices, dtype=float)
        face_arr = np.array(list(faces), dtype=int)
        md = gl.MeshData(vertexes=verts, faces=face_arr)
        item = gl.GLMeshItem(meshdata=md, smooth=False, shader="shaded", drawEdges=True, edgeColor=edge, color=color)
        self._view.addItem(item)

    def _add_line(self, p1, p2, *, color=(0.2, 0.2, 0.2, 1.0), width=2.0):
        if self._view is None or gl is None or np is None or p1 is None or p2 is None:
            return
        arr = np.array([[float(v) for v in p1], [float(v) for v in p2]], dtype=float)
        item = gl.GLLinePlotItem(pos=arr, color=color, width=width, antialias=True, mode="lines")
        self._view.addItem(item)
