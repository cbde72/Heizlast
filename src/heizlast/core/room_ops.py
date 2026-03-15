from __future__ import annotations

from typing import Iterable, Optional, Sequence

from .anchors import dump_meta, meta_rooms, parse_edge_anchor, parse_meta, update_edge_anchor_meta
from .geometry import nearest_edge_span_for_point, room_polygon
from ..domain.models import ElementModel, RoomModel

EPS = 1e-9


def stable_split_room_id(base_id: str, existing_ids: Iterable[str]) -> str:
    existing = {str(x) for x in existing_ids}
    base = str(base_id or 'ROOM').strip() or 'ROOM'
    candidates = [f"{base}_2", f"{base}_B", f"{base}_split"]
    for cand in candidates:
        if cand not in existing:
            return cand
    i = 2
    while True:
        cand = f"{base}_{i}"
        if cand not in existing:
            return cand
        i += 1


def element_center(e: ElementModel) -> tuple[Optional[float], Optional[float]]:
    if getattr(e, 'has_geometry', lambda: False)():
        try:
            return (
                0.5 * (float(e.x0_m) + float(e.x1_m)),
                0.5 * (float(e.y0_m) + float(e.y1_m)),
            )
        except Exception:
            pass
    try:
        if getattr(e, 'label_x_m', None) is not None and getattr(e, 'label_y_m', None) is not None:
            return float(e.label_x_m), float(e.label_y_m)
    except Exception:
        pass
    return None, None


def point_in_or_on_polygon(x: float, y: float, pts: Sequence[tuple[float, float]], tol: float = 0.05) -> bool:
    if len(pts) < 3:
        return False
    x = float(x); y = float(y)
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if min(x0, x1) - tol <= x <= max(x0, x1) + tol and min(y0, y1) - tol <= y <= max(y0, y1) + tol:
            dx = x1 - x0; dy = y1 - y0
            if abs(dx) <= EPS and abs(x - x0) <= tol:
                return True
            if abs(dy) <= EPS and abs(y - y0) <= tol:
                return True
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        intersects = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) if abs(yj - yi) > EPS else EPS) + xi)
        if intersects:
            inside = not inside
        j = i
    return inside


def find_room_for_point(rooms: Sequence[RoomModel], x: float, y: float, *, floor: Optional[str] = None, preferred_ids: Optional[set[str]] = None) -> Optional[RoomModel]:
    cand = [r for r in rooms if floor is None or getattr(r, 'floor', None) == floor]
    if preferred_ids:
        preferred = [r for r in cand if str(getattr(r, 'id', '')) in preferred_ids]
        if preferred:
            cand = preferred + [r for r in cand if str(getattr(r, 'id', '')) not in preferred_ids]
    for r in cand:
        try:
            if point_in_or_on_polygon(float(x), float(y), room_polygon(r)):
                return r
        except Exception:
            pass
    return None


def affected_room_ids_from_element(e: ElementModel) -> set[str]:
    ids = set(meta_rooms(getattr(e, 'meta', '') or ''))
    rid = str(getattr(e, 'room_id', '') or '')
    if rid:
        ids.add(rid)
    return ids


def is_auto_generated_element(e: ElementModel) -> bool:
    uid = str(getattr(e, 'uid', '') or '')
    meta = str(getattr(e, 'meta', '') or '')
    return uid.startswith('auto_') or 'auto_contour' in meta or 'auto_shared' in meta


def reassign_elements_after_room_operation(
    elements: list[ElementModel],
    rooms_by_id: dict[str, RoomModel],
    *,
    affected_room_ids: Iterable[str],
    deleted_room_ids: Iterable[str] = (),
) -> list[ElementModel]:
    affected = {str(x) for x in affected_room_ids}
    deleted = {str(x) for x in deleted_room_ids}
    rooms_all = list(rooms_by_id.values())
    out: list[ElementModel] = []
    for e in elements:
        room_refs = affected_room_ids_from_element(e)
        if not (room_refs & (affected | deleted)):
            out.append(e)
            continue
        if is_auto_generated_element(e):
            # auto-elements are rebuilt elsewhere
            continue
        floor = getattr(e, 'floor', None)
        x, y = element_center(e)
        if str(getattr(e, 'element_type', '') or '') == 'Fenster':
            if x is None or y is None:
                continue
            floor_rooms = [r for r in rooms_all if getattr(r, 'floor', None) == floor]
            preferred = {rid for rid in room_refs if rid in rooms_by_id}
            target_room = find_room_for_point(floor_rooms, float(x), float(y), floor=floor, preferred_ids=preferred)
            if target_room is None:
                continue
            span = nearest_edge_span_for_point(floor_rooms, floor, float(x), float(y), prefer_outer=True, room_id=target_room.id)
            if span is None:
                span = nearest_edge_span_for_point(floor_rooms, floor, float(x), float(y), prefer_outer=True)
            if span is None:
                continue
            e.room_id = span.owner_room_id
            e.floor = span.floor
            orient = span.orient
            a0 = min(float(span.a0), float(span.a1))
            a1 = max(float(span.a0), float(span.a1))
            width = float(parse_edge_anchor(getattr(e, 'meta', '') or '').get('w') or 0.0)
            if width <= 1e-9 and getattr(e, 'has_geometry', lambda: False)():
                try:
                    width = ((float(e.x1_m) - float(e.x0_m)) ** 2 + (float(e.y1_m) - float(e.y0_m)) ** 2) ** 0.5
                except Exception:
                    width = 0.0
            width = max(0.2, width)
            if orient == 'H':
                center = max(a0 + 0.5 * width, min(float(x), a1 - 0.5 * width)) if (a1 - a0) > width else 0.5 * (a0 + a1)
                e.x0_m, e.y0_m, e.x1_m, e.y1_m = center - 0.5 * width, float(span.c), center + 0.5 * width, float(span.c)
                s = center - a0
            else:
                center = max(a0 + 0.5 * width, min(float(y), a1 - 0.5 * width)) if (a1 - a0) > width else 0.5 * (a0 + a1)
                e.x0_m, e.y0_m, e.x1_m, e.y1_m = float(span.c), center - 0.5 * width, float(span.c), center + 0.5 * width
                s = center - a0
            e.length_m = width
            e.meta = update_edge_anchor_meta(
                getattr(e, 'meta', '') or '',
                parent=span.uid,
                orient=orient,
                c=float(span.c),
                a0=a0,
                a1=a1,
                s=s,
                w=width,
                rooms=getattr(span, 'room_ids', None),
            )
            out.append(e)
            continue

        # generic/manual elements: keep UID and move ownership to containing room if possible
        target = None
        if x is not None and y is not None:
            target = find_room_for_point(rooms_all, float(x), float(y), floor=floor, preferred_ids={rid for rid in room_refs if rid in rooms_by_id})
        if target is None:
            current = str(getattr(e, 'room_id', '') or '')
            if current in rooms_by_id:
                target = rooms_by_id[current]
            elif room_refs:
                for rid in sorted(room_refs):
                    if rid in rooms_by_id:
                        target = rooms_by_id[rid]
                        break
        if target is None:
            continue
        e.room_id = target.id
        e.floor = target.floor
        meta = parse_meta(getattr(e, 'meta', '') or '')
        rooms_keep = sorted({rid for rid in room_refs if rid in rooms_by_id} | {target.id})
        if rooms_keep:
            meta['rooms'] = ','.join(rooms_keep)
            try:
                e.meta = dump_meta(meta)
            except Exception:
                pass
        out.append(e)
    return out
