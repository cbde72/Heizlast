from __future__ import annotations
from dataclasses import dataclass
try:
    from PySide6.QtGui import QColor
except Exception:  # pragma: no cover - headless tests
    class QColor:  # minimal fallback
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs


CSV_DELIMITER = ";"
CSV_ENCODING = "utf-8-sig"

PX_PER_M = 60.0  # drawing scale (GUI)

# Heatmap settings
HEATMAP_CAP_W_PER_M2 = 200.0

# Defaults (user-adjustable later)
DEFAULT_U = {
    "Aussenwand": 0.45,
    "Außenwand": 0.45,
    "Fenster": 2.8,
    "Dach": 0.30,
    "Boden": 0.35,
    "Innenwand": 0.0,
}

DEFAULT_FACTOR = {
    "Aussenwand": 1.0,
    "Außenwand": 1.0,
    "Fenster": 1.0,
    "Dach": 1.0,
    "Boden": 1.0,
    "Innenwand": 0.0,
}

ELEMENT_STYLES = {
    "Aussenwand": {"color": QColor(0, 70, 200), "width": 7, "dash": False},
    "Außenwand": {"color": QColor(0, 70, 200), "width": 7, "dash": False},
    "Fenster": {"color": QColor(76, 187, 23), "width": 2, "dash": False},
    "Innenwand": {"color": QColor(120, 120, 120), "width": 2, "dash": True},
    "default": {"color": QColor(200, 0, 0), "width": 3, "dash": False},
}

@dataclass(frozen=True)
class VentilationCfg:
    c_air: float = 0.34  # W/(m³*K)


# ---------------------------
# DIN EN 12831 - Usage defaults (Sprint 1)
# ---------------------------
# Minimal defaults (can be extended). Keys are free text from CSV "usage_type".
# Values: (t_inside_c, air_change_1ph)
ROOM_USAGE_DEFAULTS = {
    "WOHNEN": {"t_inside_c": 20.0, "air_change_1ph": 0.5},
    "SCHLAFEN": {"t_inside_c": 20.0, "air_change_1ph": 0.5},
    "KINDER": {"t_inside_c": 20.0, "air_change_1ph": 0.5},
    "KUECHE": {"t_inside_c": 20.0, "air_change_1ph": 0.7},
    "KÜCHE": {"t_inside_c": 20.0, "air_change_1ph": 0.7},
    "BAD": {"t_inside_c": 24.0, "air_change_1ph": 0.7},
    "WC": {"t_inside_c": 24.0, "air_change_1ph": 0.7},
    "FLUR": {"t_inside_c": 15.0, "air_change_1ph": 0.5},
    "TREPPENHAUS": {"t_inside_c": 15.0, "air_change_1ph": 0.5},
    "ABSTELL": {"t_inside_c": 15.0, "air_change_1ph": 0.3},
    "KELLER": {"t_inside_c": 12.0, "air_change_1ph": 0.3},
    "HWR": {"t_inside_c": 15.0, "air_change_1ph": 0.5},
}

def usage_defaults(usage_type: str):
    if not usage_type:
        return None
    key = str(usage_type).strip().upper()
    return ROOM_USAGE_DEFAULTS.get(key)

@dataclass(frozen=True)
class ProjectCfg:
    """Project-level metadata for DIN traceability and optional climate lookup."""
    location_plz: str = "52396"
    altitude_m: float = 200.0

    # If climate_table_path is set and auto_t_out is True, you may derive t_out from PLZ/altitude.
    climate_table_path: str = ""   # e.g. "./climate_de_plz.csv"
    auto_t_out: bool = False
    lapse_k_per_m: float = 0.0065  # ~6.5 K / 1000 m

    # Free-text source label used in reporting (e.g. "DIN EN 12831-1 NA / Klimatabelle / user")
    t_out_source: str = "DIN EN 12831-1"


def resolve_t_out_c(
    *,
    t_out_c: float | None,
    project: ProjectCfg | None = None,
) -> tuple[float, str]:
    """Resolve design outdoor temperature and a source string.

    Priority:
      1) explicit t_out_c (caller)
      2) climate lookup if project.auto_t_out and project.climate_table_path and project.location_plz set
      3) fallback 0°C
    """
    if t_out_c is not None:
        src = (project.t_out_source if project else "") or "user"
        return float(t_out_c), src

    if project and project.auto_t_out and project.climate_table_path and project.location_plz:
        try:
            from .climate_lookup import lookup_design_t_out_c
        except Exception:
            # standalone fallback import
            from climate_lookup import lookup_design_t_out_c
        t, src = lookup_design_t_out_c(
            plz=project.location_plz,
            altitude_m=project.altitude_m,
            table_path=project.climate_table_path,
            lapse_k_per_m=project.lapse_k_per_m,
        )
        # prefer explicit label if provided
        label = project.t_out_source.strip()
        return float(t), (label + " | " + src) if label else src

    return 0.0, "fallback"

# Drawing
GRID_M = 0.10
HANDLE_SZ_PX = 10.0



'''
Berechnung des U-Werts:
Wärmeleitfähigkeiten (λ) typisch:
Vorsatzverblender (Klinker): λ ≈ 0.5 - 0.8 W/(m·K)

Ich nehme konservativ: 0.7 W/(m·K)

Mineralfaserdämmung (WLG 040): λ ≈ 0.040 W/(m·K)

HBL 2 (24 cm): λ ≈ 0.45 - 0.55 W/(m·K)

Typisch: 0.50 W/(m·K)

Innenputz: λ ≈ 0.70 W/(m·K)

Wärmedurchlasswiderstände (R = d/λ):
Außenluftschicht: Ra = 0.04 m²K/W

Vorsatzverblender (11.5 cm = 0.115 m):

R₁ = 0.115 / 0.7 = 0.164 m²K/W

Luftschicht (4 cm hinterlüftet):

Sehr geringer Widerstand, vernachlässigbar ≈ 0.17 m²K/W

Mineralfaserdämmung (6 cm = 0.06 m):

R₂ = 0.06 / 0.04 = 1.50 m²K/W

HBL 2 (24 cm = 0.24 m):

R₃ = 0.24 / 0.5 = 0.48 m²K/W

Innenputz (1.5 cm): R₄ ≈ 0.015 / 0.7 = 0.021 m²K/W

Innenluftschicht: Ri = 0.13 m²K/W

Gesamtwiderstand (Rtotal):
Rtotal = 0.04 + 0.164 + 0.17 + 1.50 + 0.48 + 0.021 + 0.13
Rtotal ≈ 2.505 m²K/W

U-Wert = 1 / Rtotal:
U = 1 / 2.505 = 0.40 W/(m²K)

Ergebnis:
U-Wert ≈ 0.40 W/(m²K)


'''