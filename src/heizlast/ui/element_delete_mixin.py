from typing import List, Optional
from PySide6.QtCore import Qt
from ..core import ElementMetricsService
from ..core import meta_rooms

from PySide6.QtWidgets import QMessageBox

from ..domain.models import ElementModel

class MainWindowElementDeleteMixin:
    def _delete_selected_room_element(self) -> None:
        """Löscht das ausgewählte Element aus der Liste."""
        if not hasattr(self, "list_room_elements"):
            return
        items = self.list_room_elements.selectedItems()
        if not items:
            return

        uid = items[0].data(Qt.UserRole)
        if not uid:
            return

        e = self._find_element_by_uid(uid)
        if e is None:
            return

        et = getattr(e, "element_type", "")
        ans = QMessageBox.question(
            self,
            "Element löschen",
            f"Element wirklich löschen?\n\nTyp: {et}\nUID: {uid}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if ans != QMessageBox.Yes:
            return

        # Modell löschen
        self.elements = [x for x in self.elements if getattr(x, "uid", None) != uid]
        self.metrics = ElementMetricsService(self.rooms, self.elements)

        # Grafik + Liste aktualisieren
        self._clear_element_highlight()
        self._rebuild_elements_graphics()
        self._recompute_and_redraw()
        self._populate_room_elements_list()

    def _delete_selection(self):
        """Löscht die aktuelle Auswahl (Fenster oder Räume)."""
        if self._selected_window_uids():
            self._delete_selected_windows()
            return
        self._delete_selected_rooms()

    def _delete_selected_windows(self):
        """Löscht ausgewählte Fenster."""
        uids = self._selected_window_uids()
        if not uids:
            self.statusBar().showMessage("Kein Fenster ausgewählt.", 2500)
            return

        uid_set = set(uids)
        self.elements = [e for e in self.elements if not (e.element_type == "Fenster" and e.uid in uid_set)]
        self.metrics = ElementMetricsService(self.rooms, self.elements)

        # Grafik-Items entfernen
        for uid in uids:
            it = self.element_items.pop(uid, None)
            if it is None:
                continue
            self._safe_remove_from_scene(it)

        self._recompute_and_redraw()
        self.statusBar().showMessage(f"Fenster gelöscht: {len(uids)}", 3500)

    def _delete_selected_rooms(self):
        """Löscht ausgewählte Räume und zugehörige Elemente."""
        rids = self._selected_room_ids()
        if not rids:
            self.statusBar().showMessage("Kein Raum ausgewählt.", 2500)
            return

        txt = "\n".join(rids)
        ret = QMessageBox.question(
            self,
            "Raum löschen",
            f"Folgende Räume löschen?\n\n{txt}\n\nHinweis: Zugehörige Elemente (inkl. Fenster) werden entfernt.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return

        rid_set = set(rids)
        for rid in rids:
            self.rooms.pop(rid, None)

        #
        def _touches_deleted_room(e: ElementModel) -> bool:
            rid0 = str(getattr(e, "room_id", "") or "")
            if rid0 in rid_set:
                return True
            m = str(getattr(e, "meta", "") or "")
            return bool(meta_rooms(m) & rid_set)

        self.elements = [e for e in self.elements if not _touches_deleted_room(e)]
        self.metrics = ElementMetricsService(self.rooms, self.elements)
        #

        if self._selected_room_id in rid_set:
            self._selected_room_id = None
            self.ed_id.setText("")

        if self.autowalls_enabled:
            self._rebuild_autowalls_all()
        self._rebuild_all_graphics()
        self.statusBar().showMessage(f"Räume gelöscht: {len(rids)}", 3500)

    # ---------------- Beschriftungs-Sichtbarkeit ----------------