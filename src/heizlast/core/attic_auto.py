from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from .attic_geometry import AtticGeometry
from .config import DEFAULT_FACTOR, DEFAULT_U
from .dormer_auto_elements import build_dormer_results_from_attic_cfg, dormer_to_auto_elements
from .din_boundary import DIN_BOUNDARY_CONDITIONS
from .geometry import classify_floor_edge_spans
from ..domain.models import ElementModel, RoomModel
from ..configs.project_config import AtticCfgDTO
from .roof_line_geometry import estimate_roof_line_extra_area_m2

EPS = 1e-9
AUTO_ATTIC_UID_PREFIX = "auto_attic_"


@dataclass(frozen=True)
class _RoofModel:
    width_m: float
    length_m: float
    knee_m: float
    pitch_deg: float
    roof_type: str
    ridge_orientation: str
    ridge_offset_ratio: float
    ridge_height_m: float | None
    pult_rise_side: str
    half_hip_ratio: float = 0.45
    roof_line_area_factor: float = 1.0

    @property
    def cross_span_m(self) -> float:
        return self.width_m if self.ridge_orientation == "length" else self.length_m

    @property
    def along_span_m(self) -> float:
        return self.length_m if self.ridge_orientation == "length" else self.width_m

    @property
    def ridge_pos_m(self) -> float:
        half = 0.5 * self.cross_span_m
        raw = half * (1.0 + max(-0.8, min(0.8, float(self.ridge_offset_ratio))))
        return max(0.10 * self.cross_span_m, min(0.90 * self.cross_span_m, raw))

    @property
    def left_run_m(self) -> float:
        return max(EPS, self.ridge_pos_m)

    @property
    def right_run_m(self) -> float:
        return max(EPS, self.cross_span_m - self.ridge_pos_m)

    @property
    def rise_m(self) -> float:
        if self.ridge_height_m is not None:
            return max(0.0, float(self.ridge_height_m) - float(self.knee_m))
        pitch = math.radians(max(1.0, float(self.pitch_deg)))
        if self.roof_type == "flachdach":
            return 0.12
        if self.roof_type == "pultdach":
            return self.cross_span_m * math.tan(pitch)
        return 0.5 * self.cross_span_m * math.tan(pitch)

    @property
    def hip_run_m(self) -> float:
        if self.roof_type not in {"walmdach", "krueppelwalmdach"}:
            return 0.0
        hip = max(EPS, min(self.left_run_m, self.right_run_m, 0.5 * self.along_span_m))
        if self.roof_type == "krueppelwalmdach":
            hip *= max(0.05, min(0.95, float(self.half_hip_ratio)))
        return hip

    @property
    def slant_left_m(self) -> float:
        if self.roof_type == "flachdach":
            return self.cross_span_m
        if self.roof_type == "pultdach":
            return math.hypot(self.cross_span_m, self.rise_m)
        return math.hypot(self.left_run_m, self.rise_m)

    @property
    def slant_right_m(self) -> float:
        if self.roof_type == "flachdach":
            return self.cross_span_m
        if self.roof_type == "pultdach":
            return self.slant_left_m
        return math.hypot(self.right_run_m, self.rise_m)


def parse_attic_meta(meta: str | None) -> dict[str, str]:
    parts: dict[str, str] = {}
    for chunk in str(meta or '').split('|'):
        if '=' in chunk:
            k, v = chunk.split('=', 1)
            parts[str(k).strip()] = str(v).strip()
        elif chunk:
            parts[str(chunk).strip()] = '1'
    return parts


def attic_part_display_name(attic_part: str | None) -> str:
    mapping = {
        'roof_left': 'roof_left',
        'roof_right': 'roof_right',
        'gable_front': 'gable_front',
        'gable_back': 'gable_back',
        'gable_left': 'gable_left',
        'gable_right': 'gable_right',
        'roof_front': 'roof_front',
        'roof_back': 'roof_back',
        'roof_window': 'roof_window',
    }
    return mapping.get(str(attic_part or '').strip(), str(attic_part or '').strip())


def auto_attic_marker_label(e: ElementModel) -> str:
    meta = parse_attic_meta(getattr(e, 'meta', None))
    attic_part = attic_part_display_name(meta.get('attic_part', '') or (f"dormer_{meta.get('part', '')}" if "dormer_auto" in str(getattr(e, "meta", "") or "") else ""))
    if attic_part:
        return f'auto_attic | {attic_part}'
    return 'auto_attic'


def is_auto_attic_element(e: ElementModel) -> bool:
    uid = str(getattr(e, "uid", "") or "")
    meta = str(getattr(e, "meta", "") or "")
    return uid.startswith(AUTO_ATTIC_UID_PREFIX) or uid.startswith("auto_dormer_") or "attic_auto" in meta or "dormer_auto" in meta


def remove_auto_attic_elements(elements: Sequence[ElementModel]) -> list[ElementModel]:
    return [e for e in elements if not is_auto_attic_element(e)]


def _fmt_num(x: float) -> str:
    return f"{float(x):.6f}".replace('-', 'm').replace('.', 'p')


def _dg_bbox(rooms: Iterable[RoomModel]) -> Optional[tuple[float, float, float, float]]:
    xs0: list[float] = []
    ys0: list[float] = []
    xs1: list[float] = []
    ys1: list[float] = []
    for r in rooms:
        try:
            r.ensure_polygon()
            r.normalize_polygon_bbox()
        except Exception:
            pass
        xs0.append(float(getattr(r, "x_m", 0.0) or 0.0))
        ys0.append(float(getattr(r, "y_m", 0.0) or 0.0))
        xs1.append(float(getattr(r, "x_m", 0.0) or 0.0) + float(getattr(r, "w_m", 0.0) or 0.0))
        ys1.append(float(getattr(r, "y_m", 0.0) or 0.0) + float(getattr(r, "h_m", 0.0) or 0.0))
    if not xs0:
        return None
    return min(xs0), min(ys0), max(xs1), max(ys1)


def _build_geom_from_cfg(cfg: AtticCfgDTO) -> Optional[AtticGeometry]:
    if not bool(getattr(cfg, "enabled", False)):
        return None
    try:
        return AtticGeometry(
            building_width_m=float(getattr(cfg, "building_width_m", 0.0) or 0.0),
            building_length_m=float(getattr(cfg, "building_length_m", 0.0) or 0.0),
            knee_wall_height_m=float(getattr(cfg, "knee_wall_height_m", 0.0) or 0.0),
            roof_pitch_deg=float(getattr(cfg, "roof_pitch_deg", 0.0) or 0.0),
            roof_type=str(getattr(cfg, "roof_type", "satteldach") or "satteldach").strip().lower(),
            ridge_orientation=str(getattr(cfg, "ridge_orientation", "length") or "length").strip().lower(),
            roof_overhang_m=float(getattr(cfg, "roof_overhang_m", 0.30) or 0.0),
            eave_overhang_m=float(getattr(cfg, "eave_overhang_m", getattr(cfg, "roof_overhang_m", 0.30)) or 0.0),
            gable_overhang_m=float(getattr(cfg, "gable_overhang_m", getattr(cfg, "roof_overhang_m", 0.30)) or 0.0),
            ridge_offset_ratio=float(getattr(cfg, "ridge_offset_ratio", 0.0) or 0.0),
            ridge_height_m=(float(getattr(cfg, "ridge_height_m")) if getattr(cfg, "ridge_height_m", None) is not None else None),
            pult_rise_side=str(getattr(cfg, "pult_rise_side", "right") or "right").strip().lower(),
            half_hip_ratio=float(getattr(cfg, "half_hip_ratio", 0.45) or 0.45),
            dormer_type=str(getattr(cfg, "dormer_type", "none") or "none").strip().lower(),
            dormer_width_m=float(getattr(cfg, "dormer_width_m", 1.80) or 1.80),
            dormer_height_m=float(getattr(cfg, "dormer_height_m", 1.20) or 1.20),
            dormer_offset_ratio=float(getattr(cfg, "dormer_offset_ratio", 0.0) or 0.0),
            roof_window_count=int(getattr(cfg, "roof_window_count", 0) or 0),
            roof_window_width_m=float(getattr(cfg, "roof_window_width_m", 0.78) or 0.78),
            roof_window_height_m=float(getattr(cfg, "roof_window_height_m", 1.18) or 1.18),
            roof_window_side=str(getattr(cfg, "roof_window_side", "right") or "right").strip().lower(),
            roof_lines=tuple((str(getattr(line, "kind", "first") or "first"), float(getattr(line, "x1_ratio", 0.0) or 0.0), float(getattr(line, "y1_ratio", 0.0) or 0.0), float(getattr(line, "x2_ratio", 0.0) or 0.0), float(getattr(line, "y2_ratio", 0.0) or 0.0)) for line in list(getattr(cfg, "roof_lines", []) or [])),
        )
    except Exception:
        return None


def _build_roof_model(cfg: AtticCfgDTO) -> _RoofModel:
    ridge_orientation = str(getattr(cfg, "ridge_orientation", "length") or "length").strip().lower()
    if ridge_orientation not in {"length", "width"}:
        ridge_orientation = "length"
    roof_type = str(getattr(cfg, "roof_type", "satteldach") or "satteldach").strip().lower()
    if roof_type not in {"satteldach", "pultdach", "walmdach", "krueppelwalmdach", "flachdach", "winkeldach"}:
        roof_type = "satteldach"
    pult_rise_side = str(getattr(cfg, "pult_rise_side", "right") or "right").strip().lower()
    if pult_rise_side not in {"left", "right"}:
        pult_rise_side = "right"
    extra_area = estimate_roof_line_extra_area_m2(
        getattr(cfg, "roof_lines", []) or [],
        width_m=float(getattr(cfg, "building_width_m", 0.0) or 0.0),
        length_m=float(getattr(cfg, "building_length_m", 0.0) or 0.0),
        rise_m=(float(getattr(cfg, "building_width_m", 0.0) or 0.0) * math.tan(math.radians(max(1.0, float(getattr(cfg, "roof_pitch_deg", 0.0) or 0.0)))) * 0.5) if roof_type != "pultdach" else (float(getattr(cfg, "building_width_m", 0.0) or 0.0) * math.tan(math.radians(max(1.0, float(getattr(cfg, "roof_pitch_deg", 0.0) or 0.0))))),
    )
    base_plan = max(EPS, float(getattr(cfg, "building_width_m", 0.0) or 0.0) * float(getattr(cfg, "building_length_m", 0.0) or 0.0))
    return _RoofModel(
        width_m=float(getattr(cfg, "building_width_m", 0.0) or 0.0),
        length_m=float(getattr(cfg, "building_length_m", 0.0) or 0.0),
        knee_m=float(getattr(cfg, "knee_wall_height_m", 0.0) or 0.0),
        pitch_deg=float(getattr(cfg, "roof_pitch_deg", 0.0) or 0.0),
        roof_type=roof_type,
        ridge_orientation=ridge_orientation,
        ridge_offset_ratio=float(getattr(cfg, "ridge_offset_ratio", 0.0) or 0.0),
        ridge_height_m=(float(getattr(cfg, "ridge_height_m")) if getattr(cfg, "ridge_height_m", None) is not None else None),
        pult_rise_side=pult_rise_side,
        half_hip_ratio=float(getattr(cfg, "half_hip_ratio", 0.45) or 0.45),
        roof_line_area_factor=1.0 + max(0.0, float(extra_area)) / base_plan,
    )


def _integrate_linear(func, s0: float, s1: float, breaks: list[float] | None = None) -> float:
    a = float(min(s0, s1))
    b = float(max(s0, s1))
    if b - a <= EPS:
        return 0.0
    pts = [a, b]
    for p in breaks or []:
        if a + EPS < p < b - EPS:
            pts.append(float(p))
    pts = sorted(set(round(p, 9) for p in pts))
    area = 0.0
    for p0, p1 in zip(pts, pts[1:]):
        y0 = float(func(p0))
        y1 = float(func(p1))
        area += 0.5 * (y0 + y1) * (p1 - p0)
    return float(area)


def _side_wall_height(side: str, pos_m: float, model: _RoofModel) -> float:
    pos = max(0.0, min(float(pos_m), model.width_m if side in {"front", "back"} else model.length_m))
    knee = model.knee_m
    rt = model.roof_type
    if rt == "flachdach":
        return knee + model.rise_m

    if model.ridge_orientation == "length":
        if side in {"front", "back"}:
            x = pos
            if rt in {"walmdach", "krueppelwalmdach"}:
                return knee
            if rt == "pultdach":
                if model.pult_rise_side == "left":
                    return knee + model.rise_m * max(0.0, 1.0 - x / max(EPS, model.cross_span_m))
                return knee + model.rise_m * max(0.0, x / max(EPS, model.cross_span_m))
            if x <= model.ridge_pos_m:
                return knee + model.rise_m * (x / max(EPS, model.left_run_m))
            return knee + model.rise_m * ((model.cross_span_m - x) / max(EPS, model.right_run_m))
        return knee

    # ridge along width
    if side in {"left", "right"}:
        y = pos
        if rt in {"walmdach", "krueppelwalmdach"}:
            return knee
        if rt == "pultdach":
            if model.pult_rise_side == "left":
                return knee + model.rise_m * (y / max(EPS, model.cross_span_m))
            return knee + model.rise_m * max(0.0, 1.0 - y / max(EPS, model.cross_span_m))
        if y <= model.ridge_pos_m:
            return knee + model.rise_m * (y / max(EPS, model.left_run_m))
        return knee + model.rise_m * ((model.cross_span_m - y) / max(EPS, model.right_run_m))
    return knee


def _roof_depth_at_along(side: str, along_m: float, model: _RoofModel) -> float:
    s = max(0.0, min(float(along_m), model.along_span_m))
    rt = model.roof_type
    if rt == "flachdach":
        return model.cross_span_m
    if rt == "pultdach":
        return model.slant_left_m
    if rt == "satteldach":
        return model.slant_left_m if side in {"left", "front"} else model.slant_right_m

    hip = model.hip_run_m
    taper = min(1.0, s / max(EPS, hip), (model.along_span_m - s) / max(EPS, hip))
    taper = max(0.0, taper)
    if side in {"left", "front"}:
        run = model.left_run_m * taper
        rise = model.rise_m * taper
        return math.hypot(run, rise)
    run = model.right_run_m * taper
    rise = model.rise_m * taper
    return math.hypot(run, rise)


def _roof_strip_area(side: str, s0: float, s1: float, model: _RoofModel) -> float:
    breaks: list[float] = []
    if model.roof_type in {"walmdach", "krueppelwalmdach"}:
        hip = model.hip_run_m
        breaks = [hip, model.along_span_m - hip]
    return _integrate_linear(lambda s: _roof_depth_at_along(side, s, model), s0, s1, breaks)


def _wall_strip_area(side: str, p0: float, p1: float, model: _RoofModel) -> float:
    breaks: list[float] = []
    if model.roof_type in {"satteldach", "pultdach"}:
        breaks = [model.ridge_pos_m]
    return _integrate_linear(lambda s: _side_wall_height(side, s, model), p0, p1, breaks)


def _roof_window_specs(cfg: AtticCfgDTO, model: _RoofModel) -> list[dict[str, float | str]]:
    count = max(0, int(getattr(cfg, "roof_window_count", 0) or 0))
    if count <= 0 or model.roof_type == "flachdach":
        return []

    side_raw = str(getattr(cfg, "roof_window_side", "right") or "right").strip().lower()
    active = ("left", "right") if model.ridge_orientation == "length" else ("front", "back")
    if side_raw == "both":
        sides = [active[i % 2] for i in range(count)]
    elif side_raw in active:
        sides = [side_raw for _ in range(count)]
    else:
        sides = [active[-1] for _ in range(count)]

    width = max(0.3, float(getattr(cfg, "roof_window_width_m", 0.78) or 0.78))
    height = max(0.4, float(getattr(cfg, "roof_window_height_m", 1.18) or 1.18))
    usable = max(width, 0.70 * model.along_span_m)
    start = 0.5 * (model.along_span_m - usable)
    out: list[dict[str, float | str]] = []
    for i, side in enumerate(sides):
        center = start + usable * ((i + 0.5) / count)
        out.append({
            "side": side,
            "center": max(0.0, min(model.along_span_m, center)),
            "width": width,
            "area": width * height,
        })
    return out


def _opening_overlap_share(center_m: float, width_m: float, span0_m: float, span1_m: float) -> float:
    half = 0.5 * max(0.0, float(width_m))
    opening0 = float(center_m) - half
    opening1 = float(center_m) + half
    span0 = min(float(span0_m), float(span1_m))
    span1 = max(float(span0_m), float(span1_m))
    if opening1 <= opening0 or span1 <= span0:
        return 0.0
    return max(0.0, min(opening1, span1) - max(opening0, span0)) / (opening1 - opening0)


def _subtract_roof_opening(elems: list[ElementModel], *, side: str, center_m: float, width_m: float, area_m2: float, tag: str) -> str | None:
    target_room: str | None = None
    opening_area = max(0.0, float(area_m2))
    for elem in elems:
        if elem.element_type != "Dach":
            continue
        meta = parse_attic_meta(getattr(elem, "meta", None))
        if meta.get("side") != side:
            continue
        try:
            local0 = float(meta.get("local0", "nan"))
            local1 = float(meta.get("local1", "nan"))
        except ValueError:
            continue
        share = _opening_overlap_share(center_m, width_m, local0, local1)
        if share <= EPS:
            continue
        delta = min(float(elem.area_m2), opening_area * share)
        elem.area_m2 = max(0.0, float(elem.area_m2) - delta)
        elem.meta = f"{elem.meta or ''}|roof_opening_subtract={tag}:{delta:.6f}"
        target_room = target_room or elem.room_id
    if target_room is not None:
        return target_room
    return next((e.room_id for e in elems if e.element_type == "Dach" and parse_attic_meta(e.meta).get("side") == side), None)


def _add_roof_windows(elems: list[ElementModel], cfg: AtticCfgDTO, model: _RoofModel) -> None:
    win_u = float(DEFAULT_U.get("Fenster", 1.30))
    for idx, spec in enumerate(_roof_window_specs(cfg, model), 1):
        side = str(spec["side"])
        center = float(spec["center"])
        width = float(spec["width"])
        area = float(spec["area"])
        room_id = _subtract_roof_opening(elems, side=side, center_m=center, width_m=width, area_m2=area, tag=f"roof_window_{idx}")
        if room_id is None:
            continue
        elems.append(ElementModel(
            room_id=room_id,
            element_type="Fenster",
            area_m2=area,
            u_w_m2k=win_u,
            factor=1.0,
            floor="DG",
            uid=f"auto_roof_window_{idx}_{side}_{_fmt_num(center)}",
            meta=f"attic_auto|attic_part=roof_window|basis=roof_window|side={side}|boundary=outside|center={center:.6f}|width={width:.6f}",
        ))


def _add_dormers(elems: list[ElementModel], cfg: AtticCfgDTO) -> None:
    try:
        results = build_dormer_results_from_attic_cfg(cfg)
    except Exception:
        return
    for result in results:
        side = str(result.input.roof_side)
        center = float(result.input.center_along_m)
        width = float(result.input.width_m)
        cutout = float(result.areas.cutout_main_roof_m2)
        room_id = _subtract_roof_opening(elems, side=side, center_m=center, width_m=width, area_m2=cutout, tag=f"dormer_{result.input.id}")
        if room_id is None:
            room_id = next((e.room_id for e in elems if e.element_type == "Dach"), "DG")
        elems.extend(dormer_to_auto_elements(result, room_id=room_id, floor="DG"))


def derive_auto_attic_elements(dg_rooms: Sequence[RoomModel], attic_cfg: AtticCfgDTO) -> List[ElementModel]:
    geom = _build_geom_from_cfg(attic_cfg)
    if geom is None:
        return []
    model = _build_roof_model(attic_cfg)

    rooms = [r for r in dg_rooms if str(getattr(r, "floor", "") or "").strip().upper() == "DG"]
    if not rooms:
        return []

    bbox = _dg_bbox(rooms)
    if bbox is None:
        return []
    min_x, min_y, max_x, max_y = bbox
    bbox_w = max(EPS, max_x - min_x)
    bbox_l = max(EPS, max_y - min_y)
    x_scale = float(model.width_m) / bbox_w
    y_scale = float(model.length_m) / bbox_l

    spans = classify_floor_edge_spans(list(rooms))

    out: List[ElementModel] = []
    roof_u = float(getattr(attic_cfg, "u_roof_w_m2k", DEFAULT_U.get("Dach", 0.30)) or DEFAULT_U.get("Dach", 0.30))
    gable_u = float(getattr(attic_cfg, "u_gable_w_m2k", DEFAULT_U.get("Außenwand", DEFAULT_U.get("Aussenwand", 0.45))) or DEFAULT_U.get("Außenwand", DEFAULT_U.get("Aussenwand", 0.45)))
    roof_factor = float(DEFAULT_FACTOR.get('Dach', 1.0))
    roof_boundary = str(getattr(attic_cfg, "roof_boundary", "outside") or "outside").strip().lower()
    roof_boundary_key = "attic_unheated" if roof_boundary == "unheated_attic" else "outside"
    if roof_boundary_key == "attic_unheated":
        default_factor = DIN_BOUNDARY_CONDITIONS["attic_unheated"].factor
        roof_factor *= max(0.0, float(getattr(attic_cfg, "roof_unheated_factor", default_factor) or default_factor))
    zero_roof_gable = bool(getattr(attic_cfg, "zero_roof_gable_transmission", False))

    for s in spans:
        if s.element_type != 'Aussenwand':
            continue
        room = next((r for r in rooms if r.id == s.owner_room_id), None)
        if room is None:
            continue

        if s.orient == 'V':
            if abs(float(s.c) - min_x) <= 1e-6:
                side = 'left'
                local0 = (float(s.a0) - min_y) * y_scale
                local1 = (float(s.a1) - min_y) * y_scale
            elif abs(float(s.c) - max_x) <= 1e-6:
                side = 'right'
                local0 = (float(s.a0) - min_y) * y_scale
                local1 = (float(s.a1) - min_y) * y_scale
            else:
                continue

            if model.ridge_orientation == 'length':
                area = _roof_strip_area(side, local0, local1, model) * float(getattr(model, "roof_line_area_factor", 1.0) or 1.0)
                etype = 'Dach'
                part = f'roof_{side}'
                u_val = roof_u
                factor = roof_factor
                h_val = max(0.0, area / max(EPS, abs(float(s.a1) - float(s.a0))))
            else:
                area = _wall_strip_area(side, local0, local1, model)
                etype = 'Giebelwand'
                part = f'gable_{side}'
                u_val = gable_u
                factor = float(DEFAULT_FACTOR.get('Außenwand', DEFAULT_FACTOR.get('Aussenwand', 1.0)))
                h_val = None
            if zero_roof_gable:
                factor = 0.0

            if area > EPS:
                uid = f"{AUTO_ATTIC_UID_PREFIX}{part}_{room.id}_{_fmt_num(local0)}_{_fmt_num(local1)}"
                boundary_key = roof_boundary_key if etype == 'Dach' else "outside"
                meta = f"attic_auto|attic_part={part}|basis=edge|side={side}|boundary={boundary_key}|local0={local0:.6f}|local1={local1:.6f}|source_uid={s.uid}"
                out.append(ElementModel(
                    room_id=room.id,
                    element_type=etype,
                    area_m2=float(area),
                    u_w_m2k=u_val,
                    factor=factor,
                    floor="DG",
                    x0_m=float(s.c),
                    y0_m=float(s.a0),
                    x1_m=float(s.c),
                    y1_m=float(s.a1),
                    length_m=float(abs(float(s.a1) - float(s.a0))),
                    height_m=h_val,
                    uid=uid,
                    meta=meta,
                ))

        elif s.orient == 'H':
            if abs(float(s.c) - min_y) <= 1e-6:
                side = 'front'
                local0 = (float(s.a0) - min_x) * x_scale
                local1 = (float(s.a1) - min_x) * x_scale
            elif abs(float(s.c) - max_y) <= 1e-6:
                side = 'back'
                local0 = (float(s.a0) - min_x) * x_scale
                local1 = (float(s.a1) - min_x) * x_scale
            else:
                continue

            if model.ridge_orientation == 'length':
                area = _wall_strip_area(side, local0, local1, model)
                etype = 'Giebelwand'
                part = f'gable_{side}'
                u_val = gable_u
                factor = float(DEFAULT_FACTOR.get('Außenwand', DEFAULT_FACTOR.get('Aussenwand', 1.0)))
                h_val = None
            else:
                area = _roof_strip_area(side, local0, local1, model) * float(getattr(model, "roof_line_area_factor", 1.0) or 1.0)
                etype = 'Dach'
                part = f'roof_{side}'
                u_val = roof_u
                factor = roof_factor
                h_val = max(0.0, area / max(EPS, abs(float(s.a1) - float(s.a0))))
            if zero_roof_gable:
                factor = 0.0

            if area <= EPS:
                continue
            uid = f"{AUTO_ATTIC_UID_PREFIX}{part}_{room.id}_{_fmt_num(local0)}_{_fmt_num(local1)}"
            boundary_key = roof_boundary_key if etype == 'Dach' else "outside"
            meta = f"attic_auto|attic_part={part}|basis=edge|side={side}|boundary={boundary_key}|local0={local0:.6f}|local1={local1:.6f}|source_uid={s.uid}"
            out.append(ElementModel(
                room_id=room.id,
                element_type=etype,
                area_m2=float(area),
                u_w_m2k=u_val,
                factor=factor,
                floor="DG",
                x0_m=float(s.a0),
                y0_m=float(s.c),
                x1_m=float(s.a1),
                y1_m=float(s.c),
                length_m=float(abs(float(s.a1) - float(s.a0))),
                height_m=h_val,
                uid=uid,
                meta=meta,
            ))

    _add_roof_windows(out, attic_cfg, model)
    _add_dormers(out, attic_cfg)
    return out


def rebuild_auto_attic_elements(*, rooms: Sequence[RoomModel], elements: List[ElementModel], attic_cfg: AtticCfgDTO) -> None:
    kept = remove_auto_attic_elements(elements)
    dg_rooms = [r for r in rooms if str(getattr(r, "floor", "") or "").strip().upper() == "DG"]
    autos = derive_auto_attic_elements(dg_rooms, attic_cfg)
    elements[:] = kept + autos
