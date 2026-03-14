from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from ...core.geometry import merge_room_polygons, room_polygon, split_room_polygon, subtract_room_polygons
from ...core.room_ops import reassign_elements_after_room_operation, stable_split_room_id
from ...core.polygon_ops import polygon_area, polygon_bbox, rect_to_polygon, serialize_polygon_m, validate_orthogonal_polygon
from ..house_state import HouseState
from ..models import ElementModel, RoomModel
from .house_domain_service import BuildAutoWallsFn, HouseDomainService


@dataclass
class RoomOperationSnapshot:
    rooms: Dict[str, RoomModel]
    elements: List[ElementModel]


@dataclass
class RoomOperationRecord:
    operation: str
    before: RoomOperationSnapshot
    after: RoomOperationSnapshot
    selected_room_id: Optional[str] = None

    def undo(self, state: HouseState) -> None:
        state.rooms = deepcopy(self.before.rooms)
        state.elements = deepcopy(self.before.elements)

    def redo(self, state: HouseState) -> None:
        state.rooms = deepcopy(self.after.rooms)
        state.elements = deepcopy(self.after.elements)


@dataclass
class RoomOperationService:
    domain: HouseDomainService
    build_auto_walls: Optional[BuildAutoWallsFn] = None

    def snapshot(self, state: HouseState) -> RoomOperationSnapshot:
        return RoomOperationSnapshot(rooms=deepcopy(state.rooms), elements=deepcopy(state.elements))

    def _normalize_room(self, room: RoomModel) -> None:
        room.ensure_polygon()
        self.domain.normalize_room_geometry(room)

    def _rect_bbox_from_points(self, points: Sequence[tuple[float, float]]) -> Optional[tuple[float, float, float, float]]:
        pts = list(points or [])
        if len(pts) != 4:
            return None
        x0, y0, x1, y1 = polygon_bbox(pts)
        target = {
            (round(x0, 9), round(y0, 9)),
            (round(x1, 9), round(y0, 9)),
            (round(x1, 9), round(y1, 9)),
            (round(x0, 9), round(y1, 9)),
        }
        got = {(round(x, 9), round(y, 9)) for x, y in pts}
        if got != target or abs(x1 - x0) <= 1e-9 or abs(y1 - y0) <= 1e-9:
            return None
        return float(x0), float(y0), float(x1), float(y1)

    def _merge_fallback(self, polygons: Sequence[Sequence[tuple[float, float]]]) -> list[tuple[float, float]]:
        rects = [self._rect_bbox_from_points(p) for p in polygons]
        if any(r is None for r in rects):
            return []
        xs0 = [r[0] for r in rects if r is not None]
        ys0 = [r[1] for r in rects if r is not None]
        xs1 = [r[2] for r in rects if r is not None]
        ys1 = [r[3] for r in rects if r is not None]
        bx0, by0, bx1, by1 = min(xs0), min(ys0), max(xs1), max(ys1)
        area_sum = sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects if r is not None)
        if abs(area_sum - ((bx1 - bx0) * (by1 - by0))) > 1e-6:
            return []
        return rect_to_polygon(bx0, by0, bx1 - bx0, by1 - by0)

    def _subtract_fallback(self, base_polygon: Sequence[tuple[float, float]], cut_polygons: Sequence[Sequence[tuple[float, float]]]) -> list[tuple[float, float]]:
        base = self._rect_bbox_from_points(base_polygon)
        cuts = [self._rect_bbox_from_points(p) for p in cut_polygons]
        if base is None or any(c is None for c in cuts):
            return []
        x0, y0, x1, y1 = base
        for cut in [c for c in cuts if c is not None]:
            cx0, cy0, cx1, cy1 = cut
            if abs(cy0 - y0) <= 1e-9 and abs(cy1 - y1) <= 1e-9:
                if abs(cx0 - x0) <= 1e-9 and x0 < cx1 < x1:
                    x0 = cx1
                    continue
                if abs(cx1 - x1) <= 1e-9 and x0 < cx0 < x1:
                    x1 = cx0
                    continue
            if abs(cx0 - x0) <= 1e-9 and abs(cx1 - x1) <= 1e-9:
                if abs(cy0 - y0) <= 1e-9 and y0 < cy1 < y1:
                    y0 = cy1
                    continue
                if abs(cy1 - y1) <= 1e-9 and y0 < cy0 < y1:
                    y1 = cy0
                    continue
            return []
        if x1 - x0 <= 1e-9 or y1 - y0 <= 1e-9:
            return []
        return rect_to_polygon(x0, y0, x1 - x0, y1 - y0)

    def _split_fallback(self, points: Sequence[tuple[float, float]], orientation: str, coord: float) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        rect = self._rect_bbox_from_points(points)
        if rect is None:
            return [], []
        x0, y0, x1, y1 = rect
        c = float(coord)
        if str(orientation).lower().startswith('v'):
            if not (x0 < c < x1):
                return [], []
            return rect_to_polygon(x0, y0, c - x0, y1 - y0), rect_to_polygon(c, y0, x1 - c, y1 - y0)
        if not (y0 < c < y1):
            return [], []
        return rect_to_polygon(x0, y0, x1 - x0, c - y0), rect_to_polygon(x0, c, x1 - x0, y1 - c)

    def _new_room_from_polygon(self, *, base_room: RoomModel, room_id: str, name: str, points: Sequence[tuple[float, float]]) -> RoomModel:
        pts = list(points or [])
        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        room = RoomModel(
            id=str(room_id),
            floor=str(base_room.floor),
            name=str(name),
            x_m=min(xs),
            y_m=min(ys),
            w_m=max(xs) - min(xs),
            h_m=max(ys) - min(ys),
            height_m=float(getattr(base_room, 'height_m', 2.5) or 2.5),
            t_inside_c=float(getattr(base_room, 't_inside_c', 20.0) or 20.0),
            air_change_1ph=float(getattr(base_room, 'air_change_1ph', 0.5) or 0.5),
            usage_type=getattr(base_room, 'usage_type', None),
            polygon_m=serialize_polygon_m(pts),
        )
        self._normalize_room(room)
        return room

    def _finalize(self, state: HouseState, *, affected_room_ids: Iterable[str], deleted_room_ids: Iterable[str]) -> None:
        state.elements = reassign_elements_after_room_operation(
            list(state.elements),
            dict(state.rooms),
            affected_room_ids=list(affected_room_ids),
            deleted_room_ids=list(deleted_room_ids),
        )
        if self.build_auto_walls is not None:
            self.domain.rebuild_autowalls_all(state, build_auto_walls=self.build_auto_walls)

    def merge_rooms(self, state: HouseState, room_ids: Sequence[str]) -> Optional[RoomOperationRecord]:
        ids = [str(rid) for rid in room_ids if str(rid) in state.rooms]
        if len(ids) < 2:
            return None
        rooms = [state.rooms[rid] for rid in ids]
        if len({r.floor for r in rooms}) != 1:
            return None
        polygons = [room_polygon(r) for r in rooms]
        merged = merge_room_polygons(polygons)
        if not validate_orthogonal_polygon(merged):
            merged = self._merge_fallback(polygons)
        if not validate_orthogonal_polygon(merged):
            return None
        before = self.snapshot(state)
        keep = rooms[0]
        removed_ids = [r.id for r in rooms[1:]]
        keep.set_polygon_points(merged)
        self._normalize_room(keep)
        for rid in removed_ids:
            state.rooms.pop(rid, None)
        self._finalize(state, affected_room_ids=[keep.id], deleted_room_ids=removed_ids)
        after = self.snapshot(state)
        return RoomOperationRecord('merge', before=before, after=after, selected_room_id=keep.id)

    def subtract_rooms(self, state: HouseState, base_room_id: str, cutter_room_ids: Sequence[str]) -> Optional[RoomOperationRecord]:
        base = state.rooms.get(str(base_room_id))
        if base is None:
            return None
        cutters = [state.rooms[rid] for rid in cutter_room_ids if rid in state.rooms and rid != base.id]
        if not cutters:
            return None
        if len({r.floor for r in [base] + cutters}) != 1:
            return None
        base_poly = room_polygon(base)
        cut_polys = [room_polygon(r) for r in cutters]
        result = subtract_room_polygons(base_poly, cut_polys)
        if not validate_orthogonal_polygon(result):
            result = self._subtract_fallback(base_poly, cut_polys)
        if not validate_orthogonal_polygon(result):
            return None
        before = self.snapshot(state)
        removed_ids = [r.id for r in cutters]
        base.set_polygon_points(result)
        self._normalize_room(base)
        for rid in removed_ids:
            state.rooms.pop(rid, None)
        self._finalize(state, affected_room_ids=[base.id], deleted_room_ids=removed_ids)
        after = self.snapshot(state)
        return RoomOperationRecord('subtract', before=before, after=after, selected_room_id=base.id)

    def split_room(self, state: HouseState, room_id: str, *, orientation: str, coord: float) -> Optional[RoomOperationRecord]:
        room = state.rooms.get(str(room_id))
        if room is None:
            return None
        poly = room_polygon(room)
        a, b = split_room_polygon(poly, orientation, float(coord))
        if not (validate_orthogonal_polygon(a) and validate_orthogonal_polygon(b)):
            a, b = self._split_fallback(poly, orientation, float(coord))
        if not (validate_orthogonal_polygon(a) and validate_orthogonal_polygon(b)):
            return None
        before = self.snapshot(state)
        old_room_id = room.id
        room.set_polygon_points(a)
        self._normalize_room(room)
        new_id = stable_split_room_id(old_room_id, state.rooms.keys())
        new_name = f"{getattr(room, 'name', old_room_id)} B"
        new_room = self._new_room_from_polygon(base_room=room, room_id=new_id, name=new_name, points=b)
        state.rooms[new_room.id] = new_room
        self._finalize(state, affected_room_ids=[old_room_id, new_room.id], deleted_room_ids=[])
        after = self.snapshot(state)
        return RoomOperationRecord('split', before=before, after=after, selected_room_id=old_room_id)
