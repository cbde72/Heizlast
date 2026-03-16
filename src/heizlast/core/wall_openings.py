from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .anchors import parse_edge_anchor, parse_meta
from ..domain.models import ElementModel, RoomModel


@dataclass
class WallOpeningData:
    offset_m: float
    width_m: float
    sill_m: float
    height_m: float
    label: str = "Fenster"
    opening_type: str = "window"


def _safe_float(v, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _meta_float(parts: dict[str, str], *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        if key in parts and str(parts.get(key)).strip() != "":
            try:
                return float(parts.get(key))
            except Exception:
                continue
    return default


def opening_geometry_from_element(element: ElementModel, *, default_sill_m: float = 0.90) -> tuple[float, float]:
    parts = parse_meta(getattr(element, "meta", None))
    et_lower = str(getattr(element, "element_type", "") or "").strip().lower()
    is_door = ("tür" in et_lower) or ("tuer" in et_lower) or ("door" in et_lower)

    height_m = max(0.01, _safe_float(getattr(element, "height_m", None), default=1.0 if not is_door else 2.01))

    # Explicit vertical parameters from meta have priority.
    sill_m = _meta_float(
        parts,
        "sill_m", "sill", "parapet_m", "parapet", "bruestung_m", "bruestung",
        "brüstung_m", "brüstung", "okff_sill_m", "okff_brustung_m", "okff_brüstung_m",
        default=None,
    )
    if sill_m is None:
        top_m = _meta_float(
            parts,
            "head_m", "lintel_m", "top_m", "opening_top_m", "okff_top_m",
            default=None,
        )
        if top_m is not None:
            sill_m = max(0.0, float(top_m) - float(height_m))

    if sill_m is None:
        sill_m = 0.0 if is_door else float(default_sill_m)

    return float(max(0.0, sill_m)), float(height_m)


def wall_openings_for_element(
    wall: ElementModel,
    elements: Iterable[ElementModel],
    *,
    room: RoomModel | None = None,
    default_window_sill_m: float = 0.90,
) -> List[WallOpeningData]:
    openings: List[WallOpeningData] = []
    wall_uid = str(getattr(wall, "uid", "") or "")
    wx0 = float(min(getattr(wall, "x0_m", 0.0) or 0.0, getattr(wall, "x1_m", 0.0) or 0.0))
    wy0 = float(min(getattr(wall, "y0_m", 0.0) or 0.0, getattr(wall, "y1_m", 0.0) or 0.0))
    horizontal = abs(float((getattr(wall, "y1_m", 0.0) or 0.0) - (getattr(wall, "y0_m", 0.0) or 0.0))) <= abs(float((getattr(wall, "x1_m", 0.0) or 0.0) - (getattr(wall, "x0_m", 0.0) or 0.0)))

    for e in list(elements or []):
        et_raw = str(getattr(e, "element_type", "") or "")
        et = et_raw.strip().lower()
        is_window = et == "fenster"
        is_door = ("tür" in et) or ("tuer" in et) or ("door" in et)
        if not (is_window or is_door):
            continue

        anchor = parse_edge_anchor(getattr(e, "meta", None))
        parent_uid = str(anchor.get("parent") or "")
        if wall_uid and parent_uid == wall_uid:
            offset = float(anchor.get("s") or 0.0) - 0.5 * float(getattr(e, "length_m", 0.0) or 0.0)
        else:
            if getattr(e, "room_id", None) != getattr(wall, "room_id", None):
                continue
            ex0 = float(min(getattr(e, "x0_m", 0.0) or 0.0, getattr(e, "x1_m", 0.0) or 0.0))
            ey0 = float(min(getattr(e, "y0_m", 0.0) or 0.0, getattr(e, "y1_m", 0.0) or 0.0))
            if horizontal:
                if abs(float(getattr(e, "y0_m", 0.0) or 0.0) - float(getattr(wall, "y0_m", 0.0) or 0.0)) > 1e-6:
                    continue
                offset = ex0 - wx0
            else:
                if abs(float(getattr(e, "x0_m", 0.0) or 0.0) - float(getattr(wall, "x0_m", 0.0) or 0.0)) > 1e-6:
                    continue
                offset = ey0 - wy0

        sill_m, height_m = opening_geometry_from_element(
            e,
            default_sill_m=default_window_sill_m,
        )
        openings.append(WallOpeningData(
            offset_m=max(0.0, float(offset)),
            width_m=max(0.01, float(getattr(e, "length_m", 0.0) or 0.0)),
            sill_m=sill_m,
            height_m=max(0.01, float(height_m)),
            label=et_raw or ("Tür" if is_door else "Fenster"),
            opening_type="door" if is_door else "window",
        ))
    openings.sort(key=lambda o: (o.offset_m, o.width_m, o.label.lower()))
    return openings
