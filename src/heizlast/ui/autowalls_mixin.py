try:
    import shiboken6
except Exception:
    class _ShibokenFallback:
        @staticmethod
        def isValid(obj):
            return obj is not None
    shiboken6 = _ShibokenFallback()

from typing import List
from ..domain.models import ElementModel

from ..core.geometry import build_auto_walls_shared_merge

class MainWindowAutowallsMixin:
    def _rebuild_autowalls_all(self):
        def _is_auto_wall(e: ElementModel) -> bool:
            uid = str(getattr(e, "uid", "") or "")
            meta = str(getattr(e, "meta", "") or "")
            # robust: alle Auto-Wände erkennen, auch wenn uid fehlt/anders ist
            return (
                uid.startswith("auto_")
                or meta.startswith("auto_")
                or ("auto_contour" in meta)
                or ("auto_shared" in meta)
            )

        # >>> Snapshot: User-Overrides (inkl. meta ov_*) sichern, bevor Auto-Elemente entfernt werden
        snap = self._snapshot_user_overrides_for_autowalls()


        # 1) Alte Auto-Wände vollständig entfernen
        self.elements = [e for e in self.elements if not _is_auto_wall(e)]
        # 2) Neue Auto-Wände erzeugen
        autos: List[ElementModel] = []
        u_outer = float(getattr(getattr(self, "project_cfg", None), "u_aussenwand_w_m2k", 0.45))
        for floor in ("KG", "EG", "DG"):
            rooms = [r for r in self.rooms.values() if r.floor == floor]
            autos.extend(build_auto_walls_shared_merge(rooms, u_aussenwand_w_m2k=u_outer))

        # >>> Overrides aus Snapshot auf neu erzeugte Auto-Elemente anwenden + ov_* in meta persistieren
        self._apply_user_overrides_to_autowalls(autos, snap)

        # 3) Degenerierte Segmente (L=0) verwerfen + Duplikate vermeiden
        seen = set()
        clean: List[ElementModel] = []

        for e in autos:
            if not getattr(e, "has_geometry", lambda: False)():
                continue
            try:
                x0 = float(e.x0_m); y0 = float(e.y0_m); x1 = float(e.x1_m); y1 = float(e.y1_m)
            except Exception:
                continue

            dx = x1 - x0
            dy = y1 - y0

            if abs(dx) <= 1e-6 and abs(dy) <= 1e-6:
                continue  # Punkt/degeneriert

            # Duplikat-Key unabhängig von Richtung
            if abs(dy) <= 1e-6 and abs(dx) > 1e-6:
                orient = "H"
                c = round(y0, 6)
                a0, a1 = sorted([round(x0, 6), round(x1, 6)])
            elif abs(dx) <= 1e-6 and abs(dy) > 1e-6:
                orient = "V"
                c = round(x0, 6)
                a0, a1 = sorted([round(y0, 6), round(y1, 6)])
            else:
                # sollte bei Auto-Wänden nicht vorkommen, trotzdem zulassen
                orient = "S"
                c = 0.0
                a0, a1 = 0.0, 0.0

            key = (e.floor, orient, c, a0, a1, (e.element_type or "").strip().lower())
            if key in seen:
                continue
            seen.add(key)

            clean.append(e)
         #print("rooms: _rebuild_autowalls_all", len(self.rooms), "elements:", len(self.elements))
        # 5) Übernehmen + Grafik neu
        self.elements.extend(clean)
        # Fenster nach Wand-Neubau an Wände "re-anchorn"
        for r in self.rooms.values():
            self._reanchor_windows_for_room(r.id)

        self._rebuild_elements_graphics()

        if self._selected_room_id:
            self._populate_room_elements_list()
