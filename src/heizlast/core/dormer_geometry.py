from __future__ import annotations

from dataclasses import dataclass, field
from math import radians, sqrt, tan
from typing import Literal, Optional

DormerType = Literal["shed", "gable", "flat", "pointed"]
RoofSide = Literal["left", "right", "front", "back"]
RidgeDirection = Literal["length", "width"]


@dataclass(slots=True, frozen=True)
class Rect2D:
    x_m: float
    y_m: float
    width_m: float
    height_m: float

    @property
    def area_m2(self) -> float:
        return max(0.0, float(self.width_m)) * max(0.0, float(self.height_m))


@dataclass(slots=True, frozen=True)
class DormerInput:
    id: str
    dormer_type: DormerType
    roof_side: RoofSide
    center_along_m: float
    width_m: float
    depth_m: float
    front_height_m: float
    window_count: int = 1
    window_width_m: float = 1.20
    window_height_m: float = 1.20
    sill_height_m: float = 0.90
    roof_pitch_deg: Optional[float] = None
    min_edge_clearance_m: float = 0.40


@dataclass(slots=True, frozen=True)
class DormerAreas:
    cutout_main_roof_m2: float = 0.0
    front_wall_gross_m2: float = 0.0
    front_wall_net_m2: float = 0.0
    side_walls_gross_m2: float = 0.0
    side_walls_net_m2: float = 0.0
    dormer_roof_m2: float = 0.0
    window_area_m2: float = 0.0
    opaque_total_m2: float = 0.0
    envelope_total_m2: float = 0.0


@dataclass(slots=True, frozen=True)
class DormerPreviewGeometry:
    roof_plan_rect: Rect2D
    front_windows: list[Rect2D] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class DormerResult:
    input: DormerInput
    areas: DormerAreas
    preview: DormerPreviewGeometry
    ridge_length_m: float = 0.0
    rise_m: float = 0.0


@dataclass(slots=True, frozen=True)
class RoofContext:
    roof_type: str
    ridge_direction: RidgeDirection
    building_length_m: float
    building_width_m: float
    eaves_overhang_m: float = 0.0
    gable_overhang_m: float = 0.0
    roof_pitch_deg_left: float = 35.0
    roof_pitch_deg_right: float = 35.0

    @property
    def along_span_m(self) -> float:
        return float(self.building_length_m) if self.ridge_direction == "length" else float(self.building_width_m)

    @property
    def cross_span_m(self) -> float:
        return float(self.building_width_m) if self.ridge_direction == "length" else float(self.building_length_m)

    def active_roof_sides(self) -> tuple[str, str]:
        if self.ridge_direction == "length":
            return ("left", "right")
        return ("front", "back")


class DormerGeometry:
    def __init__(self, roof: RoofContext):
        self.roof = roof

    def validate(self, d: DormerInput) -> None:
        if d.width_m <= 0:
            raise ValueError("Gaubenbreite muss > 0 sein.")
        if d.depth_m <= 0:
            raise ValueError("Gaubentiefe muss > 0 sein.")
        if d.front_height_m <= 0:
            raise ValueError("Gaubenhöhe muss > 0 sein.")
        if d.window_count < 0:
            raise ValueError("window_count darf nicht negativ sein.")
        if d.window_width_m < 0 or d.window_height_m < 0:
            raise ValueError("Fenstermaße dürfen nicht negativ sein.")
        if d.roof_side not in self.roof.active_roof_sides():
            raise ValueError(f"Gaubenseite '{d.roof_side}' passt nicht zur Firstrichtung '{self.roof.ridge_direction}'.")

        half_width = d.width_m / 2.0
        left_edge = d.center_along_m - half_width
        right_edge = d.center_along_m + half_width
        usable_start = float(d.min_edge_clearance_m)
        usable_end = float(self.roof.along_span_m) - float(d.min_edge_clearance_m)
        if left_edge < usable_start or right_edge > usable_end:
            raise ValueError(
                f"Gaube '{d.id}' liegt zu nah am Dachrand (along-span={self.roof.along_span_m:.2f} m)."
            )

    def build(self, d: DormerInput) -> DormerResult:
        self.validate(d)
        if d.dormer_type == "flat":
            return self._build_flat_dormer(d)
        if d.dormer_type == "shed":
            return self._build_shed_dormer(d)
        if d.dormer_type == "gable":
            return self._build_gable_dormer(d)
        if d.dormer_type == "pointed":
            return self._build_pointed_dormer(d)
        raise ValueError(f"Unbekannter Gaubentyp: {d.dormer_type}")

    def _build_flat_dormer(self, d: DormerInput) -> DormerResult:
        window_area = d.window_count * d.window_width_m * d.window_height_m
        front_gross = d.width_m * d.front_height_m
        front_net = max(0.0, front_gross - window_area)
        side_each = d.depth_m * d.front_height_m
        side_gross = 2.0 * side_each
        roof_area = d.width_m * d.depth_m
        cutout_area = d.width_m * d.depth_m
        return self._build_result(d, window_area, front_gross, front_net, side_gross, roof_area, cutout_area, ridge_length_m=d.width_m, rise_m=0.0)

    def _build_shed_dormer(self, d: DormerInput) -> DormerResult:
        pitch_deg = float(d.roof_pitch_deg if d.roof_pitch_deg is not None else 15.0)
        rise = d.depth_m * tan(radians(pitch_deg))
        window_area = d.window_count * d.window_width_m * d.window_height_m
        front_gross = d.width_m * d.front_height_m
        front_net = max(0.0, front_gross - window_area)
        mean_side_height = d.front_height_m + 0.5 * rise
        side_gross = 2.0 * d.depth_m * mean_side_height
        roof_slope_len = sqrt(d.depth_m ** 2 + rise ** 2)
        roof_area = d.width_m * roof_slope_len
        cutout_area = d.width_m * roof_slope_len
        return self._build_result(d, window_area, front_gross, front_net, side_gross, roof_area, cutout_area, ridge_length_m=d.width_m, rise_m=rise)

    def _build_gable_dormer(self, d: DormerInput) -> DormerResult:
        pitch_deg = float(d.roof_pitch_deg if d.roof_pitch_deg is not None else 35.0)
        half_width = d.width_m / 2.0
        rise = tan(radians(pitch_deg)) * half_width
        window_area = d.window_count * d.window_width_m * d.window_height_m
        front_rect = d.width_m * d.front_height_m
        front_gable = 0.5 * d.width_m * rise
        front_gross = front_rect + front_gable
        front_net = max(0.0, front_gross - window_area)
        side_gross = 2.0 * d.depth_m * d.front_height_m
        roof_slope_len = sqrt(half_width ** 2 + rise ** 2)
        roof_area = 2.0 * d.depth_m * roof_slope_len
        cutout_area = d.width_m * d.depth_m
        return self._build_result(d, window_area, front_gross, front_net, side_gross, roof_area, cutout_area, ridge_length_m=d.depth_m, rise_m=rise)

    def _build_pointed_dormer(self, d: DormerInput) -> DormerResult:
        height = float(d.front_height_m)
        half_width = float(d.width_m) / 2.0
        window_area = d.window_count * d.window_width_m * d.window_height_m
        front_gross = 0.5 * d.width_m * height
        front_net = max(0.0, front_gross - window_area)
        side_gross = d.depth_m * height
        roof_slope_len = sqrt(half_width ** 2 + height ** 2)
        roof_area = d.depth_m * roof_slope_len
        cutout_area = 0.5 * d.width_m * d.depth_m
        return self._build_result(d, window_area, front_gross, front_net, side_gross, roof_area, cutout_area, ridge_length_m=d.depth_m, rise_m=height)

    def _build_result(self, d: DormerInput, window_area: float, front_gross: float, front_net: float, side_gross: float, roof_area: float, cutout_area: float, *, ridge_length_m: float, rise_m: float) -> DormerResult:
        preview = DormerPreviewGeometry(
            roof_plan_rect=Rect2D(
                x_m=d.center_along_m - d.width_m / 2.0,
                y_m=0.0,
                width_m=d.width_m,
                height_m=d.depth_m,
            ),
            front_windows=self._build_front_windows(d),
        )
        areas = DormerAreas(
            cutout_main_roof_m2=cutout_area,
            front_wall_gross_m2=front_gross,
            front_wall_net_m2=front_net,
            side_walls_gross_m2=side_gross,
            side_walls_net_m2=side_gross,
            dormer_roof_m2=roof_area,
            window_area_m2=window_area,
        )
        object.__setattr__(areas, "opaque_total_m2", areas.front_wall_net_m2 + areas.side_walls_net_m2 + areas.dormer_roof_m2)
        object.__setattr__(areas, "envelope_total_m2", areas.opaque_total_m2 + areas.window_area_m2)
        return DormerResult(input=d, areas=areas, preview=preview, ridge_length_m=ridge_length_m, rise_m=rise_m)

    def _build_front_windows(self, d: DormerInput) -> list[Rect2D]:
        if d.window_count <= 0 or d.window_width_m <= 0 or d.window_height_m <= 0:
            return []
        total_window_width = d.window_count * d.window_width_m
        min_side_margin = 0.15
        usable_width = d.width_m - 2.0 * min_side_margin
        gap = 0.05 if total_window_width > usable_width else max(0.05, (usable_width - total_window_width) / (d.window_count + 1))
        x = min_side_margin + gap
        y = d.sill_height_m
        rects: list[Rect2D] = []
        for _ in range(d.window_count):
            rects.append(Rect2D(x_m=x, y_m=y, width_m=d.window_width_m, height_m=d.window_height_m))
            x += d.window_width_m + gap
        return rects
