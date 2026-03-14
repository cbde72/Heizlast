from __future__ import annotations
import math
from typing import Callable, List, Optional, Tuple
from ..domain.models import ElementModel

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPen, QBrush, QPainter, QColor, QPainterPath
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsRectItem, QGraphicsLineItem, QGraphicsSimpleTextItem, QGraphicsPathItem
)

from ..core.config import PX_PER_M, GRID_M, HANDLE_SZ_PX, ELEMENT_STYLES, HEATMAP_CAP_W_PER_M2
from ..domain.models import RoomModel, ElementModel
from ..core.geometry import polygon_bbox, translate_polygon

# Room interaction tuning
RESIZE_MARGIN_PX = 10.0  # px: grab zone at room edges
ROOM_SNAP_PX = 10.0      # px: snap tolerance to other room edges
ROOM_TOUCH_EPS = 0.0     # px: >0 would require a gap; 0 => touching is allowed


# --------------------------------------------------------------------------------------
# helpers (kept)
# --------------------------------------------------------------------------------------

def snap_m(x: float, step: float = 0.05) -> float:
    return round(x / step) * step


def heat_rgba(wpm2: float, cap: float = HEATMAP_CAP_W_PER_M2):
    x = max(0.0, min(wpm2, cap)) / cap
    if x <= 0.5:
        t = x / 0.5
        r = 0.0 + t * 1.0
        g = 0.3 + t * 0.7
        b = 1.0 - t * 1.0
    else:
        t = (x - 0.5) / 0.5
        r = 1.0
        g = 1.0 - t * 1.0
        b = 0.0
    return (r, g, b, 0.35)


def angle_upright_degrees(p0: QPointF, p1: QPointF) -> float:
    dx = p1.x() - p0.x()
    dy = p1.y() - p0.y()
    ang = math.degrees(math.atan2(dy, dx))
    if ang > 90:
        ang -= 180
    if ang < -90:
        ang += 180
    return ang

def _point_eq(a: tuple[float, float], b: tuple[float, float], eps: float = 1e-9) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _simplify_orthogonal_polygon(points: list[tuple[float, float]], eps: float = 1e-9) -> list[tuple[float, float]]:
    pts = list(points or [])
    if len(pts) >= 2 and _point_eq(pts[0], pts[-1], eps):
        pts = pts[:-1]
    changed = True
    while changed and len(pts) >= 3:
        changed = False
        out: list[tuple[float, float]] = []
        n = len(pts)
        for i in range(n):
            p_prev = pts[(i - 1) % n]
            p_cur = pts[i]
            p_next = pts[(i + 1) % n]
            if _point_eq(p_prev, p_cur, eps) or _point_eq(p_cur, p_next, eps):
                changed = True
                continue
            collinear_v = abs(p_prev[0] - p_cur[0]) <= eps and abs(p_cur[0] - p_next[0]) <= eps
            collinear_h = abs(p_prev[1] - p_cur[1]) <= eps and abs(p_cur[1] - p_next[1]) <= eps
            if collinear_v or collinear_h:
                changed = True
                continue
            out.append(p_cur)
        pts = out
    return pts


def _polygon_is_axis_aligned(points: list[tuple[float, float]], eps: float = 1e-9) -> bool:
    if len(points) < 3:
        return False
    n = len(points)
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        if abs(x0 - x1) > eps and abs(y0 - y1) > eps:
            return False
    return True


def _segments_intersect(a1, a2, b1, b2, eps: float = 1e-9) -> bool:
    def orient(p, q, r):
        val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        if abs(val) <= eps:
            return 0
        return 1 if val > 0 else 2

    def on_seg(p, q, r):
        return (min(p[0], r[0]) - eps <= q[0] <= max(p[0], r[0]) + eps and
                min(p[1], r[1]) - eps <= q[1] <= max(p[1], r[1]) + eps)

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_seg(a1, b1, a2):
        return True
    if o2 == 0 and on_seg(a1, b2, a2):
        return True
    if o3 == 0 and on_seg(b1, a1, b2):
        return True
    if o4 == 0 and on_seg(b1, a2, b2):
        return True
    return False


def _polygon_self_intersects(points: list[tuple[float, float]], eps: float = 1e-9) -> bool:
    n = len(points)
    if n < 4:
        return False
    for i in range(n):
        a1 = points[i]
        a2 = points[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            if i == 0 and j == n - 1:
                continue
            b1 = points[j]
            b2 = points[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2, eps):
                return True
    return False


def _is_valid_edit_polygon(points: list[tuple[float, float]]) -> bool:
    pts = _simplify_orthogonal_polygon(points)
    if len(pts) < 4:
        return False
    if not _polygon_is_axis_aligned(pts):
        return False
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    if abs(area) <= 1e-6:
        return False
    if _polygon_self_intersects(pts):
        return False
    return True




# --------------------------------------------------------------------------------------
# Plan view (kept)
# --------------------------------------------------------------------------------------

class PlanView(QGraphicsView):
    """V06-style view: antialiasing + background grid."""
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # Zoom-Setup
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

        self._zoom_level = 0
        self._zoom_step = 1.15
        self._zoom_min = -12
        self._zoom_max = 24

    def reset_zoom(self):
        self.resetTransform()
        self._zoom_level = 0

    def zoom_in(self):
        if self._zoom_level >= self._zoom_max:
            return
        self._zoom_level += 1
        self.scale(self._zoom_step, self._zoom_step)

    def zoom_out(self):
        if self._zoom_level <= self._zoom_min:
            return
        self._zoom_level -= 1
        self.scale(1.0 / self._zoom_step, 1.0 / self._zoom_step)

    def fit_all(self):
        # passt die komplette Scene ins Fenster
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
        self._zoom_level = 0

    def drawBackground(self, painter, rect):
        painter.setPen(QPen(Qt.lightGray, 1))
        step = GRID_M * PX_PER_M
        if step <= 0:
            return
        left = int(rect.left()) - (int(rect.left()) % int(step))
        top = int(rect.top()) - (int(rect.top()) % int(step))

        x = left
        while x < rect.right():
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += int(step)

        y = top
        while y < rect.bottom():
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += int(step)

    def wheelEvent(self, event):
        # Nur Ctrl+Wheel = Zoom
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                return

            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()

            event.accept()
            return

        # Ohne Ctrl: Standard-Scroll
        super().wheelEvent(event)


# --------------------------------------------------------------------------------------
# Room handles + room item (kept)
# --------------------------------------------------------------------------------------

class HandleItem(QGraphicsRectItem):
    """Resize handle (child of RoomRectItem). Delegates resize to parent."""
    def __init__(self, parent_room: "RoomRectItem", idx: int):
        super().__init__(-HANDLE_SZ_PX / 2, -HANDLE_SZ_PX / 2, HANDLE_SZ_PX, HANDLE_SZ_PX, parent_room)
        self.parent_room = parent_room
        self.idx = idx
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.black, 1))
        self.setZValue(10)
        self.setCacheMode(QGraphicsItem.NoCache)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.SizeAllCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            if not getattr(self.parent_room, "_in_resize", False):
                new_pos: QPointF = value
                self.parent_room.resize_from_handle(self.idx, new_pos)
            return self.pos()
        return super().itemChange(change, value)



class RoomResizeBandItem(QGraphicsPathItem):
    # Invisible edge band to capture resize drags above all other items.
    # This avoids accidentally dragging element items when the user intends to resize a room.
    def __init__(self, room_item: "RoomRectItem", margin_px: float = RESIZE_MARGIN_PX):
        super().__init__(room_item)  # child: moves with room
        self.room_item = room_item
        self.margin_px = float(margin_px)

        self.setBrush(Qt.NoBrush)
        self.setPen(Qt.NoPen)
        self.setZValue(1_000_000)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setAcceptHoverEvents(True)

        self._rebuild_path()

    def _rebuild_path(self) -> None:
        r = self.room_item.rect()
        m = self.margin_px
        outer = QPainterPath()
        outer.addRect(r.adjusted(-m, -m, +m, +m))
        inner = QPainterPath()
        inner.addRect(r.adjusted(+m, +m, -m, -m))
        self.setPath(outer.subtracted(inner))

    def update_geometry(self) -> None:
        self.prepareGeometryChange()
        self._rebuild_path()

    def hoverMoveEvent(self, event):
        zone = self.room_item._hit_resize_zone(event.pos())
        if zone in ("L", "R"):
            self.setCursor(Qt.SizeHorCursor)
        elif zone in ("T", "B"):
            self.setCursor(Qt.SizeVerCursor)
        elif zone in ("TL", "BR"):
            self.setCursor(Qt.SizeFDiagCursor)
        elif zone in ("TR", "BL"):
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self.room_item.mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.room_item.mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.room_item.mouseReleaseEvent(event)


class RoomRectItem(QGraphicsRectItem):
    """Room item: movable + edge-resize + heatmap fill, with no-overlap and edge-snap."""

    def __init__(
        self,
        model: RoomModel,
        heatmap_enabled_cb: Callable[[], bool],
        on_geometry_changed: Optional[Callable[[RoomModel], None]] = None,
    ):
        self.model = model
        self.heatmap_enabled_cb = heatmap_enabled_cb or (lambda: False)
        self.on_geometry_changed = on_geometry_changed

        self._in_itemchange = False
        self._in_resize = False
        self._moving_interactively = False

        self.get_other_rooms_cb: Optional[Callable[[], List["RoomRectItem"]]] = None

        super().__init__(0, 0, model.w_m * PX_PER_M, model.h_m * PX_PER_M)

        self.setPos(model.x_m * PX_PER_M, model.y_m * PX_PER_M)
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        self._resize_band = RoomResizeBandItem(self, margin_px=RESIZE_MARGIN_PX)

        self.pen_norm = QPen(Qt.black, 2)
        self.pen_sel = QPen(Qt.darkBlue, 3)
        self.setBrush(QBrush(Qt.transparent))
        self.setZValue(1)

        # Handles disabled (edge-drag resize instead). Keep attribute to avoid crashes.
        self.handles: List[HandleItem] = []

        self._heat_wpm2 = 0.0
        self._heat_w = 0.0
        self._area_in_m2 = 0.0

    def set_debug_overlay(self, text: str) -> None:
        self._debug_overlay_text = text
        self.update()

    def set_heat(self, w_total: float, w_per_m2: float):
        self._heat_w = w_total
        self._heat_wpm2 = w_per_m2
        self.update()

    def set_area(self, a_inner: float):
        self._area_in_m2 = a_inner
        self.update()

    def _place_handles(self):
        return

    def _rect_scene(self) -> QRectF:
        r = self.rect()
        p = self.pos()
        return QRectF(p.x(), p.y(), r.width(), r.height())

    def _rect_scene_for(self, pos_xy: QPointF, rect_local: QRectF) -> QRectF:
        return QRectF(pos_xy.x(), pos_xy.y(), rect_local.width(), rect_local.height())

    def _other_room_rects_scene(self) -> List[QRectF]:
        cb = getattr(self, "get_other_rooms_cb", None)
        if not cb:
            return []
        out: List[QRectF] = []
        try:
            others = cb() or []
        except Exception:
            others = []
        for it in others:
            try:
                out.append(it._rect_scene())
            except Exception:
                pass
        return out

    @staticmethod
    def _ranges_overlap(a0: float, a1: float, b0: float, b1: float) -> bool:
        return min(a1, b1) > max(a0, b0)  # strict => touch allowed

    def _snap_pos_to_room_edges(self, cand: QRectF) -> QPointF:
        snap = ROOM_SNAP_PX
        best = snap + 1e-6
        best_dx = 0.0
        best_dy = 0.0

        L, R, T, B = cand.left(), cand.right(), cand.top(), cand.bottom()

        for o in self._other_room_rects_scene():
            oL, oR, oT, oB = o.left(), o.right(), o.top(), o.bottom()

            for a in (oL, oR):
                d = abs(L - a)
                if d < best:
                    best = d
                    best_dx = a - L
                    best_dy = 0.0
                d = abs(R - a)
                if d < best:
                    best = d
                    best_dx = a - R
                    best_dy = 0.0

            for a in (oT, oB):
                d = abs(T - a)
                if d < best:
                    best = d
                    best_dx = 0.0
                    best_dy = a - T
                d = abs(B - a)
                if d < best:
                    best = d
                    best_dx = 0.0
                    best_dy = a - B

        if best <= snap:
            return QPointF(cand.x() + best_dx, cand.y() + best_dy)
        return QPointF(cand.x(), cand.y())

    def _clamp_move_no_overlap(self, p_target: QPointF) -> QPointF:
        cur = QPointF(self.pos())
        dx = p_target.x() - cur.x()
        dy = p_target.y() - cur.y()

        base = self._rect_scene()
        w = base.width()
        h = base.height()

        dx_allowed = dx
        if dx != 0.0:
            cand_y0 = base.top()
            cand_y1 = base.bottom()
            for o in self._other_room_rects_scene():
                if not self._ranges_overlap(cand_y0, cand_y1, o.top(), o.bottom()):
                    continue
                if dx > 0:
                    max_dx = o.left() - base.right()
                    if max_dx < dx_allowed:
                        dx_allowed = max_dx
                else:
                    min_dx = o.right() - base.left()
                    if min_dx > dx_allowed:
                        dx_allowed = min_dx

        base2 = QRectF(base.x() + dx_allowed, base.y(), w, h)

        dy_allowed = dy
        if dy != 0.0:
            cand_x0 = base2.left()
            cand_x1 = base2.right()
            for o in self._other_room_rects_scene():
                if not self._ranges_overlap(cand_x0, cand_x1, o.left(), o.right()):
                    continue
                if dy > 0:
                    max_dy = o.top() - base2.bottom()
                    if max_dy < dy_allowed:
                        dy_allowed = max_dy
                else:
                    min_dy = o.bottom() - base2.top()
                    if min_dy > dy_allowed:
                        dy_allowed = min_dy

        return QPointF(cur.x() + dx_allowed, cur.y() + dy_allowed)

    def _clamp_resize_no_overlap(self, pos_scene: QPointF, rect_local: QRectF, zone: str) -> Tuple[QPointF, QRectF]:
        cand = self._rect_scene_for(pos_scene, rect_local)
        L, R, T, B = cand.left(), cand.right(), cand.top(), cand.bottom()
        w, h = cand.width(), cand.height()

        if "R" in zone:
            limit = None
            for o in self._other_room_rects_scene():
                if not self._ranges_overlap(T, B, o.top(), o.bottom()):
                    continue
                if o.left() >= L:
                    if limit is None or o.left() < limit:
                        limit = o.left()
            if limit is not None:
                R = min(R, limit)
                w = max(0.2 * PX_PER_M, R - L)

        if "L" in zone:
            limit = None
            for o in self._other_room_rects_scene():
                if not self._ranges_overlap(T, B, o.top(), o.bottom()):
                    continue
                if o.right() <= R:
                    if limit is None or o.right() > limit:
                        limit = o.right()
            if limit is not None:
                L = max(L, limit)
                w = max(0.2 * PX_PER_M, R - L)

        if "B" in zone:
            limit = None
            for o in self._other_room_rects_scene():
                if not self._ranges_overlap(L, R, o.left(), o.right()):
                    continue
                if o.top() >= T:
                    if limit is None or o.top() < limit:
                        limit = o.top()
            if limit is not None:
                B = min(B, limit)
                h = max(0.2 * PX_PER_M, B - T)

        if "T" in zone:
            limit = None
            for o in self._other_room_rects_scene():
                if not self._ranges_overlap(L, R, o.left(), o.right()):
                    continue
                if o.bottom() <= B:
                    if limit is None or o.bottom() > limit:
                        limit = o.bottom()
            if limit is not None:
                T = max(T, limit)
                h = max(0.2 * PX_PER_M, B - T)

        return QPointF(L, T), QRectF(0.0, 0.0, w, h)

    def _sync_model_from_geometry(self):
        self.model.x_m = snap_m(self.pos().x() / PX_PER_M)
        self.model.y_m = snap_m(self.pos().y() / PX_PER_M)
        self.model.w_m = snap_m(self.rect().width() / PX_PER_M)
        self.model.h_m = snap_m(self.rect().height() / PX_PER_M)
        try:
            self.model.recompute_volume()
        except Exception:
            pass

    def _apply_snapped_geometry(self, x_m: float, y_m: float, w_m: float, h_m: float):
        self.prepareGeometryChange()
        self.setPos(x_m * PX_PER_M, y_m * PX_PER_M)
        self.setRect(QRectF(0, 0, w_m * PX_PER_M, h_m * PX_PER_M))
        if hasattr(self, "_resize_band") and self._resize_band is not None:
            self._resize_band.update_geometry()

    def _hit_resize_zone(self, p_local: QPointF) -> Optional[str]:
        r = self.rect()
        x, y = p_local.x(), p_local.y()
        m = RESIZE_MARGIN_PX

        left = x <= r.left() + m
        right = x >= r.right() - m
        top = y <= r.top() + m
        bottom = y >= r.bottom() - m

        if top and left:
            return "TL"
        if top and right:
            return "TR"
        if bottom and left:
            return "BL"
        if bottom and right:
            return "BR"
        if left:
            return "L"
        if right:
            return "R"
        if top:
            return "T"
        if bottom:
            return "B"
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._moving_interactively = True
            zone = self._hit_resize_zone(event.pos())
            if zone:
                self._drag_resize_zone = zone
                self._drag_start_scene = event.scenePos()
                self._drag_start_pos = QPointF(self.pos())
                self._drag_start_rect = QRectF(self.rect())

                self._drag_old_movable = bool(self.flags() & QGraphicsItem.ItemIsMovable)
                self.setFlag(QGraphicsItem.ItemIsMovable, False)

                self._in_resize = True
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        zone = getattr(self, "_drag_resize_zone", None)
        if zone:
            ds = event.scenePos() - self._drag_start_scene

            start_pos = self._drag_start_pos
            start_rect = self._drag_start_rect

            x = start_pos.x()
            y = start_pos.y()
            w = start_rect.width()
            h = start_rect.height()

            dx = ds.x()
            dy = ds.y()

            min_w = 0.2 * PX_PER_M
            min_h = 0.2 * PX_PER_M

            if "L" in zone:
                new_x = x + dx
                new_w = w - dx
                if new_w < min_w:
                    new_x = x + (w - min_w)
                    new_w = min_w
                x, w = new_x, new_w

            if "R" in zone:
                new_w = w + dx
                if new_w < min_w:
                    new_w = min_w
                w = new_w

            if "T" in zone:
                new_y = y + dy
                new_h = h - dy
                if new_h < min_h:
                    new_y = y + (h - min_h)
                    new_h = min_h
                y, h = new_y, new_h

            if "B" in zone:
                new_h = h + dy
                if new_h < min_h:
                    new_h = min_h
                h = new_h

            cand_pos = QPointF(x, y)
            cand_rect = QRectF(0.0, 0.0, w, h)
            #p2, r2 = self._clamp_resize_no_overlap(cand_pos, cand_rect, zone)
            #cand_scene = self._rect_scene_for(p2, r2)

            p2, r2 = cand_pos, cand_rect
            cand_scene = self._rect_scene_for(p2, r2)

            p3 = self._snap_pos_to_room_edges(cand_scene)

            x_m = snap_m(p3.x() / PX_PER_M)
            y_m = snap_m(p3.y() / PX_PER_M)
            w_m = snap_m(r2.width() / PX_PER_M)
            h_m = snap_m(r2.height() / PX_PER_M)

            self._apply_snapped_geometry(x_m, y_m, w_m, h_m)
            self._sync_model_from_geometry()
            if self.on_geometry_changed:
                self.on_geometry_changed(self.model)

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        commit = False
        if getattr(self, "_drag_resize_zone", None):
            self._drag_resize_zone = None
            self._in_resize = False
            try:
                self.setFlag(QGraphicsItem.ItemIsMovable, bool(getattr(self, "_drag_old_movable", True)))
            except Exception:
                pass
            commit = True
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            commit = True

        self._moving_interactively = False
        if commit:
            try:
                self._sync_model_from_geometry()
                if self.on_geometry_changed:
                    self.on_geometry_changed(self.model)
            except Exception:
                pass

    def itemChange(self, change, value):
        if getattr(self, "_in_itemchange", False):
            return super().itemChange(change, value)

        if change == QGraphicsItem.ItemPositionChange:
            p: QPointF = value

            x_m = snap_m(p.x() / PX_PER_M)
            y_m = snap_m(p.y() / PX_PER_M)
            p_snap = QPointF(x_m * PX_PER_M, y_m * PX_PER_M)

            cand = self._rect_scene_for(p_snap, self.rect())
            p_snap2 = self._snap_pos_to_room_edges(cand)
            return p_snap2
            #p_clamped = self._clamp_move_no_overlap(p_snap2)
            #return p_clamped
            #return QPointF(x_m * PX_PER_M, y_m * PX_PER_M)

        if change == QGraphicsItem.ItemPositionHasChanged:
            try:
                self._in_itemchange = True
                self._sync_model_from_geometry()
                if self.on_geometry_changed and not (self._moving_interactively or self._in_resize):
                    self.on_geometry_changed(self.model)
            finally:
                self._in_itemchange = False

        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(self.pen_sel if self.isSelected() else self.pen_norm)

        txt = getattr(self, "_debug_overlay_text", "")
        if txt:
            painter.save()
            font = painter.font()
            font.setPointSize(max(7, font.pointSize() - 1))
            painter.setFont(font)
            r = self.boundingRect().adjusted(4, 4, -4, -4)
            painter.drawText(r, Qt.AlignLeft | Qt.AlignTop, txt)
            painter.restore()

        if self.heatmap_enabled_cb():
            rr, gg, bb, aa = heat_rgba(self._heat_wpm2)
            painter.fillRect(self.rect(), QBrush(QColor.fromRgbF(rr, gg, bb, aa)))

        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect())

        painter.save()
        painter.setPen(Qt.black)
        area_m2 = self._area_in_m2
        txt = f"{self.model.name}\n{area_m2:.1f} m²\n{self._heat_w:.0f} W\n{self._heat_wpm2:.0f} W/m²"
        painter.drawText(self.rect().adjusted(6, 6, -6, -6), Qt.AlignLeft | Qt.AlignTop, txt)
        painter.restore()



class PolygonVertexHandleItem(QGraphicsRectItem):
    """Corner handle for polygon-room editing."""
    def __init__(self, parent_room: "RoomPolygonItem", idx: int):
        super().__init__(-HANDLE_SZ_PX / 2, -HANDLE_SZ_PX / 2, HANDLE_SZ_PX, HANDLE_SZ_PX, parent_room)
        self.parent_room = parent_room
        self.idx = idx
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.darkBlue, 1))
        self.setZValue(10)
        self.setCacheMode(QGraphicsItem.NoCache)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.SizeAllCursor)

    def mousePressEvent(self, event):
        try:
            self.parent_room.setSelected(True)
        except Exception:
            pass
        self.parent_room._vertex_drag_active = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene_pt = self.mapToScene(event.pos())
        self.parent_room.move_vertex_from_scene(self.idx, scene_pt, final=False)
        event.accept()

    def mouseReleaseEvent(self, event):
        scene_pt = self.mapToScene(event.pos())
        self.parent_room.move_vertex_from_scene(self.idx, scene_pt, final=True)
        self.parent_room._vertex_drag_active = False
        event.accept()


class PolygonEdgeHandleItem(QGraphicsRectItem):
    """Mid-edge handle for shifting an entire orthogonal wall segment."""
    def __init__(self, parent_room: "RoomPolygonItem", edge_idx: int):
        size = max(8.0, HANDLE_SZ_PX - 2)
        super().__init__(-size / 2, -size / 2, size, size, parent_room)
        self.parent_room = parent_room
        self.edge_idx = edge_idx
        self._orientation = 'h'
        self.setBrush(QBrush(QColor(230, 240, 255)))
        self.setPen(QPen(Qt.darkBlue, 1, Qt.DashLine))
        self.setZValue(9)
        self.setCacheMode(QGraphicsItem.NoCache)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self._update_cursor()

    def set_orientation(self, orientation: str) -> None:
        self._orientation = orientation if orientation in ('h', 'v') else 'h'
        self._update_cursor()

    def _update_cursor(self) -> None:
        self.setCursor(Qt.SizeVerCursor if self._orientation == 'h' else Qt.SizeHorCursor)

    def mousePressEvent(self, event):
        try:
            self.parent_room.setSelected(True)
        except Exception:
            pass
        self.parent_room._edge_drag_active = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene_pt = self.mapToScene(event.pos())
        self.parent_room.move_edge_from_scene(self.edge_idx, scene_pt, final=False)
        event.accept()

    def mouseReleaseEvent(self, event):
        scene_pt = self.mapToScene(event.pos())
        self.parent_room.move_edge_from_scene(self.edge_idx, scene_pt, final=True)
        self.parent_room._edge_drag_active = False
        event.accept()


class RoomPolygonItem(QGraphicsPathItem):
    """Movable orthogonal polygon room with editable corner handles."""
    def __init__(self, model: RoomModel, heatmap_enabled_cb: Callable[[], bool], on_geometry_changed: Optional[Callable[[RoomModel], None]] = None):
        super().__init__()
        self.model = model
        self.heatmap_enabled_cb = heatmap_enabled_cb or (lambda: False)
        self.on_geometry_changed = on_geometry_changed
        self.pen_norm = QPen(Qt.black, 2)
        self.pen_sel = QPen(Qt.darkBlue, 3)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)
        self._heat_wpm2 = 0.0
        self._heat_w = 0.0
        self._area_in_m2 = 0.0
        self._in_itemchange = False
        self._vertex_drag_active = False
        self._edge_drag_active = False
        self.vertex_handles: list[PolygonVertexHandleItem] = []
        self.edge_handles: list[PolygonEdgeHandleItem] = []
        self._rebuild_path_from_model()
        self._refresh_edit_handles()

    def _rebuild_path_from_model(self):
        pts = self.model.polygon_points()
        if len(pts) < 3:
            x, y, w, h = self.model.x_m, self.model.y_m, self.model.w_m, self.model.h_m
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        min_x, min_y, max_x, max_y = polygon_bbox(pts)
        path = QPainterPath()
        first = True
        for x, y in pts:
            px = (x - min_x) * PX_PER_M
            py = (y - min_y) * PX_PER_M
            if first:
                path.moveTo(px, py)
                first = False
            else:
                path.lineTo(px, py)
        path.closeSubpath()
        self.setPath(path)
        self.setPos(min_x * PX_PER_M, min_y * PX_PER_M)
        self._refresh_edit_handles()

    def _refresh_edit_handles(self) -> None:
        pts = self.model.polygon_points()
        if len(pts) < 3:
            pts = [(self.model.x_m, self.model.y_m), (self.model.x_m + self.model.w_m, self.model.y_m), (self.model.x_m + self.model.w_m, self.model.y_m + self.model.h_m), (self.model.x_m, self.model.y_m + self.model.h_m)]
        min_x, min_y, _, _ = polygon_bbox(pts)
        while len(self.vertex_handles) < len(pts):
            self.vertex_handles.append(PolygonVertexHandleItem(self, len(self.vertex_handles)))
        while len(self.vertex_handles) > len(pts):
            h = self.vertex_handles.pop()
            try:
                if h.scene() is not None:
                    h.scene().removeItem(h)
            except Exception:
                pass
            try:
                h.setParentItem(None)
            except Exception:
                pass
        while len(self.edge_handles) < len(pts):
            self.edge_handles.append(PolygonEdgeHandleItem(self, len(self.edge_handles)))
        while len(self.edge_handles) > len(pts):
            h = self.edge_handles.pop()
            try:
                if h.scene() is not None:
                    h.scene().removeItem(h)
            except Exception:
                pass
            try:
                h.setParentItem(None)
            except Exception:
                pass
        selected = self.isSelected()
        n = len(pts)
        for i, (x, y) in enumerate(pts):
            h = self.vertex_handles[i]
            h.idx = i
            h.setPos((x - min_x) * PX_PER_M, (y - min_y) * PX_PER_M)
            h.setVisible(selected)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            eh = self.edge_handles[i]
            eh.edge_idx = i
            eh.setPos(((x0 + x1) * 0.5 - min_x) * PX_PER_M, ((y0 + y1) * 0.5 - min_y) * PX_PER_M)
            eh.set_orientation('h' if abs(y0 - y1) <= 1e-9 else 'v')
            eh.setVisible(selected)

    def _edited_points_for_vertex(self, idx: int, new_x_m: float, new_y_m: float) -> list[tuple[float, float]]:
        pts = list(self.model.polygon_points())
        n = len(pts)
        if n < 3 or idx < 0 or idx >= n:
            return pts
        prev_idx = (idx - 1) % n
        next_idx = (idx + 1) % n
        px, py = pts[prev_idx]
        cx, cy = pts[idx]
        nx, ny = pts[next_idx]
        prev_horizontal = abs(py - cy) <= 1e-9
        next_horizontal = abs(ny - cy) <= 1e-9
        pts[idx] = (new_x_m, new_y_m)
        pts[prev_idx] = (px, new_y_m) if prev_horizontal else (new_x_m, py)
        pts[next_idx] = (nx, new_y_m) if next_horizontal else (new_x_m, ny)
        return pts

    def move_vertex_from_scene(self, idx: int, scene_pt: QPointF, final: bool = False) -> None:
        new_x_m = snap_m(scene_pt.x() / PX_PER_M)
        new_y_m = snap_m(scene_pt.y() / PX_PER_M)
        candidate = self._edited_points_for_vertex(idx, new_x_m, new_y_m)
        if not _is_valid_edit_polygon(candidate):
            return
        if final:
            candidate = _simplify_orthogonal_polygon(candidate)
            if not _is_valid_edit_polygon(candidate):
                return
        self.model.set_polygon_points(candidate)
        self._rebuild_path_from_model()
        self.update()
        if final and self.on_geometry_changed:
            self.on_geometry_changed(self.model)

    def _edited_points_for_edge(self, idx: int, scene_pt: QPointF) -> list[tuple[float, float]]:
        pts = list(self.model.polygon_points())
        n = len(pts)
        if n < 3 or idx < 0 or idx >= n:
            return pts
        next_idx = (idx + 1) % n
        x0, y0 = pts[idx]
        x1, y1 = pts[next_idx]
        if abs(y0 - y1) <= 1e-9:
            new_y = snap_m(scene_pt.y() / PX_PER_M)
            pts[idx] = (x0, new_y)
            pts[next_idx] = (x1, new_y)
        else:
            new_x = snap_m(scene_pt.x() / PX_PER_M)
            pts[idx] = (new_x, y0)
            pts[next_idx] = (new_x, y1)
        return pts

    def move_edge_from_scene(self, idx: int, scene_pt: QPointF, final: bool = False) -> None:
        candidate = self._edited_points_for_edge(idx, scene_pt)
        if not _is_valid_edit_polygon(candidate):
            return
        if final:
            candidate = _simplify_orthogonal_polygon(candidate)
            if not _is_valid_edit_polygon(candidate):
                return
        self.model.set_polygon_points(candidate)
        self._rebuild_path_from_model()
        self.update()
        if final and self.on_geometry_changed:
            self.on_geometry_changed(self.model)

    def set_debug_overlay(self, text: str) -> None:
        self._debug_overlay_text = text
        self.update()

    def set_heat(self, w_total: float, w_per_m2: float):
        self._heat_w = w_total
        self._heat_wpm2 = w_per_m2
        self.update()

    def set_area(self, a_inner: float):
        self._area_in_m2 = a_inner
        self.update()

    def _sync_model_from_geometry(self):
        old_pts = self.model.polygon_points()
        if len(old_pts) >= 3:
            min_x, min_y, _, _ = polygon_bbox(old_pts)
            new_x = snap_m(self.pos().x() / PX_PER_M)
            new_y = snap_m(self.pos().y() / PX_PER_M)
            dx = new_x - min_x
            dy = new_y - min_y
            self.model.set_polygon_points(translate_polygon(old_pts, dx, dy))
        else:
            self.model.x_m = snap_m(self.pos().x() / PX_PER_M)
            self.model.y_m = snap_m(self.pos().y() / PX_PER_M)
        try:
            self.model.recompute_volume()
        except Exception:
            pass
        self._refresh_edit_handles()

    def _apply_snapped_geometry(self, x_m: float, y_m: float, w_m: float, h_m: float):
        if self.model.has_polygon():
            self.model.translate_polygon_to(x_m, y_m)
            self._rebuild_path_from_model()
        else:
            self.setPos(x_m * PX_PER_M, y_m * PX_PER_M)

    def itemChange(self, change, value):
        if getattr(self, '_in_itemchange', False):
            return super().itemChange(change, value)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._refresh_edit_handles()
        if change == QGraphicsItem.ItemPositionChange:
            if self._vertex_drag_active:
                return self.pos()
            p = value
            x_m = snap_m(p.x() / PX_PER_M)
            y_m = snap_m(p.y() / PX_PER_M)
            return QPointF(x_m * PX_PER_M, y_m * PX_PER_M)
        if change == QGraphicsItem.ItemPositionHasChanged:
            if self._vertex_drag_active or self._edge_drag_active:
                return super().itemChange(change, value)
            try:
                self._in_itemchange = True
                self._sync_model_from_geometry()
                if self.on_geometry_changed:
                    self.on_geometry_changed(self.model)
            finally:
                self._in_itemchange = False
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(self.pen_sel if self.isSelected() else self.pen_norm)
        if self.heatmap_enabled_cb():
            rr, gg, bb, aa = heat_rgba(self._heat_wpm2)
            painter.fillPath(self.path(), QBrush(QColor.fromRgbF(rr, gg, bb, aa)))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())
        txt = getattr(self, '_debug_overlay_text', '')
        if txt:
            painter.save()
            r = self.boundingRect().adjusted(4, 4, -4, -4)
            painter.drawText(r, Qt.AlignLeft | Qt.AlignTop, txt)
            painter.restore()
        painter.save()
        painter.setPen(Qt.black)
        txt = f"{self.model.name}\n{self._area_in_m2:.1f} m²\n{self._heat_w:.0f} W\n{self._heat_wpm2:.0f} W/m²"
        painter.drawText(self.boundingRect().adjusted(6, 6, -6, -6), Qt.AlignLeft | Qt.AlignTop, txt)
        painter.restore()


class ElementLabelItem(QGraphicsSimpleTextItem):
    """
    Movable label for elements/windows.

    Conservative refactor:
    - still movable/selectable (as before)
    - BUT writes label position back as SCENE coordinates (meters), even if label is child
    - clicking the label will also select the parent (so element highlight works reliably)
    """
    def __init__(self, element: ElementModel):
        self._in_change = False
        super().__init__()
        self.element = element
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(25)
        self.setCacheMode(QGraphicsItem.NoCache)

    def mousePressEvent(self, event):
        # Ensure parent selection follows label click (prevents “selected label but not element” UX)
        try:
            p = self.parentItem()
            if p is not None:
                p.setSelected(True)
        except Exception:
            pass
        super().mousePressEvent(event)

    def itemChange(self, change, value):
        if getattr(self, "_in_change", False):
            return super().itemChange(change, value)
        if change == QGraphicsItem.ItemPositionHasChanged:
            try:
                self._in_change = True
                # store label in SCENE coords (meters) robustly (also works for child items)
                p_scene = self.mapToScene(QPointF(0, 0))
                self.element.label_x_m = p_scene.x() / PX_PER_M
                self.element.label_y_m = p_scene.y() / PX_PER_M
            finally:
                self._in_change = False

        return super().itemChange(change, value)


class ElementLineItem(QGraphicsLineItem):
    """
    Wall/element line item.

    Conservative refactor goals:
    - keep existing signature (element, on_select=None); add optional on_propose_move kw-only compat
    - ensure label/leader are *children* (prevents duplicate/ghost labels)
    - make item movable; write back model endpoints on move
    - selection highlight = bright red
    - single label placement logic (no duplicate positioning blocks)
    """

    def __init__(
        self,
        element: ElementModel,
        on_select: Optional[Callable[[ElementModel], None]] = None,
        on_propose_move: Optional[Callable[[ElementModel, float, float], Optional[Tuple[float, float]]]] = None,
    ):
        # MUST exist before Qt potentially triggers itemChange during init/flag changes
        self._in_itemchange = False
        super().__init__()

        self.element = element
        self.on_select = on_select
        self.on_propose_move = on_propose_move

        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(20)
        self.setCacheMode(QGraphicsItem.NoCache)

        # Aux items as children (single instance; moves/deletes with parent)
        self.leader = QGraphicsLineItem(self)
        self.leader.setZValue(21)

        self.label = ElementLabelItem(element)
        self.label.setParentItem(self)
        self.label.setZValue(22)

        self._base_pen = None
        self._base_label_brush = None
        self._base_leader_pen = None

        self._apply_style()
        self._sync_from_model()

    # --- styling / highlight -------------------------------------------------

    def _apply_style(self):
        style = ELEMENT_STYLES.get(self.element.element_type, ELEMENT_STYLES["default"])
        pen = QPen(style["color"], style["width"])
        if style.get("dash"):
            pen.setStyle(Qt.DashLine)
        self.setPen(pen)
        self.label.setBrush(QBrush(style["color"]))
        self.leader.setPen(QPen(style["color"], 1))

        # cache base
        self._base_pen = QPen(self.pen())
        self._base_label_brush = QBrush(self.label.brush())
        self._base_leader_pen = QPen(self.leader.pen())

    def _set_selected_visual(self, selected: bool) -> None:
        if selected:
            hl = QColor(255, 0, 0)
            p = QPen(hl, max(3, int(self.pen().widthF()) + 2))
            p.setCapStyle(Qt.RoundCap)
            p.setJoinStyle(Qt.RoundJoin)
            self.setPen(p)
            self.label.setBrush(QBrush(hl))
            self.leader.setPen(QPen(hl, 2))
        else:
            if self._base_pen is not None:
                self.setPen(QPen(self._base_pen))
            if self._base_label_brush is not None:
                self.label.setBrush(QBrush(self._base_label_brush))
            if self._base_leader_pen is not None:
                self.leader.setPen(QPen(self._base_leader_pen))

    # --- geometry sync -------------------------------------------------------

    def _sync_from_model(self):
        if not self.element.has_geometry():
            return

        x0 = float(self.element.x0_m) * PX_PER_M
        y0 = float(self.element.y0_m) * PX_PER_M
        x1 = float(self.element.x1_m) * PX_PER_M
        y1 = float(self.element.y1_m) * PX_PER_M

        # Store line in local coordinates; item pos = startpoint (stable for moving)
        #self.setPos(x0, y0)
        #self.setLine(0.0, 0.0, (x1 - x0), (y1 - y0))

         # >>> FIX: während Sync KEIN write-back via itemChange <<<
        self._in_itemchange = True
        try:
            # Store line in local coordinates; item pos = startpoint
            self.setPos(x0, y0)
            self.setLine(0.0, 0.0, (x1 - x0), (y1 - y0))
        finally:
            self._in_itemchange = False


        # label text
        L = self.element.length_m
        if L is None:
            L = self.element.compute_length()
            print(f"[DEBUG][graphics-sync] uid={self.element.uid} computed_length={L}")

            self.element.length_m = L
        # keep existing multi-line style (conservative)
        try:
            A = float(self.element.area_m2 or 0.0)
        except Exception:
            A = 0.0




        txt = f"{self.element.element_type}\nL={float(L or 0.0):.2f} m\nA={A:.2f} m²"
        self.label.setText(txt)

        # label placement (single source of truth)
        self._sync_label_and_leader()

        # rotate label upright
        pA = self.mapToScene(QPointF(0, 0))
        pB = self.mapToScene(QPointF(self.line().x2(), self.line().y2()))
        ang = angle_upright_degrees(pA, pB)
        br = self.label.boundingRect()
        self.label.setTransformOriginPoint(br.center())
        self.label.setRotation(ang)


    def _sync_label_and_leader(self):
        # midpoint in local coords
        ln = self.line()
        mx = (ln.x1() + ln.x2()) / 2.0
        my = (ln.y1() + ln.y2()) / 2.0

        # Stored label position is in scene coords (m). Convert to local child coords.
        if self.element.label_x_m is not None and self.element.label_y_m is not None:
            sx = float(self.element.label_x_m) * PX_PER_M
            sy = float(self.element.label_y_m) * PX_PER_M
            self.label.setPos(sx - self.pos().x(), sy - self.pos().y())
        else:
            self.label.setPos(mx + 8.0, my + 8.0)

        # leader line
        lbl = self.label.pos()
        dist = math.hypot(lbl.x() - mx, lbl.y() - my)
        if dist > 18:
            self.leader.setLine(mx, my, lbl.x(), lbl.y())
            self.leader.show()
        else:
            self.leader.hide()

    def _write_back_model_from_item(self):
        # write back endpoints based on item pos + local line
        ln = self.line()
        x0_px = self.pos().x()
        y0_px = self.pos().y()
        x1_px = x0_px + ln.x2()
        y1_px = y0_px + ln.y2()
        self.element.x0_m = x0_px / PX_PER_M
        self.element.y0_m = y0_px / PX_PER_M
        self.element.x1_m = x1_px / PX_PER_M
        self.element.y1_m = y1_px / PX_PER_M

        # recompute L/area (conservative: only if helpers exist)
        try:
            L = self.element.compute_length()
            if L is not None:
                print(f"[DEBUG][graphics-move] uid={self.element.uid} moved_length={L}")

                self.element.length_m = float(L)
            if getattr(self.element, "height_m", None) is not None and L is not None:
                self.element.area_m2 = float(L) * float(self.element.height_m)
        except Exception:
            pass

        # label is stored by ElementLabelItem in scene coords automatically

    # --- events --------------------------------------------------------------

    def itemChange(self, change, value):
        # guard against re-entrancy
        if getattr(self, "_in_itemchange", False):
            return super().itemChange(change, value)

        if change == QGraphicsItem.ItemSelectedHasChanged:
            try:
                self._set_selected_visual(bool(value))
            except Exception:
                pass
            return super().itemChange(change, value)

        if change == QGraphicsItem.ItemPositionChange and isinstance(value, QPointF):
            # optional snap/validation via callback (MainWindow)
            if self.on_propose_move and self.element.has_geometry():
                try:
                    x0_m = value.x() / PX_PER_M
                    y0_m = value.y() / PX_PER_M
                    out = self.on_propose_move(self.element, float(x0_m), float(y0_m))
                    if out is not None:
                        nx0, ny0 = out
                        return QPointF(float(nx0) * PX_PER_M, float(ny0) * PX_PER_M)
                except Exception:
                    pass
            return value

        if change == QGraphicsItem.ItemPositionHasChanged:
            try:
                self._in_itemchange = True
                self._write_back_model_from_item()
                # refresh label text/leader (kept conservative, but ensures correct after move)
                self._sync_from_model()
            finally:
                self._in_itemchange = False

        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if self.on_select:
            try:
                self.on_select(self.element)
            except Exception:
                pass
        super().mousePressEvent(event)


# --------------------------------------------------------------------------------------
# Legacy room class (kept as-is)
# --------------------------------------------------------------------------------------

class RoomRectItem_delete(QGraphicsRectItem):
    def __init__(self, room_model: RoomModel, on_changed: Callable[[RoomModel], None]):
        super().__init__(0, 0, room_model.w_m * PX_PER_M, room_model.h_m * PX_PER_M)
        self.room_model = room_model
        self.on_changed = on_changed
        self.setPos(room_model.x_m * PX_PER_M, room_model.y_m * PX_PER_M)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setBrush(QBrush(Qt.transparent))
        self.setPen(QPen(Qt.black, 2))
        self.setZValue(1)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            p = self.pos()
            self.room_model.x_m = p.x() / PX_PER_M
            self.room_model.y_m = p.y() / PX_PER_M
            self.on_changed(self.room_model)
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(self.pen() if not self.isSelected() else QPen(Qt.red, 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect())
        painter.drawText(self.rect().adjusted(6, 6, -6, -6), Qt.AlignLeft | Qt.AlignTop, self.room_model.name)


# --------------------------------------------------------------------------------------
# WindowLineItem (already uses local coords + child label; kept)
# --------------------------------------------------------------------------------------

class WindowLineItem(QGraphicsLineItem):
    """Movable window item constrained to its host wall (axis-aligned).

    The line is stored in *local* coordinates; the item's pos() is the start point (x0/y0).
    """

    def __init__(
        self,
        element: ElementModel,
        *,
        orient: str,
        c_m: float,
        a0_m: float,
        a1_m: float,
        on_geometry_changed: Optional[Callable[[ElementModel], None]] = None,
    ):
        super().__init__()
        self.element = element
        self._orient = orient  # 'H'/'V'
        self._c_m = float(c_m)
        self._a0_m = float(min(a0_m, a1_m))
        self._a1_m = float(max(a0_m, a1_m))
        self._on_geometry_changed = on_geometry_changed

        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(30)
        self.setCacheMode(QGraphicsItem.NoCache)

        self.leader = QGraphicsLineItem(self)
        self.leader.setZValue(31)
        # Keep label as child so it is shown and gets deleted with the window.
        self.label = ElementLabelItem(element)
        self.label.setParentItem(self)
        self.label.setZValue(32)

        self._apply_style()
        self._sync_from_model()

    def _apply_style(self):
        style = ELEMENT_STYLES.get(self.element.element_type, ELEMENT_STYLES["default"])
        pen = QPen(style["color"], style["width"])
        if style.get("dash"):
            pen.setStyle(Qt.DashLine)
        self.setPen(pen)
        self.label.setBrush(QBrush(style["color"]))
        self.leader.setPen(QPen(style["color"], 1))

    def _sync_from_model(self):
        # Ensure length
        L = self.element.length_m
        if L is None:
            L = self.element.compute_length() or 1.0
            self.element.length_m = L

        # local line + item pos
        if self._orient == "H":
            self.setLine(0, 0, L * PX_PER_M, 0)
            x0 = (self.element.x0_m or 0.0) * PX_PER_M
            y0 = (self.element.y0_m if self.element.y0_m is not None else self._c_m) * PX_PER_M
            self.setPos(x0, y0)
        else:
            self.setLine(0, 0, 0, L * PX_PER_M)
            x0 = (self.element.x0_m if self.element.x0_m is not None else self._c_m) * PX_PER_M
            y0 = (self.element.y0_m or 0.0) * PX_PER_M
            self.setPos(x0, y0)

        # label text
        A = self.element.area_m2
        txt = f"{self.element.element_type}\nL={L:.2f} m\nA={A:.2f} m²"
        self.label.setText(txt)

        # label rotation
        pA = self.mapToScene(QPointF(0, 0))
        pB = self.mapToScene(QPointF(self.line().x2(), self.line().y2()))
        ang = angle_upright_degrees(pA, pB)
        br = self.label.boundingRect()
        self.label.setTransformOriginPoint(br.center())
        self.label.setRotation(ang)

        # label position (relative)
        mx = (pA.x() + pB.x()) / 2
        my = (pA.y() + pB.y()) / 2
        self.label.setPos(self.mapFromScene(mx + 8, my + 8))

        # leader line if displaced
        lbl_scene = self.mapToScene(self.label.pos())
        dist = math.hypot(lbl_scene.x() - mx, lbl_scene.y() - my)
        if dist > 18:
            a = self.mapFromScene(mx, my)
            self.leader.setLine(a.x(), a.y(), self.label.pos().x(), self.label.pos().y())
            self.leader.show()
        else:
            self.leader.hide()

    def _write_back_model(self):
        L = float(self.element.length_m or 0.0)
        sx = self.scenePos().x() / PX_PER_M
        sy = self.scenePos().y() / PX_PER_M
        if self._orient == "H":
            x0 = sx
            y0 = self._c_m
            self.element.x0_m = x0
            self.element.y0_m = y0
            self.element.x1_m = x0 + L
            self.element.y1_m = y0
        else:
            x0 = self._c_m
            y0 = sy
            self.element.x0_m = x0
            self.element.y0_m = y0
            self.element.x1_m = x0
            self.element.y1_m = y0 + L

        # label stored as scene coordinates
        lbl_scene = self.mapToScene(self.label.pos())
        self.element.label_x_m = lbl_scene.x() / PX_PER_M
        self.element.label_y_m = lbl_scene.y() / PX_PER_M

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and isinstance(value, QPointF):
            # constrain to wall axis and to [a0, a1]
            x = value.x() / PX_PER_M
            y = value.y() / PX_PER_M
            L = float(self.element.length_m or 0.0)

            if self._orient == "H":
                y = self._c_m
                x_min = self._a0_m
                x_max = self._a1_m - L
                if x_max < x_min:
                    x_max = x_min
                x = max(x_min, min(x, x_max))
            else:
                x = self._c_m
                y_min = self._a0_m
                y_max = self._a1_m - L
                if y_max < y_min:
                    y_max = y_min
                y = max(y_min, min(y, y_max))

            return QPointF(x * PX_PER_M, y * PX_PER_M)

        if change == QGraphicsItem.ItemPositionHasChanged:
            self._write_back_model()
            if self._on_geometry_changed:
                self._on_geometry_changed(self.element)

        return super().itemChange(change, value)