from typing import List, Optional
from ..domain.models import RoomModel
from ..core.config import usage_defaults
from ..core.polygon_ops import snap_m
from .graphics import RoomPolygonItem
from .graphics import WindowLineItem
from PySide6.QtWidgets import QMessageBox
from ..core.element_access import get_room_elements
from ..core.attic_auto import is_auto_attic_element, auto_attic_marker_label
from PySide6.QtGui import QPen

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from ..domain.models import ElementModel

try:
    import shiboken6
except Exception:  # pragma: no cover - only relevant in broken PySide installs
    shiboken6 = None


class MainWindowSelectionMixin:
    def _is_valid_qt_object(self, obj) -> bool:
        if obj is None:
            return False
        if shiboken6 is None:
            return True
        try:
            return bool(shiboken6.isValid(obj))
        except Exception:
            return False

    def _safe_selected_items(self, scene):
        if not self._is_valid_qt_object(scene):
            return []
        try:
            return list(scene.selectedItems())
        except RuntimeError:
            return []

    def _scene_for_floor(self, floor: str):
        if floor == "KG":
            return getattr(self, "scene_KG", None)
        if floor == "EG":
            return getattr(self, "scene_EG", None)
        if floor == "DG":
            return getattr(self, "scene_DG", None)
        return None

    def _on_scene_selection_changed_kg(self):
        self._on_scene_selection_changed("KG")

    def _on_scene_selection_changed_eg(self):
        self._on_scene_selection_changed("EG")

    def _on_scene_selection_changed_dg(self):
        self._on_scene_selection_changed("DG")

    def _on_scene_selection_changed(self, floor: str):
        """Wird aufgerufen, wenn sich die Auswahl in einer Szene ändert."""
        scene = self._scene_for_floor(floor)
        sel = self._safe_selected_items(scene)
        rid = None
        picked_elem_uid = None
        for it in sel:
            if hasattr(it, "model") and isinstance(getattr(it, "model"), RoomModel):
                rid = it.model.id
                break
            if hasattr(it, "room") and isinstance(getattr(it, "room"), RoomModel):
                rid = it.room.id
                break
            # Falls ein Element selektiert wurde: später Liste synchronisieren
            if hasattr(it, "element") and isinstance(getattr(it, "element"), ElementModel):
                 el = getattr(it, "element")
                 if getattr(el, "uid", None):
                     picked_elem_uid = el.uid
                 if getattr(el, "room_id", None):
                     rid = el.room_id

        self._selected_room_id = rid
        self._populate_room_form()
        # Element-Selektion -> Liste markieren (ohne rekursive Signal-Kaskade)
        if picked_elem_uid:
            self._sync_list_with_uid(picked_elem_uid)

    def _populate_room_form(self):
        """Füllt das Formular mit den Daten des ausgewählten Raums."""
        rid = self._selected_room_id
        if not rid or rid not in self.rooms:
            self.ed_id.setText("")
            if hasattr(self, "list_room_elements"):
                self.list_room_elements.clear()
            self._clear_element_highlight()
            return

        r = self.rooms[rid]
        widgets = [self.ed_name, self.cb_floor, self.sp_x, self.sp_y,
                   self.sp_w, self.sp_h, self.sp_height, self.sp_tin, self.sp_n]
        if hasattr(self, "cb_usage_type"):
            widgets.append(self.cb_usage_type)
        for w in widgets:
            w.blockSignals(True)

        try:
            r.ensure_polygon()
            self.ed_id.setText(r.id)
            self.ed_name.setText(r.name)
            self.cb_floor.setCurrentText(r.floor)
            self.sp_x.setValue(r.x_m)
            self.sp_y.setValue(r.y_m)
            self.sp_w.setValue(r.w_m)
            self.sp_h.setValue(r.h_m)
            self.sp_height.setValue(r.height_m)
            self._set_usage_combo_from_room(r)
            self.sp_tin.setValue(r.t_inside_c)
            self.sp_n.setValue(r.air_change_1ph)
            rect_mode = bool(getattr(r, "is_axis_aligned_rect_polygon", lambda: False)())
            self.sp_w.setEnabled(rect_mode)
            self.sp_h.setEnabled(rect_mode)
            tip = "" if rect_mode else "Bei Polygonräumen wird die Größe über Geometrie-Handles geändert."
            self.sp_w.setToolTip(tip)
            self.sp_h.setToolTip(tip)
        finally:
            for w in widgets:
                w.blockSignals(False)

        self._refresh_selected_room_norm_status(r)
        self._populate_room_elements_list()

    def _apply_room_form(self):
        """Übernimmt die Formulardaten in das Raummodell (Pfad 2: polygon-first)."""
        rid = self._selected_room_id
        if not rid or rid not in self.rooms:
            return

        r = self.rooms[rid]
        r.ensure_polygon()
        old_floor = r.floor
        r.name = self.ed_name.text().strip() or r.id
        r.floor = self.cb_floor.currentText()

        new_x = snap_m(self.sp_x.value())
        new_y = snap_m(self.sp_y.value())
        new_w = max(0.20, snap_m(self.sp_w.value()))
        new_h = max(0.20, snap_m(self.sp_h.value()))

        if getattr(r, "is_axis_aligned_rect_polygon", lambda: False)():
            r.resize_rect_polygon_from_bbox(new_x, new_y, new_w, new_h)
        else:
            r.move_to(new_x, new_y)

        r.height_m = snap_m(self.sp_height.value(), 0.01)
        if hasattr(self, "cb_usage_type"):
            usage = self.cb_usage_type.currentData()
            r.usage_type = str(usage).strip() if usage else None
        r.t_inside_c = self.sp_tin.value()
        r.air_change_1ph = self.sp_n.value()
        self._normalize_room_geometry(r)

        it = self.room_items.get(r.id)
        if it and self._is_valid_graphics_item(it):
            if old_floor != r.floor:
                old_scene = self.scene_EG if old_floor == "EG" else self.scene_DG
                new_scene = self.scene_EG if r.floor == "EG" else self.scene_DG
                if self._is_valid_graphics_item(old_scene):
                    old_scene.removeItem(it)
                if self._is_valid_graphics_item(new_scene):
                    new_scene.addItem(it)
            if hasattr(it, "_apply_snapped_geometry"):
                it._apply_snapped_geometry(r.x_m, r.y_m, r.w_m, r.h_m)
            it.update()

        if self.autowalls_enabled:
             self._rebuild_autowalls_all()
        self._recompute_and_redraw()
        self._refresh_selected_room_norm_status(r)
        self._populate_room_elements_list()


    # ---------------- Element-Liste ----------------

    def _set_usage_combo_from_room(self, room: RoomModel) -> None:
        combo = getattr(self, "cb_usage_type", None)
        if combo is None:
            return
        usage = str(getattr(room, "usage_type", "") or "").strip().upper()
        idx = combo.findData(usage)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_room_usage_preset_changed(self, _index: int) -> None:
        combo = getattr(self, "cb_usage_type", None)
        if combo is None:
            return
        usage = str(combo.currentData() or "").strip()
        defaults = usage_defaults(usage)
        if not defaults:
            return
        self.sp_tin.blockSignals(True)
        self.sp_n.blockSignals(True)
        try:
            self.sp_tin.setValue(float(defaults.get("t_inside_c", self.sp_tin.value())))
            self.sp_n.setValue(float(defaults.get("air_change_1ph", self.sp_n.value())))
        finally:
            self.sp_tin.blockSignals(False)
            self.sp_n.blockSignals(False)

    def _refresh_selected_room_norm_status(self, room: RoomModel | None = None) -> None:
        label = getattr(self, "lbl_room_norm_status", None)
        if label is None:
            return
        if room is None:
            rid = getattr(self, "_selected_room_id", None)
            room = self.rooms.get(rid) if rid else None
        if room is None:
            label.setText("Raumstatus: —")
            return
        issues: list[str] = []
        try:
            if float(room.area_m2()) <= 0.0:
                issues.append("Fläche fehlt")
        except Exception:
            issues.append("Fläche nicht berechenbar")
        if float(getattr(room, "height_m", 0.0) or 0.0) <= 0.0:
            issues.append("Höhe fehlt")
        if float(getattr(room, "volume_m3", 0.0) or 0.0) <= 0.0:
            issues.append("Volumen fehlt")
        if not (5.0 <= float(getattr(room, "t_inside_c", 0.0) or 0.0) <= 35.0):
            issues.append("T innen prüfen")
        if float(getattr(room, "air_change_1ph", 0.0) or 0.0) < 0.0:
            issues.append("Luftwechsel prüfen")
        if not str(getattr(room, "usage_type", "") or "").strip():
            issues.append("Nutzung fehlt")
        if issues:
            label.setText("Raumstatus: Prüfen · " + "; ".join(issues))
        else:
            label.setText("Raumstatus: OK · Raumdaten vollständig")

    def _populate_room_elements_list(self):
        """Füllt die Elementliste für den selektierten Raum (inkl. shared elements)."""
        #print("populate list for:", self._selected_room_id)


        self.list_room_elements.clear()
        if not self._selected_room_id:
            return

        all_elements = self.elements.values() if isinstance(self.elements, dict) else self.elements
        elements = get_room_elements(all_elements, self._selected_room_id)
        #print("room elems:", len(elements), [e.uid for e in elements[:5]])

        for el in elements:
            # zentrale Konsistenz-Regeln (L/H/A + auto_contour Sonderfall)
            self.metrics.ensure_metrics(el)

            l_val = float(getattr(el, "length_m", 0.0) or 0.0)
            a_val = float(getattr(el, "area_m2", 0.0) or 0.0)
            u_val = float(getattr(el, "u_w_m2k", 0.0) or 0.0)

            et = getattr(el, "element_type", "") or "Element"
            auto_marker = f" [{auto_attic_marker_label(el)}]" if is_auto_attic_element(el) else ""
            label = f"{et}{auto_marker}: {a_val:.2f} m² (L: {l_val:.2f} m, U: {u_val:.2f})"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, getattr(el, "uid", None))
            self.list_room_elements.addItem(item)
        filt = getattr(self, "ed_element_filter", None)
        if filt is not None:
            self._filter_room_elements_list(filt.text())

        #print("metrics.rooms size:", len(getattr(self.metrics, "rooms", {}) or {}))
        #print("main rooms size:", len(self.rooms))

    def _find_element_by_uid(self, uid: str) -> Optional[ElementModel]:
        """Findet ein Element anhand seiner UID."""
        for e in self.elements:
            if getattr(e, "uid", None) == uid:
                return e
        return None

    def _on_room_element_selected(self) -> None:
        """Wird aufgerufen, wenn ein Element in der Liste ausgewählt wird."""
        if not hasattr(self, "list_room_elements"):
            return
        items = self.list_room_elements.selectedItems()
        if not items:
            self._clear_element_highlight()
            return
        uid = items[0].data(Qt.UserRole)
        if not uid:
            self._clear_element_highlight()
            return
        self._highlight_element_uid(uid)

    def _on_room_element_double_clicked(self, item: QListWidgetItem) -> None:
        """Öffnet den Bearbeitungsdialog für ein Element."""
        uid = item.data(Qt.UserRole)
        if not uid:
            QMessageBox.information(self, "Element", "Keine UID für dieses Element gefunden.")
            return

        e = self._find_element_by_uid(uid)
        if e is None:
            QMessageBox.warning(self, "Element", "Element nicht mehr in der Liste vorhanden.")
            return

        changed = self._edit_element_dialog(e)
        if changed:
            self._recompute_and_redraw()
            self._populate_room_elements_list()

    def _selected_graphics_items(self):
        """Gibt alle ausgewählten Grafik-Items aus allen Szenen zurück."""
        sel = []
        for scene in (
            getattr(self, "scene_KG", None),
            getattr(self, "scene_EG", None),
            getattr(self, "scene_DG", None),
        ):
            sel.extend(self._safe_selected_items(scene))
        return sel

    def _selected_room_ids(self) -> List[str]:
        """Gibt die IDs aller ausgewählten Räume zurück."""
        rids: List[str] = []
        for it in self._selected_graphics_items():
            if isinstance(it, RoomPolygonItem):
                rids.append(it.model.id)
            elif hasattr(it, "model") and isinstance(getattr(it, "model"), RoomModel):
                rids.append(it.model.id)
        if not rids and self._selected_room_id:
            rids = [self._selected_room_id]
        out: List[str] = []
        for rid in rids:
            if rid not in out:
                out.append(rid)
        return out

    def _selected_window_uids(self) -> List[str]:
        """Gibt die UIDs aller ausgewählten Fenster zurück."""
        uids: List[str] = []
        for it in self._selected_graphics_items():
            if isinstance(it, WindowLineItem):
                if it.element and it.element.uid:
                    uids.append(it.element.uid)
                continue
            if hasattr(it, "element") and isinstance(getattr(it, "element"), ElementModel):
                el = getattr(it, "element")
                if el.element_type == "Fenster" and el.uid:
                    uids.append(el.uid)
        out: List[str] = []
        for uid in uids:
            if uid not in out:
                out.append(uid)
        return out

    def _sync_list_with_graphics_selection(self, floor: str):
        return

    def _sync_list_with_uid(self, uid: str) -> None:
         """Markiert uid in der rechten Liste, ohne Re-Entrancy/Signal-Kaskaden."""
         if not uid or not hasattr(self, "list_room_elements"):
             return
         if self._in_sync_list_with_graphics_selection:
             return
         self._in_sync_list_with_graphics_selection = True
         try:
             # SelectionChanged der Liste nicht triggern lassen (Highlight bleibt stabil)
             self.list_room_elements.blockSignals(True)
             for i in range(self.list_room_elements.count()):
                 item = self.list_room_elements.item(i)
                 if item.data(Qt.UserRole) == uid:
                     self.list_room_elements.setCurrentItem(item)
                     # kein Centering, aber Scroll ist ok
                     self.list_room_elements.scrollToItem(item)
                     break
         finally:
             self.list_room_elements.blockSignals(False)
             self._in_sync_list_with_graphics_selection = False


    # -------------------------------------------------------------------------
    # 3D: Außenhülle (Skin) + Wände/Fenster als Linien
    # -------------------------------------------------------------------------

    def _highlight_element_uid(self, uid: str) -> None:
        """Hebt ein Element durch ein gelbes Rechteck hervor."""
        self._clear_element_highlight()

        it = self.element_items.get(uid)
        if it is None or not self._is_valid_graphics_item(it):
            return

        sc = it.scene()
        if sc is None or not self._is_valid_graphics_item(sc):
            return

        br = it.sceneBoundingRect()
        from PySide6.QtWidgets import QGraphicsRectItem

        r = QGraphicsRectItem(br)
        pen = QPen(Qt.yellow)
        pen.setWidth(3)
        r.setPen(pen)
        r.setBrush(Qt.transparent)
        r.setZValue(999999)
        sc.addItem(r)
        self._highlight_item = r
        #self._center_view_on_item(it)

    def _clear_element_highlight(self) -> None:
        """Entfernt die Hervorhebung."""
        if self._highlight_item is not None:
            self._safe_remove_from_scene(self._highlight_item)
        self._highlight_item = None

    def _center_view_on_item(self, item):
        """Zentriert die Ansicht auf ein Item."""
        if item is None or not self._is_valid_graphics_item(item):
            return

        scene = item.scene()
        if scene is None or not self._is_valid_graphics_item(scene):
            return

        br = item.sceneBoundingRect()
        center = br.center()

        if scene is self.scene_KG and hasattr(self, "view_KG"):
            self.view_KG.centerOn(center)
        elif scene is self.scene_EG and hasattr(self, "view_EG"):
            self.view_EG.centerOn(center)
        elif scene is self.scene_DG and hasattr(self, "view_DG"):
            self.view_DG.centerOn(center)

    # ---------------- Löschfunktionen ----------------
