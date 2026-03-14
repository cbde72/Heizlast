from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


def _parse_polygon_string(poly: Optional[str]) -> list[tuple[float, float]]:
    if not poly:
        return []
    out: list[tuple[float, float]] = []
    for part in str(poly).replace(';', '|').split('|'):
        part = part.strip()
        if not part or ',' not in part:
            continue
        xs, ys = part.split(',', 1)
        try:
            out.append((float(xs.strip().replace(',', '.')), float(ys.strip().replace(',', '.'))))
        except Exception:
            pass
    return out


def _polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    s = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def _polygon_perimeter(points: list[tuple[float, float]]) -> float:
    import math
    if len(points) < 2:
        return 0.0
    s = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += math.hypot(x2 - x1, y2 - y1)
    return s


@dataclass
class RoomModel:
    id: str
    floor: str  # EG/DG
    name: str
    x_m: float
    y_m: float
    w_m: float
    h_m: float
    height_m: float = 2.50
    t_inside_c: float = 20.0
    air_change_1ph: float = 0.5
    usage_type: Optional[str] = None
    volume_m3: float = 0.0
    polygon_m: Optional[str] = None

    def __post_init__(self):
        self.normalize_polygon_bbox()
        self.recompute_volume()

    def polygon_points(self) -> list[tuple[float, float]]:
        return _parse_polygon_string(self.polygon_m)

    def has_polygon(self) -> bool:
        return len(self.polygon_points()) >= 3

    def set_polygon_points(self, pts: list[tuple[float, float]]) -> None:
        if pts and pts[0] == pts[-1]:
            pts = pts[:-1]
        self.polygon_m = '|'.join(f"{float(x):.3f},{float(y):.3f}" for x, y in pts) if pts else None
        self.normalize_polygon_bbox()
        self.recompute_volume()

    def translate_polygon_to(self, x_m: float, y_m: float) -> None:
        pts = self.polygon_points()
        if not pts:
            self.x_m = x_m
            self.y_m = y_m
            return
        min_x = min(x for x, _ in pts)
        min_y = min(y for _, y in pts)
        dx = float(x_m) - float(min_x)
        dy = float(y_m) - float(min_y)
        moved = [(x + dx, y + dy) for x, y in pts]
        self.set_polygon_points(moved)

    def normalize_polygon_bbox(self) -> None:
        pts = self.polygon_points()
        if len(pts) < 3:
            return
        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        self.x_m = min(xs)
        self.y_m = min(ys)
        self.w_m = max(xs) - min(xs)
        self.h_m = max(ys) - min(ys)

    def area_m2(self) -> float:
        pts = self.polygon_points()
        if len(pts) >= 3:
            return _polygon_area(pts)
        return max(self.w_m, 0.0) * max(self.h_m, 0.0)

    def perimeter_m(self) -> float:
        pts = self.polygon_points()
        if len(pts) >= 3:
            return _polygon_perimeter(pts)
        return 2.0 * (max(self.w_m, 0.0) + max(self.h_m, 0.0))

    def recompute_volume(self) -> None:
        self.volume_m3 = self.area_m2() * max(self.height_m, 0.0)

@dataclass
class ElementModel:
    room_id: str
    element_type: str
    area_m2: float
    u_w_m2k: float
    factor: float = 1.0

    floor: Optional[str] = None
    x0_m: Optional[float] = None
    y0_m: Optional[float] = None
    x1_m: Optional[float] = None
    y1_m: Optional[float] = None

    length_m: Optional[float] = None
    height_m: Optional[float] = None

    label_x_m: Optional[float] = None
    label_y_m: Optional[float] = None

    uid: Optional[str] = None
    meta: Optional[str] = None

    def has_geometry(self) -> bool:
        return None not in (self.x0_m, self.y0_m, self.x1_m, self.y1_m)

    def compute_length(self) -> Optional[float]:
        if not self.has_geometry():
            return None
        import math
        return math.hypot(self.x1_m - self.x0_m, self.y1_m - self.y0_m)
