from __future__ import annotations
import csv
from pathlib import Path
from typing import List, Optional
from ..domain.models import ElementModel
from .config import CSV_DELIMITER, CSV_ENCODING ,  DEFAULT_U, usage_defaults
from ..domain.models import RoomModel

def _f(x: str) -> float:
    return float(str(x).strip().replace(",", "."))

def _opt(row: dict, key: str) -> Optional[str]:
    v = row.get(key)
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None

def load_rooms(path: str, delimiter: str = CSV_DELIMITER) -> List[RoomModel]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding=CSV_ENCODING, newline="") as f:
        r = csv.DictReader(f, delimiter=delimiter)
        rows = list(r)
    rooms: List[RoomModel] = []
    for row in rows:
        rid = (row.get("id") or "").strip()
        if not rid:
            continue
        floor = (row.get("floor") or "EG").strip().upper()
        name = (row.get("name") or rid).strip()

        x = _f(row.get("x_m", "0"))
        y = _f(row.get("y_m", "0"))

        # Flexible dims: prefer w_m/h_m else length_m/width_m else area based
        w = row.get("w_m")
        h = row.get("h_m")
        if w is not None and str(w).strip() and h is not None and str(h).strip():
            w_m = _f(w); h_m = _f(h)
        else:
            lm = row.get("length_m"); wm = row.get("width_m")
            if lm is not None and str(lm).strip() and wm is not None and str(wm).strip():
                w_m = _f(lm); h_m = _f(wm)
            else:
                area = row.get("area_m2")
                if area is not None and str(area).strip() and lm is not None and str(lm).strip():
                    w_m = _f(lm)
                    h_m = _f(area) / max(w_m, 1e-9)
                elif area is not None and str(area).strip() and wm is not None and str(wm).strip():
                    h_m = _f(wm)
                    w_m = _f(area) / max(h_m, 1e-9)
                else:
                    w_m = 4.0; h_m = 3.0

        height_m = _f(row.get("height_m", "2.5"))
        polygon_m = _opt(row, "polygon_m")
        usage_type = _opt(row, "usage_type")
        t_in_raw = _opt(row, "t_inside_c")
        n_raw = _opt(row, "air_change_1ph")
        ud = usage_defaults(usage_type) if usage_type else None
        t_in = _f(t_in_raw) if t_in_raw is not None else float((ud or {}).get("t_inside_c", 20.0))
        n = _f(row.get("air_change_1ph", "0.5"))
        vol = row.get("volume_m3")
        if vol is not None and str(vol).strip():
            vol_m3 = _f(vol)
        else:
            vol_m3 = w_m*h_m*height_m

        rm = RoomModel(
            id=rid, floor=floor, name=name,
            x_m=x, y_m=y, w_m=w_m, h_m=h_m,
            height_m=height_m, t_inside_c=t_in,
            air_change_1ph=n, volume_m3=vol_m3,
            polygon_m=polygon_m
        )
        rooms.append(rm)
    return rooms

def save_rooms(path: str, rooms: List[RoomModel], delimiter: str = CSV_DELIMITER) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    header = ["id","floor","name","x_m","y_m","w_m","h_m","polygon_m","length_m","width_m","area_m2","perimeter_m",
              "height_m","t_inside_c","volume_m3","air_change_1ph","usage_type"]
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(header)
        for r in rooms:
            r.recompute_volume()
            w.writerow([
                r.id, r.floor, r.name,
                f"{r.x_m:.3f}".replace(".", ","), f"{r.y_m:.3f}".replace(".", ","),
                f"{r.w_m:.3f}".replace(".", ","), f"{r.h_m:.3f}".replace(".", ","),
                (getattr(r, "polygon_m", None) or ""),
                f"{r.w_m:.3f}".replace(".", ","), f"{r.h_m:.3f}".replace(".", ","),
                f"{r.area_m2():.3f}".replace(".", ","), f"{r.perimeter_m():.3f}".replace(".", ","),
                f"{r.height_m:.3f}".replace(".", ","), f"{r.t_inside_c:.1f}".replace(".", ","),
                f"{r.volume_m3:.3f}".replace(".", ","), f"{r.air_change_1ph:.3f}".replace(".", ","),
                (getattr(r, "usage_type", None) or ""),
            ])

def load_elements(path: str, delimiter: str = CSV_DELIMITER) -> List[ElementModel]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding=CSV_ENCODING, newline="") as f:
        r = csv.DictReader(f, delimiter=delimiter)
        rows = list(r)
    els: List[ElementModel] = []
    for row in rows:
        room_id = (row.get("room_id") or "").strip()
        if not room_id:
            continue
        et = (row.get("element_type") or "Bauteil").strip()
        area = _f(row.get("area_m2", "0"))
        u = _f(row.get("u_w_m2k", "0"))
        factor = _f(row.get("factor", "1.0"))

        e = ElementModel(room_id=room_id, element_type=et, area_m2=area, u_w_m2k=u, factor=factor)
        e.floor = _opt(row, "floor")
        for k in ("x0_m","y0_m","x1_m","y1_m","length_m","height_m","label_x_m","label_y_m"):
            v = _opt(row, k)
            if v is None:
                continue
            setattr(e, k, _f(v))
        e.uid = _opt(row, "uid")
        e.meta = _opt(row, "meta")
        els.append(e)
    return els

def save_elements(path: str, elements: List[ElementModel], delimiter: str = CSV_DELIMITER) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    header = ["room_id","element_type","area_m2","u_w_m2k","factor","floor",
              "x0_m","y0_m","x1_m","y1_m","length_m","height_m","label_x_m","label_y_m","uid","meta"]
    
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(header)
        for e in elements:
            # --- U defaulting (no room context needed) ---
            try:
                U = float(getattr(e, "u_w_m2k", 0.0) or 0.0)
            except Exception:
                U = 0.0
            if U <= 1e-9:
                et = str(getattr(e, "element_type", "") or "").strip()
                # try exact type; fallback to generic keys used in config
                U_def = None
                try:
                    U_def = DEFAULT_U.get(et, None)
                    if U_def is None:
                        # common fallbacks (keep conservative, don't guess too much)
                        if "außen" in et.lower() or "aussen" in et.lower():
                            U_def = DEFAULT_U.get("Aussenwand", None)
                        elif "fenster" in et.lower():
                            U_def = DEFAULT_U.get("Fenster", None)
                        elif "keller" in et.lower() and "deck" in et.lower():
                            U_def = DEFAULT_U.get("Kellerdecke", None)
                        elif "geschoss" in et.lower() and "deck" in et.lower():
                            U_def = DEFAULT_U.get("Geschossdecke", None)
                except Exception:
                    U_def = None

                if U_def is not None:
                    try:
                        e.u_w_m2k = float(U_def)
                    except Exception:
                        pass 
            # --- derive missing geometry-derived fields (safe, no room context here) ---
            # length
            try:
                L = float(getattr(e, "length_m", 0.0) or 0.0)
            except Exception:
                L = 0.0
            if (L <= 1e-9) and getattr(e, "has_geometry", lambda: False)():
                try:
                    L2 = e.compute_length()
                    if L2 is not None and float(L2) > 1e-9:
                        e.length_m = float(L2)
                        L = float(L2)
                except Exception:
                    pass

            # area = length * height for line-elements if missing/zero
            try:
                A = float(getattr(e, "area_m2", 0.0) or 0.0)
            except Exception:
                A = 0.0
            try:
                H = float(getattr(e, "height_m", 0.0) or 0.0)
            except Exception:
                H = 0.0
            if (A <= 1e-9) and (L > 1e-9) and (H > 1e-9):
                try:
                    e.area_m2 = float(L * H)
                except Exception:
                    pass                
            
    
            w.writerow([
                e.room_id, e.element_type,
                ("" if e.area_m2 is None else f"{e.area_m2:.3f}".replace(".", ",")),
                ("" if e.u_w_m2k is None else f"{e.u_w_m2k:.3f}".replace(".", ",")),
                ("" if e.factor is None else f"{e.factor:.3f}".replace(".", ",")),
                e.floor or "",
                "" if e.x0_m is None else f"{e.x0_m:.3f}".replace(".", ","),
                "" if e.y0_m is None else f"{e.y0_m:.3f}".replace(".", ","),
                "" if e.x1_m is None else f"{e.x1_m:.3f}".replace(".", ","),
                "" if e.y1_m is None else f"{e.y1_m:.3f}".replace(".", ","),
                "" if e.length_m is None else f"{e.length_m:.3f}".replace(".", ","),
                "" if e.height_m is None else f"{e.height_m:.3f}".replace(".", ","),
                "" if e.label_x_m is None else f"{e.label_x_m:.3f}".replace(".", ","),
                "" if e.label_y_m is None else f"{e.label_y_m:.3f}".replace(".", ","),
                e.uid or "", e.meta or ""
            ])