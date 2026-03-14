from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple

from ..domain.models import ElementModel


@dataclass(frozen=True)
class GroundModelCfg:
    """
    Vereinfachtes Erdreichmodell für DIN-nahe Behandlung von Bodenplatte/Kellerwand.

    mode:
      - "none"       : Erdreichmodell aus
      - "simplified" : effektive Erdtemperatur Tg
      - "perimeter"  : simplified + ψ·L·ΔT-Randverlust

    ground_temp_c:
      Feste Erdtemperatur. Wenn ``None``, wird Tg aus ``f_ground`` gebildet.
    """

    mode: Literal["none", "simplified", "perimeter"] = "simplified"
    ground_temp_c: Optional[float] = None
    f_slab: float = 0.40
    f_wall: float = 0.60
    psi_perimeter_w_mk: float = 0.0


def effective_ground_temp(
    t_in_c: float,
    t_out_c: float,
    *,
    fixed_ground_temp_c: Optional[float] = None,
    f_ground: float = 0.40,
) -> float:
    """Return a simplified effective ground temperature."""
    if fixed_ground_temp_c is not None:
        try:
            return float(fixed_ground_temp_c)
        except Exception:
            pass
    return float(t_out_c) + float(f_ground) * (float(t_in_c) - float(t_out_c))


def is_ground_element(e: ElementModel) -> Tuple[bool, str]:
    """
    Erkennt erdberührte Elemente.

    Returns:
      (True, "slab")  für Bodenplatte
      (True, "wall")  für Kellerwand / erdberührte Wand
      (False, "")     sonst
    """
    et = str(getattr(e, "element_type", "") or "").strip().lower()
    et_norm = et.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    meta = str(getattr(e, "meta", "") or "").lower()

    if ("bodenplatte" in et_norm) or ("ground=slab" in meta) or ("erdreich=bodenplatte" in meta):
        return True, "slab"

    if (
        ("kellerwand" in et_norm)
        or ("erdberuehrte wand" in et_norm)
        or ("erdberuhrte wand" in et_norm)
        or ("erdberührte wand" in et)
        or ("ground=wall" in meta)
        or ("erdreich=wand" in meta)
    ):
        return True, "wall"

    return False, ""


# Backward-compatible aliases for existing internal call sites
_effective_ground_temp = effective_ground_temp
_is_ground_element = is_ground_element
