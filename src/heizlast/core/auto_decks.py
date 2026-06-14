from __future__ import annotations

from typing import Iterable, Optional

from ..domain.models import ElementModel, RoomModel

DEFAULT_U_KELLERDECKE_W_M2K = 0.45
DEFAULT_U_EG_GESCHOSSDECKE_W_M2K = 0.30
DEFAULT_U_DG_GESCHOSSDECKE_W_M2K = 0.25


def _norm_str(value: str) -> str:
    return (value or "").strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def _parse_meta(meta: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in str(meta or "").split("|"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def is_auto_deck(e: ElementModel) -> bool:
    meta = getattr(e, "meta", "") or ""
    uid = str(getattr(e, "uid", "") or "")
    return ("auto_deck=1" in meta) or uid.startswith("deck_")


def deck_kind_for_element(e: ElementModel) -> str | None:
    meta = _parse_meta(getattr(e, "meta", "") or "")
    kind = _norm_str(meta.get("deck_kind", ""))
    if kind in {"keller", "geschoss", "speicher"}:
        return kind

    adj_floor = _norm_str(meta.get("adj_floor", ""))
    if adj_floor in {"kg", "ug", "keller"}:
        return "keller"
    if adj_floor in {"dg", "og"}:
        return "geschoss"
    if adj_floor in {"oben", "speicher", "dachraum"}:
        return "speicher"

    boundary = _norm_str(meta.get("boundary", "") or meta.get("boundary_condition", ""))
    if boundary == "basement_unheated":
        return "keller"
    if boundary in {"attic_unheated", "unheated"}:
        return "speicher"
    if boundary in {"interzone", "adjacent_heated"}:
        return "geschoss"

    et = _norm_str(getattr(e, "element_type", "") or "")
    if et in {"kellerdecke", "kgdecke", "kg-decke"} or ("keller" in et and "decke" in et):
        return "keller"
    if et in {"speicherdecke", "dachdecke", "dachraumdecke"} or ("speicher" in et and "decke" in et) or ("dach" in et and "decke" in et):
        return "speicher"
    if et in {"geschossdecke", "zwischendecke"} or ("geschoss" in et and "decke" in et) or ("zwischen" in et and "decke" in et):
        return "geschoss"
    return None


def ensure_auto_decks(
    rooms: Iterable[RoomModel],
    elements: list[ElementModel],
    *,
    u_kellerdecke_w_m2k: float = DEFAULT_U_KELLERDECKE_W_M2K,
    u_eg_geschossdecke_w_m2k: float = DEFAULT_U_EG_GESCHOSSDECKE_W_M2K,
    u_dg_geschossdecke_w_m2k: float = DEFAULT_U_DG_GESCHOSSDECKE_W_M2K,
    t_keller_c: Optional[float] = None,
    t_oben_c: Optional[float] = None,
    u_value_source: str = "",
    boundary_source: str = "",
    auto_deck_assumptions_confirmed: bool = False,
    create_eg_kellerdecke: bool = True,
    create_eg_geschossdecke: bool = True,
    create_dg_speicherdecke: bool = True,
    factor: float = 1.0,
    update_existing: bool = True,
) -> None:
    """
    Erzeugt oder aktualisiert automatische Decken-Elemente.

    Default-Regeln:
      - EG: Kellerdecke + Geschossdecke gegen DG-Mitteltemperatur
      - DG: Speicherdecke gegen unbeheizten Dachraum/oben
      - KG: keine automatische Decke

    Die Regeln bleiben rückwärtskompatibel, schreiben aber DIN-Prüfmetadaten.
    Für einen belastbaren Nachweis müssen die Projektannahmen bestätigt werden.
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

    manual_deck_keys = {
        (str(getattr(e, "room_id", "") or ""), kind)
        for e in elements
        if (kind := deck_kind_for_element(e)) is not None and not is_auto_deck(e)
    }

    def _source_or_default(value: str, default: str) -> str:
        return str(value or "").strip() or default

    def _add(
        room: RoomModel,
        *,
        uid: str,
        etype: str,
        kind: str,
        u_value: float,
        adj_floor: str,
        t_adj_c: Optional[float],
        boundary: str,
        t_source: str,
    ) -> None:
        room_key = (str(getattr(room, "id", "") or ""), kind)
        if room_key in manual_deck_keys:
            existing = by_uid.get(uid)
            if existing is not None and is_auto_deck(existing):
                meta = getattr(existing, "meta", "") or ""
                meta = _set_meta_kv(meta, "auto_suppressed", "1")
                meta = _set_meta_kv(meta, "suppressed_by", "manual_deck")
                existing.meta = meta
            return

        if uid in by_uid:
            if update_existing:
                e = by_uid[uid]
                if is_auto_deck(e):
                    e.element_type = etype
                    e.u_w_m2k = float(u_value)
                    e.factor = float(factor)
                    meta = getattr(e, "meta", "") or ""
                    meta = _set_meta_kv(meta, "auto_deck", "1")
                    meta = _set_meta_kv(meta, "deck_kind", kind)
                    meta = _set_meta_kv(meta, "adj_floor", adj_floor)
                    meta = _set_meta_kv(meta, "boundary", boundary)
                    meta = _set_meta_kv(meta, "area_source", "room_floor_area")
                    meta = _set_meta_kv(meta, "u_source", _source_or_default(u_value_source, "project_auto_deck_default"))
                    meta = _set_meta_kv(meta, "t_source", t_source)
                    meta = _set_meta_kv(meta, "boundary_source", _source_or_default(boundary_source, "project_auto_deck_default"))
                    meta = _set_meta_kv(meta, "assumptions_confirmed", "1" if auto_deck_assumptions_confirmed else "0")
                    meta = _set_meta_kv(meta, "auto_suppressed", None)
                    meta = _set_meta_kv(meta, "suppressed_by", None)
                    if t_adj_c is not None:
                        meta = _set_meta_kv(meta, "t_adj_c", f"{float(t_adj_c):.3f}")
                    else:
                        meta = _set_meta_kv(meta, "t_adj_c", None)
                    e.meta = meta
            return

        area = max(0.0, float(room.w_m or 0.0) * float(room.h_m or 0.0))
        meta_parts = [
            "auto_deck=1",
            f"deck_kind={kind}",
            f"adj_floor={adj_floor}",
            f"boundary={boundary}",
            "area_source=room_floor_area",
            f"u_source={_source_or_default(u_value_source, 'project_auto_deck_default')}",
            f"t_source={t_source}",
            f"boundary_source={_source_or_default(boundary_source, 'project_auto_deck_default')}",
            f"assumptions_confirmed={'1' if auto_deck_assumptions_confirmed else '0'}",
        ]
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
            if create_eg_kellerdecke:
                _add(
                    r,
                    uid=f"deck_{r.id}_KG",
                    etype="Kellerdecke",
                    kind="keller",
                    u_value=u_kellerdecke_w_m2k,
                    adj_floor="KG",
                    t_adj_c=float(t_keller_c) if t_keller_c is not None else None,
                    boundary="basement_unheated",
                    t_source="project_t_keller_c" if t_keller_c is not None else "calc_t_keller_c",
                )
            if create_eg_geschossdecke:
                t_adj = t_dg_mean if t_dg_mean is not None else float(getattr(r, "t_inside_c", 0.0) or 0.0)
                _add(
                    r,
                    uid=f"deck_{r.id}_DG",
                    etype="Geschossdecke",
                    kind="geschoss",
                    u_value=u_eg_geschossdecke_w_m2k,
                    adj_floor="DG",
                    t_adj_c=t_adj,
                    boundary="interzone",
                    t_source="dg_mean_room_temperature" if t_dg_mean is not None else "same_room_temperature_fallback",
                )
        elif floor == "DG":
            if create_dg_speicherdecke:
                _add(
                    r,
                    uid=f"deck_{r.id}_OBEN",
                    etype="Speicherdecke",
                    kind="speicher",
                    u_value=u_dg_geschossdecke_w_m2k,
                    adj_floor="OBEN",
                    t_adj_c=float(t_oben_c) if t_oben_c is not None else None,
                    boundary="attic_unheated",
                    t_source="project_t_oben_c" if t_oben_c is not None else "calc_t_oben_c",
                )
