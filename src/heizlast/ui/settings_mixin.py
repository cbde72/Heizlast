from typing import Optional
from ..domain.models import RoomModel
from PySide6.QtWidgets import QMessageBox, QDialog, QInputDialog
from ..core.element_metrics import ElementMetricsService
from ..core.config import DEFAULT_FACTOR, DEFAULT_U
from ..core.attic_auto import derive_auto_attic_elements
from ..core.dormer_auto_elements import build_dormer_results_from_attic_cfg, dormer_cutout_area_total

from ..configs.project_config import save_project_cfg, DormerCfgDTO
from ..domain.models import ElementModel
from ..ui.dialogs.project_settings_dialog import ProjectSettingsDialog, DormerEditDialog

class MainWindowSettingsMixin:
    def _open_project_settings_dialog(self, initial_tab: str | None = None):
        dlg = ProjectSettingsDialog(self, self.project_cfg, initial_tab=initial_tab)
        if dlg.exec() != QDialog.Accepted:
            return False
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
        if hasattr(self, "_refresh_attic_preview"):
            self._refresh_attic_preview()
        self._sync_roof_profile_widgets()
        self._sync_facade_material_widgets()
        self._sync_roof_material_widgets()
        self._sync_roof_editor_tab_widgets()
        return True




    def _current_facade_material(self) -> str:
        attic = getattr(self.project_cfg, "attic", None)
        material = str(getattr(attic, "facade_material", "klinker") or "klinker").strip().lower()
        allowed = {"klinker", "putz", "holz", "beton"}
        return material if material in allowed else "klinker"

    def _facade_material_display_name(self, material: str) -> str:
        return {"klinker": "Klinker", "putz": "Putz", "holz": "Holz", "beton": "Beton"}.get(str(material or "").lower(), "Klinker")

    def _current_roof_material(self) -> str:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        material = str(getattr(attic, "roof_material", "ziegel") or "ziegel").strip().lower()
        allowed = {"ziegel"}
        return material if material in allowed else "ziegel"

    def _roof_material_display_name(self, material: str) -> str:
        return {"ziegel": "Ziegel"}.get(str(material or "").lower(), "Ziegel")

    def _sync_roof_profile_widgets(self) -> None:
        roof_type = str(getattr(getattr(self.project_cfg, "attic", None), "roof_type", "satteldach") or "satteldach").strip().lower()
        allowed = {"satteldach", "pultdach", "walmdach", "krueppelwalmdach", "flachdach", "winkeldach"}
        if roof_type not in allowed:
            roof_type = "satteldach"

        combo = getattr(self, "cb_roof_profile_quick", None)
        if combo is not None:
            label = {
                "satteldach": "Satteldach",
                "pultdach": "Pultdach",
                "walmdach": "Walmdach",
                "krueppelwalmdach": "Krüppelwalmdach",
                "flachdach": "Flachdach",
                "winkeldach": "Winkel-/Kehldach",
            }.get(roof_type, "Satteldach")
            combo.blockSignals(True)
            combo.setCurrentText(label)
            combo.blockSignals(False)

        actions = getattr(self, "_roof_profile_actions", None) or {}
        for key, act in actions.items():
            try:
                act.blockSignals(True)
                act.setChecked(str(key).lower() == roof_type)
                act.blockSignals(False)
            except Exception:
                pass

    def _persist_project_cfg_if_possible(self) -> None:
        if self._project_rooms_path:
            try:
                cfg_path = self._project_json_path_for_rooms(self._project_rooms_path)
                save_project_cfg(cfg_path, self.project_cfg)
            except Exception:
                pass

    def _sync_roof_editor_tab_widgets(self) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        if attic is None:
            return

        roof_type = str(getattr(attic, "roof_type", "satteldach") or "satteldach").strip().lower()
        ridge_orientation = str(getattr(attic, "ridge_orientation", "length") or "length").strip().lower()

        profile_combo = getattr(self, "cb_roof_tab_profile", None)
        if profile_combo is not None:
            profile_combo.blockSignals(True)
            profile_combo.setCurrentText({
                "satteldach": "Satteldach",
                "pultdach": "Pultdach",
                "walmdach": "Walmdach",
                "krueppelwalmdach": "Krüppelwalmdach",
                "flachdach": "Flachdach",
                "winkeldach": "Winkel-/Kehldach",
            }.get(roof_type, "Satteldach"))
            profile_combo.blockSignals(False)

        ridge_combo = getattr(self, "cb_roof_tab_ridge", None)
        if ridge_combo is not None:
            ridge_combo.blockSignals(True)
            ridge_combo.setCurrentText("First quer" if ridge_orientation == "width" else "First längs")
            ridge_combo.blockSignals(False)

        for attr, value in (
            ("sp_roof_tab_pitch", float(getattr(attic, "roof_pitch_deg", 35.0) or 0.0)),
            ("sp_roof_tab_knee", float(getattr(attic, "knee_wall_height_m", 1.0) or 0.0)),
            ("sp_roof_tab_overhang", float(getattr(attic, "roof_overhang_m", 0.30) or 0.0)),
        ):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.blockSignals(True)
                widget.setValue(value)
                widget.blockSignals(False)

        line_kind_combo = getattr(self, "cb_roof_tab_line_kind", None)
        editor = getattr(self, "roof_line_editor_tab", None)
        if line_kind_combo is not None and editor is not None:
            current_kind = str(getattr(editor, "_current_kind", "first") or "first").strip().lower()
            line_kind_combo.blockSignals(True)
            line_kind_combo.setCurrentText({"first": "First", "grat": "Grat", "kehle": "Kehle"}.get(current_kind, "First"))
            line_kind_combo.blockSignals(False)

        if editor is not None:
            editor.set_lines(list(getattr(attic, "roof_lines", []) or []))

        self._sync_roof_editor_line_list()
        self._sync_roof_editor_dormer_list()
        self._refresh_roof_editor_dormer_actions()
        self._sync_roof_editor_facet_list()
        self._sync_roof_editor_summary()

    def _sync_roof_editor_summary(self) -> None:
        geom_getter = getattr(self, "_current_attic_geometry", None)
        geom = geom_getter() if callable(geom_getter) else None
        metrics = {
            "lbl_roof_metric_area": "–",
            "lbl_roof_metric_facets": "–",
            "lbl_roof_metric_lines": "–",
            "lbl_roof_metric_height": "–",
        }
        if geom is not None:
            try:
                facets = geom.roof_facets()
            except Exception:
                facets = []
            try:
                metrics["lbl_roof_metric_area"] = f"{float(getattr(geom, 'roof_area_total_m2', 0.0)):.2f} m²"
                metrics["lbl_roof_metric_facets"] = str(len(facets))
                metrics["lbl_roof_metric_lines"] = str(len(list(getattr(geom, 'roof_lines', []) or [])))
                metrics["lbl_roof_metric_height"] = f"{float(getattr(geom, 'total_height_m', 0.0)):.2f} m"
            except Exception:
                pass
        for attr, value in metrics.items():
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.setText(value)
        self._sync_roof_editor_balance()
        self._sync_roof_editor_validation()

    def _sync_roof_editor_balance(self) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        geom_getter = getattr(self, "_current_attic_geometry", None)
        geom = geom_getter() if callable(geom_getter) else None
        values = {
            "lbl_roof_balance_gross": "–",
            "lbl_roof_balance_openings": "–",
            "lbl_roof_balance_effective": "–",
            "lbl_roof_balance_heat": "–",
        }
        if attic is not None and geom is not None:
            try:
                roof_window_area = (
                    max(0, int(getattr(attic, "roof_window_count", 0) or 0))
                    * max(0.0, float(getattr(attic, "roof_window_width_m", 0.0) or 0.0))
                    * max(0.0, float(getattr(attic, "roof_window_height_m", 0.0) or 0.0))
                )
                try:
                    dormer_cutout = dormer_cutout_area_total(build_dormer_results_from_attic_cfg(attic))
                except Exception:
                    dormer_cutout = 0.0
                rooms = [r for r in getattr(self, "rooms", {}).values() if str(getattr(r, "floor", "") or "").strip().upper() == "DG"]
                auto = derive_auto_attic_elements(rooms, attic) if rooms else []
                effective_roof = sum(
                    float(getattr(e, "area_m2", 0.0) or 0.0)
                    for e in auto
                    if getattr(e, "element_type", "") == "Dach" and not str(getattr(e, "uid", "") or "").startswith("auto_dormer_")
                )
                if effective_roof <= 0.0:
                    effective_roof = max(0.0, float(getattr(geom, "roof_area_total_m2", 0.0)) - roof_window_area - dormer_cutout)
                roof_phi = sum(
                    float(getattr(e, "area_m2", 0.0) or 0.0) * float(getattr(e, "u_w_m2k", 0.0) or 0.0) * float(getattr(e, "factor", 1.0) or 1.0)
                    for e in auto
                    if getattr(e, "element_type", "") == "Dach"
                )
                values["lbl_roof_balance_gross"] = f"{float(getattr(geom, 'roof_area_total_m2', 0.0)):.2f} m²"
                values["lbl_roof_balance_openings"] = f"-{roof_window_area + dormer_cutout:.2f} m²"
                values["lbl_roof_balance_effective"] = f"{effective_roof:.2f} m²"
                values["lbl_roof_balance_heat"] = f"{roof_phi:.1f} W/K"
            except Exception:
                pass
        for attr, value in values.items():
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.setText(value)

    def _sync_roof_editor_validation(self) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        label = getattr(self, "lbl_roof_validation", None)
        if label is None:
            return
        if attic is None or not bool(getattr(attic, "enabled", False)):
            label.setText("○ DG-Dachprofil ist deaktiviert.")
            return
        warnings: list[str] = []
        errors: list[str] = []
        if abs(float(getattr(attic, "ridge_offset_ratio", 0.0) or 0.0)) > 1e-9 and getattr(attic, "ridge_height_m", None) is None:
            warnings.append("Firstversatz ohne explizite Firsthöhe")
        if str(getattr(attic, "roof_boundary", "outside") or "outside").strip().lower() == "unheated_attic":
            warnings.append("Dachboden/Abseite: Faktor prüfen")
        if int(getattr(attic, "roof_window_count", 0) or 0) > 0 and float(getattr(attic, "roof_window_width_m", 0.0) or 0.0) <= 0.0:
            errors.append("Dachfensterbreite fehlt")
        if list(getattr(attic, "dormers", []) or []) and str(getattr(attic, "roof_type", "satteldach") or "satteldach").strip().lower() == "flachdach":
            errors.append("Gauben bei Flachdach deaktivieren")
        if errors:
            label.setText("● Prüfen: " + "; ".join(errors + warnings))
        elif warnings:
            label.setText("● Hinweis: " + "; ".join(warnings))
        else:
            label.setText("● Dach/Giebel-Eingaben vollständig für DIN-nahe Bilanz.")

    def _sync_roof_editor_facet_list(self) -> None:
        lst = getattr(self, "lst_roof_tab_facets", None)
        if lst is None:
            return
        geom_getter = getattr(self, "_current_attic_geometry", None)
        geom = geom_getter() if callable(geom_getter) else None
        facets = []
        if geom is not None:
            try:
                facets = list(geom.roof_facets() or [])
            except Exception:
                facets = []
        lst.clear()
        if not facets:
            lst.addItem("Keine Facetten berechnet")
        else:
            for facet in facets:
                kinds = ", ".join(str(k).capitalize() for k in list(getattr(facet, "boundary_kinds", []) or []) if str(k).strip())
                suffix = f" · Grenzen: {kinds}" if kinds else ""
                lst.addItem(f"{getattr(facet, 'label', 'RF')} · Plan {float(getattr(facet, 'plan_area_m2', 0.0)):.2f} m² · Fläche {float(getattr(facet, 'surface_area_m2', 0.0)):.2f} m²{suffix}")
        badge = getattr(self, "lbl_roof_facet_count", None)
        if badge is not None:
            badge.setText(f"{len(facets)} Facetten")

    def _sync_roof_editor_line_list(self) -> None:
        lst = getattr(self, "lst_roof_tab_lines", None)
        editor = getattr(self, "roof_line_editor_tab", None)
        if lst is None or editor is None:
            return
        current = int(getattr(editor, "_selected_index", -1) or -1)
        lines = editor.current_lines()
        lst.blockSignals(True)
        lst.clear()
        for idx, line in enumerate(lines, start=1):
            kind = {"first": "First", "grat": "Grat", "kehle": "Kehle"}.get(str(getattr(line, "kind", "first") or "first").lower(), str(getattr(line, "kind", "Linie")))
            lst.addItem(f"{idx:02d} · {kind} · ({line.x1_ratio:.2f}, {line.y1_ratio:.2f}) → ({line.x2_ratio:.2f}, {line.y2_ratio:.2f})")
        if 0 <= current < lst.count():
            lst.setCurrentRow(current)
        lst.blockSignals(False)
        badge = getattr(self, "lbl_roof_line_count", None)
        if badge is not None:
            badge.setText(f"{len(lines)} Linien")
    def _friendly_roof_editor_dormer_label(self, dormer: DormerCfgDTO) -> str:
        tmap = {"schleppgaube": "Schleppgaube", "satteldachgaube": "Satteldachgaube", "flachdachgaube": "Flachdachgaube"}
        smap = {"left": "links", "right": "rechts", "front": "vorne", "back": "hinten"}
        pitch = "auto" if getattr(dormer, "roof_pitch_deg", None) is None else f"{float(getattr(dormer, 'roof_pitch_deg', 0.0)):.1f}°"
        return (
            f"{getattr(dormer, 'id', 'gaube')} · {tmap.get(str(getattr(dormer, 'dormer_type', 'schleppgaube')), str(getattr(dormer, 'dormer_type', 'schleppgaube')))} · "
            f"{smap.get(str(getattr(dormer, 'roof_side', 'right')), str(getattr(dormer, 'roof_side', 'right')))} · "
            f"Pos {float(getattr(dormer, 'center_along_m', 0.0)):.2f} m · B {float(getattr(dormer, 'width_m', 0.0)):.2f} m · T {float(getattr(dormer, 'depth_m', 0.0)):.2f} m · Dach {pitch}"
        )

    def _roof_editor_active_dormer_sides(self) -> tuple[str, ...]:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        ridge_orientation = str(getattr(attic, "ridge_orientation", "length") or "length").strip().lower() if attic is not None else "length"
        return ("front", "back") if ridge_orientation == "width" else ("left", "right")

    def _sync_roof_editor_dormer_list(self) -> None:
        lst = getattr(self, "lst_roof_tab_dormers", None)
        if lst is None:
            return
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        dormers = list(getattr(attic, "dormers", []) or []) if attic is not None else []
        current = lst.currentRow()
        lst.blockSignals(True)
        lst.clear()
        for dormer in dormers:
            lst.addItem(self._friendly_roof_editor_dormer_label(dormer))
        if dormers:
            lst.setCurrentRow(max(0, min(current, len(dormers) - 1)))
        lst.blockSignals(False)
        badge = getattr(self, "lbl_roof_dormer_count", None)
        if badge is not None:
            badge.setText(f"{len(dormers)} Gauben")

    def _sync_roof_editor_preview_interaction_state(self) -> None:
        panel = getattr(self, "roof_editor_preview_panel", None)
        if panel is None:
            return
        active = bool(getattr(self, "_roof_editor_place_dormer_active", False))
        draw_mode = bool(getattr(self, "_roof_editor_draw_dormer_active", False))
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        lst = getattr(self, "lst_roof_tab_dormers", None)
        dormers = list(getattr(attic, "dormers", []) or []) if attic is not None else []
        row = lst.currentRow() if lst is not None else -1
        has_selection = row >= 0 and row < len(dormers)
        dormer = dormers[row] if has_selection else self._make_default_roof_editor_dormer()
        try:
            panel.set_dormer_preview_state(
                active,
                has_selection=has_selection,
                dormer_width_m=float(getattr(dormer, "width_m", 1.80) or 1.80),
                min_edge_clearance_m=float(getattr(dormer, "min_edge_clearance_m", 0.40) or 0.40),
                draw_mode=draw_mode,
            )
            panel.set_selected_dormer_state(self._selected_roof_editor_dormer_preview_payload())
        except Exception:
            pass

    def _refresh_roof_editor_dormer_actions(self) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        roof_type = str(getattr(attic, "roof_type", "satteldach") or "satteldach").strip().lower() if attic is not None else "satteldach"
        enabled = attic is not None and roof_type != "flachdach"
        lst = getattr(self, "lst_roof_tab_dormers", None)
        has_selection = lst is not None and lst.currentRow() >= 0
        for attr, state in (("btn_roof_tab_add_dormer", enabled), ("btn_roof_tab_edit_dormer", enabled and has_selection), ("btn_roof_tab_delete_dormer", enabled and has_selection), ("btn_roof_tab_place_dormer", enabled), ("btn_roof_tab_draw_dormer", enabled), ("btn_roof_tab_place_window", enabled)):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.setEnabled(bool(state))
        if lst is not None:
            lst.setEnabled(bool(enabled))
        hint = getattr(self, "lbl_roof_dormer_place_hint", None)
        if hint is not None:
            hint.setText(
                "Tipp: 'Gaube zeichnen' für Click+Drag-Erzeugung oder 'Grafisch platzieren' für Klickplatzierung, Verschieben und Resize verwenden."
                if enabled else
                "Grafische Gauben-Platzierung ist für Flachdächer deaktiviert."
            )
        self._sync_roof_editor_preview_interaction_state()

    def _set_roof_editor_draw_mode(self, active: bool, *, update_button: bool = True) -> None:
        self._roof_editor_draw_dormer_active = bool(active)
        btn = getattr(self, "btn_roof_tab_draw_dormer", None)
        if btn is not None and update_button and btn.isChecked() != bool(active):
            btn.blockSignals(True)
            btn.setChecked(bool(active))
            btn.blockSignals(False)
        if bool(active):
            self._roof_editor_place_dormer_active = False
            other = getattr(self, "btn_roof_tab_place_dormer", None)
            if other is not None and other.isChecked():
                other.blockSignals(True)
                other.setChecked(False)
                other.blockSignals(False)
            self._set_roof_editor_window_place_mode(False)
        hint = getattr(self, "lbl_roof_dormer_place_hint", None)
        if hint is not None:
            if bool(active):
                hint.setText("Zeichenmodus aktiv: Im Dachplan klicken und ziehen, um eine neue Gaube grafisch aufzuziehen. Die Breite wird aus der Ziehstrecke erzeugt.")
            else:
                attic = getattr(getattr(self, "project_cfg", None), "attic", None)
                roof_type = str(getattr(attic, "roof_type", "satteldach") or "satteldach").strip().lower() if attic is not None else "satteldach"
                hint.setText(
                    "Grafische Gauben-Platzierung ist für Flachdächer deaktiviert."
                    if roof_type == "flachdach" else
                    "Tipp: 'Gaube zeichnen' für Click+Drag-Erzeugung oder 'Grafisch platzieren' für Klickplatzierung, Verschieben und Resize verwenden."
                )
        self._sync_roof_editor_preview_interaction_state()

    def _on_toggle_roof_editor_dormer_draw_mode(self, checked: bool) -> None:
        self._set_roof_editor_draw_mode(bool(checked), update_button=False)

    def _set_roof_editor_place_mode(self, active: bool, *, update_button: bool = True) -> None:
        self._roof_editor_place_dormer_active = bool(active)
        if bool(active):
            self._roof_editor_draw_dormer_active = False
            other = getattr(self, "btn_roof_tab_draw_dormer", None)
            if other is not None and other.isChecked():
                other.blockSignals(True)
                other.setChecked(False)
                other.blockSignals(False)
            self._set_roof_editor_window_place_mode(False)
        btn = getattr(self, "btn_roof_tab_place_dormer", None)
        if btn is not None and update_button and btn.isChecked() != bool(active):
            btn.blockSignals(True)
            btn.setChecked(bool(active))
            btn.blockSignals(False)
        hint = getattr(self, "lbl_roof_dormer_place_hint", None)
        if hint is not None:
            if bool(active):
                hint.setText("Platzierungsmodus aktiv: im Dachplan bewegen und klicken. Mit Auswahl wird die markierte Gaube verschoben, sonst wird eine neue Gaube angelegt. Einfügemarker und Hover-Vorschau zeigen die Zielposition.")
            else:
                attic = getattr(getattr(self, "project_cfg", None), "attic", None)
                roof_type = str(getattr(attic, "roof_type", "satteldach") or "satteldach").strip().lower() if attic is not None else "satteldach"
                hint.setText(
                    "Grafische Gauben-Platzierung ist für Flachdächer deaktiviert."
                    if roof_type == "flachdach" else
                    "Tipp: 'Gaube zeichnen' für Click+Drag-Erzeugung oder 'Grafisch platzieren' für Klickplatzierung, Verschieben und Resize verwenden."
                )
        self._sync_roof_editor_preview_interaction_state()

    def _on_toggle_roof_editor_dormer_place_mode(self, checked: bool) -> None:
        self._set_roof_editor_place_mode(bool(checked), update_button=False)

    def _set_roof_editor_window_place_mode(self, active: bool, *, update_button: bool = True) -> None:
        self._roof_editor_place_window_active = bool(active)
        if bool(active):
            self._set_roof_editor_draw_mode(False)
            self._set_roof_editor_place_mode(False)
        btn = getattr(self, "btn_roof_tab_place_window", None)
        if btn is not None and update_button and btn.isChecked() != bool(active):
            btn.blockSignals(True)
            btn.setChecked(bool(active))
            btn.blockSignals(False)
        hint = getattr(self, "lbl_roof_dormer_place_hint", None)
        if hint is not None:
            hint.setText(
                "Dachfenster-Platzierung aktiv: im Dachplan auf die gewünschte Dachseite klicken."
                if bool(active) else
                "Tipp: 'Gaube zeichnen' für Click+Drag-Erzeugung oder 'Grafisch platzieren' für Klickplatzierung, Verschieben und Resize verwenden."
            )

    def _on_toggle_roof_editor_window_place_mode(self, checked: bool) -> None:
        self._set_roof_editor_window_place_mode(bool(checked), update_button=False)

    def _clamp_roof_editor_dormer_center(self, dormer: DormerCfgDTO, along_m: float) -> float:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        ridge_orientation = str(getattr(attic, "ridge_orientation", "length") or "length").strip().lower() if attic is not None else "length"
        along_span = float(getattr(attic, "building_width_m", 8.0) or 8.0) if ridge_orientation == "width" else float(getattr(attic, "building_length_m", 10.0) or 10.0)
        min_clearance = max(0.0, float(getattr(dormer, "min_edge_clearance_m", 0.40) or 0.0))
        half_width = max(0.05, float(getattr(dormer, "width_m", 1.80) or 1.80) / 2.0)
        lo = min_clearance + half_width
        hi = max(lo, along_span - min_clearance - half_width)
        return max(lo, min(hi, float(along_m or 0.0)))

    def _selected_roof_editor_dormer_preview_payload(self) -> dict | None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        lst = getattr(self, "lst_roof_tab_dormers", None)
        if attic is None or lst is None:
            return None
        row = lst.currentRow()
        dormers = list(getattr(attic, "dormers", []) or [])
        if row < 0 or row >= len(dormers):
            return None
        dormer = dormers[row]
        return {
            "along_m": float(getattr(dormer, "center_along_m", 0.0) or 0.0),
            "side": str(getattr(dormer, "roof_side", self._roof_editor_active_dormer_sides()[-1]) or self._roof_editor_active_dormer_sides()[-1]),
            "width_m": float(getattr(dormer, "width_m", 1.80) or 1.80),
            "depth_m": float(getattr(dormer, "depth_m", 1.40) or 1.40),
            "min_edge_clearance_m": float(getattr(dormer, "min_edge_clearance_m", 0.40) or 0.40),
        }

    def _apply_roof_editor_dormer_payload(self, payload: dict, *, finalize: bool) -> bool:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        lst = getattr(self, "lst_roof_tab_dormers", None)
        if attic is None or lst is None:
            return False
        row = lst.currentRow()
        dormers = list(getattr(attic, "dormers", []) or [])
        if row < 0 or row >= len(dormers):
            return False
        base = dormers[row]
        side = str((payload or {}).get("side", getattr(base, "roof_side", self._roof_editor_active_dormer_sides()[-1])) or getattr(base, "roof_side", self._roof_editor_active_dormer_sides()[-1]))
        width_m = max(0.30, float((payload or {}).get("width_m", getattr(base, "width_m", 1.80)) or getattr(base, "width_m", 1.80) or 1.80))
        depth_m = max(0.20, float((payload or {}).get("depth_m", getattr(base, "depth_m", 1.40)) or getattr(base, "depth_m", 1.40) or 1.40))
        probe = DormerCfgDTO(
            id=str(getattr(base, "id", f"gaube_{row + 1}") or f"gaube_{row + 1}"),
            dormer_type=str(getattr(base, "dormer_type", "schleppgaube") or "schleppgaube"),
            roof_side=side,
            center_along_m=float(getattr(base, "center_along_m", 0.0) or 0.0),
            width_m=width_m,
            depth_m=depth_m,
            front_height_m=float(getattr(base, "front_height_m", 1.20) or 1.20),
            window_count=int(getattr(base, "window_count", 1) or 0),
            window_width_m=float(getattr(base, "window_width_m", 1.20) or 1.20),
            window_height_m=float(getattr(base, "window_height_m", 1.20) or 1.20),
            sill_height_m=float(getattr(base, "sill_height_m", 0.90) or 0.90),
            roof_pitch_deg=getattr(base, "roof_pitch_deg", None),
            min_edge_clearance_m=float(getattr(base, "min_edge_clearance_m", 0.40) or 0.40),
        )
        along_m = self._clamp_roof_editor_dormer_center(probe, float((payload or {}).get("along_m", getattr(base, "center_along_m", 0.0)) or 0.0))
        dormers[row] = DormerCfgDTO(
            id=probe.id,
            dormer_type=probe.dormer_type,
            roof_side=side,
            center_along_m=along_m,
            width_m=width_m,
            depth_m=depth_m,
            front_height_m=probe.front_height_m,
            window_count=probe.window_count,
            window_width_m=probe.window_width_m,
            window_height_m=probe.window_height_m,
            sill_height_m=probe.sill_height_m,
            roof_pitch_deg=probe.roof_pitch_deg,
            min_edge_clearance_m=probe.min_edge_clearance_m,
        )
        attic.dormers = dormers
        self._sync_attic_legacy_dormer_fields()
        if finalize:
            self._persist_project_cfg_if_possible()
        self._recompute_and_redraw()
        self._refresh_attic_preview()
        self._sync_roof_editor_tab_widgets()
        self._sync_roof_editor_preview_interaction_state()
        if hasattr(self, "lst_roof_tab_dormers"):
            self.lst_roof_tab_dormers.setCurrentRow(row)
        return True

    def _on_roof_editor_dormer_drag_started(self, payload: dict) -> None:
        try:
            self.statusBar().showMessage("Gaube wird per Drag&Drop verschoben …", 1200)
        except Exception:
            pass

    def _on_roof_editor_dormer_drag_moved(self, payload: dict) -> None:
        self._apply_roof_editor_dormer_payload(payload, finalize=False)

    def _on_roof_editor_dormer_drag_finished(self, payload: dict) -> None:
        if self._apply_roof_editor_dormer_payload(payload, finalize=True):
            try:
                self.statusBar().showMessage("Gaube per Drag&Drop verschoben.", 2500)
            except Exception:
                pass
            if bool(getattr(self, "_roof_editor_place_dormer_active", False)):
                self._set_roof_editor_place_mode(False)

    def _on_roof_editor_dormer_resize_started(self, payload: dict) -> None:
        try:
            self.statusBar().showMessage("Gaube wird über Resize-Griffe angepasst …", 1200)
        except Exception:
            pass

    def _on_roof_editor_dormer_resize_moved(self, payload: dict) -> None:
        self._apply_roof_editor_dormer_payload(payload, finalize=False)

    def _on_roof_editor_dormer_resize_finished(self, payload: dict) -> None:
        if self._apply_roof_editor_dormer_payload(payload, finalize=True):
            try:
                self.statusBar().showMessage("Gaube per Resize-Griff angepasst.", 2500)
            except Exception:
                pass
            if bool(getattr(self, "_roof_editor_place_dormer_active", False)):
                self._set_roof_editor_place_mode(False)

    def _on_roof_editor_dormer_draw_finished(self, payload: dict) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        if attic is None or not bool(getattr(self, "_roof_editor_draw_dormer_active", False)):
            return
        roof_type = str(getattr(attic, "roof_type", "satteldach") or "satteldach").strip().lower()
        if roof_type == "flachdach":
            self._set_roof_editor_draw_mode(False)
            return
        created = self._make_default_roof_editor_dormer()
        ridge_orientation = str((payload or {}).get("ridge_orientation", getattr(attic, "ridge_orientation", "length")) or getattr(attic, "ridge_orientation", "length")).strip().lower()
        side = str((payload or {}).get("draw_side", (payload or {}).get("side", self._roof_editor_active_dormer_sides()[-1])) or self._roof_editor_active_dormer_sides()[-1])
        if ridge_orientation == "width":
            start_v = float((payload or {}).get("draw_start_x_m", 0.0) or 0.0)
            end_v = float((payload or {}).get("x_m", start_v) or start_v)
        else:
            start_v = float((payload or {}).get("draw_start_y_m", 0.0) or 0.0)
            end_v = float((payload or {}).get("y_m", start_v) or start_v)
        width_m = max(0.30, abs(end_v - start_v))
        center_target = 0.5 * (float((payload or {}).get("draw_start_along_m", 0.0) or 0.0) + float((payload or {}).get("along_m", 0.0) or 0.0))
        created = DormerCfgDTO(
            id=str(getattr(created, "id", f"gaube_{len(list(getattr(attic, 'dormers', []) or [])) + 1}") or f"gaube_{len(list(getattr(attic, 'dormers', []) or [])) + 1}"),
            dormer_type=str(getattr(created, "dormer_type", "schleppgaube") or "schleppgaube"),
            roof_side=side,
            center_along_m=self._clamp_roof_editor_dormer_center(created, center_target),
            width_m=width_m,
            depth_m=float(getattr(created, "depth_m", 1.40) or 1.40),
            front_height_m=float(getattr(created, "front_height_m", 1.20) or 1.20),
            window_count=int(getattr(created, "window_count", 1) or 0),
            window_width_m=float(getattr(created, "window_width_m", 1.20) or 1.20),
            window_height_m=float(getattr(created, "window_height_m", 1.20) or 1.20),
            sill_height_m=float(getattr(created, "sill_height_m", 0.90) or 0.90),
            roof_pitch_deg=getattr(created, "roof_pitch_deg", None),
            min_edge_clearance_m=float(getattr(created, "min_edge_clearance_m", 0.40) or 0.40),
        )
        dormers = list(getattr(attic, "dormers", []) or [])
        dormers.append(created)
        attic.dormers = dormers
        self._sync_attic_legacy_dormer_fields()
        self._persist_project_cfg_if_possible()
        self._recompute_and_redraw()
        self._refresh_attic_preview()
        self._sync_roof_editor_tab_widgets()
        lst = getattr(self, "lst_roof_tab_dormers", None)
        if lst is not None:
            lst.setCurrentRow(len(dormers) - 1)
        self._sync_roof_editor_preview_interaction_state()
        self._set_roof_editor_draw_mode(False)
        try:
            self.statusBar().showMessage("Gaube grafisch aufgezogen.", 2500)
        except Exception:
            pass

    def _on_roof_editor_preview_plan_clicked(self, payload: dict) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        if attic is not None and bool(getattr(self, "_roof_editor_place_window_active", False)):
            side = str((payload or {}).get("side", "right") or "right").strip().lower()
            previous = str(getattr(attic, "roof_window_side", "right") or "right").strip().lower()
            active = {"left", "right"} if str(getattr(attic, "ridge_orientation", "length") or "length").strip().lower() == "length" else {"front", "back"}
            attic.roof_window_count = int(getattr(attic, "roof_window_count", 0) or 0) + 1
            attic.roof_window_side = side if previous not in active or previous == side or int(getattr(attic, "roof_window_count", 0) or 0) == 1 else "both"
            self._persist_project_cfg_if_possible()
            self._recompute_and_redraw()
            self._refresh_attic_preview()
            self._sync_roof_editor_tab_widgets()
            self._set_roof_editor_window_place_mode(False)
            try:
                self.statusBar().showMessage(f"Dachfenster eingefügt: {side}", 2500)
            except Exception:
                pass
            return
        if attic is None or bool(getattr(self, "_roof_editor_draw_dormer_active", False)) or not bool(getattr(self, "_roof_editor_place_dormer_active", False)):
            return
        roof_type = str(getattr(attic, "roof_type", "satteldach") or "satteldach").strip().lower()
        if roof_type == "flachdach":
            QMessageBox.information(self, "Gauben-Platzierung", "Für Flachdächer ist die grafische Gauben-Platzierung deaktiviert.")
            self._set_roof_editor_place_mode(False)
            return
        lst = getattr(self, "lst_roof_tab_dormers", None)
        row = lst.currentRow() if lst is not None else -1
        dormers = list(getattr(attic, "dormers", []) or [])
        side = str((payload or {}).get("side", self._roof_editor_active_dormer_sides()[-1]) or self._roof_editor_active_dormer_sides()[-1])
        along_m = float((payload or {}).get("along_m", 0.0) or 0.0)
        moved_existing = row >= 0 and row < len(dormers)
        if moved_existing:
            base = dormers[row]
            updated = DormerCfgDTO(
                id=str(getattr(base, "id", f"gaube_{row + 1}") or f"gaube_{row + 1}"),
                dormer_type=str(getattr(base, "dormer_type", "schleppgaube") or "schleppgaube"),
                roof_side=side,
                center_along_m=self._clamp_roof_editor_dormer_center(base, along_m),
                width_m=float(getattr(base, "width_m", 1.80) or 1.80),
                depth_m=float(getattr(base, "depth_m", 1.40) or 1.40),
                front_height_m=float(getattr(base, "front_height_m", 1.20) or 1.20),
                window_count=int(getattr(base, "window_count", 1) or 0),
                window_width_m=float(getattr(base, "window_width_m", 1.20) or 1.20),
                window_height_m=float(getattr(base, "window_height_m", 1.20) or 1.20),
                sill_height_m=float(getattr(base, "sill_height_m", 0.90) or 0.90),
                roof_pitch_deg=getattr(base, "roof_pitch_deg", None),
                min_edge_clearance_m=float(getattr(base, "min_edge_clearance_m", 0.40) or 0.40),
            )
            dormers[row] = updated
        else:
            created = self._make_default_roof_editor_dormer()
            created = DormerCfgDTO(
                id=str(getattr(created, "id", f"gaube_{len(dormers) + 1}") or f"gaube_{len(dormers) + 1}"),
                dormer_type=str(getattr(created, "dormer_type", "schleppgaube") or "schleppgaube"),
                roof_side=side,
                center_along_m=self._clamp_roof_editor_dormer_center(created, along_m),
                width_m=float(getattr(created, "width_m", 1.80) or 1.80),
                depth_m=float(getattr(created, "depth_m", 1.40) or 1.40),
                front_height_m=float(getattr(created, "front_height_m", 1.20) or 1.20),
                window_count=int(getattr(created, "window_count", 1) or 0),
                window_width_m=float(getattr(created, "window_width_m", 1.20) or 1.20),
                window_height_m=float(getattr(created, "window_height_m", 1.20) or 1.20),
                sill_height_m=float(getattr(created, "sill_height_m", 0.90) or 0.90),
                roof_pitch_deg=getattr(created, "roof_pitch_deg", None),
                min_edge_clearance_m=float(getattr(created, "min_edge_clearance_m", 0.40) or 0.40),
            )
            dormers.append(created)
            row = len(dormers) - 1
        attic.dormers = dormers
        self._sync_attic_legacy_dormer_fields()
        self._persist_project_cfg_if_possible()
        self._recompute_and_redraw()
        self._refresh_attic_preview()
        self._sync_roof_editor_tab_widgets()
        if lst is not None and row >= 0:
            lst.setCurrentRow(row)
        self._sync_roof_editor_preview_interaction_state()
        self._set_roof_editor_place_mode(False)
        try:
            self.statusBar().showMessage(
                "Gaube grafisch verschoben." if moved_existing else "Gaube grafisch eingefügt.",
                2500,
            )
        except Exception:
            pass

    def _make_default_roof_editor_dormer(self) -> DormerCfgDTO:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        dormers = list(getattr(attic, "dormers", []) or []) if attic is not None else []
        idx = len(dormers) + 1
        side = self._roof_editor_active_dormer_sides()[-1]
        length_m = float(getattr(attic, "building_length_m", 10.0) or 10.0) if attic is not None else 10.0
        width_m = float(getattr(attic, "dormer_width_m", 1.80) or 1.80) if attic is not None else 1.80
        height_m = float(getattr(attic, "dormer_height_m", 1.20) or 1.20) if attic is not None else 1.20
        pitch = float(getattr(attic, "roof_pitch_deg", 35.0) or 35.0) if attic is not None else 35.0
        return DormerCfgDTO(
            id=f"gaube_{idx}",
            dormer_type="schleppgaube",
            roof_side=side,
            center_along_m=max(0.0, length_m / 2.0),
            width_m=width_m,
            depth_m=max(0.8, 0.75 * width_m),
            front_height_m=height_m,
            window_count=1,
            window_width_m=1.20,
            window_height_m=1.20,
            sill_height_m=0.90,
            roof_pitch_deg=pitch,
            min_edge_clearance_m=0.40,
        )

    def _sync_attic_legacy_dormer_fields(self) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        if attic is None:
            return
        dormers = list(getattr(attic, "dormers", []) or [])
        if dormers:
            first = dormers[0]
            attic.dormer_type = str(getattr(first, "dormer_type", "schleppgaube") or "schleppgaube")
            attic.dormer_width_m = float(getattr(first, "width_m", getattr(attic, "dormer_width_m", 1.80)) or 1.80)
            attic.dormer_height_m = float(getattr(first, "front_height_m", getattr(attic, "dormer_height_m", 1.20)) or 1.20)
            along = float(getattr(attic, "building_length_m", 10.0) or 10.0)
            center = float(getattr(first, "center_along_m", along / 2.0) or 0.0)
            attic.dormer_offset_ratio = 0.0 if along <= 1e-9 else max(-0.9, min(0.9, 2.0 * center / along - 1.0))
        else:
            attic.dormer_type = "none"

    def _add_roof_editor_dormer(self) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        if attic is None:
            return
        dlg = DormerEditDialog(self, self._make_default_roof_editor_dormer(), active_sides=self._roof_editor_active_dormer_sides())
        if dlg.exec() != QDialog.Accepted:
            return
        attic.dormers = list(getattr(attic, "dormers", []) or []) + [dlg.to_dto()]
        self._sync_attic_legacy_dormer_fields()
        self._persist_project_cfg_if_possible()
        self._recompute_and_redraw()
        self._refresh_attic_preview()
        self._refresh_roof_editor_dormer_actions()
        self._sync_roof_editor_tab_widgets()
        self._sync_roof_editor_preview_interaction_state()
        self._set_roof_editor_place_mode(False)

    def _edit_selected_roof_editor_dormer(self) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        lst = getattr(self, "lst_roof_tab_dormers", None)
        if attic is None or lst is None:
            return
        row = lst.currentRow()
        dormers = list(getattr(attic, "dormers", []) or [])
        if row < 0 or row >= len(dormers):
            return
        dlg = DormerEditDialog(self, dormers[row], active_sides=self._roof_editor_active_dormer_sides())
        if dlg.exec() != QDialog.Accepted:
            return
        dormers[row] = dlg.to_dto()
        attic.dormers = dormers
        self._sync_attic_legacy_dormer_fields()
        self._persist_project_cfg_if_possible()
        self._recompute_and_redraw()
        self._refresh_attic_preview()
        self._sync_roof_editor_tab_widgets()
        self.lst_roof_tab_dormers.setCurrentRow(row)
        self._set_roof_editor_place_mode(False)

    def _delete_selected_roof_editor_dormer(self) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        lst = getattr(self, "lst_roof_tab_dormers", None)
        if attic is None or lst is None:
            return
        row = lst.currentRow()
        dormers = list(getattr(attic, "dormers", []) or [])
        if row < 0 or row >= len(dormers):
            return
        del dormers[row]
        attic.dormers = dormers
        self._sync_attic_legacy_dormer_fields()
        self._persist_project_cfg_if_possible()
        self._recompute_and_redraw()
        self._refresh_attic_preview()
        self._sync_roof_editor_tab_widgets()
        if hasattr(self, "lst_roof_tab_dormers") and dormers:
            self.lst_roof_tab_dormers.setCurrentRow(min(row, len(dormers) - 1))
        self._set_roof_editor_place_mode(False)

    def _on_roof_editor_dormer_selected(self, _row: int) -> None:
        self._refresh_roof_editor_dormer_actions()
        self._sync_roof_editor_preview_interaction_state()


    def _on_roof_editor_profile_changed(self, label: str) -> None:
        mapping = {
            "Satteldach": "satteldach",
            "Pultdach": "pultdach",
            "Walmdach": "walmdach",
            "Krüppelwalmdach": "krueppelwalmdach",
            "Flachdach": "flachdach",
            "Winkel-/Kehldach": "winkeldach",
        }
        self._set_attic_roof_type(mapping.get(str(label), "satteldach"))
        self._sync_roof_editor_tab_widgets()
        self._refresh_roof_editor_dormer_actions()
        self._set_roof_editor_place_mode(False)

    def _on_roof_editor_ridge_changed(self, label: str) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        if attic is None:
            return
        attic.ridge_orientation = "width" if str(label) == "First quer" else "length"
        self._persist_project_cfg_if_possible()
        self._recompute_and_redraw()
        self._refresh_attic_preview()

    def _on_roof_editor_numeric_changed(self, *_args) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        if attic is None:
            return
        attic.roof_pitch_deg = float(getattr(self, "sp_roof_tab_pitch").value())
        attic.knee_wall_height_m = float(getattr(self, "sp_roof_tab_knee").value())
        overhang = float(getattr(self, "sp_roof_tab_overhang").value())
        attic.roof_overhang_m = overhang
        attic.eave_overhang_m = overhang
        attic.gable_overhang_m = overhang
        self._persist_project_cfg_if_possible()
        self._recompute_and_redraw()
        self._refresh_attic_preview()

    def _on_roof_editor_line_kind_changed(self, label: str) -> None:
        mapping = {"First": "first", "Grat": "grat", "Kehle": "kehle"}
        editor = getattr(self, "roof_line_editor_tab", None)
        if editor is not None:
            editor.set_current_kind(mapping.get(str(label), "first"))

    def _on_roof_editor_lines_changed(self) -> None:
        attic = getattr(getattr(self, "project_cfg", None), "attic", None)
        editor = getattr(self, "roof_line_editor_tab", None)
        if attic is None or editor is None:
            return
        attic.roof_lines = editor.current_lines()
        self._sync_roof_editor_line_list()
        self._persist_project_cfg_if_possible()
        self._recompute_and_redraw()
        self._refresh_attic_preview()

    def _on_roof_editor_line_selected(self, row: int) -> None:
        editor = getattr(self, "roof_line_editor_tab", None)
        if editor is None:
            return
        editor._selected_index = int(row)
        editor.update()

    def _delete_selected_roof_editor_line(self) -> None:
        editor = getattr(self, "roof_line_editor_tab", None)
        if editor is not None:
            editor.delete_selected_line()

    def _clear_roof_editor_lines(self) -> None:
        editor = getattr(self, "roof_line_editor_tab", None)
        if editor is not None:
            editor.clear_all()

    def _set_attic_roof_type(self, roof_type: str, *, persist: bool = True) -> None:
        roof_type = str(roof_type or "satteldach").strip().lower()
        allowed = {"satteldach", "pultdach", "walmdach", "krueppelwalmdach", "flachdach", "winkeldach"}
        if roof_type not in allowed:
            roof_type = "satteldach"

        attic = getattr(self.project_cfg, "attic", None)
        if attic is None:
            return

        attic.roof_type = roof_type
        self._sync_roof_profile_widgets()
        self._sync_roof_editor_tab_widgets()

        if persist:
            self._persist_project_cfg_if_possible()

        self._recompute_and_redraw()
        if hasattr(self, "_refresh_attic_preview"):
            self._refresh_attic_preview()
        try:
            self.statusBar().showMessage(f"Dachprofil gesetzt: {self._roof_display_name(roof_type)}", 2500)
        except Exception:
            pass

    def _on_roof_profile_changed(self, label: str) -> None:
        mapping = {
            "Satteldach": "satteldach",
            "Pultdach": "pultdach",
            "Walmdach": "walmdach",
            "Krüppelwalmdach": "krueppelwalmdach",
            "Flachdach": "flachdach",
            "Winkel-/Kehldach": "winkeldach",
        }
        self._set_attic_roof_type(mapping.get(str(label), "satteldach"))

    def _sync_facade_material_widgets(self) -> None:
        material = self._current_facade_material()

        combo = getattr(self, "cb_facade_material_quick", None)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentText(self._facade_material_display_name(material))
            combo.blockSignals(False)

        actions = getattr(self, "_facade_material_actions", None) or {}
        for key, act in actions.items():
            try:
                act.blockSignals(True)
                act.setChecked(str(key).lower() == material)
                act.blockSignals(False)
            except Exception:
                pass

    def _sync_roof_material_widgets(self) -> None:
        material = self._current_roof_material()

        combo = getattr(self, "cb_roof_material_quick", None)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentText(self._roof_material_display_name(material))
            combo.blockSignals(False)

        actions = getattr(self, "_roof_material_actions", None) or {}
        for key, act in actions.items():
            try:
                act.blockSignals(True)
                act.setChecked(str(key).lower() == material)
                act.blockSignals(False)
            except Exception:
                pass

    def _set_facade_material(self, material: str, *, persist: bool = True) -> None:
        material = str(material or "klinker").strip().lower()
        allowed = {"klinker", "putz", "holz", "beton"}
        if material not in allowed:
            material = "klinker"

        attic = getattr(self.project_cfg, "attic", None)
        if attic is None:
            return

        attic.facade_material = material
        self._sync_facade_material_widgets()

        if self._project_rooms_path and persist:
            try:
                cfg_path = self._project_json_path_for_rooms(self._project_rooms_path)
                save_project_cfg(cfg_path, self.project_cfg)
            except Exception:
                pass

        self._recompute_and_redraw()
        if hasattr(self, "_refresh_attic_preview"):
            self._refresh_attic_preview()
        try:
            self.statusBar().showMessage(f"3D-Fassadenmaterial gesetzt: {self._facade_material_display_name(material)}", 2500)
        except Exception:
            pass

    def _on_facade_material_changed(self, label: str) -> None:
        mapping = {"Klinker": "klinker", "Putz": "putz", "Holz": "holz", "Beton": "beton"}
        self._set_facade_material(mapping.get(str(label), "klinker"))

    def _on_project_settings(self):
        """Öffnet den Projekteinstellungen-Dialog."""
        self._open_project_settings_dialog()

    def _on_project_settings_norm(self):
        """Öffnet die Projektparameter direkt auf der Normprüfung."""
        self._open_project_settings_dialog("Normprüfung")

    def _on_project_settings_u_values(self):
        """Öffnet die Projektparameter direkt auf den U-Werten."""
        self._open_project_settings_dialog("Auto-Decken")

    def _on_project_settings_ventilation(self):
        """Öffnet die Projektparameter direkt auf der Lüftung."""
        self._open_project_settings_dialog("Lüftung")

    def _on_project_settings_ground(self):
        """Öffnet die Projektparameter direkt auf dem Erdreichansatz."""
        self._open_project_settings_dialog("Erdreich")

    def _on_attic_project_settings(self):
        """Öffnet die Projektparameter direkt auf dem Tab DG Dach."""
        self._open_project_settings_dialog("DG Dach")

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

    def _set_roof_material(self, material: str, *, persist: bool = True) -> None:
        material = str(material or "ziegel").strip().lower()
        allowed = {"ziegel"}
        if material not in allowed:
            material = "ziegel"

        attic = getattr(self.project_cfg, "attic", None)
        if attic is None:
            return

        attic.roof_material = material
        self._sync_roof_material_widgets()

        if self._project_rooms_path and persist:
            try:
                cfg_path = self._project_json_path_for_rooms(self._project_rooms_path)
                save_project_cfg(cfg_path, self.project_cfg)
            except Exception:
                pass

        self._recompute_and_redraw()
        if hasattr(self, "_refresh_attic_preview"):
            self._refresh_attic_preview()
        try:
            self.statusBar().showMessage(f"Dachmaterial gesetzt: {self._roof_material_display_name(material)}", 2500)
        except Exception:
            pass

    def _on_roof_material_changed(self, label: str) -> None:
        mapping = {"Ziegel": "ziegel"}
        self._set_roof_material(mapping.get(str(label), "ziegel"))


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
