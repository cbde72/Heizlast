import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from ..domain.models import RoomModel
from ..core.geometry import orthogonalize_points, serialize_polygon_m, validate_orthogonal_polygon, simplify_orthogonal_polygon, room_polygon, merge_room_polygons, subtract_room_polygons, split_room_polygon
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QMessageBox, QVBoxLayout, QPushButton

try:
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
except Exception:
    plt = None
    Figure = None
    FigureCanvas = None
    Poly3DCollection = None
from .graphics import PX_PER_M
from .graphics import snap_m
from .graphics import RoomRectItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QPen,QBrush
from PySide6.QtWidgets import QVBoxLayout

from PySide6.QtCore import QPointF

from ..domain.models import ElementModel, RoomModel

class MainWindowMiscMixin:
    def _meta_parse_any(self, meta: str) -> tuple[dict, str]:
        """Parst meta entweder als JSON-Objekt ('{...}') oder als Pipe-Format 'k=v|k2=v2'.
        Returns (dict, fmt) with fmt in {'json','pipe'} and preserves arbitrary keys.
        """
        s = (meta or "").strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                d = json.loads(s)
                if isinstance(d, dict):
                    return {str(k): ("" if v is None else str(v)) for k, v in d.items()}, "json"
            except Exception:
                pass

        d: dict = {}
        for part in (meta or "").split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k:
                    d[k] = v
        return d, "pipe"

    def _meta_dump_any(self, d: dict, fmt: str) -> str:
        """Serialisiert meta-dict zurück ins ursprüngliche Format (JSON oder Pipe)."""
        if fmt == "json":
            return json.dumps(d, ensure_ascii=False, sort_keys=True, indent=2)

        parts = []
        for k, v in d.items():
            if v is None:
                continue
            ks = str(k).strip().replace("|", "/").replace("\n", " ").replace("\r", " ")
            vs = str(v).strip().replace("|", "/").replace("\n", " ").replace("\r", " ")
            if ks:
                parts.append(f"{ks}={vs}")
        return "|".join(parts)
        #

    def _is_auto_deck(self, e) -> bool:
        et = (str(getattr(e, "element_type", "") or "")).lower()
        uid = str(getattr(e, "uid", "") or "")
        # Auto-Decken typischerweise auto_* und enthält decke/geschoss/keller
        if not uid.startswith("auto_"):
            return False
        return ("decke" in et) or ("geschoss" in et) or ("keller" in et)

    def _snapshot_auto_deck_overrides(self) -> dict:
        """Merkt ov_* Overrides (aus meta) für Auto-Decken, damit ensure_auto_decks sie nicht 'wegsetzt'."""
        snap = {}
        for e in self.elements:
            if not self._is_auto_deck(e):
                continue
            parts = self._parse_meta(getattr(e, "meta", "") or "")
            ov = {k: v for k, v in parts.items() if k.startswith("ov_")}
            if not ov:
                continue
            key = (str(getattr(e, "room_id", "") or ""), (str(getattr(e, "element_type", "") or "")).lower())
            snap[key] = ov
        return snap
    #

    def _restore_auto_deck_overrides(self, snap: dict) -> None:
        """Schreibt ov_* wieder in meta und wendet sie direkt an (U/A/H/L/Typ etc.)."""
        if not snap:
            return
        apply = getattr(self.metrics, "_apply_overrides_from_meta", None) if hasattr(self, "metrics") else None

        for e in self.elements:
            if not self._is_auto_deck(e):
                continue
            key = (str(getattr(e, "room_id", "") or ""), (str(getattr(e, "element_type", "") or "")).lower())
            ov = snap.get(key)
            if not ov:
                continue
            parts = self._parse_meta(getattr(e, "meta", "") or "")
            parts.update(ov)
            e.meta = self._format_meta(parts)

            # sofort im Modell wirksam machen (damit GUI/Report stimmt)
            if callable(apply):
                try:
                    apply(e)
                except Exception:
                    pass
    #

    def _meta_parse(self, meta: str) -> dict:
        """Parst meta im Format 'k=v|k2=v2' zu dict."""
        d = {}
        for part in (meta or "").split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k:
                    d[k] = v
        return d

    def _collect_outer_polygons_by_floor(self) -> dict:
        """
        Liefert je Geschoss eine einfache Außenkontur als Polygonliste.
        Fallback-Implementierung auf Basis der Raum-Umhüllung, damit die 3D-Ansicht
        auch dann nicht abstürzt, wenn keine spezialisierte Kontur-Funktion vorhanden ist.
        Format: {"EG": [[(x,y), ...]], ...}
        """
        poly_by_floor: dict = {}
        rooms = getattr(self, "rooms", {}) or {}
        for floor in ("KG", "EG", "DG"):
            rs = [r for r in rooms.values() if getattr(r, "floor", None) == floor]
            if not rs:
                continue
            min_x = min(float(r.x_m) for r in rs)
            min_y = min(float(r.y_m) for r in rs)
            max_x = max(float(r.x_m) + float(r.w_m) for r in rs)
            max_y = max(float(r.y_m) + float(r.h_m) for r in rs)
            poly_by_floor[floor] = [[
                (min_x, min_y),
                (max_x, min_y),
                (max_x, max_y),
                (min_x, max_y),
            ]]
        return poly_by_floor

    def _collect_floor_heights(self) -> dict:
        heights = {}
        rooms = getattr(self, "rooms", {}) or {}
        for floor in ("KG", "EG", "DG"):
            rs = [r for r in rooms.values() if getattr(r, "floor", None) == floor]
            if not rs:
                continue
            vals = [float(getattr(r, "height_m", 2.5) or 2.5) for r in rs]
            heights[floor] = max(vals) if vals else 2.5
        return heights

    def _floor_z_offsets(self, heights: dict) -> dict:
        z = {}
        current = 0.0
        for floor in ("KG", "EG", "DG"):
            z[floor] = current
            current += float(heights.get(floor, 2.5) or 2.5)
        return z

    def _plot_3d_skin_and_lines(self, ax, poly_by_floor: dict, heights: dict, z_base: dict) -> None:
        if Poly3DCollection is None:
            return

        all_x = []
        all_y = []
        all_z = []

        for floor, polys in poly_by_floor.items():
            h = float(heights.get(floor, 2.5) or 2.5)
            z0 = float(z_base.get(floor, 0.0) or 0.0)
            z1 = z0 + h

            for poly in polys:
                if len(poly) < 3:
                    continue
                pts = [(float(x), float(y)) for x, y in poly]
                roof = [(x, y, z1) for x, y in pts]
                base = [(x, y, z0) for x, y in pts]

                ax.add_collection3d(Poly3DCollection([roof], alpha=0.15))
                ax.add_collection3d(Poly3DCollection([base], alpha=0.08))

                for i in range(len(pts)):
                    x0, y0 = pts[i]
                    x1, y1 = pts[(i + 1) % len(pts)]
                    wall = [[(x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1)]]
                    ax.add_collection3d(Poly3DCollection(wall, alpha=0.12))
                    ax.plot([x0, x1], [y0, y1], [z0, z0])
                    ax.plot([x0, x1], [y0, y1], [z1, z1])
                    ax.plot([x0, x0], [y0, y0], [z0, z1])

                all_x.extend([p[0] for p in pts])
                all_y.extend([p[1] for p in pts])
                all_z.extend([z0, z1])

        if all_x and all_y and all_z:
            ax.set_xlim(min(all_x), max(all_x))
            ax.set_ylim(min(all_y), max(all_y))
            ax.set_zlim(min(all_z), max(all_z))

        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_zlabel("z [m]")
        ax.set_title("3D Hausansicht")

    def _on_show_3d_house(self) -> None:
        if plt is None or FigureCanvas is None or Poly3DCollection is None:
            QMessageBox.warning(self, "3D Ansicht", "matplotlib/QtAgg ist nicht verfügbar.")
            return

        poly_by_floor = self._collect_outer_polygons_by_floor()
        if not poly_by_floor:
            QMessageBox.warning(
                self, "3D Ansicht",
                "Keine EG-Außenkontur gefunden. Bitte erst 'Auto-Wände neu (All)' ausführen "
                "und sicherstellen, dass Außenwände Geometrie + auto_contour-Meta haben."
            )
            return

        heights = self._collect_floor_heights()
        z_base = self._floor_z_offsets(heights)

        dlg = QDialog(self)
        dlg.setWindowTitle("3D Hausansicht (Skin + Linien)")
        lay = QVBoxLayout(dlg)

        fig = Figure(figsize=(10, 6))
        canvas = FigureCanvas(fig)
        lay.addWidget(canvas)

        ax = fig.add_subplot(111, projection="3d")
        self._plot_3d_skin_and_lines(ax, poly_by_floor, heights, z_base)

        fig.tight_layout()
        canvas.draw()

        btn = QPushButton("Schließen")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn)

        dlg.resize(1100, 750)
        dlg.exec()

    def _set_room_draw_tool(self, tool: str | None):
        tool = tool or "rect"
        self._draw_tool = tool
        self._room_draw_mode = tool in {"rect", "l", "poly"}
        self._polygon_room_mode = tool == "poly"
        self._l_room_mode = tool == "l"
        self._split_room_mode = tool == "split"
        if getattr(self, 'act_rect_room', None) is not None and tool != 'rect':
            self.act_rect_room.setChecked(False)
        if getattr(self, 'act_l_room', None) is not None and tool != 'l':
            self.act_l_room.setChecked(False)
        if getattr(self, 'act_polygon_room', None) is not None and tool != 'poly':
            self.act_polygon_room.setChecked(False)
        if getattr(self, 'act_split_room', None) is not None and tool != 'split':
            self.act_split_room.setChecked(False)
        if getattr(self, 'act_add_window', None) is not None and self._room_draw_mode:
            self.act_add_window.setChecked(False)
            self._add_window_mode = False
        self._cancel_polygon_room_preview()
        self._cancel_l_room_preview()
        self._cancel_split_preview()

    def _on_draw_floorplan(self):
        self._set_room_draw_tool('rect')
        if getattr(self, 'act_rect_room', None) is not None:
            self.act_rect_room.setChecked(True)
        try:
            self.statusBar().showMessage('Grundriss zeichnen aktiv: Rechteck-Raum', 4000)
        except Exception:
            pass

    def _on_toggle_rect_room_mode(self, checked=False):
        self._set_room_draw_tool('rect' if checked else None)

    def _on_toggle_l_room_mode(self, checked=False):
        self._set_room_draw_tool('l' if checked else None)

    def _on_toggle_split_room_mode(self, checked=False):
        self._set_room_draw_tool('split' if checked else None)

    def _current_floor_room_items(self, floor: str):
        return [it for rid, it in getattr(self, 'room_items', {}).items() if getattr(getattr(it, 'model', None), 'floor', None) == floor]

    def _snap_scene_point_for_drawing(self, floor: str, scene_pt: QPointF) -> QPointF:
        x_m = snap_m(scene_pt.x() / PX_PER_M)
        y_m = snap_m(scene_pt.y() / PX_PER_M)
        best = QPointF(x_m * PX_PER_M, y_m * PX_PER_M)
        best_dist = 0.20
        for it in self._current_floor_room_items(floor):
            room = getattr(it, 'model', None)
            if room is None:
                continue
            pts = room_polygon(room)
            for x, y in pts:
                d = ((x - x_m) ** 2 + (y - y_m) ** 2) ** 0.5
                if d < best_dist:
                    best_dist = d
                    best = QPointF(x * PX_PER_M, y * PX_PER_M)
            xs = sorted(set(round(x, 6) for x, _ in pts))
            ys = sorted(set(round(y, 6) for _, y in pts))
            for x in xs:
                d = abs(x - x_m)
                if d < best_dist:
                    best_dist = d
                    best = QPointF(x * PX_PER_M, best.y())
            for y in ys:
                d = abs(y - y_m)
                if d < best_dist:
                    best_dist = d
                    best = QPointF(best.x(), y * PX_PER_M)
        return best

    def _create_room_from_polygon(self, floor: str, pts_m: list[tuple[float, float]], select: bool = True):
        pts_m = simplify_orthogonal_polygon([(snap_m(x), snap_m(y)) for x, y in pts_m])
        if not validate_orthogonal_polygon(pts_m):
            return None
        rid = self._new_room_id(floor)
        xs = [x for x, _ in pts_m]; ys = [y for _, y in pts_m]
        r = RoomModel(id=rid, floor=floor, name=rid, x_m=min(xs), y_m=min(ys), w_m=max(xs)-min(xs), h_m=max(ys)-min(ys), polygon_m=serialize_polygon_m(pts_m))
        self._normalize_room_geometry(r)
        self.rooms[rid] = r
        self._rebuild_all_graphics()
        if select:
            it = self.room_items.get(rid)
            if it is not None:
                try:
                    sc = it.scene()
                    if sc is not None:
                        sc.clearSelection()
                    it.setSelected(True)
                except Exception:
                    pass
            self._selected_room_id = rid
            self._populate_room_form()
        return r

    def _cancel_l_room_preview(self):
        self._l_room_points_scene = []
        try:
            if getattr(self, '_preview_polygon', None) is not None:
                self._safe_remove_from_scene(self._preview_polygon)
        except Exception:
            pass
        self._preview_polygon = None

    def _cancel_split_preview(self):
        self._split_start_scene = None
        try:
            if getattr(self, '_preview_split_line', None) is not None:
                self._safe_remove_from_scene(self._preview_split_line)
        except Exception:
            pass
        self._preview_split_line = None

    def _build_l_room_polygon(self, pts_scene: list[QPointF]) -> list[tuple[float, float]]:
        if len(pts_scene) < 3:
            return []
        p0, p1, p2 = pts_scene[:3]
        x0, y0 = p0.x() / PX_PER_M, p0.y() / PX_PER_M
        x1, y1 = p1.x() / PX_PER_M, p1.y() / PX_PER_M
        x2, y2 = p2.x() / PX_PER_M, p2.y() / PX_PER_M
        min_x, max_x = sorted((snap_m(x0), snap_m(x1)))
        min_y, max_y = sorted((snap_m(y0), snap_m(y1)))
        ix = min(max(snap_m(x2), min_x + 0.05), max_x - 0.05)
        iy = min(max(snap_m(y2), min_y + 0.05), max_y - 0.05)
        # notch in quadrant nearest to p2
        left = abs(ix - min_x) < abs(ix - max_x)
        top = abs(iy - min_y) < abs(iy - max_y)
        if left and top:
            pts = [(min_x, min_y), (max_x, min_y), (max_x, iy), (ix, iy), (ix, max_y), (min_x, max_y)]
        elif (not left) and top:
            pts = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (ix, max_y), (ix, iy), (min_x, iy)]
        elif left and (not top):
            pts = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y), (min_x, iy), (ix, iy)]
        else:
            pts = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (ix, max_y), (ix, iy), (min_x, iy)]
        pts = simplify_orthogonal_polygon(pts)
        return pts

    def _finish_l_room(self, floor: str):
        pts = self._build_l_room_polygon(self._l_room_points_scene)
        self._cancel_l_room_preview()
        if len(pts) < 4:
            return True
        self._create_room_from_polygon(floor, pts)
        return True

    def _selected_room_ids(self) -> list[str]:
        out = []
        for rid, it in getattr(self, 'room_items', {}).items():
            try:
                if it.isSelected():
                    out.append(rid)
            except Exception:
                pass
        if not out and getattr(self, '_selected_room_id', None):
            out = [self._selected_room_id]
        return out

    def _on_merge_selected_rooms(self):
        ids = self._selected_room_ids()
        if len(ids) < 2:
            try: self.statusBar().showMessage('Bitte mindestens zwei Räume zum Verschmelzen selektieren.', 4000)
            except Exception: pass
            return
        rooms = [self.rooms[rid] for rid in ids if rid in self.rooms]
        floors = {r.floor for r in rooms}
        if len(floors) != 1:
            return
        merged = merge_room_polygons([room_polygon(r) for r in rooms])
        if not validate_orthogonal_polygon(merged):
            return
        keep = rooms[0]
        for r in rooms[1:]:
            self.rooms.pop(r.id, None)
        keep.set_polygon_points(merged)
        self._normalize_room_geometry(keep)
        self._rebuild_all_graphics()

    def _on_subtract_selected_rooms(self):
        ids = self._selected_room_ids()
        if len(ids) < 2:
            try: self.statusBar().showMessage('Bitte zuerst den Basisraum, dann die abzuziehenden Räume selektieren.', 4000)
            except Exception: pass
            return
        rooms = [self.rooms[rid] for rid in ids if rid in self.rooms]
        floors = {r.floor for r in rooms}
        if len(floors) != 1:
            return
        base = rooms[0]
        result = subtract_room_polygons(room_polygon(base), [room_polygon(r) for r in rooms[1:]])
        if not validate_orthogonal_polygon(result):
            try: self.statusBar().showMessage('Subtraktion ergab keine gültige orthogonale Restfläche.', 5000)
            except Exception: pass
            return
        for r in rooms[1:]:
            self.rooms.pop(r.id, None)
        base.set_polygon_points(result)
        self._normalize_room_geometry(base)
        self._rebuild_all_graphics()

    def _on_toggle_polygon_room_mode(self, checked=False):
        self._set_room_draw_tool('poly' if checked else None)

    def _cancel_polygon_room_preview(self):
        try:
            if getattr(self, '_preview_polygon', None) is not None:
                self._safe_remove_from_scene(self._preview_polygon)
        except Exception:
            pass
        self._preview_polygon = None
        self._polygon_points_scene = []

    def _update_polygon_room_preview(self, scene, current_pos=None):
        pts = list(getattr(self, '_polygon_points_scene', []) or [])
        if current_pos is not None and pts:
            last = pts[-1]
            dx = current_pos.x() - last.x()
            dy = current_pos.y() - last.y()
            if abs(dx) >= abs(dy):
                current_pos = QPointF(current_pos.x(), last.y())
            else:
                current_pos = QPointF(last.x(), current_pos.y())
            pts.append(current_pos)
        if len(pts) < 2:
            return
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        if self._preview_polygon is None:
            self._preview_polygon = scene.addPath(path, QPen(Qt.darkGray, 1, Qt.DashLine), QBrush(Qt.transparent))
            self._preview_polygon.setZValue(100)
        else:
            self._preview_polygon.setPath(path)

    def _finish_polygon_room(self, floor: str):
        pts_scene = [(p.x() / PX_PER_M, p.y() / PX_PER_M) for p in (self._polygon_points_scene or [])]
        pts_scene = orthogonalize_points([(snap_m(x), snap_m(y)) for x, y in pts_scene])
        self._cancel_polygon_room_preview()
        if len(pts_scene) < 3:
            return True
        if pts_scene[0] == pts_scene[-1]:
            pts_scene = pts_scene[:-1]
        self._create_room_from_polygon(floor, pts_scene)
        return True

    def eventFilter(self, obj, event):
        """Filtert Mausereignisse für das Zeichnen von Räumen und Einfügen von Fenstern."""
        if event.type() not in (event.Type.MouseButtonPress, event.Type.MouseMove, event.Type.MouseButtonRelease, event.Type.MouseButtonDblClick):
            return super().eventFilter(obj, event)

        view = (self.view_KG if obj is self.view_KG.viewport() else (self.view_EG if obj is self.view_EG.viewport() else (self.view_DG if obj is self.view_DG.viewport() else None)))
        if view is None:
            return super().eventFilter(obj, event)

        scene, floor = ((self.scene_KG, "KG") if view is self.view_KG else ((self.scene_EG, "EG") if view is self.view_EG else (self.scene_DG, "DG")))

        if event.type() == event.Type.MouseButtonPress:
            if event.button() == Qt.LeftButton and self._add_window_mode and not (event.modifiers() & Qt.ShiftModifier):
                p = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                self._add_window_at(floor, p)
                return True

            if self._polygon_room_mode:
                p = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                if event.button() == Qt.LeftButton:
                    if self._polygon_points_scene:
                        last = self._polygon_points_scene[-1]
                        dx = p.x() - last.x(); dy = p.y() - last.y()
                        if abs(dx) >= abs(dy):
                            p = QPointF(p.x(), last.y())
                        else:
                            p = QPointF(last.x(), p.y())
                    self._polygon_points_scene.append(p)
                    self._update_polygon_room_preview(scene)
                    return True
                if event.button() == Qt.RightButton:
                    return self._finish_polygon_room(floor)

            if self._l_room_mode:
                p = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                if event.button() == Qt.LeftButton:
                    self._l_room_points_scene.append(p)
                    if len(self._l_room_points_scene) >= 3:
                        return self._finish_l_room(floor)
                    self._update_polygon_room_preview(scene, p)
                    return True
                if event.button() == Qt.RightButton:
                    self._cancel_l_room_preview()
                    return True

            if self._split_room_mode and event.button() == Qt.LeftButton:
                p0 = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                self._split_start_scene = (floor, p0)
                self._preview_split_line = scene.addLine(p0.x(), p0.y(), p0.x(), p0.y(), QPen(Qt.darkGreen, 2, Qt.DashLine))
                self._preview_split_line.setZValue(120)
                return True

            if event.button() == Qt.LeftButton and (self._draw_tool == 'rect' or (event.modifiers() & Qt.ShiftModifier)):
                p0 = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                self._start_pos_scene = (floor, p0)
                from PySide6.QtWidgets import QGraphicsRectItem
                self._preview_room = scene.addRect(0, 0, 1, 1, QPen(Qt.darkGray, 1, Qt.DashLine), QBrush(Qt.transparent))
                self._preview_room.setZValue(100)
                return True

        if event.type() == event.Type.MouseMove:
            if self._polygon_room_mode and self._polygon_points_scene:
                p1 = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                self._update_polygon_room_preview(scene, p1)
                return True
            if self._l_room_mode and self._l_room_points_scene:
                p1 = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                pts = list(self._l_room_points_scene)
                if len(pts) == 1:
                    self._update_polygon_room_preview(scene, p1)
                else:
                    pts = pts + [p1]
                    poly = self._build_l_room_polygon(pts)
                    if poly:
                        qpts = [QPointF(x * PX_PER_M, y * PX_PER_M) for x, y in poly]
                        self._polygon_points_scene = qpts
                        self._update_polygon_room_preview(scene)
                return True
            if self._split_start_scene and self._preview_split_line:
                f0, p0 = self._split_start_scene
                if f0 != floor:
                    return True
                p1 = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                dx = p1.x() - p0.x(); dy = p1.y() - p0.y()
                if abs(dx) >= abs(dy):
                    p1 = QPointF(p1.x(), p0.y())
                else:
                    p1 = QPointF(p0.x(), p1.y())
                self._preview_split_line.setLine(p0.x(), p0.y(), p1.x(), p1.y())
                return True
            if self._start_pos_scene and self._preview_room:
                f0, p0 = self._start_pos_scene
                if f0 != floor:
                    return True
                p1 = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                x0 = min(p0.x(), p1.x())
                y0 = min(p0.y(), p1.y())
                x1 = max(p0.x(), p1.x())
                y1 = max(p0.y(), p1.y())
                self._preview_room.setRect(x0, y0, max(1.0, x1 - x0), max(1.0, y1 - y0))
                return True

        if event.type() == event.Type.MouseButtonDblClick:
            if self._polygon_room_mode and event.button() == Qt.LeftButton:
                p = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                if self._polygon_points_scene:
                    last = self._polygon_points_scene[-1]
                    dx = p.x() - last.x(); dy = p.y() - last.y()
                    if abs(dx) >= abs(dy):
                        p = QPointF(p.x(), last.y())
                    else:
                        p = QPointF(last.x(), p.y())
                    self._polygon_points_scene.append(p)
                return self._finish_polygon_room(floor)

        if event.type() == event.Type.MouseButtonRelease:
            if self._split_start_scene and self._preview_split_line:
                f0, p0 = self._split_start_scene
                p1 = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                self._safe_remove_from_scene(self._preview_split_line)
                self._preview_split_line = None
                self._split_start_scene = None
                dx = p1.x() - p0.x(); dy = p1.y() - p0.y()
                orientation = 'v' if abs(dx) >= abs(dy) else 'h'
                coord = (p0.x() if orientation == 'v' else p0.y()) / PX_PER_M
                room = None
                for rid in self._selected_room_ids():
                    cand = self.rooms.get(rid)
                    if cand and cand.floor == floor:
                        room = cand
                        break
                if room is None:
                    return True
                a, b = split_room_polygon(room_polygon(room), orientation, coord)
                if not (validate_orthogonal_polygon(a) and validate_orthogonal_polygon(b)):
                    return True
                room.set_polygon_points(a)
                self._normalize_room_geometry(room)
                self._create_room_from_polygon(floor, b, select=False)
                self._rebuild_all_graphics()
                return True
            if self._start_pos_scene and self._preview_room:
                f0, p0 = self._start_pos_scene
                p1 = self._snap_scene_point_for_drawing(floor, view.mapToScene(event.position().toPoint()))
                self._safe_remove_from_scene(self._preview_room)
                self._preview_room = None
                self._start_pos_scene = None

                x0 = min(p0.x(), p1.x()) / PX_PER_M
                y0 = min(p0.y(), p1.y()) / PX_PER_M
                w = abs(p1.x() - p0.x()) / PX_PER_M
                h = abs(p1.y() - p0.y()) / PX_PER_M
                if w < 0.2 or h < 0.2:
                    return True

                x0 = snap_m(x0)
                y0 = snap_m(y0)
                w = snap_m(w)
                h = snap_m(h)
                pts_rect = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
                self._create_room_from_polygon(floor, pts_rect)
                return True

        return super().eventFilter(obj, event)
    #