
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

from dataclasses import dataclass
import re
from typing import Dict, List, Literal, Optional, Tuple

from .config import VentilationCfg, DEFAULT_U
from .ground_model import GroundModelCfg, _effective_ground_temp, _is_ground_element
from ..domain.models import ElementModel, RoomModel


# ---------------------------------------------------------------------------
# Grundkonstanten / Typen
# ---------------------------------------------------------------------------

EPS = 1e-6

FloorAreaMode = Literal["inner", "outer"]
ThicknessMode = Literal["half", "full"]

OUTER_WALL_TYPES = {"Aussenwand", "Außenwand"}
INNER_WALL_TYPES = {"Innenwand"}
WINDOW_TYPES = {"Fenster"}

# Wanddicken [m] für Innenmaßbestimmung
WALL_THICKNESS_OUTER_M = 0.455   # 45.5 cm Außenwand
WALL_THICKNESS_INNER_M = 0.1150  # 11.5 cm Innenwand

# Default-U-Werte für Auto-Decken (kannst du später in GUI parametrieren)
DEFAULT_U_KELLERDECKE_W_M2K = 0.45
DEFAULT_U_EG_GESCHOSSDECKE_W_M2K = 0.30   # EG↔DG Zwischendecke
DEFAULT_U_DG_GESCHOSSDECKE_W_M2K = 0.25   # DG→oben (Dachraum)


@dataclass(frozen=True)
class ThermalBridgeCfg:
    """
    Wärmebrücken-Zuschlag (vereinfachtes Modell).

    mode:
      - "none"    : keine Wärmebrücken
      - "delta_u" : ΔU-WB Zuschlag auf Hüllfläche: Φ_WB = ΔU · A · ΔT
      - "psi"     : lineare Wärmebrücken: Φ_WB = Σ ψ·L·ΔT
      - "percent" : prozentualer Zuschlag: Φ_WB = p · Φ_trans

    delta_u_w_m2k:
      Typischer grober Ansatz (projektabhängig!). In vielen Praxisfällen wird z.B.
      0.05 W/(m²K) verwendet — das ist KEIN universeller Normwert, sondern ein
      vereinfachter Zuschlag, den du projekt-/detailabhängig festlegen musst.

    psi_default_w_mk:
      Default ψ für ψ-Modus, wenn kein ψ pro Element vorliegt.

    use_element_meta_psi:
      Wenn True, wird versucht, aus e.meta "psi_w_mk=<...>" zu lesen.
      Optional kann "psi_L_m=<...>" angegeben werden (sonst compute_length()).

    include_*:
      Zuschlag auch für Keller/oben (unbeheizt) anwenden.
    """
    mode: Literal["none", "delta_u", "psi", "percent"] = "none"
    delta_u_w_m2k: float = 0.05
    psi_default_w_mk: float = 0.0
    percent_of_trans: float = 0.0
    use_element_meta_psi: bool = True
    include_out: bool = True
    include_keller: bool = True
    include_oben: bool = True


@dataclass(frozen=True)
class RoomInnerGeometry:
    w_in_m: float
    h_in_m: float
    a_in_m2: float
    v_in_m3: float




# ---------------------------------------------------------------------------
# Meta parsing (dein bestehendes Format: 'a=b|c=d|...')
# ---------------------------------------------------------------------------

def _meta_get_float(meta: Optional[str], key: str) -> Optional[float]:
    if not meta:
        return None
    try:
        parts: Dict[str, str] = {}
        for kv in str(meta).split("|"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                parts[k.strip()] = v.strip()
        if key not in parts:
            return None
        return float(parts[key])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Auto-Decken-Erzeugung (Schnittstelle bleibt)
# ---------------------------------------------------------------------------

def ensure_auto_decks(
    rooms: List[RoomModel],
    elements: List[ElementModel],
    *,
    u_kellerdecke_w_m2k: float = DEFAULT_U_KELLERDECKE_W_M2K,
    u_eg_geschossdecke_w_m2k: float = DEFAULT_U_EG_GESCHOSSDECKE_W_M2K,
    u_dg_geschossdecke_w_m2k: float = DEFAULT_U_DG_GESCHOSSDECKE_W_M2K,
    factor: float = 1.0,
    update_existing: bool = True,
) -> None:
    """
    Erzeugt Decken-Elemente automatisch, wenn keine elements.csv gepflegt wird.

    Regeln:
      - EG: Kellerdecke (gegen unbeh. Keller t_keller_c) + Geschossdecke (gegen DG-Temperatur via meta t_adj_c)
      - DG: Geschossdecke (gegen t_oben_c)
      - KG: keine automatische Decke

    Duplikatschutz über stabile UID: deck_<roomid>_<KG|DG|OBEN>
    """
    # DG-Mitteltemperatur (für EG->DG)
    dg_temps: List[float] = []
    for r in rooms:
        if (getattr(r, "floor", "") or "").strip().upper() == "DG" and getattr(r, "t_inside_c", None) is not None:
            try:
                dg_temps.append(float(r.t_inside_c))
            except Exception:
                pass
    t_dg_mean = (sum(dg_temps) / len(dg_temps)) if dg_temps else None

    #existing = {str(getattr(e, "uid", "") or "") for e in elements}
    by_uid: Dict[str, ElementModel] = {str(getattr(e, "uid", "") or ""): e for e in elements if getattr(e, "uid", None)}

    def _is_auto_deck(e: ElementModel) -> bool:
        m = (getattr(e, "meta", "") or "")
        return ("auto_deck=1" in m) or (str(getattr(e, "uid", "") or "").startswith("deck_"))

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



    def _add(room: RoomModel, *, uid: str, etype: str, U: float, adj_floor: str, t_adj_c: Optional[float]) -> None:
#        if uid in existing:
#            return
        #
        if uid in by_uid:
            if update_existing:
                e = by_uid[uid]
                # nur Auto-Decken anfassen, nie manuell angelegte Bauteile überschreiben
                if _is_auto_deck(e):
                    e.element_type = etype
                    e.u_w_m2k = float(U)
                    e.factor = float(factor)
                    meta = (getattr(e, "meta", "") or "")
                    meta = _set_meta_kv(meta, "auto_deck", "1")
                    meta = _set_meta_kv(meta, "adj_floor", adj_floor)
                    if t_adj_c is not None:
                        meta = _set_meta_kv(meta, "t_adj_c", f"{float(t_adj_c):.3f}")
                    e.meta = meta
            return

        #
        A = max(0.0, float(room.w_m or 0.0) * float(room.h_m or 0.0))
        meta_parts = ["auto_deck=1", f"adj_floor={adj_floor}"]
        if t_adj_c is not None:
            meta_parts.append(f"t_adj_c={float(t_adj_c):.3f}")
        meta = "|".join(meta_parts)

        elements.append(ElementModel(
            room_id=room.id,
            element_type=etype,
            area_m2=A,
            u_w_m2k=float(U),
            factor=float(factor),
            floor=getattr(room, "floor", None),
            x0_m=None, y0_m=None, x1_m=None, y1_m=None,
            length_m=None, height_m=None,
            uid=uid,
            meta=meta,
        ))

        by_uid[uid] = elements[-1]
    #
    # --- Mehrgeschoss-Kopplung EG -> DG über Grundriss-Überlappung ---
    #dg_rooms: List[RoomModel] = [
    #    rr for rr in rooms
    #    if (getattr(rr, "floor", "") or "").strip().upper() == "DG"
    #]
    # neu
    for r in rooms:
        fl = (getattr(r, "floor", "") or "").strip().upper()
        if fl == "EG":
            _add(r, uid=f"deck_{r.id}_KG", etype="Kellerdecke", U=u_kellerdecke_w_m2k, adj_floor="KG", t_adj_c=None)
            t_adj = t_dg_mean if t_dg_mean is not None else float(getattr(r, "t_inside_c", 0.0) or 0.0)
            _add(r, uid=f"deck_{r.id}_DG", etype="Geschossdecke", U=u_eg_geschossdecke_w_m2k, adj_floor="DG", t_adj_c=t_adj)
        elif fl == "DG":
            _add(r, uid=f"deck_{r.id}_OBEN", etype="Speicherdecke", U=u_dg_geschossdecke_w_m2k, adj_floor="OBEN", t_adj_c=None)
            e_top = by_uid.get(f"deck_{r.id}_OBEN")
            if e_top is not None:
                meta = (getattr(e_top, "meta", "") or "")
                meta = _set_meta_kv(meta, "deck_kind", "speicher")
                e_top.meta = meta
    # ende neu
    '''
    def _rect_intersection_area(a: RoomModel, b: RoomModel) -> float:
        ax0, ay0 = float(a.x_m), float(a.y_m)
        ax1, ay1 = ax0 + float(a.w_m), ay0 + float(a.h_m)
        bx0, by0 = float(b.x_m), float(b.y_m)
        bx1, by1 = bx0 + float(b.w_m), by0 + float(b.h_m)
        ix0, iy0 = max(ax0, bx0), max(ay0, by0)
        ix1, iy1 = min(ax1, bx1), min(ay1, by1)
        w = ix1 - ix0
        h = iy1 - iy0
        return (w * h) if (w > 0 and h > 0) else 0.0
    def _best_overlapping_dg_room(eg_room: RoomModel) -> Optional[RoomModel]:
        if not dg_rooms:
            return None
        best = None
        best_a = 0.0
        a_eg = max(0.0, float(eg_room.w_m) * float(eg_room.h_m))
        for dg in dg_rooms:
            a = _rect_intersection_area(eg_room, dg)
            if a > best_a:
                best_a = a
                best = dg
        # Mindestüberdeckung: 25% der EG-Fläche (konservativ)
        if a_eg > 1e-9 and (best_a / a_eg) < 0.25:
            return None
        return best

    for r in rooms:
        fl = (getattr(r, "floor", "") or "").strip().upper()
        if fl == "EG":
            _add(r, uid=f"deck_{r.id}_KG", etype="Kellerdecke", U=u_kellerdecke_w_m2k, adj_floor="KG", t_adj_c=None)
            #t_adj = t_dg_mean if t_dg_mean is not None else float(getattr(r, "t_inside_c", 0.0) or 0.0)
            #_add(r, uid=f"deck_{r.id}_DG", etype="Geschossdecke", U=u_eg_geschossdecke_w_m2k, adj_floor="DG", t_adj_c=t_adj)
            #
            dg = _best_overlapping_dg_room(r)
            if dg is not None and getattr(dg, "t_inside_c", None) is not None:
                t_adj = float(dg.t_inside_c)
                _add(r, uid=f"deck_{r.id}_DG", etype="Geschossdecke", U=u_eg_geschossdecke_w_m2k,
                     adj_floor="DG", t_adj_c=t_adj)
                # Meta: adj_room_id zusätzlich setzen (nur für Auto-Decken)
                # -> wir hängen es nach dem _add an, indem wir by_uid updaten
                try:
                    e_d = by_uid.get(f"deck_{r.id}_DG")
                    if e_d is not None:
                        meta = (getattr(e_d, "meta", "") or "")
                        meta = _set_meta_kv(meta, "adj_room_id", str(dg.id))
                        e_d.meta = meta
                except Exception:
                    pass
            else:
                t_adj = t_dg_mean if t_dg_mean is not None else float(getattr(r, "t_inside_c", 0.0) or 0.0)
                _add(r, uid=f"deck_{r.id}_DG", etype="Geschossdecke", U=u_eg_geschossdecke_w_m2k, adj_floor="DG", t_adj_c=t_adj)
            #
        elif fl == "DG":
            _add(r, uid=f"deck_{r.id}_OBEN", etype="Geschossdecke", U=u_dg_geschossdecke_w_m2k, adj_floor="OBEN", t_adj_c=None)

'''
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
    L = w.compute_length()
    if L is None or L <= EPS:
        return 0.0
    if w.area_m2 is None:
        return 0.0
    return max(0.0, float(w.area_m2) / max(float(L), EPS))


def _opening_area_on_wall_segment(wall: ElementModel, windows: List[ElementModel]) -> float:
    """Opening area to subtract from this wall segment (union with max-height)."""
    wl = _axis_aligned_line(wall)
    if wl is None:
        return 0.0
    orient, c, wa0, wa1 = wl

    intervals: List[Tuple[float, float, float]] = []  # (a0, a1, h)
    for w in windows:
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
        h = _window_height_m(w)
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
    s = (s or "").strip().lower()
    return s.replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")

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
    ensure_auto_decks(rooms, elements)

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
        room_windows = [e for e in room_elements if (e.element_type or "").strip() in WINDOW_TYPES]

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
            nonlocal A_env_out, A_env_keller, A_env_oben, A_env_interzone, A_env_dachraum
            nonlocal L_env_out, L_env_keller, L_env_oben, L_env_interzone, L_env_dachraum
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
                    "uid": str(line.get("uid", "") or ""),
                    "element_type": str(line.get("element_type", "") or ""),
                    "A_m2": float(A_br),
                    "A_open_m2": float(A_op),
                    "A_eff_m2": float(A_eff),
                    "L_m": float(line.get("L_m", 0.0) or 0.0),
                    "U_w_m2k": float(line.get("U_W_m2K", 0.0) or 0.0),
                    "note": str(line.get("notes", "") or ""),
                })

        for e in room_elements:
            U = float(e.u_w_m2k or 0.0)
            f = float(e.factor or 1.0)
            et = (e.element_type or "").strip()

            is_ground, ground_kind = _is_ground_element(e)
            if is_ground and ground.mode != "none":
                fg = float(ground.f_slab if ground_kind == "slab" else ground.f_wall)
                Tg = _effective_ground_temp(
                    t_in,
                    float(t_out_c),
                    fixed_ground_temp_c=getattr(ground, "ground_temp_c", None),
                    f_ground=fg,
                )
                dT_e = max(0.0, t_in - float(Tg))
                bucket = "ground"
            else:
                dT_e, bucket = _deltaT_and_bucket(
                    r, e, t_out_c=t_out_c, t_keller_c=t_keller_c, t_oben_c=t_oben_c
                )

            scale = _edge_scale_for_element(e)

            # Grundfläche A aus Daten
            A = float(e.area_m2 or 0.0)
            # ---------------------------------------------------------------
            # Fallbacks für Außenwand: U/L/A wenn im Datensatz 0 oder fehlt
            # ---------------------------------------------------------------
            if et in OUTER_WALL_TYPES:
                # 1) U-Wert defaulten
                if U <= EPS:
                    U = float(DEFAULT_U.get(et, DEFAULT_U.get("Aussenwand", 0.45)))
                    try:
                        e.u_w_m2k = U
                    except Exception:
                        pass

            # Decken/Bodenflächen explizit aus Raumfläche (damit inner/outer sicher wirkt)
            if _is_kellerdecke(et) or _is_geschossdecke(et):
                A = (A_in_eff if floor_area_mode == "inner" else A_out_eff)
                _acc_env(bucket, A, 0.0)

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
                    "bucket": bucket,
                    "U_W_m2K": float(U),
                    "factor": float(f),
                    "scale": float(scale),
                    "dT_K": float(dT_e),
                    "A_brutto_m2": float(A),          # bereits skaliert
                    "A_open_m2": float(A_open),       # bereits skaliert
                    "A_eff_m2": float(A_eff),
                    "Q_W": float(Q_e),
                    "notes": "outer wall (A_eff = A - openings)",
                })

                Q_trans += Q_e
                if bucket == "ground":
                    Q_trans_ground += Q_e
                elif bucket == "keller":
                    Q_trans_keller += Q_e
                elif bucket == "oben":
                    Q_trans_oben += Q_e
                    Q_trans_dachraum += Q_e
                elif bucket == "interzone":
                    Q_trans_interzone += Q_e
                else:
                    Q_trans_out += Q_e

            else:
                # Fenster: ggf. aus Geometrie ableiten
                if et in WINDOW_TYPES and e.has_geometry():
                    Lw = float(e.compute_length() or 0.0)
                    hw = _window_height_m(e)
                    if Lw > EPS and hw > EPS:
                        A = max(A, Lw * hw)
                    A *= scale
                    _acc_env(bucket, A, Lw * scale)

                # Wände ohne explizite Fläche: aus Länge*Höhe ableiten
                if et not in WINDOW_TYPES and e.has_geometry() and A <= EPS:
                    Lg = float(e.compute_length() or 0.0)
                    if Lg > EPS:
                        A = Lg * room_h
                    A *= scale
                    _acc_env(bucket, A, Lg * scale)
                elif et not in WINDOW_TYPES:
                    # wenn A gesetzt ist, aber Element auf Raumkante liegt, trotzdem skalieren
                    A *= scale
                    _acc_env(bucket, A, float(e.compute_length() or 0.0) * scale if e.has_geometry() else 0.0)

                Q_e = U * A * dT_e * f

                _add_line({
                    "line_type": "TRANSMISSION",
                    "uid": str(getattr(e, "uid", "") or ""),
                    "element_type": et,
                    "bucket": bucket,
                    "U_W_m2K": float(U),
                    "factor": float(f),
                    "scale": float(scale),
                    "dT_K": float(dT_e),
                    "A_brutto_m2": float(A),     # i.d.R. bereits skaliert
                    "A_open_m2": 0.0,
                    "A_eff_m2": float(A),
                    "Q_W": float(Q_e),
                    "notes": "",
                })

                Q_trans += Q_e
                if bucket == "keller":
                    Q_trans_keller += Q_e
                elif bucket == "oben":
                    Q_trans_oben += Q_e
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
        dT_ground_ref = max(
            0.0,
            t_in - _effective_ground_temp(
                t_in,
                float(t_out_c),
                fixed_ground_temp_c=getattr(ground, "ground_temp_c", None),
                f_ground=float(ground.f_slab),
            )
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
                "element_type": "Wärmebrücken (Oben/Dachraum)",
                "bucket": "dachraum",
                "mode": tb.mode,
                "dT_K": float(max(0.0, t_in - float(t_oben_c))),
                "A_env_m2": float(A_env_dachraum),
                "L_env_m": float(L_env_dachraum),
                "Q_W": float(Q_tb_oben),
                "notes": "thermal bridge surcharge",
            })
        Q_tb = Q_tb_out + Q_tb_keller + Q_tb_oben + Q_tb_ground  # ground/oben includes backward-compat; dachraum separate key below


        # Zuschlag zur Transmission addieren
        Q_trans += Q_tb
        Q_trans_out += Q_tb_out
        Q_trans_keller += Q_tb_keller
        Q_trans_oben += Q_tb_oben
        Q_trans_ground += Q_tb_ground
        # interzone: keine WB-Zuschläge

        # -------------------------------------------------------------------
        # Lüftung (immer Innenvolumen)
        # -------------------------------------------------------------------
        Q_vent = float(vent_cfg.c_air) * float(r.air_change_1ph or 0.0) * float(V_in_eff or 0.0) * dT_out
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
            "notes": f"c_air={float(vent_cfg.c_air):.3f} Wh/(m³K); n={float(r.air_change_1ph or 0.0):.3f} 1/h; V_in={float(V_in_eff):.3f} m³",
        })

        Q_sum = Q_trans + Q_vent

        # Bezugsfläche für W/m²
        A_ref = A_in_eff if floor_area_mode == "inner" else A_out_eff
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
            "L_env_sum_m": (L_env_out + L_env_keller + L_env_oben),
            "L_env_interzone_m": L_env_interzone,
            "L_env_dachraum_m": L_env_dachraum,
            "L_env_ground_m": L_env_ground,
            "L_env_sum_m": (L_env_out + L_env_keller + L_env_oben + L_env_ground),

            "ground_mode": ground.mode,
            "ground_temp_c": (None if getattr(ground, "ground_temp_c", None) is None else float(ground.ground_temp_c)),
            "ground_f_slab": float(ground.f_slab),
            "ground_f_wall": float(ground.f_wall),
            "ground_psi_perimeter_w_mk": float(ground.psi_perimeter_w_mk),

            "w_in_m": geom_in.w_in_m,
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


# ---------------------------------------------------------------------------
# Public API: Wohnfläche & Volumen je Geschoss (für GUI/Report)
# ---------------------------------------------------------------------------

def calc_floor_living_area_by_floor(
    *,
    rooms: List[RoomModel],
    results_by_room: Dict[str, dict],
    thickness_mode: ThicknessMode = "full",
    area_shrink_factor: float = 1.0,
) -> Dict[str, object]:
    """Berechnet Wohnfläche *und* Volumen je Geschoss.

    Wohnfläche je Geschoss = Σ A_in_m2 je Raum des Geschosses.
    Volumen je Geschoss     = Σ V_in_m3 je Raum des Geschosses.

    A_in_m2 / V_in_m3 werden im Tool pro Raum berechnet und im results_by_room gespeichert.
    Falls Werte fehlen, wird pauschal über Raum-Außenmaß minus Wandabzug (Außenwanddicke) gefallbackt.
    """
    by_floor_A: Dict[str, float] = {}
    by_floor_V: Dict[str, float] = {}
    by_room: List[Dict[str, object]] = []

    for r in rooms:
        fl = str(getattr(r, "floor", "") or "").strip().upper() or "?"
        rr = results_by_room.get(r.id, {}) if isinstance(results_by_room, dict) else {}

        A_in = None
        V_in = None
        try:
            if isinstance(rr, dict):
                if rr.get("A_in_m2") is not None:
                    A_in = float(rr.get("A_in_m2"))
                if rr.get("V_in_m3") is not None:
                    V_in = float(rr.get("V_in_m3"))
        except Exception:
            A_in = None
            V_in = None

        if (A_in is None) or (V_in is None):
            try:
                w = max(0.0, float(getattr(r, "w_m", 0.0) or 0.0))
                h = max(0.0, float(getattr(r, "h_m", 0.0) or 0.0))
                k = 2.0 if str(thickness_mode) == "full" else 1.0
                w_in = max(0.0, w - k * WALL_THICKNESS_OUTER_M)
                h_in = max(0.0, h - k * WALL_THICKNESS_OUTER_M)
                A_fb = (w_in * h_in) * float(area_shrink_factor)
                if A_in is None:
                    A_in = A_fb
                if V_in is None:
                    hh = max(0.0, float(getattr(r, "height_m", 0.0) or 0.0))
                    V_in = A_fb * hh
            except Exception:
                if A_in is None:
                    A_in = 0.0
                if V_in is None:
                    V_in = 0.0

        by_floor_A[fl] = by_floor_A.get(fl, 0.0) + float(A_in)
        by_floor_V[fl] = by_floor_V.get(fl, 0.0) + float(V_in)

        by_room.append({
            "room_id": str(getattr(r, "id", "")),
            "room": str(getattr(r, "name", "")),
            "floor": fl,
            "A_in_m2": float(A_in),
            "V_in_m3": float(V_in),
        })

    def _floor_key(f: str):
        f = (f or "").upper().strip()
        pri = {"KG": 0, "UG": 0, "EG": 1, "OG": 2, "1.OG": 2, "2.OG": 3, "3.OG": 4, "DG": 9, "OBEN": 10}
        return (pri.get(f, 50), f)

    floors_sorted = [fl for fl, _ in sorted(by_floor_A.items(), key=lambda kv: _floor_key(kv[0]))]
    rows = [{"floor": fl, "A_m2": float(by_floor_A.get(fl, 0.0)), "V_m3": float(by_floor_V.get(fl, 0.0))}
            for fl in floors_sorted]

    return {
        "by_floor": rows,
        "total_m2": float(sum(by_floor_A.values())),
        "total_m3": float(sum(by_floor_V.values())),
        "by_room": by_room,
        "meta": {"thickness_mode": str(thickness_mode), "area_shrink_factor": float(area_shrink_factor)},
    }


def render_floor_living_area_plot_png(
    summary: Dict[str, object],
    png_path: str,
    *,
    title: str = "Wohnfläche & Volumen je Geschoss",
) -> Optional[str]:
    """Erzeugt ein Balkendiagramm (PNG) aus summary['by_floor'].

    - Fläche [m²] links
    - Volumen [m³] rechts (falls vorhanden)
    """
    if _plt is None:
        return None
    try:
        rows = (summary or {}).get("by_floor", []) or []
        floors = [str(r.get("floor", "")) for r in rows]
        A = [float(r.get("A_m2", 0.0) or 0.0) for r in rows]
        V = [float(r.get("V_m3", 0.0) or 0.0) for r in rows]
        if not floors:
            return None

        os.makedirs(os.path.dirname(png_path) or ".", exist_ok=True)

        fig = _plt.figure(figsize=(6.4, 3.0), dpi=160)
        ax1 = fig.add_subplot(111)

        import numpy as _np
        x = _np.arange(len(floors), dtype=float)

        has_V = any(abs(v) > 1e-12 for v in V)
        if has_V:
            w = 0.38
            ax1.bar(x - w/2, A, width=w, label="Wohnfläche [m²]")
            ax2 = ax1.twinx()
            ax2.bar(x + w/2, V, width=w, label="Volumen [m³]")

            ax1.set_ylabel("m²")
            ax2.set_ylabel("m³")

            for i, v in enumerate(A):
                ax1.text(x[i] - w/2, v, f"{v:.1f}", ha="center", va="bottom", fontsize=8)
            for i, v in enumerate(V):
                ax2.text(x[i] + w/2, v, f"{v:.1f}", ha="center", va="bottom", fontsize=8)

            h1, l1 = ax1.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)
        else:
            ax1.bar(x, A)
            ax1.set_ylabel("m²")
            for i, v in enumerate(A):
                ax1.text(x[i], v, f"{v:.1f}", ha="center", va="bottom", fontsize=8)

        ax1.set_xticks(x)
        ax1.set_xticklabels(floors)
        ax1.set_title(title)
        ax1.grid(True, axis="y", linestyle=":", linewidth=0.5)

        fig.tight_layout()
        fig.savefig(png_path)
        _plt.close(fig)
        return png_path
    except Exception:
        try:
            _plt.close("all")
        except Exception:
            pass
        return None