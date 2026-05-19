from __future__ import annotations
import math
from typing import Callable, Optional, Tuple
from ..domain.models import ElementModel

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QBrush, QPainter, QColor, QPainterPath
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsRectItem, QGraphicsLineItem, QGraphicsSimpleTextItem, QGraphicsPathItem, QGraphicsEllipseItem,
    QSizePolicy,
)

from ..core.attic_auto import is_auto_attic_element, parse_attic_meta
from ..core.config import PX_PER_M, GRID_M, HANDLE_SZ_PX, ELEMENT_STYLES, HEATMAP_CAP_W_PER_M2
from ..domain.models import RoomModel
from ..core.polygon_ops import (
    polygon_bbox,
    simplify_orthogonal_polygon,
    snap_m as core_snap_m,
    translate_polygon,
    validate_orthogonal_polygon,
)

# Room interaction tuning
RESIZE_MARGIN_PX = 10.0  # px: grab zone at room edges
ROOM_SNAP_PX = 10.0      # px: snap tolerance to other room edges
ROOM_TOUCH_EPS = 0.0     # px: >0 would require a gap; 0 => touching is allowed


def _ctrl_drag_requested(event) -> bool:
    try:
        return bool(event.modifiers() & Qt.ControlModifier)
    except Exception:
        return False


# --------------------------------------------------------------------------------------
# helpers (kept)
# --------------------------------------------------------------------------------------

def snap_m(x: float, step: float = 0.05) -> float:
    return core_snap_m(x, step)


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


# --------------------------------------------------------------------------------------
# Plan view (kept)
# --------------------------------------------------------------------------------------

class PlanView(QGraphicsView):
    """V06-style view with smoother CAD-like zoom and pan behaviour."""
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)

        # Zoom-Setup
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

        self._zoom_level = 0
        self._zoom_step = 1.15
        self._zoom_min = -12
        self._zoom_max = 24
        self._panning = False
        self._pan_start = None

        # Drag only on explicit pan gesture, selection remains unchanged otherwise.
        self.setDragMode(QGraphicsView.NoDrag)
        self._context_menu_handler = None

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

    def fit_content(self, padding_px: float = 40.0):
        """Zentriert und zoomt auf den tatsächlichen Inhalt der Szene."""
        scene = self.scene()
        if scene is None:
            self.fit_all()
            return

        rect = scene.itemsBoundingRect()
        if not rect.isValid() or rect.isNull() or rect.width() <= 1.0 or rect.height() <= 1.0:
            self.fit_all()
            return

        rect = rect.adjusted(-padding_px, -padding_px, padding_px, padding_px)
        self.fitInView(rect, Qt.KeepAspectRatio)
        self.centerOn(rect.center())
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
        # Maus-Rad zoomt immer zur Mausposition; Ctrl bleibt ebenfalls unterstützt.
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return

        steps = max(1, abs(delta) // 120)
        for _ in range(int(steps)):
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()

        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


    def contextMenuEvent(self, event):
        handler = getattr(self, "_context_menu_handler", None)
        if callable(handler):
            try:
                if handler(self, event):
                    event.accept()
                    return
            except Exception:
                pass
        super().contextMenuEvent(event)


# --------------------------------------------------------------------------------------
# Room handles + room item (kept)
# --------------------------------------------------------------------------------------


# Legacy RoomRectItem path removed in 7A block 1.
# Rooms are rendered and edited exclusively via RoomPolygonItem.

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
        self._ctrl_move_active = False
        self._mouse_move_guard_active = False
        self.vertex_handles: list[PolygonVertexHandleItem] = []
        self.edge_handles: list[PolygonEdgeHandleItem] = []
        self._rebuild_path_from_model()
        self._refresh_edit_handles()

    def _rebuild_path_from_model(self):
        self.model.ensure_polygon()
        pts = self.model.polygon_points()
        if len(pts) < 3:
            return
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
        self.model.ensure_polygon()
        pts = self.model.polygon_points()
        if len(pts) < 3:
            return
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
        if not validate_orthogonal_polygon(candidate):
            return
        if final:
            candidate = simplify_orthogonal_polygon(candidate)
            if not validate_orthogonal_polygon(candidate):
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
        if not validate_orthogonal_polygon(candidate):
            return
        if final:
            candidate = simplify_orthogonal_polygon(candidate)
            if not validate_orthogonal_polygon(candidate):
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
        self.model.ensure_polygon()
        old_pts = self.model.polygon_points()
        if len(old_pts) >= 3:
            min_x, min_y, _, _ = polygon_bbox(old_pts)
            new_x = snap_m(self.pos().x() / PX_PER_M)
            new_y = snap_m(self.pos().y() / PX_PER_M)
            dx = new_x - min_x
            dy = new_y - min_y
            self.model.set_polygon_points(translate_polygon(old_pts, dx, dy))
        try:
            self.model.recompute_volume()
        except Exception:
            pass
        self._refresh_edit_handles()

    def _apply_snapped_geometry(self, x_m: float, y_m: float, w_m: float, h_m: float):
        self.model.ensure_polygon()
        self.model.translate_polygon_to(x_m, y_m)
        self._rebuild_path_from_model()

    def itemChange(self, change, value):
        if getattr(self, '_in_itemchange', False):
            return super().itemChange(change, value)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._refresh_edit_handles()
        if change == QGraphicsItem.ItemPositionChange:
            if getattr(self, "_mouse_move_guard_active", False) and not getattr(self, "_ctrl_move_active", False):
                return self.pos()
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

    def mousePressEvent(self, event):
        self._mouse_move_guard_active = True
        self._ctrl_move_active = _ctrl_drag_requested(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._ctrl_move_active = _ctrl_drag_requested(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._mouse_move_guard_active = False
        self._ctrl_move_active = False

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
        self._ctrl_move_active = False
        self._mouse_move_guard_active = False
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
        self._mouse_move_guard_active = True
        self._ctrl_move_active = _ctrl_drag_requested(event)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._mouse_move_guard_active = False
        self._ctrl_move_active = False

    def mouseMoveEvent(self, event):
        self._ctrl_move_active = _ctrl_drag_requested(event)
        super().mouseMoveEvent(event)

    def itemChange(self, change, value):
        if getattr(self, "_in_change", False):
            return super().itemChange(change, value)
        if (
            change == QGraphicsItem.ItemPositionChange
            and getattr(self, "_mouse_move_guard_active", False)
            and not getattr(self, "_ctrl_move_active", False)
        ):
            return self.pos()
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
        self._ctrl_move_active = False
        self._mouse_move_guard_active = False
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
        self._show_auto_attic_visual = False
        self._badge_circle = None
        self._badge_text = None

        self._apply_style()
        self._sync_from_model()

    # --- styling / highlight -------------------------------------------------

    def _is_auto_attic(self) -> bool:
        try:
            return is_auto_attic_element(self.element)
        except Exception:
            return False

    def _auto_attic_part(self) -> str:
        try:
            return str(parse_attic_meta(getattr(self.element, "meta", None)).get("attic_part", "") or "")
        except Exception:
            return ""

    def _auto_attic_style_spec(self) -> tuple[QColor, str]:
        part = self._auto_attic_part()
        mapping = {
            "roof_left": (QColor(168, 85, 247), "DL"),
            "roof_right": (QColor(217, 70, 239), "DR"),
            "roof_front": (QColor(129, 140, 248), "DF"),
            "roof_back": (QColor(99, 102, 241), "DH"),
            "gable_front": (QColor(245, 158, 11), "GV"),
            "gable_back": (QColor(234, 88, 12), "GH"),
            "gable_left": (QColor(251, 191, 36), "GL"),
            "gable_right": (QColor(249, 115, 22), "GR"),
            "roof_window": (QColor(14, 165, 233), "DF"),
            "dormer_front": (QColor(20, 184, 166), "GF"),
            "dormer_side_left": (QColor(13, 148, 136), "GS"),
            "dormer_side_right": (QColor(13, 148, 136), "GS"),
            "dormer_roof": (QColor(45, 212, 191), "GD"),
            "dormer_window": (QColor(6, 182, 212), "GW"),
        }
        return mapping.get(part, (QColor(139, 92, 246), "DG"))

    def set_auto_attic_visual_enabled(self, enabled: bool) -> None:
        self._show_auto_attic_visual = bool(enabled)
        self._apply_style()
        self._sync_label_and_leader()
        self.update()

    def _ensure_auto_attic_badge(self) -> None:
        if self._badge_circle is None:
            self._badge_circle = QGraphicsEllipseItem(self)
            self._badge_circle.setZValue(23)
            self._badge_circle.setRect(-9.0, -9.0, 18.0, 18.0)
            self._badge_circle.setPen(QPen(Qt.white, 1.5))
        if self._badge_text is None:
            self._badge_text = QGraphicsSimpleTextItem(self)
            self._badge_text.setZValue(24)

    def _sync_auto_attic_badge(self) -> None:
        enabled = bool(self._show_auto_attic_visual and self._is_auto_attic())
        if not enabled:
            if self._badge_circle is not None:
                self._badge_circle.hide()
            if self._badge_text is not None:
                self._badge_text.hide()
            return

        self._ensure_auto_attic_badge()
        color, badge = self._auto_attic_style_spec()
        self._badge_circle.setBrush(QBrush(color))
        self._badge_text.setBrush(QBrush(Qt.white))
        self._badge_text.setText(badge)

        ln = self.line()
        mx = (ln.x1() + ln.x2()) / 2.0
        my = (ln.y1() + ln.y2()) / 2.0
        dx = ln.x2() - ln.x1()
        dy = ln.y2() - ln.y1()
        length = max(1.0, math.hypot(dx, dy))
        nx = -dy / length
        ny = dx / length
        bx = mx + nx * 14.0
        by = my + ny * 14.0
        self._badge_circle.setPos(bx, by)
        br = self._badge_text.boundingRect()
        self._badge_text.setPos(bx - br.width() / 2.0, by - br.height() / 2.0)
        self._badge_circle.show()
        self._badge_text.show()

    def _apply_style(self):
        style = ELEMENT_STYLES.get(self.element.element_type, ELEMENT_STYLES["default"])
        line_color = style["color"]
        line_width = style["width"]
        dash = bool(style.get("dash"))
        if self._show_auto_attic_visual and self._is_auto_attic():
            attic_color, _ = self._auto_attic_style_spec()
            line_color = attic_color
            line_width = max(float(line_width) + 1.0, 4.0)
            dash = True
        pen = QPen(line_color, line_width)
        if dash:
            pen.setStyle(Qt.DashLine)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
        self.label.setBrush(QBrush(line_color))
        self.leader.setPen(QPen(line_color, 1))

        # cache base
        self._base_pen = QPen(self.pen())
        self._base_label_brush = QBrush(self.label.brush())
        self._base_leader_pen = QPen(self.leader.pen())
        self._sync_auto_attic_badge()

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

        self._sync_auto_attic_badge()

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
            if getattr(self, "_mouse_move_guard_active", False) and not getattr(self, "_ctrl_move_active", False):
                return self.pos()
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
        self._mouse_move_guard_active = True
        self._ctrl_move_active = _ctrl_drag_requested(event)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._mouse_move_guard_active = False
        self._ctrl_move_active = False

    def mouseMoveEvent(self, event):
        self._ctrl_move_active = _ctrl_drag_requested(event)
        super().mouseMoveEvent(event)


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
        self._ctrl_move_active = False
        self._mouse_move_guard_active = False

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
            if getattr(self, "_mouse_move_guard_active", False) and not getattr(self, "_ctrl_move_active", False):
                return self.pos()
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

    def mousePressEvent(self, event):
        self._mouse_move_guard_active = True
        self._ctrl_move_active = _ctrl_drag_requested(event)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._mouse_move_guard_active = False
        self._ctrl_move_active = False

    def mouseMoveEvent(self, event):
        self._ctrl_move_active = _ctrl_drag_requested(event)
        super().mouseMoveEvent(event)
