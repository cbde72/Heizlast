import uuid
import math
from typing import List, Optional, Tuple
from ..domain.models import RoomModel
from .graphics import WindowLineItem
from ..core.config import DEFAULT_FACTOR, DEFAULT_U
from .graphics import PX_PER_M
from PySide6.QtWidgets import QDialog

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QMessageBox

from ..domain.models import ElementModel
from .dialogs.window_dialog import WindowDialog

class MainWindowWindowInsertMixin:
    def _on_add_window_toggle(self, checked: bool):
        """Schaltet den Fenster-Einfügemodus um."""
        self._add_window_mode = bool(checked)
        if checked and hasattr(self, 'act_polygon_room'):
            try:
                self.act_polygon_room.setChecked(False)
            except Exception:
                pass
        if hasattr(self, "act_add_window") and self.act_add_window.isChecked() != bool(checked):
            self.act_add_window.blockSignals(True)
            self.act_add_window.setChecked(bool(checked))
            self.act_add_window.blockSignals(False)

        # Im Fenster-Modus dürfen vorhandene Graphics-Items keine Klicks "abfangen".
        disable_item_hits = bool(checked)
        for item in list(getattr(self, "room_items", {}).values()) + list(getattr(self, "element_items", {}).values()):
            try:
                item.setAcceptedMouseButtons(Qt.NoButton if disable_item_hits else Qt.LeftButton)
            except Exception:
                pass
            try:
                item.setAcceptHoverEvents(not disable_item_hits)
            except Exception:
                pass
            try:
                item.setEnabled(not disable_item_hits)
            except Exception:
                pass

        for view in (getattr(self, "view_KG", None), getattr(self, "view_EG", None), getattr(self, "view_DG", None)):
            if view is None:
                continue
            try:
                view.viewport().setCursor(Qt.CrossCursor if checked else Qt.ArrowCursor)
            except Exception:
                pass

        for sc in (getattr(self, "scene_KG", None), getattr(self, "scene_EG", None), getattr(self, "scene_DG", None)):
            try:
                sc.clearSelection()
            except Exception:
                pass

        if checked:
            self.statusBar().showMessage("Fenster-Modus aktiv: auf eine Außenwand klicken, dann Dialog ausfüllen.")
        else:
            self.statusBar().clearMessage()

    def _dist_point_to_axis_segment(self, x: float, y: float, orient: str, c: float, a0: float, a1: float) -> float:
        """Berechnet den Abstand eines Punktes zu einem achsenparallelen Segment."""
        a_min = min(a0, a1)
        a_max = max(a0, a1)
        if orient == "H":
            if a_min <= x <= a_max:
                return abs(y - c)
            xx = a_min if x < a_min else a_max
            return ((x - xx) ** 2 + (y - c) ** 2) ** 0.5
        else:
            if a_min <= y <= a_max:
                return abs(x - c)
            yy = a_min if y < a_min else a_max
            return ((x - c) ** 2 + (y - yy) ** 2) ** 0.5

    def _nearest_wall(self, floor: str, x_m: float, y_m: float) -> Optional[Tuple[ElementModel, str, float, float, float]]:
        """Findet die nächste achsenparallele Wand zum angeklickten Punkt."""
        walls: List[ElementModel] = []

        for e in self.elements:
            if not e.has_geometry():
                continue

            et = (e.element_type or "").strip().lower()
            # nur Wände (Fenster explizit raus)
            if "fenster" in et:
                continue
            if not any(t in et for t in ["wand", "wall", "außen", "aussen", "innen"]):
                continue

            efloor = e.floor
            if efloor is None:
                r = self.rooms.get(e.room_id)
                efloor = r.floor if r else None
            if efloor != floor:
                continue

            walls.append(e)

        if not walls:
            return None

        AX_TOL = 1e-3  # 1 mm
        best = None
        best_d = 1e9

        for w in walls:
            x0, y0, x1, y1 = w.x0_m, w.y0_m, w.x1_m, w.y1_m
            if None in (x0, y0, x1, y1):
                continue

            x0 = float(x0); y0 = float(y0); x1 = float(x1); y1 = float(y1)
            dx = x1 - x0
            dy = y1 - y0
            if abs(dx) <= 1e-6 and abs(dy) <= 1e-6:
                continue
            # Strikt: nur achsenparallel zulassen
            if abs(dy) <= AX_TOL and abs(dx) > AX_TOL:
                orient = "H"
                c = y0
                a0 = x0
                a1 = x1
            elif abs(dx) <= AX_TOL and abs(dy) > AX_TOL:
                orient = "V"
                c = x0
                a0 = y0
                a1 = y1
            else:
                continue  # nicht achsenparallel -> ignorieren

            d = self._dist_point_to_axis_segment(x_m, y_m, orient, c, a0, a1)

            # Außenwände leicht bevorzugen
            et_w = (w.element_type or "").strip().lower()
            if "außen" in et_w or "aussen" in et_w:
                d *= 0.8

            if d < best_d:
                best_d = d
                best = (w, orient, float(c), float(a0), float(a1))

        # Toleranz für Klick daneben
        if best is None or best_d > 0.8:
            return None
        return best
    #

    def _add_window_at(self, floor: str, scene_pos) -> None:
        # NICHT snappen für die Suche (sonst springt der Punkt weg)
        x_m_raw = float(scene_pos.x() / PX_PER_M)
        y_m_raw = float(scene_pos.y() / PX_PER_M)

        wall = self._nearest_wall(floor, x_m_raw, y_m_raw)
        if wall is None:
            #
            # Debug-Information für den Benutzer
            wand_typen = set()
            for e in self.elements:
                if e.has_geometry() and (e.floor == floor or (e.floor is None and self.rooms.get(e.room_id, RoomModel()).floor == floor)):
                    wand_typen.add((e.element_type or "").strip())

            msg = "Bitte nahe an einer (Außen-)Wand klicken (<= 0,5 m).\n\n"
            if wand_typen:
                msg += f"Verfügbare Wandelemente im Geschoss {floor}:\n"
                for typ in sorted(wand_typen):
                    msg += f"  • {typ}\n"
            else:
                msg += f"Keine Wandelemente im Geschoss {floor} gefunden."

            QMessageBox.information(self, "Fenster einfügen", msg)
            return
            #

        w_el, orient, c, a0, a1 = wall
        a_min = min(a0, a1)
        a_max = max(a0, a1)

        if orient == "H":
            cx = max(a_min, min(x_m_raw, a_max))
            cy = c
        else:
            cx = c
            cy = max(a_min, min(y_m_raw, a_max))

        dlg = WindowDialog(
            self,
            length_m=1.20,
            height_m=1.30,
            u_w_m2k=DEFAULT_U.get("Fenster", 2.8),
            factor=DEFAULT_FACTOR.get("Fenster", 1.0),
            center_x_m=cx,
            center_y_m=cy,
            orient=orient
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        L = max(0.20, float(v["length_m"]))
        H = max(0.20, float(v["height_m"]))
        U = float(v["u_w_m2k"])
        F = float(v["factor"])
        cx = float(v["center_x_m"])
        cy = float(v["center_y_m"])

        half = L / 2.0
        if orient == "H":
            if L > (a_max - a_min):
                L = max(0.20, (a_max - a_min) - 0.02)
                half = L / 2.0
            cx = max(a_min + half, min(cx, a_max - half))
            x0 = cx - half
            x1 = cx + half
            y0 = y1 = c
        else:
            if L > (a_max - a_min):
                L = max(0.20, (a_max - a_min) - 0.02)
                half = L / 2.0
            cy = max(a_min + half, min(cy, a_max - half))
            y0 = cy - half
            y1 = cy + half
            x0 = x1 = c

        rid = w_el.room_id
        uid = f"win_{uuid.uuid4().hex[:10]}"
        #meta = f"host={w_el.uid or ''}|orient={orient}|c={c:.3f}|a0={a_min:.3f}|a1={a_max:.3f}"

        #
        # s = Fenstermitte entlang der Wand, gemessen ab a_min
        if orient == "H":
            s = cx - a_min
        else:
            s = cy - a_min

        meta = (
            f"parent={w_el.uid or ''}|"
            f"s={s:.4f}|w={L:.4f}|"
            f"orient={orient}|c={c:.3f}|a0={a_min:.3f}|a1={a_max:.3f}"
        )

        #print(f"[DEBUG][add-window] new window length={L}")

        e = ElementModel(
            room_id=rid,
            element_type="Fenster",
            area_m2=L * H,
            u_w_m2k=U,
            factor=F,
            floor=floor,
            x0_m=x0, y0_m=y0, x1_m=x1, y1_m=y1,
            length_m=L, height_m=H,
            uid=uid,
            meta=meta
        )
        e.label_x_m = (x0 + x1) / 2.0 + 0.15
        e.label_y_m = (y0 + y1) / 2.0 + 0.15

        self.elements.append(e)

        sc = self.scene_KG if floor == "KG" else (self.scene_EG if floor == "EG" else self.scene_DG)
        item = WindowLineItem(e, orient=orient, c_m=c, a0_m=a_min, a1_m=a_max,
                              on_geometry_changed=self._on_element_geometry_changed)
        sc.addItem(item)
        self.element_items[uid] = item

        self._recompute_and_redraw()

    # ---------------- Event-Filter für Raumzeichnen und Fenster einfügen ----------------
