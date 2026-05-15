from __future__ import annotations

from math import hypot
from typing import Iterable

from .polygon_ops import simplify_orthogonal_polygon


Point2D = tuple[float, float]
Point3D = tuple[float, float, float]


def _point_in_polygon(x: float, y: float, points: list[Point2D]) -> bool:
    inside = False
    n = len(points)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = points[i]
        xj, yj = points[j]
        crosses = ((yi > y) != (yj > y))
        if crosses:
            x_cross = (xj - xi) * (y - yi) / max((yj - yi), 1e-12) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    abx = bx - ax
    aby = by - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        return hypot(px - ax, py - ay)
    t = ((px - ax) * abx + (py - ay) * aby) / denom
    t = max(0.0, min(1.0, t))
    qx = ax + t * abx
    qy = ay + t * aby
    return hypot(px - qx, py - qy)


def point_to_polygon_boundary_distance(x: float, y: float, points: list[Point2D]) -> float:
    n = len(points)
    if n < 2:
        return 0.0
    return min(
        _point_segment_distance(x, y, points[i][0], points[i][1], points[(i + 1) % n][0], points[(i + 1) % n][1])
        for i in range(n)
    )


def build_winkeldach_mesh(
    points: Iterable[Point2D],
    *,
    z_top: float,
    peak_height_m: float,
    target_cells: int = 24,
) -> tuple[list[list[Point3D]], list[list[Point3D]]]:
    """Create a simple roof mesh for orthogonal L-/angle-shaped footprints.

    The roof height is derived from the distance to the outer polygon boundary.
    This produces ridges and valleys for concave footprints without requiring
    full straight-skeleton construction. It is intended for stable preview/3D
    visualization, not as a normative geometry kernel.
    """
    pts = simplify_orthogonal_polygon(list(points or []))
    if len(pts) < 4:
        return [], []
    xs = [float(x) for x, _ in pts]
    ys = [float(y) for _, y in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(1e-9, max_x - min_x)
    span_y = max(1e-9, max_y - min_y)
    nx = max(8, min(48, int(target_cells * span_x / max(span_x, span_y))))
    ny = max(8, min(48, int(target_cells * span_y / max(span_x, span_y))))
    dx = span_x / max(nx, 1)
    dy = span_y / max(ny, 1)

    inside_samples: list[tuple[float, float, float]] = []
    for ix in range(nx):
        cx = min_x + (ix + 0.5) * dx
        for iy in range(ny):
            cy = min_y + (iy + 0.5) * dy
            if _point_in_polygon(cx, cy, pts):
                dist = point_to_polygon_boundary_distance(cx, cy, pts)
                inside_samples.append((cx, cy, dist))
    if not inside_samples:
        return [], []
    max_dist = max(d for _, _, d in inside_samples)
    max_dist = max(max_dist, min(dx, dy) * 0.5, 1e-6)

    def z_at(x: float, y: float) -> float:
        if not _point_in_polygon(x, y, pts):
            return z_top
        d = point_to_polygon_boundary_distance(x, y, pts)
        return z_top + peak_height_m * max(0.0, min(1.0, d / max_dist))

    faces: list[list[Point3D]] = []
    for ix in range(nx):
        x0 = min_x + ix * dx
        x1 = min_x + (ix + 1) * dx
        cx = 0.5 * (x0 + x1)
        for iy in range(ny):
            y0 = min_y + iy * dy
            y1 = min_y + (iy + 1) * dy
            cy = 0.5 * (y0 + y1)
            if not _point_in_polygon(cx, cy, pts):
                continue
            face = [
                (x0, y0, z_at(x0, y0)),
                (x1, y0, z_at(x1, y0)),
                (x1, y1, z_at(x1, y1)),
                (x0, y1, z_at(x0, y1)),
            ]
            faces.append(face)

    # simple feature lines: connect local maxima samples for visual ridge/valley hints
    lines: list[list[Point3D]] = []
    tol = 0.12 * peak_height_m if peak_height_m > 0 else 0.02
    ridge_pts = [(x, y, z_top + peak_height_m * d / max_dist) for x, y, d in inside_samples if (max_dist - d) <= max(1e-6, tol)]
    ridge_pts.sort(key=lambda p: (round(p[0], 3), round(p[1], 3)))
    for i in range(len(ridge_pts) - 1):
        a = ridge_pts[i]
        b = ridge_pts[i + 1]
        if hypot(a[0] - b[0], a[1] - b[1]) <= max(dx, dy) * 1.6:
            lines.append([a, b])
    return faces, lines
