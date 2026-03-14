from ..configs.project_config import save_project_cfg
try:
    import shiboken6
except Exception:
    class _ShibokenFallback:
        @staticmethod
        def isValid(obj):
            return obj is not None
    shiboken6 = _ShibokenFallback()

from typing import Any, Dict, Optional
from ..domain.models import ElementModel

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsRectItem

class MainWindowOverlayMixin:
    def _apply_element_label_visibility(self):
        """Wendet die Sichtbarkeitseinstellungen auf Element-Beschriftungen an."""
        for it in self.element_items.values():
            if not self._is_valid_graphics_item(it):
                continue

            el = None
            if hasattr(it, "element") and isinstance(getattr(it, "element"), ElementModel):
                el = getattr(it, "element")
            elif hasattr(it, "model") and isinstance(getattr(it, "model"), ElementModel):
                el = getattr(it, "model")

            if el is None:
                continue

            et = (el.element_type or "").strip().lower()

            show = True
            if et == "fenster":
                show = bool(self.show_window_labels)
            elif et in ("aussenwand", "außenwand"):
                show = bool(self.show_outerwall_labels)
            elif et == "innenwand":
                show = bool(self.show_innerwall_labels)

            if hasattr(it, "label") and getattr(it, "label") is not None:
                try:
                    if self._is_valid_graphics_item(getattr(it, "label")):
                        getattr(it, "label").setVisible(show)
                except Exception:
                    pass
            if hasattr(it, "leader") and getattr(it, "leader") is not None:
                try:
                    if self._is_valid_graphics_item(getattr(it, "leader")):
                        getattr(it, "leader").setVisible(show)
                except Exception:
                    pass

    def _on_regenerate_labels(self):
        """Wendet Label-Sichtbarkeit an und aktualisiert die Darstellung."""
        self._labels_dirty = False
        self._apply_element_label_visibility()
        # auch EG-Overlay sicherstellen (falls Szene neu aufgebaut wurde)
        try:
            self._rebuild_eg_shadow_in_dg()
        except Exception:
            pass
        try:
            self.scene_EG.update()
            self.scene_DG.update()
        except Exception:
            pass
        self.statusBar().showMessage("Labels regeneriert.", 2000)

    def _on_toggle_outerwall_labels(self, checked: bool):
        self.show_outerwall_labels = bool(checked)
        self._apply_element_label_visibility()

    def _on_toggle_innerwall_labels(self, checked: bool):
        self.show_innerwall_labels = bool(checked)
        self._apply_element_label_visibility()

    def _on_toggle_window_labels(self, checked: bool):
        self.show_window_labels = bool(checked)
        self._apply_element_label_visibility()

    def _on_toggle_debug_overlay(self, checked: bool) -> None:
        """Schaltet das Debug-Overlay um."""
        self.show_debug_overlay = bool(checked)
        try:
            self._settings.setValue("debug_overlay", bool(checked))
        except Exception:
            pass
        self._apply_room_debug_overlay(getattr(self, "_last_heatload_results", None))

    def _apply_room_debug_overlay(self, results: Optional[Dict[str, dict]]) -> None:
        """Wendet Debug-Overlay auf Räume an."""
        if results is None:
            results = {}

        for rid, it in self.room_items.items():
            if not self._is_valid_graphics_item(it):
                continue

            if not self.show_debug_overlay:
                try:
                    it.set_debug_overlay("")
                except Exception:
                    pass
                continue

            res = results.get(rid) or {}
            A_in = float(res.get("A_in_m2", 0.0) or 0.0)
            A_out = float(res.get("A_out_m2", 0.0) or 0.0)
            A_ref = float(res.get("A_ref_m2", 0.0) or 0.0)
            mode = str(res.get("floor_area_mode", "inner") or "inner")

            txt = f"A_in:  {A_in:.2f} m²\nA_out: {A_out:.2f} m²\nA_ref: {A_ref:.2f} m² ({mode})"
            try:
                it.set_debug_overlay(txt)
            except Exception:
                pass

            try:
                it.update()
            except Exception:
                pass

    def _on_toggle_area_ref_outer_action(self, checked: bool):
        """Menü/Toolbar-Action für Bezugsfläche."""
        checked = bool(checked)

        try:
            self._settings.setValue("area_ref_outer", checked)
        except Exception:
            pass

        try:
            self.project_cfg.floor_area_mode = "outer" if checked else "inner"
            if self._project_rooms_path:
                cfg_path = self._project_json_path_for_rooms(self._project_rooms_path)
                save_project_cfg(cfg_path, self.project_cfg)
        except Exception:
            pass

        if hasattr(self, "cb_area_ref_outer"):
            self.cb_area_ref_outer.blockSignals(True)
            self.cb_area_ref_outer.setChecked(checked)
            self.cb_area_ref_outer.blockSignals(False)

        self._recompute_and_redraw()

    # ---------------- Dateioperationen ----------------

    def _on_heat_toggle(self, on: bool):
        self.heatmap_enabled = bool(on)
        if hasattr(self, "chk_heat") and self.chk_heat.isChecked() != bool(on):
            self.chk_heat.blockSignals(True)
            self.chk_heat.setChecked(bool(on))
            self.chk_heat.blockSignals(False)
        if hasattr(self, "act_heatmap") and self.act_heatmap.isChecked() != bool(on):
            self.act_heatmap.blockSignals(True)
            self.act_heatmap.setChecked(bool(on))
            self.act_heatmap.blockSignals(False)
        self._recompute_and_redraw()

    def _on_autow_toggle(self, on: bool):
        self.autowalls_enabled = bool(on)
        if hasattr(self, "chk_autow") and self.chk_autow.isChecked() != bool(on):
            self.chk_autow.blockSignals(True)
            self.chk_autow.setChecked(bool(on))
            self.chk_autow.blockSignals(False)
        if hasattr(self, "act_autowalls_enabled") and self.act_autowalls_enabled.isChecked() != bool(on):
            self.act_autowalls_enabled.blockSignals(True)
            self.act_autowalls_enabled.setChecked(bool(on))
            self.act_autowalls_enabled.blockSignals(False)
        if self.autowalls_enabled:
            self._rebuild_autowalls_all()

    # ---------------- Geometrie-Änderungen ----------------
