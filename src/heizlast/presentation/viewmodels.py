from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from ..core.element_metrics import ElementMetricsService
from ..domain.models import ElementModel

@dataclass(frozen=True)
class ElementListRow:
    uid: str
    label: str
    tooltip: str = ""
    sort_key: str = ""


def format_element_row(e: ElementModel, metrics: Optional[ElementMetricsService] = None) -> ElementListRow:
    if metrics is not None:
        try:
            metrics.ensure_metrics(e)
        except Exception:
            pass

    uid = str(getattr(e, "uid", "") or "")
    et = str(getattr(e, "element_type", "") or "Element")
    name = str(getattr(e, "name", "") or "")
    room_id = str(getattr(e, "room_id", "") or "")

    l_val = float(getattr(e, "length_m", 0.0) or 0.0)
    a_val = float(getattr(e, "area_m2", 0.0) or 0.0)
    u_val = float(getattr(e, "u_w_m2k", 0.0) or 0.0)
    psi = float(getattr(e, "psi_w_mk", 0.0) or 0.0)
    fac = float(getattr(e, "factor", 1.0) or 1.0)
    h_val = float(getattr(e, "height_m", 0.0) or 0.0)
    floor = str(getattr(e, "floor", "") or "")

    # Compact label for list
    parts = [f"{et}: {a_val:.2f} m²", f"L {l_val:.2f} m", f"U {u_val:.2f}"]
    if abs(psi) > 1e-9:
        parts.append(f"ψ {psi:.2f}")
    if abs(fac - 1.0) > 1e-6:
        parts.append(f"f {fac:.2f}")

    label = " (".join([parts[0], ", ".join(parts[1:])]) + ")"

    tip_lines = []
    if name:
        tip_lines.append(f"Name: {name}")
    if room_id:
        tip_lines.append(f"Room: {room_id}")
    if floor:
        tip_lines.append(f"Floor: {floor}")
    tip_lines.append(f"UID: {uid}")
    if h_val > 0:
        tip_lines.append(f"Height: {h_val:.2f} m")
    tooltip = "\n".join(tip_lines)

    sort_key = f"{et.lower()}|{room_id}|{uid}"
    return ElementListRow(uid=uid, label=label, tooltip=tooltip, sort_key=sort_key)


def build_element_rows(elements: Iterable[ElementModel], metrics: Optional[ElementMetricsService] = None) -> List[ElementListRow]:
    rows = []
    for e in elements:
        uid = str(getattr(e, "uid", "") or "")
        if not uid:
            continue
        rows.append(format_element_row(e, metrics=metrics))
    rows.sort(key=lambda r: r.sort_key)
    return rows
