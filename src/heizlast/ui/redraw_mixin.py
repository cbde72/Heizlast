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

from typing import Any, Dict, Optional
from ..domain.models import RoomModel

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QPen

from ..core.config import VentilationCfg
from ..core.heatload import calc_heatloads, ensure_auto_decks
from ..domain.models import ElementModel, RoomModel
from ..presentation.plan_presenter import PlanPresenter

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

    def _on_element_geometry_changed(self, element: ElementModel):
        """Wird aufgerufen, wenn sich die Geometrie eines Elements ändert."""
        self._recompute_and_redraw()

    # ---------------- Neuberechnung und Zeichnung ----------------

    def _recompute_and_redraw(self):
        """Berechnet die Heizlast neu und aktualisiert die Anzeige."""
        vent_cfg = getattr(self, "vent_cfg", None) or VentilationCfg()
        cfg = self.project_cfg
        area_mode = cfg.floor_area_mode

        snap = self._snapshot_auto_deck_overrides()
        try:
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
        results = calc_heatloads(
            list(self.rooms.values()), self.elements, t_out_c=float(cfg.t_out_c),
            vent_cfg=vent_cfg,
            thickness_mode=cfg.thickness_mode,
            area_shrink_factor=float(cfg.area_shrink_factor),
            floor_area_mode=area_mode
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
        self._apply_room_debug_overlay(results)
        self._update_statusbar_summary()

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

        for e in self.elements:
            if not e.has_geometry():
                continue
            uid = e.uid or str(uuid.uuid4())
            e.uid = uid
            self.metrics.ensure_metrics(e)
            if e.element_type == "Fenster":
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
                on_geometry_changed=self._on_room_geometry_changed,
            )
            sc.addItem(it)
            self.room_items[r.id] = it

        # EG-Grundriss im DG als Overlay
        self._rebuild_eg_shadow_in_dg()

    def _rebuild_all_graphics(self):
        """Baut alle Grafiken neu."""
        self._rebuild_rooms_graphics()
        self._rebuild_elements_graphics()
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