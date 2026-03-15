from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from ..domain.models import ElementModel, RoomModel
from .config import DEFAULT_U, DEFAULT_FACTOR
from .anchors import build_edge_span_meta
from .polygon_ops import parse_polygon_m, rect_to_polygon, simplify_orthogonal_polygon

EPS = 1e-6

@dataclass(frozen=True)
class Edge:
    orient: str  # 'H' or 'V'
    c: float     # y for H, x for V
    a0: float    # interval start (x for H, y for V)
    a1: float    # interval end
    room_id: str
    floor: str
    height_m: float


@dataclass(frozen=True)
class EdgeSpan:
    orient: str
    c: float
    a0: float
    a1: float
    floor: str
    room_ids: Tuple[str, ...]
    owner_room_id: str
    height_m: float
    element_type: str
    meta: str
    uid: str

    @property
    def length_m(self) -> float:
        return abs(float(self.a1) - float(self.a0))

    def endpoints(self) -> tuple[tuple[float, float], tuple[float, float]]:
        if self.orient == 'H':
            return (float(self.a0), float(self.c)), (float(self.a1), float(self.c))
        return (float(self.c), float(self.a0)), (float(self.c), float(self.a1))

def orthogonalize_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not points:
        return []
    out = [points[0]]
    for x, y in points[1:]:
        px, py = out[-1]
        dx = x - px
        dy = y - py
        if abs(dx) >= abs(dy):
            out.append((x, py))
        else:
            out.append((px, y))
    return out


def room_edges(room: RoomModel) -> List[Edge]:
    pts = room_polygon(room)
    out: List[Edge] = []
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if abs(y0 - y1) <= EPS:
            a0, a1 = sorted((x0, x1))
            out.append(Edge('H', float(y0), float(a0), float(a1), room.id, room.floor, room.height_m))
        elif abs(x0 - x1) <= EPS:
            a0, a1 = sorted((y0, y1))
            out.append(Edge('V', float(x0), float(a0), float(a1), room.id, room.floor, room.height_m))
    return out

def _key(orient: str, c: float, tol: float=1e-6) -> Tuple[str, int]:
    return (orient, int(round(c / tol)))


def _normalize_interval(a0: float, a1: float) -> Tuple[float,float]:
    return (a0, a1) if a0 <= a1 else (a1, a0)


def _fmt_uid_num(x: float) -> str:
    return f"{float(x):.6f}".replace('-', 'm').replace('.', 'p')


def _edge_span_uid(floor: str, orient: str, c: float, a0: float, a1: float, element_type: str) -> str:
    et = 'shared' if 'innen' in (element_type or '').strip().lower() else 'outer'
    return f"auto_{et}_{floor}_{orient}_{_fmt_uid_num(c)}_{_fmt_uid_num(a0)}_{_fmt_uid_num(a1)}"


def _dist_point_to_axis_segment(x: float, y: float, orient: str, c: float, a0: float, a1: float) -> float:
    a_min = min(a0, a1)
    a_max = max(a0, a1)
    if orient == 'H':
        if a_min <= x <= a_max:
            return abs(y - c)
        xx = a_min if x < a_min else a_max
        return ((x - xx) ** 2 + (y - c) ** 2) ** 0.5
    if a_min <= y <= a_max:
        return abs(x - c)
    yy = a_min if y < a_min else a_max
    return ((x - c) ** 2 + (y - yy) ** 2) ** 0.5


def classify_floor_edge_spans(rooms: List[RoomModel]) -> List[EdgeSpan]:
    groups: Dict[Tuple[str,int], List[Edge]] = {}
    for r in rooms:
        for e in room_edges(r):
            groups.setdefault(_key(e.orient, e.c), []).append(e)

    spans: List[EdgeSpan] = []
    for (orient, _), edges in groups.items():
        cuts: List[float] = []
        for e in edges:
            a0, a1 = _normalize_interval(e.a0, e.a1)
            cuts.extend([a0, a1])
        cuts = sorted({round(x, 6) for x in cuts})
        for i in range(len(cuts) - 1):
            s0, s1 = cuts[i], cuts[i + 1]
            if s1 - s0 <= EPS:
                continue
            mid = (s0 + s1) / 2.0
            covering = [
                e for e in edges
                if _normalize_interval(e.a0, e.a1)[0] - EPS <= mid <= _normalize_interval(e.a0, e.a1)[1] + EPS
            ]
            if not covering:
                continue
            unique_rooms = tuple(sorted({e.room_id for e in covering}))
            if len(unique_rooms) >= 2:
                etype = 'Innenwand'
                color_meta = 'auto_shared'
            else:
                etype = 'Aussenwand'
                color_meta = 'auto_contour'
            owner = next((e for e in covering if e.room_id == unique_rooms[0]), covering[0])
            uid = _edge_span_uid(owner.floor, orient, owner.c, s0, s1, etype)
            meta = build_edge_span_meta(kind=color_meta, room_ids=unique_rooms, orient=orient, c=owner.c, a0=s0, a1=s1, uid=uid)
            if etype == 'Innenwand':
                meta = meta + '|nolabel'
            spans.append(
                EdgeSpan(
                    orient=orient, c=float(owner.c), a0=float(s0), a1=float(s1),
                    floor=owner.floor, room_ids=unique_rooms, owner_room_id=owner.room_id,
                    height_m=max(e.height_m for e in covering), element_type=etype, meta=meta, uid=uid,
                )
            )
    return spans


def edge_span_to_element(span: EdgeSpan) -> ElementModel:
    (x0, y0), (x1, y1) = span.endpoints()
    length = span.length_m
    area = length * float(span.height_m)
    u = DEFAULT_U['Innenwand'] if span.element_type == 'Innenwand' else DEFAULT_U.get('Aussenwand', 0.5)
    factor = DEFAULT_FACTOR['Innenwand'] if span.element_type == 'Innenwand' else DEFAULT_FACTOR.get('Aussenwand', 1.0)
    return ElementModel(
        room_id=span.owner_room_id, element_type=span.element_type, area_m2=area, u_w_m2k=u, factor=factor, floor=span.floor,
        x0_m=x0, y0_m=y0, x1_m=x1, y1_m=y1, length_m=length, height_m=float(span.height_m), uid=span.uid, meta=span.meta
    )


def build_auto_walls_shared_merge(rooms: List[RoomModel]) -> List[ElementModel]:
    return [edge_span_to_element(span) for span in classify_floor_edge_spans(rooms)]


def nearest_edge_span_for_point(rooms: List[RoomModel], floor: str, x_m: float, y_m: float, *, prefer_outer: bool = True, max_dist: Optional[float] = None, room_id: Optional[str] = None) -> Optional[EdgeSpan]:
    spans = [s for s in classify_floor_edge_spans(rooms) if s.floor == floor]
    if room_id:
        spans = [s for s in spans if room_id in s.room_ids]
    if prefer_outer:
        outer = [s for s in spans if s.element_type == 'Aussenwand']
        if outer:
            spans = outer
    best: Optional[EdgeSpan] = None
    best_d = 1e99
    for s in spans:
        d = _dist_point_to_axis_segment(float(x_m), float(y_m), s.orient, float(s.c), float(s.a0), float(s.a1))
        if prefer_outer and s.element_type == 'Aussenwand':
            d *= 0.8
        if d < best_d:
            best_d = d
            best = s
    if best is None:
        return None
    if max_dist is not None and best_d > float(max_dist):
        return None
    return best



def room_polygon(room: RoomModel) -> list[tuple[float, float]]:
    try:
        room.ensure_polygon()
    except Exception:
        pass
    pts = parse_polygon_m(getattr(room, "polygon_m", None))
    if len(pts) >= 3:
        return pts
    return rect_to_polygon(room.x_m, room.y_m, room.w_m, room.h_m)


def _grid_range(a0: float, a1: float, step: float = 0.05) -> range:
    i0 = int(round(min(a0, a1) / step))
    i1 = int(round(max(a0, a1) / step))
    return range(i0, i1)


def polygon_to_grid_cells(points: list[tuple[float, float]], step: float = 0.05) -> set[tuple[int, int]]:
    pts = simplify_orthogonal_polygon(points)
    if len(pts) < 3:
        return set()
    xs = sorted({round(float(x), 6) for x, _ in pts})
    ys = sorted({round(float(y), 6) for _, y in pts})
    cells: set[tuple[int, int]] = set()
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        if abs(y0 - y1) <= 1e-9:
            for gx in _grid_range(x0, x1, step):
                gy = int(round(y0 / step))
                # horizontal edges are handled by scanline later
                pass
    if not xs or not ys:
        return cells
    min_x = int(round(min(xs) / step))
    max_x = int(round(max(xs) / step))
    min_y = int(round(min(ys) / step))
    max_y = int(round(max(ys) / step))
    n = len(pts)
    for gx in range(min_x, max_x):
        cx = (gx + 0.5) * step
        for gy in range(min_y, max_y):
            cy = (gy + 0.5) * step
            inside = False
            j = n - 1
            for i in range(n):
                xi, yi = pts[i]
                xj, yj = pts[j]
                if ((yi > cy) != (yj > cy)) and (cx < (xj - xi) * (cy - yi) / ((yj - yi) or 1e-12) + xi):
                    inside = not inside
                j = i
            if inside:
                cells.add((gx, gy))
    return cells


def _cells_boundary_edges(cells: set[tuple[int, int]], step: float = 0.05) -> list[tuple[tuple[float,float], tuple[float,float]]]:
    edges=[]
    for gx, gy in cells:
        x0 = gx * step; y0 = gy * step; x1 = x0 + step; y1 = y0 + step
        if (gx, gy - 1) not in cells:
            edges.append(((x0, y0), (x1, y0)))
        if (gx + 1, gy) not in cells:
            edges.append(((x1, y0), (x1, y1)))
        if (gx, gy + 1) not in cells:
            edges.append(((x1, y1), (x0, y1)))
        if (gx - 1, gy) not in cells:
            edges.append(((x0, y1), (x0, y0)))
    return edges


def cells_to_orthogonal_polygon(cells: set[tuple[int, int]], step: float = 0.05) -> list[tuple[float, float]]:
    if not cells:
        return []
    edges = _cells_boundary_edges(cells, step=step)
    adjacency: dict[tuple[float,float], list[tuple[float,float]]] = {}
    for a, b in edges:
        adjacency.setdefault(a, []).append(b)
    start = min(adjacency.keys(), key=lambda p: (p[1], p[0]))
    poly = [start]
    current = start
    prev = None
    limit = max(20, len(edges) * 3)
    for _ in range(limit):
        options = adjacency.get(current, [])
        if not options:
            break
        if prev is None:
            def key_first(p):
                dx = p[0] - current[0]; dy = p[1] - current[1]
                return (0 if dx > 0 else 1 if dy > 0 else 2 if dx < 0 else 3, abs(dx) + abs(dy))
            nxt = sorted(options, key=key_first)[0]
        else:
            candidates = [p for p in options if p != prev] or options
            def turn_key(p):
                vx = current[0] - prev[0]; vy = current[1] - prev[1]
                nx = p[0] - current[0]; ny = p[1] - current[1]
                cross = vx * ny - vy * nx
                straight = (vx == nx and vy == ny)
                return (0 if cross > 0 else 1 if straight else 2, abs(nx) + abs(ny))
            nxt = sorted(candidates, key=turn_key)[0]
        prev, current = current, nxt
        if current == start:
            break
        poly.append(current)
    return simplify_orthogonal_polygon(poly)


def merge_room_polygons(polygons: list[list[tuple[float, float]]], step: float = 0.05) -> list[tuple[float, float]]:
    cells: set[tuple[int, int]] = set()
    for poly in polygons:
        cells |= polygon_to_grid_cells(poly, step=step)
    return cells_to_orthogonal_polygon(cells, step=step)


def subtract_room_polygons(base_polygon: list[tuple[float, float]], cut_polygons: list[list[tuple[float, float]]], step: float = 0.05) -> list[tuple[float, float]]:
    cells = polygon_to_grid_cells(base_polygon, step=step)
    for poly in cut_polygons:
        cells -= polygon_to_grid_cells(poly, step=step)
    return cells_to_orthogonal_polygon(cells, step=step)


def split_room_polygon(points: list[tuple[float, float]], orientation: str, coord: float, step: float = 0.05) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    cells = polygon_to_grid_cells(points, step=step)
    if orientation.lower().startswith('v'):
        g = int(round(coord / step))
        a = {c for c in cells if c[0] < g}
        b = {c for c in cells if c[0] >= g}
    else:
        g = int(round(coord / step))
        a = {c for c in cells if c[1] < g}
        b = {c for c in cells if c[1] >= g}
    return cells_to_orthogonal_polygon(a, step=step), cells_to_orthogonal_polygon(b, step=step)
