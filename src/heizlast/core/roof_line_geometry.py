from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Callable, Iterable, Sequence

try:
    from shapely.geometry import GeometryCollection, LineString, Point, Polygon
    from shapely.ops import split as shapely_split
except Exception:  # pragma: no cover
    GeometryCollection = None
    LineString = None
    Polygon = None
    shapely_split = None


@dataclass(frozen=True)
class RoofFacet:
    label: str
    polygon_m: tuple[tuple[float, float], ...]
    plan_area_m2: float
    surface_area_m2: float
    boundary_kinds: tuple[str, ...] = ()


def clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def normalized_roof_lines(lines: Iterable[object]) -> list[tuple[str, float, float, float, float]]:
    out: list[tuple[str, float, float, float, float]] = []
    for line in list(lines or []):
        try:
            kind = str(getattr(line, "kind", "first") or "first").strip().lower()
            if kind not in {"first", "grat", "kehle"}:
                kind = "first"
            x1 = clamp01(getattr(line, "x1_ratio", 0.0))
            y1 = clamp01(getattr(line, "y1_ratio", 0.0))
            x2 = clamp01(getattr(line, "x2_ratio", 1.0))
            y2 = clamp01(getattr(line, "y2_ratio", 1.0))
            out.append((kind, x1, y1, x2, y2))
        except Exception:
            continue
    return out


def roof_lines_to_plan_segments(
    lines: Iterable[object],
    *,
    x0_m: float,
    y0_m: float,
    width_m: float,
    length_m: float,
) -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    segs: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
    for kind, x1r, y1r, x2r, y2r in normalized_roof_lines(lines):
        p1 = (float(x0_m) + float(width_m) * x1r, float(y0_m) + float(length_m) * y1r)
        p2 = (float(x0_m) + float(width_m) * x2r, float(y0_m) + float(length_m) * y2r)
        segs.append((kind, p1, p2))
    return segs


def roof_line_length_m(kind: str, p1: tuple[float, float], p2: tuple[float, float]) -> float:
    scale = {"first": 1.00, "grat": 1.12, "kehle": 1.18}.get(str(kind).strip().lower(), 1.00)
    return hypot(float(p2[0]) - float(p1[0]), float(p2[1]) - float(p1[1])) * scale


def estimate_roof_line_extra_area_m2(
    lines: Iterable[object],
    *,
    width_m: float,
    length_m: float,
    rise_m: float,
) -> float:
    width_m = max(1e-9, float(width_m))
    length_m = max(1e-9, float(length_m))
    rise_m = max(0.0, float(rise_m))
    segs = roof_lines_to_plan_segments(lines, x0_m=0.0, y0_m=0.0, width_m=width_m, length_m=length_m)
    extra = 0.0
    for kind, p1, p2 in segs:
        length = roof_line_length_m(kind, p1, p2)
        gain = {"first": 0.08, "grat": 0.18, "kehle": 0.22}.get(kind, 0.08)
        extra += gain * length * max(0.10, 0.60 * rise_m)
    return float(extra)


def split_plan_polygon_by_segments(
    polygon_pts: Sequence[tuple[float, float]],
    segments: Sequence[tuple[str, tuple[float, float], tuple[float, float]]],
    *,
    min_area_m2: float = 1e-6,
) -> list[tuple[tuple[float, float], ...]]:
    if Polygon is None or shapely_split is None or len(polygon_pts) < 3:
        return [tuple((float(x), float(y)) for x, y in polygon_pts)] if polygon_pts else []

    poly = Polygon([(float(x), float(y)) for x, y in polygon_pts])
    if poly.is_empty or poly.area <= min_area_m2:
        return []

    parts = [poly]
    boundary = poly.boundary
    for _kind, p1, p2 in list(segments or []):
        if hypot(float(p2[0]) - float(p1[0]), float(p2[1]) - float(p1[1])) <= 1e-9:
            continue
        ep1 = Point(float(p1[0]), float(p1[1]))
        ep2 = Point(float(p2[0]), float(p2[1]))
        on_b1 = boundary.distance(ep1) <= 1e-7
        on_b2 = boundary.distance(ep2) <= 1e-7
        if on_b1 ^ on_b2:
            cutter = LineString([p1, p2])
        elif (not on_b1) and (not on_b2):
            dx = float(p2[0]) - float(p1[0])
            dy = float(p2[1]) - float(p1[1])
            norm = max(1e-9, (dx * dx + dy * dy) ** 0.5)
            scale = max(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1], 1.0) * 3.0
            ux = dx / norm
            uy = dy / norm
            cutter = LineString([(float(p1[0]) - ux * scale, float(p1[1]) - uy * scale), (float(p2[0]) + ux * scale, float(p2[1]) + uy * scale)])
        else:
            cutter = LineString([p1, p2])
        new_parts = []
        for part in parts:
            try:
                if not part.intersects(cutter):
                    new_parts.append(part)
                    continue
                res = shapely_split(part, cutter)
                geoms = list(getattr(res, "geoms", [res]))
                polys = [g for g in geoms if getattr(g, "geom_type", "") == "Polygon" and float(getattr(g, "area", 0.0) or 0.0) > min_area_m2]
                new_parts.extend(polys or [part])
            except Exception:
                new_parts.append(part)
        parts = new_parts or parts

    out: list[tuple[tuple[float, float], ...]] = []
    for part in parts:
        try:
            coords = list(part.exterior.coords)
        except Exception:
            continue
        if len(coords) < 4:
            continue
        pts = tuple((float(x), float(y)) for x, y in coords[:-1])
        if polygon_area_m2(pts) > min_area_m2:
            out.append(pts)
    out.sort(key=lambda pts: (-polygon_area_m2(pts), polygon_centroid(pts)[1], polygon_centroid(pts)[0]))
    return out or [tuple((float(x), float(y)) for x, y in polygon_pts)]


def polygon_area_m2(pts: Sequence[tuple[float, float]]) -> float:
    if len(pts) < 3:
        return 0.0
    area2 = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        area2 += float(x0) * float(y1) - float(x1) * float(y0)
    return abs(area2) * 0.5


def polygon_centroid(pts: Sequence[tuple[float, float]]) -> tuple[float, float]:
    if len(pts) < 3:
        if not pts:
            return (0.0, 0.0)
        sx = sum(float(x) for x, _ in pts)
        sy = sum(float(y) for _, y in pts)
        return (sx / len(pts), sy / len(pts))
    a2 = 0.0
    cx = 0.0
    cy = 0.0
    ring = list(pts)
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        cross = float(x0) * float(y1) - float(x1) * float(y0)
        a2 += cross
        cx += (float(x0) + float(x1)) * cross
        cy += (float(y0) + float(y1)) * cross
    if abs(a2) <= 1e-12:
        sx = sum(float(x) for x, _ in pts)
        sy = sum(float(y) for _, y in pts)
        return (sx / len(pts), sy / len(pts))
    return (cx / (3.0 * a2), cy / (3.0 * a2))


def triangle_area_3d(a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> float:
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cx = ab[1] * ac[2] - ab[2] * ac[1]
    cy = ab[2] * ac[0] - ab[0] * ac[2]
    cz = ab[0] * ac[1] - ab[1] * ac[0]
    return 0.5 * (cx * cx + cy * cy + cz * cz) ** 0.5


def polygon_surface_area_3d(
    pts: Sequence[tuple[float, float]],
    height_fn: Callable[[float, float], float],
    *,
    z_base: float = 0.0,
) -> float:
    if len(pts) < 3:
        return 0.0
    verts = [(float(x), float(y), float(z_base) + float(height_fn(float(x), float(y)))) for x, y in pts]
    area = 0.0
    a = verts[0]
    for i in range(1, len(verts) - 1):
        area += triangle_area_3d(a, verts[i], verts[i + 1])
    return float(area)


def facet_boundary_kinds(
    polygon_pts: Sequence[tuple[float, float]],
    segments: Sequence[tuple[str, tuple[float, float], tuple[float, float]]],
    *,
    tol_m: float = 1e-6,
) -> tuple[str, ...]:
    if LineString is None or Polygon is None:
        return ()
    try:
        boundary = Polygon(list(polygon_pts)).boundary
    except Exception:
        return ()
    kinds: list[str] = []
    for kind, p1, p2 in list(segments or []):
        try:
            line = LineString([p1, p2])
            inter = boundary.intersection(line)
            if not getattr(inter, "is_empty", True) and float(getattr(inter, "length", 0.0) or 0.0) > tol_m:
                kinds.append(str(kind))
        except Exception:
            continue
    return tuple(sorted(set(kinds)))


def build_roof_facets(
    polygon_pts: Sequence[tuple[float, float]],
    segments: Sequence[tuple[str, tuple[float, float], tuple[float, float]]],
    height_fn: Callable[[float, float], float],
    *,
    extra_area_total_m2: float = 0.0,
    label_prefix: str = "F",
) -> list[RoofFacet]:
    polys = split_plan_polygon_by_segments(polygon_pts, segments)
    if not polys:
        return []
    raw: list[dict] = []
    for idx, pts in enumerate(polys, start=1):
        plan_area = polygon_area_m2(pts)
        surface_area = polygon_surface_area_3d(pts, height_fn)
        kinds = facet_boundary_kinds(pts, segments)
        raw.append({
            "label": f"{label_prefix}{idx}",
            "polygon_m": pts,
            "plan_area_m2": plan_area,
            "surface_area_m2": surface_area,
            "boundary_kinds": kinds,
        })
    if extra_area_total_m2 > 1e-9:
        weights = []
        for item in raw:
            weight = 0.0
            for kind in item["boundary_kinds"]:
                weight += {"first": 0.08, "grat": 0.18, "kehle": 0.22}.get(kind, 0.08)
            weights.append(max(0.0, weight))
        total_w = sum(weights)
        if total_w <= 1e-12:
            weights = [item["plan_area_m2"] for item in raw]
            total_w = sum(weights)
        if total_w > 1e-12:
            for item, w in zip(raw, weights):
                item["surface_area_m2"] += float(extra_area_total_m2) * float(w) / float(total_w)
    return [RoofFacet(**item) for item in raw]
