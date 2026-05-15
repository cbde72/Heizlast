from __future__ import annotations

from typing import Iterable, List

from ..configs.project_config import AtticCfgDTO, DormerCfgDTO
from ..domain.models import ElementModel
from .config import DEFAULT_FACTOR, DEFAULT_U
from .dormer_geometry import DormerGeometry, DormerInput, DormerResult, RoofContext

_DORMER_TYPE_MAP = {
    "schleppgaube": "shed",
    "satteldachgaube": "gable",
    "flachdachgaube": "flat",
    "shed": "shed",
    "gable": "gable",
    "flat": "flat",
}


def roof_context_from_attic_cfg(cfg: AtticCfgDTO) -> RoofContext:
    return RoofContext(
        roof_type=str(getattr(cfg, "roof_type", "satteldach") or "satteldach").strip().lower(),
        ridge_direction=str(getattr(cfg, "ridge_orientation", "length") or "length").strip().lower(),
        building_length_m=float(getattr(cfg, "building_length_m", 0.0) or 0.0),
        building_width_m=float(getattr(cfg, "building_width_m", 0.0) or 0.0),
        eaves_overhang_m=float(getattr(cfg, "eave_overhang_m", getattr(cfg, "roof_overhang_m", 0.0)) or 0.0),
        gable_overhang_m=float(getattr(cfg, "gable_overhang_m", getattr(cfg, "roof_overhang_m", 0.0)) or 0.0),
        roof_pitch_deg_left=float(getattr(cfg, "roof_pitch_deg", 35.0) or 35.0),
        roof_pitch_deg_right=float(getattr(cfg, "roof_pitch_deg", 35.0) or 35.0),
    )


def dormer_inputs_from_attic_cfg(cfg: AtticCfgDTO) -> list[DormerInput]:
    items = list(getattr(cfg, "dormers", []) or [])
    ridge_direction = str(getattr(cfg, "ridge_orientation", "length") or "length").strip().lower()
    default_side = "right" if ridge_direction == "length" else "back"
    along_span_m = float(getattr(cfg, "building_length_m", 0.0) or 0.0) if ridge_direction == "length" else float(getattr(cfg, "building_width_m", 0.0) or 0.0)
    out: list[DormerInput] = []
    for idx, item in enumerate(items, 1):
        if not isinstance(item, DormerCfgDTO):
            continue
        typ = _DORMER_TYPE_MAP.get(str(item.dormer_type or "").strip().lower(), None)
        if not typ:
            continue
        center = float(item.center_along_m)
        if center <= 0.0 and along_span_m > 0.0:
            center = 0.5 * along_span_m
        out.append(DormerInput(
            id=str(item.id or f"dormer_{idx}"),
            dormer_type=typ,
            roof_side=str(item.roof_side or default_side).strip().lower(),
            center_along_m=center,
            width_m=float(item.width_m),
            depth_m=float(item.depth_m),
            front_height_m=float(item.front_height_m),
            window_count=int(item.window_count),
            window_width_m=float(item.window_width_m),
            window_height_m=float(item.window_height_m),
            sill_height_m=float(item.sill_height_m),
            roof_pitch_deg=float(item.roof_pitch_deg) if item.roof_pitch_deg is not None else None,
            min_edge_clearance_m=float(item.min_edge_clearance_m),
        ))
    return out


def build_dormer_results_from_attic_cfg(cfg: AtticCfgDTO) -> list[DormerResult]:
    roof = roof_context_from_attic_cfg(cfg)
    engine = DormerGeometry(roof)
    return [engine.build(item) for item in dormer_inputs_from_attic_cfg(cfg)]


def dormer_cutout_area_total(results: Iterable[DormerResult]) -> float:
    return sum(float(r.areas.cutout_main_roof_m2) for r in results)


def dormer_to_auto_elements(result: DormerResult, *, room_id: str = "DG", floor: str = "DG") -> List[ElementModel]:
    elems: list[ElementModel] = []
    wall_factor = float(DEFAULT_FACTOR.get("Außenwand", DEFAULT_FACTOR.get("Aussenwand", 1.0)))
    roof_factor = float(DEFAULT_FACTOR.get("Dach", 1.0))
    wall_u = float(DEFAULT_U.get("Außenwand", DEFAULT_U.get("Aussenwand", 0.45)))
    roof_u = float(DEFAULT_U.get("Dach", 0.30))
    win_u = float(DEFAULT_U.get("Fenster", 1.30))

    if result.areas.front_wall_net_m2 > 0:
        elems.append(ElementModel(room_id=room_id, element_type="Außenwand", area_m2=result.areas.front_wall_net_m2, u_w_m2k=wall_u, factor=wall_factor, floor=floor, uid=f"auto_dormer_front_{result.input.id}", meta=f"dormer_auto|part=front|dormer_id={result.input.id}"))
    side_each = result.areas.side_walls_net_m2 / 2.0
    if side_each > 0:
        elems.append(ElementModel(room_id=room_id, element_type="Außenwand", area_m2=side_each, u_w_m2k=wall_u, factor=wall_factor, floor=floor, uid=f"auto_dormer_side_left_{result.input.id}", meta=f"dormer_auto|part=side_left|dormer_id={result.input.id}"))
        elems.append(ElementModel(room_id=room_id, element_type="Außenwand", area_m2=side_each, u_w_m2k=wall_u, factor=wall_factor, floor=floor, uid=f"auto_dormer_side_right_{result.input.id}", meta=f"dormer_auto|part=side_right|dormer_id={result.input.id}"))
    if result.areas.dormer_roof_m2 > 0:
        elems.append(ElementModel(room_id=room_id, element_type="Dach", area_m2=result.areas.dormer_roof_m2, u_w_m2k=roof_u, factor=roof_factor, floor=floor, uid=f"auto_dormer_roof_{result.input.id}", meta=f"dormer_auto|part=roof|dormer_id={result.input.id}"))
    if result.areas.window_area_m2 > 0:
        elems.append(ElementModel(room_id=room_id, element_type="Fenster", area_m2=result.areas.window_area_m2, u_w_m2k=win_u, factor=1.0, floor=floor, uid=f"auto_dormer_window_{result.input.id}", meta=f"dormer_auto|part=window|dormer_id={result.input.id}"))
    return elems
