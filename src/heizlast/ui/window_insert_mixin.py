import uuid
from .graphics import WindowLineItem
from ..core.config import DEFAULT_FACTOR, DEFAULT_U
from .graphics import PX_PER_M
from PySide6.QtWidgets import QDialog

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from ..domain.models import ElementModel
from ..core.anchors import update_edge_anchor_meta
from ..core.geometry import nearest_edge_span_for_point
from .dialogs.window_dialog import WindowDialog

class MainWindowWindowInsertMixin:
    def _on_add_window_toggle(self, checked: bool):
        """Schaltet den Fenster-Einfügemodus um."""
        self._set_opening_insert_mode("window", checked)

    def _on_add_door_toggle(self, checked: bool):
        """Schaltet den Tür-Einfügemodus um."""
        self._set_opening_insert_mode("door", checked)

    def _set_opening_insert_mode(self, mode: str, checked: bool):
        """Aktiviert genau einen Einfügemodus für Wandöffnungen."""
        active_mode = mode if checked else ""
        self._add_window_mode = active_mode == "window"
        self._add_door_mode = active_mode == "door"

        if checked and hasattr(self, 'act_polygon_room'):
            try:
                self.act_polygon_room.setChecked(False)
            except Exception:
                pass

        for attr, expected in (("act_add_window", "window"), ("act_add_door", "door")):
            action = getattr(self, attr, None)
            if action is None:
                continue
            want_checked = active_mode == expected
            if action.isChecked() != want_checked:
                action.blockSignals(True)
                action.setChecked(want_checked)
                action.blockSignals(False)

        # Im Einfügemodus dürfen vorhandene Graphics-Items keine Klicks "abfangen".
        disable_item_hits = bool(active_mode)
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
                view.viewport().setCursor(Qt.CrossCursor if active_mode else Qt.ArrowCursor)
            except Exception:
                pass

        for sc in (getattr(self, "scene_KG", None), getattr(self, "scene_EG", None), getattr(self, "scene_DG", None)):
            try:
                sc.clearSelection()
            except Exception:
                pass

        if active_mode == "window":
            self.statusBar().showMessage("Fenster-Modus aktiv: auf eine Außenwand klicken, dann Dialog ausfüllen.")
        elif active_mode == "door":
            self.statusBar().showMessage("Tür-Modus aktiv: auf eine Außenwand klicken, dann Dialog ausfüllen.")
        else:
            self.statusBar().clearMessage()


    def _add_window_at(self, floor: str, scene_pos) -> None:
        self._add_opening_at(floor, scene_pos, opening_kind="window")

    def _add_door_at(self, floor: str, scene_pos) -> None:
        self._add_opening_at(floor, scene_pos, opening_kind="door")

    def _add_opening_at(self, floor: str, scene_pos, *, opening_kind: str) -> None:
        # NICHT snappen für die Suche (sonst springt der Punkt weg)
        x_m_raw = float(scene_pos.x() / PX_PER_M)
        y_m_raw = float(scene_pos.y() / PX_PER_M)

        is_door = opening_kind == "door"
        label = "Tür" if is_door else "Fenster"

        rooms = [r for r in self.rooms.values() if getattr(r, 'floor', None) == floor]
        wall = nearest_edge_span_for_point(rooms, floor, x_m_raw, y_m_raw, prefer_outer=True, max_dist=1.2)
        if wall is None:
            #
            # Debug-Information für den Benutzer
            wand_typen = set()
            for e in self.elements:
                if e.has_geometry() and (e.floor == floor or (e.floor is None and getattr(self.rooms.get(e.room_id), 'floor', None) == floor)):
                    wand_typen.add((e.element_type or "").strip())

            msg = "Bitte nahe an einer (Außen-)Wand klicken (<= 0,5 m).\n\n"
            if wand_typen:
                msg += f"Verfügbare Wandelemente im Geschoss {floor}:\n"
                for typ in sorted(wand_typen):
                    msg += f"  • {typ}\n"
            else:
                msg += f"Keine Wandelemente im Geschoss {floor} gefunden."

            QMessageBox.information(self, f"{label} einfügen", msg)
            return
            #

        span = wall
        orient, c, a0, a1 = span.orient, span.c, span.a0, span.a1
        a_min = min(a0, a1)
        a_max = max(a0, a1)

        if orient == "H":
            cx = max(a_min, min(x_m_raw, a_max))
            cy = c
        else:
            cx = c
            cy = max(a_min, min(y_m_raw, a_max))

        default_type = "Tür" if is_door else "Fenster"
        dlg = WindowDialog(
            self,
            length_m=1.00 if is_door else 1.20,
            height_m=2.01 if is_door else 1.30,
            u_w_m2k=DEFAULT_U.get(default_type, 1.8 if is_door else 2.8),
            factor=DEFAULT_FACTOR.get(default_type, 1.0),
            center_x_m=cx,
            center_y_m=cy,
            orient=orient,
            title=f"{label} anlegen",
            element_label=label,
            element_types=("Tür", "Haustür", "Terrassentür") if is_door else None,
            default_element_type=default_type,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        element_type = str(v.get("element_type") or default_type).strip() or default_type
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

        rid = span.owner_room_id
        uid_prefix = "door" if is_door else "win"
        uid = f"{uid_prefix}_{uuid.uuid4().hex[:10]}"

        # s = Öffnungsmitte entlang der Wand, gemessen ab a_min
        if orient == "H":
            s = cx - a_min
        else:
            s = cy - a_min

        meta = update_edge_anchor_meta(
            '',
            parent=span.uid,
            orient=orient,
            c=c,
            a0=a_min,
            a1=a_max,
            s=s,
            w=L,
            rooms=getattr(span, 'room_ids', None),
        )

        e = ElementModel(
            room_id=rid,
            element_type=element_type,
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
        self.statusBar().showMessage(
            f"{label} an Wand {span.uid} eingefügt: Mitte {cx:.2f}/{cy:.2f} m, Länge {L:.2f} m.",
            5000,
        )

    # ---------------- Event-Filter für Raumzeichnen und Fenster einfügen ----------------
