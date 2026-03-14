# element_access.py
from __future__ import annotations
from typing import Iterable, List, Optional, Set

# Importpfade an dein Package anpassen, falls nötig:
from ..domain.models import ElementModel


def meta_rooms(meta: str) -> Set[str]:
    """
    Parse meta string (pipe-separated) and return set of room IDs listed in rooms=...
    Example meta: "auto_contour|rooms=R1,R2|line=H:0.000"
    """
    out: Set[str] = set()
    try:
        if not meta:
            return out
        for part in str(meta).split("|"):
            part = part.strip()
            if part.startswith("rooms="):
                raw = part.split("=", 1)[1].strip()
                out |= {x.strip() for x in raw.split(",") if x.strip()}
                return out
    except Exception:
        pass
    return out


def element_belongs_to_room(e: ElementModel, room_id: str) -> bool:
    """True if element is owned by room_id or references it via meta rooms=..."""
    try:
        if getattr(e, "room_id", None) == room_id:
            return True
        m = getattr(e, "meta", "") or ""
        return room_id in meta_rooms(m)
    except Exception:
        return False


def get_room_elements(elements: Iterable[ElementModel], room_id: str) -> List[ElementModel]:
    """
    Central resolver: returns all elements relevant to the given room.
    - Includes owned elements (e.room_id == room_id)
    - Includes shared elements via meta rooms=...
    - Deduplicates by uid if present
    """
    out: List[ElementModel] = []
    seen_uid: Set[str] = set()

    for e in elements:
        if not element_belongs_to_room(e, room_id):
            continue

        uid = str(getattr(e, "uid", "") or "")
        if uid:
            if uid in seen_uid:
                continue
            seen_uid.add(uid)

        out.append(e)

    return out


def element_axis_length_from_geometry(e: ElementModel, tol: float = 1e-6) -> Optional[float]:
    """
    Returns axis-aligned length from geometry (preferred):
    H => |dx|, V => |dy|, else hypot(dx,dy)
    Returns None if no geometry.
    """
    if not getattr(e, "has_geometry", lambda: False)():
        return None
    try:
        x0 = float(e.x0_m); y0 = float(e.y0_m)
        x1 = float(e.x1_m); y1 = float(e.y1_m)
    except Exception:
        return None

    dx = x1 - x0
    dy = y1 - y0

    if abs(dx) <= tol and abs(dy) <= tol:
        return 0.0
    if abs(dy) <= tol and abs(dx) > tol:
        return abs(dx)
    if abs(dx) <= tol and abs(dy) > tol:
        return abs(dy)
    # fallback for non-axis-aligned
    return (dx * dx + dy * dy) ** 0.5