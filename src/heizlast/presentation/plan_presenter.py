from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional
from ..domain.models import ElementModel

try:
    import shiboken6
except Exception:
    class _ShibokenFallback:
        @staticmethod
        def isValid(obj):
            return obj is not None
    shiboken6 = _ShibokenFallback()
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPen, QColor
from PySide6.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsItem

from ..domain.models import RoomModel
from ..core.element_metrics import ElementMetricsService
from ..ui.graphics import RoomPolygonItem, ElementLineItem, WindowLineItem, PX_PER_M


@dataclass
class PlanPresenter:
    """Presentation layer helper: renders domain state into QGraphicsScene items.

    Performance goals:
    - NO scene.clear() for incremental redraws (preserve element items, avoid re-index rebuild).
    - Reuse existing QGraphicsItems whenever uid/id is stable (caches labels/leader items).
    - Only create/remove delta items.
    """

    scene_EG: QGraphicsScene
    scene_DG: QGraphicsScene
    room_items: Dict[str, RoomPolygonItem]
    element_items: Dict[str, Any]
    metrics: ElementMetricsService

    # transient UI-only highlight rect
    _highlight_item: Optional[QGraphicsRectItem] = None

    # cached EG ghost overlay in DG (grey dashed)
    _ghost_eg_items: Dict[str, QGraphicsRectItem] = field(default_factory=dict)

    def _is_valid(self, item) -> bool:
        try:
            return item is not None and shiboken6.isValid(item)
        except Exception:
            return False

    def _safe_remove(self, item) -> None:
        try:
            if not self._is_valid(item):
                return
            sc = item.scene()
            if sc is not None and self._is_valid(sc):
                sc.removeItem(item)
        except RuntimeError:
            pass

    # ---------------- public API ----------------

    def clear_scenes(self) -> None:
        """Hard reset: remove everything from scenes."""
        for it in list(self.room_items.values()):
            self._safe_remove(it)
        for it in list(self.element_items.values()):
            self._safe_remove(it)
        for it in list(self._ghost_eg_items.values()):
            self._safe_remove(it)

        self.room_items.clear()
        self.element_items.clear()
        self._ghost_eg_items.clear()

        try:
            self.scene_EG.clear()
            self.scene_DG.clear()
        except Exception:
            pass

        self.clear_highlight()

    def rebuild_rooms(
        self,
        rooms: Dict[str, RoomModel],
        *,
        heatmap_enabled_cb: Callable[[], bool],
        on_geometry_changed: Optional[Callable[[RoomModel], None]] = None,
        show_eg_in_dg: bool = False,
    ) -> None:
        """Rebuild/update room items only (incremental; keeps elements)."""
        wanted_ids = set(rooms.keys())

        # remove deleted rooms
        for rid, it in list(self.room_items.items()):
            if rid not in wanted_ids or not self._is_valid(it):
                self._safe_remove(it)
                self.room_items.pop(rid, None)

        # add/update rooms
        for r in rooms.values():
            sc = self.scene_EG if r.floor == "EG" else self.scene_DG
            it = self.room_items.get(r.id)
            if it is None or not self._is_valid(it) or it.scene() is not sc:
                # remove stale item if any
                if it is not None:
                    self._safe_remove(it)
                it = RoomPolygonItem(r, heatmap_enabled_cb=heatmap_enabled_cb, on_geometry_changed=on_geometry_changed)
                sc.addItem(it)
                self.room_items[r.id] = it
            else:
                # update existing item in-place
                try:
                    it.model = r
                    it.heatmap_enabled_cb = heatmap_enabled_cb
                    it.on_geometry_changed = on_geometry_changed
                    try:
                        r.ensure_polygon()
                    except Exception:
                        pass
                    try:
                        it._rebuild_path_from_model()
                    except Exception:
                        pass
                    try:
                        it._refresh_edit_handles()
                    except Exception:
                        pass
                    it.update()
                except Exception:
                    pass

        # optional: show EG floorplan in DG (grey dashed)
        if show_eg_in_dg:
            self._update_eg_ghost_in_dg(rooms)
        else:
            self._clear_eg_ghost_in_dg()

    def rebuild_elements(
        self,
        rooms: Dict[str, RoomModel],
        elements: Iterable[ElementModel],
        *,
        on_propose_move,
        on_select=None,
    ) -> None:
        """Incremental rebuild/update of element items (caches labels)."""
        wanted: Dict[str, ElementModel] = {}

        for e in elements:
            if not getattr(e, "has_geometry", lambda: False)():
                continue
            uid = getattr(e, "uid", None) or str(uuid.uuid4())
            e.uid = uid
            wanted[uid] = e

        # remove deleted elements
        for uid, it in list(self.element_items.items()):
            if uid not in wanted or not self._is_valid(it):
                self._safe_remove(it)
                self.element_items.pop(uid, None)

        # add/update
        for uid, e in wanted.items():
            # keep metrics consistent for display (purely presentational)
            try:
                self.metrics.ensure_metrics(e)
            except Exception:
                pass

            floor = e.floor
            if floor is None:
                r = rooms.get(e.room_id)
                floor = r.floor if r else "EG"
            sc = self.scene_EG if floor == "EG" else self.scene_DG

            it = self.element_items.get(uid)
            want_window = (str(e.element_type or "").strip().lower() == "fenster")

            if it is not None and self._is_valid(it) and it.scene() is sc:
                # reuse if class matches
                if want_window and isinstance(it, WindowLineItem):
                    try:
                        it.element = e
                        # If meta changed (orient/constraints), easiest conservative strategy:
                        # keep existing constraints unless missing; they come from meta at creation time.
                        it._sync_from_model()
                    except Exception:
                        pass
                    continue
                if (not want_window) and isinstance(it, ElementLineItem):
                    try:
                        it.element = e
                        it.on_select = on_select
                        it.on_propose_move = on_propose_move
                        it._sync_from_model()
                    except Exception:
                        pass
                    continue

            # otherwise recreate (class mismatch or moved floor)
            if it is not None:
                self._safe_remove(it)

            if want_window:
                orient, c, a0, a1 = self._parse_window_meta(e)
                new_it = WindowLineItem(e, orient=orient, c_m=c, a0_m=a0, a1_m=a1, on_geometry_changed=None)
            else:
                new_it = ElementLineItem(e, on_select=on_select, on_propose_move=on_propose_move)

            sc.addItem(new_it)
            self.element_items[uid] = new_it

        # highlight rect must follow reused item; keep as-is unless explicitly called
        # (rebuilding does not auto-highlight)

    def apply_label_visibility(self, show_outer: bool, show_inner: bool, show_windows: bool) -> None:
        for it in self.element_items.values():
            if not self._is_valid(it):
                continue

            el = getattr(it, "element", None)
            if not isinstance(el, ElementModel):
                continue

            et = (el.element_type or "").strip().lower()
            show = True
            if et == "fenster":
                show = bool(show_windows)
            elif et in ("aussenwand", "außenwand"):
                show = bool(show_outer)
            elif et == "innenwand":
                show = bool(show_inner)

            for attr in ("label", "leader"):
                obj = getattr(it, attr, None)
                if obj is None or not self._is_valid(obj):
                    continue
                try:
                    obj.setVisible(show)
                except Exception:
                    pass

    def update_room_heat(self, results: Dict, show_debug: bool, apply_debug_overlay_cb) -> None:
        for rid, it in self.room_items.items():
            if not self._is_valid(it):
                continue
            res = results.get(rid)
            if res:
                try:
                    it.set_heat(res["Q_sum_W"], res["Q_W_per_m2"])
                    it.set_area(res.get("A_ref_m2", res.get("A_in_m2", 0.0)))
                except Exception:
                    pass
            try:
                it.update()
            except Exception:
                pass

        apply_debug_overlay_cb(results if show_debug else results)

    def highlight_uid(self, uid: str) -> None:
        self.clear_highlight()
        it = self.element_items.get(uid)
        if it is None or not self._is_valid(it):
            return
        sc = it.scene()
        if sc is None or not self._is_valid(sc):
            return
        br = it.sceneBoundingRect()
        r = QGraphicsRectItem(br)
        pen = QPen(Qt.yellow)
        pen.setWidth(3)
        r.setPen(pen)
        r.setBrush(Qt.transparent)
        r.setZValue(999999)
        sc.addItem(r)
        self._highlight_item = r

    def clear_highlight(self) -> None:
        if self._highlight_item is not None:
            self._safe_remove(self._highlight_item)
        self._highlight_item = None

    # ---------------- internals ----------------

    def _parse_window_meta(self, e: ElementModel):
        orient = "H"
        c = 0.0
        a0 = 0.0
        a1 = 1000.0
        m = getattr(e, "meta", "") or ""
        try:
            parts = {kv.split("=", 1)[0]: kv.split("=", 1)[1] for kv in m.split("|") if "=" in kv}
            orient = parts.get("orient", orient)
            c = float(parts.get("c", c))
            a0 = float(parts.get("a0", a0))
            a1 = float(parts.get("a1", a1))
        except Exception:
            pass
        return orient, c, a0, a1

    def _clear_eg_ghost_in_dg(self) -> None:
        for rid, it in list(self._ghost_eg_items.items()):
            self._safe_remove(it)
        self._ghost_eg_items.clear()

    def _update_eg_ghost_in_dg(self, rooms: Dict[str, RoomModel]) -> None:
        eg_ids = {r.id for r in rooms.values() if getattr(r, "floor", "EG") == "EG"}

        # remove ghosts no longer needed
        for rid, it in list(self._ghost_eg_items.items()):
            if rid not in eg_ids or not self._is_valid(it):
                self._safe_remove(it)
                self._ghost_eg_items.pop(rid, None)

        # add/update ghosts
        pen = QPen(QColor(150, 150, 150))
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)

        for r in rooms.values():
            if getattr(r, "floor", "EG") != "EG":
                continue
            it = self._ghost_eg_items.get(r.id)
            if it is None or not self._is_valid(it) or it.scene() is not self.scene_DG:
                if it is not None:
                    self._safe_remove(it)
                it = QGraphicsRectItem()
                it.setZValue(0)  # behind real DG rooms
                it.setFlag(QGraphicsItem.ItemIsSelectable, False)
                it.setFlag(QGraphicsItem.ItemIsMovable, False)
                it.setAcceptedMouseButtons(Qt.NoButton)
                it.setPen(pen)
                it.setBrush(Qt.transparent)
                self.scene_DG.addItem(it)
                self._ghost_eg_items[r.id] = it

            try:
                it.setPos(float(r.x_m) * PX_PER_M, float(r.y_m) * PX_PER_M)
                it.setRect(QRectF(0, 0, float(r.w_m) * PX_PER_M, float(r.h_m) * PX_PER_M))
            except Exception:
                pass