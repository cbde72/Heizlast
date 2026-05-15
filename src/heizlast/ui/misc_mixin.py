import json
from ..domain.models import RoomModel
from ..core.geometry import orthogonalize_points, room_polygon
from ..domain.services.room_operation_service import RoomOperationRecord
from ..domain.house_state import HouseState
from ..core.polygon_ops import serialize_polygon_m, validate_orthogonal_polygon, simplify_orthogonal_polygon, snap_m
from ..core.roof_mesh import build_winkeldach_mesh
from ..core.roof_line_geometry import build_roof_facets, estimate_roof_line_extra_area_m2, roof_lines_to_plan_segments
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QVBoxLayout, QPushButton, QMessageBox, QMenu

try:
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
except Exception:
    plt = None
    Figure = None
    FigureCanvas = None
    NavigationToolbar = None
    Poly3DCollection = None
from .graphics import PX_PER_M
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen,QBrush
from PySide6.QtCore import QPointF

from ..domain.models import ElementModel
from .. import APP_NAME, __version__, __internal_version__, PROJECT_SCHEMA_VERSION
from .dialogs.info_dialog import InfoDialog
from .dialogs.wall_elevation_dialog import WallElevationDialog, WallOpeningViewModel
from ..core.wall_openings import wall_openings_for_element
from .gl_3d_shell_dialog import Shell3DDialog
from .shell_2d_dialog import Shell2DDialog

class MainWindowMiscMixin:

    def _is_wall_like_element(self, element: ElementModel) -> bool:
        et = str(getattr(element, "element_type", "") or "").strip().lower()
        return "wand" in et

    def _wall_openings_for_element(self, wall: ElementModel) -> list[WallOpeningViewModel]:
        room = getattr(self, "rooms", {}).get(getattr(wall, "room_id", None))
        openings = wall_openings_for_element(wall, getattr(self, "elements", []) or [], room=room, default_window_sill_m=0.90)
        return [
            WallOpeningViewModel(
                offset_m=float(o.offset_m),
                width_m=float(o.width_m),
                sill_m=float(o.sill_m),
                height_m=float(o.height_m),
                label=str(o.label),
                opening_type=str(o.opening_type),
            )
            for o in openings
        ]


    def _show_wall_elevation_dialog(self, wall: ElementModel) -> None:
        wall_width_m = float(getattr(wall, "length_m", 0.0) or 0.0)
        wall_height_m = float(getattr(wall, "height_m", 0.0) or 0.0)
        if wall_width_m <= 0.0:
            try:
                wall_width_m = float(wall.compute_length() or 0.0)
            except Exception:
                wall_width_m = 0.0
        if wall_height_m <= 0.0:
            room = getattr(self, "rooms", {}).get(getattr(wall, "room_id", None))
            wall_height_m = float(getattr(room, "height_m", 2.50) or 2.50)
        openings = self._wall_openings_for_element(wall)
        title = f"2D-Ansicht – {getattr(wall, 'element_type', 'Wand')} ({getattr(wall, 'floor', '')})"
        dlg = WallElevationDialog(title=title, wall_width_m=wall_width_m, wall_height_m=wall_height_m, openings=openings, parent=self)
        dlg.exec()

    def _handle_plan_context_menu(self, view, event) -> bool:
        scene_pos = view.mapToScene(event.pos())
        item = view.itemAt(event.pos())
        target_element = None
        if item is not None:
            if hasattr(item, "element") and isinstance(getattr(item, "element"), ElementModel):
                target_element = getattr(item, "element")
            elif hasattr(item, "parentItem") and item.parentItem() is not None and hasattr(item.parentItem(), "element") and isinstance(getattr(item.parentItem(), "element"), ElementModel):
                target_element = getattr(item.parentItem(), "element")
        if target_element is None or not self._is_wall_like_element(target_element):
            return False

        try:
            for sc in (getattr(self, "scene_KG", None), getattr(self, "scene_EG", None), getattr(self, "scene_DG", None)):
                if sc is not None:
                    sc.clearSelection()
            item.setSelected(True)
        except Exception:
            pass

        menu = QMenu(view)
        act = menu.addAction("Ansicht")
        chosen = menu.exec(view.mapToGlobal(event.pos()))
        if chosen is act:
            self._show_wall_elevation_dialog(target_element)
            return True
        return bool(chosen is not None)

    def _on_show_info_dialog(self) -> None:
        cfg = getattr(self, "project_cfg", None)
        internal_project_version = getattr(cfg, "internal_project_version", "V13-intern-01")
        dlg = InfoDialog(
            self,
            app_name=APP_NAME,
            app_version=__version__,
            internal_app_version=__internal_version__,
            project_schema_version=PROJECT_SCHEMA_VERSION,
            internal_project_version=internal_project_version,
        )
        dlg.exec()

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
        room_polys = self._collect_room_polygons_by_floor()
        if not room_polys:
            return {}
        poly_by_floor: dict = {}
        for floor, polys in room_polys.items():
            all_pts = [pt for poly in polys for pt in poly]
            if len(all_pts) < 3:
                continue
            xs = [float(p[0]) for p in all_pts]
            ys = [float(p[1]) for p in all_pts]
            min_x = min(xs)
            min_y = min(ys)
            max_x = max(xs)
            max_y = max(ys)
            poly_by_floor[floor] = [[
                (min_x, min_y),
                (max_x, min_y),
                (max_x, max_y),
                (min_x, max_y),
            ]]
        return poly_by_floor

    def _current_roof_type(self) -> str:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        rt = str(getattr(attic, "roof_type", "satteldach") or "satteldach").strip().lower()
        allowed = {"satteldach", "pultdach", "walmdach", "flachdach"}
        return rt if rt in allowed else "satteldach"


    def _current_facade_material(self) -> str:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        material = str(getattr(attic, "facade_material", "klinker") or "klinker").strip().lower()
        allowed = {"klinker", "putz", "holz", "beton"}
        return material if material in allowed else "klinker"

    def _facade_material_display_name(self, material: str) -> str:
        return {"klinker": "Klinker", "putz": "Putz", "holz": "Holz", "beton": "Beton"}.get(str(material or "").lower(), "Klinker")

    def _facade_material_style(self) -> dict:
        material = self._current_facade_material()
        styles = {
            "klinker": {
                "wall_face": (0.70, 0.33, 0.22, 1.0),
                "wall_edge": (0.28, 0.16, 0.11, 0.85),
                "texture": "brick",
                "texture_rows": 10,
            },
            "putz": {
                "wall_face": (0.90, 0.88, 0.82, 1.0),
                "wall_edge": (0.55, 0.53, 0.48, 0.85),
                "texture": "plaster",
                "texture_rows": 9,
            },
            "holz": {
                "wall_face": (0.61, 0.45, 0.28, 1.0),
                "wall_edge": (0.30, 0.21, 0.10, 0.85),
                "texture": "wood",
                "texture_rows": 8,
            },
            "beton": {
                "wall_face": (0.70, 0.71, 0.72, 1.0),
                "wall_edge": (0.36, 0.38, 0.40, 0.85),
                "texture": "concrete",
                "texture_rows": 7,
            },
        }
        style = dict(styles.get(material, styles["klinker"]))
        style["material"] = material
        style["material_name"] = self._facade_material_display_name(material)
        return style

    def _current_roof_material(self) -> str:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        material = str(getattr(attic, "roof_material", "ziegel") or "ziegel").strip().lower()
        allowed = {"ziegel"}
        return material if material in allowed else "ziegel"

    def _roof_material_display_name(self, material: str) -> str:
        return {"ziegel": "Ziegel"}.get(str(material or "").lower(), "Ziegel")

    def _roof_material_style(self) -> dict:
        material = self._current_roof_material()
        style = {"roof_face": (0.74, 0.24, 0.15, 1.0), "roof_edge": (0.30, 0.10, 0.08, 0.95), "material": material, "material_name": self._roof_material_display_name(material)}
        return style

    def _add_roof_texture_lines(self, ax, face, roof_style: dict) -> None:
        if not face or len(face) < 3:
            return
        x0=min(float(p[0]) for p in face); x1=max(float(p[0]) for p in face)
        y0=min(float(p[1]) for p in face); y1=max(float(p[1]) for p in face)
        z0=min(float(p[2]) for p in face); z1=max(float(p[2]) for p in face)
        if abs(x1-x0) < 1e-9 or abs(y1-y0) < 1e-9:
            return
        for r in range(1,9):
            t = r / 9.0
            z = z0 + (z1 - z0) * t
            y = y0 + (y1 - y0) * t
            ax.plot([x0, x1], [y, y], [z, z], linewidth=0.55, alpha=0.35)

    def _roof_display_name(self, roof_type: str) -> str:
        mapping = {
            "satteldach": "Satteldach",
            "pultdach": "Pultdach",
            "walmdach": "Walmdach",
            "krueppelwalmdach": "Krüppelwalmdach",
            "flachdach": "Flachdach",
            "winkeldach": "Winkel-/Kehldach",
        }
        return mapping.get(str(roof_type or "").lower(), "Satteldach")

    def _roof_peak_height(self) -> float:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        if attic is None:
            return 1.0
        width = max(0.5, float(getattr(attic, "building_width_m", 8.0) or 8.0))
        pitch_deg = max(0.0, min(85.0, float(getattr(attic, "roof_pitch_deg", 35.0) or 35.0)))
        roof_type = self._current_roof_type()
        import math
        if roof_type == "flachdach":
            return 0.12
        if roof_type == "pultdach":
            return max(0.2, width * math.tan(math.radians(max(1.0, pitch_deg))))
        return max(0.2, 0.5 * width * math.tan(math.radians(max(1.0, pitch_deg))))

    def _roof_profile_params(self) -> dict:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        return {
            "roof_type": self._current_roof_type(),
            "ridge_orientation": str(getattr(attic, "ridge_orientation", "length") or "length").strip().lower(),
            "roof_overhang_m": max(0.0, float(getattr(attic, "roof_overhang_m", 0.30) or 0.0)),
            "eave_overhang_m": max(0.0, float(getattr(attic, "eave_overhang_m", getattr(attic, "roof_overhang_m", 0.30)) or 0.0)),
            "gable_overhang_m": max(0.0, float(getattr(attic, "gable_overhang_m", getattr(attic, "roof_overhang_m", 0.30)) or 0.0)),
            "ridge_offset_ratio": float(getattr(attic, "ridge_offset_ratio", 0.0) or 0.0),
            "pult_rise_side": str(getattr(attic, "pult_rise_side", "right") or "right").strip().lower(),
            "half_hip_ratio": float(getattr(attic, "half_hip_ratio", 0.45) or 0.45),
        }

    def _add_surface_texture_lines(self, ax, p0, p1, z0: float, z1: float, material: str = "klinker", rows: int = 10) -> None:
        x0, y0 = float(p0[0]), float(p0[1])
        x1, y1 = float(p1[0]), float(p1[1])
        rows = max(4, int(rows))
        dz = (z1 - z0) / rows if rows else (z1 - z0)

        if material == "holz":
            for c in range(9):
                t = c / 8.0
                xb = x0 + (x1 - x0) * t
                yb = y0 + (y1 - y0) * t
                ax.plot([xb, xb], [yb, yb], [z0, z1], linewidth=0.7, alpha=0.18)
            for r in range(0, rows + 1, 2):
                z = z0 + r * dz
                ax.plot([x0, x1], [y0, y1], [z, z], linewidth=0.5, alpha=0.10)
            return

        if material == "putz":
            for r in range(rows + 1):
                z = z0 + r * dz
                ax.plot([x0, x1], [y0, y1], [z, z], linewidth=0.4, alpha=0.08)
            for c in range(5):
                t = c / 4.0
                xb = x0 + (x1 - x0) * t
                yb = y0 + (y1 - y0) * t
                ax.plot([xb, xb], [yb, yb], [z0, z1], linewidth=0.35, alpha=0.06)
            return

        if material == "beton":
            for r in range(0, rows + 1, 2):
                z = z0 + r * dz
                ax.plot([x0, x1], [y0, y1], [z, z], linewidth=0.45, alpha=0.12)
            for c in range(4):
                t = c / 3.0
                xb = x0 + (x1 - x0) * t
                yb = y0 + (y1 - y0) * t
                ax.plot([xb, xb], [yb, yb], [z0, z1], linewidth=0.3, alpha=0.08)
            return

        for r in range(rows + 1):
            z = z0 + r * dz
            ax.plot([x0, x1], [y0, y1], [z, z], linewidth=0.5, alpha=0.28)
        for c in range(7):
            t = c / 6.0
            xb = x0 + (x1 - x0) * t
            yb = y0 + (y1 - y0) * t
            ax.plot([xb, xb], [yb, yb], [z0, z1], linewidth=0.45, alpha=0.18)

    def _build_roof_faces(self, pts: list[tuple[float, float]], z_top: float) -> tuple[list[list[tuple[float, float, float]]], list[tuple[float, float, float]]]:
        if len(pts) < 4:
            return [], []
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        params = self._roof_profile_params()
        roof_type = params["roof_type"]
        ridge_orientation = params["ridge_orientation"]
        overhang = float(params["roof_overhang_m"])
        eave_overhang = float(params.get("eave_overhang_m", overhang))
        gable_overhang = float(params.get("gable_overhang_m", overhang))
        ridge_offset_ratio = max(-0.8, min(0.8, float(params["ridge_offset_ratio"])))
        pult_side = params["pult_rise_side"]

        core_dx = max(1e-9, max_x - min_x)
        core_dy = max(1e-9, max_y - min_y)
        if ridge_orientation == "length":
            ex0, ex1 = min_x - eave_overhang, max_x + eave_overhang
            ey0, ey1 = min_y - gable_overhang, max_y + gable_overhang
        else:
            ex0, ex1 = min_x - gable_overhang, max_x + gable_overhang
            ey0, ey1 = min_y - eave_overhang, max_y + eave_overhang
        peak = z_top + self._roof_peak_height()

        if roof_type == "flachdach":
            return [[(ex0, ey0, z_top + 0.05), (ex1, ey0, z_top + 0.05), (ex1, ey1, z_top + 0.05), (ex0, ey1, z_top + 0.05)]], []

        if roof_type == "winkeldach":
            return build_winkeldach_mesh(pts, z_top=z_top, peak_height_m=self._roof_peak_height(), target_cells=26)

        cross_span = core_dx if ridge_orientation == "length" else core_dy
        along_span = core_dy if ridge_orientation == "length" else core_dx
        ridge_pos = 0.5 * cross_span * (1.0 + ridge_offset_ratio)
        ridge_pos = max(0.10 * cross_span, min(0.90 * cross_span, ridge_pos))
        left_run = max(1e-9, ridge_pos)
        right_run = max(1e-9, cross_span - ridge_pos)
        hip_run = max(1e-9, min(left_run, right_run, 0.5 * along_span)) if roof_type in {"walmdach", "krueppelwalmdach"} else 0.0
        if roof_type == "krueppelwalmdach":
            hip_run *= max(0.05, min(0.95, float(params.get("half_hip_ratio", 0.45))))

        if roof_type == "pultdach":
            if ridge_orientation == "width":
                y_low, y_high = (ey1, ey0) if pult_side == "left" else (ey0, ey1)
                return [[(ex0, y_low, z_top), (ex1, y_low, z_top), (ex1, y_high, peak), (ex0, y_high, peak)]], []
            x_low, x_high = (ex1, ex0) if pult_side == "left" else (ex0, ex1)
            return [[(x_low, ey0, z_top), (x_high, ey0, peak), (x_high, ey1, peak), (x_low, ey1, z_top)]], []

        if ridge_orientation == "width":
            ridge_y = min_y + ridge_pos
            if roof_type in {"walmdach", "krueppelwalmdach"}:
                ridge_x0 = min_x + hip_run
                ridge_x1 = max_x - hip_run
                ridge = [(ridge_x0, ridge_y, peak), (ridge_x1, ridge_y, peak)]
                faces = [
                    [(ex0, ey0, z_top), ridge[0], ridge[1], (ex1, ey0, z_top)],
                    [(ex0, ey1, z_top), ridge[0], ridge[1], (ex1, ey1, z_top)],
                    [(ex0, ey0, z_top), ridge[0], (ex0, ey1, z_top)],
                    [(ex1, ey0, z_top), ridge[1], (ex1, ey1, z_top)],
                ]
                return faces, ridge
            ridge = [(ex0, ridge_y, peak), (ex1, ridge_y, peak)]
            faces = [
                [(ex0, ey0, z_top), (ex1, ey0, z_top), ridge[1], ridge[0]],
                [(ex0, ey1, z_top), (ex1, ey1, z_top), ridge[1], ridge[0]],
            ]
            return faces, ridge

        ridge_x = min_x + ridge_pos
        if roof_type in {"walmdach", "krueppelwalmdach"}:
            ridge_y0 = min_y + hip_run
            ridge_y1 = max_y - hip_run
            ridge = [(ridge_x, ridge_y0, peak), (ridge_x, ridge_y1, peak)]
            faces = [
                [(ex0, ey0, z_top), ridge[0], (ex1, ey0, z_top)],
                [(ex1, ey0, z_top), ridge[1], (ex1, ey1, z_top)],
                [(ex1, ey1, z_top), ridge[1], (ex0, ey1, z_top)],
                [(ex0, ey1, z_top), ridge[0], (ex0, ey0, z_top)],
            ]
            return faces, ridge

        ridge = [(ridge_x, ey0, peak), (ridge_x, ey1, peak)]
        faces = [
            [(ex0, ey0, z_top), ridge[0], ridge[1], (ex0, ey1, z_top)],
            [(ex1, ey0, z_top), ridge[0], ridge[1], (ex1, ey1, z_top)],
        ]
        return faces, ridge
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

    def _roof_line_cfg_items(self):
        cfg = getattr(getattr(self, "project_cfg", None), "attic", None)
        return list(getattr(cfg, "roof_lines", []) or [])

    def _roof_line_segments_for_polygon(self, pts: list[tuple[float, float]]):
        lines = self._roof_line_cfg_items()
        if not lines or not pts:
            return []
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return roof_lines_to_plan_segments(lines, x0_m=min_x, y0_m=min_y, width_m=max(1e-9, max_x - min_x), length_m=max(1e-9, max_y - min_y))

    def _roof_bbox_context(self, pts: list[tuple[float, float]]):
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return min_x, min_y, max_x, max_y, max(1e-9, max_x - min_x), max(1e-9, max_y - min_y)

    def _roof_plan_segments_for_polygon(self, pts: list[tuple[float, float]]):
        segs = []
        min_x, min_y, max_x, max_y, dx, dy = self._roof_bbox_context(pts)
        params = self._roof_profile_params()
        roof_type = self._current_roof_type()
        ridge_orientation = str(params.get("ridge_orientation", "length") or "length").strip().lower()
        ridge_offset_ratio = max(-0.8, min(0.8, float(params.get("ridge_offset_ratio", 0.0) or 0.0)))
        ridge_pos = 0.5 * (dx if ridge_orientation == "length" else dy) * (1.0 + ridge_offset_ratio)
        hip_run = 0.0
        if roof_type in {"walmdach", "krueppelwalmdach"}:
            cross_span = dx if ridge_orientation == "length" else dy
            along_span = dy if ridge_orientation == "length" else dx
            ridge_pos = max(0.10 * cross_span, min(0.90 * cross_span, ridge_pos))
            left_run = max(1e-9, ridge_pos)
            right_run = max(1e-9, cross_span - ridge_pos)
            hip_run = max(1e-9, min(left_run, right_run, 0.5 * along_span))
            if roof_type == "krueppelwalmdach":
                hip_run *= max(0.05, min(0.95, float(params.get("half_hip_ratio", 0.45) or 0.45)))
        if roof_type != "flachdach":
            if ridge_orientation == "width":
                y = min_y + max(0.10 * dy, min(0.90 * dy, ridge_pos))
                p1 = (min_x + hip_run, y)
                p2 = (max_x - hip_run, y)
            else:
                x = min_x + max(0.10 * dx, min(0.90 * dx, ridge_pos))
                p1 = (x, min_y + hip_run)
                p2 = (x, max_y - hip_run)
            segs.append(("first", p1, p2))
        if roof_type in {"walmdach", "krueppelwalmdach"}:
            if ridge_orientation == "width":
                left_ridge, right_ridge = segs[0][1], segs[0][2]
                segs.extend([("grat", (min_x, min_y), left_ridge), ("grat", (max_x, min_y), right_ridge), ("grat", (min_x, max_y), left_ridge), ("grat", (max_x, max_y), right_ridge)])
            else:
                top_ridge, bottom_ridge = segs[0][1], segs[0][2]
                segs.extend([("grat", (min_x, min_y), top_ridge), ("grat", (max_x, min_y), top_ridge), ("grat", (min_x, max_y), bottom_ridge), ("grat", (max_x, max_y), bottom_ridge)])
        segs.extend(self._roof_line_segments_for_polygon(pts))
        return segs

    def _roof_height_for_polygon_point(self, pts: list[tuple[float, float]], x: float, y: float) -> float:
        min_x, min_y, max_x, max_y, dx, dy = self._roof_bbox_context(pts)
        params = self._roof_profile_params()
        roof_type = self._current_roof_type()
        ridge_orientation = str(params.get("ridge_orientation", "length") or "length").strip().lower()
        ridge_offset_ratio = max(-0.8, min(0.8, float(params.get("ridge_offset_ratio", 0.0) or 0.0)))
        pult_side = str(params.get("pult_rise_side", "right") or "right").strip().lower()
        peak = self._roof_peak_height()
        x = max(min_x, min(max_x, float(x)))
        y = max(min_y, min(max_y, float(y)))
        if roof_type == "flachdach":
            return 0.05
        if ridge_orientation == "width":
            cross = dy; along = dx; c = y - min_y; a = x - min_x
        else:
            cross = dx; along = dy; c = x - min_x; a = y - min_y
        ridge_pos = 0.5 * cross * (1.0 + ridge_offset_ratio)
        ridge_pos = max(0.10 * cross, min(0.90 * cross, ridge_pos))
        left_run = max(1e-9, ridge_pos)
        right_run = max(1e-9, cross - ridge_pos)
        if roof_type == "pultdach":
            frac = c / max(1e-9, cross)
            if pult_side == "left":
                frac = 1.0 - frac
            return max(0.0, min(1.0, frac)) * peak
        if roof_type in {"walmdach", "krueppelwalmdach"}:
            hip = max(1e-9, min(left_run, right_run, 0.5 * along))
            if roof_type == "krueppelwalmdach":
                hip *= max(0.05, min(0.95, float(params.get("half_hip_ratio", 0.45) or 0.45)))
            along_factor = 1.0
            if a < hip:
                along_factor = max(0.0, min(1.0, a / hip))
            elif a > along - hip:
                along_factor = max(0.0, min(1.0, (along - a) / hip))
            cross_factor = c / left_run if c <= ridge_pos else (cross - c) / right_run
            return max(0.0, min(1.0, min(cross_factor, along_factor))) * peak
        frac = c / left_run if c <= ridge_pos else (cross - c) / right_run
        return max(0.0, min(1.0, frac)) * peak

    def _build_roof_facets_for_polygon(self, pts: list[tuple[float, float]], z_top: float):
        segs = self._roof_plan_segments_for_polygon(pts)
        if not segs:
            return []
        lines = self._roof_line_cfg_items()
        min_x, min_y, max_x, max_y, dx, dy = self._roof_bbox_context(pts)
        extra = estimate_roof_line_extra_area_m2(lines, width_m=dx, length_m=dy, rise_m=self._roof_peak_height()) if lines else 0.0
        height_fn = lambda x, y: self._roof_height_for_polygon_point(pts, x, y)
        return build_roof_facets(pts, segs, height_fn, extra_area_total_m2=extra, label_prefix="RF")

    def _roof_line_z_pair(self, kind: str, p1: tuple[float, float], p2: tuple[float, float], z_top: float, peak: float):
        kind = str(kind or "first").strip().lower()
        if kind == "first":
            z = z_top + peak
            return z, z
        if kind == "grat":
            return z_top + 0.76 * peak, z_top + 0.92 * peak
        return z_top + 0.38 * peak, z_top + 0.62 * peak

    def _plot_3d_skin_and_lines(self, ax, poly_by_floor: dict, heights: dict, z_base: dict) -> None:
        if Poly3DCollection is None:
            return

        all_x = []
        all_y = []
        all_z = []
        roof_type = self._current_roof_type()
        roof_name = self._roof_display_name(roof_type)
        material_style = self._facade_material_style()
        roof_style = self._roof_material_style()

        for floor, polys in poly_by_floor.items():
            h = float(heights.get(floor, 2.5) or 2.5)
            z0 = float(z_base.get(floor, 0.0) or 0.0)
            z1 = z0 + h
            is_top_floor = floor == max(poly_by_floor.keys(), key=lambda f: float(z_base.get(f, 0.0) or 0.0))

            for poly in polys:
                if len(poly) < 3:
                    continue
                pts = [(float(x), float(y)) for x, y in poly]
                base = [(x, y, z0) for x, y in pts]

                ax.add_collection3d(Poly3DCollection([base], alpha=0.06))

                for i in range(len(pts)):
                    x0, y0 = pts[i]
                    x1, y1 = pts[(i + 1) % len(pts)]
                    wall = [[(x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1)]]
                    pc = Poly3DCollection(wall, alpha=0.72)
                    pc.set_facecolor(material_style["wall_face"])
                    pc.set_edgecolor(material_style["wall_edge"])
                    ax.add_collection3d(pc)
                    self._add_surface_texture_lines(ax, (x0, y0), (x1, y1), z0, z1, material=material_style["material"], rows=material_style["texture_rows"])
                    ax.plot([x0, x1], [y0, y1], [z0, z0], linewidth=1.0)
                    ax.plot([x0, x1], [y0, y1], [z1, z1], linewidth=1.0)
                    ax.plot([x0, x0], [y0, y0], [z0, z1], linewidth=0.9)

                if is_top_floor:
                    roof_facets = self._build_roof_facets_for_polygon(pts, z1)
                    if roof_facets:
                        for facet in roof_facets:
                            face = [(x, y, z1 + self._roof_height_for_polygon_point(pts, x, y)) for x, y in facet.polygon_m]
                            pc = Poly3DCollection([face], alpha=0.86)
                            pc.set_facecolor(roof_style["roof_face"])
                            pc.set_edgecolor(roof_style["roof_edge"])
                            ax.add_collection3d(pc)
                            self._add_roof_texture_lines(ax, face, roof_style)
                            cx = sum(v[0] for v in face) / len(face)
                            cy = sum(v[1] for v in face) / len(face)
                            cz = sum(v[2] for v in face) / len(face)
                            ax.text(cx, cy, cz + 0.08, facet.label, fontsize=8)
                            all_z.extend([v[2] for v in face])
                    else:
                        roof_faces, ridge = self._build_roof_faces(pts, z1)
                        for face in roof_faces:
                            pc = Poly3DCollection([face], alpha=0.86)
                            pc.set_facecolor(roof_style["roof_face"])
                            pc.set_edgecolor(roof_style["roof_edge"])
                            ax.add_collection3d(pc)
                            self._add_roof_texture_lines(ax, face, roof_style)
                        for i in range(len(ridge) - 1):
                            a = ridge[i]
                            b = ridge[i + 1]
                            ax.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]], linewidth=1.6)
                    for kind, p1, p2 in self._roof_plan_segments_for_polygon(pts):
                        z_a = z1 + self._roof_height_for_polygon_point(pts, p1[0], p1[1])
                        z_b = z1 + self._roof_height_for_polygon_point(pts, p2[0], p2[1])
                        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [z_a, z_b], linewidth=2.2 if kind == "first" else 1.6, linestyle="--" if kind != "kehle" else ":")
                        all_z.extend([z_a, z_b])
                    all_z.extend([z1 + self._roof_peak_height()])
                else:
                    roof = [(x, y, z1) for x, y in pts]
                    pc = Poly3DCollection([roof], alpha=0.12)
                    pc.set_facecolor((0.65, 0.65, 0.68, 1.0))
                    ax.add_collection3d(pc)

                all_x.extend([p[0] for p in pts])
                all_y.extend([p[1] for p in pts])
                all_z.extend([z0, z1])

        if all_x and all_y and all_z:
            dx = max(all_x) - min(all_x)
            dy = max(all_y) - min(all_y)
            dz = max(all_z) - min(all_z)
            ax.set_xlim(min(all_x), max(all_x))
            ax.set_ylim(max(all_y), min(all_y))
            ax.set_zlim(min(all_z), max(all_z))
            ax.set_box_aspect((max(dx, 1.0), max(dy, 1.0), max(dz, 1.0)))

        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_zlabel("z [m]")
        params = self._roof_profile_params()
        ax.set_title(f"3D Hausansicht · {roof_name} · Fassade: {material_style['material_name']} · Dach: {roof_style['material_name']} · First: {params['ridge_orientation']} · Überstand: {params['roof_overhang_m']:.2f} m")
    def _collect_room_polygons_by_floor(self) -> dict:
        """Liefert je Geschoss alle verfügbaren Raum-Polygone für eine detailreiche 3D-Ansicht."""
        poly_by_floor: dict = {}
        rooms = getattr(self, "rooms", {}) or {}
        for floor in ("KG", "EG", "DG"):
            polys = []
            for room in rooms.values():
                if getattr(room, "floor", None) != floor:
                    continue
                try:
                    room.ensure_polygon()
                    pts = [(float(x), float(y)) for x, y in (room.polygon_points() or [])]
                except Exception:
                    pts = []
                if len(pts) >= 3:
                    polys.append(pts)
                    continue
                try:
                    x0 = float(getattr(room, "x_m", 0.0) or 0.0)
                    y0 = float(getattr(room, "y_m", 0.0) or 0.0)
                    x1 = x0 + float(getattr(room, "w_m", 0.0) or 0.0)
                    y1 = y0 + float(getattr(room, "h_m", 0.0) or 0.0)
                    if x1 > x0 and y1 > y0:
                        polys.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
                except Exception:
                    pass
            if polys:
                poly_by_floor[floor] = polys
        return poly_by_floor

    def _current_floor_key(self) -> str:
        view = self._current_plan_view() if hasattr(self, "_current_plan_view") else None
        if view is getattr(self, "view_KG", None):
            return "KG"
        if view is getattr(self, "view_DG", None):
            return "DG"
        return "EG"

    def _current_floor_title(self) -> str:
        return {"KG": "Keller", "EG": "Erdgeschoss", "DG": "Dachgeschoss"}.get(self._current_floor_key(), "Geschoss")

    def _wall_segment_key(self, p0, p1, ndigits: int = 6) -> tuple:
        a = (round(float(p0[0]), ndigits), round(float(p0[1]), ndigits))
        b = (round(float(p1[0]), ndigits), round(float(p1[1]), ndigits))
        return (a, b) if a <= b else (b, a)

    def _wall_elements_for_floor(self, floor: str) -> dict:
        walls_by_segment: dict = {}
        for e in list(getattr(self, "elements", []) or []):
            if getattr(e, "floor", None) != floor or not self._is_wall_like_element(e):
                continue
            if None in (getattr(e, "x0_m", None), getattr(e, "y0_m", None), getattr(e, "x1_m", None), getattr(e, "y1_m", None)):
                continue
            key = self._wall_segment_key((float(e.x0_m), float(e.y0_m)), (float(e.x1_m), float(e.y1_m)))
            walls_by_segment.setdefault(key, []).append(e)
        return walls_by_segment

    def _polygon_signed_area(self, pts: list[tuple[float, float]]) -> float:
        if len(pts) < 3:
            return 0.0
        s = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            s += float(x0) * float(y1) - float(x1) * float(y0)
        return 0.5 * s

    def _shell_wall_thickness_m(self) -> float:
        cfg = getattr(self, "project_cfg", None)
        return max(0.05, float(getattr(cfg, "wall_thickness_outer_m", 0.455) or 0.455))

    def _wall_openings_compact(self, walls: list, wall_length_m: float) -> list[dict]:
        return self._combined_wall_openings(walls, wall_length_m)

    def _collect_shell_3d_scene_data(self) -> dict:
        import math
        poly_by_floor = self._collect_outer_polygons_by_floor()
        if not poly_by_floor:
            return {}
        heights = self._collect_floor_heights()
        z_base = self._floor_z_offsets(heights)
        material_style = self._facade_material_style()
        roof_style = self._roof_material_style()
        walls: list[dict] = []
        roof_faces: list[dict] = []
        roof_lines: list[dict] = []
        all_pts: list[tuple[float, float, float]] = []
        top_floor = max(poly_by_floor.keys(), key=lambda f: float(z_base.get(f, 0.0) or 0.0))
        for floor, polys in poly_by_floor.items():
            z0 = float(z_base.get(floor, 0.0) or 0.0)
            z1 = z0 + float(heights.get(floor, 2.5) or 2.5)
            wall_segments = self._wall_elements_for_floor(floor)
            for poly in list(polys or []):
                pts = [(float(x), float(y)) for x, y in list(poly or [])]
                if len(pts) < 3:
                    continue
                sign = self._polygon_signed_area(pts)
                for i in range(len(pts)):
                    p0 = pts[i]
                    p1 = pts[(i + 1) % len(pts)]
                    seg_len = math.hypot(float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1]))
                    if seg_len <= 1e-9:
                        continue
                    wall_entry = {"walls": wall_segments.get(self._wall_segment_key(p0, p1), [])}
                    openings = self._wall_openings_compact(list(wall_entry.get("walls", []) or []), seg_len)
                    walls.append({
                        "p0": p0, "p1": p1, "z0": z0, "z1": z1, "poly_sign": sign,
                        "thickness_m": self._shell_wall_thickness_m(),
                        "openings": openings,
                        "color": material_style["wall_face"],
                        "edge": material_style["wall_edge"],
                        "floor": floor,
                    })
                    all_pts.extend([(p0[0], p0[1], z0), (p1[0], p1[1], z1)])
                if floor == top_floor:
                    facets = self._build_roof_facets_for_polygon(pts, z1)
                    for facet in list(facets or []):
                        face_pts = [(x, y, z1 + self._roof_height_for_polygon_point(pts, x, y)) for x, y in facet.polygon_m]
                        if len(face_pts) >= 3:
                            roof_faces.append({"points": face_pts, "color": roof_style["roof_face"], "edge": roof_style["roof_edge"], "label": facet.label})
                            all_pts.extend(face_pts)
                    for kind, rp1, rp2 in self._roof_plan_segments_for_polygon(pts):
                        za = z1 + self._roof_height_for_polygon_point(pts, rp1[0], rp1[1])
                        zb = z1 + self._roof_height_for_polygon_point(pts, rp2[0], rp2[1])
                        roof_lines.append({
                            "kind": kind,
                            "p1": (float(rp1[0]), float(rp1[1]), float(za)),
                            "p2": (float(rp2[0]), float(rp2[1]), float(zb)),
                            "width": 3.0 if kind == "first" else 2.0,
                            "color": (0.18, 0.18, 0.18, 1.0) if kind == "first" else ((0.40, 0.22, 0.12, 1.0) if kind == "grat" else (0.18, 0.30, 0.48, 1.0)),
                        })
                        all_pts.extend([(float(rp1[0]), float(rp1[1]), float(za)), (float(rp2[0]), float(rp2[1]), float(zb))])
        xs = [p[0] for p in all_pts] if all_pts else [0.0, 10.0]
        ys = [p[1] for p in all_pts] if all_pts else [0.0, 10.0]
        zs = [p[2] for p in all_pts] if all_pts else [0.0, 6.0]
        span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0)
        return {
            "title": f"3D Gebäudehülle+ · {self._roof_display_name(self._current_roof_type())}",
            "walls": walls,
            "roof_faces": roof_faces,
            "roof_lines": roof_lines,
            "camera_distance": span * 2.3,
        }

    def _collect_shell_2d_scene_data(self) -> dict:
        scene_data = dict(self._collect_shell_3d_scene_data() or {})
        if not scene_data:
            return {}
        roof_plan_lines: list[dict] = []
        for line in list(scene_data.get("roof_lines", []) or []):
            p1 = line.get("p1")
            p2 = line.get("p2")
            if not p1 or not p2:
                continue
            roof_plan_lines.append({
                "kind": str(line.get("kind", "line") or "line"),
                "p1": (float(p1[0]), float(p1[1])),
                "p2": (float(p2[0]), float(p2[1])),
            })
        scene_data["title"] = str(scene_data.get("title", "3D Gebäudehülle+")).replace("3D", "2D", 1)
        scene_data["roof_plan_lines"] = roof_plan_lines
        scene_data["px_per_m"] = 140.0
        return scene_data

    def _on_show_2d_shell(self) -> None:
        scene_data = self._collect_shell_2d_scene_data()
        if not scene_data:
            QMessageBox.warning(self, "2D Gebäudehülle+", "Keine Außenkontur gefunden. Bitte zuerst Räume anlegen oder Auto-Wände erzeugen.")
            return
        dlg = Shell2DDialog(scene_data, parent=self)
        try:
            self.statusBar().showMessage("2D Gebäudehülle+ geöffnet: Wanddicke, Öffnungen und Dachlinien in der Draufsicht.", 7000)
        except Exception:
            pass
        dlg.exec()

    def _on_show_3d_shell_gl(self) -> None:
        scene_data = self._collect_shell_3d_scene_data()
        if not scene_data:
            QMessageBox.warning(self, "3D Gebäudehülle+", "Keine Außenkontur gefunden. Bitte zuerst Räume anlegen oder Auto-Wände erzeugen.")
            return
        if not Shell3DDialog.is_available():
            QMessageBox.information(self, "3D Gebäudehülle+", "pyqtgraph.opengl ist nicht verfügbar. Es wird die bestehende 3D-Hausansicht geöffnet.")
            self._on_show_3d_house()
            return
        dlg = Shell3DDialog(scene_data, parent=self)
        try:
            self.statusBar().showMessage("3D Gebäudehülle+ geöffnet: OpenGL-Renderer mit Wanddicke, Laibungen und Dachlinien.", 7000)
        except Exception:
            pass
        dlg.exec()

    def _combined_wall_openings(self, walls: list, wall_length_m: float) -> list[dict]:
        merged = []
        for wall in list(walls or []):
            wall_height_m = float(getattr(wall, "height_m", 0.0) or 0.0)
            for op in self._wall_openings_for_element(wall):
                start = max(0.0, float(getattr(op, "offset_m", 0.0) or 0.0))
                end = min(float(wall_length_m), start + max(0.0, float(getattr(op, "width_m", 0.0) or 0.0)))
                if end <= start + 1e-9:
                    continue
                sill = max(0.0, float(getattr(op, "sill_m", 0.0) or 0.0))
                top = max(sill, sill + max(0.0, float(getattr(op, "height_m", 0.0) or 0.0)))
                if wall_height_m > 1e-9:
                    top = min(top, wall_height_m)
                merged.append({
                    "start": start,
                    "end": end,
                    "sill": sill,
                    "top": top,
                    "type": str(getattr(op, "opening_type", "window") or "window").lower(),
                    "label": str(getattr(op, "label", "Öffnung") or "Öffnung"),
                })
        merged.sort(key=lambda o: (o["start"], o["end"], o["type"]))
        return merged

    def _point_on_segment(self, p0, p1, s_m: float, seg_len_m: float):
        if seg_len_m <= 1e-12:
            return (float(p0[0]), float(p0[1]))
        t = max(0.0, min(1.0, float(s_m) / float(seg_len_m)))
        return (float(p0[0]) + (float(p1[0]) - float(p0[0])) * t, float(p0[1]) + (float(p1[1]) - float(p0[1])) * t)

    def _add_wall_quad(self, ax, p0, p1, z_bottom: float, z_top: float, *, facecolor, edgecolor, alpha: float = 0.78, linewidth: float = 0.9) -> None:
        if Poly3DCollection is None or z_top <= z_bottom + 1e-9:
            return
        wall = [[(float(p0[0]), float(p0[1]), z_bottom), (float(p1[0]), float(p1[1]), z_bottom), (float(p1[0]), float(p1[1]), z_top), (float(p0[0]), float(p0[1]), z_top)]]
        pc = Poly3DCollection(wall, alpha=alpha)
        pc.set_facecolor(facecolor)
        pc.set_edgecolor(edgecolor)
        try:
            pc.set_linewidth(linewidth)
        except Exception:
            pass
        ax.add_collection3d(pc)

    def _add_opening_panel(self, ax, p0, p1, z_bottom: float, z_top: float, opening_type: str = "window") -> None:
        if Poly3DCollection is None or z_top <= z_bottom + 1e-9:
            return
        opening_type = str(opening_type or "window").lower()
        if opening_type == "door":
            face = (0.74, 0.56, 0.35, 0.92)
            edge = (0.33, 0.20, 0.10, 0.95)
            alpha = 0.88
        else:
            face = (0.63, 0.82, 0.98, 0.55)
            edge = (0.10, 0.36, 0.72, 0.85)
            alpha = 0.52
        self._add_wall_quad(ax, p0, p1, z_bottom, z_top, facecolor=face, edgecolor=edge, alpha=alpha, linewidth=1.2)

    def _render_wall_with_openings(self, ax, p0, p1, z0: float, z1: float, wall_entry: dict, material_style: dict) -> tuple[int, int]:
        import math
        seg_len = math.hypot(float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1]))
        if seg_len <= 1e-9:
            return (0, 0)
        openings = self._combined_wall_openings(list((wall_entry or {}).get("walls", []) or []), seg_len)
        if not openings:
            self._add_wall_quad(ax, p0, p1, z0, z1, facecolor=material_style["wall_face"], edgecolor=material_style["wall_edge"], alpha=0.78)
            self._add_surface_texture_lines(ax, p0, p1, z0, z1, material=material_style["material"], rows=max(6, int(material_style["texture_rows"])))
            return (0, 0)

        cuts = [0.0, seg_len]
        for op in openings:
            cuts.extend([max(0.0, min(seg_len, float(op["start"]))), max(0.0, min(seg_len, float(op["end"])) )])
        cuts = sorted({round(c, 6) for c in cuts})
        intervals = [(cuts[i], cuts[i+1]) for i in range(len(cuts)-1) if cuts[i+1] - cuts[i] > 1e-6]
        n_windows = 0
        n_doors = 0
        for a, b in intervals:
            mid = 0.5 * (a + b)
            op_here = None
            for op in openings:
                if float(op["start"]) - 1e-6 <= mid <= float(op["end"]) + 1e-6:
                    op_here = op
                    break
            pa = self._point_on_segment(p0, p1, a, seg_len)
            pb = self._point_on_segment(p0, p1, b, seg_len)
            if op_here is None:
                self._add_wall_quad(ax, pa, pb, z0, z1, facecolor=material_style["wall_face"], edgecolor=material_style["wall_edge"], alpha=0.78)
                self._add_surface_texture_lines(ax, pa, pb, z0, z1, material=material_style["material"], rows=max(6, int(material_style["texture_rows"])))
                continue
            sill = max(z0, min(z1, float(op_here["sill"])))
            top = max(z0, min(z1, float(op_here["top"])))
            if sill > z0 + 1e-6:
                self._add_wall_quad(ax, pa, pb, z0, sill, facecolor=material_style["wall_face"], edgecolor=material_style["wall_edge"], alpha=0.78)
                self._add_surface_texture_lines(ax, pa, pb, z0, sill, material=material_style["material"], rows=max(4, int(material_style["texture_rows"])))
            if top < z1 - 1e-6:
                self._add_wall_quad(ax, pa, pb, top, z1, facecolor=material_style["wall_face"], edgecolor=material_style["wall_edge"], alpha=0.78)
                self._add_surface_texture_lines(ax, pa, pb, top, z1, material=material_style["material"], rows=max(4, int(material_style["texture_rows"])))
            self._add_opening_panel(ax, pa, pb, sill, top, opening_type=op_here["type"])
            if op_here["type"] == "door":
                n_doors += 1
            else:
                n_windows += 1
        return (n_windows, n_doors)

    def _plot_3d_floor_detail(self, ax, floor: str, poly_by_floor: dict, heights: dict) -> None:
        if Poly3DCollection is None:
            return
        polys = list(poly_by_floor.get(floor, []) or [])
        if not polys:
            return

        z0 = 0.0
        z1 = z0 + float(heights.get(floor, 2.5) or 2.5)
        material_style = self._facade_material_style()
        wall_segments = self._wall_elements_for_floor(floor)
        all_x = []
        all_y = []
        all_z = [z0, z1]
        total_windows = 0
        total_doors = 0

        for poly in polys:
            if len(poly) < 3:
                continue
            pts = [(float(x), float(y)) for x, y in poly]
            floor_face = [(x, y, z0) for x, y in pts]
            ceil_face = [(x, y, z1) for x, y in pts]
            slab = Poly3DCollection([floor_face], alpha=0.10)
            slab.set_facecolor((0.76, 0.79, 0.82, 1.0))
            slab.set_edgecolor((0.40, 0.43, 0.46, 0.55))
            ax.add_collection3d(slab)
            ceiling = Poly3DCollection([ceil_face], alpha=0.05)
            ceiling.set_facecolor((0.90, 0.91, 0.92, 1.0))
            ceiling.set_edgecolor((0.55, 0.57, 0.60, 0.25))
            ax.add_collection3d(ceiling)

            for i in range(len(pts)):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % len(pts)]
                p0 = (x0, y0)
                p1 = (x1, y1)
                key = self._wall_segment_key(p0, p1)
                wall_entry = {"walls": wall_segments.get(key, [])}
                nw, nd = self._render_wall_with_openings(ax, p0, p1, z0, z1, wall_entry, material_style)
                total_windows += nw
                total_doors += nd
                ax.plot([x0, x1], [y0, y1], [z0, z0], linewidth=1.0)
                ax.plot([x0, x1], [y0, y1], [z1, z1], linewidth=1.0)
                ax.plot([x0, x0], [y0, y0], [z0, z1], linewidth=0.8)

            all_x.extend([p[0] for p in pts])
            all_y.extend([p[1] for p in pts])

        if all_x and all_y:
            dx = max(all_x) - min(all_x)
            dy = max(all_y) - min(all_y)
            dz = max(all_z) - min(all_z)
            pad_x = max(0.4, 0.06 * max(dx, 1.0))
            pad_y = max(0.4, 0.06 * max(dy, 1.0))
            ax.set_xlim(min(all_x) - pad_x, max(all_x) + pad_x)
            ax.set_ylim(max(all_y) + pad_y, min(all_y) - pad_y)
            ax.set_zlim(z0, z1 + max(0.3, 0.08 * max(dx, dy, 1.0)))
            ax.set_box_aspect((max(dx, 1.0), max(dy, 1.0), max(dz, 1.0)))

        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_zlabel("z [m]")
        ax.set_title(f"3D-Geschossansicht · {self._current_floor_title()} · Fassade: {material_style['material_name']} · Fenster: {total_windows} · Türen: {total_doors}")

    def _on_show_3d_floor(self) -> None:
        if plt is None or FigureCanvas is None or Poly3DCollection is None:
            QMessageBox.warning(self, "3D Geschossansicht", "matplotlib/QtAgg ist nicht verfügbar.")
            return

        floor = self._current_floor_key()
        poly_by_floor = self._collect_room_polygons_by_floor()
        polys = list(poly_by_floor.get(floor, []) or [])
        if not polys:
            QMessageBox.warning(self, "3D Geschossansicht", f"Für {self._current_floor_title()} wurden noch keine Räume gefunden.")
            return

        heights = self._collect_floor_heights()

        dlg = QDialog(self)
        dlg.setWindowTitle(f"3D-Geschossansicht – {self._current_floor_title()}")
        lay = QVBoxLayout(dlg)

        fig = Figure(figsize=(10, 6))
        canvas = FigureCanvas(fig)
        if NavigationToolbar is not None:
            lay.addWidget(NavigationToolbar(canvas, dlg))
        lay.addWidget(canvas)

        ax = fig.add_subplot(111, projection="3d")
        self._plot_3d_floor_detail(ax, floor, poly_by_floor, heights)
        try:
            ax.view_init(elev=26, azim=-52)
        except Exception:
            pass

        fig.tight_layout()
        canvas.draw()

        btn = QPushButton("Schließen")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn)

        try:
            self.statusBar().showMessage(f"3D-Geschossansicht geöffnet: {self._current_floor_title()}.", 5000)
        except Exception:
            pass

        dlg.resize(1120, 780)
        dlg.exec()

    def _on_show_3d_house(self) -> None:
        if plt is None or FigureCanvas is None or Poly3DCollection is None:
            QMessageBox.warning(self, "3D Ansicht", "matplotlib/QtAgg ist nicht verfügbar.")
            return

        poly_by_floor = self._collect_outer_polygons_by_floor()
        if not poly_by_floor:
            QMessageBox.warning(
                self, "3D Ansicht",
                "Keine Gebäudeaußenkontur gefunden. Bitte zuerst Räume anlegen oder Auto-Wände erzeugen."
            )
            return

        heights = self._collect_floor_heights()
        z_base = self._floor_z_offsets(heights)

        dlg = QDialog(self)
        dlg.setWindowTitle("3D Hausansicht (drehbar)")
        lay = QVBoxLayout(dlg)

        fig = Figure(figsize=(10, 6))
        canvas = FigureCanvas(fig)
        if NavigationToolbar is not None:
            lay.addWidget(NavigationToolbar(canvas, dlg))
        lay.addWidget(canvas)

        ax = fig.add_subplot(111, projection="3d")
        self._plot_3d_skin_and_lines(ax, poly_by_floor, heights, z_base)
        try:
            ax.view_init(elev=24, azim=-58)
        except Exception:
            pass

        fig.tight_layout()
        canvas.draw()

        btn = QPushButton("Schließen")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn)

        try:
            self.statusBar().showMessage("3D-Ansicht geöffnet: Linke Maustaste drehen, rechte Maustaste zoomen/verschieben.", 7000)
        except Exception:
            pass

        dlg.resize(1180, 820)
        dlg.exec()

    def _set_room_draw_tool(self, tool: str | None):
        tool = tool or "select"
        self._draw_tool = tool
        self._room_draw_mode = tool in {"rect", "l", "poly"}
        self._polygon_room_mode = tool == "poly"
        self._l_room_mode = tool == "l"
        self._split_room_mode = tool == "split"
        if getattr(self, 'act_select_tool', None) is not None and tool != 'select':
            self.act_select_tool.setChecked(False)
        if getattr(self, 'act_rect_room', None) is not None and tool != 'rect':
            self.act_rect_room.setChecked(False)
        if getattr(self, 'act_l_room', None) is not None and tool != 'l':
            self.act_l_room.setChecked(False)
        if getattr(self, 'act_polygon_room', None) is not None and tool != 'poly':
            self.act_polygon_room.setChecked(False)
        if getattr(self, 'act_split_room', None) is not None and tool != 'split':
            self.act_split_room.setChecked(False)
        if getattr(self, 'act_add_window', None) is not None:
            self.act_add_window.setChecked(False)
            self._add_window_mode = False
        for view in (getattr(self, "view_KG", None), getattr(self, "view_EG", None), getattr(self, "view_DG", None)):
            if view is None:
                continue
            try:
                view.viewport().setCursor(Qt.ArrowCursor if tool == 'select' else Qt.CrossCursor)
            except Exception:
                pass
        self._cancel_polygon_room_preview()
        self._cancel_l_room_preview()
        self._cancel_split_preview()
        try:
            msg = {
                'select': 'Auswahlmodus aktiv: Räume und Elemente können selektiert und verschoben werden.',
                'rect': 'Zeichnen aktiv: Rechteck-Raum per Ziehen aufspannen.',
                'l': 'Zeichnen aktiv: L-Raum mit drei Klickpunkten definieren.',
                'poly': 'Zeichnen aktiv: Polygonraum mit orthogonalen Klickpunkten definieren.',
                'split': 'Teilen aktiv: selektierten Raum mit einer Linie teilen.',
            }.get(tool)
            if msg:
                self.statusBar().showMessage(msg, 5000)
        except Exception:
            pass

    def _on_draw_floorplan(self):
        self._set_room_draw_tool('rect')
        if getattr(self, 'act_rect_room', None) is not None:
            self.act_rect_room.setChecked(True)

    def _on_toggle_select_mode(self, checked=False):
        self._set_room_draw_tool('select' if checked else None)

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

    def _create_room_from_polygon(self, floor: str, pts_m: list[tuple[float, float]], select: bool = True, room_id: str | None = None, name: str | None = None):
        pts_m = simplify_orthogonal_polygon([(snap_m(x), snap_m(y)) for x, y in pts_m])
        if not validate_orthogonal_polygon(pts_m):
            return None
        rid = str(room_id or self._new_room_id(floor))
        xs = [x for x, _ in pts_m]; ys = [y for _, y in pts_m]
        r = RoomModel(id=rid, floor=floor, name=str(name or rid), x_m=min(xs), y_m=min(ys), w_m=max(xs)-min(xs), h_m=max(ys)-min(ys), polygon_m=serialize_polygon_m(pts_m))
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


    def _build_room_operation_service(self):
        """Liefert einen RoomOperationService für UI-Aktionen.

        Nutzt bevorzugt den bereits verdrahteten AppController. Falls die UI
        ohne Controller läuft, wird ein lokaler Service auf Basis des
        HouseDomainService erzeugt.
        """
        ctrl = getattr(self, "controller", None)
        room_ops = getattr(ctrl, "room_ops", None) if ctrl is not None else None
        if room_ops is not None:
            factory = getattr(room_ops, "_service", None)
            if callable(factory):
                return factory()
            return room_ops

        from ..core.geometry import build_auto_walls_shared_merge
        from ..domain.services.house_domain_service import HouseDomainService
        from ..domain.services.room_operation_service import RoomOperationService

        domain = getattr(ctrl, "domain", None) if ctrl is not None else None
        if domain is None:
            domain = HouseDomainService()
        return RoomOperationService(domain=domain, build_auto_walls=build_auto_walls_shared_merge)

    def _controller_house_state(self):
        ctrl = getattr(self, "controller", None)
        state = getattr(ctrl, "state", None)
        if state is not None:
            return state
        return HouseState(
            rooms=dict(getattr(self, "rooms", {}) or {}),
            elements=list(getattr(self, "elements", []) or []),
            project_cfg=getattr(self, "project_cfg", None),
        )

    def _sync_from_house_state(self, state: HouseState) -> None:
        """Überträgt einen HouseState zurück in die UI-Datenstrukturen."""
        self.rooms = dict(getattr(state, "rooms", {}) or {})
        self.elements = list(getattr(state, "elements", []) or [])
        cfg = getattr(state, "project_cfg", None)
        if cfg is not None:
            self.project_cfg = cfg
            try:
                self.t_out_c = float(self.project_cfg.t_out_c)
            except Exception:
                pass
        try:
            self.metrics.bind(self.rooms, self.elements)
        except Exception:
            pass

    def _push_room_operation_record(self, rec: RoomOperationRecord | None) -> None:
        if rec is None:
            return
        stack = getattr(self, '_room_op_undo_stack', None)
        if stack is None:
            stack = []
            self._room_op_undo_stack = stack
        stack.append(rec)
        self._room_op_redo_stack = []

    def _apply_room_operation_record_to_ui(self, state: HouseState, rec: RoomOperationRecord | None) -> None:
        self._sync_from_house_state(state)
        try:
            self._rebuild_all_graphics()
        except Exception:
            pass
        self._selected_room_id = getattr(rec, 'selected_room_id', None) if rec is not None else None
        try:
            self._populate_room_form()
        except Exception:
            pass

    def _undo_last_room_operation(self) -> None:
        stack = getattr(self, '_room_op_undo_stack', None) or []
        if not stack:
            return
        rec = stack.pop()
        state = self._controller_house_state()
        rec.undo(state)
        redo = getattr(self, '_room_op_redo_stack', None)
        if redo is None:
            redo = []
            self._room_op_redo_stack = redo
        redo.append(rec)
        self._apply_room_operation_record_to_ui(state, rec)

    def _redo_last_room_operation(self) -> None:
        stack = getattr(self, '_room_op_redo_stack', None) or []
        if not stack:
            return
        rec = stack.pop()
        state = self._controller_house_state()
        rec.redo(state)
        undo = getattr(self, '_room_op_undo_stack', None)
        if undo is None:
            undo = []
            self._room_op_undo_stack = undo
        undo.append(rec)
        self._apply_room_operation_record_to_ui(state, rec)

    def _on_merge_selected_rooms(self):
        ids = self._selected_room_ids()
        if len(ids) < 2:
            try: self.statusBar().showMessage('Bitte mindestens zwei Räume zum Verschmelzen selektieren.', 4000)
            except Exception: pass
            return
        ctrl = getattr(self, "controller", None)
        if ctrl is None:
            return
        rec = ctrl.merge_rooms(ids)
        if rec is None:
            return
        self._push_room_operation_record(rec)
        self._apply_room_operation_record_to_ui(ctrl.state, rec)

    def _on_subtract_selected_rooms(self):
        ids = self._selected_room_ids()
        if len(ids) < 2:
            try: self.statusBar().showMessage('Bitte zuerst den Basisraum, dann die abzuziehenden Räume selektieren.', 4000)
            except Exception: pass
            return
        ctrl = getattr(self, "controller", None)
        if ctrl is None:
            return
        rec = ctrl.subtract_rooms(ids[0], ids[1:])
        if rec is None:
            try: self.statusBar().showMessage('Subtraktion ergab keine gültige orthogonale Restfläche.', 5000)
            except Exception: pass
            return
        self._push_room_operation_record(rec)
        self._apply_room_operation_record_to_ui(ctrl.state, rec)

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
                service = self._build_room_operation_service()
                state = self._controller_house_state()
                rec = service.split_room(state, room.id, orientation=orientation, coord=coord)
                if rec is None:
                    return True
                self._push_room_operation_record(rec)
                self._apply_room_operation_record_to_ui(state, rec)
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