from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional


@dataclass(frozen=True)
class AtticGeometry:
    """Vereinfachte Dach-/Giebelgeometrie für Vorschau, Reporting und DG-Hilfsfunktionen."""

    building_width_m: float
    building_length_m: float
    knee_wall_height_m: float = 1.0
    roof_pitch_deg: float = 35.0
    ridge_height_m: Optional[float] = None
    roof_type: str = "satteldach"
    ridge_orientation: str = "length"
    roof_overhang_m: float = 0.30
    ridge_offset_ratio: float = 0.0
    pult_rise_side: str = "right"

    def __post_init__(self) -> None:
        if self.building_width_m <= 0 or self.building_length_m <= 0:
            raise ValueError("Gebäudebreite und -länge müssen > 0 sein.")
        if self.knee_wall_height_m < 0:
            raise ValueError("Kniestockhöhe muss >= 0 sein.")
        if not (0.0 <= self.roof_pitch_deg < 89.0):
            raise ValueError("Dachneigung muss zwischen 0° und <89° liegen.")
        if self.ridge_height_m is not None and self.ridge_height_m <= self.knee_wall_height_m:
            raise ValueError("Firsthöhe muss größer als die Kniestockhöhe sein.")
        if float(self.roof_overhang_m) < 0.0:
            raise ValueError("Dachüberstand muss >= 0 sein.")

    @property
    def half_span_m(self) -> float:
        return 0.5 * float(self.building_width_m)

    @property
    def roof_pitch_rad(self) -> float:
        return math.radians(float(self.roof_pitch_deg))

    @property
    def cross_span_m(self) -> float:
        return float(self.building_width_m) if str(self.ridge_orientation).strip().lower() == "length" else float(self.building_length_m)

    @property
    def along_span_m(self) -> float:
        return float(self.building_length_m) if str(self.ridge_orientation).strip().lower() == "length" else float(self.building_width_m)

    @property
    def ridge_pos_m(self) -> float:
        half = 0.5 * self.cross_span_m
        raw = half * (1.0 + max(-0.8, min(0.8, float(self.ridge_offset_ratio))))
        return max(0.10 * self.cross_span_m, min(0.90 * self.cross_span_m, raw))

    @property
    def ridge_x_m(self) -> float:
        return self.ridge_pos_m

    @property
    def left_run_m(self) -> float:
        return max(1e-9, self.ridge_pos_m)

    @property
    def right_run_m(self) -> float:
        return max(1e-9, self.cross_span_m - self.ridge_pos_m)

    @property
    def hip_run_m(self) -> float:
        if str(self.roof_type).lower() != "walmdach":
            return 0.0
        return max(1e-9, min(self.left_run_m, self.right_run_m, 0.5 * self.along_span_m))

    @property
    def roof_rise_m(self) -> float:
        if self.ridge_height_m is not None:
            return float(self.ridge_height_m) - float(self.knee_wall_height_m)
        pitch = max(0.0, float(self.roof_pitch_deg))
        if str(self.roof_type).lower() == "flachdach":
            return 0.12
        if str(self.roof_type).lower() == "pultdach":
            return self.cross_span_m * math.tan(math.radians(max(1.0, pitch)))
        return 0.5 * self.cross_span_m * math.tan(math.radians(max(1.0, pitch)))

    @property
    def total_height_m(self) -> float:
        return float(self.knee_wall_height_m) + self.roof_rise_m

    @property
    def rafter_length_left_m(self) -> float:
        if str(self.roof_type).lower() == "flachdach":
            return float(self.building_length_m)
        if str(self.roof_type).lower() == "pultdach":
            return self.cross_span_m / math.cos(math.radians(max(1.0, float(self.roof_pitch_deg))))
        return math.hypot(self.left_run_m, self.roof_rise_m)

    @property
    def rafter_length_right_m(self) -> float:
        if str(self.roof_type).lower() == "flachdach":
            return float(self.building_length_m)
        if str(self.roof_type).lower() == "pultdach":
            return self.rafter_length_left_m
        return math.hypot(self.right_run_m, self.roof_rise_m)

    @property
    def rafter_length_m(self) -> float:
        return 0.5 * (self.rafter_length_left_m + self.rafter_length_right_m)

    @property
    def roof_area_one_side_m2(self) -> float:
        return self.rafter_length_m * float(self.building_length_m)

    @property
    def roof_area_total_m2(self) -> float:
        rt = str(self.roof_type).lower()
        if rt == "flachdach":
            ov = 2.0 * float(self.roof_overhang_m)
            return max(0.0, (float(self.building_width_m) + ov) * (float(self.building_length_m) + ov))
        if rt == "pultdach":
            return self.rafter_length_left_m * float(self.building_length_m)
        return (self.rafter_length_left_m + self.rafter_length_right_m) * float(self.building_length_m)

    @property
    def knee_wall_area_total_m2(self) -> float:
        return 2.0 * float(self.knee_wall_height_m) * float(self.building_length_m)

    @property
    def gable_rect_area_m2(self) -> float:
        return float(self.building_width_m) * float(self.knee_wall_height_m)

    @property
    def gable_triangle_area_m2(self) -> float:
        return 0.5 * float(self.building_width_m) * self.roof_rise_m

    @property
    def gable_area_total_m2(self) -> float:
        return self.gable_rect_area_m2 + self.gable_triangle_area_m2

    @property
    def gable_area_both_sides_m2(self) -> float:
        rt = str(self.roof_type).lower()
        if rt in ("satteldach", "pultdach"):
            return 2.0 * self.gable_area_total_m2
        if rt == "walmdach":
            return 0.35 * 2.0 * self.gable_area_total_m2
        return 0.0

    @property
    def cross_section_area_m2(self) -> float:
        return self.gable_area_total_m2

    @property
    def volume_m3(self) -> float:
        return self.cross_section_area_m2 * float(self.building_length_m)

    def _x_bounds_at_height(self, height_m: float) -> tuple[float, float]:
        h = float(height_m)
        rt = str(self.roof_type).lower()
        if h <= self.knee_wall_height_m:
            return 0.0, float(self.building_width_m)
        if h >= self.total_height_m:
            if rt == "pultdach":
                return (0.0, 0.0) if str(self.pult_rise_side).lower() == "right" else (float(self.building_width_m), float(self.building_width_m))
            return self.ridge_x_m, self.ridge_x_m
        dy = h - float(self.knee_wall_height_m)
        if rt == "flachdach":
            return 0.0, float(self.building_width_m)
        if rt == "pultdach":
            frac = dy / max(self.roof_rise_m, 1e-9)
            width = float(self.building_width_m) * (1.0 - frac)
            if str(self.pult_rise_side).lower() == "left":
                return float(self.building_width_m) - width, float(self.building_width_m)
            return 0.0, width
        x_left = dy * self.left_run_m / max(self.roof_rise_m, 1e-9)
        x_right = float(self.building_width_m) - dy * self.right_run_m / max(self.roof_rise_m, 1e-9)
        return max(0.0, x_left), min(float(self.building_width_m), x_right)


    def cross_section_points(self) -> list[tuple[float, float]]:
        rt = str(self.roof_type).lower()
        left = 0.0
        right = self.cross_span_m
        knee = float(self.knee_wall_height_m)
        peak = float(self.total_height_m)
        ridge = float(self.ridge_pos_m)
        if rt == "pultdach":
            if str(self.pult_rise_side).strip().lower() == "left":
                return [(left, 0.0), (left, peak), (right, knee), (right, 0.0)]
            return [(left, 0.0), (left, knee), (right, peak), (right, 0.0)]
        if rt == "flachdach":
            return [(left, 0.0), (left, peak), (right, peak), (right, 0.0)]
        return [(left, 0.0), (left, knee), (ridge, peak), (right, knee), (right, 0.0)]

    def plan_outer_rect(self) -> tuple[float, float, float, float]:
        ov = float(self.roof_overhang_m)
        return (0.0, 0.0, float(self.building_width_m) + 2.0 * ov, float(self.building_length_m) + 2.0 * ov)

    def plan_inner_rect(self) -> tuple[float, float, float, float]:
        ov = float(self.roof_overhang_m)
        return (ov, ov, ov + float(self.building_width_m), ov + float(self.building_length_m))

    def plan_ridge_or_slope_line(self) -> list[tuple[float, float]]:
        rt = str(self.roof_type).lower()
        ov = float(self.roof_overhang_m)
        ridge_orientation = str(self.ridge_orientation).strip().lower()
        if rt == "flachdach":
            return []
        if rt == "pultdach":
            y = ov + 0.5 * float(self.building_length_m)
            if ridge_orientation == "width":
                x = ov + 0.5 * float(self.building_width_m)
                if str(self.pult_rise_side).strip().lower() == "left":
                    return [(x, ov + float(self.building_length_m)), (x, ov)]
                return [(x, ov), (x, ov + float(self.building_length_m))]
            if str(self.pult_rise_side).strip().lower() == "left":
                return [(ov + float(self.building_width_m), y), (ov, y)]
            return [(ov, y), (ov + float(self.building_width_m), y)]
        hip = self.hip_run_m if rt == "walmdach" else 0.0
        if ridge_orientation == "width":
            y = ov + float(self.ridge_pos_m)
            return [(ov + hip, y), (ov + float(self.building_width_m) - hip, y)]
        x = ov + float(self.ridge_pos_m)
        return [(x, ov + hip), (x, ov + float(self.building_length_m) - hip)]

    def plan_hip_lines(self) -> list[list[tuple[float, float]]]:
        if str(self.roof_type).lower() != "walmdach":
            return []
        ov = float(self.roof_overhang_m)
        hip = self.hip_run_m
        ridge = self.plan_ridge_or_slope_line()
        if len(ridge) != 2:
            return []
        x0, y0 = ov, ov
        x1, y1 = ov + float(self.building_width_m), ov + float(self.building_length_m)
        if str(self.ridge_orientation).strip().lower() == "width":
            left_ridge, right_ridge = ridge
            return [
                [(x0, y0), left_ridge],
                [(x1, y0), right_ridge],
                [(x0, y1), left_ridge],
                [(x1, y1), right_ridge],
            ]
        top_ridge, bottom_ridge = ridge
        return [
            [(x0, y0), top_ridge],
            [(x1, y0), top_ridge],
            [(x0, y1), bottom_ridge],
            [(x1, y1), bottom_ridge],
        ]

    def clear_width_at_height_m(self, height_m: float) -> float:
        x0, x1 = self._x_bounds_at_height(height_m)
        return max(0.0, x1 - x0)

    def area_above_height_m2(self, height_m: float) -> float:
        h = max(0.0, float(height_m))
        if h <= 0.0:
            return self.cross_section_area_m2
        if h >= self.total_height_m:
            return 0.0
        if h <= self.knee_wall_height_m:
            lower_rect = float(self.building_width_m) * h
            return self.cross_section_area_m2 - lower_rect
        width_at_h = self.clear_width_at_height_m(h)
        upper_tri_h = self.total_height_m - h
        return 0.5 * width_at_h * upper_tri_h

    def floor_area_band_m2(self, h_min_m: float, h_max_m: float) -> float:
        h0 = max(0.0, min(float(h_min_m), float(h_max_m)))
        h1 = max(0.0, max(float(h_min_m), float(h_max_m)))
        if h0 >= self.total_height_m:
            return 0.0
        area = self.area_above_height_m2(h0) - self.area_above_height_m2(h1)
        return max(0.0, area) * float(self.building_length_m)

    def floor_area_ge_2m_m2(self) -> float:
        return self.clear_width_at_height_m(2.0) * float(self.building_length_m)

    def floor_area_1m_to_2m_m2(self) -> float:
        width1 = self.clear_width_at_height_m(1.0)
        width2 = self.clear_width_at_height_m(2.0)
        return max(0.0, width1 - width2) * float(self.building_length_m)

    def floor_area_lt_1m_m2(self) -> float:
        usable_width_1m = self.clear_width_at_height_m(1.0)
        return max(0.0, float(self.building_width_m) - usable_width_1m) * float(self.building_length_m)

    def weighted_floor_area_m2(self, low_band_weight: float = 0.5) -> float:
        return self.floor_area_ge_2m_m2() + low_band_weight * self.floor_area_1m_to_2m_m2()

    def slope_offset_x_m(self, level_height_m: float) -> float:
        x0, _ = self._x_bounds_at_height(level_height_m)
        return max(0.0, x0)

    def to_dict(self) -> dict:
        return {
            "building_width_m": float(self.building_width_m),
            "building_length_m": float(self.building_length_m),
            "knee_wall_height_m": float(self.knee_wall_height_m),
            "roof_pitch_deg": float(self.roof_pitch_deg),
            "ridge_height_m": float(self.total_height_m),
            "roof_rise_m": float(self.roof_rise_m),
            "rafter_length_m": float(self.rafter_length_m),
            "roof_area_total_m2": float(self.roof_area_total_m2),
            "gable_area_total_m2": float(self.gable_area_total_m2),
            "volume_m3": float(self.volume_m3),
            "floor_area_ge_2m_m2": float(self.floor_area_ge_2m_m2()),
            "floor_area_1m_to_2m_m2": float(self.floor_area_1m_to_2m_m2()),
            "floor_area_lt_1m_m2": float(self.floor_area_lt_1m_m2()),
            "weighted_floor_area_m2": float(self.weighted_floor_area_m2()),
            "roof_type": str(self.roof_type),
            "ridge_orientation": str(self.ridge_orientation),
            "roof_overhang_m": float(self.roof_overhang_m),
            "ridge_offset_ratio": float(self.ridge_offset_ratio),
            "pult_rise_side": str(self.pult_rise_side),
        }
