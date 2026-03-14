from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from ..core.polygon_ops import (
    parse_polygon_m,
    polygon_area,
    polygon_bbox,
    polygon_perimeter,
    rect_to_polygon,
    serialize_polygon_m,
    translate_polygon,
)


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
        self.ensure_polygon()
        self.normalize_polygon_bbox()
        self.recompute_volume()

    def polygon_points(self) -> list[tuple[float, float]]:
        return parse_polygon_m(self.polygon_m)

    def has_polygon(self) -> bool:
        return len(self.polygon_points()) >= 3

    def ensure_polygon(self) -> None:
        pts = self.polygon_points()
        if len(pts) >= 3:
            self.polygon_m = serialize_polygon_m(pts)
            return
        self.polygon_m = serialize_polygon_m(
            rect_to_polygon(self.x_m, self.y_m, self.w_m, self.h_m)
        )

    def set_polygon_points(self, pts: list[tuple[float, float]]) -> None:
        self.polygon_m = serialize_polygon_m(pts) if pts else None
        self.ensure_polygon()
        self.normalize_polygon_bbox()
        self.recompute_volume()

    def translate_polygon_to(self, x_m: float, y_m: float) -> None:
        self.ensure_polygon()
        pts = self.polygon_points()
        min_x, min_y, _, _ = polygon_bbox(pts)
        dx = float(x_m) - float(min_x)
        dy = float(y_m) - float(min_y)
        moved = translate_polygon(pts, dx, dy)
        self.set_polygon_points(moved)

    def bbox_tuple(self) -> tuple[float, float, float, float]:
        self.normalize_polygon_bbox()
        return self.x_m, self.y_m, self.w_m, self.h_m

    def move_by(self, dx_m: float, dy_m: float) -> None:
        self.ensure_polygon()
        pts = self.polygon_points()
        moved = translate_polygon(pts, float(dx_m), float(dy_m))
        self.set_polygon_points(moved)

    def move_to(self, x_m: float, y_m: float) -> None:
        self.translate_polygon_to(x_m, y_m)

    def normalize_polygon_bbox(self) -> None:
        self.ensure_polygon()
        pts = self.polygon_points()
        if len(pts) < 3:
            return
        x0, y0, x1, y1 = polygon_bbox(pts)
        self.x_m = x0
        self.y_m = y0
        self.w_m = x1 - x0
        self.h_m = y1 - y0

    def is_axis_aligned_rect_polygon(self, eps: float = 1e-9) -> bool:
        pts = self.polygon_points()
        if len(pts) != 4:
            return False
        x0, y0, x1, y1 = polygon_bbox(pts)
        target = {
            (round(x0, 9), round(y0, 9)),
            (round(x1, 9), round(y0, 9)),
            (round(x1, 9), round(y1, 9)),
            (round(x0, 9), round(y1, 9)),
        }
        got = {(round(x, 9), round(y, 9)) for x, y in pts}
        return got == target and abs(x1 - x0) > eps and abs(y1 - y0) > eps

    def resize_rect_polygon_from_bbox(self, x_m: float, y_m: float, w_m: float, h_m: float) -> None:
        self.polygon_m = serialize_polygon_m(rect_to_polygon(x_m, y_m, w_m, h_m))
        self.ensure_polygon()
        self.normalize_polygon_bbox()
        self.recompute_volume()

    def area_m2(self) -> float:
        pts = self.polygon_points()
        if len(pts) >= 3:
            return polygon_area(pts)
        return max(self.w_m, 0.0) * max(self.h_m, 0.0)

    def perimeter_m(self) -> float:
        pts = self.polygon_points()
        if len(pts) >= 3:
            return polygon_perimeter(pts)
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
