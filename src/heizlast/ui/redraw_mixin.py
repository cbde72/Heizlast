import uuid
from .graphics import RoomPolygonItem
from .graphics import WindowLineItem
from .graphics import ElementLineItem
from .graphics import PX_PER_M
from PySide6.QtWidgets import QGraphicsItem
try:
    import shiboken6
except Exception:
    class _ShibokenFallback:
        @staticmethod
        def isValid(obj):
            return obj is not None
    shiboken6 = _ShibokenFallback()

from ..domain.models import RoomModel

from PySide6.QtCore import Qt
from PySide6.QtGui import QPen

from ..core.config import VentilationCfg
from ..core.din_status import din_status_summary
from ..core.ground_model import GroundModelCfg
from ..core.heatload import calc_heatloads, ensure_auto_decks
from ..core.heatload_types import ThermalBridgeCfg, is_opening_type
from ..core.attic_auto import rebuild_auto_attic_elements
from ..domain.models import ElementModel

class MainWindowRedrawMixin:
    def _on_room_geometry_changed(self, room: RoomModel):
        """Wird aufgerufen, wenn sich die Geometrie eines Raums ändert."""
         # Zentrale Normalisierung stellt sicher: w/h nie 0, immer gesetzt
        self._normalize_room_geometry(room)

        # Nach Geometrieänderung: Auto-Wände sofort neu (Raum hat wieder 4 Kanten)
        if self.autowalls_enabled:
            self._rebuild_autowalls_all()

        self._recompute_and_redraw()

        if self._selected_room_id == room.id:
            self._populate_room_form()
            self._update_room_3d_dialog_selection()

    def _on_element_geometry_changed(self, element: ElementModel):
        """Wird aufgerufen, wenn sich die Geometrie eines Elements ändert."""
        self._recompute_and_redraw()
        self._update_room_3d_dialog_selection()

    # ---------------- Neuberechnung und Zeichnung ----------------

    def _recompute_and_redraw(self, *, sync_auto_elements: bool = True, mark_dirty: bool = True, update_din_status: bool = True):
        """Berechnet die Heizlast neu und aktualisiert die Anzeige."""
        vent_cfg = getattr(self, "vent_cfg", None) or VentilationCfg()
        cfg = self.project_cfg
        area_mode = cfg.floor_area_mode

        if sync_auto_elements:
            snap = self._snapshot_auto_deck_overrides()
            try:
                ensure_auto_decks(
                    self.rooms.values(),
                    self.elements,
                    u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
                    u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
                    u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
                    t_keller_c=float(cfg.t_keller_c),
                    t_oben_c=float(cfg.t_oben_c),
                    u_value_source=str(getattr(cfg, "u_value_source", "")),
                    boundary_source=str(getattr(cfg, "auto_deck_boundary_source", "")),
                    auto_deck_assumptions_confirmed=bool(getattr(cfg, "auto_deck_assumptions_confirmed", False)),
                    create_eg_kellerdecke=bool(getattr(cfg, "auto_deck_create_eg_kellerdecke", True)),
                    create_eg_geschossdecke=bool(getattr(cfg, "auto_deck_create_eg_geschossdecke", True)),
                    create_dg_speicherdecke=bool(getattr(cfg, "auto_deck_create_dg_speicherdecke", True)),
                )
            except Exception:
                pass
            self._restore_auto_deck_overrides(snap)

            prev_attic_sig = tuple(sorted(str(getattr(e, "uid", "") or "") for e in self.elements if str(getattr(e, "uid", "") or "").startswith("auto_attic_")))
            try:
                rebuild_auto_attic_elements(
                    rooms=list(self.rooms.values()),
                    elements=self.elements,
                    attic_cfg=cfg.attic,
                )
            except Exception:
                pass
            new_attic_sig = tuple(sorted(str(getattr(e, "uid", "") or "") for e in self.elements if str(getattr(e, "uid", "") or "").startswith("auto_attic_")))
            if new_attic_sig != prev_attic_sig:
                try:
                    self._rebuild_elements_graphics()
                except Exception:
                    pass
        results = calc_heatloads(
            list(self.rooms.values()), self.elements, t_out_c=float(cfg.t_out_c),
            vent_cfg=vent_cfg,
            thickness_mode=cfg.thickness_mode,
            area_shrink_factor=float(cfg.area_shrink_factor),
            floor_area_mode=area_mode,
            tb_cfg=ThermalBridgeCfg(**cfg.tb.__dict__),
            ground_cfg=GroundModelCfg(**cfg.ground.__dict__),
            u_aussenwand_w_m2k=float(getattr(cfg, "u_aussenwand_w_m2k", 0.45)),
            u_fenster_w_m2k=float(getattr(cfg, "u_fenster_w_m2k", 2.80)),
            u_tuer_w_m2k=float(getattr(cfg, "u_tuer_w_m2k", 1.80)),
            reheat_power_w_m2=(float(cfg.reheat_power_w_m2) if bool(getattr(cfg, "reheat_enabled", False)) else 0.0),
            reheat_duration_h=(float(cfg.reheat_duration_h) if bool(getattr(cfg, "reheat_enabled", False)) else 0.0),
            reheat_temp_drop_k=(float(cfg.reheat_temp_drop_k) if bool(getattr(cfg, "reheat_enabled", False)) else 0.0),
            reheat_capacity_wh_m2k=float(getattr(cfg, "reheat_capacity_wh_m2k", 20.0)),
            u_kellerdecke_w_m2k=float(cfg.u_kellerdecke_w_m2k),
            u_eg_geschossdecke_w_m2k=float(cfg.u_eg_geschossdecke_w_m2k),
            u_dg_geschossdecke_w_m2k=float(cfg.u_dg_geschossdecke_w_m2k),
            u_bodenplatte_w_m2k=float(getattr(cfg, "u_bodenplatte_w_m2k", 0.40)),
            u_erdberuehrte_wand_w_m2k=float(getattr(cfg, "u_erdberuehrte_wand_w_m2k", 0.60)),
            ventilation_mode=str(getattr(cfg, "ventilation_mode", "natural")),
            min_air_change_1ph=float(getattr(cfg, "min_air_change_1ph", 0.0)),
            infiltration_air_change_1ph=float(getattr(cfg, "infiltration_air_change_1ph", 0.0)),
            mech_supply_m3h=float(getattr(cfg, "mech_supply_m3h", 0.0)),
            mech_exhaust_m3h=float(getattr(cfg, "mech_exhaust_m3h", 0.0)),
            heat_recovery_efficiency=float(getattr(cfg, "heat_recovery_efficiency", 0.0)),
            sync_auto_decks=False,
        )

        for rid, it in self.room_items.items():
            if not self._is_valid_graphics_item(it):
                continue
            res = results.get(rid)
            if res:
                it.set_heat(res["Q_sum_W"], res["Q_W_per_m2"])
                it.set_area(res.get("A_ref_m2", res["A_in_m2"]))
            it.update()

        self._last_heatload_results = results
        if update_din_status:
            self._update_din_status_from_results(results=results, vent_cfg=vent_cfg)
        else:
            self._last_din_status = ("△", "DIN-Ampel wird nach dem Laden aktualisiert.")
        self._apply_room_debug_overlay(results)
        self._update_statusbar_summary()
        if mark_dirty and hasattr(self, "_mark_dirty"):
            try:
                self._mark_dirty("recompute", refresh_ui=False)
            except TypeError:
                self._mark_dirty("recompute")

    def _update_din_status_from_results(self, *, results: dict | None = None, vent_cfg: VentilationCfg | None = None) -> None:
        """Aktualisiert nur die DIN-Ampel; kann nach dem schnellen Laden verzögert laufen."""
        results = results if results is not None else getattr(self, "_last_heatload_results", None)
        if not isinstance(results, dict):
            return
        vent_cfg = vent_cfg or getattr(self, "vent_cfg", None) or VentilationCfg()
        try:
            self._last_din_status = din_status_summary(
                results=results,
                project_cfg=self.project_cfg,
                vent_cfg=vent_cfg,
                elements=self.elements,
                rooms=list(self.rooms.values()),
            )
        except Exception:
            self._last_din_status = ("✗", "DIN-Ampel: Rot – Status konnte nicht berechnet werden.")

    def _clear_elements_graphics(self):
        """Entfernt alle Element-Grafiken sicher."""
        items = list(self.element_items.items())
        self.element_items.clear()

        for uid, it in items:
            self._safe_remove_from_scene(it)
    #

    def _rebuild_elements_graphics(self):
        """Baut alle Element-Grafiken neu."""
        self._clear_elements_graphics()
        try:
            self.metrics.invalidate_cache()
        except Exception:
            pass

        for e in self.elements:
            if not e.has_geometry():
                continue
            uid = e.uid or str(uuid.uuid4())
            e.uid = uid
            self.metrics.ensure_metrics(e)
            if is_opening_type(e.element_type):
                orient = "H"
                c = 0.0
                a0 = 0.0
                a1 = 1000.0
                m = e.meta or ""
                try:
                    parts = {kv.split("=", 1)[0]: kv.split("=", 1)[1] for kv in m.split("|") if "=" in kv}
                    orient = parts.get("orient", orient)
                    c = float(parts.get("c", c))
                    a0 = float(parts.get("a0", a0))
                    a1 = float(parts.get("a1", a1))
                except Exception:
                    pass
                item = WindowLineItem(
                    e,
                    orient=orient,
                    c_m=c,
                    a0_m=a0,
                    a1_m=a1,
                    on_geometry_changed=self._on_element_geometry_changed,
                )
            else:
                item = ElementLineItem(
                    e,
                    on_select=None,
                    on_propose_move=self._propose_element_move,
                )
                try:
                    item.set_auto_attic_visual_enabled(bool(getattr(self, "show_auto_attic_markers", False)))
                except Exception:
                    pass

            floor = e.floor
            if floor is None:
                r = self.rooms.get(e.room_id)
                floor = r.floor if r else "EG"

            sc = self.scene_KG if floor == "KG" else (self.scene_EG if floor == "EG" else self.scene_DG)
            if self._is_valid_graphics_item(sc):
                sc.addItem(item)

            if hasattr(item, "label") and getattr(item, "label") is not None:
                try:
                    item.label.setVisible(False)
                except Exception:
                    pass
            if hasattr(item, "leader") and getattr(item, "leader") is not None:
                try:
                    item.leader.setVisible(False)
                except Exception:
                    pass

            self.element_items[uid] = item

        if self._selected_room_id:
            self._populate_room_elements_list()
            self._update_room_3d_dialog_selection()

    def _rebuild_eg_shadow_in_dg(self) -> None:
        """Zeichnet EG-Grundriss im DG als graue gestrichelte Kontur."""
        # Alte Shadow-Items entfernen
        for it in list(getattr(self, "eg_shadow_items", {}).values()):
            try:
                if it is not None and it.scene() is not None:
                    it.scene().removeItem(it)
            except Exception:
                pass
        self.eg_shadow_items = {}

        sc = getattr(self, "scene_DG", None)
        if not self._is_valid_graphics_item(sc):
            return

        pen = QPen(Qt.gray)
        pen.setStyle(Qt.DashLine)
        pen.setWidthF(1.0)

        for r in self.rooms.values():
            if getattr(r, "floor", None) != "EG":
                continue
            try:
                r.ensure_polygon()
                pts = getattr(r, "polygon_points", lambda: [])()
            except Exception:
                pts = []
            if len(pts) >= 3:
                from PySide6.QtGui import QPainterPath
                path = QPainterPath()
                first = True
                for x_m, y_m in pts:
                    px = float(x_m) * PX_PER_M
                    py = float(y_m) * PX_PER_M
                    if first:
                        path.moveTo(px, py); first = False
                    else:
                        path.lineTo(px, py)
                path.closeSubpath()
                it = sc.addPath(path, pen, Qt.NoBrush)
            else:
                continue
            it.setZValue(-10_000)
            it.setAcceptedMouseButtons(Qt.NoButton)
            it.setFlag(QGraphicsItem.ItemIsSelectable, False)
            it.setFlag(QGraphicsItem.ItemIsMovable, False)
            self.eg_shadow_items[r.id] = it

    def _rebuild_rooms_graphics(self):
        """Baut alle Raum-Grafiken neu."""
        try:
            self._clear_elements_graphics()
        except Exception:
            pass

        self.room_items.clear()

        self.scene_KG.clear()
        self.scene_EG.clear()
        self.scene_DG.clear()

        for r in self.rooms.values():
            sc = self.scene_KG if r.floor == "KG" else (self.scene_EG if r.floor == "EG" else self.scene_DG)
            if not self._is_valid_graphics_item(sc):
                continue
            try:
                r.ensure_polygon()
            except Exception:
                pass
            it = RoomPolygonItem(
                r,
                heatmap_enabled_cb=lambda: self.heatmap_enabled,
                on_geometry_changed=None,
            )
            it.on_geometry_changed = self._on_room_geometry_changed
            sc.addItem(it)
            self.room_items[r.id] = it

        # EG-Grundriss im DG als Overlay
        self._rebuild_eg_shadow_in_dg()

    def _rebuild_all_graphics(self, *, recompute: bool = True):
        """Baut alle Grafiken neu."""
        self._rebuild_rooms_graphics()
        self._rebuild_elements_graphics()
        if recompute:
            self._recompute_and_redraw()

    # ---------------- Element-Bewegungsvorschlag (Snapping) ----------------

    def _is_valid_graphics_item(self, item) -> bool:
        """Prüft, ob ein QGraphicsItem noch gültig ist."""
        try:
            return item is not None and shiboken6.isValid(item)
        except Exception:
            return False

    def _safe_remove_from_scene(self, item):
        """Entfernt ein Item sicher aus der Szene."""
        try:
            if not self._is_valid_graphics_item(item):
                return
            scene = item.scene()
            if scene is not None and self._is_valid_graphics_item(scene):
                scene.removeItem(item)
        except RuntimeError:
            pass
