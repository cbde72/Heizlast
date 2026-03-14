from __future__ import annotations

import math
from typing import Optional

EPS = 1e-9


def snap_m(x: float, step: float = 0.05) -> float:
    x = float(x)
    step = float(step)
    return round(x / step) * step if step > 0 else x


def _point_eq(a: tuple[float, float], b: tuple[float, float], eps: float = EPS) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def parse_polygon_m(poly: Optional[str]) -> list[tuple[float, float]]:
    if not poly:
        return []

    out: list[tuple[float, float]] = []
    for part in str(poly).replace(";", "|").split("|"):
        part = part.strip()
        if not part or "," not in part:
            continue
        xs, ys = part.split(",", 1)
        try:
            x = float(xs.strip().replace(",", "."))
            y = float(ys.strip().replace(",", "."))
            out.append((x, y))
        except Exception:
            pass
    return out


def serialize_polygon_m(points: list[tuple[float, float]]) -> str:
    pts = list(points or [])
    if pts and _point_eq(pts[0], pts[-1]):
        pts = pts[:-1]
    return "|".join(f"{float(x):.3f},{float(y):.3f}" for x, y in pts)


def deserialize_polygon_m(text: Optional[str]) -> list[tuple[float, float]]:
    return parse_polygon_m(text)


def rect_to_polygon(x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
    x = float(x)
    y = float(y)
    w = float(w)
    h = float(h)
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    s = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def polygon_perimeter(points: list[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    s = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += math.hypot(x2 - x1, y2 - y1)
    return s


def polygon_bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    if not points:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def translate_polygon(points: list[tuple[float, float]], dx: float, dy: float) -> list[tuple[float, float]]:
    dx = float(dx)
    dy = float(dy)
    return [(float(x) + dx, float(y) + dy) for x, y in points]


def simplify_orthogonal_polygon(points: list[tuple[float, float]], eps: float = EPS) -> list[tuple[float, float]]:
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


def is_axis_aligned_polygon(points: list[tuple[float, float]], eps: float = EPS) -> bool:
    if len(points) < 3:
        return False
    n = len(points)
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        if abs(x0 - x1) > eps and abs(y0 - y1) > eps:
            return False
    return True


def _segments_intersect(a1, a2, b1, b2, eps: float = EPS) -> bool:
    def orient(p, q, r):
        val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        if abs(val) <= eps:
            return 0
        return 1 if val > 0 else 2

    def on_seg(p, q, r):
        return (
            min(p[0], r[0]) - eps <= q[0] <= max(p[0], r[0]) + eps
            and min(p[1], r[1]) - eps <= q[1] <= max(p[1], r[1]) + eps
        )

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


def polygon_self_intersects(points: list[tuple[float, float]], eps: float = EPS) -> bool:
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


def validate_orthogonal_polygon(points: list[tuple[float, float]], eps: float = EPS) -> bool:
    pts = simplify_orthogonal_polygon(points, eps=eps)
    if len(pts) < 4:
        return False
    if not is_axis_aligned_polygon(pts, eps=eps):
        return False
    if abs(polygon_area(pts)) <= 1e-6:
        return False
    if polygon_self_intersects(pts, eps=eps):
        return False
    return True


def move_polygon_edge(
    points: list[tuple[float, float]],
    idx: int,
    new_coord: float,
    snap: float = 0.05,
) -> list[tuple[float, float]]:
    pts = list(points or [])
    n = len(pts)
    if n < 3 or idx < 0 or idx >= n:
        return pts

    next_idx = (idx + 1) % n
    x0, y0 = pts[idx]
    x1, y1 = pts[next_idx]

    if abs(y0 - y1) <= EPS:
        y = snap_m(float(new_coord), snap)
        pts[idx] = (x0, y)
        pts[next_idx] = (x1, y)
    elif abs(x0 - x1) <= EPS:
        x = snap_m(float(new_coord), snap)
        pts[idx] = (x, y0)
        pts[next_idx] = (x, y1)

    return pts
