from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING, Optional

from .roof_line_geometry import RoofFacet, build_roof_facets, estimate_roof_line_extra_area_m2, normalized_roof_lines, roof_lines_to_plan_segments

if TYPE_CHECKING:
    from .dormer_geometry import DormerInput, DormerResult


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
    eave_overhang_m: float = 0.30
    gable_overhang_m: float = 0.30
    ridge_offset_ratio: float = 0.0
    pult_rise_side: str = "right"
    half_hip_ratio: float = 0.45
    dormer_type: str = "none"
    dormer_width_m: float = 1.80
    dormer_height_m: float = 1.20
    dormer_offset_ratio: float = 0.0
    roof_window_count: int = 0
    roof_window_width_m: float = 0.78
    roof_window_height_m: float = 1.18
    roof_window_side: str = "right"
    roof_lines: tuple[tuple[str, float, float, float, float], ...] = ()

    def __post_init__(self) -> None:
        if self.building_width_m <= 0 or self.building_length_m <= 0:
            raise ValueError("Gebäudebreite und -länge müssen > 0 sein.")
        if self.knee_wall_height_m < 0:
            raise ValueError("Kniestockhöhe muss >= 0 sein.")
        if not (0.0 <= self.roof_pitch_deg < 89.0):
            raise ValueError("Dachneigung muss zwischen 0° und <89° liegen.")
        if self.ridge_height_m is not None and self.ridge_height_m <= self.knee_wall_height_m:
            raise ValueError("Firsthöhe muss größer als die Kniestockhöhe sein.")
        for val in (self.roof_overhang_m, self.eave_overhang_m, self.gable_overhang_m):
            if float(val) < 0.0:
                raise ValueError("Dachüberstände müssen >= 0 sein.")

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
    def effective_eave_overhang_m(self) -> float:
        val = float(self.eave_overhang_m if self.eave_overhang_m is not None else self.roof_overhang_m)
        return max(0.0, val)

    @property
    def effective_gable_overhang_m(self) -> float:
        val = float(self.gable_overhang_m if self.gable_overhang_m is not None else self.roof_overhang_m)
        return max(0.0, val)

    @property
    def plan_overhang_x_m(self) -> float:
        return self.effective_eave_overhang_m if str(self.ridge_orientation).strip().lower() == "length" else self.effective_gable_overhang_m

    @property
    def plan_overhang_y_m(self) -> float:
        return self.effective_gable_overhang_m if str(self.ridge_orientation).strip().lower() == "length" else self.effective_eave_overhang_m

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
        if str(self.roof_type).lower() not in {"walmdach", "krueppelwalmdach"}:
            return 0.0
        return max(1e-9, min(self.left_run_m, self.right_run_m, 0.5 * self.along_span_m))

    @property
    def half_hip_run_m(self) -> float:
        if str(self.roof_type).lower() != "krueppelwalmdach":
            return 0.0
        ratio = max(0.05, min(0.95, float(self.half_hip_ratio)))
        return self.hip_run_m * ratio

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
            return max(0.0, (float(self.building_width_m) + 2.0 * self.plan_overhang_x_m) * (float(self.building_length_m) + 2.0 * self.plan_overhang_y_m))
        if rt == "pultdach":
            return self.rafter_length_left_m * float(self.along_span_m)
        base = (self.rafter_length_left_m + self.rafter_length_right_m) * float(self.along_span_m)
        if rt == "krueppelwalmdach":
            base = base * (1.0 - 0.08 * max(0.05, min(0.95, float(self.half_hip_ratio))))
        facets = self.roof_facets()
        if facets:
            return sum(float(f.surface_area_m2) for f in facets)
        if self.roof_lines:
            base += estimate_roof_line_extra_area_m2(
                self.roof_lines,
                width_m=float(self.building_width_m),
                length_m=float(self.building_length_m),
                rise_m=float(self.roof_rise_m),
            )
        return base

    @property
    def knee_wall_area_total_m2(self) -> float:
        return 2.0 * float(self.knee_wall_height_m) * float(self.building_length_m)

    @property
    def gable_rect_area_m2(self) -> float:
        return float(self.cross_span_m) * float(self.knee_wall_height_m)

    @property
    def gable_triangle_area_m2(self) -> float:
        tri = 0.5 * float(self.cross_span_m) * self.roof_rise_m
        if str(self.roof_type).lower() == "krueppelwalmdach":
            return tri * (1.0 - max(0.05, min(0.95, float(self.half_hip_ratio))))
        return tri

    @property
    def gable_area_total_m2(self) -> float:
        return self.gable_rect_area_m2 + self.gable_triangle_area_m2

    @property
    def gable_area_both_sides_m2(self) -> float:
        rt = str(self.roof_type).lower()
        if rt in ("satteldach", "pultdach", "krueppelwalmdach"):
            return 2.0 * self.gable_area_total_m2
        if rt == "walmdach":
            return 0.35 * 2.0 * (float(self.cross_span_m) * float(self.knee_wall_height_m) + 0.5 * float(self.cross_span_m) * self.roof_rise_m)
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

    def dormer_rect(self) -> tuple[float, float, float, float] | None:
        if str(self.dormer_type).lower() == "none":
            return None
        width = min(max(0.6, float(self.dormer_width_m)), 0.8 * self.along_span_m)
        height = max(0.4, float(self.dormer_height_m))
        center = 0.5 * self.along_span_m * (1.0 + max(-0.7, min(0.7, float(self.dormer_offset_ratio))))
        x0 = max(0.15 * self.along_span_m, center - 0.5 * width)
        x1 = min(0.85 * self.along_span_m, x0 + width)
        if x1 <= x0:
            x1 = x0 + width
        return (x0, x1, max(self.knee_wall_height_m + 0.20, self.total_height_m - height), self.total_height_m)

    def roof_window_rects(self) -> list[tuple[float, float, float, float]]:
        count = max(0, int(self.roof_window_count))
        if count <= 0 or str(self.roof_type).lower() == "flachdach":
            return []
        width = max(0.3, float(self.roof_window_width_m))
        height = max(0.4, float(self.roof_window_height_m))
        span = self.along_span_m
        usable = max(width, 0.70 * span)
        start = 0.5 * (span - usable)
        rects = []
        for i in range(count):
            cx = start + usable * ((i + 0.5) / count)
            x0 = max(0.1 * span, cx - 0.5 * width)
            x1 = min(0.9 * span, x0 + width)
            y1 = max(self.knee_wall_height_m + 0.7, self.total_height_m - 0.35 * self.roof_rise_m)
            y0 = max(self.knee_wall_height_m + 0.15, y1 - height)
            rects.append((x0, x1, y0, y1))
        return rects

    def plan_outer_rect(self) -> tuple[float, float, float, float]:
        ox = self.plan_overhang_x_m
        oy = self.plan_overhang_y_m
        return (0.0, 0.0, float(self.building_width_m) + 2.0 * ox, float(self.building_length_m) + 2.0 * oy)

    def plan_inner_rect(self) -> tuple[float, float, float, float]:
        ox = self.plan_overhang_x_m
        oy = self.plan_overhang_y_m
        return (ox, oy, ox + float(self.building_width_m), oy + float(self.building_length_m))

    def plan_ridge_or_slope_line(self) -> list[tuple[float, float]]:
        rt = str(self.roof_type).lower()
        ox = self.plan_overhang_x_m
        oy = self.plan_overhang_y_m
        ridge_orientation = str(self.ridge_orientation).strip().lower()
        if rt == "flachdach":
            return []
        if rt == "pultdach":
            y = oy + 0.5 * float(self.building_length_m)
            if ridge_orientation == "width":
                x = ox + 0.5 * float(self.building_width_m)
                if str(self.pult_rise_side).strip().lower() == "left":
                    return [(x, oy + float(self.building_length_m)), (x, oy)]
                return [(x, oy), (x, oy + float(self.building_length_m))]
            if str(self.pult_rise_side).strip().lower() == "left":
                return [(ox + float(self.building_width_m), y), (ox, y)]
            return [(ox, y), (ox + float(self.building_width_m), y)]
        hip = self.half_hip_run_m if rt == "krueppelwalmdach" else (self.hip_run_m if rt == "walmdach" else 0.0)
        if ridge_orientation == "width":
            y = oy + float(self.ridge_pos_m)
            return [(ox + hip, y), (ox + float(self.building_width_m) - hip, y)]
        x = ox + float(self.ridge_pos_m)
        return [(x, oy + hip), (x, oy + float(self.building_length_m) - hip)]



    def all_plan_line_segments(self) -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
        segs: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
        ridge = self.plan_ridge_or_slope_line()
        if len(ridge) == 2:
            segs.append(("first", ridge[0], ridge[1]))
        for line in self.plan_hip_lines():
            if len(line) == 2:
                segs.append(("grat", line[0], line[1]))
        segs.extend(self.custom_roof_line_segments())
        return segs

    def roof_height_at_plan_point_m(self, x_m: float, y_m: float) -> float:
        x = float(x_m) - self.plan_overhang_x_m
        y = float(y_m) - self.plan_overhang_y_m
        x = max(0.0, min(float(self.building_width_m), x))
        y = max(0.0, min(float(self.building_length_m), y))
        rt = str(self.roof_type).strip().lower()
        if rt == "flachdach":
            return self.roof_rise_m
        if str(self.ridge_orientation).strip().lower() == "width":
            cross = max(1e-9, float(self.building_length_m))
            along = max(1e-9, float(self.building_width_m))
            c = y
            a = x
        else:
            cross = max(1e-9, float(self.building_width_m))
            along = max(1e-9, float(self.building_length_m))
            c = x
            a = y
        if rt == "pultdach":
            frac = c / cross
            if str(self.pult_rise_side).strip().lower() == "left":
                frac = 1.0 - frac
            return max(0.0, min(1.0, frac)) * self.roof_rise_m
        if rt in {"walmdach", "krueppelwalmdach"}:
            hip = self.half_hip_run_m if rt == "krueppelwalmdach" else self.hip_run_m
            along_factor = 1.0
            if hip > 1e-9:
                if a < hip:
                    along_factor = max(0.0, min(1.0, a / hip))
                elif a > along - hip:
                    along_factor = max(0.0, min(1.0, (along - a) / hip))
            if c <= self.ridge_pos_m:
                cross_factor = c / max(1e-9, self.left_run_m)
            else:
                cross_factor = (cross - c) / max(1e-9, self.right_run_m)
            return max(0.0, min(cross_factor, along_factor)) * self.roof_rise_m
        if c <= self.ridge_pos_m:
            frac = c / max(1e-9, self.left_run_m)
        else:
            frac = (cross - c) / max(1e-9, self.right_run_m)
        return max(0.0, min(1.0, frac)) * self.roof_rise_m

    def roof_facets(self) -> list[RoofFacet]:
        outer = self.plan_outer_rect()
        poly = ((outer[0], outer[1]), (outer[2], outer[1]), (outer[2], outer[3]), (outer[0], outer[3]))
        segs = self.all_plan_line_segments()
        extra = estimate_roof_line_extra_area_m2(
            self.roof_lines,
            width_m=float(self.building_width_m),
            length_m=float(self.building_length_m),
            rise_m=float(self.roof_rise_m),
        ) if self.roof_lines else 0.0
        return build_roof_facets(poly, segs, self.roof_height_at_plan_point_m, extra_area_total_m2=extra, label_prefix="RF")

    def custom_roof_line_segments(self) -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
        if not self.roof_lines:
            return []
        ox = self.plan_overhang_x_m
        oy = self.plan_overhang_y_m
        return roof_lines_to_plan_segments(self.roof_lines, x0_m=ox, y0_m=oy, width_m=float(self.building_width_m), length_m=float(self.building_length_m))

    def plan_hip_lines(self) -> list[list[tuple[float, float]]]:
        rt = str(self.roof_type).lower()
        if rt not in {"walmdach", "krueppelwalmdach"}:
            return []
        ox = self.plan_overhang_x_m
        oy = self.plan_overhang_y_m
        ridge = self.plan_ridge_or_slope_line()
        if len(ridge) != 2:
            return []
        x0, y0 = ox, oy
        x1, y1 = ox + float(self.building_width_m), oy + float(self.building_length_m)
        if str(self.ridge_orientation).strip().lower() == "width":
            left_ridge, right_ridge = ridge
            return [[(x0, y0), left_ridge], [(x1, y0), right_ridge], [(x0, y1), left_ridge], [(x1, y1), right_ridge]]
        top_ridge, bottom_ridge = ridge
        return [[(x0, y0), top_ridge], [(x1, y0), top_ridge], [(x0, y1), bottom_ridge], [(x1, y1), bottom_ridge]]

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
            "eave_overhang_m": float(self.effective_eave_overhang_m),
            "gable_overhang_m": float(self.effective_gable_overhang_m),
            "ridge_offset_ratio": float(self.ridge_offset_ratio),
            "pult_rise_side": str(self.pult_rise_side),
            "half_hip_ratio": float(self.half_hip_ratio),
            "dormer_type": str(self.dormer_type),
            "dormer_width_m": float(self.dormer_width_m),
            "dormer_height_m": float(self.dormer_height_m),
            "dormer_offset_ratio": float(self.dormer_offset_ratio),
            "roof_window_count": int(self.roof_window_count),
            "roof_window_width_m": float(self.roof_window_width_m),
            "roof_window_height_m": float(self.roof_window_height_m),
            "roof_window_side": str(self.roof_window_side),
            "roof_lines": [
                {"kind": kind, "x1_ratio": x1, "y1_ratio": y1, "x2_ratio": x2, "y2_ratio": y2}
                for kind, x1, y1, x2, y2 in normalized_roof_lines(self.roof_lines)
            ],
            "roof_facets": [
                {
                    "label": facet.label,
                    "plan_area_m2": float(facet.plan_area_m2),
                    "surface_area_m2": float(facet.surface_area_m2),
                    "boundary_kinds": list(facet.boundary_kinds),
                    "polygon_m": [[float(x), float(y)] for x, y in facet.polygon_m],
                }
                for facet in self.roof_facets()
            ],
        }

    def build_dormer_inputs(self) -> list["DormerInput"]:
        from .dormer_geometry import DormerInput

        dtype_map = {
            "schleppgaube": "shed",
            "satteldachgaube": "gable",
            "flachdachgaube": "flat",
        }
        kind = dtype_map.get(str(self.dormer_type).strip().lower())
        if not kind:
            return []
        side = "right" if str(self.ridge_orientation).strip().lower() == "length" else "back"
        center = 0.5 * self.along_span_m * (1.0 + max(-0.9, min(0.9, float(self.dormer_offset_ratio))))
        center = max(0.40 + 0.5 * float(self.dormer_width_m), min(self.along_span_m - 0.40 - 0.5 * float(self.dormer_width_m), center))
        return [DormerInput(
            id="legacy_dormer_1",
            dormer_type=kind,
            roof_side=side,
            center_along_m=center,
            width_m=float(self.dormer_width_m),
            depth_m=max(0.8, 0.75 * float(self.dormer_width_m)),
            front_height_m=float(self.dormer_height_m),
        )]

    def build_dormers(self) -> list["DormerResult"]:
        from .dormer_geometry import DormerGeometry, RoofContext

        engine = DormerGeometry(RoofContext(
            roof_type=str(self.roof_type).strip().lower(),
            ridge_direction=str(self.ridge_orientation).strip().lower(),
            building_length_m=float(self.building_length_m),
            building_width_m=float(self.building_width_m),
            eaves_overhang_m=float(self.effective_eave_overhang_m),
            gable_overhang_m=float(self.effective_gable_overhang_m),
            roof_pitch_deg_left=float(self.roof_pitch_deg),
            roof_pitch_deg_right=float(self.roof_pitch_deg),
        ))
        return [engine.build(item) for item in self.build_dormer_inputs()]
