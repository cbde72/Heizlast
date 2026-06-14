from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

EPS = 1e-6

FloorAreaMode = Literal["inner", "outer"]
ThicknessMode = Literal["half", "full"]

OUTER_WALL_TYPES = {"Aussenwand", "Außenwand"}
INNER_WALL_TYPES = {"Innenwand"}
WINDOW_TYPES = {"Fenster"}
DOOR_TYPES = {
    "Tür",
    "Tuer",
    "Außentür",
    "Aussentür",
    "Aussentuer",
    "Haustür",
    "Haustuer",
    "Terrassentür",
    "Terrassentuer",
    "Terassentür",
    "Terassentuer",
}


def normalize_element_type(value: object) -> str:
    return str(value or "").strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def is_window_type(value: object) -> bool:
    return normalize_element_type(value) == "fenster"


def is_door_type(value: object) -> bool:
    key = normalize_element_type(value)
    return key in {normalize_element_type(item) for item in DOOR_TYPES} or "tuer" in key or "door" in key


def is_opening_type(value: object) -> bool:
    return is_window_type(value) or is_door_type(value)

WALL_THICKNESS_OUTER_M = 0.455
WALL_THICKNESS_INNER_M = 0.1150


@dataclass(frozen=True)
class ThermalBridgeCfg:
    """
    Wärmebrücken-Zuschlag (vereinfachtes Modell).

    mode:
      - "none"    : keine Wärmebrücken
      - "delta_u" : ΔU-WB Zuschlag auf Hüllfläche: Φ_WB = ΔU · A · ΔT
      - "psi"     : lineare Wärmebrücken: Φ_WB = Σ ψ·L·ΔT
      - "percent" : prozentualer Zuschlag: Φ_WB = p · Φ_trans
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


def meta_get_float(meta: Optional[str], key: str) -> Optional[float]:
    if not meta:
        return None
    try:
        parts: dict[str, str] = {}
        for kv in str(meta).split("|"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                parts[k.strip()] = v.strip()
        if key not in parts:
            return None
        return float(parts[key])
    except Exception:
        return None


_meta_get_float = meta_get_float
