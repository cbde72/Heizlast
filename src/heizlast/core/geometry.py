from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple
from ..domain.models import ElementModel, RoomModel
from .config import DEFAULT_U, DEFAULT_FACTOR

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


def parse_polygon_m(poly: str | None) -> list[tuple[float, float]]:
    if not poly:
        return []
    out: list[tuple[float, float]] = []
    for part in str(poly).replace(';', '|').split('|'):
        part = part.strip()
        if not part or ',' not in part:
            continue
        xs, ys = part.split(',', 1)
        try:
            out.append((float(xs.strip()), float(ys.strip())))
        except Exception:
            pass
    return out


def serialize_polygon_m(points: list[tuple[float, float]]) -> str:
    return '|'.join(f"{float(x):.3f},{float(y):.3f}" for x, y in points)




def deserialize_polygon_m(text: str | None) -> list[tuple[float, float]]:
    return parse_polygon_m(text)


def _point_eq(a: tuple[float, float], b: tuple[float, float], eps: float = 1e-9) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def simplify_orthogonal_polygon(points: list[tuple[float, float]], eps: float = 1e-9) -> list[tuple[float, float]]:
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


def validate_orthogonal_polygon(points: list[tuple[float, float]], eps: float = 1e-9) -> bool:
    pts = simplify_orthogonal_polygon(points, eps=eps)
    if len(pts) < 4:
        return False
    if not _polygon_is_axis_aligned(pts, eps=eps):
        return False
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    if abs(area) <= 1e-6:
        return False
    if _polygon_self_intersects(pts, eps=eps):
        return False
    return True


def move_polygon_edge(points: list[tuple[float, float]], idx: int, new_coord: float, snap: float = 0.05) -> list[tuple[float, float]]:
    pts = list(points or [])
    n = len(pts)
    if n < 3 or idx < 0 or idx >= n:
        return pts

    def snap_m(v: float) -> float:
        return round(v / snap) * snap if snap > 0 else v

    next_idx = (idx + 1) % n
    x0, y0 = pts[idx]
    x1, y1 = pts[next_idx]
    if abs(y0 - y1) <= 1e-9:
        y = snap_m(float(new_coord))
        pts[idx] = (x0, y)
        pts[next_idx] = (x1, y)
    elif abs(x0 - x1) <= 1e-9:
        x = snap_m(float(new_coord))
        pts[idx] = (x, y0)
        pts[next_idx] = (x, y1)
    return pts

def polygon_bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def translate_polygon(points: list[tuple[float, float]], dx: float, dy: float) -> list[tuple[float, float]]:
    return [(float(x) + float(dx), float(y) + float(dy)) for x, y in points]


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
    pts = room.polygon_points() if hasattr(room, 'polygon_points') else []
    if len(pts) >= 3:
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
    x0 = room.x_m; y0 = room.y_m; x1 = room.x_m + room.w_m; y1 = room.y_m + room.h_m
    a = min(x0, x1); b = max(x0, x1)
    c = min(y0, y1); d = max(y0, y1)
    return [
        Edge('H', c, a, b, room.id, room.floor, room.height_m),
        Edge('H', d, a, b, room.id, room.floor, room.height_m),
        Edge('V', a, c, d, room.id, room.floor, room.height_m),
        Edge('V', b, c, d, room.id, room.floor, room.height_m),
    ]

def _key(orient: str, c: float, tol: float=1e-6) -> Tuple[str, int]:
    return (orient, int(round(c / tol)))

def _normalize_interval(a0: float, a1: float) -> Tuple[float,float]:
    return (a0, a1) if a0 <= a1 else (a1, a0)

def build_auto_walls_shared_merge(rooms: List[RoomModel]) -> List[ElementModel]:
    groups: Dict[Tuple[str,int], List[Edge]] = {}
    for r in rooms:
        for e in room_edges(r):
            groups.setdefault(_key(e.orient, e.c), []).append(e)
    elements: List[ElementModel] = []
    uid_counter = 0
    for (orient, _), edges in groups.items():
        cuts: List[float] = []
        for e in edges:
            a0, a1 = _normalize_interval(e.a0, e.a1)
            cuts.extend([a0, a1])
        cuts = sorted({round(x, 6) for x in cuts})
        for i in range(len(cuts) - 1):
            s0, s1 = cuts[i], cuts[i+1]
            if s1 - s0 <= EPS:
                continue
            mid = (s0 + s1) / 2.0
            covering = [e for e in edges if _normalize_interval(e.a0, e.a1)[0] - EPS <= mid <= _normalize_interval(e.a0, e.a1)[1] + EPS]
            if not covering:
                continue
            unique_rooms = {e.room_id for e in covering}
            if len(unique_rooms) >= 2:
                etype = 'Innenwand'; u = DEFAULT_U['Innenwand']; factor = DEFAULT_FACTOR['Innenwand']; color_meta = 'auto_shared|nolabel'
            else:
                etype = 'Aussenwand'; u = DEFAULT_U.get('Aussenwand', 0.5); factor = DEFAULT_FACTOR.get('Aussenwand', 1.0); color_meta = 'auto_contour'
            owner = covering[0]
            involved = ','.join(sorted(unique_rooms))
            meta = f"{color_meta}|rooms={involved}|line={orient}:{owner.c:.3f}"
            uid_counter += 1
            if orient == 'H':
                x0, y0 = s0, owner.c; x1, y1 = s1, owner.c; length = abs(s1 - s0)
            else:
                x0, y0 = owner.c, s0; x1, y1 = owner.c, s1; length = abs(s1 - s0)
            height = max(e.height_m for e in covering)
            area = length * height
            el = ElementModel(room_id=owner.room_id, element_type=etype, area_m2=area, u_w_m2k=u, factor=factor, floor=owner.floor,
                              x0_m=x0, y0_m=y0, x1_m=x1, y1_m=y1, length_m=length, height_m=height,
                              uid=f"auto_{etype}_{uid_counter}", meta=meta)
            elements.append(el)
    return elements


def rect_to_polygon(x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
    x0 = float(x); y0 = float(y); x1 = x0 + float(w); y1 = y0 + float(h)
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def room_polygon(room: RoomModel) -> list[tuple[float, float]]:
    pts = room.polygon_points() if hasattr(room, 'polygon_points') else []
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
