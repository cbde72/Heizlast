from typing import Optional
from ..domain.models import RoomModel
from PySide6.QtWidgets import QMessageBox, QDialog, QInputDialog
from ..core import ElementMetricsService
from ..core.config import DEFAULT_FACTOR, DEFAULT_U

from ..configs.project_config import save_project_cfg
from ..domain.models import ElementModel, RoomModel
from ..ui.dialogs.project_settings_dialog import ProjectSettingsDialog

class MainWindowSettingsMixin:
    def _on_project_settings(self):
        """Öffnet den Projekteinstellungen-Dialog."""
        dlg = ProjectSettingsDialog(self, self.project_cfg)
        if dlg.exec() != QDialog.Accepted:
            return
        dlg.apply_to_cfg(self.project_cfg)

        self.t_out_c = float(self.project_cfg.t_out_c)
        want_outer = (self.project_cfg.floor_area_mode == "outer")
        if hasattr(self, "cb_area_ref_outer"):
            self.cb_area_ref_outer.blockSignals(True)
            self.cb_area_ref_outer.setChecked(bool(want_outer))
            self.cb_area_ref_outer.blockSignals(False)
        if hasattr(self, "act_area_ref_outer"):
            self.act_area_ref_outer.blockSignals(True)
            self.act_area_ref_outer.setChecked(bool(want_outer))
            self.act_area_ref_outer.blockSignals(False)

        if self._project_rooms_path:
            try:
                cfg_path = self._project_json_path_for_rooms(self._project_rooms_path)
                save_project_cfg(cfg_path, self.project_cfg)
            except Exception:
                pass

        self._recompute_and_redraw()

    def _on_auto_keller(self) -> None:
        """Erzeugt automatisch einen Keller (KG) aus den *tatsächlichen* EG-Außenwänden.

        Vorgehen:
          1) EG-Außenwände aus den vorhandenen Elementen sammeln (auto_contour, element_type='Außenwand').
          2) Aus den Segmenten die äußere Gebäudekontur (Polygon) rekonstruieren.
          3) Einen Raum 'KG_AUTO' als Bounding-Box über dem Polygon anlegen (RoomModel ist rechteckig).
          4) KG-Außenwände als Segmente (exakt wie EG-Kontur) + Bodenplatte mit Polygonfläche erzeugen.

        Hinweis:
          - Falls keine EG-Außenwände verfügbar sind, wird auf die bisherige Bounding-Box über EG-Räume
            zurückgefallen.
        """
        if not self.rooms:
            QMessageBox.warning(self, "Auto Keller", "Keine Räume geladen.")
            return

        # Deckenhöhe abfragen
        h_default = 2.2
        h, ok = QInputDialog.getDouble(
            self, "Auto Keller", "Keller-Deckenhöhe [m]", h_default, 1.5, 5.0, 2
        )
        if not ok:
            return

        eg_rooms = [r for r in self.rooms.values() if (getattr(r, 'floor', '') or '').strip().upper() == 'EG']
        if not eg_rooms:
            QMessageBox.warning(self, "Auto Keller", "Keine EG-Räume gefunden (floor='EG').")
            return

        # ------------------------------------------------------------------
        # EG-Footprint aus tatsächlichen EG-Außenwänden (auto_contour)
        # ------------------------------------------------------------------

        def _is_eg_outer_wall(e: ElementModel) -> bool:
            try:
                if (getattr(e, "floor", "") or "").strip().upper() != "EG":
                    return False
                if str(getattr(e, "element_type", "") or "").strip() != "Außenwand":
                    return False
                meta = str(getattr(e, "meta", "") or "")
                if "auto_contour" not in meta:
                    return False
                if not getattr(e, "has_geometry", lambda: False)():
                    return False
                return True
            except Exception:
                return False

        def _norm_pt(x: float, y: float, tol: float = 1e-6) -> tuple[float, float]:
            return (round(float(x) / tol) * tol, round(float(y) / tol) * tol)

        def _polygon_area(poly: list[tuple[float, float]]) -> float:
            if not poly or len(poly) < 3:
                return 0.0
            s = 0.0
            for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
                s += x0 * y1 - x1 * y0
            return 0.5 * s

        def _outer_polygon_from_segments(
            segs: list[tuple[tuple[float, float], tuple[float, float]]],
            *,
            tol: float = 1e-6
        ) -> Optional[list[tuple[float, float]]]:
            """Rekonstruiert äußeres Polygon aus Segmenten (Planar-Graph Face-Walk).

            Robust genug für rechtwinklige Grundrisse (auch L-Formen), solange die Segmente
            sauber aneinander anschließen.
            """
            if not segs:
                return None

            # Adjazenz
            adj: dict[tuple[float, float], set[tuple[float, float]]] = {}
            for (a, b) in segs:
                a = _norm_pt(a[0], a[1], tol)
                b = _norm_pt(b[0], b[1], tol)
                if a == b:
                    continue
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)

            if not adj:
                return None

            # Nachbarn CCW sortieren
            import math

            nbr_sorted: dict[tuple[float, float], list[tuple[float, float]]] = {}
            for v, nbrs in adj.items():
                vx, vy = v
                lst = list(nbrs)
                lst.sort(key=lambda u: math.atan2(u[1] - vy, u[0] - vx))
                nbr_sorted[v] = lst

            def prev_ccw(v: tuple[float, float], u: tuple[float, float]) -> Optional[tuple[float, float]]:
                lst = nbr_sorted.get(v, [])
                if not lst:
                    return None
                try:
                    idx = lst.index(u)
                except ValueError:
                    return lst[-1]
                return lst[(idx - 1) % len(lst)]

            visited: set[tuple[tuple[float, float], tuple[float, float]]] = set()
            faces: list[list[tuple[float, float]]] = []

            for u in adj:
                for v in adj[u]:
                    if (u, v) in visited:
                        continue
                    face: list[tuple[float, float]] = []
                    start = (u, v)
                    cu, cv = u, v
                    while True:
                        visited.add((cu, cv))
                        face.append(cu)
                        nw = prev_ccw(cv, cu)
                        if nw is None:
                            break
                        cu, cv = cv, nw
                        if (cu, cv) == start:
                            break
                        if len(face) > 5000:
                            break

                    if len(face) >= 3:
                        cleaned: list[tuple[float, float]] = []
                        for p in face:
                            if not cleaned or (abs(cleaned[-1][0] - p[0]) > tol or abs(cleaned[-1][1] - p[1]) > tol):
                                cleaned.append(p)
                        if len(cleaned) >= 3:
                            faces.append(cleaned)

            if not faces:
                return None

            faces.sort(key=lambda poly: abs(_polygon_area(poly)), reverse=True)
            outer = faces[0]
            if len(outer) >= 2 and (abs(outer[0][0] - outer[-1][0]) < tol and abs(outer[0][1] - outer[-1][1]) < tol):
                outer = outer[:-1]
            return outer

        eg_outer_walls = [e for e in self.elements if _is_eg_outer_wall(e)]
        segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for e in eg_outer_walls:
            try:
                segs.append(((float(e.x0_m), float(e.y0_m)), (float(e.x1_m), float(e.y1_m))))
            except Exception:
                pass

        poly = _outer_polygon_from_segments(segs)

        if poly and len(poly) >= 3:
            minx = min(p[0] for p in poly)
            miny = min(p[1] for p in poly)
            maxx = max(p[0] for p in poly)
            maxy = max(p[1] for p in poly)
            w = max(0.1, maxx - minx)
            hh = max(0.1, maxy - miny)
            slab_area = abs(_polygon_area(poly))
        else:
            # Fallback: Bounding Box über alle EG-Räume
            minx = min(float(getattr(r, 'x_m', 0.0) or 0.0) for r in eg_rooms)
            miny = min(float(getattr(r, 'y_m', 0.0) or 0.0) for r in eg_rooms)
            maxx = max(float(getattr(r, 'x_m', 0.0) or 0.0) + float(getattr(r, 'w_m', 0.0) or 0.0) for r in eg_rooms)
            maxy = max(float(getattr(r, 'y_m', 0.0) or 0.0) + float(getattr(r, 'h_m', 0.0) or 0.0) for r in eg_rooms)
            w = max(0.1, maxx - minx)
            hh = max(0.1, maxy - miny)
            slab_area = float(w) * float(hh)

        kg_id = 'KG_AUTO'

        # Vorhandene Auto-Keller Elemente entfernen
        self.elements = [e for e in self.elements if not (getattr(e, 'uid', '') or '').startswith('auto_keller_')]

        # Raum anlegen/überschreiben
        t_keller = float(getattr(self.project_cfg, 't_keller_c', 14.0) or 14.0)
        rm = RoomModel(
            id=kg_id,
            floor='KG',
            name='Keller (auto)',
            x_m=float(minx),
            y_m=float(miny),
            w_m=float(w),
            h_m=float(hh),
            height_m=float(h),
            t_inside_c=t_keller,
            air_change_1ph=0.1,
            volume_m3=0.0,
        )
        try:
            rm.recompute_volume()
        except Exception:
            rm.volume_m3 = rm.w_m * rm.h_m * rm.height_m

        self.rooms[kg_id] = rm

        # Basis-Bodenplatte erzeugen
        slab_uid = 'auto_keller_bodenplatte'
        self.elements.append(
            ElementModel(
                room_id=kg_id,
                element_type='Bodenplatte',
                area_m2=slab_area,
                u_w_m2k=float(DEFAULT_U.get("Boden", 0.35)),
                factor=float(DEFAULT_FACTOR.get("Boden", 1.0)),
                floor='KG',
                uid=slab_uid,
                meta=("auto_keller=1" + ("|shape=poly" if (poly and len(poly) >= 3) else "|shape=bbox")),
            )
        )

        # KG-Außenwände aus EG-Kontur-Segmenten nachbauen
        if poly and len(poly) >= 3 and eg_outer_walls:
            self.elements = [e for e in self.elements if not (getattr(e, 'uid', '') or '').startswith('auto_keller_wall_')]
            for i, e_src in enumerate(eg_outer_walls):
                try:
                    x0 = float(e_src.x0_m); y0 = float(e_src.y0_m)
                    x1 = float(e_src.x1_m); y1 = float(e_src.y1_m)
                    L = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
                except Exception:
                    continue
                if L <= 1e-9:
                    continue
                uid = f"auto_keller_wall_{i:04d}"
                self.elements.append(
                    ElementModel(
                        room_id=kg_id,
                        element_type='Außenwand',
                        area_m2=float(L) * float(h),
                        u_w_m2k=float(getattr(e_src, 'u_w_m2k', DEFAULT_U.get('Außenwand', 0.45)) or DEFAULT_U.get('Außenwand', 0.45)),
                        factor=float(getattr(e_src, 'factor', DEFAULT_FACTOR.get('Außenwand', 1.0)) or DEFAULT_FACTOR.get('Außenwand', 1.0)),
                        floor='KG',
                        x0_m=float(x0), y0_m=float(y0), x1_m=float(x1), y1_m=float(y1),
                        length_m=float(L),
                        height_m=float(h),
                        uid=uid,
                        meta=f"auto_keller=1|src=EG|src_uid={(getattr(e_src, 'uid', '') or '')}"
                    )
                )

        # Metrics aktualisieren
        self.metrics = ElementMetricsService(self.rooms, self.elements)

        # Auto-Wände neu berechnen (inkl. KG), wenn aktiv
        if getattr(self, 'autowalls_enabled', True):
            try:
                self._rebuild_autowalls_all()
            except Exception:
                pass

        # Grafik neu
        try:
            self._rebuild_all_graphics()
        except Exception:
            try:
                self._rebuild_rooms_graphics()
                self._rebuild_elements_graphics()
            except Exception:
                pass

        self._recompute_and_redraw()

        QMessageBox.information(
            self, "Auto Keller",
            f"Keller erzeugt: {kg_id}  ({slab_area:.1f} m² Bodenplatte, Höhe {h:.2f} m)"
        )

def load_project_from_paths(self, rooms_csv_path, elements_csv_path=None):
    """Best-effort loader for packaged runtime starts."""
    from pathlib import Path
    from ..core.csv_io import load_rooms, load_elements
    from ..configs.project_config import load_project_cfg
    from ..core.config import CSV_DELIMITER

    rooms_csv_path = Path(rooms_csv_path)
    if elements_csv_path is None:
        stem = rooms_csv_path.stem
        if rooms_csv_path.name.lower() == "rooms.csv":
            elements_csv_path = rooms_csv_path.with_name("elements.csv")
        elif stem.lower().endswith("_rooms"):
            elements_csv_path = rooms_csv_path.with_name(stem[:-6] + "_elements.csv")
        else:
            elements_csv_path = rooms_csv_path.with_name(stem + "_elements.csv")
    else:
        elements_csv_path = Path(elements_csv_path)

    self._project_rooms_path = rooms_csv_path
    self._project_elements_path = elements_csv_path

    rooms = load_rooms(str(rooms_csv_path), delimiter=CSV_DELIMITER)
    elements = load_elements(str(elements_csv_path), delimiter=CSV_DELIMITER) if elements_csv_path.exists() else []
    self.rooms = {r.id: r for r in rooms}
    self.elements = list(elements)

    cfg_path = rooms_csv_path.with_name(f"{rooms_csv_path.stem}.project.json")
    if cfg_path.exists():
        try:
            self.project_cfg = load_project_cfg(cfg_path)
            try:
                self.t_out_c = float(self.project_cfg.t_out_c)
            except Exception:
                pass
        except Exception:
            pass

    try:
        self.metrics.bind(self.rooms, self.elements)
    except Exception:
        try:
            self.metrics.rooms = self.rooms
            self.metrics.elements = self.elements
        except Exception:
            pass

    for name in ("_rebuild_all_graphics", "_rebuild_rooms_graphics", "_rebuild_elements_graphics", "_recompute_and_redraw", "_update_statusbar_summary"):
        fn = getattr(self, name, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass
