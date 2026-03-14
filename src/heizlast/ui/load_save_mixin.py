import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from ..domain.models import RoomModel
from ..core.polygon_ops import snap_m

from PySide6.QtWidgets import QFileDialog, QMessageBox
from .dialogs.new_project_dialog import NewProjectDialog

from ..core.config import CSV_DELIMITER, DEFAULT_FACTOR, DEFAULT_U
from ..core.csv_io import load_elements, load_rooms, save_elements, save_rooms
from ..core.element_metrics import ElementMetricsService
from ..core.geometry import build_auto_walls_shared_merge
from ..core.heatload import ensure_auto_decks
from ..domain.models import ElementModel, RoomModel
from ..configs.project_config import ProjectCfg, load_project_cfg, save_project_cfg

class MainWindowLoadSaveMixin:
    def _project_json_path_for_rooms(self, rooms_csv_path: Path) -> Path:
        """Erzeugt den Pfad zur Projekt-JSON-Datei."""
        return rooms_csv_path.with_name(f"{rooms_csv_path.stem}.project.json")

    def _derive_elements_path(self, rooms_path: Path) -> Path:
        """Leitet den Pfad zur Element-CSV aus dem Raum-CSV-Pfad ab."""
        name = rooms_path.name
        stem = rooms_path.stem
        if name.lower() == "rooms.csv":
            return rooms_path.with_name("elements.csv")
        if stem.lower().endswith("_rooms"):
            return rooms_path.with_name(stem[:-6] + "_elements.csv")
        return rooms_path.with_name(stem + "_elements.csv")

    def _new_room_id(self, floor: str) -> str:
        """Erzeugt eine neue eindeutige Raum-ID."""
        base = (floor or "EG").upper()
        i = 1
        while True:
            rid = f"{base}_{i}"
            if rid not in self.rooms:
                return rid
            i += 1

    def _default_project_dir(self) -> Path:
        try:
            last_dir = getattr(self, "_last_project_dir", None) or self._settings.value("last_project_dir", "", type=str)
        except Exception:
            last_dir = ""
        if last_dir:
            return Path(str(last_dir))
        if self._project_rooms_path:
            return self._project_rooms_path.parent
        return Path.cwd()

    def _remember_project_path(self, rooms_path: Path) -> None:
        try:
            self._last_project_dir = str(rooms_path.parent)
            self._settings.setValue("last_project_dir", self._last_project_dir)
        except Exception:
            self._last_project_dir = str(rooms_path.parent)
        self._add_recent_file(rooms_path)
        try:
            self._update_statusbar_summary()
        except Exception:
            pass

    def _recent_files(self) -> list[str]:
        try:
            recent = self._settings.value("recent_project_files", [], type=list) or []
        except Exception:
            recent = []
        return [str(x) for x in recent if str(x).strip()]

    def _add_recent_file(self, rooms_path: Path) -> None:
        p = str(rooms_path)
        recent = [x for x in self._recent_files() if x != p]
        recent.insert(0, p)
        recent = recent[:10]
        try:
            self._settings.setValue("recent_project_files", recent)
        except Exception:
            pass
        if hasattr(self, "_refresh_recent_files_menu"):
            self._refresh_recent_files_menu()

    def _clear_recent_files(self) -> None:
        try:
            self._settings.setValue("recent_project_files", [])
        except Exception:
            pass
        if hasattr(self, "_refresh_recent_files_menu"):
            self._refresh_recent_files_menu()

    def _open_recent_project(self, path: str) -> None:
        rooms_path = Path(path)
        if not rooms_path.exists():
            QMessageBox.warning(self, "Zuletzt verwendet", f"Datei nicht gefunden:\n{rooms_path}")
            try:
                recent = [x for x in self._recent_files() if x != str(rooms_path)]
                self._settings.setValue("recent_project_files", recent)
            except Exception:
                pass
            if hasattr(self, "_refresh_recent_files_menu"):
                self._refresh_recent_files_menu()
            return
        self._load_project_from_path(rooms_path)

    def _show_new_project_dialog(self) -> dict | None:
        dlg = NewProjectDialog(self, default_dir=str(self._default_project_dir()))
        if dlg.exec() != dlg.DialogCode.Accepted:
            return None
        return dlg.values()

    def _create_new_project_from_dialog(self, *, open_settings_default: bool = False) -> None:
        if not self._confirm_discard_for_new_project():
            return
        values = self._show_new_project_dialog()
        if not values:
            return
        self._reset_project_state()
        try:
            self.tabs.setCurrentIndex(["KG", "EG", "DG"].index(values.get("start_floor", "EG")))
        except Exception:
            pass
        rooms_path = Path(values["rooms_path"])
        elements_path = Path(values["elements_path"])
        self._project_rooms_path = rooms_path
        self._project_elements_path = elements_path
        self._remember_project_path(rooms_path)
        if values.get("save_now", True):
            self._save_to_paths(rooms_path, elements_path)
        else:
            self._update_statusbar_summary()
        if values.get("open_settings", open_settings_default):
            try:
                self._on_project_settings()
            except Exception:
                pass
        self.statusBar().showMessage(f"Neues Projekt angelegt: {rooms_path.stem}", 4000)


    def _confirm_discard_for_new_project(self) -> bool:
        """Fragt vor dem Verwerfen des aktuellen Projektstands nach."""
        ret = QMessageBox.question(
            self,
            "Neues Projekt",
            "Aktuelles Projekt verwerfen und ein neues leeres Projekt anlegen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        return ret == QMessageBox.Yes

    def _reset_project_state(self) -> None:
        """Setzt Projektzustand, Auswahl und Szenen vollständig zurück."""
        self.rooms = {}
        self.elements = []
        try:
            self.metrics.bind(self.rooms, self.elements)
        except Exception:
            self.metrics = ElementMetricsService(self.rooms, self.elements)

        self._selected_room_id = None
        self._start_pos_scene = None
        self._preview_room = None
        self._last_heatload_results = None
        self._project_rooms_path = None
        self._project_elements_path = None
        self.project_cfg = ProjectCfg()
        self.t_out_c = float(self.project_cfg.t_out_c)

        for sc_name in ("scene_KG", "scene_EG", "scene_DG"):
            sc = getattr(self, sc_name, None)
            try:
                if sc is not None:
                    sc.clear()
            except Exception:
                pass

        self.room_items = {}
        self.element_items = {}
        self.element_items_by_uid = {}
        self.eg_shadow_items = {}

        if hasattr(self, "list_room_elements"):
            self.list_room_elements.clear()
        if hasattr(self, "ed_id"):
            self.ed_id.clear()
        if hasattr(self, "ed_name"):
            self.ed_name.clear()
        if hasattr(self, "cb_floor"):
            self.cb_floor.setCurrentText("EG")
        for name, value in (("sp_x", 0.0), ("sp_y", 0.0), ("sp_w", 4.0), ("sp_h", 4.0), ("sp_height", 2.5), ("sp_tin", 20.0), ("sp_n", 0.5)):
            w = getattr(self, name, None)
            if w is not None:
                try:
                    w.setValue(value)
                except Exception:
                    pass

        want_outer = (self.project_cfg.floor_area_mode == "outer")
        if hasattr(self, "cb_area_ref_outer"):
            self.cb_area_ref_outer.blockSignals(True)
            self.cb_area_ref_outer.setChecked(bool(want_outer))
            self.cb_area_ref_outer.blockSignals(False)
        if hasattr(self, "act_area_ref_outer"):
            self.act_area_ref_outer.blockSignals(True)
            self.act_area_ref_outer.setChecked(bool(want_outer))
            self.act_area_ref_outer.blockSignals(False)

        self._rebuild_all_graphics()
        self._update_statusbar_summary()

    def _on_new_project_empty(self):
        """Legt ein neues Projekt an."""
        self._create_new_project_from_dialog(open_settings_default=False)

    def _on_new_project_with_settings(self):
        """Legt ein neues Projekt an und öffnet direkt die Projektparameter."""
        self._create_new_project_from_dialog(open_settings_default=True)

    # ---------------- Auswahl und Formular ----------------

    def _normalize_room_geometry(self, r: RoomModel) -> None:
         try:
             if hasattr(self, "controller") and getattr(self, "controller", None) is not None:
                 self.controller.domain.normalize_room_geometry(r)
                 return
         except Exception:
             pass

         try:
             MIN_SIZE = 0.20
             r.ensure_polygon()
             r.normalize_polygon_bbox()
             r.x_m = snap_m(float(r.x_m or 0.0))
             r.y_m = snap_m(float(r.y_m or 0.0))
             r.w_m = max(MIN_SIZE, snap_m(abs(float(r.w_m or MIN_SIZE))))
             r.h_m = max(MIN_SIZE, snap_m(abs(float(r.h_m or MIN_SIZE))))
             if float(getattr(r, "height_m", 0.0) or 0.0) <= 1e-6:
                 r.height_m = 2.50
             if getattr(r, "is_axis_aligned_rect_polygon", lambda: False)():
                 r.resize_rect_polygon_from_bbox(r.x_m, r.y_m, r.w_m, r.h_m)
             else:
                 r.normalize_polygon_bbox()
             r.recompute_volume()
         except Exception:
             pass

    def _on_load(self):
        """Lädt CSV-Dateien."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "rooms.csv wählen",
            str(self._default_project_dir()),
            "CSV (*.csv)"
        )
        if not path:
            return
        self._load_project_from_path(Path(path))

    def _load_project_from_path(self, rooms_path: Path) -> bool:
        elements_path = self._derive_elements_path(rooms_path)

        try:
            rooms = load_rooms(str(rooms_path), delimiter=CSV_DELIMITER)
            elements = load_elements(str(elements_path), delimiter=CSV_DELIMITER) if elements_path.exists() else []
        except Exception as e:
            QMessageBox.critical(self, "Load error", str(e))
            return False

        for r in rooms:
            try:
                r.ensure_polygon()
                self._normalize_room_geometry(r)
            except Exception:
                pass
        self.rooms = {r.id: r for r in rooms}
        self.elements = elements

        if hasattr(self, "metrics") and self.metrics is not None:
            self.metrics.bind(self.rooms, self.elements)
        else:
            self.metrics = ElementMetricsService(self.rooms, self.elements)
        self._project_rooms_path = rooms_path
        self._project_elements_path = elements_path

        cfg_path = self._project_json_path_for_rooms(rooms_path)
        if cfg_path.exists():
            try:
                self.project_cfg = load_project_cfg(cfg_path)
            except Exception:
                self.project_cfg = ProjectCfg()
        else:
            self.project_cfg = ProjectCfg()

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

        snap = self._snapshot_auto_deck_overrides()
        try:
            cfg = self.project_cfg
            ensure_auto_decks(
                self.rooms.values(),
                self.elements,
                u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
                u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
                u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
            )
        except Exception:
            pass
        self._restore_auto_deck_overrides(snap)

        self._remember_project_path(rooms_path)
        self._rebuild_all_graphics()
        self._update_statusbar_summary()
        self.statusBar().showMessage(f"Geladen: {rooms_path.name}", 3500)
        return True

    def _save_to_paths(self, rooms_path: Path, elements_path: Path) -> bool:
        """Speichert die Daten in den angegebenen Pfaden."""
        try:
            save_rooms(str(rooms_path), list(self.rooms.values()), delimiter=CSV_DELIMITER)
            save_elements(str(elements_path), self.elements, delimiter=CSV_DELIMITER)
            self._project_rooms_path = rooms_path
            self._project_elements_path = elements_path
            self._remember_project_path(rooms_path)

            try:
                cfg_path = self._project_json_path_for_rooms(rooms_path)
                save_project_cfg(cfg_path, self.project_cfg)
            except Exception:
                pass

            self._update_statusbar_summary()
            self.statusBar().showMessage(f"Gespeichert: {rooms_path.name}", 3500)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))
            return False

    def _on_save(self):
        """Speichert die Daten."""
        if not self._project_rooms_path:
            self._on_save_as()
            return
        rooms_path = self._project_rooms_path
        elements_path = self._project_elements_path or self._derive_elements_path(rooms_path)
        self._save_to_paths(rooms_path, elements_path)

    def _on_save_as(self):
        """Speichert die Daten unter einem neuen Namen."""
        start_dir = str(self._default_project_dir())
        start_name = str(self._project_rooms_path) if self._project_rooms_path else str(Path(start_dir) / "rooms.csv")
        path, _ = QFileDialog.getSaveFileName(self, "CSV speichern unter… (rooms)", start_name, "CSV (*.csv)")
        if not path:
            return
        rooms_path = Path(path)
        if rooms_path.suffix.lower() != ".csv":
            rooms_path = rooms_path.with_suffix(".csv")
        elements_path = self._derive_elements_path(rooms_path)
        self._save_to_paths(rooms_path, elements_path)
