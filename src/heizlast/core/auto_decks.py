from __future__ import annotations

from typing import Iterable, Optional

from ..domain.models import ElementModel, RoomModel

DEFAULT_U_KELLERDECKE_W_M2K = 0.45
DEFAULT_U_EG_GESCHOSSDECKE_W_M2K = 0.30
DEFAULT_U_DG_GESCHOSSDECKE_W_M2K = 0.25


def ensure_auto_decks(
    rooms: Iterable[RoomModel],
    elements: list[ElementModel],
    *,
    u_kellerdecke_w_m2k: float = DEFAULT_U_KELLERDECKE_W_M2K,
    u_eg_geschossdecke_w_m2k: float = DEFAULT_U_EG_GESCHOSSDECKE_W_M2K,
    u_dg_geschossdecke_w_m2k: float = DEFAULT_U_DG_GESCHOSSDECKE_W_M2K,
    factor: float = 1.0,
    update_existing: bool = True,
) -> None:
    """
    Erzeugt oder aktualisiert automatische Decken-Elemente.

    Regeln:
      - EG: Kellerdecke + Geschossdecke gegen DG-Mitteltemperatur
      - DG: Speicherdecke gegen unbeheizten Dachraum/oben
      - KG: keine automatische Decke
    """
    rooms = list(rooms)

    dg_temps: list[float] = []
    for r in rooms:
        if (getattr(r, "floor", "") or "").strip().upper() == "DG" and getattr(r, "t_inside_c", None) is not None:
            try:
                dg_temps.append(float(r.t_inside_c))
            except Exception:
                pass
    t_dg_mean = (sum(dg_temps) / len(dg_temps)) if dg_temps else None

    by_uid: dict[str, ElementModel] = {str(getattr(e, "uid", "") or ""): e for e in elements if getattr(e, "uid", None)}

    def _is_auto_deck(e: ElementModel) -> bool:
        meta = getattr(e, "meta", "") or ""
        uid = str(getattr(e, "uid", "") or "")
        return ("auto_deck=1" in meta) or uid.startswith("deck_")

    def _set_meta_kv(meta: str, key: str, value: Optional[str]) -> str:
        parts = [p for p in (meta or "").split("|") if p.strip()]
        out = []
        found = False
        for p in parts:
            if p.startswith(key + "="):
                found = True
                if value is not None:
                    out.append(f"{key}={value}")
            else:
                out.append(p)
        if not found and value is not None:
            out.append(f"{key}={value}")
        return "|".join(out)

    def _add(room: RoomModel, *, uid: str, etype: str, u_value: float, adj_floor: str, t_adj_c: Optional[float]) -> None:
        if uid in by_uid:
            if update_existing:
                e = by_uid[uid]
                if _is_auto_deck(e):
                    e.element_type = etype
                    e.u_w_m2k = float(u_value)
                    e.factor = float(factor)
                    meta = getattr(e, "meta", "") or ""
                    meta = _set_meta_kv(meta, "auto_deck", "1")
                    meta = _set_meta_kv(meta, "adj_floor", adj_floor)
                    if t_adj_c is not None:
                        meta = _set_meta_kv(meta, "t_adj_c", f"{float(t_adj_c):.3f}")
                    e.meta = meta
            return

        area = max(0.0, float(room.w_m or 0.0) * float(room.h_m or 0.0))
        meta_parts = ["auto_deck=1", f"adj_floor={adj_floor}"]
        if t_adj_c is not None:
            meta_parts.append(f"t_adj_c={float(t_adj_c):.3f}")

        elements.append(
            ElementModel(
                room_id=room.id,
                element_type=etype,
                area_m2=area,
                u_w_m2k=float(u_value),
                factor=float(factor),
                floor=getattr(room, "floor", None),
                x0_m=None,
                y0_m=None,
                x1_m=None,
                y1_m=None,
                length_m=None,
                height_m=None,
                uid=uid,
                meta="|".join(meta_parts),
            )
        )
        by_uid[uid] = elements[-1]

    for r in rooms:
        floor = (getattr(r, "floor", "") or "").strip().upper()
        if floor == "EG":
            _add(r, uid=f"deck_{r.id}_KG", etype="Kellerdecke", u_value=u_kellerdecke_w_m2k, adj_floor="KG", t_adj_c=None)
            t_adj = t_dg_mean if t_dg_mean is not None else float(getattr(r, "t_inside_c", 0.0) or 0.0)
            _add(r, uid=f"deck_{r.id}_DG", etype="Geschossdecke", u_value=u_eg_geschossdecke_w_m2k, adj_floor="DG", t_adj_c=t_adj)
        elif floor == "DG":
            _add(r, uid=f"deck_{r.id}_OBEN", etype="Speicherdecke", u_value=u_dg_geschossdecke_w_m2k, adj_floor="OBEN", t_adj_c=None)
            e_top = by_uid.get(f"deck_{r.id}_OBEN")
            if e_top is not None:
                e_top.meta = _set_meta_kv(getattr(e_top, "meta", "") or "", "deck_kind", "speicher")
