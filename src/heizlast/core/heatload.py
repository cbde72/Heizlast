
from __future__ import annotations

"""
heatload.py — Heizlastberechnung (Tool-intern), inkl. optionaler Wärmebrücken-Zuschläge
====================================================================================

Ziele dieses Moduls
-------------------
- Reproduzierbare, transparente Heizlastberechnung pro Raum.
- Saubere Trennung zwischen:
  * Geometrie (Innenmaße, Flächen)
  * Transmission (U·A·ΔT·f)
  * Lüftung (c_air·n·V·ΔT)
  * Wärmebrücken (optional) nach DIN-üblichen vereinfachten Zuschlagsmodellen

WICHTIGER HINWEIS (DIN EN 12831 / DIN-Praxis)
---------------------------------------------
DIN EN 12831-1 verweist für Wärmebrücken in der Praxis auf:
- detaillierte ψ-Werte (linear) nach DIN EN ISO 14683 / DIN 4108 Beiblatt etc. oder
- vereinfachte Zuschläge (z.B. ΔU_WB) auf die Hüllfläche.

Dieses Tool implementiert bewusst ein transparentes, parametrierbares Modell:
- ΔU-Methode:  Φ_WB = ΔU_WB · A_envelope · ΔT
- ψ-Methode:   Φ_WB = Σ (ψ_i · L_i · ΔT)
- Prozent:     Φ_WB = p · Φ_trans

Das ist *konformitätsnah* als Rechenmodell, ersetzt aber nicht automatisch die
normative Detailmodellierung (ψ-Katalog, Anschlussdetails) ohne passende Eingabedaten.
"""

import re
from typing import Dict, List, Optional, Tuple

from .anchors import parse_edge_anchor
from .auto_decks import (
    DEFAULT_U_DG_GESCHOSSDECKE_W_M2K,
    DEFAULT_U_EG_GESCHOSSDECKE_W_M2K,
    DEFAULT_U_KELLERDECKE_W_M2K,
    deck_kind_for_element,
    ensure_auto_decks,
    is_auto_deck,
)
from .config import DEFAULT_U, VentilationCfg
from .floor_area import calc_floor_living_area_by_floor, render_floor_living_area_plot_png
from .ground_model import GroundModelCfg, _effective_ground_temp_for_cfg, _is_ground_element
from .din_boundary import boundary_from_meta, boundary_label_for_bucket, canonical_bucket
from .heatload_types import (
    EPS,
    INNER_WALL_TYPES,
    OUTER_WALL_TYPES,
    WALL_THICKNESS_INNER_M,
    WALL_THICKNESS_OUTER_M,
    is_door_type,
    is_opening_type,
    is_window_type,
    FloorAreaMode,
    RoomInnerGeometry,
    ThermalBridgeCfg,
    ThicknessMode,
    meta_get_float as _meta_get_float,
    normalize_element_type,
)
from ..domain.models import ElementModel, RoomModel

__all__ = [
    "DEFAULT_U_DG_GESCHOSSDECKE_W_M2K",
    "DEFAULT_U_EG_GESCHOSSDECKE_W_M2K",
    "DEFAULT_U_KELLERDECKE_W_M2K",
    "FloorAreaMode",
    "ThermalBridgeCfg",
    "ThicknessMode",
    "calc_floor_living_area_by_floor",
    "calc_heatloads",
    "ensure_auto_decks",
    "render_floor_living_area_plot_png",
]


# ---------------------------------------------------------------------------
# Public constants/types are imported from heatload_types and auto_decks.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Geometrie-Helfer
# ---------------------------------------------------------------------------

def _axis_aligned_line(e: ElementModel) -> Optional[Tuple[str, float, float, float]]:
    """Return (orient, c, a0, a1) for axis-aligned element geometry."""
    if not e.has_geometry():
        return None
    x0, y0, x1, y1 = float(e.x0_m), float(e.y0_m), float(e.x1_m), float(e.y1_m)
    if abs(y0 - y1) <= EPS and abs(x0 - x1) > EPS:
        a0, a1 = (x0, x1) if x0 <= x1 else (x1, x0)
        return ("h", y0, a0, a1)
    if abs(x0 - x1) <= EPS and abs(y0 - y1) > EPS:
        a0, a1 = (y0, y1) if y0 <= y1 else (y1, y0)
        return ("v", x0, a0, a1)
    return None


def _window_height_m(w: ElementModel) -> float:
    """Prefer height_m else infer from area/length."""
    if w.height_m is not None and float(w.height_m) > 0:
        return float(w.height_m)
    L = _opening_width_m(w)
    if L is None or L <= EPS:
        return 0.0
    if w.area_m2 is None:
        return 0.0
    return max(0.0, float(w.area_m2) / max(float(L), EPS))


def _positive_float(value: object) -> Optional[float]:
    try:
        v = float(value)
    except Exception:
        return None
    return v if v > EPS else None


def _opening_width_m(w: ElementModel) -> Optional[float]:
    direct = _positive_float(getattr(w, "length_m", None))
    if direct is not None:
        return direct
    try:
        computed = _positive_float(w.compute_length())
    except Exception:
        computed = None
    if computed is not None:
        return computed
    try:
        anchor = parse_edge_anchor(getattr(w, "meta", None))
        anchored = _positive_float(anchor.get("w"))
    except Exception:
        anchored = None
    if anchored is not None:
        return anchored
    height = _positive_float(getattr(w, "height_m", None))
    area = _positive_float(getattr(w, "area_m2", None))
    if height is not None and area is not None:
        return area / max(height, EPS)
    return None


def _opening_height_m(w: ElementModel) -> float:
    if not is_door_type(getattr(w, "element_type", "")):
        return _window_height_m(w)
    if w.height_m is not None and float(w.height_m) > 0:
        return float(w.height_m)
    L = _opening_width_m(w)
    if L is not None and L > EPS and w.area_m2 is not None and float(w.area_m2) > EPS:
        return max(0.01, float(w.area_m2) / max(float(L), EPS))
    return 2.01


def _anchored_opening_interval_on_wall(
    wall: ElementModel,
    opening: ElementModel,
    orient: str,
    wa0: float,
    wa1: float,
) -> Optional[Tuple[float, float, float]]:
    wall_uid = str(getattr(wall, "uid", "") or "")
    if not wall_uid:
        return None
    try:
        anchor = parse_edge_anchor(getattr(opening, "meta", None))
    except Exception:
        return None
    if str(anchor.get("parent") or "") != wall_uid:
        return None
    anchor_orient = str(anchor.get("orient") or "").strip().lower()[:1]
    if anchor_orient and anchor_orient != orient:
        return None
    center_s = _positive_float(anchor.get("s"))
    width = _opening_width_m(opening)
    height = _opening_height_m(opening)
    if center_s is None or width is None or width <= EPS or height <= EPS:
        return None
    center_abs = float(wa0) + float(center_s)
    a0c = max(float(wa0), center_abs - 0.5 * float(width))
    a1c = min(float(wa1), center_abs + 0.5 * float(width))
    if a1c - a0c <= EPS:
        return None
    return a0c, a1c, height


def _opening_area_on_wall_segment(wall: ElementModel, windows: List[ElementModel]) -> float:
    """Opening area to subtract from this wall segment (union with max-height)."""
    wl = _axis_aligned_line(wall)
    if wl is None:
        return 0.0
    orient, c, wa0, wa1 = wl

    intervals: List[Tuple[float, float, float]] = []  # (a0, a1, h)
    for w in windows:
        if not is_opening_type(getattr(w, "element_type", "")):
            continue
        anchored = _anchored_opening_interval_on_wall(wall, w, orient, wa0, wa1)
        if anchored is not None:
            intervals.append(anchored)
            continue
        ww = _axis_aligned_line(w)
        if ww is None:
            continue
        worient, wc, a0, a1 = ww
        if worient != orient:
            continue
        if abs(wc - c) > 1e-3:
            continue
        a0c = max(min(a0, a1), wa0)
        a1c = min(max(a0, a1), wa1)
        if a1c - a0c <= EPS:
            continue
        h = _opening_height_m(w)
        if h <= EPS:
            continue
        intervals.append((a0c, a1c, h))

    if not intervals:
        return 0.0

    cuts = [wa0, wa1]
    for a0, a1, _h in intervals:
        cuts.append(a0)
        cuts.append(a1)
    cuts = sorted(set(round(x, 6) for x in cuts))

    area = 0.0
    for i in range(len(cuts) - 1):
        s0, s1 = cuts[i], cuts[i + 1]
        if s1 - s0 <= EPS:
            continue
        mid = 0.5 * (s0 + s1)
        hmax = 0.0
        for a0, a1, h in intervals:
            if a0 - EPS <= mid <= a1 + EPS:
                hmax = max(hmax, h)
        if hmax > 0.0:
            area += (s1 - s0) * hmax

    return max(0.0, area)


def _inner_dims_for_room(
    r: RoomModel,
    room_elements: List[ElementModel],
    *,
    thickness_mode: ThicknessMode = "full",
) -> RoomInnerGeometry:
    """
    Innenmaße aus Raumaußenmaßen minus Wanddicken.
    thickness_mode:
      - "full": ganze Wanddicke je Seite abziehen
      - "half": halbe Wanddicke je Seite abziehen (wie es häufig in Grundrissskizzen genutzt wird)
    """
    x0, y0 = float(r.x_m), float(r.y_m)
    x1, y1 = x0 + float(r.w_m), y0 + float(r.h_m)

    t = {"left": 0.0, "right": 0.0, "top": 0.0, "bottom": 0.0}

    def _update(side: str, elem_type: str):
        if elem_type in OUTER_WALL_TYPES:
            t[side] = max(t[side], WALL_THICKNESS_OUTER_M)
        elif elem_type in INNER_WALL_TYPES:
            if t[side] < WALL_THICKNESS_OUTER_M - EPS:
                t[side] = max(t[side], WALL_THICKNESS_INNER_M)

    for e in room_elements:
        if not e.has_geometry():
            continue
        ax = _axis_aligned_line(e)
        if not ax:
            continue
        orient, c, a0, a1 = ax
        a_lo, a_hi = (a0, a1) if a0 <= a1 else (a1, a0)

        if orient == "v":
            if a_hi < y0 + EPS or a_lo > y1 - EPS:
                continue
            if abs(c - x0) <= 1e-3:
                _update("left", e.element_type)
            elif abs(c - x1) <= 1e-3:
                _update("right", e.element_type)

        elif orient == "h":
            if a_hi < x0 + EPS or a_lo > x1 - EPS:
                continue
            if abs(c - y0) <= 1e-3:
                _update("top", e.element_type)
            elif abs(c - y1) <= 1e-3:
                _update("bottom", e.element_type)

    k = 0.5 if thickness_mode == "half" else 1.0
    w_in = max(0.0, float(r.w_m) - k * (t["left"] + t["right"]))
    h_in = max(0.0, float(r.h_m) - k * (t["top"] + t["bottom"]))

    a_in = w_in * h_in
    room_h = max(float(getattr(r, "height_m", 2.5) or 2.5), 0.0)
    v_in = a_in * room_h

    return RoomInnerGeometry(w_in_m=w_in, h_in_m=h_in, a_in_m2=a_in, v_in_m3=v_in)


# ---------------------------------------------------------------------------
# Element-Klassifikation / ΔT
# ---------------------------------------------------------------------------

def _norm_str(s: str) -> str:
    return normalize_element_type(s)

''' alt
def _is_kellerdecke(et: str) -> bool:
    s = (et or "").strip().lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    if s in ("kellerdecke", "kgdecke", "kg-decke"):
        return True
    has_keller = ("keller" in s) or ("kg" in s.split()) or ("untergeschoss" in s) or ("ug" in s.split())
    has_decke_boden = ("decke" in s) or ("boden" in s) or ("bodenplatte" in s) or ("platte" in s)
    return bool(has_keller and has_decke_boden)

def _is_geschossdecke(et: str) -> bool:
    s = (et or "").strip().lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    if s in ("geschossdecke", "zwischendecke"):
        return True
    # Decke zwischen Geschossen (EG/DG), Decke zum Dach/oben
    has_between = ("geschoss" in s) or ("zwischen" in s) or ("zwisch" in s) or ("eg" in s) or ("dg" in s)
    has_decke = ("decke" in s)
    # explizite Dachdecke als "oben"-Decke zählt ebenfalls hier (Bucket wird später über t_adj/oben bestimmt)
    has_roof = ("dach" in s) and has_decke
    return bool((has_between and has_decke) or has_roof)
''' #alt ende
# neu
def _is_kellerdecke(et: str) -> bool:
    s = _norm_str(et)
    if s in ("kellerdecke", "kgdecke", "kg-decke"):
        return True
    has_keller = ("keller" in s) or ("untergeschoss" in s) or ("ug" in s.split()) or ("kg" in s.split())
    has_decke = ("decke" in s) or ("boden" in s) or ("bodenplatte" in s) or ("platte" in s)
    return bool(has_keller and has_decke)



def _is_geschossdecke(et: str) -> bool:
    """Decke zwischen beheizten Geschossen (EG↔DG)."""
    s = _norm_str(et)
    if s in ("geschossdecke", "zwischendecke"):
        return True
    # tolerate labels like "Decke EG/DG", "Zwischen-Decke", etc.
    has_between = ("geschoss" in s) or ("zwischen" in s) or ("zwisch" in s) or ("eg" in s) or ("dg" in s)
    return bool(has_between and ("decke" in s))


def _is_speicherdecke(et: str) -> bool:
    """Decke zum nicht ausgebauten Speicher / Dachraum (beheizt → unbeheizt)."""
    s = _norm_str(et)
    if s in ("speicherdecke", "dachdecke", "dachraumdecke"):
        return True
    return ("speicher" in s) or ("dachraum" in s) or (("dach" in s) and ("decke" in s))
#neu end


def _transmission_surface_role(e: ElementModel, *, ground_kind: str = "") -> str:
    """Classify a transmission line for DIN-style reporting groups."""
    et = _norm_str(getattr(e, "element_type", "") or "")
    if ground_kind == "slab" or "bodenplatte" in et or "fussboden" in et or "fußboden" in et:
        return "floor_ground"
    if ground_kind == "wall":
        return "wall_ground"
    if et == "dach" or et.startswith("dach ") or "dachflaeche" in et or "dachfläche" in et:
        return "roof"
    if _is_kellerdecke(getattr(e, "element_type", "") or ""):
        return "deck_basement"
    if _is_speicherdecke(getattr(e, "element_type", "") or ""):
        return "deck_attic"
    if _is_geschossdecke(getattr(e, "element_type", "") or ""):
        return "deck_interzone"
    if et in {"fenster", "dachfenster"}:
        return "window"
    if "wand" in et:
        return "wall"
    return "other"

''' alt
def _deltaT_and_bucket(
    r: RoomModel,
    e: ElementModel,
    *,
    t_out_c: float,
    t_keller_c: float,
    t_oben_c: float,
) -> Tuple[float, str]:
    """Return (ΔT, bucket).

    bucket in {'out','keller','dachraum','interzone'}.

    - keller: Kellerdecke (EG→Keller)
    - interzone: Decke zwischen beheizten Geschossen (EG↔DG) via meta t_adj_c
    - dachraum: Decke zum nicht ausgebauten Speicher / Dachraum (beheizt → unbeheizt)
    """
    t_in = float(r.t_inside_c or 0.0)
    et = (e.element_type or "")
    explicit_boundary = boundary_from_meta(getattr(e, "meta", None))
    if explicit_boundary is not None:
        if explicit_boundary.key == "attic_unheated":
            t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
            if t_adj is None:
                t_adj = float(t_oben_c)
            return max(0.0, t_in - float(t_adj)), "dachraum"
        if explicit_boundary.key in {"unheated", "basement_unheated"}:
            t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
            if t_adj is None:
                t_adj = float(t_keller_c if explicit_boundary.key == "basement_unheated" else t_oben_c)
            return max(0.0, t_in - float(t_adj)), "keller" if explicit_boundary.key == "basement_unheated" else "dachraum"
        if explicit_boundary.key in {"adjacent_heated", "interzone"}:
            t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
            if t_adj is None:
                t_adj = t_in
            return max(0.0, t_in - float(t_adj)), "interzone"
        if explicit_boundary.key == "ground":
            return max(0.0, t_in - float(t_keller_c)), "ground"
        if explicit_boundary.key == "outside":
            return max(0.0, t_in - float(t_out_c)), "out"

    if _is_kellerdecke(et):
        # optional adjacent override via meta
        t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
        if t_adj is None:
            t_adj = float(t_keller_c)
        return max(0.0, t_in - float(t_adj)), "keller"

    if _is_geschossdecke(et):
        t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
        if t_adj is not None:
            # EG->DG Zwischendecke
            return max(0.0, t_in - float(t_adj)), "out"  # ΔT zu "beheizt" ist meist ~0; bucket "out" ist ok für Summen
        return max(0.0, t_in - float(t_oben_c)), "oben"

    return max(0.0, t_in - float(t_out_c)), "out"
''' #alt ende
def _deltaT_and_bucket(
    r: RoomModel,
    e: ElementModel,
    *,
    t_out_c: float,
    t_keller_c: float,
    t_oben_c: float,
) -> Tuple[float, str]:
    """Return (ΔT, bucket).

    bucket in {'out','keller','dachraum','interzone'}.

    - keller: Kellerdecke (EG→Keller)
    - interzone: Decke zwischen beheizten Geschossen (EG↔DG) via meta t_adj_c
    - dachraum: Decke zum nicht ausgebauten Speicher / Dachraum (beheizt → unbeheizt)
    """
    t_in = float(r.t_inside_c or 0.0)
    et = (e.element_type or "")
    explicit_boundary = boundary_from_meta(getattr(e, "meta", None))
    if explicit_boundary is not None:
        if explicit_boundary.key == "attic_unheated":
            t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
            if t_adj is None:
                t_adj = float(t_oben_c)
            return max(0.0, t_in - float(t_adj)), "dachraum"
        if explicit_boundary.key in {"unheated", "basement_unheated"}:
            t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
            if t_adj is None:
                t_adj = float(t_keller_c if explicit_boundary.key == "basement_unheated" else t_oben_c)
            return max(0.0, t_in - float(t_adj)), "keller" if explicit_boundary.key == "basement_unheated" else "dachraum"
        if explicit_boundary.key in {"adjacent_heated", "interzone"}:
            t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
            if t_adj is None:
                t_adj = t_in
            return max(0.0, t_in - float(t_adj)), "interzone"
        if explicit_boundary.key == "ground":
            return max(0.0, t_in - float(t_keller_c)), "ground"
        if explicit_boundary.key == "outside":
            return max(0.0, t_in - float(t_out_c)), "out"

    if _is_kellerdecke(et):
        # optional adjacent override via meta
        t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
        if t_adj is None:
            t_adj = float(t_keller_c)
        return max(0.0, t_in - float(t_adj)), "keller"

    # Interzone: EG↔DG (beheizt ↔ beheizt) — nur wenn t_adj_c gesetzt ist
    if _is_geschossdecke(et):
        t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
        if t_adj is not None:
            return max(0.0, t_in - float(t_adj)), "interzone"
        # Wenn keine Adj-Temp vorhanden ist, behandeln wir es NICHT als Hülle.
        # (z.B. fehlendes Mapping) -> interzone mit ΔT=0 als konservativer Fallback.
        return 0.0, "interzone"

    # Dachraum/Speicher
    if _is_speicherdecke(et):
        t_adj = _meta_get_float(getattr(e, "meta", None), "t_adj_c")
        if t_adj is None:
            t_adj = float(t_oben_c)
        return max(0.0, t_in - float(t_adj)), "dachraum"

    # Backward-compat: falls jemand "Geschossdecke" als Speicherdecke benutzt hat
    s_et = _norm_str(et)
    if ("dach" in s_et and "decke" in s_et) or ("speicher" in s_et):
        return max(0.0, t_in - float(t_oben_c)), "dachraum"

    if _norm_str(et) in INNER_WALL_TYPES or "innenwand" in _norm_str(et):
        return 0.0, "interzone"

    return max(0.0, t_in - float(t_out_c)), "out"


# ---------------------------------------------------------------------------
# Public API: calc_heatloads (Schnittstelle beibehalten)
# ---------------------------------------------------------------------------

def calc_heatloads(
    rooms: List[RoomModel],
    elements: List[ElementModel],
    t_out_c: float,
    vent_cfg: VentilationCfg = VentilationCfg(),
    thickness_mode: ThicknessMode = "full",
    area_shrink_factor: float = 1.0,
    t_keller_c: float = 12.0,  # Keller (unbeheizt), vollunterkellert: EG->KG
    t_oben_c: float = 12.0,
    floor_area_mode: FloorAreaMode = "inner",
    tb_cfg: Optional[ThermalBridgeCfg] = None,
    ground_cfg: Optional[GroundModelCfg] = None,
    u_aussenwand_w_m2k: float = 0.45,
    u_fenster_w_m2k: float = 2.80,
    u_tuer_w_m2k: float = 1.80,
    reheat_power_w_m2: float = 0.0,
    reheat_duration_h: float = 0.0,
    reheat_temp_drop_k: float = 0.0,
    reheat_capacity_wh_m2k: float = 20.0,
    u_kellerdecke_w_m2k: float = DEFAULT_U_KELLERDECKE_W_M2K,
    u_eg_geschossdecke_w_m2k: float = DEFAULT_U_EG_GESCHOSSDECKE_W_M2K,
    u_dg_geschossdecke_w_m2k: float = DEFAULT_U_DG_GESCHOSSDECKE_W_M2K,
    u_value_source: str = "",
    auto_deck_assumptions_confirmed: bool = False,
    auto_deck_boundary_source: str = "",
    auto_deck_create_eg_kellerdecke: bool = True,
    auto_deck_create_eg_geschossdecke: bool = True,
    auto_deck_create_dg_speicherdecke: bool = True,
    u_bodenplatte_w_m2k: float = 0.40,
    u_erdberuehrte_wand_w_m2k: float = 0.60,
    ventilation_mode: str = "natural",
    min_air_change_1ph: float = 0.0,
    infiltration_air_change_1ph: float = 0.0,
    mech_supply_m3h: float = 0.0,
    mech_exhaust_m3h: float = 0.0,
    heat_recovery_efficiency: float = 0.0,
    sync_auto_decks: bool = True,
) -> Dict[str, dict]:
    """
    Berechnet Heizlasten pro Raum.

    floor_area_mode wirkt auf:
      - Transmissionsflächen (Wände/Fenster/Decken) und
      - Bezugsfläche A_ref für W/m²
    Volumen/Lüftung bleibt immer Innenmaß-basiert.

    Wärmebrücken (optional):
      - mode='delta_u'  -> Φ_WB = ΔU_WB * A_envelope * ΔT
      - mode='psi'      -> Φ_WB = Σ(ψ*L*ΔT)
      - mode='percent'  -> Φ_WB = p * Φ_trans
    """
    if sync_auto_decks:
        ensure_auto_decks(
            rooms,
            elements,
            u_kellerdecke_w_m2k=float(u_kellerdecke_w_m2k),
            u_eg_geschossdecke_w_m2k=float(u_eg_geschossdecke_w_m2k),
            u_dg_geschossdecke_w_m2k=float(u_dg_geschossdecke_w_m2k),
            t_keller_c=float(t_keller_c),
            t_oben_c=float(t_oben_c),
            u_value_source=str(u_value_source or ""),
            boundary_source=str(auto_deck_boundary_source or ""),
            auto_deck_assumptions_confirmed=bool(auto_deck_assumptions_confirmed),
            create_eg_kellerdecke=bool(auto_deck_create_eg_kellerdecke),
            create_eg_geschossdecke=bool(auto_deck_create_eg_geschossdecke),
            create_dg_speicherdecke=bool(auto_deck_create_dg_speicherdecke),
        )

    tb = tb_cfg or ThermalBridgeCfg()
    ground = ground_cfg or GroundModelCfg()

    # Elemente nach Raum gruppieren
    #e_by_room: Dict[str, List[ElementModel]] = {}
    #for e in elements:
    #    e_by_room.setdefault(e.room_id, []).append(e)
    ###
    def _meta_rooms_list(meta: str) -> List[str]:
        """
        Parse meta token rooms=<rid1,rid2,...> from meta string "k=v|k2=v2".
        Returns [] if not present.
        """
        if not meta:
            return []
        m = re.search(r"(?:^|\|)rooms=([^|]+)", meta)
        if not m:
            return []
        raw = m.group(1).strip()
        if not raw:
            return []
        return [x.strip() for x in raw.split(",") if x.strip()]

    def _auto_deck_suppressed(e: ElementModel) -> bool:
        meta = str(getattr(e, "meta", "") or "")
        return "auto_suppressed=1" in meta or "suppressed_by=manual_deck" in meta

    def _horizontal_boundary_kind(item: ElementModel) -> str | None:
        deck_kind = deck_kind_for_element(item)
        if deck_kind in {"keller", "geschoss", "speicher"}:
            return deck_kind
        is_ground, ground_kind = _is_ground_element(item)
        if is_ground and ground_kind == "slab":
            return "bodenplatte"
        role = _transmission_surface_role(item, ground_kind=ground_kind if is_ground else "")
        if role == "floor_ground":
            return "bodenplatte"
        et = _norm_str(getattr(item, "element_type", "") or "")
        meta = str(getattr(item, "meta", "") or "").lower()
        if ("bodenplatte" in et) or ("fussboden" in et) or ("fußboden" in et) or ("ground=slab" in meta):
            return "bodenplatte"
        if et in {"boden", "fussboden", "fußboden"}:
            return "boden"
        return None

    def _element_signature(item: ElementModel) -> tuple:
        return (
            _norm_str(getattr(item, "element_type", "") or ""),
            round(float(getattr(item, "area_m2", 0.0) or 0.0), 6),
            round(float(getattr(item, "u_w_m2k", 0.0) or 0.0), 6),
            round(float(getattr(item, "factor", 1.0) or 1.0), 6),
            str(getattr(item, "meta", "") or ""),
        )

    def _keep_unique_manual(candidates: list[ElementModel]) -> list[ElementModel]:
        seen: set[tuple] = set()
        kept: list[ElementModel] = []
        for item in candidates:
            sig = _element_signature(item)
            if sig in seen:
                continue
            seen.add(sig)
            kept.append(item)
        return kept

    def _dedupe_room_horizontal_boundaries(room_id: str, room_items: List[ElementModel]) -> List[ElementModel]:
        grouped: dict[str, list[ElementModel]] = {}
        out: list[ElementModel] = []
        for item in room_items:
            kind = _horizontal_boundary_kind(item)
            if kind is None:
                out.append(item)
                continue
            grouped.setdefault(kind, []).append(item)

        lower_manual = []
        for lower_kind in ("bodenplatte", "boden", "keller"):
            lower_manual.extend([item for item in grouped.get(lower_kind, []) if not is_auto_deck(item)])
        if lower_manual:
            lower_kind_to_keep = "bodenplatte" if grouped.get("bodenplatte") else ("boden" if grouped.get("boden") else "keller")
            grouped["keller"] = [item for item in grouped.get("keller", []) if not is_auto_deck(item)]
            for lower_kind in ("bodenplatte", "boden", "keller"):
                if lower_kind != lower_kind_to_keep:
                    grouped[lower_kind] = [item for item in grouped.get(lower_kind, []) if is_auto_deck(item) and _auto_deck_suppressed(item)]

        for kind in ("keller", "geschoss", "speicher", "bodenplatte", "boden"):
            candidates = grouped.get(kind, [])
            if not candidates:
                continue
            manual = [item for item in candidates if not is_auto_deck(item)]
            if manual:
                out.extend(_keep_unique_manual(manual))
                continue
            kept_auto = False
            for item in candidates:
                if _auto_deck_suppressed(item):
                    continue
                if kept_auto:
                    continue
                out.append(item)
                kept_auto = True
        return out

    # Elemente nach Raum gruppieren (inkl. shared walls via meta rooms=...)
    e_by_room: Dict[str, List[ElementModel]] = {}
    seen_uid_per_room: Dict[str, set] = {}

    for e in elements:
        # always add to owner room_id
        rid0 = str(getattr(e, "room_id", "") or "")
        u = str(getattr(e, "uid", "") or "")  # may be empty
        if rid0:
            e_by_room.setdefault(rid0, []).append(e)
            if u:
                seen_uid_per_room.setdefault(rid0, set()).add(u)

        # additionally add to rooms listed in meta rooms=...
        meta = str(getattr(e, "meta", "") or "")
        for rid in _meta_rooms_list(meta):
            if not rid:
                continue
            if rid == rid0:
                continue
            if u and (u in seen_uid_per_room.setdefault(rid, set())):
                continue
            e_by_room.setdefault(rid, []).append(e)
            if u:
                seen_uid_per_room.setdefault(rid, set()).add(u)

    for rid, room_items in list(e_by_room.items()):
        e_by_room[rid] = _dedupe_room_horizontal_boundaries(rid, room_items)
    ###
    out: Dict[str, dict] = {}

    # --- Gebäude-Hüllflächen-Auswertung (für Reporting, DIN-Nachweis) ---
    # Wir summieren die "wirksamen" Flächen A_eff (= Fläche minus Öffnungen bei Wänden)
    # getrennt nach Geschoss und nach Randbedingung (außen / Keller unbeheizt / oben-Spitzboden / Dachraum / Interzone).
    env_by_floor: Dict[str, Dict[str, float]] = {}
    env_details: List[Dict[str, object]] = []

    def _norm_floor(label: str) -> str:
        s = (label or "").strip().upper()
        if s in ("", "UNKNOWN", "UNBEKANNT"):
            return "UNBEKANNT"
        # häufige Varianten
        if s in ("1OG", "1.OG", "OG", "Obergeschoss".upper()):
            return "OG"
        if s in ("DG", "DACHGESCHOSS"):
            return "DG"
        if s in ("EG", "ERDGESCHOSS"):
            return "EG"
        if s in ("KG", "UG", "KELLER", "UNTERGESCHOSS"):
            return "KG"
        if s in ("SP", "SPEICHER", "DACHRAUM"):
            return "SPEICHER"
        return s

    def _env_acc(floor_key: str, bucket: str, A_eff: float) -> None:
        d = env_by_floor.setdefault(floor_key, {})
        d[bucket] = d.get(bucket, 0.0) + float(A_eff)

    for r in rooms:
        room_elements = e_by_room.get(r.id, [])
        room_windows = [e for e in room_elements if is_opening_type(getattr(e, "element_type", ""))]

        floor_key = _norm_floor(getattr(r, 'floor', '') or '')

        # Innenmaße (für Volumen/Lüftung)
        geom_in = _inner_dims_for_room(r, room_elements, thickness_mode=thickness_mode)

        # Außenmaße
        w_out = max(float(r.w_m or 0.0), 0.0)
        h_out = max(float(r.h_m or 0.0), 0.0)
        A_out = w_out * h_out

        shrink = float(area_shrink_factor or 1.0)
        A_in_eff = geom_in.a_in_m2 * shrink
        V_in_eff = geom_in.v_in_m3 * shrink
        A_out_eff = A_out * shrink

        # Skalierung für Flächen entlang Raumkanten (nur für "inner")
        sx = (geom_in.w_in_m / w_out) if (floor_area_mode == "inner" and w_out > EPS) else 1.0
        sy = (geom_in.h_in_m / h_out) if (floor_area_mode == "inner" and h_out > EPS) else 1.0

        x0, y0 = float(r.x_m or 0.0), float(r.y_m or 0.0)
        x1, y1 = x0 + w_out, y0 + h_out

        room_h = float(getattr(r, "height_m", None) or 2.5)
        room_perimeter = 0.0
        try:
            room_perimeter = max(0.0, float(r.perimeter_m()))
        except Exception:
            room_perimeter = 2.0 * (max(w_out, 0.0) + max(h_out, 0.0))

        def _edge_scale_for_element(e: ElementModel) -> float:
            """Skaliert Elemente auf Raumkanten (sx oder sy) wenn floor_area_mode='inner'."""
            if floor_area_mode != "inner":
                return 1.0
            ax = _axis_aligned_line(e)
            if ax is None:
                return 1.0
            orient, c, _a0, _a1 = ax
            if orient == "v" and (abs(c - x0) <= 1e-3 or abs(c - x1) <= 1e-3):
                return sy
            if orient == "h" and (abs(c - y0) <= 1e-3 or abs(c - y1) <= 1e-3):
                return sx
            return 1.0

        # ΔT zur Außenluft
        t_in = float(r.t_inside_c or 0.0)
        dT_out = max(0.0, t_in - float(t_out_c))

        # Transmission Summen
        Q_trans = 0.0
        Q_trans_out = 0.0
        Q_trans_keller = 0.0
        Q_trans_oben = 0.0
        Q_trans_interzone = 0.0
        Q_trans_dachraum = 0.0
        Q_trans_ground = 0.0

        # für Report/Debug
        A_openings = 0.0
        A_outer_eff = 0.0

        # Wärmebrücken-Bemessungsgrößen
        A_env_out = 0.0
        A_env_keller = 0.0
        A_env_oben = 0.0
        A_env_dachraum = 0.0
        A_env_interzone = 0.0
        A_env_ground = 0.0
        L_env_out = 0.0
        L_env_keller = 0.0
        L_env_oben = 0.0
        L_env_dachraum = 0.0
        L_env_interzone = 0.0
        L_env_ground = 0.0

        def _acc_env(bucket: str, A_used: float, L_used: float):
            #nonlocal A_env_out, A_env_keller, A_env_oben, A_env_interzone
            #nonlocal L_env_out, L_env_keller, L_env_oben, L_env_interzone
            nonlocal A_env_out, A_env_keller, A_env_oben, A_env_interzone, A_env_dachraum, A_env_ground
            nonlocal L_env_out, L_env_keller, L_env_oben, L_env_interzone, L_env_dachraum, L_env_ground
            if bucket == "out" and tb.include_out:
                A_env_out += A_used
                L_env_out += L_used
            elif bucket == "keller" and tb.include_keller:
                A_env_keller += A_used
                L_env_keller += L_used
            elif bucket in ("oben","dachraum") and tb.include_oben:
                # "oben" kept for backward-compat; "dachraum" is the new explicit bucket
                A_env_oben += A_used
                L_env_oben += L_used
                A_env_dachraum += A_used
                L_env_dachraum += L_used
            elif bucket == "interzone":
                # bewusst nicht für Wärmebrücken heranziehen, aber für Reporting/Debug tracken
                A_env_interzone += A_used
                L_env_interzone += L_used
                A_env_oben += A_used
                L_env_oben += L_used
            elif bucket == "ground":
                A_env_ground += A_used
                L_env_ground += L_used

        # -------------------------------------------------------------------
        # Audit-Trail / Berechnungsnachweis (wird von reporting.py genutzt)
        # -------------------------------------------------------------------
        # Jede Zeile beschreibt einen einzelnen Rechenschritt, so dass reporting.py
        # nichts mehr "neu" berechnen muss (nur noch darstellen).
        room_lines: List[dict] = []
        type_sums: Dict[str, Dict[str, float]] = {}

        def _add_line(line: dict) -> None:
            room_lines.append(line)
            ety = str(line.get("element_type", "") or "")
            lt = str(line.get("line_type", "TRANSMISSION") or "TRANSMISSION")
            if lt not in ("TRANSMISSION", "VENTILATION", "THERMAL_BRIDGE"):
                return
            type_sums.setdefault(ety, {"A_brutto_m2": 0.0, "A_open_m2": 0.0, "A_eff_m2": 0.0, "Q_W": 0.0})
            type_sums[ety]["A_brutto_m2"] += float(line.get("A_brutto_m2", 0.0) or 0.0)
            type_sums[ety]["A_open_m2"] += float(line.get("A_open_m2", 0.0) or 0.0)
            type_sums[ety]["A_eff_m2"] += float(line.get("A_eff_m2", 0.0) or 0.0)
            type_sums[ety]["Q_W"] += float(line.get("Q_W", 0.0) or 0.0)

            # --- Gebäude-Hüllflächen-Audit: genau 1 Detailzeile pro TRANSMISSION-Line ---
            if lt == "TRANSMISSION":
                try:
                    bkt = str(line.get("bucket", "") or "")
                    A_br = float(line.get("A_brutto_m2", 0.0) or 0.0)
                    A_op = float(line.get("A_open_m2", 0.0) or 0.0)
                    A_eff = float(line.get("A_eff_m2", 0.0) or 0.0)
                except Exception:
                    bkt, A_br, A_op, A_eff = ("", 0.0, 0.0, 0.0)

                _env_acc(floor_key, bkt, A_eff)
                env_details.append({
                    "floor": floor_key,
                    "bucket": bkt,
                    "boundary_bucket": canonical_bucket(bkt),
                    "boundary_label": boundary_label_for_bucket(bkt),
                    "uid": str(line.get("uid", "") or ""),
                    "element_type": str(line.get("element_type", "") or ""),
                    "surface_role": str(line.get("surface_role", "") or ""),
                    "A_m2": float(A_br),
                    "A_open_m2": float(A_op),
                    "A_eff_m2": float(A_eff),
                    "L_m": float(line.get("L_m", 0.0) or 0.0),
                    "perimeter_m": float(line.get("perimeter_m", 0.0) or 0.0),
                    "B_prime_m": float(line.get("B_prime_m", 0.0) or 0.0),
                    "U_w_m2k": float(line.get("U_W_m2K", 0.0) or 0.0),
                    "note": str(line.get("notes", "") or ""),
                })

        for e in room_elements:
            U = float(e.u_w_m2k or 0.0)
            f = 1.0 if getattr(e, "factor", None) is None else float(e.factor)
            et = (e.element_type or "").strip()

            is_ground, ground_kind = _is_ground_element(e)
            if is_ground and ground.mode != "none":
                if U <= EPS:
                    U = float(u_bodenplatte_w_m2k if ground_kind == "slab" else u_erdberuehrte_wand_w_m2k)
                    try:
                        e.u_w_m2k = U
                    except Exception:
                        pass
                Tg, fg, ground_method = _effective_ground_temp_for_cfg(ground, ground_kind, t_in, float(t_out_c))
                dT_e = max(0.0, t_in - float(Tg))
                bucket = "ground"
            else:
                Tg = None
                fg = 0.0
                ground_method = ""
                dT_e, bucket = _deltaT_and_bucket(
                    r, e, t_out_c=t_out_c, t_keller_c=t_keller_c, t_oben_c=t_oben_c
                )
            surface_role = _transmission_surface_role(e, ground_kind=ground_kind if is_ground else "")

            scale = _edge_scale_for_element(e)

            # Grundfläche A aus Daten
            A = float(e.area_m2 or 0.0)
            # ---------------------------------------------------------------
            # Fallbacks für Außenwand: U/L/A wenn im Datensatz 0 oder fehlt
            # ---------------------------------------------------------------
            if et in OUTER_WALL_TYPES:
                # 1) U-Wert defaulten
                if U <= EPS:
                    U = float(u_aussenwand_w_m2k or DEFAULT_U.get(et, DEFAULT_U.get("Aussenwand", 0.45)))
                    try:
                        e.u_w_m2k = U
                    except Exception:
                        pass
            elif is_window_type(et) and U <= EPS:
                U = float(u_fenster_w_m2k or DEFAULT_U.get("Fenster", 2.80))
                try:
                    e.u_w_m2k = U
                except Exception:
                    pass
            elif is_door_type(et) and U <= EPS:
                U = float(u_tuer_w_m2k or DEFAULT_U.get(et, DEFAULT_U.get("Tür", 1.80)))
                try:
                    e.u_w_m2k = U
                except Exception:
                    pass

            # Decken/Bodenflächen explizit aus Raumfläche (damit inner/outer sicher wirkt)
            if _is_kellerdecke(et) or _is_geschossdecke(et) or _is_speicherdecke(et):
                A = (geom_in.a_in_m2 if floor_area_mode == "inner" else A_out)

            # Außenwand: aus Geometrie ableiten + Öffnungen abziehen
            if et in OUTER_WALL_TYPES and e.has_geometry():
                #L = float(e.compute_length() or 0.0)
                L = float(e.compute_length() or 0.0)
                # 2) Länge fallbacken (wenn Geometrie degeneriert / Länge 0)
                if L <= EPS:
                    ax = _axis_aligned_line(e)
                    if ax is not None:
                        orient, _c, _a0, _a1 = ax
                        #L = float(w_out if orient == "h" else h_out)
                        L = abs(float(_a1) - float(_a0))  # Segmentlänge, nicht Raummaß
                    else:
                        L = float(getattr(e, "length_m", 0.0) or 0.0)
                        if L <= EPS:
                            L = float(max(w_out, h_out))
                    try:
                        e.length_m = L
                    except Exception:
                        pass

                if L > EPS:
                    A = max(A, L * room_h)
                # 3) Fläche fallbacken (wenn weiterhin 0)
                if A <= EPS and L > EPS:
                    A = L * room_h
                try:
                    if float(getattr(e, "area_m2", 0.0) or 0.0) <= EPS and A > EPS:
                        e.area_m2 = A
                except Exception:
                    pass




                A *= scale

                A_open = _opening_area_on_wall_segment(e, room_windows) * scale
                A_openings += A_open

                A_eff = max(0.0, A - A_open)
                A_outer_eff += A_eff

                _acc_env(bucket, A_eff, L * scale)

                # Gebäude-Hüllflächen pro Geschoss/bucket (Audit-Trail)

                Q_e = U * A_eff * dT_e * f

                _add_line({
                    "line_type": "TRANSMISSION",
                    "uid": str(getattr(e, "uid", "") or ""),
                    "element_type": et,
                    "surface_role": surface_role,
                    "bucket": bucket,
                    "boundary_bucket": canonical_bucket(bucket),
                    "boundary_label": boundary_label_for_bucket(bucket),
                    "U_W_m2K": float(U),
                    "factor": float(f),
                    "scale": float(scale),
                    "dT_K": float(dT_e),
                    "A_brutto_m2": float(A),          # bereits skaliert
                    "A_open_m2": float(A_open),       # bereits skaliert
                    "A_eff_m2": float(A_eff),
                    "perimeter_m": 0.0,
                    "B_prime_m": 0.0,
                    "ground_kind": str(ground_kind or ""),
                    "Q_W": float(Q_e),
                    "notes": (
                        f"outer wall (A_eff = A - openings); ground_method={ground_method}; f_ground={fg:.3f}; Tg={float(Tg):.2f} °C"
                        if bucket == "ground" and Tg is not None
                        else "outer wall (A_eff = A - openings)"
                    ),
                })

                Q_trans += Q_e
                if bucket == "ground":
                    Q_trans_ground += Q_e
                elif bucket == "keller":
                    Q_trans_keller += Q_e
                elif bucket == "oben":
                    Q_trans_oben += Q_e
                    Q_trans_dachraum += Q_e
                elif bucket == "dachraum":
                    Q_trans_dachraum += Q_e
                elif bucket == "interzone":
                    Q_trans_interzone += Q_e
                else:
                    Q_trans_out += Q_e

            else:
                # Fenster/Türen: ggf. aus Geometrie oder Wandanker ableiten
                if is_opening_type(et):
                    Lw = float(_opening_width_m(e) or 0.0)
                    hw = _opening_height_m(e)
                    if A <= EPS and Lw > EPS and hw > EPS:
                        A = max(A, Lw * hw)
                    try:
                        if float(getattr(e, "area_m2", 0.0) or 0.0) <= EPS and A > EPS:
                            e.area_m2 = A
                    except Exception:
                        pass
                    A *= scale
                    _acc_env(bucket, A, Lw * scale)
                    L_env_used = Lw * scale

                # Wände ohne explizite Fläche: aus Länge*Höhe ableiten
                elif not is_opening_type(et) and e.has_geometry() and A <= EPS:
                    Lg = float(e.compute_length() or 0.0)
                    if Lg > EPS:
                        A = Lg * room_h
                    A *= scale
                    L_env_used = Lg * scale
                    _acc_env(bucket, A, L_env_used)
                elif not is_opening_type(et):
                    # wenn A gesetzt ist, aber Element auf Raumkante liegt, trotzdem skalieren
                    A *= scale
                    L_env_used = float(e.compute_length() or 0.0) * scale if e.has_geometry() else 0.0
                    if bucket == "ground" and ground_kind == "slab" and L_env_used <= EPS:
                        L_env_used = room_perimeter * (shrink ** 0.5 if floor_area_mode == "inner" else 1.0)
                    _acc_env(bucket, A, L_env_used)
                else:
                    L_env_used = 0.0

                Q_e = U * A * dT_e * f
                b_prime = A / max(0.5 * L_env_used, EPS) if bucket == "ground" and ground_kind == "slab" and A > EPS and L_env_used > EPS else 0.0

                _add_line({
                    "line_type": "TRANSMISSION",
                    "uid": str(getattr(e, "uid", "") or ""),
                    "element_type": et,
                    "surface_role": surface_role,
                    "bucket": bucket,
                    "boundary_bucket": canonical_bucket(bucket),
                    "boundary_label": boundary_label_for_bucket(bucket),
                    "U_W_m2K": float(U),
                    "factor": float(f),
                    "scale": float(scale),
                    "dT_K": float(dT_e),
                    "A_brutto_m2": float(A),     # i.d.R. bereits skaliert
                    "A_open_m2": 0.0,
                    "A_eff_m2": float(A),
                    "perimeter_m": float(L_env_used if bucket == "ground" and ground_kind == "slab" else 0.0),
                    "B_prime_m": float(b_prime),
                    "ground_kind": str(ground_kind or ""),
                    "Q_W": float(Q_e),
                    "notes": (
                        f"ground element; ground_method={ground_method}; f_ground={fg:.3f}; Tg={float(Tg):.2f} °C"
                        if bucket == "ground" and Tg is not None
                        else ""
                    ),
                })

                Q_trans += Q_e
                if bucket == "ground":
                    Q_trans_ground += Q_e
                elif bucket == "keller":
                    Q_trans_keller += Q_e
                elif bucket == "oben":
                    Q_trans_oben += Q_e
                    Q_trans_dachraum += Q_e
                elif bucket == "dachraum":
                    Q_trans_dachraum += Q_e
                elif bucket == "interzone":
                    Q_trans_interzone += Q_e
                else:
                    Q_trans_out += Q_e

        # -------------------------------------------------------------------
        # Wärmebrücken-Zuschlag
        # -------------------------------------------------------------------
        Q_tb_out = 0.0
        Q_tb_keller = 0.0
        Q_tb_oben = 0.0
        Q_tb_dachraum = 0.0
        Q_tb_interzone = 0.0
        Q_tb_ground = 0.0

        if tb.mode == "delta_u":
            dU = float(tb.delta_u_w_m2k or 0.0)
            Q_tb_out = dU * A_env_out * dT_out
            Q_tb_keller = dU * A_env_keller * max(0.0, t_in - float(t_keller_c))
            Q_tb_oben = dU * A_env_oben * max(0.0, t_in - float(t_oben_c))
            Q_tb_dachraum = dU * A_env_dachraum * max(0.0, t_in - float(t_oben_c))

        elif tb.mode == "psi":
            # global default ψ; optional per element via meta (vereinfachter Einstieg)
            psi_def = float(tb.psi_default_w_mk or 0.0)
            Q_tb_out = psi_def * L_env_out * dT_out
            Q_tb_keller = psi_def * L_env_keller * max(0.0, t_in - float(t_keller_c))
            Q_tb_oben = psi_def * L_env_oben * max(0.0, t_in - float(t_oben_c))
            Q_tb_dachraum = psi_def * L_env_dachraum * max(0.0, t_in - float(t_oben_c))

            # Optional: elementweise ψ addieren (wenn meta psi_w_mk gesetzt ist)
            if tb.use_element_meta_psi:
                for e in room_elements:
                    psi = _meta_get_float(getattr(e, "meta", None), "psi_w_mk")
                    if psi is None:
                        continue
                    # Länge für ψ: meta override oder compute_length
                    L = _meta_get_float(getattr(e, "meta", None), "psi_L_m")
                    if L is None:
                        L = float(e.compute_length() or 0.0)
                    if L <= EPS:
                        continue
                    dT_e, bucket = _deltaT_and_bucket(r, e, t_out_c=t_out_c, t_keller_c=t_keller_c, t_oben_c=t_oben_c)
                    q = float(psi) * float(L) * float(dT_e)
                    if bucket == "keller" and tb.include_keller:
                        Q_tb_keller += q
                    elif bucket == "oben" and tb.include_oben:
                        Q_tb_oben += q
                    elif bucket == "dachraum" and tb.include_oben:
                        Q_tb_dachraum += q
                    elif bucket == "ground":
                        Q_tb_ground += q
                    elif bucket == "interzone":
                        pass
                    elif tb.include_out:
                        Q_tb_out += q

        elif tb.mode == "percent":
            p = max(0.0, float(tb.percent_of_trans or 0.0))
            Q_tb_out = p * Q_trans_out
            Q_tb_keller = p * Q_trans_keller
            Q_tb_oben = p * Q_trans_oben
            Q_tb_dachraum = p * Q_trans_dachraum
            Q_tb_interzone = 0.0

        # Erdreich-Zuschläge (nur wenn Ground-Modell aktiv und Erdreichflächen existieren)
        Tg_ground_ref, _fg_ground_ref, _ground_ref_method = _effective_ground_temp_for_cfg(ground, "slab", t_in, float(t_out_c))
        dT_ground_ref = max(
            0.0,
            t_in - Tg_ground_ref
        )
        if ground.mode != "none":
            if tb.mode == "delta_u":
                Q_tb_ground = float(tb.delta_u_w_m2k or 0.0) * A_env_ground * dT_ground_ref
            elif tb.mode == "psi":
                Q_tb_ground = float(tb.psi_default_w_mk or 0.0) * L_env_ground * dT_ground_ref
            elif tb.mode == "percent":
                Q_tb_ground = max(0.0, float(tb.percent_of_trans or 0.0)) * Q_trans_ground

        if ground.mode == "perimeter" and (L_env_ground > EPS) and ((Q_trans_ground > 0.0) or (A_env_ground > 0.0)):
            q_per = float(ground.psi_perimeter_w_mk or 0.0) * float(L_env_ground) * float(dT_ground_ref)
            Q_tb_ground += q_per



        # Nachweis: Wärmebrücken als eigene (synthetische) Zeilen je Bucket
        if abs(Q_tb_out) > 1e-12:
            _add_line({
                "line_type": "THERMAL_BRIDGE",
                "element_type": "Wärmebrücken (Außen)",
                "bucket": "out",
                "mode": tb.mode,
                "dT_K": float(dT_out),
                "A_env_m2": float(A_env_out),
                "L_env_m": float(L_env_out),
                "Q_W": float(Q_tb_out),
                "notes": "thermal bridge surcharge",
            })
        if abs(Q_tb_keller) > 1e-12:
            _add_line({
                "line_type": "THERMAL_BRIDGE",
                "element_type": "Wärmebrücken (Keller)",
                "bucket": "keller",
                "mode": tb.mode,
                "dT_K": float(max(0.0, t_in - float(t_keller_c))),
                "A_env_m2": float(A_env_keller),
                "L_env_m": float(L_env_keller),
                "Q_W": float(Q_tb_keller),
                "notes": "thermal bridge surcharge",
            })
        if abs(Q_tb_ground) > 1e-12:
            _add_line({
                "line_type": "THERMAL_BRIDGE",
                "element_type": "Wärmebrücken (Erdreich)",
                "bucket": "ground",
                "mode": ("perimeter" if ground.mode == "perimeter" else tb.mode),
                "dT_K": float(dT_ground_ref),
                "A_env_m2": float(A_env_ground),
                "L_env_m": float(L_env_ground),
                "Q_W": float(Q_tb_ground),
                "notes": "ground surcharge",
            })
        if abs(Q_tb_oben) > 1e-12:
            _add_line({
                "line_type": "THERMAL_BRIDGE",
                "element_type": "Wärmebrücken (Oben)",
                "bucket": "oben",
                "mode": tb.mode,
                "dT_K": float(max(0.0, t_in - float(t_oben_c))),
                "A_env_m2": float(A_env_oben),
                "L_env_m": float(L_env_oben),
                "Q_W": float(Q_tb_oben),
                "notes": "thermal bridge surcharge",
            })
        if abs(Q_tb_dachraum) > 1e-12:
            _add_line({
                "line_type": "THERMAL_BRIDGE",
                "element_type": "Wärmebrücken (Dachraum)",
                "bucket": "dachraum",
                "mode": tb.mode,
                "dT_K": float(max(0.0, t_in - float(t_oben_c))),
                "A_env_m2": float(A_env_dachraum),
                "L_env_m": float(L_env_dachraum),
                "Q_W": float(Q_tb_dachraum),
                "notes": "thermal bridge surcharge",
            })
        Q_tb = Q_tb_out + Q_tb_keller + Q_tb_oben + Q_tb_dachraum + Q_tb_ground


        # Zuschlag zur Transmission addieren
        Q_trans += Q_tb
        Q_trans_out += Q_tb_out
        Q_trans_keller += Q_tb_keller
        Q_trans_oben += Q_tb_oben
        Q_trans_dachraum += Q_tb_dachraum
        Q_trans_ground += Q_tb_ground
        # interzone: keine WB-Zuschläge

        # -------------------------------------------------------------------
        # Lüftung (immer Innenvolumen)
        # -------------------------------------------------------------------
        c_air = float(vent_cfg.c_air)
        n_room = max(0.0, float(r.air_change_1ph or 0.0))
        n_min = max(0.0, float(min_air_change_1ph or 0.0))
        n_inf = max(0.0, float(infiltration_air_change_1ph or 0.0))
        v_room = float(V_in_eff or 0.0)
        vdot_room = n_room * v_room
        vdot_min = n_min * v_room
        vdot_inf = n_inf * v_room
        Q_vent_natural = c_air * max(vdot_room, vdot_min + vdot_inf) * dT_out
        vent_mode = str(ventilation_mode or "natural").strip().lower()
        total_volume = sum(max(float(getattr(room, "volume_m3", 0.0) or 0.0), 0.0) for room in rooms)
        room_share = (v_room / max(total_volume, EPS)) if total_volume > EPS else 0.0
        mech_flow = max(float(mech_supply_m3h or 0.0), float(mech_exhaust_m3h or 0.0))
        hrv_eta = min(1.0, max(0.0, float(heat_recovery_efficiency or 0.0)))
        vdot_mech_room = room_share * mech_flow
        vdot_mech_recovered = vdot_mech_room * (1.0 - hrv_eta)
        vdot_min_uncovered = max(0.0, vdot_min - vdot_mech_room)
        vdot_din_room = vdot_inf + vdot_min_uncovered + vdot_mech_recovered
        Q_vent_mech = c_air * vdot_din_room * dT_out
        Q_vent = Q_vent_mech if (vent_mode == "mechanical" and mech_flow > EPS) else Q_vent_natural
        _add_line({
            "line_type": "VENTILATION",
            "element_type": "Lüftung",
            "bucket": "out",
            "U_W_m2K": None,
            "factor": None,
            "scale": 1.0,
            "dT_K": float(dT_out),
            "A_brutto_m2": 0.0,
            "A_open_m2": 0.0,
            "A_eff_m2": 0.0,
            "Q_W": float(Q_vent),
            "V_in_m3": float(v_room),
            "n_room_1ph": float(n_room),
            "n_min_1ph": float(n_min),
            "n_infiltration_1ph": float(n_inf),
            "Vdot_room_m3h": float(vdot_room),
            "Vdot_min_m3h": float(vdot_min),
            "Vdot_infiltration_m3h": float(vdot_inf),
            "Vdot_mech_room_m3h": float(vdot_mech_room),
            "Vdot_effective_m3h": float(vdot_din_room if (vent_mode == "mechanical" and mech_flow > EPS) else max(vdot_room, vdot_min + vdot_inf)),
            "notes": (
                f"mechanical; c_air={c_air:.3f}; Vdot={mech_flow:.3f} m³/h; share={room_share:.3f}; eta_WRG={hrv_eta:.3f}; Vdot_inf={vdot_inf:.3f}; Vdot_min_uncovered={vdot_min_uncovered:.3f}; Q_nat_ref={Q_vent_natural:.3f} W"
                if (vent_mode == "mechanical" and mech_flow > EPS)
                else f"natural; c_air={c_air:.3f} Wh/(m³K); n_room={n_room:.3f} 1/h; n_min={n_min:.3f} 1/h; n_inf={n_inf:.3f} 1/h; V_in={v_room:.3f} m³"
            ),
        })

        # Bezugsfläche für W/m²
        A_ref = A_in_eff if floor_area_mode == "inner" else A_out_eff
        q_reheat = max(0.0, float(reheat_power_w_m2 or 0.0))
        if q_reheat <= EPS and float(reheat_duration_h or 0.0) > EPS and float(reheat_temp_drop_k or 0.0) > EPS:
            q_reheat = max(0.0, float(reheat_capacity_wh_m2k or 0.0)) * max(0.0, float(reheat_temp_drop_k or 0.0)) / max(float(reheat_duration_h), EPS)
        Q_reheat = q_reheat * max(0.0, float(A_ref or 0.0))
        if Q_reheat > 1e-12:
            _add_line({
                "line_type": "REHEAT",
                "element_type": "Aufheizzuschlag",
                "bucket": "out",
                "U_W_m2K": None,
                "factor": None,
                "scale": 1.0,
                "dT_K": 0.0,
                "A_brutto_m2": float(A_ref),
                "A_open_m2": 0.0,
                "A_eff_m2": float(A_ref),
                "Q_W": float(Q_reheat),
                "notes": f"q_hu={float(q_reheat):.3f} W/m²; A_ref={float(A_ref):.3f} m²; duration={float(reheat_duration_h or 0.0):.2f} h; temp_drop={float(reheat_temp_drop_k or 0.0):.2f} K",
            })

        Q_sum = Q_trans + Q_vent + Q_reheat
        q_W_per_m2 = Q_sum / max(A_ref, EPS)

        out[r.id] = {
            "lines": room_lines,
            "type_sums": type_sums,
            "Q_trans_W": Q_trans,
            "Q_trans_out_W": Q_trans_out,
            "Q_trans_keller_W": Q_trans_keller,
            "Q_trans_oben_W": Q_trans_oben,
            "Q_trans_dachraum_W": Q_trans_dachraum,
            "Q_trans_interzone_W": Q_trans_interzone,
            "Q_trans_ground_W": Q_trans_ground,

            "Q_tb_W": Q_tb,
            "Q_tb_out_W": Q_tb_out,
            "Q_tb_keller_W": Q_tb_keller,
            "Q_tb_oben_W": Q_tb_oben,
            "Q_tb_dachraum_W": Q_tb_dachraum,
            "Q_tb_interzone_W": Q_tb_interzone,
            "Q_tb_ground_W": Q_tb_ground,

            "Q_vent_W": Q_vent,
            "Q_vent_natural_ref_W": Q_vent_natural,
            "Q_vent_mech_W": Q_vent_mech,
            "ventilation_n_room_1ph": n_room,
            "ventilation_n_min_1ph": n_min,
            "ventilation_n_infiltration_1ph": n_inf,
            "ventilation_vdot_room_m3h": vdot_room,
            "ventilation_vdot_min_m3h": vdot_min,
            "ventilation_vdot_infiltration_m3h": vdot_inf,
            "ventilation_vdot_mech_room_m3h": vdot_mech_room,
            "ventilation_vdot_effective_m3h": (vdot_din_room if (vent_mode == "mechanical" and mech_flow > EPS) else max(vdot_room, vdot_min + vdot_inf)),
            "Q_reheat_W": Q_reheat,
            "q_reheat_W_m2": q_reheat,
            "Q_sum_W": Q_sum,
            "Q_W_per_m2": q_W_per_m2,

            "A_openings_m2": A_openings,
            "A_outer_eff_m2": A_outer_eff,

            "A_env_out_m2": A_env_out,
            "A_env_keller_m2": A_env_keller,
            "A_env_oben_m2": A_env_oben,
            "A_env_dachraum_m2": A_env_dachraum,
            "A_env_interzone_m2": A_env_interzone,
            "A_env_ground_m2": A_env_ground,

            "w_in_m": geom_in.w_in_m,
            "h_in_m": geom_in.h_in_m,
            "A_in_m2": A_in_eff,
            "V_in_m3": V_in_eff,

            "A_out_m2": A_out_eff,
            "A_ref_m2": A_ref,

            "floor_area_mode": floor_area_mode,
            "area_shrink_factor": shrink,
            "thickness_mode": thickness_mode,

            "t_keller_c": float(t_keller_c),
            "t_oben_c": float(t_oben_c),

            "tb_mode": tb.mode,
            "tb_delta_u_w_m2k": tb.delta_u_w_m2k,
            "tb_psi_default_w_mk": tb.psi_default_w_mk,
            "tb_percent_of_trans": tb.percent_of_trans,

            "L_env_out_m": L_env_out,
            "L_env_keller_m": L_env_keller,
            "L_env_oben_m": L_env_oben,
            "L_env_interzone_m": L_env_interzone,
            "L_env_dachraum_m": L_env_dachraum,
            "L_env_ground_m": L_env_ground,
            "L_env_sum_m": (L_env_out + L_env_keller + L_env_oben + L_env_ground),

            "ground_mode": ground.mode,
            "ground_temp_c": (None if getattr(ground, "ground_temp_c", None) is None else float(ground.ground_temp_c)),
            "ground_f_slab": float(ground.f_slab),
            "ground_f_wall": float(ground.f_wall),
            "ground_psi_perimeter_w_mk": float(ground.psi_perimeter_w_mk),
            "ground_din_ts_f_slab": float(getattr(ground, "din_ts_f_slab", 0.35)),
            "ground_din_ts_f_wall": float(getattr(ground, "din_ts_f_wall", 0.50)),
            "u_aussenwand_w_m2k": float(u_aussenwand_w_m2k),
            "u_fenster_w_m2k": float(u_fenster_w_m2k),
            "u_tuer_w_m2k": float(u_tuer_w_m2k),
            "u_bodenplatte_w_m2k": float(u_bodenplatte_w_m2k),
            "u_erdberuehrte_wand_w_m2k": float(u_erdberuehrte_wand_w_m2k),
            "ventilation_mode": vent_mode,
            "min_air_change_1ph": n_min,
            "infiltration_air_change_1ph": n_inf,
            "mech_supply_m3h": float(mech_supply_m3h or 0.0),
            "mech_exhaust_m3h": float(mech_exhaust_m3h or 0.0),
            "heat_recovery_efficiency": hrv_eta,
        }

    # --- Gebäude-Hüllflächen: Summen & Details für Reporting ---
    env_summary_rows: List[Dict[str, object]] = []
    total_by_bucket: Dict[str, float] = {}
    total_env_all: float = 0.0
    
    for fk, bmap in env_by_floor.items():
        a_out = float(bmap.get("out", 0.0))
        a_keller = float(bmap.get("keller", 0.0))
        a_oben = float(bmap.get("oben", 0.0))
        a_dachraum = float(bmap.get("dachraum", 0.0))
        a_interzone = float(bmap.get("interzone", 0.0))
        a_ground = float(bmap.get("ground", 0.0))
        a_sum = a_out + a_keller + a_oben + a_dachraum + a_ground  # Interzone ist KEINE Hüllfläche
        env_summary_rows.append({
            "floor": fk,
            "A_env_out_m2": a_out,
            "A_env_keller_m2": a_keller,
            "A_env_oben_m2": a_oben,
            "A_env_dachraum_m2": a_dachraum,
            "A_env_interzone_m2": a_interzone,
            "A_env_ground_m2": a_ground,
            "A_env_sum_m2": a_sum,
        })
        total_by_bucket["out"] = total_by_bucket.get("out", 0.0) + a_out
        total_by_bucket["keller"] = total_by_bucket.get("keller", 0.0) + a_keller
        total_by_bucket["oben"] = total_by_bucket.get("oben", 0.0) + a_oben
        total_by_bucket["dachraum"] = total_by_bucket.get("dachraum", 0.0) + a_dachraum
        total_by_bucket["interzone"] = total_by_bucket.get("interzone", 0.0) + a_interzone
        total_by_bucket["ground"] = total_by_bucket.get("ground", 0.0) + a_ground
        total_env_all += a_sum
    
    # stabile Sortierung: KG, EG, OG/DG, SPEICHER, dann Rest
    floor_order = {"KG": 0, "EG": 1, "OG": 2, "DG": 3, "SPEICHER": 4, "UNBEKANNT": 99}
    env_summary_rows.sort(key=lambda r: (floor_order.get(str(r.get("floor")), 50), str(r.get("floor"))))
    
    out["envelope"] = {
        "summary_by_floor": env_summary_rows,
        "totals": {
            "A_env_out_m2": float(total_by_bucket.get("out", 0.0)),
            "A_env_keller_m2": float(total_by_bucket.get("keller", 0.0)),
            "A_env_oben_m2": float(total_by_bucket.get("oben", 0.0)),
            "A_env_dachraum_m2": float(total_by_bucket.get("dachraum", 0.0)),
            "A_env_interzone_m2": float(total_by_bucket.get("interzone", 0.0)),
            "A_env_ground_m2": float(total_by_bucket.get("ground", 0.0)),
            "A_env_sum_m2": float(total_env_all),
        },
        "details": env_details,
        "notes": [
            "A_eff = A - A_open (nur bei Außenwänden mit Öffnungsabzug).",
            "Interzone-Flächen (zu beheizten Nachbarräumen) sind keine Hüllflächen und werden in A_env_sum nicht gezählt.",
            "Boundary-Buckets: external, ground, basement, attic/unheated, adjacent_heated/interzone werden zusätzlich zu den historischen Buckets im Detailnachweis ausgewiesen.",
            "DG wird als Dachgeschoss geführt; 'SPEICHER' nur, wenn entsprechende Räume/Elemente vorhanden sind.",
            "Erdberührte Flächen (ground) werden separat ausgewiesen.",
        ],
    }

    # -------------------------------------------------------------------
    # Zusatz: Wohnfläche & Volumen je Geschoss (Innenmaße · shrink)
    # -------------------------------------------------------------------
    try:
        out["floor_area"] = calc_floor_living_area_by_floor(
            rooms=rooms,
            results_by_room=out,
            thickness_mode=thickness_mode,
            area_shrink_factor=area_shrink_factor,
        )
    except Exception:
        out["floor_area"] = {
            "by_floor": [],
            "total_m2": 0.0,
            "total_m3": 0.0,
            "by_room": [],
            "meta": {"thickness_mode": str(thickness_mode), "area_shrink_factor": float(area_shrink_factor)},
        }

    return out
